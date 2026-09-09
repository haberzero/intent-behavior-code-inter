"""
core.runtime.vm.jit_codegen — P4 真 JIT：热直线体 Python codegen（修复版，subagent B1-B7）。

为符合安全子集判据的 while 循环体生成**直接执行体**（Python 函数），绕开每节点 CPS
生成器协议（gen.send/StopIteration，P1 profile 主导成本），保持 §11 不变量：
- 统一执行入口（#1）：codegen 体在 CPS 循环内被 vm_handle_IbWhile 调用，非独立通道；
- 控制流数据化 Signal（#2）：v1 体无 return/break/continue → 返回 None；
- 协议分派 receive（#6）：binop/比较经 receive（禁 isinstance(IbXxx) 分派/内联 op 特化）。

安全子集（v1，whitelist 判据）：体语句 ∈ {IbAssign（单目标简单名，llmexcept None），
IbIf（llmexcept None，test ∈ ExprSet，body/orelse 递归符合），IbPass}；ExprSet =
{IbConstant, IbName（node_to_symbol + 读取干净）, IbBinOp, IbUnaryOp, IbCompare（单比较）}。
排除 嵌套 while/for/函数调用/意图注解/复合赋值/多目标/下标/属性/raise/try/yield/await。

声呐（B4）：模块节点池含 IbBehaviorExpr → LLM 污点（LLMFuture/不确定容器）可能 → 不安全，
返回 None（走 CPS）。body 语句 llmexcept_handler 须 None（保护语句重试协议不可绕过）。

修复清单（subagent B1-B7）：
- B1 常量装箱 ``box(native)``（box=registry.box 绑定方法；原 ``box(None, native)`` 误把
  native 当 memo、val=None → 每常量返 IbNone）。
- B2 赋值 ``rt.set_variable_by_uid(uid, val)``（去 skip_type_check=True——该 flag 是
  LLMFuture 写回内部标志，误用跳过运行时类型检查致语义分歧）。
- B3 异常位置：生成体逐语句 ``loc[0] = <stmt_uid>``；调用点捕获异常后经单一权威
  ``_annotate_exception_location``（复用 vm_executor，避免 while 节点误导位置）。
- B4 声呐（上）。
- B5 判据扩展 IbIf/IbCompare（branch 程序 while 体 [IbIf, IbAssign] 由此可 codegen）。
- B6 无调试脚手架残留。
- B7 ``exec`` 注入 ``__builtins__: {}``（生成体全局闭包不泄漏内建）。
"""
from __future__ import annotations
from typing import Any, List, Optional

from core.runtime.shared.op_constants import OP_MAPPING, UNARY_OP_MAPPING, AST_OP_MAP

# IbCompare op 符号 → dunder（复用 OP_MAPPING 比较 op）
_COMPARE_OPS = {
    '==': '__eq__', '!=': '__ne__', '<': '__lt__', '<=': '__le__', '>': '__gt__', '>=': '__ge__',
}


def _gen_expr(expr_uid, ec, box, consts, counter):
    """生成子表达式 Python 源码片段；不可 codegen 返回 None。

    consts：常量名 → 装箱 IbValue（生成期预计算，B1：box(native)）；counter：常量计数。
    """
    if expr_uid is None:
        return None
    node_data = ec.get_node_data(expr_uid)
    if not node_data:
        return None
    node_type = node_data.get("_type")

    if node_type == "IbConstant":
        native = node_data.get("value")
        name = f"_C{counter[0]}"
        counter[0] += 1
        consts[name] = box(native)  # B1
        return name

    if node_type == "IbName":
        sym_uid = ec.get_side_table("node_to_symbol", expr_uid)
        if not sym_uid:
            return None
        return f"rt.get_variable_by_uid({sym_uid!r})"

    if node_type == "IbBinOp":
        left_expr = _gen_expr(node_data.get("left"), ec, box, consts, counter)
        right_expr = _gen_expr(node_data.get("right"), ec, box, consts, counter)
        if left_expr is None or right_expr is None:
            return None
        method = OP_MAPPING.get(node_data.get("op"))
        if not method:
            return None
        return f"({left_expr}).receive({method!r}, [{right_expr}])"

    if node_type == "IbUnaryOp":
        operand_expr = _gen_expr(node_data.get("operand"), ec, box, consts, counter)
        if operand_expr is None:
            return None
        op = AST_OP_MAP.get(node_data.get("op"), node_data.get("op"))
        method = UNARY_OP_MAPPING.get(op)
        if not method:
            return None
        return f"({operand_expr}).receive({method!r}, [])"

    if node_type == "IbCompare":
        # v1 单比较：left op comparator（IbCompare 结构：left/ops/comparators）；
        # 链式比较（ops > 1）→ None，走 CPS。
        ops = node_data.get("ops") or []
        left = node_data.get("left")
        comparators = node_data.get("comparators") or []
        if len(ops) != 1 or left is None or len(comparators) != 1:
            return None
        l_expr = _gen_expr(left, ec, box, consts, counter)
        r_expr = _gen_expr(comparators[0], ec, box, consts, counter)
        if l_expr is None or r_expr is None:
            return None
        method = _COMPARE_OPS.get(ops[0]) or OP_MAPPING.get(ops[0])
        if not method:
            return None
        return f"({l_expr}).receive({method!r}, [{r_expr}])"

    return None


