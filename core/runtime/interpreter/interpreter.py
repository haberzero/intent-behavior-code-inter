from typing import Any, Dict, List, Optional, Callable, Union
from core.types import parser_types as ast
from core.types.exception_types import (
    InterpreterError, ReturnException, BreakException, ContinueException, ThrownException,
    LLMUncertaintyError, RetryException
)
from core.support.diagnostics.codes import (
    RUN_GENERIC_ERROR, RUN_TYPE_MISMATCH, RUN_UNDEFINED_VARIABLE,
    RUN_LIMIT_EXCEEDED, RUN_CALL_ERROR
)
from core.foundation.interfaces import (
    Interpreter as InterpreterInterface, 
    RuntimeContext, LLMExecutor, InterOp, ModuleManager, ServiceContext, IssueTracker,
    PermissionManager, Scope
)
from .runtime_context import RuntimeContextImpl
from .llm_executor import LLMExecutorImpl
from .interop import InterOpImpl
from .module_manager import ModuleManagerImpl
from .permissions import PermissionManager as PermissionManagerImpl
from core.foundation.kernel import IbObject, IbClass, IbUserFunction, IbFunction, IbNativeFunction
from core.foundation.kernel import Type, ListType, DictType, ANY_TYPE
from core.foundation.builtins import IbInteger, IbString, IbList, IbNone, initialize_builtin_classes
from core.foundation.bootstrapper import Bootstrapper
from core.support.host_interface import HostInterface
from core.foundation.capabilities import IStackInspector
from core.support.diagnostics.core_debugger import CoreModule, DebugLevel, core_debugger



# 运算符映射 (模拟汇编操作码)
OP_MAPPING = {
    '+': '__add__',
    '-': '__sub__',
    '*': '__mul__',
    '/': '__div__',
    '//': '__div__',
    '%': '__mod__',
    '&': '__and__',
    '|': '__or__',
    '^': '__xor__',
    '<<': '__lshift__',
    '>>': '__rshift__',
    '==': '__eq__',
    '!=': '__ne__',
    '<': '__lt__',
    '<=': '__le__',
    '>': '__gt__',
    '>=': '__ge__',
}

UNARY_OP_MAPPING = {
    '-': '__neg__',
    '+': '__pos__',
    'not': '__not__',
    '~': '__invert__',
}

class ServiceContextImpl:
    """注入容器实现类 (已移除 Evaluator)"""
    def __init__(self, issue_tracker: IssueTracker, 
                 runtime_context: RuntimeContext,
                 llm_executor: LLMExecutor,
                 module_manager: ModuleManager,
                 interop: InterOp,
                 permission_manager: PermissionManager,
                 interpreter: InterpreterInterface,
                 debugger: Any = None):
        self._issue_tracker = issue_tracker
        self._runtime_context = runtime_context
        self._llm_executor = llm_executor
        self._module_manager = module_manager
        self._interop = interop
        self._permission_manager = permission_manager
        self._interpreter = interpreter
        self._debugger = debugger

    @property
    def debugger(self) -> Any: return self._debugger
    @property
    def interpreter(self) -> InterpreterInterface: return self._interpreter
    @property
    def issue_tracker(self) -> IssueTracker: return self._issue_tracker
    @property
    def runtime_context(self) -> RuntimeContext: return self._runtime_context
    @property
    def llm_executor(self) -> LLMExecutor: return self._llm_executor
    @property
    def module_manager(self) -> ModuleManager: return self._module_manager
    @property
    def interop(self) -> InterOp: return self._interop
    @property
    def permission_manager(self) -> PermissionManager: return self._permission_manager

