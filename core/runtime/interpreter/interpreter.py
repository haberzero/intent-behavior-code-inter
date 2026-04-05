import os
import re
import json
import sys
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Callable, Union, Mapping
from core.kernel import ast as ast
from core.kernel.issue import (
    InterpreterError, Severity
)
from core.runtime.exceptions import (
    ReturnException, BreakException, ContinueException, ThrownException
)
from core.runtime.host.isolation_policy import IsolationPolicy
from core.base.source_atomic import Location
from core.base.diagnostics.codes import (
    RUN_GENERIC_ERROR, RUN_TYPE_MISMATCH, RUN_UNDEFINED_VARIABLE,
    RUN_LIMIT_EXCEEDED, RUN_CALL_ERROR, RUN_ATTRIBUTE_ERROR
)
from core.runtime.interfaces import (
    Interpreter as InterpreterInterface,
    RuntimeContext, LLMExecutor, InterOp, ModuleManager, ServiceContext, IssueTracker,
    PermissionManager, Scope, SymbolView, ISourceProvider, ICompilerService, IObjectFactory,
    IIbBehavior, IIbIntent, Registry
)
from core.runtime.interpreter.runtime_context import RuntimeContextImpl
from core.runtime.factory import RuntimeObjectFactory
from core.runtime.interpreter.interop import InterOpImpl
from core.runtime.interpreter.module_manager import ModuleManagerImpl
from core.runtime.interpreter.permissions import PermissionManager as PermissionManagerImpl
from core.runtime.objects.kernel import IbObject, IbClass, IbUserFunction, IbFunction, IbNativeFunction, IbLLMFunction, IbDeferredField
from core.kernel.types.descriptors import TypeDescriptor as Type, ListMetadata as ListType, DictMetadata as DictType, ANY_DESCRIPTOR as ANY_TYPE
from core.runtime.objects.builtins import IbInteger, IbString, IbList, IbNone, IbBehavior
from core.runtime.bootstrap.builtin_initializer import initialize_builtin_classes
from core.kernel.registry import KernelRegistry
from core.runtime.host.host_interface import HostInterface
from core.runtime.interfaces import IStackInspector, IExecutionContext
from core.base.diagnostics.debugger import CoreModule, DebugLevel, core_debugger
from core.runtime.objects.intent import IbIntent, IntentMode, IntentRole
from core.runtime.interpreter.intrinsics import IntrinsicManager
from core.runtime.interpreter.ast_view import ReadOnlyNodePool
from core.runtime.loader import ArtifactLoader
from core.runtime.host.service import HostService
from core.runtime.interpreter.constants import OP_MAPPING, UNARY_OP_MAPPING
from core.runtime.interpreter.service_context import ServiceContextImpl
from core.runtime.interpreter.execution_context import ExecutionContextImpl
from core.runtime.interpreter.call_stack import LogicalCallStack, StackFrame
from .llm_result import LLMResult


