from typing import Any, Mapping, List, Optional, Union
from core.runtime.interpreter.handlers.base_handler import BaseHandler
from core.runtime.interfaces import ServiceContext, IExecutionContext
from core.runtime.objects.kernel import IbObject, IbLLMUncertain
from core.runtime.objects.builtins import IbInteger, IbString, IbList, IbNone
from core.runtime.objects.intent import IbIntent, IntentMode, IntentRole
from core.base.diagnostics.debugger import CoreModule, DebugLevel
from core.kernel.issue import InterpreterError
from core.runtime.exceptions import (
    ReturnException, BreakException, ContinueException, ThrownException
)
from ..constants import OP_MAPPING, UNARY_OP_MAPPING, AST_OP_MAP

class ExprHandler(BaseHandler):
    """
    表达式节点处理分片。
    """
    def visit_IbConstant(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """UTS: 统一常量装箱"""
        return self.registry.box(self.execution_context.resolve_value(node_data.get("value")))

    def visit_IbName(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """变量读取：严格通过 Symbol UID 查找"""
        sym_uid = self.get_side_table("node_to_symbol", node_uid)
        
        # 彻底废除名称查找 fallback。
        # 任何合法的 IBCI 产物都必须在编译阶段完成符号决议并记录在 node_to_symbol 侧表中。
        if not sym_uid:
             name = node_data.get("id")
             raise self.report_error(f"Execution Error: Symbol UID missing for name '{name}'. Artifact is corrupted or unanalyzed.", node_uid)
             
        try:
            # print(f"[DEBUG] Looking up UID: {sym_uid} for node: {node_uid}")
            return self.runtime_context.get_variable_by_uid(sym_uid)
        except Exception:
            # 如果是严格模式，或者在正常模式下 UID 查找彻底失败（未定义变量），则报错
            raise self.report_error(f"Execution Error: Symbol with UID '{sym_uid}' (name: '{node_data.get('id')}') is not defined in current context.", node_uid)

    def visit_IbBinOp(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """二元运算实现"""
        left = self.visit(node_data.get("left"))
        right = self.visit(node_data.get("right"))
        
        op = node_data.get("op")
        method = OP_MAPPING.get(op)
        
        if not method: raise self.report_error(f"Unsupported op: {op}", node_uid)
        return left.receive(method, [right])

    def visit_IbBoolOp(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """逻辑运算 (and/or)"""
        is_or = node_data.get("op") == 'or'
        last_val = self.registry.get_none()
        for val_uid in node_data.get("values", []):
            val = self.visit(val_uid)
            last_val = val
            if is_or and self.execution_context.is_truthy(val): return val
            if not is_or and not self.execution_context.is_truthy(val): return val
        return last_val

    def visit_IbIfExp(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """三元表达式"""
        if self.execution_context.is_truthy(self.visit(node_data.get("test"))):
            return self.visit(node_data.get("body"))
        return self.visit(node_data.get("orelse"))

    def visit_IbUnaryOp(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """一元运算实现"""
        operand = self.visit(node_data.get("operand"))
        op_symbol = node_data.get("op")
        
        # 使用全局归一化映射，消除 Handler 内部硬编码
        op = AST_OP_MAP.get(op_symbol, op_symbol)
        method = UNARY_OP_MAPPING.get(op)
        
        if not method: raise self.report_error(f"Unsupported unary op: {op_symbol}", node_uid)
        return operand.receive(method, [])

    def visit_IbCompare(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """比较运算实现 (支持链式比较 a < b < c，以及 in / not in / is / is not)"""
        left = self.visit(node_data.get("left"))
        ops = node_data.get("ops", [])
        comparators = node_data.get("comparators", [])
        
        # 必须处理链式比较，例如 a < b < c 
        # Python 语义：(a < b) and (b < c)，且每个操作数只计算一次
        
        current_left = left
        final_res = self.registry.box(True)
        
        for op, comparator_uid in zip(ops, comparators):
            right = self.visit(comparator_uid)

            # 成员检测运算符由右侧容器的 __contains__ 处理
            if op == "in":
                contained = right.receive('__contains__', [current_left])
                cmp_res = self.registry.box(bool(contained.to_native()) if hasattr(contained, 'to_native') else bool(contained))
            elif op == "not in":
                contained = right.receive('__contains__', [current_left])
                native = contained.to_native() if hasattr(contained, 'to_native') else contained
                cmp_res = self.registry.box(not bool(native))
            elif op == "is":
                # 身份比较：检查两个对象是否是同一个运行时实例
                # 特殊情况：None 和 Uncertain 使用类型检查而非实例身份
                if isinstance(right, IbNone):
                    cmp_res = self.registry.box(isinstance(current_left, IbNone))
                elif isinstance(right, IbLLMUncertain):
                    cmp_res = self.registry.box(isinstance(current_left, IbLLMUncertain))
                else:
                    cmp_res = self.registry.box(current_left is right)
            elif op == "is not":
                if isinstance(right, IbNone):
                    cmp_res = self.registry.box(not isinstance(current_left, IbNone))
                elif isinstance(right, IbLLMUncertain):
                    cmp_res = self.registry.box(not isinstance(current_left, IbLLMUncertain))
                else:
                    cmp_res = self.registry.box(current_left is not right)
            else:
                method = OP_MAPPING.get(op)
                if not method:
                    raise self.report_error(f"Unsupported comparison: {op}", node_uid)
                cmp_res = current_left.receive(method, [right])
            
            # 短路：只要有一个比较不成立，立即返回 False
            if not self.execution_context.is_truthy(cmp_res):
                return cmp_res
            
            final_res = cmp_res
            current_left = right
            
        return final_res

    def visit_IbCall(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """UTS: 函数调用逻辑"""
        func = self.visit(node_data.get("func"))
        args = [self.visit(a) for a in node_data.get("args", [])]
        
        try:
            # 如果是 BoundMethod 或 IbFunction/IbBehavior，其 call 内部会处理作用域
            if hasattr(func, 'call'):
                return func.call(self.registry.get_none(), args)
            return func.receive('__call__', args)
        except (ReturnException, BreakException, ContinueException, ThrownException):
            raise
        except Exception as e:
            if isinstance(e, InterpreterError): raise
            raise self.report_error(f"Call failed: {str(e)}", node_uid)

    def visit_IbAttribute(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """读取属性 -> __getattr__"""
        value = self.visit(node_data.get("value"))
        attr = node_data.get("attr")
        return value.receive('__getattr__', [self.registry.box(attr)])

    def visit_IbFilteredExpr(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """带过滤条件的表达式 (e.g., while expr if filter)

        语义：先求值主表达式；主表达式为假时短路返回假值；
              否则再求值过滤条件，过滤条件为假时返回 IbNone（falsy）。
              用于 while ... if ... 语法。

        注意：for ... in items if filter 的过滤逻辑由 visit_IbFor 直接处理，
              因为过滤条件引用循环变量，必须在目标变量赋值之后才能求值。
        """
        # 求值主表达式
        result = self.visit(node_data.get("expr"))
        # 短路：主表达式为假，直接返回（不求值 filter）
        if not self.execution_context.is_truthy(result):
            return result
        # 求值过滤条件
        filter_val = self.visit(node_data.get("filter"))
        if not self.execution_context.is_truthy(filter_val):
            # 过滤条件不满足：返回假值（IbNone 在 is_truthy 中为 false）
            return self.registry.get_none()
        return result

    def visit_IbSubscript(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """下标访问 -> __getitem__"""
        value = self.visit(node_data.get("value"))
        slice_obj = self.visit(node_data.get("slice"))
        return value.receive('__getitem__', [slice_obj])

    def visit_IbSlice(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """切片对象构建"""
        lower = node_data.get("lower")
        upper = node_data.get("upper")
        step = node_data.get("step")
        
        l_val = self.visit(lower).to_native() if lower else None
        u_val = self.visit(upper).to_native() if upper else None
        s_val = self.visit(step).to_native() if step else None
        
        # 封装为 Python slice 对象并用 registry 包装
        return self.registry.box(slice(l_val, u_val, s_val))

    def visit_IbTuple(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """元组字面量 -> 装箱为不可变元组"""
        elts = tuple(self.visit(e) for e in node_data.get("elts", []))
        return self.registry.box(elts)

    def visit_IbListExpr(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """列表字面量 -> 统一装箱"""
        elts = [self.visit(e) for e in node_data.get("elts", [])]
        return self.registry.box(elts)

    def visit_IbDict(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """字典字面量 -> 统一装箱"""
        data = {}
        keys = node_data.get("keys", [])
        values = node_data.get("values", [])
        for k_uid, v_uid in zip(keys, values):
            key_obj = self.visit(k_uid) if k_uid else self.registry.get_none()
            val_obj = self.visit(v_uid)
            native_key = key_obj.to_native() if hasattr(key_obj, 'to_native') else key_obj
            data[native_key] = val_obj
        return self.registry.box(data)

    def visit_IbBehaviorExpr(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """ 行为描述行不再立即执行，而是包装为被动行为对象。"""
        # 1. 检查是否显式标记为延迟
        is_deferred = self.get_side_table("node_is_deferred", node_uid)
        
        # 统一解析呼叫级意图
        intent_uid = node_data.get("intent")
        call_intent = None
        if intent_uid:
            intent_data = self.get_node_data(intent_uid)
            call_intent = IbIntent.from_node_data(
                intent_uid, 
                intent_data, 
                self.registry.get_class("Intent"),
                role=IntentRole.SMEAR
            )

        if is_deferred:
            # 根据 deferred_mode 决定捕获行为：
            # - 'lambda'  : 不捕获意图状态（每次调用时使用调用处的当前意图栈）
            # - 'snapshot': 捕获当前意图栈的快照（隔离执行，默认行为）
            deferred_mode = self.get_side_table("node_deferred_mode", node_uid)
            # snapshot 语义：捕获当前作用域正在生效的意图栈的值快照（IbIntentContext.fork()）。
            # lambda 语义：不捕获意图状态，每次调用时使用调用位置的当前意图栈。
            captured_intents = None if deferred_mode == "lambda" else self.runtime_context.fork_intent_snapshot()
            return self.service_context.object_factory.create_behavior(
                node_uid,
                captured_intents,
                expected_type=self.get_side_table("node_to_type", node_uid),
                call_intent=call_intent,
                deferred_mode=deferred_mode,
                execution_context=self._execution_context,
            )
        
        # [Fallback] 如果是非延迟模式，直接执行
        result = self.service_context.llm_executor.execute_behavior_expression(node_uid, self.execution_context, call_intent=call_intent)

        # 将结果存储到 RuntimeContext，供 visit_IbLLMExceptionalStmt 检查
        self.runtime_context.set_last_llm_result(result)

        # 返回 IbObject（而不是 LLMResult）
        # 使用 is not None 判断，避免将 IbBool(False)/IbInteger(0) 等假值误判为空
        return result.value if result is not None and result.value is not None else self.registry.get_none()

    def visit_IbCastExpr(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """类型强转运行时实现"""
        value = self.visit(node_data.get("value"))
        
        # 强制从 side_tables 获取决议后的目标描述符
        target_descriptor = self.get_side_table("node_to_type", node_uid)
        if not target_descriptor:
            # 严禁回退到名称查找，确保完整性
            return value
            
        # 寻找对应的 IbClass (基于 UTS 唯一标识)
        target_class = self.registry.get_class(target_descriptor.name)
        if not target_class:
            return value
            
        return value.receive('cast_to', [target_class])

    def visit_IbBehaviorInstance(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """
        隐式实例化的行为描述运行时实现。
        
        (Type) @~...~ 语法创建此节点，执行流程：
        1. 构建 IbIntent 并执行 LLM 调用
        2. 获取 LLM 返回的原始字符串
        3. 使用目标类型的 from_prompt 解析
        4. 调用目标类的构造函数创建实例
        """
        segments = node_data.get("segments", [])
        target_type_name = node_data.get("target_type_name", "")

        # 1. 构建 IbIntent
        # 从 segments 构建 intent 内容
        intent_content_parts = []
        for seg in segments:
            if isinstance(seg, str):
                intent_content_parts.append(seg)
            elif isinstance(seg, dict) and seg.get("_type") == "ext_ref":
                intent_content_parts.append(self.execution_context.get_asset(seg.get("uid", "")))
            elif hasattr(seg, "to_native"):
                intent_content_parts.append(str(seg.to_native()))
            else:
                intent_content_parts.append(str(seg))
        
        intent_content = "".join(intent_content_parts)
        
        # 创建 IbIntent 实例
        intent_class = self.registry.get_class("Intent")
        if intent_class:
            from core.runtime.objects.intent import IbIntent
            call_intent = IbIntent(
                ib_class=intent_class,
                content=intent_content,
                mode=IntentMode.APPEND
            )
        else:
            call_intent = None

        # 2. 获取目标类型描述符
        target_descriptor = self.get_side_table("node_to_type", node_uid)
        if not target_descriptor and target_type_name:
            meta_reg = self.registry.get_metadata_registry()
            if meta_reg:
                target_descriptor = meta_reg.resolve(target_type_name)

        # 3. 执行 LLM 调用
        executor = self.registry.get_llm_executor()
        if executor is None:
            self.runtime_context.set_last_llm_result(None)
            return self.registry.get_none()
        result = executor.execute_behavior_expression(
            node_uid,
            self.execution_context,
            call_intent=call_intent
        )

        self.runtime_context.set_last_llm_result(result)

        # 4. 检查 LLM 结果
        if not result or not result.value:
            return self.registry.get_none()

        # 注意：llm_executor._parse_result 已经调用了 from_prompt，
        # 所以 result.value 已经是解析后的值，不需要再次调用 from_prompt

        # 5. 调用目标类的构造函数创建实例
        if target_type_name:
            target_class = self.registry.get_class(target_type_name)
            if target_class:
                instance = target_class.receive('__call__', [result.value])
                return instance

        # 兜底：返回 result.value（已经是解析后的值）
        return result.value

    def visit_IbLambdaExpr(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """
        参数化 lambda/snapshot 表达式的运行时实现。

        语义
        ----
        * 'snapshot' —— 创建 IbDeferred/IbBehavior 持有 ``closure`` 字典（按符号
          UID 索引到 ``(name, IbCell(value))``，IbCell 为定义时取值的独立副本）；
          调用时把 cell 的值在子作用域以相同 ``uid`` 重新绑定，body 内的 IbName
          走 UID 解析时即可命中本地副本而不是定义后变更的外部符号。
        * 'lambda'   —— 创建 IbDeferred/IbBehavior 持有 ``closure`` 字典（按符号
          UID 索引到 ``(name, shared_IbCell)``，IbCell 为**共享引用**，与定义处
          作用域的同一 IbCell 实例绑定，公理 SC-4）；调用时 cell.get() 返回调用
          时刻的最新值，外层对该变量的赋值会同步到 cell（公理 SC-3）。
          全局作用域变量不提升，仍通过调用处作用域链正常访问。

        M2 变更（SC-4 落地）：lambda 模式不再持有 ``captured_scope`` 引用，
        而是和 snapshot 一样使用 ``closure`` 字典；区别在于 snapshot 存值拷贝，
        lambda 存共享 IbCell 引用。

        当 body 是 ``IbBehaviorExpr`` 时构造 ``IbBehavior``（沿用 LLM 执行器路径），
        否则构造 ``IbDeferred``（普通表达式重访路径）。
        """
        params_uids: List[str] = list(node_data.get("params") or [])
        body_uid = node_data.get("body")
        deferred_mode = node_data.get("deferred_mode") or "lambda"

        body_data = self.execution_context.get_node_data(body_uid) if body_uid else None
        body_is_behavior = bool(body_data) and body_data.get("_type") == "IbBehaviorExpr"

        # H2：优先使用编译期填充的 free_vars 字段（C8 起 semantic_analyzer 已写入所有产物）。
        # 若字段缺失（旧 artifact 兼容），回退到运行时 AST 遍历（_collect_free_refs）。
        free_vars_compiled = node_data.get("free_vars")  # [[name, sym_uid], ...]
        # 形参符号 UID 集合：用于把"形参引用"从"自由变量引用"中剔除（仅 fallback 路径使用）
        param_sym_uids = self._collect_param_sym_uids(params_uids)

        closure: Dict[str, Any] = {}
        if body_uid:
            from core.runtime.objects.cell import IbCell
            current_scope = self.runtime_context.current_scope

            if free_vars_compiled:
                # 编译期路径（主路径）：直接读取已分析的自由变量列表，无运行时 AST 遍历
                free_refs = [(name, sym_uid) for name, sym_uid in free_vars_compiled]
            else:
                # 兼容旧 artifact 的 fallback：运行时遍历 AST（_collect_free_refs）
                # 此路径仅在 artifact 不含 free_vars 字段时触发（pre-C8 artifact）
                free_refs = self._collect_free_refs(body_uid, param_sym_uids)

            for name, sym_uid in free_refs:
                if sym_uid in closure:
                    continue
                if deferred_mode == "snapshot":
                    # snapshot 模式：值拷贝——在定义时刻创建独立 IbCell(current_value)
                    try:
                        val = current_scope.get_by_uid(sym_uid)
                    except (KeyError, AttributeError):
                        val = None
                    if val is not None:
                        closure[sym_uid] = (name, IbCell(val))
                    else:
                        # UID 查找失败时发出 debug 跟踪警告，便于排查缺失变量问题。
                        # 静默跳过会导致后续调用 snapshot 时抛出难以定位的 "UID not found" 错误。
                        self.debugger.trace(
                            CoreModule.INTERPRETER, DebugLevel.BASIC,
                            f"snapshot closure capture failed: free var "
                            f"name={name!r} sym_uid={sym_uid!r} not found in scope; "
                            f"variable will be missing from snapshot closure"
                        )
                else:
                    # lambda 模式（M2 SC-4）：共享引用——将外层变量提升为 Cell 并持有
                    # 同一 IbCell 实例。全局作用域变量不提升（promote_to_cell 返回 None），
                    # 它们通过调用处作用域链正常访问。
                    cell = current_scope.promote_to_cell(sym_uid)
                    if cell is not None:
                        closure[sym_uid] = (name, cell)

        if body_is_behavior:
            # IbBehavior 路径：复用 visit_IbBehaviorExpr 的意图捕获逻辑
            captured_intents = (
                None if deferred_mode == "lambda"
                else self.runtime_context.fork_intent_snapshot()
            )
            expected_type = self.get_side_table("node_to_type", body_uid)
            return self.service_context.object_factory.create_behavior(
                body_uid,
                captured_intents,
                expected_type=expected_type,
                deferred_mode=deferred_mode,
                execution_context=self._execution_context,
                params_uids=params_uids,
                closure=closure,
            )

        return self.service_context.object_factory.create_deferred(
            node_uid,
            deferred_mode=deferred_mode,
            execution_context=self._execution_context,
            params_uids=params_uids,
            body_uid=body_uid,
            closure=closure,
        )

    def _collect_param_sym_uids(self, params_uids: List[str]) -> set:
        """提取 lambda 形参的符号 UID 集合（解开 IbTypeAnnotatedExpr 包装）。"""
        sym_uids = set()
        for puid in params_uids:
            actual = puid
            pdata = self.execution_context.get_node_data(puid)
            if pdata and pdata.get("_type") == "IbTypeAnnotatedExpr":
                actual = pdata.get("target")
            if actual:
                sid = self.get_side_table("node_to_symbol", actual)
                if sid:
                    sym_uids.add(sid)
        return sym_uids

    def _collect_free_refs(self, root_uid: str, exclude_sym_uids: set) -> List:
        """
        浅层 AST 走访收集 ``IbName`` (Load 上下文) 的 ``(name, sym_uid)`` 二元组，
        过滤掉形参符号；遇到嵌套 ``IbLambdaExpr`` 时屏蔽其内层形参（最近词法
        绑定）。返回去重前的列表，由调用方按 sym_uid 去重。

        本实现避免引入新的语义侧表，runtime 期遍历开销与 body 节点数线性相关，
        典型 lambda body 规模较小，开销可忽略。
        """
        refs: List = []
        visited: set = set()
        # 栈元素: (uid, exclude_set)；嵌套 lambda 会扩展 exclude_set
        stack: List = [(root_uid, exclude_sym_uids)]
        while stack:
            cur, excl = stack.pop()
            if not isinstance(cur, str) or cur in visited:
                continue
            visited.add(cur)
            data = self.execution_context.get_node_data(cur)
            if not data:
                continue
            ntype = data.get("_type")
            if ntype == "IbName":
                if data.get("ctx", "Load") == "Load":
                    sym_uid = self.get_side_table("node_to_symbol", cur)
                    if sym_uid and sym_uid not in excl:
                        nm = data.get("id") or ""
                        refs.append((nm, sym_uid))
                continue
            if ntype == "IbLambdaExpr":
                inner_param_uids = self._collect_param_sym_uids(list(data.get("params") or []))
                inner_body = data.get("body")
                if inner_body:
                    stack.append((inner_body, excl | inner_param_uids))
                continue
            # 通用展开：将所有 list 字段中的字符串 uid 与字符串字段中合法 uid 视作子节点。
            #
            # L4 注：这是一个启发式遍历策略——AST 节点的字段可能以多种语义出现
            # （子节点 UID、字面量字符串、配置标记等）。判定 "字段值是字符串
            # 且存在于 ``node_pool``" 即视作子节点 UID。**在 IBCI 当前的 UID
            # 编码下（前 16 hex 字节的内容哈希 + ``node_`` 前缀，详见
            # ``serialization/serializer.py``），任意非 UID 的字符串字面量恰好
            # 与某个 node_pool key 碰撞的概率极低（< 2^-64）**，因此该启发式
            # 策略在实践中不会误吞字面量字符串作为子节点。
            # 若未来 UID 编码改用更短或非随机的格式，本启发式可能误判，应改用
            # 显式的 AST 字段 schema（例如 dataclass annotated fields）。
            pool = self.execution_context.node_pool
            for k, v in data.items():
                if k.startswith("_"):
                    continue
                if isinstance(v, list):
                    for it in v:
                        if isinstance(it, str) and it in pool:
                            stack.append((it, excl))
                elif isinstance(v, str) and v in pool:
                    stack.append((v, excl))
        return refs
