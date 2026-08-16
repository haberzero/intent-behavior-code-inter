"""
core.runtime.vm.handlers.leaf — 叶子 / 基础表达式 CPS handler。

"""
from __future__ import annotations
from typing import Any, Mapping, Dict

from core.runtime.shared.op_constants import (
    OP_MAPPING,
    UNARY_OP_MAPPING,
    AST_OP_MAP,
)
from core.runtime.objects.kernel import (
    IbValue,
    IbLLMUncertain,
    IbUserFunction,
)
from core.runtime.objects.kernel.base import unbox
from core.runtime.objects.kernel.ib_class import IbClass
from core.runtime.objects.kernel.functions import IbBoundMethod
from core.runtime.exceptions import (
    ThrownException,
)
from core.kernel.issue import InterpreterError
from core.runtime.objects.kernel.functions import _runtime_error_code_for
from core.kernel.spec.type_ref import TypeRef as _TypeRef
from core.runtime.objects.primitives import IbNone, IbList, IbTuple, IbDict
from core.runtime.objects.primitives.optional import is_none_value
from core.runtime.shared.llm_result import LLMFuture
from core.runtime.shared.waitable import Waitable, CPSDrivable
from core.runtime.shared.user_call import UserFunctionCall
from core.runtime.shared.signals import GeneratorYield, Signal
from core.runtime.observability.diagnostics import handle_environment_limit
from core.runtime.vm.handlers._shared import (
    _vm_call_fn_callable,
    _vm_invoke_behavior,
    _vm_invoke_llm_function,
    _resolve_iterable,
    _is_llm_uncertain_value,
    _make_uncertain_call_result,
    _raise_uncertain_parse_error,
    _expand_starred,
    _merge_dstar,
    _get_callee_param_specs,
    _resolve_call_arguments_runtime,
)


# ---------------------------------------------------------------------------
# 叶子 / 基础表达式
# ---------------------------------------------------------------------------

def vm_handle_IbConstant(executor, node_uid: str, node_data: Mapping[str, Any]):
    """常量字面量：直接装箱返回。"""
    return executor.registry.box(executor.ec.resolve_value(node_data.get("value")))


def vm_handle_IbName(executor, node_uid: str, node_data: Mapping[str, Any]):
    """变量读取（严格 UID 路径，与 ExprHandler.visit_IbName 同语义）。

    若读到的值是 ``LLMFuture``（dispatch-before-use 残留的待解析占位符），
    在此处阻塞解析并写回，使后续读取为 O(1) 命中。
    """
    sym_uid = executor.ec.get_side_table("node_to_symbol", node_uid)
    if not sym_uid:
        name = node_data.get("id")
        raise RuntimeError(
            f"VM Execution Error: Symbol UID missing for name '{name}'. "
            f"Artifact is corrupted or unanalyzed."
        )
    try:
        val = executor.runtime_context.get_variable_by_uid(sym_uid)
    except Exception as e:
        # 环境限制异常（栈溢出/内存/系统）非语义错误：保留根因传播，不包装
        if handle_environment_limit(e, rc=executor.runtime_context):
            raise
        raise RuntimeError(
            f"VM Execution Error: Symbol with UID '{sym_uid}' "
            f"(name: '{node_data.get('id')}') is not defined."
        ) from e

    # 变量使用点的 LLMFuture 解引用：yield 挂起到 LLM 完成（而非阻塞当前线程），
    # 使单脚本内 LLM 阻塞也可被调度器挂起（对齐 run_many 多根语义）。
    if isinstance(val, LLMFuture):
        sc = executor.service_context
        llm_executor = sc.llm_executor if sc is not None else None
        if llm_executor is not None:
            resolved = yield from llm_executor.resolve_future_cps(val)
            # 若 Future 解析出不确定容器（LLM parse failure），无 llmexcept 保护帧
            # 则抛 LLMParseError（保留 retry_hint/raw_response）；有帧则由
            # llmexcept 机制接管（容器沿变量流动）。
            if _is_llm_uncertain_value(resolved):
                if executor.runtime_context.get_current_llm_except_frame() is None:
                    _raise_uncertain_parse_error(executor, resolved, type_name="unknown")
            # 写回，避免后续读取再次 resolve
            # skip_type_check=True：写回是缓存优化，类型校验在首次赋值时完成
            executor.runtime_context.set_variable_by_uid(sym_uid, resolved, skip_type_check=True)
            val = resolved
    return val


