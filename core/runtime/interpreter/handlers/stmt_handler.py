from typing import Any, Mapping, List, Optional, Callable
from .base_handler import BaseHandler
from core.runtime.objects.kernel import IbObject, IbUserFunction, IbLLMFunction, IbClass
from core.runtime.exceptions import (
    ReturnException, BreakException, ContinueException, ThrownException, RetryException
)
from core.runtime.objects.intent import IbIntent, IntentMode, IntentRole
from core.foundation.diagnostics.core_debugger import CoreModule, DebugLevel
from core.runtime.enums import RegistrationState

from core.domain.issue import LLMUncertaintyError, InterpreterError
from core.foundation.diagnostics.codes import RUN_GENERIC_ERROR
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
        from core.runtime.objects.builtins import IbBehavior
        def action():
            res = self.visit(node_data.get("value"))
            # 如果是行为描述行，则立即执行（作为语句时）
            if isinstance(res, IbBehavior):
                return self.service_context.llm_executor.execute_behavior_object(res, self.context)
            return res
            
        return self.interpreter._with_llm_fallback(node_uid, node_data, action)

    def visit_IbAssign(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """赋值语句实现"""
        self.debugger.trace(CoreModule.INTERPRETER, DebugLevel.DETAIL, f"Executing assignment {node_uid}")
        
        def action():
            value_uid = node_data.get("value")
            value = self.visit(value_uid)
            
            # 处理多重赋值目标 (var a, b = 1)
            targets = node_data.get("targets", [])
            for target_uid in targets:
                target_data = self.get_node_data(target_uid)
                if not target_data: continue
                
                # 1. 普通变量赋值 (Name)
                if target_data["_type"] == "IbName":
                    sym_uid = self.get_side_table("node_to_symbol", target_uid)
                    name = target_data.get("id")
                    if sym_uid:
                        # 如果有 Symbol UID，则根据其是否存在于当前作用域决定 define 还是 set
                        if self.context.get_symbol_by_uid(sym_uid):
                            self.context.set_variable_by_uid(sym_uid, value)
                        else:
                            declared_type = self.interpreter._resolve_type_from_symbol(sym_uid)
                            self.context.define_variable(name, value, declared_type=declared_type, uid=sym_uid)
                    elif not self.interpreter.strict_mode:
                        # 回退到名称查找
                        # [IES 2.0] 动态回退：如果变量不存在则定义，存在则赋值
                        try:
                            self.context.get_variable(name)
                            self.context.set_variable(name, value)
                        except Exception:
                            self.context.define_variable(name, value)
                    else:
                        raise self.report_error(f"Strict mode: Symbol UID missing for assignment to '{name}'.", target_uid)
                
                # 2. 类型标注表达式 (TypeAnnotatedExpr)
                elif target_data["_type"] == "IbTypeAnnotatedExpr":
                    inner_target_uid = target_data.get("target")
                    inner_target_data = self.get_node_data(inner_target_uid)
                    if inner_target_data and inner_target_data["_type"] == "IbName":
                        sym_uid = self.get_side_table("node_to_symbol", inner_target_uid)
                        name = inner_target_data.get("id")
                        # 总是定义新变量
                        declared_type = self.interpreter._resolve_type_from_symbol(sym_uid)
                        self.context.define_variable(name, value, declared_type=declared_type, uid=sym_uid)
                
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
                    
            return self.registry.get_none()
            
        return self.interpreter._with_llm_fallback(node_uid, node_data, action)

    def visit_IbAugAssign(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """复合赋值实现 (a += 1)"""
        def action():
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
                    self.context.set_variable_by_uid(sym_uid, new_val)
                else:
                    self.context.set_variable(target_data.get("id"), new_val)
            elif target_data["_type"] == "IbAttribute":
                obj = self.visit(target_data.get("value"))
                attr = target_data.get("attr")
                obj.receive('__setattr__', [self.registry.box(attr), new_val])
                
            return self.registry.get_none()
            
        return self.interpreter._with_llm_fallback(node_uid, node_data, action)

    def visit_IbIf(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        def action():
            condition = self.visit(node_data.get("test"))
            if self.interpreter.is_truthy(condition):
                for stmt_uid in node_data.get("body", []):
                    self.visit(stmt_uid)
            else:
                for stmt_uid in node_data.get("orelse", []):
                    self.visit(stmt_uid)
            return self.registry.get_none()
            
        return self.interpreter._with_llm_fallback(node_uid, node_data, action)

    def visit_IbWhile(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        def action():
            while self.interpreter.is_truthy(self.visit(node_data.get("test"))):
                try:
                    for stmt_uid in node_data.get("body", []):
                        self.visit(stmt_uid)
                except BreakException: break
                except ContinueException: continue
            return self.registry.get_none()
            
        return self.interpreter._with_llm_fallback(node_uid, node_data, action)

    def visit_IbFor(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        from core.runtime.objects.builtins import IbList
        def action():
            target_uid = node_data.get("target")
            iter_uid = node_data.get("iter")
            body = node_data.get("body", [])
            
            # [IES 2.0] 条件驱动循环 (Condition-driven loop: for @~ ... ~:)
            if target_uid is None:
                # 这种情况不需要 to_list 协议，而是直接根据条件的真值决定是否继续
                while self.interpreter.is_truthy(self.visit(iter_uid)):
                    try:
                        for stmt_uid in body:
                            self.visit(stmt_uid)
                    except BreakException: 
                        return self.registry.get_none()
                    except ContinueException: 
                        continue
                return self.registry.get_none()

            # 标准 Foreach 循环 (for item in list)
            iterable_obj = self.visit(iter_uid)
            
            # UTS: 使用消息传递获取迭代列表 (to_list 协议)
            try:
                elements_obj = iterable_obj.receive('to_list', [])
                if not isinstance(elements_obj, IbList):
                    raise self.report_error(f"Object is not iterable", node_uid)
                
                elements = elements_obj.elements
            except (ReturnException, BreakException, ContinueException, RetryException, ThrownException):
                raise
            except Exception as e:
                if isinstance(e, InterpreterError): raise
                raise self.report_error(f"Iteration failed: {str(e)}", node_uid)
            
            total = len(elements)
            for i, item in enumerate(elements):
                # 注入循环上下文
                self.context.push_loop_context(i, total)
                
                # 绑定循环变量
                target_data = self.get_node_data(target_uid)
                if target_data and target_data["_type"] == "IbName":
                    name = target_data.get("id")
                    sym_uid = self.get_side_table("node_to_symbol", target_uid)
                    declared_type = self.interpreter._resolve_type_from_symbol(sym_uid)
                    self.context.define_variable(name, item, declared_type=declared_type, uid=sym_uid)
                
                try:
                    for stmt_uid in body:
                        self.visit(stmt_uid)
                except BreakException: 
                    self.context.pop_loop_context()
                    return self.registry.get_none()
                except ContinueException: 
                    self.context.pop_loop_context()
                    continue
                finally:
                    self.context.pop_loop_context()
            return self.registry.get_none()
            
        return self.interpreter._with_llm_fallback(node_uid, node_data, action)

    def visit_IbTry(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """实现异常处理块"""
        def action():
            try:
                for stmt_uid in node_data.get("body", []):
                    self.visit(stmt_uid)
            except (ReturnException, BreakException, ContinueException, RetryException):
                raise
            except (ThrownException, Exception) as e:
                # 包装 Python 原生异常
                error_obj = e.value if isinstance(e, ThrownException) else self.registry.box(str(e))
                
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
                        self.context.define_variable(name, error_obj)
                    
                    # 3. 执行处理体
                    for stmt_uid in handler_data.get("body", []):
                        self.visit(stmt_uid)
                    handled = True
                    break
                if not handled: raise
            finally:
                for stmt_uid in node_data.get("finalbody", []):
                    self.visit(stmt_uid)
            return self.registry.get_none()
            
        return self.interpreter._with_llm_fallback(node_uid, node_data, action)

    def visit_IbRetry(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        hint_uid = node_data.get("hint")
        hint_val = None
        if hint_uid:
            hint_obj = self.visit(hint_uid)
            hint_val = hint_obj.to_native() if hasattr(hint_obj, 'to_native') else str(hint_obj)
        
        # 将 hint 设置到 LLM 执行器中
        self.service_context.llm_executor.retry_hint = hint_val
        raise RetryException()

    def visit_IbFunctionDef(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """普通函数定义"""
        sym_uid = self.get_side_table("node_to_symbol", node_uid)
        declared_type = self.interpreter._resolve_type_from_symbol(sym_uid)
        func = IbUserFunction(node_uid, self.interpreter, descriptor=declared_type)
        name = node_data.get("name")
        self.context.define_variable(name, func, declared_type=declared_type, uid=sym_uid)
        return self.registry.get_none()

    def visit_IbLLMFunctionDef(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """LLM 函数 definition"""
        sym_uid = self.get_side_table("node_to_symbol", node_uid)
        declared_type = self.interpreter._resolve_type_from_symbol(sym_uid)
        func = IbLLMFunction(node_uid, self.service_context.llm_executor, self.interpreter, descriptor=declared_type)
        name = node_data.get("name")
        self.context.define_variable(name, func, declared_type=declared_type, uid=sym_uid)
        return self.registry.get_none()

    def visit_IbClassDef(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """验证类契约并将其绑定到当前作用域"""
        # [IES 2.0] IES 2.0 规范下，类必须在 STAGE 5 预水合完成。
        # 此处仅负责契约验证与作用域定义。
        name = node_data.get("name")
        is_ready = self.registry.state_level >= RegistrationState.STAGE_6_READY.value
        
        # 获取或创建符号 UID
        sym_uid = self.get_side_table("node_to_symbol", node_uid)
        
        if is_ready:
            # [IES 2.0] 生产环境/封印状态：不再允许创建和注册新类，仅执行契约校验
            existing_class = self.registry.get_class(name)
            if not existing_class:
                raise self.report_error(f"Sealed Registry Error: Class '{name}' must be pre-hydrated in STAGE 5. [IES 2.0 Contract Violation]", node_uid)
            
            # 绑定到当前作用域 (作为常量类)
            self.context.define_variable(name, existing_class, uid=sym_uid)
            
            # TODO: 深度契约校验（验证方法是否存在、参数是否一致）
            return self.registry.get_none()

        # --- 以下逻辑仅用于非 READY 状态 (如 STAGE 5 水合或极少数动态调试场景) ---
        parent_name = node_data.get("parent") or "Object"
        descriptor = self.interpreter._resolve_type_from_symbol(sym_uid)
        
        if not descriptor:
            # [IES 2.0 Strict] 除非是动态代码，否则描述符必须在符号表中存在
            if is_ready:
                raise self.report_error(f"Metadata Error: Descriptor missing for class '{name}'.", node_uid)
            
            # 动态回退逻辑 (仅用于极少数非标准加载场景)
            descriptor = self.registry.get_metadata_registry().factory.create_class(name, parent=parent_name)
            
        new_class = self.registry.create_subclass(name, descriptor, parent_name)
        
        # 注册方法与字段 (时序重构：字段仅记录 UID)
        body = node_data.get("body", [])
        for stmt_uid in body:
            stmt_data = self.get_node_data(stmt_uid)
            if not stmt_data: continue
            
            if stmt_data["_type"] == "IbFunctionDef":
                m_sym_uid = self.get_side_table("node_to_symbol", stmt_uid)
                declared_type = self.interpreter._resolve_type_from_symbol(m_sym_uid)
                new_class.register_method(stmt_data["name"], IbUserFunction(stmt_uid, self.interpreter, descriptor=declared_type))
            elif stmt_data["_type"] == "IbLLMFunctionDef":
                m_sym_uid = self.get_side_table("node_to_symbol", stmt_uid)
                declared_type = self.interpreter._resolve_type_from_symbol(m_sym_uid)
                new_class.register_method(stmt_data["name"], IbLLMFunction(stmt_uid, self.service_context.llm_executor, self.interpreter, descriptor=declared_type))
            elif stmt_data["_type"] == "IbAssign":
                val_uid = stmt_data.get("value")
                for target_uid in stmt_data.get("targets", []):
                    target_name = self.interpreter._extract_name_id(target_uid)
                    if target_name:
                        # 简单字面量快照优化
                        val_data = self.get_node_data(val_uid) if val_uid else None
                        if val_data and val_data["_type"] == "IbConstant":
                            static_val = self.registry.box(self.interpreter._resolve_value(val_data.get("value")))
                        else:
                            static_val = None
                        new_class.default_fields[target_name] = (val_uid, static_val)
        
        self.context.define_variable(name, new_class, uid=sym_uid)
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
            
        content = intent_data.get('content', '')
        mode = IntentMode.from_str(intent_data.get('mode', '+'))
        tag = intent_data.get('tag')
        segments = intent_data.get('segments', [])
        
        intent = IbIntent(
            ib_class=self.registry.get_class("Intent"),
            content=content,
            mode=mode,
            tag=tag,
            segments=segments,
            role=IntentRole.BLOCK,
            source_uid=intent_uid
        )
            
        self.context.push_intent(intent)
        try:
            for stmt_uid in node_data.get("body", []):
                self.visit(stmt_uid)
        finally:
            self.context.pop_intent()
        return self.registry.get_none()