def _module_has_behavior_expr(ec) -> bool:
    """B4 声呐：模块节点池含 IbBehaviorExpr（LLM 污点）→ codegen 不安全。

    节点池经 ec.node_pool（dict）访问——ec._nodes 为历史属性（未 populate）。
    """
    pool = getattr(ec, "node_pool", None)
    if not pool:
        return False
    for uid in list(pool.keys()):
        nd = ec.get_node_data(uid)
        if nd and nd.get("_type") == "IbBehaviorExpr":
            return True
    return False


def _stmt_eligible(stmt_uid, ec, registry, _depth=0, allow_break_continue=False):
    """单语句符合 codegen 安全子集判据（B4/B5 + v1.1 控制流）。

    allow_break_continue（v1.1）：IbBreak/IbContinue 仅在 v1.5 cond-codegen（while True
    循环体）中合法——Python break/continue 作用于 while True 循环；v1.0 体 codegen
    （per-iteration 调用）中 break/continue 会作用于函数体（非循环）→ 非法。
    """
    if _depth > 8:
        return False
    node_data = ec.get_node_data(stmt_uid) if stmt_uid else None
    if not node_data:
        return False
    if node_data.get("llmexcept_handler"):
        return False
    node_type = node_data.get("_type")
    if node_type in ("IbBreak", "IbContinue"):
        return allow_break_continue
    if node_type == "IbAssign":
        targets = node_data.get("targets") or []
        if len(targets) != 1:
            return False
        t_data = ec.get_node_data(targets[0])
        if not t_data or t_data.get("_type") not in ("IbName", "IbTypeAnnotatedExpr"):
            return False
        return _gen_expr(node_data.get("value"), ec, registry.box, {}, [0]) is not None
    if node_type == "IbIf":
        if _gen_expr(node_data.get("test"), ec, registry.box, {}, [0]) is None:
            return False
        for sub in (node_data.get("body") or [], node_data.get("orelse") or []):
            for suid in sub:
                if not _stmt_eligible(suid, ec, registry, _depth + 1, allow_break_continue):
                    return False
        return True
    if node_type == "IbPass":
        return True
    return False


def _gen_body_source(stmt_uids, ec, box, allow_break_continue=False):
    """生成直线语句序列的 Python 源码行 + 常量表；不可 codegen 返回 None。

    返回 ``(src_lines, consts)``；调用方（generate_jit_body / generate_jit_loop）据此
    编译函数。``src_lines`` 缩进 4 格（函数体一级），``loc[0]`` 逐语句设值（B3）。
    allow_break_continue（v1.1）：IbBreak/IbContinue 仅在 v1.5 cond-codegen（while True
    循环体）中生成 break/continue；v1.0 体 codegen 中非法（raise _Ineligible）。
    """
    src_lines = []
    consts = {}
    counter = [0]

    def _emit(stmts, indent):
        for stmt_uid in stmts:
            node_data = ec.get_node_data(stmt_uid)
            src_lines.append(f"{indent}loc[0] = {stmt_uid!r}")  # B3
            node_type = node_data.get("_type")
            if node_type == "IbAssign":
                target_uid = (node_data.get("targets") or [None])[0]
                t_data = ec.get_node_data(target_uid)
                if t_data.get("_type") == "IbTypeAnnotatedExpr":
                    target_uid = t_data.get("target")
                target_sym_uid = ec.get_side_table("node_to_symbol", target_uid)
                value_expr = _gen_expr(node_data.get("value"), ec, box, consts, counter)
                if value_expr is None:
                    raise _Ineligible()
                src_lines.append(
                    f"{indent}rt.set_variable_by_uid({target_sym_uid!r}, {value_expr})"
                )  # B2：无 skip_type_check
            elif node_type == "IbIf":
                cond_expr = _gen_expr(node_data.get("test"), ec, box, consts, counter)
                if cond_expr is None:
                    raise _Ineligible()
                then_body = node_data.get("body") or []
                else_body = node_data.get("orelse") or []
                src_lines.append(f"{indent}if ec.is_truthy({cond_expr}):")
                _emit(then_body, indent + "    ")
                if else_body:
                    src_lines.append(f"{indent}else:")
                    _emit(else_body, indent + "    ")
                else:
                    src_lines.append(f"{indent}pass")
            elif node_type == "IbPass":
                src_lines.append(f"{indent}pass")
            elif node_type in ("IbBreak", "IbContinue"):
                if not allow_break_continue:
                    raise _Ineligible()
                # IbBreak → Python break; IbContinue → Python continue（作用于 while True）
                py_kw = "break" if node_type == "IbBreak" else "continue"
                src_lines.append(f"{indent}{py_kw}")
            else:
                raise _Ineligible()

    _emit(stmt_uids, "    ")
    return src_lines, consts