# ---------------------------------------------------------------------------
# 复合表达式（带子节点）
# ---------------------------------------------------------------------------

def vm_handle_IbBinOp(executor, node_uid: str, node_data: Mapping[str, Any]):
    left = yield node_data.get("left")
    if _is_llm_uncertain_value(left):
        return left
    right = yield node_data.get("right")
    if _is_llm_uncertain_value(right):
        return right
    op = node_data.get("op")
    method = OP_MAPPING.get(op)
    if not method:
        raise RuntimeError(f"VM: Unsupported binary op: {op}")
    return left.receive(method, [right])


def vm_handle_IbUnaryOp(executor, node_uid: str, node_data: Mapping[str, Any]):
    operand = yield node_data.get("operand")
    if _is_llm_uncertain_value(operand):
        return operand
    op_symbol = node_data.get("op")
    op = AST_OP_MAP.get(op_symbol, op_symbol)
    method = UNARY_OP_MAPPING.get(op)
    if not method:
        raise RuntimeError(f"VM: Unsupported unary op: {op_symbol}")
    return operand.receive(method, [])


def vm_handle_IbAwaitExpr(executor, node_uid: str, node_data: Mapping[str, Any]):
    """``await <expr>``：显式等待一个 Waitable 完成，返回其结果。

    操作数求值为 Waitable（LLMFuture / HostAwaitable）时，yield 挂起等待其完成，
    恢复后返回 result()。若操作数不是 Waitable（如已在数据流读点自动解析），
    原样返回（幂等）。供容器/非变量位置持有 Waitable 时的显式等待。
    """
    value = yield node_data.get("value")
    if isinstance(value, LLMFuture):
        sc = executor.service_context
        llm_executor = sc.llm_executor if sc is not None else None
        if llm_executor is not None:
            value = yield from llm_executor.resolve_future_cps(value)
    elif isinstance(value, Waitable):
        value = yield value
    return value


def vm_handle_IbYieldExpr(executor, node_uid: str, node_data: Mapping[str, Any]):
    """``yield <expr>``：惰性生成器产出值（阶段 5）。

    求值操作数后 yield ``GeneratorYield(value)`` 标记（而非 child uid）。
    生成器驱动循环识别该标记：暂停生成器体、把 ``value`` 交付给迭代方；
    迭代恢复后 ``send`` 回驱动循环继续推进（保持循环位置/局部变量）。
    无操作数（``yield``）产出 ``None``。
    """
    value = None
    value_uid = node_data.get("value")
    if value_uid:
        value = yield value_uid
        if _is_llm_uncertain_value(value):
            return value
    return (yield GeneratorYield(value))


