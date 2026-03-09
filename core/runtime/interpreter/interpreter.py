import re
import json
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Callable, Union
from core.domain import ast as ast
from core.domain.issue import (
    InterpreterError, ReturnException, BreakException, ContinueException, ThrownException,
    LLMUncertaintyError, RetryException, Severity
)
from core.domain.issue_atomic import Location
from core.foundation.diagnostics.codes import (
    RUN_GENERIC_ERROR, RUN_TYPE_MISMATCH, RUN_UNDEFINED_VARIABLE,
    RUN_LIMIT_EXCEEDED, RUN_CALL_ERROR
)
from core.runtime.interfaces import (
    Interpreter as InterpreterInterface, 
    RuntimeContext, LLMExecutor, InterOp, ModuleManager, ServiceContext, IssueTracker,
    PermissionManager, Scope
)
from .runtime_context import RuntimeContextImpl
from .llm_executor import LLMExecutorImpl
from .interop import InterOpImpl
from .module_manager import ModuleManagerImpl
from .permissions import PermissionManager as PermissionManagerImpl
from core.runtime.objects.kernel import IbObject, IbClass, IbUserFunction, IbFunction, IbNativeFunction, IbLLMFunction
from core.domain.types.descriptors import TypeDescriptor as Type, ListMetadata as ListType, DictMetadata as DictType, ANY_DESCRIPTOR as ANY_TYPE
from core.runtime.objects.builtins import IbInteger, IbString, IbList, IbNone, IbBehavior
from core.runtime.objects.initialization import initialize_builtin_classes
from core.foundation.registry import Registry
from core.foundation.host_interface import HostInterface
from core.foundation.interfaces import IStackInspector
from core.foundation.diagnostics.core_debugger import CoreModule, DebugLevel, core_debugger
from .llm_executor import intent_scoped
from .intrinsics import IntrinsicManager



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
    def runtime_context(self) -> RuntimeContext: 
        # [FIX] 动态获取解释器当前活跃的 Context，解决跨模块加载时的作用域滞后问题
        return self._interpreter.context
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
                 input_callback: Optional[Callable[[str], str]] = None, 
                 max_instructions: int = 10000, 
                 max_call_stack: int = 100,
                 artifact: Optional[Any] = None,
                 host_interface: Optional[HostInterface] = None,
                 debugger: Optional[Any] = None,
                 root_dir: str = ".",
                 strict_mode: bool = False):
        
        # 0. 启动内核引导
        initialize_builtin_classes()
        # [NEW] 加载内置函数插件 (Intrinsics)
        IntrinsicManager.load_defaults(self)
        
        self.output_callback = output_callback
        self.input_callback = input_callback
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
        self.strict_mode = strict_mode

    def get_side_table(self, table_name: str, node_uid: str) -> Any:
        """获取当前模块下的侧表信息"""
        if not self.current_module_name:
            return None
        
        module_data = self.artifact_dict.get("modules", {}).get(self.current_module_name, {})
        if not isinstance(module_data, dict):
            # print(f"DEBUG: module_data for {self.current_module_name} is NOT a dict! it is {type(module_data)}")
            return None
            
        table = module_data.get("side_tables", {}).get(table_name, {})
        return table.get(node_uid)

    def save_state(self) -> Dict[str, Any]:
        """导出当前解释器的运行状态快照 (用于调试或热替换)"""
        return {
            "artifact": self.artifact_dict,
            "instruction_count": self.instruction_count,
            "call_stack_depth": self.call_stack_depth,
            "current_module_name": self.current_module_name,
            # 注意：Context 状态通常由外部单独管理，此处仅记录引用
        }

    def restore_state(self, state: Dict[str, Any]):
        """从快照恢复解释器运行状态"""
        self.artifact_dict = state["artifact"]
        # 重新绑定池
        pools = self.artifact_dict.get("pools", {})
        self.node_pool = pools.get("nodes", {})
        self.symbol_pool = pools.get("symbols", {})
        self.scope_pool = pools.get("scopes", {})
        self.type_pool = pools.get("types", {})
        
        self.instruction_count = state["instruction_count"]
        self.call_stack_depth = state["call_stack_depth"]
        self.current_module_name = state["current_module_name"]

    def hot_reload_pools(self, artifact_dict: Dict[str, Any]):
        """热替换底层数据池，不改变当前的变量现场"""
        self.artifact_dict = artifact_dict
        
        pools = artifact_dict.get("pools", {})
        if not isinstance(pools, dict):
             raise ValueError(f"Artifact pools must be a dict, got {type(pools)}")
             
        self.node_pool = pools.get("nodes", {})
        if not isinstance(self.node_pool, dict):
             raise ValueError(f"Node pool must be a dict, got {type(self.node_pool)}")
        self.symbol_pool = pools.get("symbols", {})
        self.scope_pool = pools.get("scopes", {})
        self.type_pool = pools.get("types", {})
        self.debugger.trace(CoreModule.INTERPRETER, DebugLevel.BASIC, "Interpreter pools hot-reloaded.")

    def _setup_context(self, context: RuntimeContext):
        """为 Context 注入基础内置变量"""
        # 使用私有属性访问以仅检查当前作用域，避免与后续 bootstrap 冲突
        global_symbols = context.global_scope.get_all_symbols()
        defined_names = set(global_symbols.keys())
        
        # 注入内置全局函数 (Prelude)
        def define_builtin(name, val):
            if name not in defined_names:
                context.define_variable(name, val, is_const=True)
                defined_names.add(name)

        # [NEW] 从 IntrinsicManager 注入插件化的内置函数
        for name, func in IntrinsicManager.get_all().items():
            define_builtin(name, func)
        
        # 注入内置类 (int, str, float, list, dict 等)
        # 注意：上面的 int, str 会覆盖这里的类符号，这在作为函数使用时是合理的。
        # 如果需要作为类型使用，目前编译器会通过 side_table 直接映射到 IbClass。
        for name, ib_class in Registry.get_all_classes().items():
            define_builtin(name, ib_class)

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
        
        # DEBUG
        # print(f"DEBUG: execute_module {module_name} uid={module_uid}")
        # if not isinstance(self.node_pool, dict):
        #     print(f"DEBUG: node_pool is NOT a dict! it is {type(self.node_pool)}")
        
        old_module = self.current_module_name
        self.current_module_name = module_name
        
        module_data = self.node_pool.get(module_uid)
        if not module_data:
            # print(f"DEBUG: module_data not found for {module_uid} in pool keys: {list(self.node_pool.keys())[:10]}")
            raise self._report_error(f"Module UID {module_uid} not found.")
        
        if not isinstance(module_data, dict):
            # print(f"DEBUG: module_data is NOT a dict! it is {type(module_data)} -> {module_data}")
            raise self._report_error(f"Module data for {module_uid} is not a dict: {type(module_data)} -> {module_data}")

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
        except InterpreterError:
            raise
        except (ReturnException, BreakException, ContinueException):
            raise self._report_error("Control flow statement used outside of function or loop.", error_code=RUN_GENERIC_ERROR)
        # except Exception as e:
        #    msg = f"Runtime error: {str(e)}"
        #    if self.service_context.issue_tracker:
        #        from core.domain.issue import Severity
        #        self.service_context.issue_tracker.report(Severity.FATAL, RUN_GENERIC_ERROR, msg)
        #    raise self._report_error(msg, error_code=RUN_GENERIC_ERROR)
        finally:
            self._current_context = old_context
            self.current_module_name = old_module

    def _report_error(self, message: str, node_uid: Optional[str] = None, error_code: Optional[str] = None) -> InterpreterError:
        """从 side_tables 中恢复位置信息并构造 InterpreterError"""
        loc_data = self.get_side_table("node_to_loc", node_uid) if node_uid else None
        
        loc = None
        if loc_data:
            loc = Location(
                file_path=loc_data.get("file_path"),
                line=loc_data.get("line", 0),
                column=loc_data.get("column", 0),
                end_line=loc_data.get("end_line"),
                end_column=loc_data.get("end_column")
            )
        
        err = InterpreterError(message, error_code=error_code)
        err.location = loc
        return err

    def visit(self, node_uid: Union[str, Any]) -> IbObject:
        """核心 Pool-Walking 分发方法"""
        if node_uid is None:
            return IbNone()
        
        # 如果不是字符串，则可能是基础类型（如 int, bool）或已解箱对象
        if not isinstance(node_uid, str):
            if hasattr(node_uid, 'uid'):
                node_uid = node_uid.uid
            else:
                # 基础类型直接装箱
                if isinstance(node_uid, (int, float, bool)):
                    return Registry.box(node_uid)
                return IbNone()

        # [DEBUG] 检查 node_uid 是否在 pool 中
        if node_uid not in self.node_pool:
            # 如果不在 pool 中，可能是字符串字面量
            return Registry.box(node_uid)

        node_data = self.node_pool.get(node_uid)
        if not isinstance(node_data, dict):
             # 这说明 pool 里存的不是 node data 字典，而是别的东西（比如另一个 UID 字符串）
             raise self._report_error(f"Pool corruption: node_pool[{node_uid}] is {type(node_data)}: {node_data}", node_uid)
        if not node_data:
            # 可能是基础类型或已解箱对象
            if isinstance(node_uid, (int, float, str, bool)):
                return Registry.box(node_uid)
            return IbNone()

        self.instruction_count += 1
        
        if self.instruction_count > self.max_instructions:
            raise self._report_error("Execution limit exceeded", node_uid, error_code=RUN_LIMIT_EXCEEDED)

        if self.call_stack_depth >= self.max_call_stack:
             raise self._report_error("Recursion depth exceeded", node_uid, error_code=RUN_LIMIT_EXCEEDED)
        
        self.call_stack_depth += 1
        try:
            if not isinstance(node_data, dict):
                raise TypeError(f"node_data for {node_uid} is {type(node_data)}: {node_data}")
            method_name = f'visit_{node_data["_type"]}'
            visitor = getattr(self, method_name, self.generic_visit)
            return visitor(node_uid, node_data)
        except (ReturnException, BreakException, ContinueException, RetryException, ThrownException):
            raise
        except InterpreterError as e:
            # 如果异常还没有位置信息，则尝试补全
            if not e.location:
                loc_data = self.get_side_table("node_to_loc", node_uid)
                if loc_data:
                    from core.domain.issue_atomic import Location
                    e.location = Location(
                        file_path=loc_data.get("file_path"),
                        line=loc_data.get("line", 0),
                        column=loc_data.get("column", 0),
                        end_line=loc_data.get("end_line"),
                        end_column=loc_data.get("end_column")
                    )
            raise
        except Exception as e:
            raise self._report_error(f"{type(e).__name__}: {str(e)}", node_uid, error_code=RUN_GENERIC_ERROR) from e
        finally:
            self.call_stack_depth -= 1

    def generic_visit(self, node_uid: str, node_data: Dict[str, Any]):
        raise self._report_error(f"No visit method implemented for {node_data['_type']}", node_uid, error_code=RUN_GENERIC_ERROR)

    # --- 访问方法实现 ---

    def visit_IbAnnotatedStmt(self, node_uid: str, node_data: Dict[str, Any]):
        """意图语句：intent '...' { ... }"""
        intent_uid = node_data.get("intent")
        stmt_uid = node_data.get("stmt")
        
        # 意图作用域管理
        def action():
            return self.visit(stmt_uid)
            
        return intent_scoped(self.service_context, intent_uid)(action)

    def visit_IbAnnotatedExpr(self, node_uid: str, node_data: Dict[str, Any]) -> IbObject:
        """意图表达式：intent '...' expr"""
        intent_uid = node_data.get("intent")
        expr_uid = node_data.get("expr")
        
        def action():
            return self.visit(expr_uid)
            
        return intent_scoped(self.service_context, intent_uid)(action)

    def visit_IbBehaviorExpr(self, node_uid: str, node_data: Dict[str, Any]) -> IbObject:
        """行为描述行：█ ... █"""
        is_deferred = self.get_side_table("node_is_deferred", node_uid)
        self.debugger.trace(CoreModule.INTERPRETER, DebugLevel.DETAIL, f"BehaviorExpr {node_uid} is_deferred={is_deferred}")
        
        if is_deferred:
            # 返回延迟执行的行为对象 (Lambda)
            # 捕获当前的意图栈
            captured_intents = list(self.context.intent_stack)
            # 获取推导出的预期类型 (如果有)
            expected_type = self.get_side_table("node_to_type", node_uid)
            return IbBehavior(node_uid, self, captured_intents, expected_type=expected_type)
        
        # 立即执行
        return self.service_context.llm_executor.execute_behavior_expression(node_uid, self.context)

    def visit_IbModule(self, node_uid: str, node_data: Dict[str, Any]):
        result = IbNone()
        for stmt_uid in node_data.get("body", []):
            result = self.visit(stmt_uid)
        return result

    def visit_IbConstant(self, node_uid: str, node_data: Dict[str, Any]) -> IbObject:
        """UTS: 统一常量装箱"""
        return Registry.box(node_data.get("value"))

    def visit_IbBinOp(self, node_uid: str, node_data: Dict[str, Any]) -> IbObject:
        """二元运算实现"""
        left = self.visit(node_data.get("left"))
        right = self.visit(node_data.get("right"))
        
        op = node_data.get("op")
        method = OP_MAPPING.get(op)
        
        if not method: raise self._report_error(f"Unsupported op: {op}", node_uid)
        return left.receive(method, [right])

    def visit_IbCompare(self, node_uid: str, node_data: Dict[str, Any]) -> IbObject:
        """比较运算实现"""
        left = self.visit(node_data.get("left"))
        # 简化：仅取第一个比较操作
        op = node_data.get("ops", ["=="])[0]
        right = self.visit(node_data.get("comparators", [None])[0])
        
        method = OP_MAPPING.get(op)
        
        if not method: raise self._report_error(f"Unsupported comparison: {op}", node_uid)
        return left.receive(method, [right])

    def visit_IbListExpr(self, node_uid: str, node_data: Dict[str, Any]) -> IbObject:
        """列表字面量 -> 统一装箱"""
        elts = [self.visit(e) for e in node_data.get("elts", [])]
        return Registry.box(elts)

    def visit_IbDict(self, node_uid: str, node_data: Dict[str, Any]) -> IbObject:
        """字典字面量 -> 统一装箱"""
        data = {}
        keys = node_data.get("keys", [])
        values = node_data.get("values", [])
        for k_uid, v_uid in zip(keys, values):
            key_obj = self.visit(k_uid) if k_uid else IbNone()
            val_obj = self.visit(v_uid)
            native_key = key_obj.to_native() if hasattr(key_obj, 'to_native') else key_obj
            data[native_key] = val_obj
        return Registry.box(data)

    def visit_IbSubscript(self, node_uid: str, node_data: Dict[str, Any]) -> IbObject:
        """下标访问 -> __getitem__"""
        value = self.visit(node_data.get("value"))
        slice_obj = self.visit(node_data.get("slice"))
        return value.receive('__getitem__', [slice_obj])

    def visit_IbUnaryOp(self, node_uid: str, node_data: Dict[str, Any]) -> IbObject:
        """一元运算实现"""
        operand = self.visit(node_data.get("operand"))
        op = node_data.get("op")
        method = {
            'UAdd': '__pos__', 'USub': '__neg__', 'Not': '__not__', 'Invert': '__invert__'
        }.get(op)
        
        if not method: raise self._report_error(f"Unsupported unary op: {op}", node_uid)
        return operand.receive(method, [])

    def visit_IbName(self, node_uid: str, node_data: Dict[str, Any]) -> IbObject:
        """变量读取：优先通过 Symbol UID 查找"""
        sym_uid = self.get_side_table("node_to_symbol", node_uid)
        if sym_uid:
            try:
                return self.context.get_variable_by_uid(sym_uid)
            except InterpreterError:
                # 如果是严格模式，UID 查找失败即报错
                if self.strict_mode: raise

        # 兼容性/动态代码回退：名称查找
        name = node_data.get("id")
        if self.strict_mode and not sym_uid:
            raise self._report_error(f"Strict mode: Symbol UID missing for variable '{name}'.", node_uid)
            
        self.debugger.trace(CoreModule.INTERPRETER, DebugLevel.DETAIL, f"Symbol UID lookup failed for {name}, falling back to name lookup.")
        return self.context.get_variable(name)

    def visit_IbAssign(self, node_uid: str, node_data: Dict[str, Any]):
        """赋值语句实现"""
        self.debugger.trace(CoreModule.INTERPRETER, DebugLevel.DETAIL, f"Executing assignment {node_uid}")
        
        value_uid = node_data.get("value")
        value = self.visit(value_uid)
        
        # 处理多重赋值目标 (var a, b = 1)
        for target_uid in node_data.get("targets", []):
            target_data = self.node_pool.get(target_uid)
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
                        self.context.define_variable(name, value, uid=sym_uid)
                elif not self.strict_mode:
                    # 回退到名称查找
                    self.context.set_variable(name, value)
                else:
                    raise self._report_error(f"Strict mode: Symbol UID missing for assignment to '{name}'.", target_uid)
            
            # 2. 类型标注表达式 (TypeAnnotatedExpr)
            elif target_data["_type"] == "IbTypeAnnotatedExpr":
                inner_target_uid = target_data.get("target")
                inner_target_data = self.node_pool.get(inner_target_uid)
                if inner_target_data and inner_target_data["_type"] == "IbName":
                    sym_uid = self.get_side_table("node_to_symbol", inner_target_uid)
                    name = inner_target_data.get("id")
                    # 总是定义新变量
                    self.context.define_variable(name, value, uid=sym_uid)
            
            # 3. 属性赋值 (Attribute)
            elif target_data["_type"] == "IbAttribute":
                obj = self.visit(target_data.get("value"))
                attr = target_data.get("attr")
                obj.receive('__setattr__', [Registry.box(attr), value])
                
        return IbNone()

    def visit_IbFunctionDef(self, node_uid: str, node_data: Dict[str, Any]):
        """普通函数定义"""
        func = IbUserFunction(node_uid, self)
        name = node_data.get("name")
        sym_uid = self.get_side_table("node_to_symbol", node_uid)
        self.context.define_variable(name, func, uid=sym_uid)
        return IbNone()

    def visit_IbLLMFunctionDef(self, node_uid: str, node_data: Dict[str, Any]):
        """LLM 函数定义"""
        func = IbLLMFunction(node_uid, self.service_context.llm_executor, self)
        name = node_data.get("name")
        sym_uid = self.get_side_table("node_to_symbol", node_uid)
        self.context.define_variable(name, func, uid=sym_uid)
        return IbNone()

    def visit_IbAugAssign(self, node_uid: str, node_data: Dict[str, Any]):
        """复合赋值实现 (a += 1)"""
        target_uid = node_data.get("target")
        target_data = self.node_pool.get(target_uid)
        
        value = self.visit(node_data.get("value"))
        op = node_data.get("op")
        method = {
            'Add': '__add__', 'Sub': '__sub__', 'Mult': '__mul__', 'Div': '__div__'
        }.get(op)
        
        if not method: raise self._report_error(f"Unsupported aug op: {op}", node_uid)
        
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
            obj.receive('__setattr__', [Registry.box(attr), new_val])
            
        return IbNone()

    def visit_IbBoolOp(self, node_uid: str, node_data: Dict[str, Any]) -> IbObject:
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

    def visit_IbCall(self, node_uid: str, node_data: Dict[str, Any]) -> IbObject:
        """UTS: 函数调用逻辑"""
        func = self.visit(node_data.get("func"))
        args = [self.visit(a) for a in node_data.get("args", [])]
        
        try:
            # 如果是 BoundMethod 或 IbFunction，其 call 内部会处理作用域
            # 如果是 IbObject，则发送 __call__ 消息
            if hasattr(func, 'call'):
                return func.call(Registry.get_none(), args)
            return func.receive('__call__', args)
        except (ReturnException, BreakException, ContinueException, RetryException, ThrownException):
            raise
        except InterpreterError:
            raise
        except Exception as e:
            raise self._report_error(f"Call failed: {str(e)}", node_uid)

    def visit_IbAttribute(self, node_uid: str, node_data: Dict[str, Any]) -> IbObject:
        """读取属性 -> __getattr__"""
        value = self.visit(node_data.get("value"))
        attr = node_data.get("attr")
        return value.receive('__getattr__', [Registry.box(attr)])

    def visit_IbIf(self, node_uid: str, node_data: Dict[str, Any]):
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

    def visit_IbWhile(self, node_uid: str, node_data: Dict[str, Any]):
        def action():
            while self.is_truthy(self.visit(node_data.get("test"))):
                try:
                    for stmt_uid in node_data.get("body", []):
                        self.visit(stmt_uid)
                except BreakException: break
                except ContinueException: continue
            return IbNone()
            
        return self._with_llm_fallback(node_uid, node_data, action)

    def visit_IbFor(self, node_uid: str, node_data: Dict[str, Any]):
        def action():
            target_uid = node_data.get("target")
            iter_uid = node_data.get("iter")
            body = node_data.get("body", [])
            
            # 标准 Foreach 循环
            iterable_obj = self.visit(iter_uid)
            
            # UTS: 使用消息传递获取迭代列表 (to_list 协议)
            try:
                elements_obj = iterable_obj.receive('to_list', [])
                if not isinstance(elements_obj, IbList):
                    raise self._report_error(f"Object is not iterable", node_uid)
                
                elements = elements_obj.elements
            except (ReturnException, BreakException, ContinueException, RetryException, ThrownException):
                raise
            except InterpreterError:
                raise
            except Exception as e:
                raise self._report_error(f"Iteration failed: {str(e)}", node_uid)
            total = len(elements)
            for i, item in enumerate(elements):
                # 注入循环上下文
                self.context.push_loop_context(i, total)
                
                # 绑定循环变量
                target_data = self.node_pool.get(target_uid)
                if target_data and target_data["_type"] == "IbName":
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

    def visit_IbReturn(self, node_uid: str, node_data: Dict[str, Any]):
        value_uid = node_data.get("value")
        value = self.visit(value_uid) if value_uid else IbNone()
        raise ReturnException(value)

    def visit_IbBreak(self, node_uid: str, node_data: Dict[str, Any]):
        raise BreakException()

    def visit_IbContinue(self, node_uid: str, node_data: Dict[str, Any]):
        raise ContinueException()

    def visit_IbExprStmt(self, node_uid: str, node_data: Dict[str, Any]):
        """表达式语句"""
        res = self.visit(node_data.get("value"))
        # 如果是行为描述行，则立即执行（作为语句时）
        if isinstance(res, IbBehavior):
            return res.receive('__call__', [])
        return res

    def visit_IbRetry(self, node_uid: str, node_data: Dict[str, Any]):
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

    def visit_IbTry(self, node_uid: str, node_data: Dict[str, Any]):
        """实现异常处理块"""
        def action():
            try:
                for stmt_uid in node_data.get("body", []):
                    self.visit(stmt_uid)
            except (ReturnException, BreakException, ContinueException, RetryException):
                raise
            except (ThrownException, Exception) as e:
                # 包装 Python 原生异常
                error_obj = e.value if isinstance(e, ThrownException) else Registry.box(str(e))
                
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

    def visit_IbImport(self, node_uid: str, node_data: Dict[str, Any]):
        for alias_uid in node_data.get("names", []):
            alias_data = self.node_pool.get(alias_uid)
            if alias_data:
                name = alias_data.get("name")
                asname = alias_data.get("asname")
                mod_inst = self.service_context.module_manager.import_module(name, self.context)
                
                # 绑定到当前作用域：优先使用别名，否则使用原始模块名
                target_name = asname if asname else name
                
                # [FIX] 必须获取符号 UID 并绑定，否则 visit_IbName 无法通过 UID 查找到该模块
                sym_uid = self.get_side_table("node_to_symbol", alias_uid)
                self.context.define_variable(target_name, mod_inst, is_const=True, uid=sym_uid)
        return IbNone()

    def visit_IbImportFrom(self, node_uid: str, node_data: Dict[str, Any]):
        names = []
        for alias_uid in node_data.get("names", []):
            alias_data = self.node_pool.get(alias_uid)
            if alias_data:
                names.append((alias_data.get("name"), alias_data.get("asname")))
        self.service_context.module_manager.import_from(node_data.get("module"), names, self.context)
        return IbNone()

    def visit_IbClassDef(self, node_uid: str, node_data: Dict[str, Any]):
        """动态创建类对象"""
        name = node_data.get("name")
        parent_name = node_data.get("parent") or "Object"
        new_class = Registry.create_subclass(name, parent_name)
        
        # 1. 注册方法与字段
        body = node_data.get("body", [])
        for stmt_uid in body:
            stmt_data = self.node_pool.get(stmt_uid)
            if not stmt_data: continue
            
            if stmt_data["_type"] == "IbFunctionDef":
                new_class.register_method(stmt_data["name"], IbUserFunction(stmt_uid, self))
            elif stmt_data["_type"] == "IbLLMFunctionDef":
                new_class.register_method(stmt_data["name"], IbLLMFunction(stmt_uid, self.service_context.llm_executor, self))
            elif stmt_data["_type"] == "IbAssign":
                val = self.visit(stmt_data.get("value")) if stmt_data.get("value") else IbNone()
                for target_uid in stmt_data.get("targets", []):
                    target_data = self.node_pool.get(target_uid)
                    if target_data and target_data["_type"] == "IbName":
                        new_class.default_fields[target_data.get("id")] = val
        
        # 绑定到当前作用域
        sym_uid = self.get_side_table("node_to_symbol", node_uid)
        self.context.define_variable(name, new_class, uid=sym_uid)
        return IbNone()

    def visit_IbRaise(self, node_uid: str, node_data: Dict[str, Any]):
        """抛出异常"""
        exc_uid = node_data.get("exc")
        exc_val = self.visit(exc_uid) if exc_uid else IbNone()
        raise ThrownException(exc_val)

    def visit_IbIntentStmt(self, node_uid: str, node_data: Dict[str, Any]):
        """处理意图块"""
        intent_uid = node_data.get("intent")
        intent_data = self.node_pool.get(intent_uid)
        
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

    def visit_IbPass(self, node_uid: str, node_data: Dict[str, Any]):
        return IbNone()

    def is_truthy(self, value: IbObject) -> bool:
        """UTS: 使用 to_bool 协议判断真值"""
        res = value.receive('to_bool', [])
        return res.to_native() != 0