class Interpreter:
    """
    IBC-Inter 2.0 消息传递解释器。
    彻底转向基于 IbObject 的统一对象模型。
    """
    def get_call_stack_depth(self) -> int:
        return self.call_stack_depth

    def get_active_intents(self) -> List[str]:
        return [i.content for i in self.runtime_context.get_active_intents()]

    def get_instruction_count(self) -> int:
        return self.instruction_count

    def get_captured_intents(self, obj: Any) -> List[str]:
        """ 获取指定对象（如 Behavior）捕获的意图栈内容"""
        if isinstance(obj, IIbBehavior):
            res = []
            for i in obj.captured_intents:
                if isinstance(i, IIbIntent):
                    res.append(i.content)
                else:
                    res.append(str(i))
            return res
        return []

    def sync_state(self, parent_context: RuntimeContext, policy: Dict[str, Any]):
        """从父上下文同步/继承状态，消除 HostService 直接穿透操作"""
        isolation_policy = IsolationPolicy.from_dict(policy) if isinstance(policy, dict) else policy

        if isolation_policy.inherit_intents:
            self.runtime_context.intent_stack = parent_context.intent_stack
            for intent in parent_context.get_global_intents():
                self.runtime_context.set_global_intent(intent)

        if isolation_policy.inherit_variables and isolation_policy.level == "FULL":
            self._sync_variables_from(parent_context)

        if isolation_policy.inherit_classes:
            self._sync_classes_from(parent_context)

        self.debugger.trace(CoreModule.INTERPRETER, DebugLevel.BASIC,
            f"Interpreter state synced from parent context with policy: {policy}")

    def _sync_variables_from(self, parent_context: RuntimeContext):
        """从父上下文同步变量"""
        parent_scope = parent_context.current_scope
        current_scope = self.runtime_context.current_scope
        for name, symbol in parent_scope._symbols.items():
            if not name.startswith("__"):
                current_scope.define(name, symbol.descriptor, is_const=symbol.is_const, force=True)

    def _sync_classes_from(self, parent_context: RuntimeContext):
        """ 从父上下文同步类定义"""
        pass


    # TODO: 怀疑此处 instance_id: str = "main"  这一行有代码异味。MVP Demo 阶段暂不深究
    def __init__(self, issue_tracker: IssueTracker,
                 output_callback: Optional[Callable[[str], None]] = None, 
                 input_callback: Optional[Callable[[str], str]] = None, 
                 max_instructions: int = 100000000, 
                 max_call_stack: int = 100,
                 artifact: Optional[Any] = None,
                 host_interface: Optional[HostInterface] = None,
                 debugger: Optional[Any] = None,
                 root_dir: str = ".",
                 strict_mode: bool = True,
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
                 plugin_loader: Optional[Callable[[ServiceContext], None]] = None,
                 kernel_token: Optional[Any] = None,
                 instance_id: str = "main",
                 orchestrator: Optional[Any] = None):
        
        # 0. 启动内核引导
        self._registry = registry or KernelRegistry()
        self._kernel_token = kernel_token
        self.instance_id = instance_id or f"inst_{id(self)}"
        
        # 引入对象工厂
        object_factory = object_factory or RuntimeObjectFactory(registry=self.registry)

        # 创建执行上下文数据容器，剥离状态与逻辑 (组合代替继承)
        self._execution_context = ExecutionContextImpl(
            registry=self._registry,
            factory=object_factory,
            visit_callback=self.visit,
            get_node_data_callback=self.get_node_data,
            get_side_table_callback=self.get_side_table,
            push_stack_callback=self.push_stack,
            pop_stack_callback=self.pop_stack,
            get_instruction_count_callback=lambda: self.instruction_count,
            get_captured_intents_callback=self.get_captured_intents,
            is_truthy_callback=self.is_truthy,
            resolve_type_from_symbol_callback=self._resolve_type_from_symbol,
            extract_name_id_callback=self._extract_name_id,
            resolve_value_callback=self._resolve_value,
            strict_mode=strict_mode
        )

        # 注册执行上下文引用到 Registry，底层仅持有该容器
        self._kernel_token = self._registry.get_kernel_token()
        if self._kernel_token:
             self._registry.set_execution_context(self._execution_context, self._kernel_token)
        
        # 仅在注册表未初始化时执行引导
        if not self.registry.is_initialized:
            initialize_builtin_classes(self.registry)
            
        # 加载内置函数插件 (Intrinsics)
        self.intrinsic_manager = IntrinsicManager(self.registry)
        # load_defaults 将在 ServiceContext 准备好后调用
        
        self.issue_tracker = issue_tracker
        self.host_interface = host_interface or HostInterface()
        self.debugger = debugger or core_debugger
        self.source_provider = source_provider
        self.compiler = compiler
        self.factory = factory
        self.artifact_dict = artifact
        if artifact:
            self.node_pool = artifact.get("pools", {}).get("nodes", {})
        
        # 1. 依赖图谱闭合：构造期完成 ServiceContext 组装
        # 核心：确保服务组件仅持有必要的数据结构，严禁穿透持有 Interpreter
        self.runtime_context = runtime_context or RuntimeContextImpl(registry=self.registry)
        
        if service_context:
            # 外部注入模式
            self.service_context = service_context
            self._execution_context.module_manager = self.service_context.module_manager
        else:
            # 内部组装模式：确保所有依赖在构造期闭合
            interop = interop or InterOpImpl(host_interface=self.host_interface)
            # object_factory 已经在前面初始化
            permission_manager = permission_manager or PermissionManagerImpl(root_dir)
            
            # 初始化 LLMExecutor，注入最小数据依赖
            llm_executor = llm_executor or object_factory.create_llm_executor(
                service_context=None, # 此时 ServiceContext 尚未完全就绪，将在后续水化
                execution_context=self._execution_context
            )
            
            # 初始化 ModuleManager，注入最小依赖与回调
            module_manager = module_manager or ModuleManagerImpl(
                interop=interop, 
                registry=self.registry,
                object_factory=object_factory,
                execute_module_callback=self.execute_module,
                artifact=self.artifact_dict,
                root_dir=root_dir
            )
            
            # 宿主能力由注入的 ServiceContext 提供，不再主动实例化 HostService
            self.service_context = ServiceContextImpl(
                issue_tracker=issue_tracker,
                llm_executor=llm_executor,
                module_manager=module_manager,
                interop=interop,
                permission_manager=permission_manager,
                object_factory=object_factory,
                registry=self.registry,
                host_service=None, # 将由外界注入或通过 scheduler 获取
                source_provider=self.source_provider,
                orchestrator=kwargs.get('orchestrator', None) if 'kwargs' in locals() else None,
                debugger=self.debugger,
                output_callback=output_callback,
                input_callback=input_callback,
                scheduler=None, # 占位，由 Engine 统一装配
                capability_registry=None, # 占位，由 Engine 统一装配
                interpreter=self # 注入解释器实例引用
            )
            self._execution_context.module_manager = self.service_context.module_manager
            
            # 完成延迟水化
            if hasattr(llm_executor, 'hydrate'):
                llm_executor.hydrate(self.service_context)
            
        # 2.  加载内置函数 (不再穿透持有 Interpreter)
        self.intrinsic_manager.load_defaults(self._execution_context, self.service_context)

        # 3. [STAGE 4] 插件加载钩子
        if plugin_loader:
            plugin_loader(self.service_context, self._execution_context, self.intrinsic_manager)
        
        # 3. [STAGE 5] 核心解耦：通过 ArtifactLoader 加载并水化产物
        loader = ArtifactLoader(self.registry)
        loaded = loader.load(self.artifact_dict)
        
        self.node_pool = loaded.node_pool
        self.symbol_pool = loaded.symbol_pool
        self.scope_pool = loaded.scope_pool
        self.type_pool = loaded.type_pool
        self.asset_pool = loaded.asset_pool
        self.entry_module = loaded.entry_module
        self.type_hydrator = loaded.artifact_rehydrator
        
        # 同步池引用到 ExecutionContext 数据容器
        self._execution_context.node_pool = self.node_pool
        self._execution_context.symbol_pool = self.symbol_pool
        self._execution_context.scope_pool = self.scope_pool
        self._execution_context.type_pool = self.type_pool
        self._execution_context.asset_pool = self.asset_pool
        
        # 4. 完成用户类的深度水化 (填充方法与字段)
        # 此时 Interpreter 已经初始化完毕，可以安全地创建函数对象
        self.current_module_name = None

        # 2. 注入全局符号与类定义
        self._hydrate_user_classes(loaded.class_to_node)
        
        # 3.  STAGE 6: 预评估类字段 (Late Evaluation)
        if self._kernel_token:
            self.registry.set_state_level(RegistrationState.STAGE_6_PRE_EVAL.value, self._kernel_token)
        else:
            # 在某些脱离 Engine 的测试环境下，如果没有令牌，系统将无法正确追踪状态流转
            self.debugger.trace(CoreModule.INTERPRETER, DebugLevel.BASIC, 
                "Warning: Kernel token missing in Interpreter. STAGE 6 transition skipped.")
            
        self._pre_evaluate_user_classes()

        # 4. 设置上下文
        self.setup_context(self.runtime_context)

        # 运行限制
        self.max_instructions = max_instructions
        self.instruction_count = 0
        
        # 递归深度安全校验
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
        self._execution_context.logical_stack = LogicalCallStack(max_depth=max_call_stack)
        self.strict_mode = strict_mode

        # 初始化分片 Handlers (通过工厂解耦)
        handlers = object_factory.create_handlers(self.service_context, self._execution_context)
        self.stmt_handler = handlers[0]
        self.expr_handler = handlers[1]
        self.import_handler = handlers[2]

        # 预先映射访问方法
        self._visitor_cache: Dict[str, Callable] = {}
        self._register_handlers([self] + handlers)

    def _register_handlers(self, handlers: List[Any]):
        """从所有 Handler 中搜集 visit_ 方法并缓存"""
        for handler in handlers:
            for attr in dir(handler):
                if attr.startswith("visit_"):
                    self._visitor_cache[attr[6:]] = getattr(handler, attr)

    @property
    def current_module_name(self) -> Optional[str]:
        return self._execution_context.current_module_name

    @current_module_name.setter
    def current_module_name(self, value: Optional[str]):
        self._execution_context.current_module_name = value

    @property
    def registry(self) -> Registry:
        return self._registry

    @property
    def execution_context(self) -> IExecutionContext:
        return self._execution_context

    @property
    def symbol_view(self) -> SymbolView:
        return self.runtime_context.get_symbol_view()

    @property
    def runtime_context(self) -> RuntimeContext:
        return self._execution_context.runtime_context

    @runtime_context.setter
    def runtime_context(self, value: RuntimeContext):
        self._execution_context.runtime_context = value

    @property
    def node_pool(self) -> Mapping[str, Any]:
        return self._execution_context.node_pool

    @node_pool.setter
    def node_pool(self, value: Mapping[str, Any]):
        self._execution_context.node_pool = value

    @property
    def logical_stack(self) -> LogicalCallStack:
        return self._execution_context.logical_stack

    @property
    def stack_inspector(self) -> IStackInspector:
        return self._execution_context

    def get_side_table(self, table_name: str, node_uid: str) -> Any:
        """从当前活跃模块的侧表中获取数据"""
        module_name = self.current_module_name or self.entry_module
        if not module_name:
            return None
            
        module_data = self.artifact_dict.get("modules", {}).get(module_name, {})
        if not isinstance(module_data, Mapping):
            return None
            
        side_tables = module_data.get("side_tables", {})
        table = side_tables.get(table_name, {})
        val = table.get(node_uid)
        
        # 自动重水化类型引用
        if table_name == "node_to_type" and isinstance(val, str):
            return self.type_hydrator.hydrate(val)
            
        return val

    def push_stack(self, name: str, location: Optional[Location] = None, is_user_function: bool = False, **kwargs):
        """向逻辑调用栈压入一帧"""
        self.logical_stack.push(
            name=name,
            local_vars={}, # 暂时不快照变量，性能考虑
            location=location,
            intent_stack=[i.content for i in self.runtime_context.get_active_intents()],
            is_user_function=is_user_function,
            **kwargs
        )

    def pop_stack(self):
        """从逻辑调用栈弹出最后一帧"""
        self.logical_stack.pop()

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

    def setup_context(self, context: RuntimeContext, force: bool = False):
        """为 Context 注入基础内置变量 (Public API)"""
        # 使用私有属性访问以仅检查当前作用域，避免与后续 bootstrap 冲突
        global_symbols = context.global_scope.get_all_symbols()
        defined_names = set(global_symbols.keys())
        
        # 内置功能插件化重绑定
        self.intrinsic_manager.rebind(self, context)
        
        # 注入内置类 (int, str, float, list, dict 等)
        # 仅注入非用户定义的内置类，用户类由 IbClassDef 访问时定义
        for name, ib_class in self.registry.get_all_classes().items():
            if name not in defined_names or force:
                if not getattr(ib_class.descriptor, 'is_user_defined', True):
                    # 注入时带上稳定的内置符号 UID，与编译器对齐
                    context.define_variable(name, ib_class, is_const=True, force=force, uid=f"builtin:{name}")
                    defined_names.add(name)

    def interpret(self, module_uid: str) -> IbObject:
        """从模块 UID 开始执行"""
        return self.execute_module(module_uid)

    def run(self) -> IbObject:
        """从入口模块开始执行完整的项目"""
        try:
            if not self.entry_module:
                return self.registry.get_none()

            module_data = self.artifact_dict.get("modules", {}).get(self.entry_module)
            if not module_data:
                return self.registry.get_none()

            result = self.execute_module(module_data["root_node_uid"], module_name=self.entry_module)
            return result if result is not None else self.registry.get_none()
        except Exception as e:
            if not isinstance(e, InterpreterError):
                import traceback
                traceback.print_exc()
            raise e

    def execute_module(self, module_uid: str, module_name: str = "main", scope: Optional[Scope] = None) -> IbObject:
        self.debugger.trace(CoreModule.INTERPRETER, DebugLevel.BASIC, f"Starting execution of module {module_name} ({module_uid})...")
        
        old_module = self.current_module_name
        self.current_module_name = module_name
        
        module_data = self.get_node_data(module_uid)
        if not module_data:
            raise self._report_error(f"Module UID {module_uid} not found.")
        
        if not isinstance(module_data, Mapping):
            raise self._report_error(f"Module data for {module_uid} is not a dict: {type(module_data)} -> {module_data}")

        old_context = self.runtime_context
        if scope:
             # 创建新 Context 并绑定 Scope
             new_ctx = RuntimeContextImpl(initial_scope=scope, registry=self.registry)
             self.runtime_context = new_ctx
             # [BugFix] 修复内置函数（如 print）在模块切换时丢失的问题
             self.setup_context(self.runtime_context)

        self.instruction_count = 0
        result = self.registry.get_none()
        
        # 注入内置路径变量
        loc_data = self.get_side_table("node_to_loc", module_uid)
        if not loc_data:
             raise self._report_error(f"Critical: Location metadata missing for module {module_uid}. Compiled artifact might be corrupted.", module_uid)
        
        loc = Location(
            file_path=loc_data.get("file_path"),
            line=loc_data.get("line", 1),
            column=loc_data.get("column", 0)
        )

        # Logical CallStack 追踪 (Module 层级)
        self.logical_stack.push(
            name=f"module:{module_name}",
            local_vars={},
            location=loc,
            intent_stack=[i.content for i in self.runtime_context.get_active_intents()]
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
            self.runtime_context = old_context
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
        """处理外部资产引用的解析"""
        # 支持 dict 和 ReadOnlyNodePool (Mapping)
        if hasattr(val, "get") and val.get("_type") == "ext_ref":
            uid = val.get("uid")
            if uid in self.asset_pool:
                return self.asset_pool[uid]
            # 如果资产池中没有，可能是编译器外置但还没注入
            return f"__EXT_ASSET_MISSING_{uid}__"
        return val

    def _pre_evaluate_user_classes(self):
        """预评估：在 STAGE 6 启动前，尝试评估类中定义的复杂默认字段值。"""
        old_module = self.current_module_name
        for name, ib_class in self.registry.get_all_classes().items():
            if not getattr(ib_class.descriptor, 'is_user_defined', False):
                continue
            
            # 遍历所有默认字段并尝试预求值
            for field_name, val_info in ib_class.default_fields.items():
                if not isinstance(val_info, IbDeferredField) or val_info.static_val is not None:
                    continue
                
                # 尝试通过 visit 动态评估复杂表达式 (如 1+2, "hello".upper())
                # 关键修复：设置正确的模块上下文，确保符号查找正确
                self.current_module_name = val_info.module_name
                try:
                    evaluated = self.visit(val_info.val_uid)
                    val_info.static_val = evaluated
                except Exception:
                    # 预评估失败是允许的，留待实例化时 (instantiate) 再次尝试
                    pass
        
        self.current_module_name = old_module

    def _hydrate_user_classes(self, class_to_node: Dict[str, Any]):
        """ STAGE 5 后期：为预水合的类实体填充方法与初始字段定义"""
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
                    ib_class.register_method(stmt_data["name"], IbUserFunction(stmt_uid, self._execution_context, descriptor=declared_type))
                elif stmt_data["_type"] == "IbLLMFunctionDef":
                    sym_uid = self.get_side_table("node_to_symbol", stmt_uid)
                    declared_type = self._resolve_type_from_symbol(sym_uid)
                    ib_class.register_method(stmt_data["name"], IbLLMFunction(stmt_uid, self.service_context.llm_executor, self._execution_context, descriptor=declared_type))
                elif stmt_data["_type"] == "IbAssign":
                    # 使用 IbDeferredField 统一管理
                    val_uid = stmt_data.get("value")
                    for target_uid in stmt_data.get("targets", []):
                        target_name = self._extract_name_id(target_uid)
                        if target_name:
                            val_data = self.get_node_data(val_uid) if val_uid else None
                            static_val = None
                            if val_data and val_data["_type"] == "IbConstant":
                                static_val = self.registry.box(self._resolve_value(val_data.get("value")))
                            
                            ib_class.default_fields[target_name] = IbDeferredField(
                                val_uid=val_uid, 
                                static_val=static_val, 
                                module_name=module_name
                            )
        
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

    def _get_location(self, node_uid: str) -> Optional[Location]:
        """从 side_tables 获取节点的位置信息"""
        loc_data = self.get_side_table("node_to_loc", node_uid)
        if not loc_data:
            return None
        return Location(
            file_path=loc_data.get("file_path"),
            line=loc_data.get("line", 0),
            column=loc_data.get("column", 0)
        )

    def visit(self, node_uid: Union[str, Any], module_name: Optional[str] = None, bypass_protection: bool = False) -> IbObject:
        """核心评估逻辑：分发 AST 节点到相应的 Handler 处理"""
        if node_uid is None:
            return self.registry.get_none()

        # 1. 影子执行拦截逻辑：检查侧表看该节点是否被 llmexcept 保护
        if not bypass_protection and isinstance(node_uid, str):
            handler_uid = self.get_side_table("node_protection", node_uid)
            if handler_uid:
                # 将执行权交给处理节点，由它来驱动 target 的执行
                # 注意：必须传入 bypass_protection=True，否则处理器节点也会被拦截跳过
                return self.visit(handler_uid, bypass_protection=True)

        # 如果指定了模块，则临时切换上下文进行求值 (Lexical Scope Support)
        old_module = self.current_module_name
        if module_name and module_name != old_module:
            self.current_module_name = module_name

        try:
            # 处理字面量或裸 UID
            if not isinstance(node_uid, str):
                if hasattr(node_uid, 'uid'):
                    node_uid = node_uid.uid
                else:
                    if isinstance(node_uid, (int, float, bool, dict)):
                        return self.registry.box(self._resolve_value(node_uid))
                    return self.registry.get_none()

            if node_uid not in self.node_pool:
                return self.registry.box(self._resolve_value(node_uid))

            node_data = self.get_node_data(node_uid)
            if not node_data:
                return self.registry.get_none()

            self.instruction_count += 1
            if self.instruction_count > self.max_instructions:
                raise self._report_error("Execution limit exceeded", node_uid, error_code=RUN_LIMIT_EXCEEDED)

            if self.call_stack_depth >= self.max_call_stack:
                 raise self._report_error("Recursion depth exceeded", node_uid, error_code=RUN_LIMIT_EXCEEDED)

            self.call_stack_depth += 1
            loc = self._get_location(node_uid)

            # 识别具有独立作用域的节点 (基于元数据特性驱动)
            pushed_frame = False
            node_type = node_data.get("_type")

            if self._is_scope_defining(node_type, node_data):
                self.push_stack(name=f"{node_type}:{node_uid}", location=loc)
                pushed_frame = True

            # 意图自动化拦截：从侧表获取绑定意图并自动压栈，实现“语义涂抹”自动化
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
                        self.runtime_context.push_intent(intent)
                        pushed_count += 1

            try:
                node_type = node_data.get("_type")

                # 2. 避免处理器节点被重复执行：
                # 如果当前节点是一个 llmexcept 处理器，且我们不是通过影子执行逻辑（bypass_protection=True）进入的，
                # 则跳过它，因为它已经被它的 target 触发执行过了。
                if not bypass_protection and node_type == "IbLLMExceptionalStmt":
                    return self.registry.get_none()

                visitor = self._visitor_cache.get(node_type, self.generic_visit)
                result = visitor(node_uid, node_data)
                
                # [Result Mode] 自动拦截不确定性结果
                if isinstance(result, LLMResult):
                    self.runtime_context.set_last_llm_result(result)
                    if result.is_uncertain:
                        # 对于不确定的结果，我们返回 None。
                        # 上层逻辑（如 IbAssign）会根据 last_llm_result.is_uncertain 决定是否中断。
                        return self.registry.get_none()
                    return result.value # 返回解包后的 IbObject
                
                return result
            except (ReturnException, BreakException, ContinueException, ThrownException):
                raise
            except InterpreterError as e:
                if not e.location:
                    e.location = loc
                raise
            except Exception as e:
                raise self._report_error(f"{type(e).__name__}: {str(e)}", node_uid, error_code=RUN_GENERIC_ERROR) from e
            finally:
                if pushed_frame:
                    self.logical_stack.pop()
                self.call_stack_depth -= 1
                # 自动出栈，确保意图作用域正确恢复
                for _ in range(pushed_count):
                    self.runtime_context.pop_intent()
        finally:
            # 恢复之前的模块上下文
            self.current_module_name = old_module

    def _is_scope_defining(self, node_type: str, node_data: Optional[Mapping[str, Any]] = None) -> bool:
        """判断 AST 节点是否具有独立逻辑作用域。完全元数据驱动。"""
        # 优先检查节点数据中是否带有分析器生成的标记
        if node_data and node_data.get("_is_scope"):
            return True
            
        return False

    def generic_visit(self, node_uid: str, node_data: Mapping[str, Any]):
        raise self._report_error(f"No visit method implemented for {node_data['_type']}", node_uid, error_code=RUN_GENERIC_ERROR)

    # --- 访问方法实现 ---

    def is_truthy(self, value: IbObject) -> bool:
        """UTS: 使用 to_bool 协议判断真值"""
        res = value.receive('to_bool', [])
        return res.to_native() != 0
