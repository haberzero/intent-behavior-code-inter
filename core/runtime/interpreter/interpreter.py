from typing import Any, Dict, List, Optional, Callable, Union
from core.domain import ast as ast
from core.domain.exceptions import (
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
        self.host_interface = host_interface or HostInterface()
        self.debugger = debugger or core_debugger
        
        # 1. 核心解耦：处理平铺化池结构
        self.artifact_dict: Dict[str, Any] = {}
        if artifact:
            # 如果是对象，则转换为扁平化池字典
            if hasattr(artifact, 'to_dict'):
                self.artifact_dict = artifact.to_dict()
            else:
                self.artifact_dict = artifact
        
        # 加载全局池 (Pools)
        pools = self.artifact_dict.get("pools", {})
        self.node_pool: Dict[str, Dict[str, Any]] = pools.get("nodes", {})
        self.symbol_pool: Dict[str, Dict[str, Any]] = pools.get("symbols", {})
        self.scope_pool: Dict[str, Dict[str, Any]] = pools.get("scopes", {})
        self.type_pool: Dict[str, Dict[str, Any]] = pools.get("types", {})
        
        # 2. 初始化基础组件
        runtime_context = RuntimeContextImpl()
        interop = InterOpImpl(host_interface=self.host_interface)
        
        # 权限管理
        permission_manager = PermissionManagerImpl(root_dir)
        
        # 3. 初始化 ModuleManager
        module_manager = ModuleManagerImpl(
            interop, 
            artifact=self.artifact_dict, # 传入字典
            interpreter=None,
            root_dir=root_dir
        )
        
        # 4. 创建 ServiceContext
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
        
        # 5. 完成子组件的注入
        llm_executor.service_context = self.service_context
        module_manager.set_interpreter(self)
        
        self._current_context = runtime_context
        self._setup_context(self._current_context)

        # 运行限制
        self.max_instructions = max_instructions
        self.instruction_count = 0
        self.max_call_stack = max_call_stack
        self.call_stack_depth = 0
        self.current_module_name: Optional[str] = None

    def get_side_table(self, table_name: str, node_uid: str) -> Any:
        """获取当前模块下的侧表信息"""
        if not self.current_module_name:
            return None
        module_data = self.artifact_dict.get("modules", {}).get(self.current_module_name, {})
        return module_data.get("side_tables", {}).get(table_name, {}).get(node_uid)

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
        if self.artifact_dict and "global_symbols" in self.artifact_dict:
            for name, val in self.artifact_dict["global_symbols"].items():
                if name not in global_symbols:
                    # 如果是运行时对象（非静态符号），则注入
                    context.define_variable(name, val)

    @property
    def context(self) -> RuntimeContext:
        return self._current_context

    @context.setter
    def context(self, value: RuntimeContext):
        self._current_context = value

    def interpret(self, module_uid: str) -> IbObject:
        """从模块 UID 开始执行"""
        return self.execute_module(module_uid)

    def execute_module(self, module_uid: str, module_name: str = "main", scope: Optional[Scope] = None) -> IbObject:
        self.debugger.trace(CoreModule.INTERPRETER, DebugLevel.BASIC, f"Starting execution of module {module_name} ({module_uid})...")
        
        old_module = self.current_module_name
        self.current_module_name = module_name
        
        module_data = self.node_pool.get(module_uid)
        if not module_data:
            raise InterpreterError(f"Module UID {module_uid} not found.")

        old_context = self._current_context
        if scope:
             # 创建新 Context 并绑定 Scope
             new_ctx = RuntimeContextImpl(initial_scope=scope)
             self._current_context = new_ctx
             self._setup_context(self._current_context)

        self.instruction_count = 0
        result = IbNone()
        try:
            # 模块主体是语句 UID 列表
            body = module_data.get("body", [])
            for stmt_uid in body:
                result = self.visit(stmt_uid)
            self.debugger.trace(CoreModule.INTERPRETER, DebugLevel.BASIC, "Execution complete.")
            return result
        except InterpreterError as e:
            # TODO: 适配新的错误报告，使用 UID 关联源码
            raise
        except (ReturnException, BreakException, ContinueException):
            raise InterpreterError("Control flow statement used outside of function or loop.", error_code=RUN_GENERIC_ERROR)
        except Exception as e:
            msg = f"Runtime error: {str(e)}"
            if self.service_context.issue_tracker:
                from core.domain.diagnostics import Severity
                self.service_context.issue_tracker.report(Severity.FATAL, RUN_GENERIC_ERROR, msg)
            raise InterpreterError(msg, error_code=RUN_GENERIC_ERROR)
        finally:
            self._current_context = old_context
            self.current_module_name = old_module

    def visit(self, node_uid: Union[str, Any]) -> IbObject:
        """核心 Pool-Walking 分发方法"""
        if node_uid is None:
            return IbNone()
        
        # 兼容性处理：如果传入的是对象（可能来自某些未重构的组件），尝试获取其 UID
        if not isinstance(node_uid, str):
            if hasattr(node_uid, 'uid'):
                node_uid = node_uid.uid
            else:
                return IbNone()

        node_data = self.node_pool.get(node_uid)
        if not node_data:
            # 可能是基础类型或已解箱对象
            if isinstance(node_uid, (int, float, str, bool)):
                return Bootstrapper.box(node_uid)
            return IbNone()

        self.instruction_count += 1
        
        if self.instruction_count > self.max_instructions:
            raise InterpreterError("Execution limit exceeded", node_uid, error_code=RUN_LIMIT_EXCEEDED)

        if self.call_stack_depth >= self.max_call_stack:
             raise InterpreterError("Recursion depth exceeded", node_uid, error_code=RUN_LIMIT_EXCEEDED)
        
        self.call_stack_depth += 1
        try:
            method_name = f'visit_{node_data["_type"]}'
            visitor = getattr(self, method_name, self.generic_visit)
            return visitor(node_uid, node_data)
        except (ReturnException, BreakException, ContinueException, RetryException, ThrownException):
            raise
        except InterpreterError:
            raise
        except Exception as e:
            raise InterpreterError(f"{type(e).__name__}: {str(e)}", node_uid, error_code=RUN_GENERIC_ERROR) from e
        finally:
            self.call_stack_depth -= 1

    def generic_visit(self, node_uid: str, node_data: Dict[str, Any]):
        raise InterpreterError(f"No visit method implemented for {node_data['_type']}", node_uid, error_code=RUN_GENERIC_ERROR)

    # --- 访问方法实现 ---

    def visit_AnnotatedStmt(self, node_uid: str, node_data: Dict[str, Any]):
        """意图语句：intent '...' { ... }"""
        intent_uid = node_data.get("intent")
        stmt_uid = node_data.get("stmt")
        
        # 意图作用域管理
        from .llm_executor import intent_scoped
        def action():
            return self.visit(stmt_uid)
            
        return intent_scoped(self.service_context, intent_uid)(action)

    def visit_AnnotatedExpr(self, node_uid: str, node_data: Dict[str, Any]) -> IbObject:
        """意图表达式：intent '...' expr"""
        intent_uid = node_data.get("intent")
        expr_uid = node_data.get("expr")
        
        from .llm_executor import intent_scoped
        def action():
            return self.visit(expr_uid)
            
        return intent_scoped(self.service_context, intent_uid)(action)

    def visit_BehaviorExpr(self, node_uid: str, node_data: Dict[str, Any]) -> IbObject:
        """行为描述行：█ ... █"""
        is_deferred = self.get_side_table("node_is_deferred", node_uid)
        self.debugger.trace(CoreModule.INTERPRETER, DebugLevel.DETAIL, f"BehaviorExpr {node_uid} is_deferred={is_deferred}")
        
        if is_deferred:
            # 返回延迟执行的行为对象 (Lambda)
            from core.foundation.builtins import IbBehavior
            # 捕获当前的意图栈
            captured_intents = list(self.context.intent_stack)
            # 获取推导出的预期类型 (如果有)
            expected_type = self.get_side_table("node_to_type", node_uid)
            return IbBehavior(node_uid, self, captured_intents, expected_type=expected_type)
        
        # 立即执行
        return self.service_context.llm_executor.execute_behavior_expression(node_uid, self.context)

    def visit_Module(self, node_uid: str, node_data: Dict[str, Any]):
        result = IbNone()
        for stmt_uid in node_data.get("body", []):
            result = self.visit(stmt_uid)
        return result

    def visit_Constant(self, node_uid: str, node_data: Dict[str, Any]) -> IbObject:
        """UTS: 统一常量装箱"""
        return Bootstrapper.box(node_data.get("value"))

    def visit_BinOp(self, node_uid: str, node_data: Dict[str, Any]) -> IbObject:
        left = self.visit(node_data.get("left"))
        right = self.visit(node_data.get("right"))
        method = OP_MAPPING.get(node_data.get("op"))
        if not method: raise InterpreterError(f"Unsupported op: {node_data.get('op')}", node_uid)
        return left.receive(method, [right])

    def visit_Compare(self, node_uid: str, node_data: Dict[str, Any]) -> IbObject:
        """处理比较运算 -> 消息发送"""
        left = self.visit(node_data.get("left"))
        ops = node_data.get("ops", [])
        comparators = node_data.get("comparators", [])
        if not ops: return left
        
        # 简化处理：只取第一个比较操作符
        op = ops[0]
        right = self.visit(comparators[0])
        
        method = OP_MAPPING.get(op)
        if not method: raise InterpreterError(f"Unsupported comparison: {op}", node_uid)
        return left.receive(method, [right])

    def visit_ListExpr(self, node_uid: str, node_data: Dict[str, Any]) -> IbObject:
        """列表字面量 -> 统一装箱"""
        elts = [self.visit(e) for e in node_data.get("elts", [])]
        return Bootstrapper.box(elts)

    def visit_Dict(self, node_uid: str, node_data: Dict[str, Any]) -> IbObject:
        """字典字面量 -> 统一装箱"""
        data = {}
        keys = node_data.get("keys", [])
        values = node_data.get("values", [])
        for k_uid, v_uid in zip(keys, values):
            key_obj = self.visit(k_uid) if k_uid else IbNone()
            val_obj = self.visit(v_uid)
            native_key = key_obj.to_native() if hasattr(key_obj, 'to_native') else key_obj
            data[native_key] = val_obj
        return Bootstrapper.box(data)

    def visit_Subscript(self, node_uid: str, node_data: Dict[str, Any]) -> IbObject:
        """下标访问 -> __getitem__"""
        value = self.visit(node_data.get("value"))
        slice_obj = self.visit(node_data.get("slice"))
        return value.receive('__getitem__', [slice_obj])

    def visit_UnaryOp(self, node_uid: str, node_data: Dict[str, Any]) -> IbObject:
        """一元运算 -> 消息发送"""
        operand = self.visit(node_data.get("operand"))
        # 注意：UNARY_OP_MAPPING 尚未定义，补全它
        UNARY_OP_MAPPING = {'UAdd': '__pos__', 'USub': '__neg__', 'Not': '__not__', 'Invert': '__invert__'}
        method = UNARY_OP_MAPPING.get(node_data.get("op"))
        if not method: raise InterpreterError(f"Unsupported unary op: {node_data.get('op')}", node_uid)
        return operand.receive(method, [])

    def visit_Name(self, node_uid: str, node_data: Dict[str, Any]) -> IbObject:
        """变量读取：优先通过 Symbol UID 查找"""
        sym_uid = self.get_side_table("node_to_symbol", node_uid)
        if sym_uid:
            try:
                return self.context.get_variable_by_uid(sym_uid)
            except InterpreterError:
                # 可能是尚未初始化的局部变量
                pass
        
        # 备选方案：按名称查找（针对内置函数、插件或动态注入）
        name = node_data.get("id")
        val = self.context.get_variable(name)
        if not isinstance(val, IbObject):
            return Bootstrapper.box(val)
        return val

    def visit_Assign(self, node_uid: str, node_data: Dict[str, Any]):
        """赋值语句实现"""
        self.debugger.trace(CoreModule.INTERPRETER, DebugLevel.DETAIL, f"Executing assignment {node_uid}")
        
        value_uid = node_data.get("value")
        value = self.visit(value_uid)
        
        # 处理多重赋值目标 (var a, b = 1)
        for target_uid in node_data.get("targets", []):
            target_data = self.node_pool.get(target_uid)
            if not target_data: continue
            
            # 1. 普通变量赋值 (Name)
            if target_data["_type"] == "Name":
                sym_uid = self.get_side_table("node_to_symbol", target_uid)
                name = target_data.get("id")
                if sym_uid:
                    # 如果有 Symbol UID，则根据其是否存在于当前作用域决定 define 还是 set
                    if self.context.get_symbol_by_uid(sym_uid):
                        self.context.set_variable_by_uid(sym_uid, value)
                    else:
                        self.context.define_variable(name, value, uid=sym_uid)
                else:
                    self.context.set_variable(name, value)
            
            # 2. 类型标注表达式 (TypeAnnotatedExpr)
            elif target_data["_type"] == "TypeAnnotatedExpr":
                inner_target_uid = target_data.get("target")
                inner_target_data = self.node_pool.get(inner_target_uid)
                if inner_target_data and inner_target_data["_type"] == "Name":
                    sym_uid = self.get_side_table("node_to_symbol", inner_target_uid)
                    name = inner_target_data.get("id")
                    # 总是定义新变量
                    self.context.define_variable(name, value, uid=sym_uid)
            
            # 3. 属性赋值 (Attribute)
            elif target_data["_type"] == "Attribute":
                obj = self.visit(target_data.get("value"))
                attr = target_data.get("attr")
                obj.receive('__setattr__', [Bootstrapper.box(attr), value])
                
        return IbNone()

    def visit_FunctionDef(self, node_uid: str, node_data: Dict[str, Any]):
        """定义用户函数"""
        from core.foundation.kernel import IbUserFunction
        func = IbUserFunction(node_uid, self)
        name = node_data.get("name")
        sym_uid = self.get_side_table("node_to_symbol", node_uid)
        self.context.define_variable(name, func, uid=sym_uid)
        return IbNone()

    def visit_LLMFunctionDef(self, node_uid: str, node_data: Dict[str, Any]):
        """定义 LLM 函数"""
        from core.foundation.kernel import IbLLMFunction
        func = IbLLMFunction(node_uid, self.service_context.llm_executor, self)
        name = node_data.get("name")
        sym_uid = self.get_side_table("node_to_symbol", node_uid)
        self.context.define_variable(name, func, uid=sym_uid)
        return IbNone()

    def visit_AugAssign(self, node_uid: str, node_data: Dict[str, Any]):
        """增量赋值 a += 1"""
        target_uid = node_data.get("target")
        value_uid = node_data.get("value")
        op = node_data.get("op")
        
        old_val = self.visit(target_uid)
        delta = self.visit(value_uid)
        
        method = OP_MAPPING.get(op)
        if not method: raise InterpreterError(f"Unsupported aug op: {op}", node_uid)
        
        new_val = old_val.receive(method, [delta])
        
        # 写回目标
        target_data = self.node_pool.get(target_uid)
        if target_data and target_data["_type"] == "Name":
            sym_uid = self.get_side_table("node_to_symbol", target_uid)
            self.context.set_variable_by_uid(sym_uid, new_val)
        
        return IbNone()

    def visit_BoolOp(self, node_uid: str, node_data: Dict[str, Any]) -> IbObject:
        """逻辑运算 (and/or)"""
        is_or = node_data.get("op") == 'or'
        last_val = IbNone()
        for val_uid in node_data.get("values", []):
            val = self.visit(val_uid)
            last_val = val
            if is_or and self.is_truthy(val): return val
            if not is_or and not self.is_truthy(val): return val
        return last_val

    def visit_IfExp(self, node_uid: str, node_data: Dict[str, Any]) -> IbObject:
        """三元表达式"""
        if self.is_truthy(self.visit(node_data.get("test"))):
            return self.visit(node_data.get("body"))
        return self.visit(node_data.get("orelse"))

    def visit_Call(self, node_uid: str, node_data: Dict[str, Any]) -> IbObject:
        """函数调用"""
        func = self.visit(node_data.get("func"))
        args = [self.visit(arg_uid) for arg_uid in node_data.get("args", [])]
        return func.call(IbNone(), args)

    def visit_Attribute(self, node_uid: str, node_data: Dict[str, Any]) -> IbObject:
        """读取属性 -> __getattr__"""
        value = self.visit(node_data.get("value"))
        attr = node_data.get("attr")
        return value.receive('__getattr__', [Bootstrapper.box(attr)])

    def visit_If(self, node_uid: str, node_data: Dict[str, Any]):
        def action():
            condition = self.visit(node_data.get("test"))
            if self.is_truthy(condition):
                for stmt_uid in node_data.get("body", []):
                    self.visit(stmt_uid)
            else:
                for stmt_uid in node_data.get("orelse", []):
                    self.visit(stmt_uid)
            return IbNone()
            
        return self._with_llm_fallback(node_uid, node_data, action)

    def visit_While(self, node_uid: str, node_data: Dict[str, Any]):
        def action():
            while self.is_truthy(self.visit(node_data.get("test"))):
                try:
                    for stmt_uid in node_data.get("body", []):
                        self.visit(stmt_uid)
                except BreakException: break
                except ContinueException: continue
            return IbNone()
            
        return self._with_llm_fallback(node_uid, node_data, action)

    def visit_For(self, node_uid: str, node_data: Dict[str, Any]):
        def action():
            target_uid = node_data.get("target")
            iter_uid = node_data.get("iter")
            body = node_data.get("body", [])
            
            # 标准 Foreach 循环
            iterable_obj = self.visit(iter_uid)
            
            # UTS: 使用消息传递获取迭代列表 (to_list 协议)
            elements_obj = iterable_obj.receive('to_list', [])
            from core.foundation.builtins import IbList
            if not isinstance(elements_obj, IbList):
                raise InterpreterError(f"Object is not iterable", node_uid)
            
            elements = elements_obj.elements
            total = len(elements)
            for i, item in enumerate(elements):
                # 注入循环上下文
                self.context.push_loop_context(i, total)
                
                # 绑定循环变量
                target_data = self.node_pool.get(target_uid)
                if target_data and target_data["_type"] == "Name":
                    name = target_data.get("id")
                    sym_uid = self.get_side_table("node_to_symbol", target_uid)
                    self.context.define_variable(name, item, uid=sym_uid)
                
                try:
                    for stmt_uid in body:
                        self.visit(stmt_uid)
                except BreakException: 
                    self.context.pop_loop_context()
                    return IbNone()
                except ContinueException: 
                    self.context.pop_loop_context()
                    continue
                finally:
                    self.context.pop_loop_context()
            return IbNone()
            
        return self._with_llm_fallback(node_uid, node_data, action)

    def visit_Return(self, node_uid: str, node_data: Dict[str, Any]):
        value_uid = node_data.get("value")
        value = self.visit(value_uid) if value_uid else IbNone()
        raise ReturnException(value)

    def visit_Break(self, node_uid: str, node_data: Dict[str, Any]):
        raise BreakException()

    def visit_Continue(self, node_uid: str, node_data: Dict[str, Any]):
        raise ContinueException()

    def visit_ExprStmt(self, node_uid: str, node_data: Dict[str, Any]):
        """表达式语句"""
        res = self.visit(node_data.get("value"))
        # 如果是行为描述行，则立即执行（作为语句时）
        from core.foundation.builtins import IbBehavior
        if isinstance(res, IbBehavior):
            return res.receive('__call__', [])
        return res

    def visit_Retry(self, node_uid: str, node_data: Dict[str, Any]):
        """处理 retry 语句"""
        hint_uid = node_data.get("hint")
        if hint_uid:
            hint_val = self.visit(hint_uid)
            # 将 hint 注入到 ai 模块（如果可用）
            try:
                ai_mod = self.service_context.module_manager.import_module("ai", self.context)
                if hasattr(ai_mod, "set_retry_hint"):
                    ai_mod.set_retry_hint(hint_val.to_native())
            except:
                pass 
        raise RetryException()

    def _with_llm_fallback(self, node_uid: str, node_data: Dict[str, Any], action: Callable):
        """LLM 容错机制的核心封装"""
        while True:
            try:
                return action()
            except LLMUncertaintyError:
                fallback_body = node_data.get("llm_fallback", [])
                if fallback_body:
                    try:
                        for stmt_uid in fallback_body:
                            self.visit(stmt_uid)
                        return IbNone()
                    except RetryException:
                        continue
                raise

    def visit_Try(self, node_uid: str, node_data: Dict[str, Any]):
        """实现异常处理块"""
        def action():
            try:
                for stmt_uid in node_data.get("body", []):
                    self.visit(stmt_uid)
            except (ReturnException, BreakException, ContinueException, RetryException):
                raise
            except (ThrownException, Exception) as e:
                # 包装 Python 原生异常
                error_obj = e.value if isinstance(e, ThrownException) else Bootstrapper.box(str(e))
                
                # 查找匹配的 except 块
                handled = False
                for handler_data in node_data.get("handlers", []):
                    # TODO: 类型匹配检查
                    name = handler_data.get("name")
                    if name:
                        self.context.define_variable(name, error_obj)
                    for stmt_uid in handler_data.get("body", []):
                        self.visit(stmt_uid)
                    handled = True
                    break
                if not handled: raise
            finally:
                for stmt_uid in node_data.get("finalbody", []):
                    self.visit(stmt_uid)
            return IbNone()
            
        return self._with_llm_fallback(node_uid, node_data, action)

    def visit_Import(self, node_uid: str, node_data: Dict[str, Any]):
        for alias_data in node_data.get("names", []):
            self.service_context.module_manager.import_module(alias_data.get("name"), self.context)
        return IbNone()

    def visit_ImportFrom(self, node_uid: str, node_data: Dict[str, Any]):
        names = [(a.get("name"), a.get("asname")) for a in node_data.get("names", [])]
        self.service_context.module_manager.import_from(node_data.get("module"), names, self.context)
        return IbNone()

    def visit_ClassDef(self, node_uid: str, node_data: Dict[str, Any]):
        """动态创建类对象"""
        name = node_data.get("name")
        parent_name = node_data.get("parent") or "Object"
        new_class = Bootstrapper.create_subclass(name, parent_name)
        
        # 1. 注册方法与字段
        body = node_data.get("body", [])
        for stmt_uid in body:
            stmt_data = self.node_pool.get(stmt_uid)
            if not stmt_data: continue
            
            if stmt_data["_type"] == "FunctionDef":
                new_class.register_method(stmt_data["name"], IbUserFunction(stmt_uid, self))
            elif stmt_data["_type"] == "LLMFunctionDef":
                new_class.register_method(stmt_data["name"], IbLLMFunction(stmt_uid, self.service_context.llm_executor, self))
            elif stmt_data["_type"] == "Assign":
                val = self.visit(stmt_data.get("value")) if stmt_data.get("value") else IbNone()
                for target_uid in stmt_data.get("targets", []):
                    target_data = self.node_pool.get(target_uid)
                    if target_data and target_data["_type"] == "Name":
                        new_class.default_fields[target_data.get("id")] = val
        
        # 绑定到当前作用域
        sym_uid = self.get_side_table("node_to_symbol", node_uid)
        self.context.define_variable(name, new_class, uid=sym_uid)
        return IbNone()

    def visit_Raise(self, node_uid: str, node_data: Dict[str, Any]):
        """抛出异常"""
        exc_uid = node_data.get("exc")
        exc_val = self.visit(exc_uid) if exc_uid else IbNone()
        raise ThrownException(exc_val)

    def visit_IntentStmt(self, node_uid: str, node_data: Dict[str, Any]):
        """处理意图块"""
        intent_uid = node_data.get("intent")
        intent_data = self.node_pool.get(intent_uid)
        
        from types import SimpleNamespace
        intent = SimpleNamespace(
            content=intent_data.get('content', '') if intent_data else '',
            mode=intent_data.get('mode', 'append') if intent_data else 'append',
            segments=intent_data.get('segments', []) if intent_data else []
        )
            
        self.context.push_intent(intent)
        try:
            for stmt_uid in node_data.get("body", []):
                self.visit(stmt_uid)
        finally:
            self.context.pop_intent()
        return IbNone()

    def visit_Pass(self, node_uid: str, node_data: Dict[str, Any]):
        return IbNone()

    def is_truthy(self, value: IbObject) -> bool:
        """UTS: 使用 to_bool 协议判断真值"""
        res = value.receive('to_bool', [])
        return res.to_native() != 0

    def _builtin_print(self, *args: IbObject):
        texts = [str(arg.to_native()) if hasattr(arg, 'to_native') else str(arg) for arg in args]
        msg = " ".join(texts)
        if self.output_callback:
            self.output_callback(msg)
        else:
            print(msg)
        return IbNone()