def vm_handle_IbYieldFromExpr(executor, node_uid: str, node_data: Mapping[str, Any]):
    """``yield from <expr>``：惰性生成器委托（阶段 5 增量）。

    求值操作数（子迭代对象）后，把其每个产出逐值 ``yield GeneratorYield(v)``
    透传给外层生成器消费者。子迭代对象为 ``IbGenerator`` 时表达式值 = 其
    ``return`` 值（``StopIteration.value``，经 ``generic_next`` 透出）；为序列 /
    ``__iter__`` 对象时为 ``None``。委托目标解析与 ``for`` 循环共用
    ``_resolve_iterable``。惰性属性由消费方决定：``next()`` 逐值惰性推进；
    ``for`` 消费经 ``to_list`` 一次性物化（与 ``yield`` 生成器一致）。
    """
    value = None
    value_uid = node_data.get("value")
    if value_uid:
        value = yield value_uid
        if _is_llm_uncertain_value(value):
            return value

    if isinstance(value, Signal):
        return value

    if value is None:
        raise RuntimeError(
            f"yield from: missing operand (uid={node_uid})"
        )

    from core.runtime.objects.kernel.generator import IbGenerator

    if isinstance(value, IbGenerator):
        # 嵌套生成器委托：逐值惰性透传；StopIteration.value = 子生成器 return。
        while True:
            try:
                item = value.generic_next()
            except StopIteration as si:
                ret = si.value
                return ret if ret is not None else executor.registry.get_none()
            yield GeneratorYield(item)

    elements = _resolve_iterable(value)
    if elements is None:
        raise RuntimeError(
            f"yield from: object is not iterable (uid={node_uid})"
        )
    for elem in elements.elements:
        yield GeneratorYield(elem)
    return executor.registry.get_none()


def vm_handle_IbBoolOp(executor, node_uid: str, node_data: Mapping[str, Any]):
    is_or = node_data.get("op") == "or"
    seq_result = executor.registry.get_none()
    for val_uid in node_data.get("values", []):
        val = yield val_uid
        if _is_llm_uncertain_value(val):
            return val
        seq_result = val
        truthy = executor.ec.is_truthy(val)
        if _is_llm_uncertain_value(truthy):
            return truthy
        if is_or and truthy:
            return val
        if not is_or and not truthy:
            return val
    return seq_result


def vm_handle_IbIfExp(executor, node_uid: str, node_data: Mapping[str, Any]):
    cond = yield node_data.get("test")
    if _is_llm_uncertain_value(cond):
        return cond
    truthy = executor.ec.is_truthy(cond)
    if _is_llm_uncertain_value(truthy):
        return truthy
    if truthy:
        res = yield node_data.get("body")
        return res
    return (yield node_data.get("orelse"))


def vm_handle_IbCompare(executor, node_uid: str, node_data: Mapping[str, Any]):
    """比较运算（支持链式 + in / not in / is / is not）。"""

    left = yield node_data.get("left")
    if _is_llm_uncertain_value(left):
        return left
    ops = node_data.get("ops", [])
    comparators = node_data.get("comparators", [])
    current_left = left
    final_res = executor.registry.box(True)

    for op, comparator_uid in zip(ops, comparators):
        right = yield comparator_uid
        if _is_llm_uncertain_value(right):
            return right

        if op == "in":
            contained = right.receive("__contains__", [current_left])
            native = unbox(contained)
            cmp_res = executor.registry.box(bool(native))
        elif op == "not in":
            contained = right.receive("__contains__", [current_left])
            native = unbox(contained)
            cmp_res = executor.registry.box(not bool(native))
        elif op == "is":
            # None 语义检测双向对称：左右任一为字面量 None（IbNone）时，
            # 判断另一侧是否 None 语义（空 Optional / 裸 None 均为 None）。
            if isinstance(right, IbNone) or isinstance(current_left, IbNone):
                cmp_res = executor.registry.box(
                    is_none_value(current_left) and is_none_value(right)
                )
            elif isinstance(right, IbLLMUncertain):
                cmp_res = executor.registry.box(isinstance(current_left, IbLLMUncertain))
            else:
                cmp_res = executor.registry.box(current_left is right)
        elif op == "is not":
            if isinstance(right, IbNone) or isinstance(current_left, IbNone):
                cmp_res = executor.registry.box(
                    not (is_none_value(current_left) and is_none_value(right))
                )
            elif isinstance(right, IbLLMUncertain):
                cmp_res = executor.registry.box(not isinstance(current_left, IbLLMUncertain))
            else:
                cmp_res = executor.registry.box(current_left is not right)
        else:
            method = OP_MAPPING.get(op)
            if not method:
                raise RuntimeError(f"VM: Unsupported comparison: {op}")
            cmp_res = current_left.receive(method, [right])

        truthy = executor.ec.is_truthy(cmp_res)
        if _is_llm_uncertain_value(truthy):
            return truthy
        if not truthy:
            return cmp_res
        final_res = cmp_res
        current_left = right

    return final_res


