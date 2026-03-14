import re
import json
import sys
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Callable, Union, Mapping
from core.domain import ast as ast
from core.domain.issue import (
    InterpreterError, LLMUncertaintyError, Severity
)
from core.runtime.exceptions import (
    ReturnException, BreakException, ContinueException, ThrownException, RetryException
)
from core.domain.issue_atomic import Location
from core.foundation.diagnostics.codes import (
    RUN_GENERIC_ERROR, RUN_TYPE_MISMATCH, RUN_UNDEFINED_VARIABLE,
    RUN_LIMIT_EXCEEDED, RUN_CALL_ERROR, RUN_ATTRIBUTE_ERROR
)
from core.runtime.interfaces import (
    Interpreter as InterpreterInterface, 
    RuntimeContext, LLMExecutor, InterOp, ModuleManager, ServiceContext, IssueTracker,
    PermissionManager, Scope, SymbolView, ISourceProvider, ICompilerService
)
from .runtime_context import RuntimeContextImpl
from .llm_executor import LLMExecutorImpl
from .interop import InterOpImpl
from .module_manager import ModuleManagerImpl
from .permissions import PermissionManager as PermissionManagerImpl
from core.runtime.objects.kernel import IbObject, IbClass, IbUserFunction, IbFunction, IbNativeFunction, IbLLMFunction
from core.domain.types.descriptors import TypeDescriptor as Type, ListMetadata as ListType, DictMetadata as DictType, ANY_DESCRIPTOR as ANY_TYPE
from core.runtime.objects.builtins import IbInteger, IbString, IbList, IbNone, IbBehavior
from core.runtime.bootstrap.builtin_initializer import initialize_builtin_classes
from core.foundation.registry import Registry
from core.foundation.host_interface import HostInterface
from core.foundation.interfaces import IStackInspector
from core.foundation.diagnostics.core_debugger import CoreModule, DebugLevel, core_debugger
from .llm_executor import intent_scoped
from core.runtime.objects.intent import IbIntent, IntentMode, IntentRole
from .intrinsics import IntrinsicManager
from .ast_view import ReadOnlyNodePool
from core.runtime.loader import ArtifactLoader
from core.runtime.host.service import HostService
from .constants import OP_MAPPING, UNARY_OP_MAPPING


