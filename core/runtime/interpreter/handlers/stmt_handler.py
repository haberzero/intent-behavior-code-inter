from typing import Any, Mapping, List, Optional, Callable
from core.runtime.interpreter.handlers.base_handler import BaseHandler
from core.runtime.objects.kernel import IbObject, IbUserFunction, IbLLMFunction, IbClass
from core.runtime.interfaces import IExecutionContext, ServiceContext, IIbList, IIbBehavior
from core.runtime.exceptions import (
    ReturnException, BreakException, ContinueException, ThrownException, RetryException
)
from core.runtime.objects.intent import IbIntent, IntentMode, IntentRole
from core.base.diagnostics.debugger import CoreModule, DebugLevel
from core.base.enums import RegistrationState

from core.kernel.issue import LLMUncertaintyError, InterpreterError
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

    def visit_IbExprStmt(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """表达式语句"""
        res = self.visit(node_data.get("value"))
        # 如果是行为描述行，则立即执行（作为语句时）
        if isinstance(res, IIbBehavior):
            return self._execute_behavior(res)
        return res

    def _assign_to_target(self, target_uid: str, value: IbObject, define_only: bool = False):
        """通用赋值逻辑，支持 Name, TypeAnnotatedExpr, Attribute, Subscript, Tuple Unpacking"""
        target_data = self.get_node_data(target_uid)
        if not target_data: return
        
        # 1. 普通变量赋值 (Name)
        if target_data["_type"] == "IbName":
            sym_uid = self.get_side_table("node_to_symbol", target_uid)
            name = target_data.get("id")
            if sym_uid:
                # 如果有 Symbol UID，则根据其是否存在于当前作用域决定 define 还是 set
                if not define_only and self.runtime_context.get_symbol_by_uid(sym_uid):
                    self.runtime_context.set_variable_by_uid(sym_uid, value)
                else:
                    declared_type = self.execution_context.resolve_type_from_symbol(sym_uid)
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
            elements_obj = value.receive('to_list', [])
            if not isinstance(elements_obj, IIbList):
                raise self.report_error(f"Cannot unpack non-iterable object", target_uid)
            
            vals = elements_obj.elements
            targets = target_data.get("elts", [])
            if len(vals) != len(targets):
                raise self.report_error(f"Unpack error: expected {len(targets)} values, got {len(vals)}", target_uid)
            
            for t_uid, val in zip(targets, vals):
                self._assign_to_target(t_uid, val, define_only=define_only)

    def visit_IbAssign(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """实现赋值语句"""
        self.debugger.trace(CoreModule.INTERPRETER, DebugLevel.DETAIL, f"Executing assignment {node_uid}")
        value = self.visit(node_data.get("value"))
        
        for target_uid in node_data.get("targets", []):
            self._assign_to_target(target_uid, value)
                
        return self.registry.get_none()

    def visit_IbAugAssign(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """复合赋值实现 (a += 1)"""
        target_uid = node_data.get("target")
        target_data = self.get_node_data(target_uid)
        
        value = self.visit(node_data.get("value"))
        op_symbol = node_data.get("op")
        
        # [IES 2.0] 使用全局归一化映射，支持完整运算符集（包含 % // 等）
        op = AST_OP_MAP.get(op_symbol, op_symbol)
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

    def visit_IbIf(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """条件分支语句"""
        condition = self.visit(node_data.get("test"))
        if self.execution_context.is_truthy(condition):
            for stmt_uid in node_data.get("body", []):
                self.visit(stmt_uid)
        else:
            for stmt_uid in node_data.get("orelse", []):
                self.visit(stmt_uid)
        return self.registry.get_none()

    def visit_IbWhile(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """循环语句"""
        while True:
            condition = self.visit(node_data.get("test"))
            if not self.execution_context.is_truthy(condition):
                break
            
            # [IES 2.2 Fix] 局部重试支持，防止冒泡导致条件判定被跳过或重复执行
            retry_count = 0
            while True:
                try:
                    for stmt_uid in node_data.get("body", []):
                        self.visit(stmt_uid)
                    break # 成功完成当前迭代逻辑
                except BreakException:
                    return self.registry.get_none()
                except ContinueException:
                    break # 跳出局部重试，由外层 while 进行下一次条件判定
                except (LLMUncertaintyError, RetryException) as e:
                    fallback_uids = node_data.get("llm_fallback", [])
                    if not fallback_uids and isinstance(e, LLMUncertaintyError):
                        raise e # 无局部处理，向上冒泡
                    
                    retry_count += 1
                    if retry_count > 3: raise e
                    
                    if fallback_uids:
                        for f_uid in fallback_uids:
                            self.visit(f_uid)
                    continue # 重新执行当前循环体
        return self.registry.get_none()
    
    def visit_IbFor(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """迭代循环语句实现"""
        target_uid = node_data.get("target")
        iter_uid = node_data.get("iter")
        body = node_data.get("body", [])
        
        # [IES 2.0] 条件驱动循环 (Condition-driven loop: for @~ ... ~:)
        if target_uid is None:
            while self.execution_context.is_truthy(self.visit(iter_uid)):
                # [IES 2.2 Fix] 局部重试支持
                retry_count = 0
                while True:
                    try:
                        for stmt_uid in body:
                            self.visit(stmt_uid)
                        break
                    except BreakException: 
                        return self.registry.get_none()
                    except ContinueException: 
                        break
                    except (LLMUncertaintyError, RetryException) as e:
                        fallback_uids = node_data.get("llm_fallback", [])
                        if not fallback_uids and isinstance(e, LLMUncertaintyError):
                            raise e
                        
                        retry_count += 1
                        if retry_count > 3: raise e
                        
                        if fallback_uids:
                            for f_uid in fallback_uids:
                                self.visit(f_uid)
                        continue
            return self.registry.get_none()

        # 标准 Foreach 循环 (for item in list)
        iterable_obj = self.visit(iter_uid)
        elements_obj = iterable_obj.receive('to_list', [])
        if not isinstance(elements_obj, IIbList):
            raise self.report_error(f"Object is not iterable", node_uid)
        
        elements = elements_obj.elements
        total = len(elements)
        for i, item in enumerate(elements):
            # [IES 2.2 Fix] 局部重试闭环，防止冒泡导致迭代器重置 (死循环隐患修复)
            retry_count = 0
            while True:
                self.runtime_context.push_loop_context(i, total)
                
                # [IES 2.2 Fix] 使用统一的赋值逻辑支持复杂循环目标
                if target_uid:
                    self._assign_to_target(target_uid, item, define_only=True)
                
                try:
                    for stmt_uid in body:
                        self.visit(stmt_uid)
                    self.runtime_context.pop_loop_context()
                    break # 成功完成当前项，进入下一个元素
                except BreakException: 
                    self.runtime_context.pop_loop_context()
                    return self.registry.get_none()
                except ContinueException: 
                    self.runtime_context.pop_loop_context()
                    break # 跳出局部重试，由外层 enumerate 进入下一项
                except (LLMUncertaintyError, RetryException) as e:
                    self.runtime_context.pop_loop_context()
                    
                    fallback_uids = node_data.get("llm_fallback", [])
                    # 只有在有 fallback 或显式 RetryException 时才在局部拦截
                    if not fallback_uids and isinstance(e, LLMUncertaintyError):
                        raise e
                    
                    retry_count += 1
                    if retry_count > 3: raise e
                    
                    if fallback_uids:
                        for f_uid in fallback_uids:
                            self.visit(f_uid)
                    # 继续局部 while True，即重新执行当前 item 的逻辑
                    continue
        return self.registry.get_none()

    def visit_IbTry(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """实现异常处理块"""
        try:
            for stmt_uid in node_data.get("body", []):
                self.visit(stmt_uid)
        except (ReturnException, BreakException, ContinueException, RetryException):
            raise
        except (ThrownException, Exception) as e:
            # [IES 2.1 Refactor] 统一异常对象化
            if isinstance(e, ThrownException):
                error_obj = e.value
            else:
                # 包装 Python 原生异常为 IBC-Inter 的 Exception 实例
                exc_class = self.registry.get_class("Exception")
                if not exc_class:
                    raise self.report_error("Critical Error: 'Exception' builtin class not found in registry. Bootstrap failed.", node_uid)
                
                # [FIX] 传入空参数列表给 instantiate
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
                    # [IES 2.2 Fix] 使用统一的赋值逻辑支持异常变量绑定
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
        hint_uid = node_data.get("hint")
        hint_val = None
        if hint_uid:
            hint_obj = self.visit(hint_uid)
            hint_val = hint_obj.to_native() if hasattr(hint_obj, 'to_native') else str(hint_obj)
        
        # 将 hint 设置到运行时上下文
        self.runtime_context.retry_hint = hint_val
        raise RetryException()

    def visit_IbFunctionDef(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """普通函数定义"""
        sym_uid = self.get_side_table("node_to_symbol", node_uid)
        declared_type = self.execution_context.resolve_type_from_symbol(sym_uid)
        func = IbUserFunction(node_uid, self.execution_context, descriptor=declared_type)
        name = node_data.get("name")
        self.runtime_context.define_variable(name, func, declared_type=declared_type, uid=sym_uid)
        return self.registry.get_none()

    def visit_IbLLMFunctionDef(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """LLM 函数 definition"""
        sym_uid = self.get_side_table("node_to_symbol", node_uid)
        declared_type = self.execution_context.resolve_type_from_symbol(sym_uid)
        func = IbLLMFunction(node_uid, self.service_context.llm_executor, self.execution_context, descriptor=declared_type)
        name = node_data.get("name")
        self.runtime_context.define_variable(name, func, declared_type=declared_type, uid=sym_uid)
        return self.registry.get_none()

    def visit_IbClassDef(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """验证类契约并将其绑定到当前作用域"""
        # [IES 2.0] IES 2.0 规范下，类必须在 STAGE 5 预水合完成。
        # 此处仅负责契约验证与作用域定义。
        name = node_data.get("name")
        
        # [IES 2.0] 生产环境/封印状态：不再允许创建和注册新类，仅执行契约校验
        existing_class = self.registry.get_class(name)
        if not existing_class:
            raise self.report_error(f"Sealed Registry Error: Class '{name}' must be pre-hydrated in STAGE 5. [IES 2.0 Contract Violation]", node_uid)
        
        # 绑定到当前作用域 (作为常量类)
        sym_uid = self.get_side_table("node_to_symbol", node_uid)
        self.runtime_context.define_variable(name, existing_class, uid=sym_uid)
        
        # [IES 2.1 Deep Audit] 深度契约校验：验证 AST 定义的方法是否全部在运行时虚表中就绪
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
                if hasattr(method_obj, 'descriptor') and method_obj.descriptor:
                    # 获取 AST 中的参数列表
                    params = stmt_data.get("args", [])
                    # 简单校验参数数量 (注意：self 在运行时会被处理，此处校验声明的一致性)
                    expected_count = len(method_obj.descriptor.params) if hasattr(method_obj.descriptor, 'params') else -1
                    if expected_count != -1 and len(params) != expected_count:
                         # [IES 2.1 Final Audit] 强制执行严格契约校验
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

    def visit_IbIntentStmt(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """处理意图块 (IES 2.0 强契约)"""
        intent_uid = node_data.get("intent")
        intent_data = self.get_node_data(intent_uid)
        
        # [Active Defense] 仅接受结构化意图对象，不再支持原始字符串
        if not intent_data:
            raise self.report_error("Invalid intent metadata: Intent must be a structured IbIntentInfo node.")
            
        # [IES 2.1 Factory] 统一使用工厂方法构造，消除局部 import 和具体类依赖
        intent = self.execution_context.factory.create_intent_from_node(
            intent_uid, 
            intent_data, 
            role=IntentRole.BLOCK
        )
            
        self.runtime_context.push_intent(intent)
        try:
            for stmt_uid in node_data.get("body", []):
                self.visit(stmt_uid)
        finally:
            self.runtime_context.pop_intent()
        return self.registry.get_none()