def vm_handle_IbCall(executor, node_uid: str, node_data: Mapping[str, Any]):
    """函数调用：CPS 求值函数对象与实参（含 *expr/**expr splat），
    经统一实参绑定器解析后按声明序绑定；IbFnCallable 完全内联 CPS 执行，
    其他 callable 仍通过 call() 同步完成。
    """
    func = yield node_data.get("func")
    if _is_llm_uncertain_value(func):
        return func

    # --- 求值位置实参（*expr 序列解包展开） ---
    positional = []
    for a_uid in node_data.get("args", []):
        a_data = executor.ec.get_node_data(a_uid)
        if a_data and a_data.get("_type") == "IbStarred":
            starred = yield a_data.get("value")
            if _is_llm_uncertain_value(starred):
                return starred
            positional.extend(_expand_starred(executor, starred))
        else:
            arg = yield a_uid
            if _is_llm_uncertain_value(arg):
                return arg
            positional.append(arg)

    # --- 求值具名实参（**expr 字典解包合并） ---
    keyword_map = {}
    for kw_uid in node_data.get("keywords", []):
        kw_data = executor.ec.get_node_data(kw_uid)
        kw_value = yield kw_data.get("value")
        if _is_llm_uncertain_value(kw_value):
            return kw_value
        kw_name = (kw_data or {}).get("arg")
        if kw_name is None:
            _merge_dstar(executor, keyword_map, kw_value)
        else:
            keyword_map[kw_name] = kw_value

    # --- 统一实参解析：位置 → 具名 → 默认填充 → varargs/varkw ---
    specs = _get_callee_param_specs(executor, func)
    if specs is not None:
        args = yield from _resolve_call_arguments_runtime(
            executor, specs, positional, keyword_map
        )
    else:
        # 无静态签名（内置构造器 / axiom-backed / 运行时 callable）：
        # 保持位置直传，splat 已展开、具名实参忽略（与语义层动态策略一致）。
        args = positional

    # IbFnCallable（lambda/snapshot）完全 CPS 内联
    if isinstance(func, IbValue) and func.ib_class.name == "fn_callable":
        result = yield from _vm_call_fn_callable(executor, func, args)
        return result

    # IbBehavior：CPS 内联以使 LLM 帧受 VM 调度管理。
    if isinstance(func, IbValue) and func.ib_class.name == "behavior":
        result = yield from _vm_invoke_behavior(executor, func, args)
        return result

    # IbUserFunction（普通/LLM 统一）：统一走 trampoline 调用。
    # 不 yield from 生成器（会嵌套 Python 栈），而是 yield 函数调用请求，
    # 由 _drive_loop_gen 把函数体作为独立 VMTask 压栈——深递归 Python 深度恒定。
    # 惰性生成器（含 yield，D-08 自标记）：调用产出 IbGenerator（不执行体），
    # 迭代驱动函数体、yield 点产出值。
    if isinstance(func, IbUserFunction):
        if func.is_generator:
            from core.runtime.objects.kernel.generator import IbGenerator
            from core.runtime.shared.user_call import UserFunctionCall as _UFC

            driver = yield _UFC(func, args)
            gen_class = executor.registry.get_class("generator")
            if gen_class is None:
                raise RuntimeError("generator class not registered (bootstrap invariant violated)")
            return IbGenerator(gen_class, driver)
        result = yield UserFunctionCall(func, args)
        return result

    # 用户方法调用 CPS 化：解包 IbBoundMethod（obj.method(x)）。
    # 把 .method 提取出来经 CPS trampoline 调用，并把 receiver 作为 self 注入
    # （与 _vm_call_user_function 的 receiver 契约一致）——嵌套调度器路径
    # （方法含 Waitable 时死锁、深递归方法嵌套 Python 栈）不可达。
    if isinstance(func, IbBoundMethod):
        method = func.method
        receiver = func.receiver
        if isinstance(method, IbUserFunction):
            if method.is_generator:
                from core.runtime.objects.kernel.generator import IbGenerator
                from core.runtime.shared.user_call import UserFunctionCall as _UFC

                driver = yield _UFC(method, args, receiver)
                gen_class = executor.registry.get_class("generator")
                if gen_class is None:
                    raise RuntimeError("generator class not registered (bootstrap invariant violated)")
                return IbGenerator(gen_class, driver)
            result = yield UserFunctionCall(method, args, receiver)
            return result

    try:
        # 统一走 receive('__call__') 协议分派（base.receive 内置 .call 兜底），
        # 不再用 hasattr 探测双路径（单一协议分派）。
        result = func.receive("__call__", args)
        # native 调用返回 Waitable（宿主异步句柄）→ 挂起本根，让调度器等待其完成，
        # 而非阻塞当前线程。恢复后 result 为完成值（如 collect 的 dict）。
        # 例外：类构造返回的**句柄** Waitable（如 thread(...) 的 IbThread）不自动
        # 挂起——否则构造即被解析成完成结果、丢失句柄。但 CPSDrivable 构造（用户类
        # 的 _ClassInstantiateDrive）仍需帧内驱动，故按 CPSDrivable 结构性协议区分：
        # CPSDrivable → 帧内驱动（无论 func 是否 IbClass）；纯 Waitable → 仅非
        # IbClass 时 auto-yield（IbClass 的纯 Waitable = 句柄，原样返回）。
        if isinstance(result, Waitable):
            if isinstance(result, CPSDrivable):
                result = yield from result.cps_drive(executor)
            elif not isinstance(func, IbClass):
                result = yield result
        return result
    except ThrownException:
        # 用户代码主动抛出的语言级异常必须穿透函数调用边界，由 IbTry / 顶层
        # try-except 体系按 IBCI 类型匹配处理；不得包装成 Python RuntimeError，
        # 否则会丢失 IBCI 异常类型。
        raise
    except Exception as e:
        # 环境限制异常（栈溢出/内存/系统）非语义错误：保留根因传播，不包装
        if handle_environment_limit(e, rc=executor.runtime_context):
            raise
        # 与 ExprHandler.visit_IbCall 同语义：对外汇报为通用调用错误。
        # 原生 Python 异常类型（AttributeError/IndexError/KeyError 等）映射为
        # 具体诊断码（幽灵码发射：属性缺失 → RUN_ATTRIBUTE_ERROR 等），
        # 替代裸 RUN_GENERIC_ERROR/VM: Call failed。
        code = _runtime_error_code_for(e)
        if code is not None:
            raise InterpreterError(str(e), error_code=code) from e
        raise RuntimeError(f"VM: Call failed: {e}") from e


