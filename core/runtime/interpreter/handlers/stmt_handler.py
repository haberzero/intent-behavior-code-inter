from typing import Any, Mapping, List, Optional, Callable
from core.runtime.interpreter.handlers.base_handler import BaseHandler
from core.runtime.objects.kernel import IbObject, IbUserFunction, IbLLMFunction, IbClass
from core.runtime.interfaces import IExecutionContext, ServiceContext, IIbList
from core.runtime.objects.builtins import IbBehavior
from core.runtime.exceptions import (
    ReturnException, BreakException, ContinueException, ThrownException
)
from core.runtime.objects.intent import IbIntent, IntentMode, IntentRole
from core.base.diagnostics.debugger import CoreModule, DebugLevel
from core.base.enums import RegistrationState

from core.kernel.issue import InterpreterError
from core.base.diagnostics.codes import RUN_GENERIC_ERROR
from ..constants import OP_MAPPING, AST_OP_MAP

class StmtHandler(BaseHandler):
    """
    语句节点处理分片。
    """
    def visit_IbModule(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        result = self.registry.get_none()
        for stmt_uid in node_data.get("body", []):
            result = self.visit(stmt_uid)
        return result

    def visit_IbPass(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        return self.registry.get_none()

    def visit_IbGlobalStmt(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """global 声明是编译期语义，运行时无需操作。"""
        return self.registry.get_none()

    def visit_IbLLMExceptionalStmt(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """
        执行 llmexcept 语句 (影子执行驱动模式)。
        """
        target_uid = node_data.get("target")
        body_uids = node_data.get("body", [])

        if not target_uid:
            return self.registry.get_none()

        # 从 ai 组件获取重试次数配置
        max_retry = 3
        if self.service_context.capability_registry:
            llm_provider = self.service_context.capability_registry.get("llm_provider")
            if llm_provider and hasattr(llm_provider, "get_retry"):
                max_retry = llm_provider.get_retry()

        # 创建帧并保存上下文切片
        frame = self.runtime_context.save_llm_except_state(
            target_uid=target_uid,
            node_type="IbLLMExceptionalStmt",
            max_retry=max_retry
        )

        self.debugger.trace(CoreModule.INTERPRETER, DebugLevel.DETAIL,
            f"llmexcept: entering frame for target={target_uid}, max_retry={max_retry}")

        last_target_value = None
        try:
            while frame.should_continue_retrying():
                attempt = frame.retry_count + 1
                self.debugger.trace(CoreModule.INTERPRETER, DebugLevel.DETAIL,
                    f"llmexcept: attempt {attempt}/{frame.max_retry + 1}, target={target_uid}")

                # 显式恢复上下文快照 (如果是 retry 跳转回来的)
                frame.restore_snapshot(self.runtime_context)

                # §9.3: 进入快照前清除共享信号通道，防止前次结果污染本次判断。
                # 此处总是清除（无条件），消除对 frame.should_retry 状态的依赖。
                self.runtime_context.set_last_llm_result(None)

                # C11/P3：node_protection 侧表已删除（C11 完成）；
                # llmexcept handler 通过 target 字段直接引用 prev_stmt，
                # vm_handle_IbLLMExceptionalStmt 显式 yield target_uid 驱动执行。
                last_target_value = self.execution_context.visit(target_uid)

                # §9.3: 读取 LLM 结果后立即从共享字段迁移到帧私有字段，
                # 使 _last_llm_result 的生命周期缩小为"快照内通信"（进入清零，读后清零）。
                result = self.runtime_context.get_last_llm_result()
                self.runtime_context.set_last_llm_result(None)

                # 如果没有 LLM 调用，或者 LLM 调用是确定的（成功匹配或明确失败）
                if result is None or result.is_certain:
                    self.debugger.trace(CoreModule.INTERPRETER, DebugLevel.DETAIL,
                        f"llmexcept: resolved on attempt {attempt}, target={target_uid}")
                    break

                # 运行到这里说明 LLM 返回了 UNCERTAIN 结果
                raw_preview = (result.raw_response or "")[:60].replace("\n", " ")
                self.debugger.trace(CoreModule.INTERPRETER, DebugLevel.BASIC,
                    f"llmexcept: uncertain result on attempt {attempt} (raw: '{raw_preview}'), entering handler body")

                # §9.3: 结果存入帧私有字段; _last_llm_result 在 body 执行期间维持 None。
                # idbg.last_result() / idbg.last_llm() 从 frames[-1].last_result 读取，无需恢复。
                frame.last_result = result
                frame.should_retry = False  # 重置为 False，等待 body 中的 retry 语句显式触发

                # 执行 llmexcept 的 body 块 (处理逻辑)
                for stmt_uid in body_uids:
                    self.visit(stmt_uid)

                # 检查重试计数
                if not frame.increment_retry():
                    self.debugger.trace(CoreModule.INTERPRETER, DebugLevel.BASIC,
                        f"llmexcept: max retries ({frame.max_retry}) exhausted for target={target_uid}")
                    break

        finally:
            # 弹出当前帧
            self.runtime_context.pop_llm_except_frame()

        # 返回 target 最后一次执行的值（对条件驱动 for 循环的条件表达式至关重要）
        return last_target_value if last_target_value is not None else self.registry.get_none()

    def visit_IbExprStmt(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """表达式语句"""
        res = self.visit(node_data.get("value"))
        # 如果是行为对象（延迟 behavior 被当作语句直接使用），触发自主执行
        if isinstance(res, IbBehavior):
            return res.call(self.registry.get_none(), [])
        return res

    def visit_IbIntentAnnotation(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """
        处理意图注释节点 - @ 和 @! 专用

        IbIntentAnnotation 代表单行意图注释，必须后续紧跟 LLM 调用。

        语义区别：
        - @ : 一次性涂抹意图（只对紧跟的下一次 LLM 调用有效，自动清除）
        - @! : 排他意图（只对当前这一次 LLM 调用有效，屏蔽当前栈）

        两者都是临时的，不会永久修改持久意图栈。
        """
        intent_info_uid = node_data.get("intent")
        if not intent_info_uid:
            return self.registry.get_none()

        intent_data = self.get_node_data(intent_info_uid)
        if not intent_data:
            return self.registry.get_none()

        intent = self.execution_context.factory.create_intent_from_node(
            intent_info_uid,
            intent_data,
            role=IntentRole.SMEAR
        )

        # @! 排他意图：设置为临时的单次意图
        # 这是临时的 IntentStack 实例，只对当前这一次 LLM 调用有效
        if intent.is_override:
            self.runtime_context.set_pending_override_intent(intent)
        else:
            # @ 一次性涂抹意图：加入 pending 队列，下一次 LLM 调用消费后自动清除
            # 不压入持久意图栈（@+ 才是持久压栈）
            self.runtime_context.add_smear_intent(intent)

        return self.registry.get_none()

    def visit_IbIntentStackOperation(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """
        处理意图栈操作节点 - @+ 和 @- 专用

        IbIntentStackOperation 代表意图栈操作，允许独立存在。
        - @+: 将意图压入栈
        - @-: 从栈中物理移除匹配的意图（按标签或内容）
        - @- (无参数): 移除栈顶意图

        此方法通过 IntentStack 内置类进行操作（公理体系融入）。
        """
        intent_info_uid = node_data.get("intent")
        if not intent_info_uid:
            return self.registry.get_none()

        intent_data = self.get_node_data(intent_info_uid)
        if not intent_data:
            return self.registry.get_none()

        intent = self.execution_context.factory.create_intent_from_node(
            intent_info_uid,
            intent_data,
            role=IntentRole.STACK
        )

        # @- 无参数：移除栈顶意图
        if intent.is_pop_top:
            self.runtime_context.pop_intent()
        # @- 按标签或内容移除
        elif intent.is_remove:
            if intent.tag:
                self.runtime_context.remove_intent(tag=intent.tag)
            elif intent.content:
                self.runtime_context.remove_intent(content=intent.content)
        else:
            # @+ 压入栈
            self.runtime_context.push_intent(intent)

        return self.registry.get_none()

    def _assign_to_target(self, target_uid: str, value: IbObject, define_only: bool = False):
        """通用赋值逻辑，支持 Name, TypeAnnotatedExpr, Attribute, Subscript, Tuple Unpacking"""
        target_data = self.get_node_data(target_uid)
        if not target_data: 
            return
        
        # 1. 普通变量赋值 (Name)
        if target_data["_type"] == "IbName":
            sym_uid = self.get_side_table("node_to_symbol", target_uid)
            name = target_data.get("id")
            if sym_uid:
                existing = self.runtime_context.get_symbol_by_uid(sym_uid)
                # 如果有 Symbol UID，则根据其是否存在于当前作用域决定 define 还是 set
                if not define_only and existing:
                    self.runtime_context.set_variable_by_uid(sym_uid, value)
                else:
                    declared_type = self.execution_context.resolve_type_from_symbol(sym_uid)
                    # global 声明：如果 sym_uid 属于全局作用域且当前不在全局作用域，
                    # 则在全局作用域中定义，而非当前（函数）作用域。
                    if (self.runtime_context.is_global_symbol_uid(sym_uid)
                            and self.runtime_context.current_scope is not self.runtime_context.global_scope):
                        self.runtime_context.define_variable_at_global(name, value, declared_type=declared_type, uid=sym_uid)
                    else:
                        self.runtime_context.define_variable(name, value, declared_type=declared_type, uid=sym_uid)
            elif not self.execution_context.strict_mode:
                # 回退到名称查找
                try:
                    self.runtime_context.get_variable(name)
                    if define_only:
                         self.runtime_context.define_variable(name, value)
                    else:
                         self.runtime_context.set_variable(name, value)
                except Exception:
                    self.runtime_context.define_variable(name, value)
            else:
                raise self.report_error(f"Strict mode: Symbol UID missing for assignment to '{name}'.", target_uid)
        
        # 2. 类型标注表达式 (TypeAnnotatedExpr)
        elif target_data["_type"] == "IbTypeAnnotatedExpr":
            inner_target_uid = target_data.get("target")
            # 递归处理内部目标，但强制使用 define 模式
            self._assign_to_target(inner_target_uid, value, define_only=True)
        
        # 3. 属性赋值 (Attribute)
        elif target_data["_type"] == "IbAttribute":
            obj = self.visit(target_data.get("value"))
            attr = target_data.get("attr")
            obj.receive('__setattr__', [self.registry.box(attr), value])
        
        # 4. 下标赋值 (Subscript)
        elif target_data["_type"] == "IbSubscript":
            obj = self.visit(target_data.get("value"))
            slice_val = self.visit(target_data.get("slice"))
            obj.receive('__setitem__', [slice_val, value])
            
        # 5. 元组解包 (Tuple)
        elif target_data["_type"] == "IbTuple":
            # 直接从 IbList/IbTuple 对象中获取元素
            from core.runtime.objects.builtins import IbList, IbTuple as IbTupleObj
            if isinstance(value, (IbList, IbTupleObj)):
                vals = list(value.elements)
            else:
                # 回退：通过 to_list 消息获取
                result = value.receive('to_list', [])
                if isinstance(result, list):
                    vals = result
                elif hasattr(result, 'elements'):
                    vals = list(result.elements)
                else:
                    raise self.report_error(f"Cannot unpack non-iterable object", target_uid)
            
            targets = target_data.get("elts", [])
            if len(vals) != len(targets):
                raise self.report_error(f"Unpack error: expected {len(targets)} values, got {len(vals)}", target_uid)
            
            for t_uid, val in zip(targets, vals):
                self._assign_to_target(t_uid, val, define_only=define_only)

    def visit_IbAssign(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """实现赋值语句"""
        self.debugger.trace(CoreModule.INTERPRETER, DebugLevel.DETAIL, f"Executing assignment {node_uid}")

        # 在访问 value 前清除上一次的 LLM 结果，防止来自前序语句的过期不确定性标记
        # 污染当前赋值。访问 value 后读取的结果仅反映本次值求值过程。
        self.runtime_context.set_last_llm_result(None)

        value_uid = node_data.get("value")

        # 通用延迟表达式拦截：
        # 如果 value 被标记为 deferred 且不是 behavior 表达式（behavior 有自己的延迟处理），
        # 则创建 IbDeferred 对象而非立即求值。
        is_deferred = self.get_side_table("node_is_deferred", value_uid) if value_uid else False
        if is_deferred and value_uid:
            value_node_data = self.get_node_data(value_uid) if isinstance(value_uid, str) else None
            value_node_type = value_node_data.get("_type", "") if value_node_data is not None else ""
            if value_node_type != "IbBehaviorExpr":
                # 通用延迟：创建 IbDeferred 对象包裹任意表达式
                deferred_mode = self.get_side_table("node_deferred_mode", value_uid) or "lambda"
                value = self.service_context.object_factory.create_deferred(
                    value_uid,
                    deferred_mode=deferred_mode,
                    execution_context=self._execution_context,
                )
            else:
                # behavior 表达式走原有路径（visit_IbBehaviorExpr 内部处理延迟）
                value = self.visit(value_uid)
        else:
            value = self.visit(value_uid)

        # 检查是否由于 LLM 不确定性导致赋值未完成
        # 如果是，则赋值为 IbLLMUncertain 特殊值，而不是跳过赋值
        last_result = self.runtime_context.get_last_llm_result()
        if last_result and not last_result.is_certain:
            value = self.registry.get_llm_uncertain()
        
        for target_uid in node_data.get("targets", []):
            self._assign_to_target(target_uid, value)
                
        return self.registry.get_none()

    def visit_IbAugAssign(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """复合赋值实现 (a += 1)"""
        target_uid = node_data.get("target")
        target_data = self.get_node_data(target_uid)
        
        value = self.visit(node_data.get("value"))
        op_symbol = node_data.get("op")
        
        # 复合赋值运算符存储为 "+=" 形式，去掉末尾 "=" 得到基础运算符
        base_op = op_symbol.rstrip('=') if op_symbol and op_symbol.endswith('=') else op_symbol
        op = AST_OP_MAP.get(base_op, base_op)
        method = OP_MAPPING.get(op)
        
        if not method: raise self.report_error(f"Unsupported aug op: {op_symbol}", node_uid)
        
        # 1. 读取旧值
        old_val = self.visit(target_uid)
        
        # 2. 计算新值
        new_val = old_val.receive(method, [value])
        
        # 3. 写回
        if target_data["_type"] == "IbName":
            sym_uid = self.get_side_table("node_to_symbol", target_uid)
            if sym_uid:
                self.runtime_context.set_variable_by_uid(sym_uid, new_val)
            else:
                self.runtime_context.set_variable(target_data.get("id"), new_val)
        elif target_data["_type"] == "IbAttribute":
            obj = self.visit(target_data.get("value"))
            attr = target_data.get("attr")
            obj.receive('__setattr__', [self.registry.box(attr), new_val])
            
        return self.registry.get_none()

    def visit_IbSwitch(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """Switch-Case 语句"""
        # 清除过期的 LLM 结果，确保只检查 test 表达式自身的求值结果
        self.runtime_context.set_last_llm_result(None)
        test_value = self.visit(node_data.get("test"))

        last_result = self.runtime_context.get_last_llm_result()
        if last_result and not last_result.is_certain:
            return self.registry.get_none()

        case_uids = node_data.get("cases", [])
        matched = False

        for case_uid in case_uids:
            case_data = self.execution_context.get_node_data(case_uid)
            pattern = case_data.get("pattern")

            if pattern is None:
                matched = True
            else:
                pattern_value = self.visit(pattern)
                
                # 使用 __eq__ 方法进行比较（支持用户定义的相等性）
                eq_result = test_value.receive('__eq__', [pattern_value])
                is_equal = self.execution_context.is_truthy(eq_result)

                if is_equal:
                    matched = True

            if matched:
                for stmt_uid in case_data.get("body", []):
                    self.visit(stmt_uid)
                break

        return self.registry.get_none()

    def visit_IbIf(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """条件分支语句"""
        # 清除过期的 LLM 结果，确保只检查 test 条件自身的求值结果
        self.runtime_context.set_last_llm_result(None)
        condition = self.visit(node_data.get("test"))

        # 核心：检查测试表达式是否产生了不确定的 LLM 结果
        # 如果不确定，说明 AI 决策模糊，我们需要立即终止 IbIf 的执行，让控制流回退到保护者
        last_result = self.runtime_context.get_last_llm_result()
        if last_result and not last_result.is_certain:
            return self.registry.get_none()

        if self.execution_context.is_truthy(condition):
            for stmt_uid in node_data.get("body", []):
                self.visit(stmt_uid)
        else:
            for stmt_uid in node_data.get("orelse", []):
                self.visit(stmt_uid)
        return self.registry.get_none()

    def visit_IbWhile(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """循环语句"""
        test_uid = node_data.get("test")
        
        while True:
            # 每次迭代前清除过期的 LLM 结果，防止循环体内的不确定性标记
            # 污染下一次循环条件的检测。只有本次条件求值产生的 LLM 结果才应被检查。
            self.runtime_context.set_last_llm_result(None)
            condition = self.visit(test_uid)

            last_result = self.runtime_context.get_last_llm_result()
            if last_result and not last_result.is_certain:
                return self.registry.get_none()

            if not self.execution_context.is_truthy(condition):
                break
            
            try:
                for stmt_uid in node_data.get("body", []):
                    self.visit(stmt_uid)
            except BreakException:
                break
            except ContinueException:
                continue
        return self.registry.get_none()
    
    def visit_IbFor(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """迭代循环语句实现"""
        target_uid = node_data.get("target")
        iter_uid = node_data.get("iter")
        body = node_data.get("body", [])

        # 检查 iter 是否为 IbFilteredExpr（for ... in items if filter: 或
        # 条件驱动 for @~...~ if filter:），提前拆包为 actual_iter_uid + filter_uid。
        filter_uid = None
        actual_iter_uid = iter_uid
        iter_node_data = self.get_node_data(iter_uid)
        if iter_node_data and iter_node_data.get("_type") == "IbFilteredExpr":
            actual_iter_uid = iter_node_data.get("expr")
            filter_uid = iter_node_data.get("filter")

        # 条件驱动循环 (Condition-driven loop: for @~ ... ~:)
        if target_uid is None:
            while True:
                # 每次迭代前清除过期的 LLM 结果，防止循环体内的不确定性标记
                # 污染下一次循环条件的检测。
                self.runtime_context.set_last_llm_result(None)
                condition = self.visit(actual_iter_uid)
                last_result = self.runtime_context.get_last_llm_result()
                if last_result and not last_result.is_certain:
                    return self.registry.get_none()
                if not self.execution_context.is_truthy(condition):
                    break
                # 过滤条件（如果有）：不满足则终止循环（与 while...if 语义一致）
                if filter_uid is not None:
                    filter_val = self.visit(filter_uid)
                    if not self.execution_context.is_truthy(filter_val):
                        break
                try:
                    for stmt_uid in body:
                        self.visit(stmt_uid)
                except BreakException:
                    break
                except ContinueException:
                    continue
            return self.registry.get_none()

        # 标准 Foreach 循环 (for item in list)
        iterable_obj = self.visit(actual_iter_uid)
        # Check for iterable: has 'elements' list attribute (duck-typing over IIbList protocol)
        if hasattr(iterable_obj, 'elements') and isinstance(iterable_obj.elements, list):
            elements_obj = iterable_obj
        else:
            elements_obj = None
            # 1. __iter__ 协议：对象实现了 __iter__() 方法，返回 list 对象
            try:
                result = iterable_obj.receive('__iter__', [])
                if hasattr(result, 'elements') and isinstance(result.elements, list):
                    elements_obj = result
            except (AttributeError, InterpreterError):
                pass
            # 2. to_list 兜底：旧版内置类型的转换接口
            if elements_obj is None:
                try:
                    result = iterable_obj.receive('to_list', [])
                    elements_obj = result if (hasattr(result, 'elements') and isinstance(result.elements, list)) else None
                except (AttributeError, InterpreterError):
                    elements_obj = None
        if elements_obj is None:
            raise self.report_error(f"Object is not iterable", node_uid)
        
        elements = elements_obj.elements
        total = len(elements)

        # 从当前 llmexcept 帧读取断点恢复索引（如果存在）。
        # retry 后 for 循环从上次失败的迭代处继续，而非从头开始。
        top_frame = (
            self.runtime_context._llm_except_frames[-1]
            if hasattr(self.runtime_context, '_llm_except_frames')
               and self.runtime_context._llm_except_frames
            else None
        )
        resume_from = top_frame.loop_resume.get(node_uid, 0) if top_frame is not None else 0

        for i, item in enumerate(elements):
            if i < resume_from:
                continue

            # 在迭代开始时更新帧的恢复索引，以便下次 retry 从此迭代继续。
            if top_frame is not None:
                top_frame.loop_resume[node_uid] = i

            self.runtime_context.push_loop_context(i, total)

            # 先赋值目标变量（过滤条件可能引用该变量，例如 for int n in items if n % 2 == 0）
            if target_uid:
                self._assign_to_target(target_uid, item, define_only=True)

            # 过滤条件（如果有）：不满足则跳过当前元素，继续下一个
            if filter_uid is not None:
                filter_val = self.visit(filter_uid)
                if not self.execution_context.is_truthy(filter_val):
                    self.runtime_context.pop_loop_context()
                    continue

            try:
                for stmt_uid in body:
                    self.visit(stmt_uid)
            except BreakException:
                self.runtime_context.pop_loop_context()
                break
            except ContinueException:
                self.runtime_context.pop_loop_context()
                continue
            
            self.runtime_context.pop_loop_context()
        return self.registry.get_none()

    def visit_IbTry(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """实现异常处理块"""
        try:
            for stmt_uid in node_data.get("body", []):
                self.visit(stmt_uid)
        except (ReturnException, BreakException, ContinueException):
            raise
        except (ThrownException, Exception) as e:
            # 统一异常对象化
            if isinstance(e, ThrownException):
                error_obj = e.value
            else:
                # 包装 Python 原生异常为 IBC-Inter 的 Exception 实例
                exc_class = self.registry.get_class("Exception")
                if not exc_class:
                    raise self.report_error("Critical Error: 'Exception' builtin class not found in registry. Bootstrap failed.", node_uid)
                
                # 传入空参数列表给 instantiate
                error_obj = exc_class.instantiate([])
                error_obj.fields["message"] = self.registry.box(str(e))
            
            # 查找匹配的 except 块
            handled = False
            for handler_uid in node_data.get("handlers", []):
                handler_data = self.get_node_data(handler_uid)
                
                # 1. 类型匹配检查
                type_uid = handler_data.get("type")
                if type_uid:
                    expected_type_obj = self.visit(type_uid)
                    # 如果捕获的是类对象，进行子类判定
                    if isinstance(expected_type_obj, IbClass):
                        if not error_obj.ib_class.is_assignable_to(expected_type_obj):
                            continue
                    # 如果捕获的是其他对象（如字符串），进行值判定（用于 LLM 异常简化匹配）
                    elif expected_type_obj != error_obj:
                        continue

                # 2. 绑定异常变量
                name = handler_data.get("name")
                if name:
                    # 使用统一的赋值逻辑支持异常变量绑定
                    # 简单起见，既然目前只有 Name，我们可以直接保留
                    sym_uid = self.get_side_table("node_to_symbol", handler_uid)
                    self.runtime_context.define_variable(name, error_obj, uid=sym_uid)
                
                # 3. 执行处理体
                for stmt_uid in handler_data.get("body", []):
                    self.visit(stmt_uid)
                handled = True
                break
            
            if not handled:
                raise e
        else:
            # 执行 else 块
            for stmt_uid in node_data.get("orelse", []):
                self.visit(stmt_uid)
        finally:
            # 执行 finally 块
            for stmt_uid in node_data.get("finalbody", []):
                self.visit(stmt_uid)
                
        return self.registry.get_none()

    def visit_IbRetry(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """
        处理 retry 语句。

        语义：
        1. 获取可选的 retry hint
        2. 从当前 llmexcept 帧恢复上下文切片
        3. 设置 should_retry = True，让 llmexcept 重新执行 target

        注意：
        - 不抛出任何异常
        - 不使用 RetryException
        """
        hint_uid = node_data.get("hint")
        hint_val = None
        if hint_uid:
            hint_obj = self.visit(hint_uid)
            hint_val = hint_obj.to_native() if hasattr(hint_obj, 'to_native') else str(hint_obj)

        # 设置 retry hint
        self.runtime_context.retry_hint = hint_val

        # 从当前帧恢复上下文并设置重试标志
        frame = self.runtime_context.get_current_llm_except_frame()
        if frame:
            frame.restore_snapshot(self.runtime_context)
            frame.should_retry = True  # 设置标志，让外层循环继续重试

        return self.registry.get_none()

    def visit_IbFunctionDef(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """普通函数定义"""
        sym_uid = self.get_side_table("node_to_symbol", node_uid)
        declared_type = self.execution_context.resolve_type_from_symbol(sym_uid)
        func = IbUserFunction(node_uid, self.execution_context, spec=declared_type)
        name = node_data.get("name")
        self.runtime_context.define_variable(name, func, declared_type=declared_type, uid=sym_uid)
        return self.registry.get_none()

    def visit_IbLLMFunctionDef(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """LLM 函数 definition"""
        sym_uid = self.get_side_table("node_to_symbol", node_uid)
        declared_type = self.execution_context.resolve_type_from_symbol(sym_uid)
        func = IbLLMFunction(node_uid, self.execution_context, spec=declared_type)
        name = node_data.get("name")
        self.runtime_context.define_variable(name, func, declared_type=declared_type, uid=sym_uid)
        return self.registry.get_none()

    def visit_IbClassDef(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """验证类契约并将其绑定到当前作用域"""
        # 类必须在 STAGE 5 预水合完成。
        # 此处仅负责契约验证与作用域定义。
        name = node_data.get("name")
        
        # 生产环境/封印状态：不再允许创建和注册新类，仅执行契约校验
        existing_class = self.registry.get_class(name)
        if not existing_class:
            raise self.report_error(f"Sealed Registry Error: Class '{name}' must be pre-hydrated in STAGE 5. ", node_uid)
        
        # 绑定到当前作用域 (作为常量类)
        sym_uid = self.get_side_table("node_to_symbol", node_uid)
        self.runtime_context.define_variable(name, existing_class, uid=sym_uid)
        
        # 深度契约校验：验证 AST 定义的方法是否全部在运行时虚表中就绪
        body = node_data.get("body", [])
        for stmt_uid in body:
            stmt_data = self.get_node_data(stmt_uid)
            if not stmt_data: continue
            
            if stmt_data["_type"] in ("IbFunctionDef", "IbLLMFunctionDef"):
                method_name = stmt_data.get("name")
                if method_name not in existing_class.methods:
                    # 这是一个严重的封印漏洞：AST 中定义的方法在 STAGE 5 漏掉了
                    raise self.report_error(f"Hydration Leak: Method '{method_name}' of class '{name}' was not hydrated in STAGE 5. [Sealed Registry Violation]", stmt_uid)
                
                # 校验参数数量一致性 (如果有元数据支持)
                method_obj = existing_class.methods[method_name]
                if hasattr(method_obj, 'spec') and method_obj.spec:
                    # 获取 AST 中的参数列表
                    params = stmt_data.get("args", [])
                    # 简单校验参数数量 (注意：self 在运行时会被处理，此处校验声明的一致性)
                    expected_count = len(method_obj.spec.params) if hasattr(method_obj.spec, 'params') else -1
                    if expected_count != -1 and len(params) != expected_count:
                         # 强制执行严格契约校验
                         raise self.report_error(f"Contract Mismatch: Method '{method_name}' of class '{name}' parameter count mismatch. AST: {len(params)}, Descriptor: {expected_count}", stmt_uid)

        # 绑定到当前作用域 (作为常量类)
        return self.registry.get_none()

    def visit_IbReturn(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        value_uid = node_data.get("value")
        value = self.visit(value_uid) if value_uid else self.registry.get_none()
        raise ReturnException(value)

    def visit_IbBreak(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        raise BreakException()

    def visit_IbContinue(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        raise ContinueException()

    def visit_IbRaise(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        exc_uid = node_data.get("exc")
        exc_val = self.visit(exc_uid) if exc_uid else self.registry.get_none()
        raise ThrownException(exc_val)