class _Ineligible(Exception):
    """codegen 生成期中不可 codegen 节点形状（内部信号，非运行时错误）。"""


def generate_jit_body(stmt_uids, ec, registry, box):
    """为直线语句序列生成直接执行体（v1.0）；不可 codegen 返回 None。

    返回 ``_jit_body(rt, ec, loc)``：经 ``rt.get/set_variable_by_uid`` + ``receive`` 直接
    执行（无 CPS 生成器协议）；``loc[0]`` 逐语句设值（B3）；无控制流信号时返回 None。
    """
    if not stmt_uids:
        return None
    if _module_has_behavior_expr(ec):
        return None
    for suid in stmt_uids:
        if not _stmt_eligible(suid, ec, registry):
            return None
    try:
        src_lines, consts = _gen_body_source(stmt_uids, ec, box)
    except _Ineligible:
        return None
    func_source = "def _jit_body(rt, ec, loc):\n" + "\n".join(src_lines) + "\n    return None\n"
    code_obj = compile(func_source, "<ibci_jit_body>", "exec")
    namespace = {"__builtins__": {}, **consts}  # B7
    exec(code_obj, namespace)
    return namespace["_jit_body"]


def generate_jit_loop(stmt_uids, test_uid, ec, registry, box):
    """v1.5 cond-codegen：条件 + 体一起 codegen（drive-loop 交互归零）。

    条件（test）也 ∈ ExprSet 时，生成 ``_jit_loop(rt, ec, loc)``：内含 ``while True``
    条件检查（``ec.is_truthy``）+ 循环体，整个 while 循环在 codegen 体内一次执行完
    （vm_handle_IbWhile 纯 return，无 per-iteration gen.send）。条件含 LLM/不确定
    （llmexcept handler / 非 ExprSet）→ 返回 None（走 v1.0/CPS）。
    """
    if not stmt_uids:
        return None
    if _module_has_behavior_expr(ec):
        return None
    # v1.1：cond-codegen 体含 while True 循环，IbBreak/IbContinue 合法（Python
    # break/continue 作用于 while True 循环）
    for suid in stmt_uids:
        if not _stmt_eligible(suid, ec, registry, allow_break_continue=True):
            return None
    # 条件须 ∈ ExprSet（无 llmexcept handler——保护语句重试协议不可绕过）
    test_data = ec.get_node_data(test_uid) if test_uid else None
    if not test_data or test_data.get("llmexcept_handler"):
        return None
    cond_expr = _gen_expr(test_uid, ec, box, {}, [0])
    if cond_expr is None:
        return None
    # 重新生成（条件常量与体常量统一；v1.1 允许 break/continue）
    try:
        src_lines, consts = _gen_body_source(stmt_uids, ec, box, allow_break_continue=True)
        cond_expr = _gen_expr(test_uid, ec, box, consts, [len(consts)])
        if cond_expr is None:
            return None
    except _Ineligible:
        return None
    # 协作取消：codegen 体整循环一次执行（无 per-iteration gen.send），须在步进边界
    # 显式检查 cancel_event（与 _drive_loop_gen 同语义——否则 t.cancel() 无法终止
    # codegen 循环体）。cancel_event 经调用方（vm_handle_IbWhile）传入。
    from core.runtime.vm.task_scheduler import TaskCancelled
    loop_src = (
        f"    while True:\n"
        f"        if cancel_event is not None and cancel_event.is_set():\n"
        f"            raise TaskCancelled()\n"
        f"        loc[0] = {test_uid!r}\n"
        f"        if not ec.is_truthy({cond_expr}):\n"
        f"            break\n"
        + "\n".join("    " + line for line in src_lines)
    )
    func_source = "def _jit_loop(rt, ec, loc, cancel_event):\n" + loop_src + "\n    return None\n"
    code_obj = compile(func_source, "<ibci_jit_loop>", "exec")
    namespace = {"__builtins__": {}, "TaskCancelled": TaskCancelled, **consts}  # B7 + cancel
    exec(code_obj, namespace)
    return namespace["_jit_loop"]