def vm_handle_IbAttribute(executor, node_uid: str, node_data: Mapping[str, Any]):
    value = yield node_data.get("value")
    if _is_llm_uncertain_value(value):
        return value
    attr = node_data.get("attr")
    return value.receive("__getattr__", [executor.registry.box(attr)])


def vm_handle_IbSubscript(executor, node_uid: str, node_data: Mapping[str, Any]):
    value = yield node_data.get("value")
    if _is_llm_uncertain_value(value):
        return value
    slice_obj = yield node_data.get("slice")
    if _is_llm_uncertain_value(slice_obj):
        return slice_obj
    return value.receive("__getitem__", [slice_obj])


def vm_handle_IbTuple(executor, node_uid: str, node_data: Mapping[str, Any]):
    elts = []
    for e_uid in node_data.get("elts", []):
        elt = yield e_uid
        if _is_llm_uncertain_value(elt):
            return elt
        elts.append(elt)
    value = executor.registry.box(tuple(elts))
    return _bind_container_specialization(executor, node_uid, value, "tuple")


def vm_handle_IbListExpr(executor, node_uid: str, node_data: Mapping[str, Any]):
    elts = []
    for e_uid in node_data.get("elts", []):
        elt = yield e_uid
        if _is_llm_uncertain_value(elt):
            return elt
        elts.append(elt)
    value = executor.registry.box(elts)
    return _bind_container_specialization(executor, node_uid, value, "list")