class Interpreter(IStackInspector):
    """
    IBC-Inter 2.0 消息传递解释器。
    彻底转向基于 IbObject 的统一对象模型。
    """
    def get_call_stack_depth(self) -> int:
        return self.call_stack_depth

    def get_active_intents(self) -> List[str]:
        return [i.content for i in self.context.get_active_intents()]

    def get_instruction_count(self) -> int:
        return self.instruction_count

    def get_captured_intents(self, obj: Any) -> List[str]:
        # TODO: 适配新的意图捕获逻辑
        return []

    def __init__(self, issue_tracker: IssueTracker,
                 output_callback: Optional[Callable[[str], None]] = None, 
                 max_instructions: int = 10000, 
                 max_call_stack: int = 100,
                 artifact: Optional[Any] = None,
                 host_interface: Optional[HostInterface] = None,
                 debugger: Optional[Any] = None,
                 root_dir: str = "."):
        
        # 0. 启动内核引导
        initialize_builtin_classes()
        
        self.output_callback = output_callback
        self.artifact = artifact
        self.host_interface = host_interface or HostInterface()
        self.debugger = debugger or core_debugger
        
        # 1. 初始化基础组件
        runtime_context = RuntimeContextImpl()
        interop = InterOpImpl(host_interface=self.host_interface)
        
        # 权限管理
        permission_manager = PermissionManagerImpl(root_dir)
        
        # 2. 初始化 ModuleManager
        module_manager = ModuleManagerImpl(
            interop, 
            artifact=artifact, 
            interpreter=None,
            root_dir=root_dir
        )
        
        # 3. 创建 ServiceContext
        llm_executor = LLMExecutorImpl()
        
        self.service_context = ServiceContextImpl(
            issue_tracker=issue_tracker,
            runtime_context=runtime_context,
            llm_executor=llm_executor,
            module_manager=module_manager,
            interop=interop,
            permission_manager=permission_manager,
            interpreter=self,
            debugger=self.debugger
        )
        
        # 4. 完成子组件的注入
        llm_executor.service_context = self.service_context
        module_manager.set_interpreter(self)
        
        self._current_context = runtime_context
        self._setup_context(self._current_context)

        # 运行限制
        self.max_instructions = max_instructions
        self.instruction_count = 0
        self.max_call_stack = max_call_stack
        self.call_stack_depth = 0

    def _setup_context(self, context: RuntimeContext):
        """为 Context 注入基础内置变量"""
        # 使用私有属性访问以仅检查当前作用域，避免与后续 bootstrap 冲突
        global_symbols = context.global_scope.get_all_symbols()
        
        if 'print' not in global_symbols:
            context.define_variable('print', IbNativeFunction(self._builtin_print, is_method=False), is_const=True)
        
        # 注入内置类 (int, str, float, list, dict 等)
        for name, ib_class in Bootstrapper.get_all_classes().items():
            if name not in global_symbols:
                context.define_variable(name, ib_class, is_const=True)

        # [NEW] 注入来自编译蓝图的全局符号
        if self.artifact and self.artifact.global_symbols:
            from core.compiler.semantic.symbols import Symbol
            for name, val in self.artifact.global_symbols.items():
                if name not in global_symbols and not isinstance(val, Symbol):
                    # 如果是运行时对象（非静态符号），则注入
                    context.define_variable(name, val)

    @property
    def context(self) -> RuntimeContext:
        return self._current_context

    @context.setter
    def context(self, value: RuntimeContext):
        self._current_context = value

    def interpret(self, module: ast.Module) -> IbObject:
        return self.execute_module(module)

    def execute_module(self, module: ast.Module, scope: Optional[Scope] = None) -> IbObject:
        self.debugger.trace(CoreModule.INTERPRETER, DebugLevel.BASIC, "Starting execution...")
        
        old_context = self._current_context
        if scope:
             # 创建新 Context 并绑定 Scope
             new_ctx = RuntimeContextImpl(initial_scope=scope)
             self._current_context = new_ctx
             self._setup_context(self._current_context)

        self.instruction_count = 0
        result = IbNone()
        try:
            for stmt in module.body:
                result = self.visit(stmt)
            self.debugger.trace(CoreModule.INTERPRETER, DebugLevel.BASIC, "Execution complete.")
            return result
        except InterpreterError as e:
            if self.service_context.issue_tracker:
                from core.types.diagnostic_types import Severity
                self.service_context.issue_tracker.report(
                    Severity.ERROR,
                    e.error_code or RUN_GENERIC_ERROR,
                    e.message,
                    location=e.node
                )
            raise
        except (ReturnException, BreakException, ContinueException):
            raise InterpreterError("Control flow statement used outside of function or loop.", error_code=RUN_GENERIC_ERROR)
        except Exception as e:
            msg = f"Runtime error: {str(e)}"
            if self.service_context.issue_tracker:
                from core.types.diagnostic_types import Severity
                self.service_context.issue_tracker.report(Severity.FATAL, RUN_GENERIC_ERROR, msg)
            raise InterpreterError(msg, error_code=RUN_GENERIC_ERROR)
        finally:
            self._current_context = old_context

    def visit(self, node: ast.ASTNode) -> IbObject:
        """核心 Visitor 分发方法"""
        self.instruction_count += 1
        
        if self.instruction_count > self.max_instructions:
            raise InterpreterError("Execution limit exceeded", node, error_code=RUN_LIMIT_EXCEEDED)

        if self.call_stack_depth >= self.max_call_stack:
             raise InterpreterError("Recursion depth exceeded", node, error_code=RUN_LIMIT_EXCEEDED)
        
        self.call_stack_depth += 1
        try:
            method_name = f'visit_{node.__class__.__name__}'
            visitor = getattr(self, method_name, self.generic_visit)
            return visitor(node)
        except (ReturnException, BreakException, ContinueException, RetryException, ThrownException):
            raise
        except InterpreterError:
            raise
        except Exception as e:
            raise InterpreterError(f"{type(e).__name__}: {str(e)}", node, error_code=RUN_GENERIC_ERROR) from e
        finally:
            self.call_stack_depth -= 1

    def generic_visit(self, node: ast.ASTNode):
        raise InterpreterError(f"No visit method implemented for {node.__class__.__name__}", node, error_code=RUN_GENERIC_ERROR)

    # --- 访问方法实现 ---

    def visit_Module(self, node: ast.Module):
        result = IbNone()
        for stmt in node.body:
            result = self.visit(stmt)
        return result

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """定义普通函数"""
        func = IbUserFunction(node, self)
        self.context.define_variable(node.name, func)
        return IbNone()

    def visit_LLMFunctionDef(self, node: ast.LLMFunctionDef):
        """定义 LLM 函数"""
        from core.foundation.kernel import IbLLMFunction
        func = IbLLMFunction(node, self.service_context.llm_executor, self)
        self.context.define_variable(node.name, func)
        return IbNone()

    def visit_Constant(self, node: ast.Constant) -> IbObject:
        """UTS: 统一常量装箱"""
        return Bootstrapper.box(node.value)

    def visit_BinOp(self, node: ast.BinOp) -> IbObject:
        left = self.visit(node.left)
        right = self.visit(node.right)
        method = OP_MAPPING.get(node.op)
        if not method: raise InterpreterError(f"Unsupported op: {node.op}", node)
        return left.receive(method, [right])

    def visit_Compare(self, node: ast.Compare) -> IbObject:
        """处理比较运算 -> 消息发送"""
        left = self.visit(node.left)
        # 简化处理：只取第一个比较操作符
        op = node.ops[0]
        right = self.visit(node.comparators[0])
        
        method = OP_MAPPING.get(op)
        if not method: raise InterpreterError(f"Unsupported comparison: {op}", node)
        return left.receive(method, [right])

    def visit_ListExpr(self, node: ast.ListExpr) -> IbObject:
        """列表字面量 -> 统一装箱"""
        elts = [self.visit(e) for e in node.elts]
        return Bootstrapper.box(elts)

    def visit_Dict(self, node: ast.Dict) -> IbObject:
        """字典字面量 -> 统一装箱"""
        data = {}
        for k, v in zip(node.keys, node.values):
            key_obj = self.visit(k) if k else IbNone()
            val_obj = self.visit(v)
            native_key = key_obj.to_native() if hasattr(key_obj, 'to_native') else key_obj
            data[native_key] = val_obj
        return Bootstrapper.box(data)

    def visit_CastExpr(self, node: ast.CastExpr) -> IbObject:
        """类型强转 (Type) Expr"""
        from core.foundation.bootstrapper import Bootstrapper
        target_class = Bootstrapper.get_class(node.type_name)
        value = self.visit(node.value)
        
        if not target_class:
            raise InterpreterError(f"Unknown type: {node.type_name}", node)
            
        # 如果是 IbBehavior，执行它并强转
        return value.receive('cast_to', [target_class])

    def visit_Subscript(self, node: ast.Subscript) -> IbObject:
        """下标访问 -> __getitem__"""
        value = self.visit(node.value)
        slice_obj = self.visit(node.slice)
        return value.receive('__getitem__', [slice_obj])

    def visit_UnaryOp(self, node: ast.UnaryOp) -> IbObject:
        """一元运算 -> 消息发送"""
        operand = self.visit(node.operand)
        method = UNARY_OP_MAPPING.get(node.op)
        if not method: raise InterpreterError(f"Unsupported unary op: {node.op}", node)
        return operand.receive(method, [])

    def visit_Name(self, node: ast.Name) -> IbObject:
        val = self.context.get_variable(node.id)
        if not isinstance(val, IbObject):
            # 自动装箱以兼容外部注入或旧代码
            return self._box_native(val)
        return val

    def _box_native(self, val: Any) -> IbObject:
        """UTS: 转发至统一装箱逻辑"""
        return Bootstrapper.box(val)

    def visit_Assign(self, node: ast.Assign):
        self.debugger.trace(CoreModule.INTERPRETER, DebugLevel.DETAIL, f"Executing assignment to {len(node.targets)} targets")
        def action():
            # 注入预期返回类型 (用于 LLM Executor 优化提示词)
            type_pushed = False
            target_type = ANY_TYPE
            if node.type_annotation:
                target_type = self._resolve_type(node.type_annotation)
                self.service_context.llm_executor.push_expected_type(target_type.name)
                type_pushed = True
            
            try:
                value = self.visit(node.value)
                
                # 关键：如果存在 llmexcept (fallback) 块，或者目标不是 callable/var 类型，则强制立即执行行为
                from core.foundation.builtins import IbBehavior
                if isinstance(value, IbBehavior):
                    force_eager = False
                    if node.llm_fallback:
                        force_eager = True
                    elif node.type_annotation:
                        if target_type.name not in ("callable", "var", "Any"):
                            force_eager = True
                    
                    if force_eager:
                        value = value._execute()
                
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        # UTS: 使用统一的类型兼容性检查协议
                        if node.type_annotation:
                            if not value.ib_class.is_assignable_to(target_type):
                                try:
                                    # 尝试自动转换协议 (如 str -> int)
                                    value = value.receive('cast_to', [target_type])
                                except (AttributeError, Exception):
                                    raise InterpreterError(f"Type mismatch: Cannot assign '{value.ib_class.name}' to '{target_type.name}'", node)
                        
                        self.context.define_variable(target.id, value)
                    elif isinstance(target, ast.Attribute):
                        obj = self.visit(target.value)
                        from core.foundation.builtins import IbString
                        obj.receive('__setattr__', [IbString(target.attr), value])
                    elif isinstance(target, ast.Subscript):
                        obj = self.visit(target.value)
                        slice_val = self.visit(target.slice)
                        obj.receive('__setitem__', [slice_val, value])
                return IbNone()
            finally:
                if type_pushed:
                    self.service_context.llm_executor.pop_expected_type()
            
        return self._with_llm_fallback(node, action)

    def visit_AugAssign(self, node: ast.AugAssign):
        """处理 +=, -= 等 -> 消息发送"""
        def action():
            target = node.target
            value = self.visit(node.value)
            method = OP_MAPPING.get(node.op)
            if not method: raise InterpreterError(f"Unsupported aug op: {node.op}", node)
            
            # 获取当前值
            if isinstance(target, ast.Name):
                current = self.context.get_variable(target.id)
                new_val = current.receive(method, [value])
                self.context.set_variable(target.id, new_val)
            elif isinstance(target, ast.Attribute):
                obj = self.visit(target.value)
                from core.foundation.builtins import IbString
                attr_name = IbString(target.attr)
                current = obj.receive('__getattr__', [attr_name])
                new_val = current.receive(method, [value])
                obj.receive('__setattr__', [attr_name, new_val])
            else:
                raise InterpreterError("Unsupported aug assign target", node)
            return IbNone()
            
        return self._with_llm_fallback(node, action)

    def visit_BoolOp(self, node: ast.BoolOp) -> IbObject:
        """处理 and/or 逻辑运算 (短路求值)"""
        from core.foundation.builtins import IbInteger
        is_or = node.op == 'or'
        
        last_val = None
        for expr in node.values:
            val = self.visit(expr)
            last_val = val
            truthy = self.is_truthy(val)
            if is_or and truthy: return val
            if not is_or and not truthy: return val
            
        return last_val or IbNone()

    def visit_IfExp(self, node: ast.IfExp) -> IbObject:
        """处理三元表达式"""
        if self.is_truthy(self.visit(node.test)):
            return self.visit(node.body)
        return self.visit(node.orelse)

    def visit_Call(self, node: ast.Call) -> IbObject:
        func = self.visit(node.func)
        args = [self.visit(arg) for arg in node.args]
        
        # UTS: 使用 __call__ 协议统一处理调用
        # func 可能是 IbFunction, IbBoundMethod 或 IbClass (构造函数)
        try:
            if node.intent:
                self.context.push_intent(node.intent)
            
            # 统一通过消息传递
            return func.receive('__call__', args)
        finally:
            if node.intent:
                self.context.pop_intent()


    def visit_Attribute(self, node: ast.Attribute) -> IbObject:
        """属性访问 -> __getattr__"""
        obj = self.visit(node.value)
        from core.foundation.builtins import IbString
        return obj.receive('__getattr__', [IbString(node.attr)])

    def visit_If(self, node: ast.If):
        def action():
            condition = self.visit(node.test)
            if self.is_truthy(condition):
                for stmt in node.body: self.visit(stmt)
            elif node.orelse:
                for stmt in node.orelse: self.visit(stmt)
            return IbNone()
            
        return self._with_llm_fallback(node, action)

    def visit_While(self, node: ast.While):
        def action():
            while self.is_truthy(self.visit(node.test)):
                try:
                    for stmt in node.body: self.visit(stmt)
                except BreakException: break
                except ContinueException: continue
            return IbNone()
            
        return self._with_llm_fallback(node, action)

    def visit_For(self, node: ast.For):
        def action():
            # 1. 广义 For 循环 (Condition-based)
            if node.target is None:
                while self.is_truthy(self.visit(node.iter)):
                    try:
                        for stmt in node.body: self.visit(stmt)
                    except BreakException: break
                    except ContinueException: continue
                return IbNone()

            # 2. 标准 Foreach 循环
            iterable_obj = self.visit(node.iter)
            
            # UTS: 使用消息传递获取迭代列表 (to_list 协议)
            elements_obj = iterable_obj.receive('to_list', [])
            from core.foundation.builtins import IbList
            if not isinstance(elements_obj, IbList):
                raise InterpreterError(f"Object of type '{iterable_obj.ib_class.name}' is not iterable (to_list failed)", node)
            
            elements = elements_obj.elements
            total = len(elements)
            for i, item in enumerate(elements):
                # 注入循环上下文 (用于隐式意图感知)
                self.context.push_loop_context(i, total)
                
                if isinstance(node.target, ast.Name):
                    self.context.define_variable(node.target.id, item)
                
                # 支持过滤条件
                try:
                    if node.filter_condition and not self.is_truthy(self.visit(node.filter_condition)):
                        continue
    
                    try:
                        for stmt in node.body: self.visit(stmt)
                    except BreakException: return IbNone()
                    except ContinueException: break
                finally:
                    self.context.pop_loop_context()
            return IbNone()
            
        return self._with_llm_fallback(node, action)

    def visit_ExprStmt(self, node: ast.ExprStmt):
        def action():
            res = self.visit(node.value)
            # 如果是行为描述行，则立即执行（作为语句时）
            from core.foundation.builtins import IbBehavior
            if isinstance(res, IbBehavior):
                return res._execute()
            return res
        return self._with_llm_fallback(node, action)

    def visit_Retry(self, node: ast.Retry):
        """处理 retry 语句"""
        if node.hint:
            hint_val = self.visit(node.hint)
            # 将 hint 注入到 ai 模块（如果可用）
            try:
                ai_mod = self.service_context.module_manager.import_module("ai", self.context)
                if hasattr(ai_mod, "set_retry_hint"):
                    ai_mod.set_retry_hint(hint_val.to_native())
            except:
                pass # 忽略注入失败
        raise RetryException()

    def _with_llm_fallback(self, node: ast.Stmt, action: Callable):
        """LLM 容错机制的核心封装"""
        while True:
            try:
                return action()
            except Exception as e:
                if isinstance(e, LLMUncertaintyError):
                    if hasattr(node, 'llm_fallback') and node.llm_fallback:
                        try:
                            for stmt in node.llm_fallback:
                                self.visit(stmt)
                            return IbNone()
                        except RetryException:
                            continue
                raise

    def visit_Try(self, node: ast.Try):
        """实现异常处理块"""
        def action():
            try:
                for stmt in node.body: self.visit(stmt)
            except (ReturnException, BreakException, ContinueException, RetryException):
                raise
            except (ThrownException, Exception) as e:
                # 包装 Python 原生异常
                error_obj = e.value if isinstance(e, ThrownException) else self._box_native(str(e))
                
                # 查找匹配的 except 块
                handled = False
                for handler in node.handlers:
                    # TODO: 类型匹配检查 (handler.type)
                    if handler.name:
                        self.context.define_variable(handler.name, error_obj)
                    for stmt in handler.body: self.visit(stmt)
                    handled = True
                    break
                if not handled: raise
            finally:
                if node.finalbody:
                    for stmt in node.finalbody: self.visit(stmt)
            return IbNone()
            
        return self._with_llm_fallback(node, action)

    def visit_Return(self, node: ast.Return):
        val = self.visit(node.value) if node.value else IbNone()
        raise ReturnException(val)

    def is_truthy(self, value: IbObject) -> bool:
        """UTS: 使用 to_bool 协议判断真值"""
        res = value.receive('to_bool', [])
        return res.to_native() != 0

    def _builtin_print(self, *args: IbObject):
        texts = [str(arg.value) if hasattr(arg, 'value') else str(arg) for arg in args]
        msg = " ".join(texts)
        if self.output_callback:
            self.output_callback(msg)
        else:
            print(msg)
        return IbNone()

    def _resolve_type(self, type_node: ast.ASTNode) -> Type:
        """UTS: 在运行时解析类型节点为 Type 对象"""
        if isinstance(type_node, ast.Name):
            target = Bootstrapper.get_class(type_node.id)
            if target: return target
            return Type(type_node.id)  # UTS: Fallback to base Type placeholder
        # 扩展支持复合类型 (如 list[int])
        if isinstance(type_node, ast.Subscript):
            base = self._resolve_type(type_node.value)
            if base.name == "list":
                elt = self._resolve_type(type_node.slice)
                return ListType(elt)
            if base.name == "dict":
                # 简单处理：只取第一个参数
                return DictType(ANY_TYPE, ANY_TYPE)
        return ANY_TYPE

    # --- 保持 Import 逻辑 ---
    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.service_context.module_manager.import_module(alias.name, self.context)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        names = [(alias.name, alias.asname) for alias in node.names]
        self.service_context.module_manager.import_from(node.module, names, self.context)

    def visit_ClassDef(self, node: ast.ClassDef):
        # 动态创建类对象
        new_class = Bootstrapper.create_subclass(node.name, node.parent or "Object")
        
        # 1. 注册方法与字段：从 node.methods/fields 或 node.body 中识别
        all_methods = list(node.methods)
        all_fields = list(node.fields)
        for stmt in node.body:
            if isinstance(stmt, (ast.FunctionDef, ast.LLMFunctionDef)):
                all_methods.append(stmt)
            elif isinstance(stmt, ast.Assign):
                all_fields.append(stmt)
        
        for m in all_methods:
            if isinstance(m, ast.LLMFunctionDef):
                from core.foundation.kernel import IbLLMFunction
                new_class.register_method(m.name, IbLLMFunction(m, self.service_context.llm_executor, self))
            else:
                new_class.register_method(m.name, IbUserFunction(m, self))
        
        # 2. 收集默认字段值
        for f in all_fields:
            if isinstance(f, ast.Assign):
                val = self.visit(f.value) if f.value else IbNone()
                for target in f.targets:
                    if isinstance(target, ast.Name):
                        new_class.default_fields[target.id] = val
            
        self.context.define_variable(node.name, new_class)

    def visit_Raise(self, node: ast.Raise):
        """抛出异常"""
        exc_val = self.visit(node.exc) if node.exc else IbNone()
        raise ThrownException(exc_val)

    def visit_BehaviorExpr(self, node: ast.BehaviorExpr):
        """
        处理行为描述行 @~...~
        如果它在赋值语句的右侧，或者作为参数传递，它应该被 Lambda 化（延迟执行）。
        """
        from core.foundation.builtins import IbBehavior
        # 获取当前意图栈的快照，用于后续 Lambda 调用时的闭包
        captured_intents = list(self.context.intent_stack)
        
        # 获取当前预期的类型
        expected_type = None
        if self.service_context.llm_executor._expected_type_stack:
            expected_type = self.service_context.llm_executor._expected_type_stack[-1]
            
        return IbBehavior(node, self, captured_intents, expected_type=expected_type)

    def visit_IntentStmt(self, node: ast.IntentStmt):
        """处理意图块"""
        # 如果是动态意图（带有 segments），先评估内容
        intent = node.intent
        if hasattr(intent, 'segments') and intent.segments:
            content = self.service_context.llm_executor._evaluate_segments(intent.segments, self.context)
            # 这里的 intent 是 AST 节点，为了不破坏 AST，我们创建一个临时的 IntentInfo 对象
            from core.types.parser_types import IntentInfo
            intent = IntentInfo(content=content, mode=intent.mode)
            
        self.context.push_intent(intent)
        try:
            for stmt in node.body:
                self.visit(stmt)
        finally:
            self.context.pop_intent()
        from core.foundation.builtins import IbNone
        return IbNone()

    def visit_Pass(self, node: ast.Pass): pass
    def visit_Break(self, node: ast.Break): raise BreakException()
    def visit_Continue(self, node: ast.Continue): raise ContinueException()
