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
    PermissionManager, Scope, SymbolView, ISourceProvider, ICompilerService, IObjectFactory
)
from .runtime_context import RuntimeContextImpl
from .factory import RuntimeObjectFactory
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
from .call_stack import LogicalCallStack, StackFrame
from .handlers.stmt_handler import StmtHandler
from .handlers.expr_handler import ExprHandler
from .handlers.import_handler import ImportHandler


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
                 object_factory: IObjectFactory,
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
        self._object_factory = object_factory
        self._host_service = host_service
        self._source_provider = source_provider
        self._compiler = compiler
        self._debugger = debugger

        # [IES 2.0] 显式双向绑定，不再使用 hasattr 探测
        # 核心服务组件必须遵循标准化接口
        self._llm_executor.service_context = self
        self._module_manager.interpreter = self._interpreter

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
        # [IES 2.0] 统一从解释器获取当前活跃的作用域，确保符号查找的一致性
        return self._interpreter.context

    @property
    def symbol_view(self) -> SymbolView:
        return self.runtime_context.get_symbol_view()
    @property
    def llm_executor(self) -> LLMExecutor: return self._llm_executor
    @property
    def module_manager(self) -> ModuleManager: return self._module_manager
    @property
    def object_factory(self) -> IObjectFactory: return self._object_factory
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
                 factory: Optional[Any] = None,
                 interop: Optional[InterOp] = None,
                 runtime_context: Optional[RuntimeContext] = None,
                 service_context: Optional[ServiceContext] = None,
                 llm_executor: Optional[LLMExecutor] = None,
                 module_manager: Optional[ModuleManager] = None,
                 permission_manager: Optional[PermissionManager] = None,
                 object_factory: Optional[IObjectFactory] = None,
                 plugin_loader: Optional[Callable[[ServiceContext], None]] = None):
        
        # 0. 启动内核引导
        self.registry = registry or Registry()
        # [IES 2.1 Audit] 注册解释器引用到 Registry 以支持类实例化时的字段求值
        self._kernel_token = self.registry.get_kernel_token()
        if self._kernel_token:
             self.registry.set_interpreter(self, self._kernel_token)
        
        # [IES 2.0] 仅在注册表未初始化时执行引导
        if not self.registry.is_initialized:
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
        self.artifact_dict = artifact
        
        # 1. [IES 2.0] 依赖图谱闭合：构造期完成 ServiceContext 组装
        if service_context:
            # 外部注入模式
            self.service_context = service_context
            self._current_context = service_context.runtime_context
        else:
            # 内部组装模式：确保所有依赖在构造期闭合
            self._current_context = runtime_context or RuntimeContextImpl(registry=self.registry)
            interop = interop or InterOpImpl(host_interface=self.host_interface)
            object_factory = object_factory or RuntimeObjectFactory(registry=self.registry)
            permission_manager = permission_manager or PermissionManagerImpl(root_dir)
            llm_executor = llm_executor or LLMExecutorImpl()
            module_manager = module_manager or ModuleManagerImpl(
                interop, 
                artifact=self.artifact_dict,
                interpreter=self,
                root_dir=root_dir,
                object_factory=object_factory
            )
            
            self.service_context = ServiceContextImpl(
                issue_tracker=issue_tracker,
                runtime_context=self._current_context,
                llm_executor=llm_executor,
                module_manager=module_manager,
                interop=interop,
                permission_manager=permission_manager,
                interpreter=self,
                registry=self.registry,
                object_factory=object_factory,
                host_service=None,
                source_provider=self.source_provider,
                compiler=self.compiler,
                debugger=self.debugger
            )
            self.host_service = HostService(self.service_context, self.factory)
            
        # 2. [STAGE 4] 插件加载钩子
        if plugin_loader:
            plugin_loader(self.service_context)
        
        # 3. [STAGE 5] 核心解耦：通过 ArtifactLoader 加载并水化产物
        loader = ArtifactLoader(self.registry)
        loaded = loader.load(self.artifact_dict)
        
        self.node_pool = loaded.node_pool
        self.symbol_pool = loaded.symbol_pool
        self.scope_pool = loaded.scope_pool
        self.type_pool = loaded.type_pool
        self.asset_pool = loaded.asset_pool
        self.entry_module = loaded.entry_module
        self.type_hydrator = loaded.type_hydrator
        
        # 4. 完成用户类的深度水化 (填充方法与字段)
        # 此时 Interpreter 已经初始化完毕，可以安全地创建函数对象
        self.current_module_name = None

        # 4. 完成用户类的深度水化 (填充方法与字段)
        # 此时 Interpreter 已经初始化完毕，可以安全地创建函数对象
        self._hydrate_user_classes(loaded.class_to_node)

        # 4. 设置上下文
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
        self.logical_stack = LogicalCallStack(max_depth=max_call_stack)
        self.current_module_name: Optional[str] = None
        self.strict_mode = strict_mode

        # [IES 4.3] 初始化分片 Handlers
        self.stmt_handler = StmtHandler(self)
        self.expr_handler = ExprHandler(self)
        self.import_handler = ImportHandler(self)

        # [IES 2.0 Optimization] 预先映射访问方法
        self._visitor_cache: Dict[str, Callable] = {}
        self._register_handlers([self, self.stmt_handler, self.expr_handler, self.import_handler])

    def _register_handlers(self, handlers: List[Any]):
        """从所有 Handler 中搜集 visit_ 方法并缓存"""
        for handler in handlers:
            for attr in dir(handler):
                if attr.startswith("visit_"):
                    self._visitor_cache[attr[6:]] = getattr(handler, attr)

    def get_side_table(self, table_name: str, node_uid: str) -> Any:
        """从侧表中获取信息，支持多模块架构"""
        if not self.current_module_name:
            return None
        
        module_data = self.artifact_dict.get("modules", {}).get(self.current_module_name, {})
        if not isinstance(module_data, Mapping):
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
        # [IES 2.0] 仅注入非用户定义的内置类，用户类由 IbClassDef 访问时定义
        for name, ib_class in self.registry.get_all_classes().items():
            if name not in defined_names or force:
                if not getattr(ib_class.descriptor, 'is_user_defined', True):
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
        
        # [NEW] Logical CallStack 追踪 (Module 层级)
        self.logical_stack.push(
            name=f"module:{module_name}",
            local_vars={},
            location=Location(file_path=module_name, line=1, column=0),
            intent_stack=[i.content for i in self.context.get_active_intents()]
        )
        
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
        finally:
            self.logical_stack.pop()
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

    def _hydrate_user_classes(self, class_to_node: Dict[str, Any]):
        """[IES 2.0] STAGE 5 后期：为预水合的类实体填充方法与初始字段定义"""
        old_module = self.current_module_name
        for name, info in class_to_node.items():
            node_uid, module_name = info if isinstance(info, tuple) else (info, "main")
            self.current_module_name = module_name
            
            ib_class = self.registry.get_class(name)
            if not ib_class or not getattr(ib_class.descriptor, 'is_user_defined', False):
                continue
            
            node_data = self.get_node_data(node_uid)
            if not node_data: continue
            
            body = node_data.get("body", [])
            for stmt_uid in body:
                stmt_data = self.get_node_data(stmt_uid)
                if not stmt_data: continue
                
                if stmt_data["_type"] == "IbFunctionDef":
                    sym_uid = self.get_side_table("node_to_symbol", stmt_uid)
                    declared_type = self._resolve_type_from_symbol(sym_uid)
                    ib_class.register_method(stmt_data["name"], IbUserFunction(stmt_uid, self, descriptor=declared_type))
                elif stmt_data["_type"] == "IbLLMFunctionDef":
                    sym_uid = self.get_side_table("node_to_symbol", stmt_uid)
                    declared_type = self._resolve_type_from_symbol(sym_uid)
                    ib_class.register_method(stmt_data["name"], IbLLMFunction(stmt_uid, self.service_context.llm_executor, self, descriptor=declared_type))
                elif stmt_data["_type"] == "IbAssign":
                    # [IES 2.0] 记录初始化节点 UID，延后至执行期或预评估期执行
                    # 这解决了 Context 未闭合导致无法处理复杂表达式的问题
                    val_uid = stmt_data.get("value")
                    for target_uid in stmt_data.get("targets", []):
                        target_name = self._extract_name_id(target_uid)
                        if target_name:
                            # 存储为 (value_node_uid, static_val) 元组
                            # 如果是简单常量，直接装箱作为快照
                            val_data = self.get_node_data(val_uid) if val_uid else None
                            if val_data and val_data["_type"] == "IbConstant":
                                static_val = self.registry.box(self._resolve_value(val_data.get("value")))
                            else:
                                static_val = None
                            
                            ib_class.default_fields[target_name] = (val_uid, static_val)
        
        self.current_module_name = old_module

    def _resolve_type_from_symbol(self, sym_uid: str) -> Optional[Any]:
        """从符号池中解析声明的类型描述符"""
        if not sym_uid or sym_uid not in self.symbol_pool:
            return None
        sym_data = self.symbol_pool[sym_uid]
        type_uid = sym_data.get("type_uid")
        if not type_uid:
            return None
        # 通过 hydrator 获取或重建描述符
        return self.type_hydrator.hydrate(type_uid)

    def _extract_name_id(self, node_uid: str) -> Optional[str]:
        """从表达式节点中提取变量名（处理类型标注等情况）"""
        node_data = self.get_node_data(node_uid)
        if not node_data: return None
        if node_data["_type"] == "IbName":
            return node_data.get("id")
        if node_data["_type"] == "IbTypeAnnotatedExpr":
            return self._extract_name_id(node_data.get("target"))
        return None

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
        
        # [NEW] Logical CallStack 追踪 (Phase 4.3.3)
        loc_data = self.get_side_table("node_to_loc", node_uid)
        loc = None
        if loc_data:
            loc = Location(
                file_path=loc_data.get("file_path"),
                line=loc_data.get("line", 0),
                column=loc_data.get("column", 0)
            )

        # 仅对具有独立作用域或重要执行单元的节点压栈
        pushed_frame = False
        node_type = node_data.get("_type")
        if node_type in ("IbModule", "IbFunctionDef", "IbLLMFunctionDef", "IbClassDef", "IbIntentStmt"):
            self.logical_stack.push(
                name=f"{node_type}:{node_uid}",
                local_vars={}, # 暂时不快照变量，性能考虑
                location=loc,
                intent_stack=[i.content for i in self.context.get_active_intents()]
            )
            pushed_frame = True

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
            visitor = self._visitor_cache.get(node_type, self.generic_visit)
            return visitor(node_uid, node_data)
        except (ReturnException, BreakException, ContinueException, RetryException, ThrownException):
            raise
        except InterpreterError as e:
            # 如果异常还没有位置信息，则尝试补全
            if not e.location:
                e.location = loc
            raise
        except Exception as e:
            raise self._report_error(f"{type(e).__name__}: {str(e)}", node_uid, error_code=RUN_GENERIC_ERROR) from e
        finally:
            if pushed_frame:
                self.logical_stack.pop()
            self.call_stack_depth -= 1
            # [NEW] 自动出栈，确保意图作用域正确恢复
            for _ in range(pushed_count):
                self.context.pop_intent()

    def generic_visit(self, node_uid: str, node_data: Mapping[str, Any]):
        raise self._report_error(f"No visit method implemented for {node_data['_type']}", node_uid, error_code=RUN_GENERIC_ERROR)

    # --- 访问方法实现 ---

    def is_truthy(self, value: IbObject) -> bool:
        """UTS: 使用 to_bool 协议判断真值"""
        res = value.receive('to_bool', [])
        return res.to_native() != 0