# === 简单表达式扩展 ===

def _bind_container_specialization(executor, node_uid: str, value, container_kind: str):
    """把容器字面量值绑定到编译期特化类型。

    编译期 ``list[int] li = [1,2]`` 使字面量节点 ``node_to_type = list[int]``；
    此处查侧表：若节点类型是内置泛型特化（LIST/DICT/TUPLE 等），把值对象
    重绑定到水化特化类（``get_class("list[int]")``，未注册则经 ``_specialize``
    创建），使 ``IbValue.type_ref`` 带实参（type() 内省一致 + 运行时类型安全）。

    无特化类型（裸 list/dict/tuple）→ 原样返回（既有行为）。非容器目标或
    节点类型缺失 → 原样返回（保守语义）。
    """
    from core.kernel.spec.base import TypeKind

    if value is None or not isinstance(value, IbValue):
        return value
    if getattr(value, "ib_class", None) is None:
        return value
    if value.ib_class.name != container_kind:
        return value
    node_spec = executor.ec.get_side_table("node_to_type", node_uid)
    if node_spec is None or not isinstance(node_spec, object):
        return value
    try:
        kind = getattr(node_spec, "kind", None)
        if kind != getattr(TypeKind, container_kind.upper()).value:
            return value
        # 特化类（list[int]）水化；裸类型（list）node_spec.name == "list" 无特化。
        # [Module Identity] 特化名用 qualified（内置容器 module_path=None，同裸名）。
        specialized_name = node_spec.qualified_name
        if specialized_name == container_kind:
            return value
        base_cls = executor.registry.get_class(container_kind)
        if base_cls is None:
            return value
        spec_reg = executor.registry.get_metadata_registry()
        if spec_reg is None or spec_reg.resolve(specialized_name) is None:
            return value
        specialized_cls = executor.registry.get_class(specialized_name)
        if specialized_cls is None:
            specialized_cls = base_cls._specialize(
                _slice_type_objs_for(executor, node_spec)
            )
            if specialized_cls is None:
                return value
        # _specialize 对内置泛型 sealed 时可能回落 boxed 字符串（嵌套实参
        # 语义），非 IbClass 时不可作值对象 ib_class——保守回退基类值。
        if not isinstance(specialized_cls, IbClass):
            return value
        value.ib_class = specialized_cls
        value.type_ref = _TypeRef.from_spec(node_spec)
        _wrap_container_elements(value, node_spec, executor.registry)
    except Exception:
        # 特化水化失败保守回退（保留基类值，不破坏程序执行）。
        return value
    return value