class ServiceContextImpl:
    """注入容器实现类 (已移除 Evaluator)"""
    def __init__(self, issue_tracker: IssueTracker, 
                 runtime_context: RuntimeContext,
                 llm_executor: LLMExecutor,
                 module_manager: ModuleManager,
                 interop: InterOp,
                 permission_manager: PermissionManager,
                 interpreter: InterpreterInterface,
                 registry: Registry,
                 host_service: Optional[Any] = None,
                 source_provider: Optional[ISourceProvider] = None,
                 compiler: Optional[ICompilerService] = None,
                 debugger: Any = None):
        self._issue_tracker = issue_tracker
        self._runtime_context = runtime_context
        self._llm_executor = llm_executor
        self._module_manager = module_manager
        self._interop = interop
        self._permission_manager = permission_manager
        self._interpreter = interpreter
        self._registry = registry
        self._host_service = host_service
        self._source_provider = source_provider
        self._compiler = compiler
        self._debugger = debugger

    @property
    def debugger(self) -> Any: return self._debugger
    @property
    def interpreter(self) -> InterpreterInterface: return self._interpreter
    @property
    def registry(self) -> Registry: return self._registry
    @property
    def issue_tracker(self) -> IssueTracker: return self._issue_tracker
    @property
    def runtime_context(self) -> RuntimeContext: 
        # [FIX] 动态获取解释器当前活跃的 Context，解决跨模块加载时的作用域滞后问题
        return self._interpreter.context

    @property
    def symbol_view(self) -> SymbolView:
        return self.runtime_context.get_symbol_view()
    @property
    def llm_executor(self) -> LLMExecutor: return self._llm_executor
    @property
    def module_manager(self) -> ModuleManager: return self._module_manager
    @property
    def interop(self) -> InterOp: return self._interop
    @property
    def permission_manager(self) -> PermissionManager: return self._permission_manager
    @property
    def host_service(self) -> Any: return self._host_service
    @property
    def source_provider(self) -> ISourceProvider: return self._source_provider
    @property
    def compiler(self) -> ICompilerService: return self._compiler

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
                 strict_mode: bool = False,
                 registry: Optional[Registry] = None,
                 source_provider: Optional[ISourceProvider] = None,
                 compiler: Optional[ICompilerService] = None,
                 factory: Optional[Any] = None):
        
        # 0. 启动内核引导
        self.registry = registry or Registry()
        initialize_builtin_classes(self.registry)
        # [NEW] 加载内置函数插件 (Intrinsics)
        self.intrinsic_manager = IntrinsicManager(self.registry)
        self.intrinsic_manager.load_defaults(self)
        
        self.issue_tracker = issue_tracker
        self.output_callback = output_callback
        self.input_callback = input_callback
        self.host_interface = host_interface or HostInterface()
        self.debugger = debugger or core_debugger
        self.source_provider = source_provider
        self.compiler = compiler
        self.factory = factory
        
        # 1. 核心解耦：通过 ArtifactLoader 加载并水化产物
        loader = ArtifactLoader(self.registry)
        loaded = loader.load(artifact)
        
        self.node_pool = loaded.node_pool
        self.symbol_pool = loaded.symbol_pool
        self.scope_pool = loaded.scope_pool
        self.type_pool = loaded.type_pool
        self.asset_pool = loaded.asset_pool
        self.entry_module = loaded.entry_module
        self.type_hydrator = loaded.type_hydrator
        self.artifact_dict = loaded.artifact_dict
        
        # 2. 初始化基础组件
        runtime_context = RuntimeContextImpl(registry=self.registry)
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
            registry=self.registry,
            host_service=None, # 占位符，稍后注入
            source_provider=self.source_provider,
            compiler=self.compiler,
            debugger=self.debugger
        )
        
        # 5. 初始化内置宿主服务 (HostService)
        # 注意：这里注入 self.factory (Orchestrator) 彻底消除物理循环依赖
        self.host_service = HostService(self.service_context, self.factory)
        self.service_context._host_service = self.host_service

        # 6. 完成子组件的注入
        llm_executor.service_context = self.service_context
        module_manager.set_interpreter(self)
        
        self._current_context = runtime_context
        self._setup_context(self._current_context)

        # 运行限制
        self.max_instructions = max_instructions
        self.instruction_count = 0
        
        # [IES 2.1 Defensive Patch] 递归深度安全校验
        # 每一层 IBCI 调用大约消耗 4 层 Python 栈帧
        # 必须确保 max_call_stack * 4 < sys.getrecursionlimit() 以免进程崩溃
        python_limit = sys.getrecursionlimit()
        safe_limit = (python_limit - 100) // 4 # 留出 100 帧给宿主系统
        if max_call_stack > safe_limit:
            self.debugger.trace(CoreModule.INTERPRETER, DebugLevel.BASIC, 
                f"Warning: max_call_stack {max_call_stack} is unsafe for Python limit {python_limit}. "
                f"Auto-adjusting to safe limit {safe_limit}")
            max_call_stack = safe_limit
            
        self.max_call_stack = max_call_stack
        self.call_stack_depth = 0
        self.current_module_name: Optional[str] = None
        self.strict_mode = strict_mode

        # [IES 2.0 Optimization] 预先映射访问方法，消除运行时的字符串拼接和反射开销
        self._visitor_cache: Dict[str, Callable] = {}
        for attr in dir(self):
            if attr.startswith("visit_"):
                self._visitor_cache[attr[6:]] = getattr(self, attr)

    def get_side_table(self, table_name: str, node_uid: str) -> Any:
        """获取当前模块下的侧表信息"""
        if not self.current_module_name:
            return None
        
        module_data = self.artifact_dict.get("modules", {}).get(self.current_module_name, {})
        if not isinstance(module_data, Mapping):
            # print(f"DEBUG: module_data for {self.current_module_name} is NOT a dict! it is {type(module_data)}")
            return None
            
        table = module_data.get("side_tables", {}).get(table_name, {})
        return table.get(node_uid)

    def get_node_data(self, node_uid: str) -> Mapping[str, Any]:
        """[Standardized] 获取 AST 节点数据的唯一入口，返回只读视图"""
        node_data = self.node_pool.get(node_uid)
        if node_data is None:
            # 这是一个防御性检查，通常由编译器保证正确
            raise self._report_error(f"Internal Error: Node pool lookup failed for {node_uid}")
        return ReadOnlyNodePool(node_data)

    def save_state(self) -> Mapping[str, Any]:
        """导出当前解释器的运行状态快照 (用于调试或热替换)"""
        return {
            "artifact": self.artifact_dict,
            "instruction_count": self.instruction_count,
            "call_stack_depth": self.call_stack_depth,
            "current_module_name": self.current_module_name,
            # 注意：Context 状态通常由外部单独管理，此处仅记录引用
        }

    def restore_state(self, state: Mapping[str, Any]):
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

    def hot_reload_pools(self, artifact_dict: Mapping[str, Any]):
        """热替换底层数据池，不改变当前的变量现场"""
        self.artifact_dict = artifact_dict
        
        pools = artifact_dict.get("pools", {})
        if not isinstance(pools, Mapping):
             raise ValueError(f"Artifact pools must be a dict, got {type(pools)}")
             
        self.node_pool = pools.get("nodes", {})
        if not isinstance(self.node_pool, Mapping):
             raise ValueError(f"Node pool must be a dict, got {type(self.node_pool)}")
        self.symbol_pool = pools.get("symbols", {})
        self.scope_pool = pools.get("scopes", {})
        self.type_pool = pools.get("types", {})
        self.debugger.trace(CoreModule.INTERPRETER, DebugLevel.BASIC, "Interpreter pools hot-reloaded.")

    def setup_context(self, context: RuntimeContext, force: bool = False, deserializer: Optional[Any] = None):
        """为 Context 注入基础内置变量 (Public API)"""
        # 使用私有属性访问以仅检查当前作用域，避免与后续 bootstrap 冲突
        global_symbols = context.global_scope.get_all_symbols()
        defined_names = set(global_symbols.keys())
        
        # [IES 2.0] 内置功能插件化重绑定
        self.intrinsic_manager.rebind(self, context, deserializer=deserializer)
        
        # 注入内置类 (int, str, float, list, dict 等)
        for name, ib_class in self.registry.get_all_classes().items():
            if name not in defined_names or force:
                context.define_variable(name, ib_class, is_const=True, force=force)
                defined_names.add(name)

    def _setup_context(self, context: RuntimeContext):
        self.setup_context(context)
        # [IES 2.1] 绑定解释器引用到上下文，以便序列化时能访问静态池
        if hasattr(context, '_interpreter'):
            context._interpreter = self
        elif hasattr(context, '__dict__'):
            context._interpreter = self

    @property
    def context(self) -> RuntimeContext:
        return self._current_context

    @context.setter
    def context(self, value: RuntimeContext):
        self._current_context = value

    def interpret(self, module_uid: str) -> IbObject:
        """从模块 UID 开始执行"""
        return self.execute_module(module_uid)

    def run(self) -> bool:
        """从入口模块开始执行完整的项目"""
        try:
            if not self.entry_module:
                return True
                
            module_data = self.artifact_dict.get("modules", {}).get(self.entry_module)
            if not module_data:
                return True
                
            self.execute_module(module_data["root_node_uid"], module_name=self.entry_module)
            return True
        except Exception as e:
            # 运行时异常已由解释器内部报告
            if not isinstance(e, InterpreterError):
                import traceback
                traceback.print_exc()
            raise e

    def execute_module(self, module_uid: str, module_name: str = "main", scope: Optional[Scope] = None) -> IbObject:
        self.debugger.trace(CoreModule.INTERPRETER, DebugLevel.BASIC, f"Starting execution of module {module_name} ({module_uid})...")
        
        # DEBUG
        # print(f"DEBUG: execute_module {module_name} uid={module_uid}")
        # if not isinstance(self.node_pool, Mapping):
        #     print(f"DEBUG: node_pool is NOT a dict! it is {type(self.node_pool)}")
        
        old_module = self.current_module_name
        self.current_module_name = module_name
        
        module_data = self.get_node_data(module_uid)
        if not module_data:
            # print(f"DEBUG: module_data not found for {module_uid} in pool keys: {list(self.node_pool.keys())[:10]}")
            raise self._report_error(f"Module UID {module_uid} not found.")
        
        if not isinstance(module_data, Mapping):
            # print(f"DEBUG: module_data is NOT a mapping! it is {type(module_data)} -> {module_data}")
            raise self._report_error(f"Module data for {module_uid} is not a dict: {type(module_data)} -> {module_data}")

        old_context = self._current_context
        if scope:
             # 创建新 Context 并绑定 Scope
             new_ctx = RuntimeContextImpl(initial_scope=scope, registry=self.registry)
             self._current_context = new_ctx
             self._setup_context(self._current_context)

        self.instruction_count = 0
        result = self.registry.get_none()
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
        """
        [Standardized] 从 side_tables 中恢复位置信息并向 IssueTracker 报告。
        实现了编译器与解释器在错误报告协议上的对齐。
        """
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
        
        # 1. 构造标准诊断信息并上报
        self.issue_tracker.report(
            severity=Severity.ERROR,
            code=error_code or RUN_GENERIC_ERROR,
            message=message,
            location=loc
        )
        
        # 2. 构造异常并返回（供 visit 方法 raise）
        err = InterpreterError(message, error_code=error_code or RUN_GENERIC_ERROR)
        err.location = loc
        return err

    def _resolve_value(self, val: Any) -> Any:
        """[IES 2.2 Security Update] 处理外部资产引用的解析"""
        # 支持 dict 和 ReadOnlyNodePool (Mapping)
        if hasattr(val, "get") and val.get("_type") == "ext_ref":
            uid = val.get("uid")
            if uid in self.asset_pool:
                return self.asset_pool[uid]
            # 如果资产池中没有，可能是编译器外置但还没注入
            return f"__EXT_ASSET_MISSING_{uid}__"
        return val

    def visit(self, node_uid: Union[str, Any]) -> IbObject:
        """核心 Pool-Walking 分发方法"""
        if node_uid is None:
            return self.registry.get_none()
        
        # 如果不是字符串，则可能是基础类型（如 int, bool）或已解箱对象
        if not isinstance(node_uid, str):
            if hasattr(node_uid, 'uid'):
                node_uid = node_uid.uid
            else:
                # 基础类型直接装箱
                if isinstance(node_uid, (int, float, bool, dict)):
                    return self.registry.box(self._resolve_value(node_uid))
                return self.registry.get_none()

        # [DEBUG] 检查 node_uid 是否在 pool 中
        if node_uid not in self.node_pool:
            # 如果不在 pool 中，可能是字符串字面量
            return self.registry.box(self._resolve_value(node_uid))

        node_data = self.get_node_data(node_uid)
        if not isinstance(node_data, Mapping):
             # 这说明 pool 里存的不是 node data 字典，而是别的东西（比如另一个 UID 字符串）
             raise self._report_error(f"Pool corruption: node_pool[{node_uid}] is {type(node_data)}: {node_data}", node_uid)
        if not node_data:
            # 可能是基础类型或已解箱对象
            if isinstance(node_uid, (int, float, str, bool, dict)):
                return self.registry.box(self._resolve_value(node_uid))
            return self.registry.get_none()

        self.instruction_count += 1
        
        if self.instruction_count > self.max_instructions:
            raise self._report_error("Execution limit exceeded", node_uid, error_code=RUN_LIMIT_EXCEEDED)

        if self.call_stack_depth >= self.max_call_stack:
             raise self._report_error("Recursion depth exceeded", node_uid, error_code=RUN_LIMIT_EXCEEDED)
        
        self.call_stack_depth += 1
        
        # [NEW] 意图自动化拦截：从侧表获取绑定意图并自动压栈，实现“语义涂抹”自动化
        pushed_count = 0
        intent_uids = self.get_side_table("node_intents", node_uid)
        if intent_uids:
            for i_uid in intent_uids:
                i_data = self.node_pool.get(i_uid)
                if i_data:
                    intent = IbIntent(
                        ib_class=self.registry.get_class("Intent"),
                        content=i_data.get('content', ''),
                        mode=IntentMode.from_str(i_data.get('mode', '+')),
                        tag=i_data.get('tag'),
                        segments=i_data.get('segments', []),
                        role=IntentRole.SMEAR,
                        source_uid=i_uid
                    )
                    self.context.push_intent(intent)
                    pushed_count += 1

        try:
            node_type = node_data["_type"]
            visitor = self._visitor_cache.get(node_type, self.generic_visit)
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
            # [NEW] 自动出栈，确保意图作用域正确恢复
            for _ in range(pushed_count):
                self.context.pop_intent()

    def generic_visit(self, node_uid: str, node_data: Mapping[str, Any]):
        raise self._report_error(f"No visit method implemented for {node_data['_type']}", node_uid, error_code=RUN_GENERIC_ERROR)

    # --- 访问方法实现 ---

    def visit_IbBehaviorExpr(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """行为描述行：█ ... █"""
        is_deferred = self.get_side_table("node_is_deferred", node_uid)
        self.debugger.trace(CoreModule.INTERPRETER, DebugLevel.DETAIL, f"BehaviorExpr {node_uid} is_deferred={is_deferred}")
        
        if is_deferred:
            # 返回延迟执行的行为对象 (Lambda)
            # [IES 2.0 Optimization] 直接引用意图栈顶节点，实现结构共享
            captured_intents = self.context.intent_stack
            # 获取推导出的预期类型 (如果有)
            expected_type = self.get_side_table("node_to_type", node_uid)
            return IbBehavior(node_uid, self, captured_intents, expected_type=expected_type)
        
        # 立即执行
        return self.service_context.llm_executor.execute_behavior_expression(node_uid, self.context)

    def visit_IbModule(self, node_uid: str, node_data: Mapping[str, Any]):
        result = self.registry.get_none()
        for stmt_uid in node_data.get("body", []):
            result = self.visit(stmt_uid)
        return result

    def visit_IbConstant(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """UTS: 统一常量装箱"""
        return self.registry.box(self._resolve_value(node_data.get("value")))

    def visit_IbBinOp(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """二元运算实现"""
        left = self.visit(node_data.get("left"))
        right = self.visit(node_data.get("right"))
        
        op = node_data.get("op")
        method = OP_MAPPING.get(op)
        
        if not method: raise self._report_error(f"Unsupported op: {op}", node_uid)
        return left.receive(method, [right])

    def visit_IbCompare(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """比较运算实现"""
        left = self.visit(node_data.get("left"))
        # 简化：仅取第一个比较操作
        op = node_data.get("ops", ["=="])[0]
        right = self.visit(node_data.get("comparators", [None])[0])
        
        method = OP_MAPPING.get(op)
        
        if not method: raise self._report_error(f"Unsupported comparison: {op}", node_uid)
        return left.receive(method, [right])

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

    def visit_IbSubscript(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """下标访问 -> __getitem__"""
        value = self.visit(node_data.get("value"))
        slice_obj = self.visit(node_data.get("slice"))
        return value.receive('__getitem__', [slice_obj])

    def visit_IbCastExpr(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """类型强转运行时实现"""
        value = self.visit(node_data.get("value"))
        target_type_name = node_data.get("type_name")
        
        # [IES 2.0] 调用目标类的 cast_to 协议
        target_class = self.registry.get_class(target_type_name)
        if not target_class:
            return value # 如果类型未定义，回退为 no-op
            
        return value.receive('cast_to', [target_class])

    def visit_IbUnaryOp(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """一元运算实现"""
        operand = self.visit(node_data.get("operand"))
        op_symbol = node_data.get("op")
        # 兼容性处理
        op_map = {'UAdd': '+', 'USub': '-', 'Not': 'not', 'Invert': '~'}
        op = op_map.get(op_symbol, op_symbol)
        
        method = UNARY_OP_MAPPING.get(op)
        
        if not method: raise self._report_error(f"Unsupported unary op: {op_symbol}", node_uid)
        return operand.receive(method, [])

    def visit_IbName(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
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
        
        try:
            return self.context.get_variable(name)
        except InterpreterError:
            # 2. 尝试从 Registry 获取类 (支持内置类型名称如 int, str)
            cls = self.registry.get_class(name)
            if cls: return cls
            
            if self.strict_mode and not sym_uid:
                raise self._report_error(f"Strict mode: Symbol UID missing for variable '{name}'.", node_uid)
            
            raise

    def visit_IbAssign(self, node_uid: str, node_data: Mapping[str, Any]):
        """赋值语句实现"""
        self.debugger.trace(CoreModule.INTERPRETER, DebugLevel.DETAIL, f"Executing assignment {node_uid}")
        
        def action():
            value_uid = node_data.get("value")
            value = self.visit(value_uid)
            
            # 处理多重赋值目标 (var a, b = 1)
            for target_uid in node_data.get("targets", []):
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
                            declared_type = self._resolve_type_from_symbol(sym_uid)
                            self.context.define_variable(name, value, declared_type=declared_type, uid=sym_uid)
                    elif not self.strict_mode:
                        # 回退到名称查找
                        self.context.set_variable(name, value)
                    else:
                        raise self._report_error(f"Strict mode: Symbol UID missing for assignment to '{name}'.", target_uid)
                
                # 2. 类型标注表达式 (TypeAnnotatedExpr)
                elif target_data["_type"] == "IbTypeAnnotatedExpr":
                    inner_target_uid = target_data.get("target")
                    inner_target_data = self.get_node_data(inner_target_uid)
                    if inner_target_data and inner_target_data["_type"] == "IbName":
                        sym_uid = self.get_side_table("node_to_symbol", inner_target_uid)
                        name = inner_target_data.get("id")
                        # 总是定义新变量
                        declared_type = self._resolve_type_from_symbol(sym_uid)
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
            
        return self._with_llm_fallback(node_uid, node_data, action)

    def visit_IbFunctionDef(self, node_uid: str, node_data: Mapping[str, Any]):
        """普通函数定义"""
        sym_uid = self.get_side_table("node_to_symbol", node_uid)
        declared_type = self._resolve_type_from_symbol(sym_uid)
        func = IbUserFunction(node_uid, self, descriptor=declared_type)
        name = node_data.get("name")
        self.context.define_variable(name, func, declared_type=declared_type, uid=sym_uid)
        return self.registry.get_none()

    def visit_IbLLMFunctionDef(self, node_uid: str, node_data: Mapping[str, Any]):
        """LLM 函数定义"""
        sym_uid = self.get_side_table("node_to_symbol", node_uid)
        declared_type = self._resolve_type_from_symbol(sym_uid)
        func = IbLLMFunction(node_uid, self.service_context.llm_executor, self, descriptor=declared_type)
        name = node_data.get("name")
        self.context.define_variable(name, func, declared_type=declared_type, uid=sym_uid)
        return self.registry.get_none()

    def visit_IbAugAssign(self, node_uid: str, node_data: Mapping[str, Any]):
        """复合赋值实现 (a += 1)"""
        def action():
            target_uid = node_data.get("target")
            target_data = self.get_node_data(target_uid)
            
            value = self.visit(node_data.get("value"))
            op_symbol = node_data.get("op")
            # 兼容性处理：如果是 Add -> +
            op_map = {'Add': '+', 'Sub': '-', 'Mult': '*', 'Div': '/'}
            op = op_map.get(op_symbol, op_symbol)
            
            method = OP_MAPPING.get(op)
            
            if not method: raise self._report_error(f"Unsupported aug op: {op_symbol}", node_uid)
            
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
            
        return self._with_llm_fallback(node_uid, node_data, action)

    def visit_IbBoolOp(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """逻辑运算 (and/or)"""
        is_or = node_data.get("op") == 'or'
        last_val = self.registry.get_none()
        for val_uid in node_data.get("values", []):
            val = self.visit(val_uid)
            last_val = val
            if is_or and self.is_truthy(val): return val
            if not is_or and not self.is_truthy(val): return val
        return last_val

    def visit_IfExp(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """三元表达式"""
        if self.is_truthy(self.visit(node_data.get("test"))):
            return self.visit(node_data.get("body"))
        return self.visit(node_data.get("orelse"))

    def visit_IbCall(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """UTS: 函数调用逻辑"""
        func = self.visit(node_data.get("func"))
        args = [self.visit(a) for a in node_data.get("args", [])]
        
        try:
            # 如果是 BoundMethod 或 IbFunction，其 call 内部会处理作用域
            # 如果是 IbObject，则发送 __call__ 消息
            if hasattr(func, 'call'):
                return func.call(self.registry.get_none(), args)
            return func.receive('__call__', args)
        except (ReturnException, BreakException, ContinueException, RetryException, ThrownException):
            raise
        except InterpreterError:
            raise
        except Exception as e:
            import traceback
            print(f"DEBUG: Call failed traceback:\n{traceback.format_exc()}")
            raise self._report_error(f"Call failed: {str(e)}", node_uid)

    def visit_IbAttribute(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        """读取属性 -> __getattr__"""
        value = self.visit(node_data.get("value"))
        attr = node_data.get("attr")
        return value.receive('__getattr__', [self.registry.box(attr)])

    def visit_IbIf(self, node_uid: str, node_data: Mapping[str, Any]):
        def action():
            condition = self.visit(node_data.get("test"))
            if self.is_truthy(condition):
                for stmt_uid in node_data.get("body", []):
                    self.visit(stmt_uid)
            else:
                for stmt_uid in node_data.get("orelse", []):
                    self.visit(stmt_uid)
            return self.registry.get_none()
            
        return self._with_llm_fallback(node_uid, node_data, action)

    def visit_IbWhile(self, node_uid: str, node_data: Mapping[str, Any]):
        def action():
            while self.is_truthy(self.visit(node_data.get("test"))):
                try:
                    for stmt_uid in node_data.get("body", []):
                        self.visit(stmt_uid)
                except BreakException: break
                except ContinueException: continue
            return self.registry.get_none()
            
        return self._with_llm_fallback(node_uid, node_data, action)

    def visit_IbFor(self, node_uid: str, node_data: Mapping[str, Any]):
        def action():
            target_uid = node_data.get("target")
            iter_uid = node_data.get("iter")
            body = node_data.get("body", [])
            
            # [IES 2.0] 条件驱动循环 (Condition-driven loop: for @~ ... ~:)
            if target_uid is None:
                # 这种情况不需要 to_list 协议，而是直接根据条件的真值决定是否继续
                while self.is_truthy(self.visit(iter_uid)):
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
                target_data = self.get_node_data(target_uid)
                if target_data and target_data["_type"] == "IbName":
                    name = target_data.get("id")
                    sym_uid = self.get_side_table("node_to_symbol", target_uid)
                    declared_type = self._resolve_type_from_symbol(sym_uid)
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
            
        return self._with_llm_fallback(node_uid, node_data, action)

    def visit_IbReturn(self, node_uid: str, node_data: Mapping[str, Any]):
        value_uid = node_data.get("value")
        value = self.visit(value_uid) if value_uid else self.registry.get_none()
        raise ReturnException(value)

    def visit_IbBreak(self, node_uid: str, node_data: Mapping[str, Any]):
        raise BreakException()

    def visit_IbContinue(self, node_uid: str, node_data: Mapping[str, Any]):
        raise ContinueException()

    def visit_IbExprStmt(self, node_uid: str, node_data: Mapping[str, Any]):
        """表达式语句"""
        def action():
            res = self.visit(node_data.get("value"))
            # 如果是行为描述行，则立即执行（作为语句时）
            if isinstance(res, IbBehavior):
                return res.receive('__call__', [])
            return res
            
        return self._with_llm_fallback(node_uid, node_data, action)

    def visit_IbRetry(self, node_uid: str, node_data: Mapping[str, Any]):
        hint_uid = node_data.get("hint")
        hint_val = None
        if hint_uid:
            hint_obj = self.visit(hint_uid)
            hint_val = hint_obj.to_native() if hasattr(hint_obj, 'to_native') else str(hint_obj)
        
        # 将 hint 设置到 LLM 执行器中
        self.service_context.llm_executor.retry_hint = hint_val
        raise RetryException()

    def _with_llm_fallback(self, node_uid: str, node_data: Mapping[str, Any], action: Callable):
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
                        return self.registry.get_none()
                    except RetryException:
                        continue
                raise

    def visit_IbTry(self, node_uid: str, node_data: Mapping[str, Any]):
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
            
        return self._with_llm_fallback(node_uid, node_data, action)

    def visit_IbImport(self, node_uid: str, node_data: Mapping[str, Any]):
        for alias_uid in node_data.get("names", []):
            alias_data = self.get_node_data(alias_uid)
            if alias_data:
                name = alias_data.get("name")
                asname = alias_data.get("asname")
                mod_inst = self.service_context.module_manager.import_module(name, self.context)
                
                # 绑定到当前作用域：优先使用别名，否则使用原始模块名
                target_name = asname if asname else name
                
                # [FIX] 必须获取符号 UID 并绑定，否则 visit_IbName 无法通过 UID 查找到该模块
                sym_uid = self.get_side_table("node_to_symbol", alias_uid)
                self.context.define_variable(target_name, mod_inst, is_const=True, uid=sym_uid)
        return self.registry.get_none()

    def visit_IbImportFrom(self, node_uid: str, node_data: Mapping[str, Any]):
        names = []
        for alias_uid in node_data.get("names", []):
            alias_data = self.get_node_data(alias_uid)
            if alias_data:
                names.append((alias_data.get("name"), alias_data.get("asname")))
        self.service_context.module_manager.import_from(node_data.get("module"), names, self.context)
        return self.registry.get_none()

    def _extract_name_id(self, node_uid: str) -> Optional[str]:
        """从表达式节点中提取变量名（处理类型标注等情况）"""
        node_data = self.get_node_data(node_uid)
        if not node_data: return None
        if node_data["_type"] == "IbName":
            return node_data.get("id")
        if node_data["_type"] == "IbTypeAnnotatedExpr":
            return self._extract_name_id(node_data.get("target"))
        return None

    def visit_IbClassDef(self, node_uid: str, node_data: Mapping[str, Any]):
        """动态创建类对象"""
        name = node_data.get("name")
        parent_name = node_data.get("parent") or "Object"
        
        # [Phase 1.1] 强元数据对齐：动态创建类描述符
        sym_uid = self.get_side_table("node_to_symbol", node_uid)
        descriptor = self._resolve_type_from_symbol(sym_uid)
        if not descriptor:
            # 如果符号表中没有预定义的描述符（如动态注入代码），则现场创建一个
            descriptor = self.registry.get_metadata_registry().factory.create_class(name, parent=parent_name)
            
        new_class = self.registry.create_subclass(name, descriptor, parent_name)
        
        # 1. 注册方法与字段
        body = node_data.get("body", [])
        for stmt_uid in body:
            stmt_data = self.get_node_data(stmt_uid)
            if not stmt_data: continue
            
            if stmt_data["_type"] == "IbFunctionDef":
                sym_uid = self.get_side_table("node_to_symbol", stmt_uid)
                declared_type = self._resolve_type_from_symbol(sym_uid)
                new_class.register_method(stmt_data["name"], IbUserFunction(stmt_uid, self, descriptor=declared_type))
            elif stmt_data["_type"] == "IbLLMFunctionDef":
                sym_uid = self.get_side_table("node_to_symbol", stmt_uid)
                declared_type = self._resolve_type_from_symbol(sym_uid)
                new_class.register_method(stmt_data["name"], IbLLMFunction(stmt_uid, self.service_context.llm_executor, self, descriptor=declared_type))
            elif stmt_data["_type"] == "IbAssign":
                val_uid = stmt_data.get("value")
                if val_uid:
                    val = self.visit(val_uid)
                else:
                    # [FIX] 兼容旧 Spec：类字段 var 定义默认初始化为 0
                    val = self.registry.box(0)
                
                # 确保 val 永远不为 Python None
                if val is None: val = self.registry.get_none()
                
                for target_uid in stmt_data.get("targets", []):
                    target_name = self._extract_name_id(target_uid)
                    if target_name:
                        new_class.default_fields[target_name] = val
        
        # 绑定到当前作用域
        sym_uid = self.get_side_table("node_to_symbol", node_uid)
        self.context.define_variable(name, new_class, uid=sym_uid)
        return self.registry.get_none()

    def _resolve_type_from_symbol(self, sym_uid: str) -> Optional[Type]:
        """从符号池中解析声明的类型描述符"""
        if not sym_uid or sym_uid not in self.symbol_pool:
            return None
        sym_data = self.symbol_pool[sym_uid]
        type_uid = sym_data.get("type_uid")
        if not type_uid:
            return None
        # 通过 hydrator 获取或重建描述符
        return self.type_hydrator.hydrate(type_uid)

    def visit_IbRaise(self, node_uid: str, node_data: Mapping[str, Any]):
        """抛出异常"""
        exc_uid = node_data.get("exc")
        exc_val = self.visit(exc_uid) if exc_uid else self.registry.get_none()
        raise ThrownException(exc_val)

    def visit_IbIntentStmt(self, node_uid: str, node_data: Mapping[str, Any]):
        """处理意图块 (IES 2.0 强契约)"""
        intent_uid = node_data.get("intent")
        intent_data = self.get_node_data(intent_uid)
        
        # [Active Defense] 仅接受结构化意图对象，不再支持原始字符串
        if not intent_data:
            raise self._report_error("Invalid intent metadata: Intent must be a structured IbIntentInfo node.")
            
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

    def visit_IbPass(self, node_uid: str, node_data: Mapping[str, Any]):
        return self.registry.get_none()

    def is_truthy(self, value: IbObject) -> bool:
        """UTS: 使用 to_bool 协议判断真值"""
        res = value.receive('to_bool', [])
        return res.to_native() != 0