def _wrap_container_elements(value, node_spec, registry):
    """按容器元素类型包装元素（统一 Optional 值模型）。

    ``list[Optional[int]] li = [None]`` / ``dict[str, Optional[int]]`` /
    ``tuple[Optional[int], str]`` 等：元素声明为 Optional 时，写入前把每个
    元素按元素类型包装（空值 → ``IbOptional(is_some=False)``），使容器元素
    与局部变量/参数/返回路径的空值表示一致（``li[0] is None`` / ``is_none()``
    可用）。非 Optional 元素类型原样保留。``_bind_container_specialization``
    已把容器绑定特化类（spec 携带元素类型），据此包装。
    """
    from core.kernel.spec.base import TypeKind
    from core.runtime.objects.primitives.optional import wrap_optional

    if value is None or node_spec is None:
        return
    kind = getattr(node_spec, "kind", None)
    spec_reg = registry.get_metadata_registry() if registry else None

    def _resolve(ref):
        if spec_reg is None or ref is None:
            return None
        return spec_reg.resolve_typeref(ref)

    try:
        if kind == TypeKind.LIST.value and isinstance(value, IbList):
            elem_spec = _resolve(getattr(node_spec, "element_type", None))
            if elem_spec is not None:
                for i, elt in enumerate(value.elements):
                    value.elements[i] = wrap_optional(elt, elem_spec, registry)
        elif kind == TypeKind.TUPLE.value and isinstance(value, IbTuple):
            positional = getattr(node_spec, "positional_element_types", None) or []
            if positional:
                new_elts = list(value.elements)
                for i, (elt, ref) in enumerate(zip(value.elements, positional)):
                    elem_spec = _resolve(ref)
                    if elem_spec is not None:
                        new_elts[i] = wrap_optional(elt, elem_spec, registry)
                # tuple 不可变：重建而非原地写（元素包装后整体替换 elements）。
                value.elements = tuple(new_elts)
            else:
                elem_spec = _resolve(getattr(node_spec, "element_type", None))
                if elem_spec is not None:
                    value.elements = tuple(
                        wrap_optional(elt, elem_spec, registry) for elt in value.elements
                    )
        elif kind == TypeKind.DICT.value and isinstance(value, IbDict):
            val_spec = _resolve(getattr(node_spec, "value_type", None))
            if val_spec is not None:
                for k in value.fields:
                    value.fields[k] = wrap_optional(value.fields[k], val_spec, registry)
    except Exception:
        # 元素包装失败保守回退（保留原值，不破坏程序执行）。
        return


def _slice_type_objs_for(executor, node_spec):
    """从特化 spec 提取 slice 类型标识对象列表（供 _specialize 水化特化类）。

    与 ``IbClass._slice_type_objs`` 同构：把特化实参（element_type /
    positional_element_types / key_type+value_type / value_type）转换为
    IbClass 标识对象。实参为结构化 TypeRef（``list[list[int]]``
    的 element_type = ``TypeRef('list',(int,))``）时沿 args 递归解析特化类
    （``get_class("list[int]")``），而非按 head 取基类——否则嵌套实参静默
    降级为基类，特化类水化失败。
    """
    from core.kernel.spec.base import TypeKind

    args: list = []
    kind = node_spec.kind
    if kind == TypeKind.LIST.value:
        args = [node_spec.element_type]
    elif kind == TypeKind.TUPLE.value:
        pos = getattr(node_spec, "positional_element_types", None) or []
        args = list(pos) or [node_spec.element_type]
    elif kind == TypeKind.DICT.value:
        args = [node_spec.key_type, node_spec.value_type]
    else:
        args = [getattr(node_spec, "value_type", None)]
    out = []
    for ref in args:
        if ref is None or ref.head in ("any", "auto", ""):
            continue
        cls = _resolve_specialized_class(executor, ref)
        if cls is not None:
            out.append(cls)
    return out


def _resolve_specialized_class(executor, ref):
    """把类型实参 TypeRef 解析为 IbClass（结构化嵌套递归，module 感知）。

    - 无实参（``int``）：``get_class("int", module=ref.module)``。
    - 有实参（``list[int]`` / ``geo.Box[int]``）：先查特化类
      ``get_class(ref.qualified_name)``（module 限定键）；未水化则经基类
      ``_specialize`` 按结构化实参创建（嵌套实参结构保真，不再按
      head 降级）。跨模块用户类实参经 ``ref.module`` 命中 qualified 键。
    """
    if ref.args:
        specialized_name = ref.qualified_name
        cls = executor.registry.get_class(specialized_name)
        if cls is not None:
            return cls
        base_cls = executor.registry.get_class(ref.head, module=ref.module)
        if base_cls is None:
            return None
        try:
            sub_args = [_resolve_specialized_class(executor, a) for a in ref.args]
            if any(a is None for a in sub_args):
                return None
            return base_cls._specialize(sub_args)
        except Exception:
            return None
    return executor.registry.get_class(ref.head, module=ref.module)


def vm_handle_IbDict(executor, node_uid: str, node_data: Mapping[str, Any]):
    """字典字面量 -> 装箱 dict（以 native key 索引）。"""
    keys = node_data.get("keys", [])
    values = node_data.get("values", [])
    data: Dict[Any, Any] = {}
    for k_uid, v_uid in zip(keys, values):
        if k_uid:
            key_obj = yield k_uid
        else:
            key_obj = executor.registry.get_none()
        if _is_llm_uncertain_value(key_obj):
            return key_obj
        val_obj = yield v_uid
        if _is_llm_uncertain_value(val_obj):
            return val_obj
        native_key = unbox(key_obj)
        data[native_key] = val_obj
    value = executor.registry.box(data)
    return _bind_container_specialization(executor, node_uid, value, "dict")


def vm_handle_IbSlice(executor, node_uid: str, node_data: Mapping[str, Any]):
    """切片对象（lower/upper/step 任意可空）-> Python slice 装箱。"""
    lower_uid = node_data.get("lower")
    upper_uid = node_data.get("upper")
    step_uid = node_data.get("step")

    l_val = None
    u_val = None
    s_val = None
    if lower_uid:
        lo = yield lower_uid
        if _is_llm_uncertain_value(lo):
            return lo
        l_val = unbox(lo)
    if upper_uid:
        up = yield upper_uid
        if _is_llm_uncertain_value(up):
            return up
        u_val = unbox(up)
    if step_uid:
        st = yield step_uid
        if _is_llm_uncertain_value(st):
            return st
        s_val = unbox(st)
    return executor.registry.box(slice(l_val, u_val, s_val))


def vm_handle_IbCastExpr(executor, node_uid: str, node_data: Mapping[str, Any]):
    """类型强转：与 ExprHandler.visit_IbCastExpr 同语义。

    若目标类型描述符或目标 IbClass 缺失，按既有保守语义直接返回原值。

    LLM-aware: 当转换失败且处于 llmexcept 保护帧内时，返回
    ``IbLLMCallResult(is_certain=False)`` 不确定容器以便 llmexcept 重试，
    而非直接抛出异常。LLM 不确定性检测属于 VM handler 层职责，
    不应由原始包装层越层访问。
    """
    value = yield node_data.get("value")
    if _is_llm_uncertain_value(value):
        return value
    target_descriptor = executor.ec.get_side_table("node_to_type", node_uid)
    if not target_descriptor:
        return value
    target_class = executor.registry.get_class(
        target_descriptor.name, module=target_descriptor.module_path
    )
    if not target_class:
        return value
    try:
        return value.receive("cast_to", [target_class])
    except Exception as e:
        rc = executor.runtime_context
        if rc is not None and rc.get_current_llm_except_frame() is not None:
            raw_val = getattr(value, 'value', '') if hasattr(value, 'value') else str(value)
            return _make_uncertain_call_result(
                executor.registry,
                raw_response=raw_val,
                retry_hint=f"类型强制转换失败: {str(e)}",
            )
        raise


def vm_handle_IbFilteredExpr(executor, node_uid: str, node_data: Mapping[str, Any]):
    """带过滤条件的表达式（while ... if filter 等）。

    与 ExprHandler.visit_IbFilteredExpr 同语义：主表达式为假则短路返回；
    过滤条件为假则返回 IbNone。任何子表达式产生不确定容器时透传。
    """
    result = yield node_data.get("expr")
    if _is_llm_uncertain_value(result):
        return result
    result_truthy = executor.ec.is_truthy(result)
    if _is_llm_uncertain_value(result_truthy):
        return result_truthy
    if not result_truthy:
        return result
    filter_val = yield node_data.get("filter")
    if _is_llm_uncertain_value(filter_val):
        return filter_val
    filter_truthy = executor.ec.is_truthy(filter_val)
    if _is_llm_uncertain_value(filter_truthy):
        return filter_truthy
    if not filter_truthy:
        return executor.registry.get_none()
    return result
