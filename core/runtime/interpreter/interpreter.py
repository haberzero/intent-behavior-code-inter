import re
import json
import traceback
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Callable, Union, Mapping

# =============================================================================
# 架构边界说明：Interpreter = 纯协调器
# =============================================================================
# Interpreter 是单个 IBCI 执行会话的隔离单元。
# 职责：接受已编译的 Artifact，在独立的运行时上下文中执行它，并返回结果。
#
# 最终文件结构：
# core/runtime/
# ├── vm/
# │   ├── handlers.py       ← 唯一 AST → 执行映射（43+ CPS handlers）
# │   ├── vm_executor.py    ← CPS 调度循环（无 fallback_visit，无 assign_to_target）
# │   └── task.py           ← Signal / UnhandledSignal（控制流数据对象）
# ├── interpreter/
# │   └── interpreter.py    ← 纯协调器（execute_module, STAGE 1-5 初始化）
# ├── objects/
# │   ├── kernel.py         ← IbUserFunction.call() 调用 vm.run_body()
# │   └── primitives/      ← IbFnCallable.call() 调用 vm.run()
# └── exceptions.py         ← 只剩 ThrownException + 基础架构异常
#
# VMExecutor CPS 调度循环是唯一的执行入口。
# Signal 数据对象是唯一的 IBCI 控制流载体。
# =============================================================================
from core.kernel import ast as ast
from core.kernel.issue import (
    InterpreterError, Severity
)
from core.base.source_atomic import Location
from core.base.uid import intrinsic_uid
from core.base.diagnostics.codes import (
    RUN_GENERIC_ERROR, RUN_LIMIT_EXCEEDED, KDIAG_RUNTIME_STAGE_SKIP, KDIAG_RUNTIME_PRE_EVAL_FALLBACK
)
from core.runtime.observability.diagnostics import kernel_diagnostic
from core.runtime.interfaces import (
    Interpreter as InterpreterInterface,
    RuntimeContext, LLMExecutor, InterOp, ModuleManager, ServiceContext, IssueTracker,
    PermissionManager, Scope, SymbolView, ISourceProvider, ICompilerService, IObjectFactory,
    Registry
)
from core.runtime.interpreter.runtime_context import RuntimeContextImpl
from core.runtime.shared.op_constants import OP_MAPPING, UNARY_OP_MAPPING
from core.runtime.factory import RuntimeObjectFactory
from core.runtime.interpreter.interop import InterOpImpl
from core.runtime.interpreter.module_manager import ModuleManagerImpl
from core.runtime.interpreter.permissions import PermissionManager as PermissionManagerImpl
from core.runtime.objects.kernel import IbObject, IbClass, IbUserFunction, IbFunction, IbNativeFunction, IbClassField, IbValue, IbLLMCallResult, IbLLMUncertain
from core.runtime.objects.kernel.host_class import HostClassBinding
from core.runtime.bootstrap.primitive_initializer import initialize_primitive_classes
from core.kernel.registry import KernelRegistry
from core.kernel.host_interface import HostInterface
from core.kernel.spec.member import MethodMemberSpec
from core.kernel.spec.type_ref import TypeRef
from core.runtime.interfaces import IStackInspector, IExecutionContext
from core.runtime.objects.intent import IbIntent, IntentMode, IntentRole
from core.runtime.interpreter.intrinsics import IntrinsicManager
from core.runtime.interpreter.ast_view import ReadOnlyNodePool
from core.runtime.loader import ArtifactLoader
from core.runtime.host.service import HostService
from core.runtime.frame import (
    set_current_frame, reset_current_frame,
    set_current_execution_context, reset_current_execution_context,
    get_current_execution_context,
)
from core.runtime.interpreter.service_context import ServiceContextImpl
from core.runtime.interpreter.execution_context import ExecutionContextImpl
from core.runtime.interpreter.call_stack import LogicalCallStack, StackFrame
from core.base.enums import Provenance, RegistrationState
from core.runtime.shared.signals import UnhandledSignal


def _auto_init_impl(self_obj, *args):
    """auto-init 共享实现（B4 声明化——不再生成运行时闭包）。

    字段名清单从 ``ib_cls.auto_init_fields`` 读取（水化期声明注册）；参数
    数量校验由调用方（``_init_expected_arity``，spec.members['__init__']
    成员表单一权威）承担——此处仅执行字段写入（zip 按声明字段数消费，
    多余实参已被调用方拦截）。
    """
    field_names = getattr(self_obj.ib_class, "auto_init_fields", None) or []
    for fname, val in zip(field_names, args):
        self_obj.fields[fname] = self_obj.ib_class._wrap_field_value(fname, val)
    return self_obj.ib_class.registry.get_none()


class Interpreter:
    """
    IBC-Inter 2.0 消息传递解释器。
    彻底转向基于 IbObject 的统一对象模型。
    """
    # 运算符 dunder 方法集合（从 op_constants 派生，单点收敛）。
    _OPERATOR_METHODS: Optional[set] = None

    def get_call_stack_depth(self) -> int:
        return self.logical_stack.depth if self.logical_stack else 0

    def get_active_intents(self) -> List[str]:
        return [i.content for i in self.runtime_context.get_active_intents()]

    def get_captured_intents(self, obj: Any) -> List[str]:
        """ 获取指定对象（如 Behavior）捕获的意图栈内容。

        ``obj.captured_intents`` 现在协议为 ``None`` 或 ``IbIntentContext`` 实例
        （详见 ``core.runtime.objects.primitives.IbBehavior``）。
        """
        if not (isinstance(obj, IbValue) and obj.ib_class.name == "behavior"):
            return []
        ci = obj.captured_intents
        if ci is None:
            return []
        return [i.content if isinstance(i, IbIntent) else str(i)
                for i in ci.get_active_intents()]


    # 注意：instance_id 默认值 "main" 在多解释器场景下存在碰撞风险
    def __init__(self, issue_tracker: IssueTracker,
                 output_callback: Optional[Callable[[str], None]] = None,
                 input_callback: Optional[Callable[[str], str]] = None,
                 max_call_stack: int = 1000,
                 artifact: Optional[Any] = None,
                 host_interface: Optional[HostInterface] = None,
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
                  entry_file: str = None,
                  entry_dir: str = None,
                  project_root: str = None):
        
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
            get_node_data_callback=self.get_node_data,
            get_side_table_callback=self.get_side_table,
            push_stack_callback=self.push_stack,
            pop_stack_callback=self.pop_stack,
            get_captured_intents_callback=self.get_captured_intents,
            is_truthy_callback=self.is_truthy,
            resolve_type_from_symbol_callback=self._resolve_type_from_symbol,
            extract_name_id_callback=self._extract_name_id,
            resolve_value_callback=self._resolve_value,
            strict_mode=strict_mode,
            entry_file=entry_file,
            entry_dir=entry_dir,
            project_root=project_root
        )

        # 注册执行上下文引用到 Registry，底层仅持有该容器
        # 如果 kernel_token 已经由调用方（如 Engine）传入，则优先使用，避免重复调用
        # get_kernel_token()（该方法是一次性的，第二次调用会返回 None）。
        if not self._kernel_token:
            self._kernel_token = self._registry.get_kernel_token()
        if self._kernel_token:
             self._registry.set_execution_context(self._execution_context, self._kernel_token)
        
        # 仅在注册表未初始化时执行引导
        if not self.registry.is_initialized:
            initialize_primitive_classes(self.registry)
            
        # 加载内置函数插件 (Intrinsics)
        self.intrinsic_manager = IntrinsicManager(self.registry)
        # load_defaults 将在 ServiceContext 准备好后调用
        
        self.issue_tracker = issue_tracker
        self.host_interface = host_interface or HostInterface()
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
            self._execution_context.permission_manager = self.service_context.permission_manager
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
                output_callback=output_callback,
                input_callback=input_callback,
                scheduler=None, # 占位，由 Engine 统一装配
                capability_registry=None, # 占位，由 Engine 统一装配
                interpreter=self # 注入解释器实例引用
            )
            self._execution_context.module_manager = self.service_context.module_manager
            self._execution_context.permission_manager = self.service_context.permission_manager
            
            # 完成延迟水化
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
        # 宿主类型绑定（bind class）先注册：impl 方法水化（_hydrate_user_classes
        # 内）经 registry.get_class 查宿主类目标，宿主类须先于 impl 水化存在。
        self._hydrate_host_classes()
        self._hydrate_user_classes(loaded.class_to_node, loaded.impl_blocks)
        
        # 3.  STAGE 6: 预评估类字段 (Late Evaluation)
        if self._kernel_token:
            self.registry.set_state_level(RegistrationState.STAGE_6_PRE_EVAL.value, self._kernel_token)
        else:
            # 在某些脱离 Engine 的测试环境下，如果没有令牌，系统将无法正确追踪状态流转
            kernel_diagnostic(
                code=KDIAG_RUNTIME_STAGE_SKIP,
                detail={},
                message="Warning: Kernel token missing in Interpreter. STAGE 6 transition skipped.",
            )

        self.strict_mode = strict_mode

        self.max_call_stack = max_call_stack
        self._execution_context.logical_stack = LogicalCallStack(max_depth=max_call_stack)

        # 4. 设置上下文（含内置变量）
        self.setup_context(self.runtime_context)

        # IntentStack 与 runtime_context 关联
        intent_stack = self.registry.get_intrinsic_instance("IntentStack")
        if intent_stack and hasattr(intent_stack, 'set_runtime_context'):
            intent_stack.set_runtime_context(self.runtime_context)

        # VMExecutor 主路径——延迟初始化
        # （ExecutionContext 必须先就绪；首个 execute_module() 调用时
        # 通过 ``_get_vm_executor()`` 实例化）
        self._vm_executor: Optional[Any] = None

        # 5. 预评估用户类字段 (STAGE 6)
        self._pre_evaluate_user_classes()

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

    def get_side_table(self, table_name: str, node_uid: str, module: Optional[str] = None) -> Any:
        """从侧表中获取数据（module 感知）。

        ``module`` 参数由调用方 EC 提供（``ExecutionContextImpl.get_side_table``
        透传自身 ``current_module_name``）——线程 worker 内 task_ec 的
        current_module_name 是任务本地值（``_shared._vm_call_user_function``
        已切换），侧表查询以调用方 EC 为准，不再读 interpreter 共享模块状态
        （读 ``self.current_module_name`` 会忽略任务本地切换，被 import 模块
        方法体在 worker 内查空报 Symbol UID missing）。
        """
        module_name = module or self.current_module_name or self.entry_module
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
            "current_module_name": self.current_module_name,
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
                if getattr(ib_class.spec, 'provenance', Provenance.USER_DEFINED) != Provenance.USER_DEFINED:
                    # 注入时带上稳定的内核原生符号 UID，与编译器对齐
                    context.define_variable(name, ib_class, is_const=True, force=force, uid=intrinsic_uid(name))
                    defined_names.add(name)

    def interpret(self, module_uid: str) -> IbObject:
        """从模块 UID 开始执行"""
        return self.execute_module(module_uid)

    def run(self) -> IbObject:
        """从入口模块开始执行完整的项目"""
        _token = set_current_frame(self.runtime_context)
        _ec_token = set_current_execution_context(self._execution_context)
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
                traceback.print_exc()
            raise e
        finally:
            reset_current_execution_context(_ec_token)
            reset_current_frame(_token)

    def _get_vm_executor(self):
        """延迟构造并返回单例 VMExecutor。

        VMExecutor 在 ``execute_module()`` 与 ``IbUserFunction.call()`` 中作为
        主路径调度器使用（覆盖全部 43 种 AST 节点类型）。

        构造完成后立即把引用写入 ``ExecutionContext.vm_executor``，
        使 ``IbUserFunction.call()`` 等持有 ExecutionContext 的代码不再需要
        通过 ``getattr(self.context, "_interpreter", ...)._get_vm_executor()``
        三级穿透查找。
        """
        if self._vm_executor is None:
            from core.runtime.vm.vm_executor import VMExecutor  # 局部导入：打破 vm ↔ interpreter 循环依赖
            self._vm_executor = VMExecutor(
                self._execution_context, interpreter=self
            )
            # 把 VMExecutor 直接绑定到 ExecutionContext，供下游调用方
            # 通过 ``self.context.vm_executor`` 直接获取。
            self._execution_context.vm_executor = self._vm_executor
        return self._vm_executor

    def execute_module(self, module_uid: str, module_name: str = "main", scope: Optional[Scope] = None) -> IbObject:
        _frame_token = set_current_frame(self.runtime_context)
        _ec_token = set_current_execution_context(self._execution_context)

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
            # 通过 ``VMExecutor.run_body()`` 统一驱动顶层语句的 CPS 执行。
            vm = self._get_vm_executor()
            body = module_data.get("body", [])
            result = vm.run_body(body)
            return result
        except InterpreterError:
            raise
        except UnhandledSignal:
            raise self._report_error("Control flow statement used outside of function or loop.", error_code=RUN_GENERIC_ERROR)
        finally:
            self.logical_stack.pop()
            self.runtime_context = old_context
            self.current_module_name = old_module
            reset_current_execution_context(_ec_token)
            reset_current_frame(_frame_token)

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
        """预评估：在 STAGE 6 启动前，尝试评估类中定义的复杂默认字段值。

        性质：预评估是**尽力而为的优化**（静态快照
        预求值减少实例化期求值）——非任务内同步重入（执行于模块启动前，宿主
        侧无调度器上下文，"任务内重入"不适用）；失败属正常预期（复杂
        表达式依赖运行期状态无法预求值），实例化路径（_eval_field_defaults）
        会完整重试且 fail-fast——故此处失败回退是职责分离 fallback，但按
        可观测性纪律记录诊断（不静默）。
        """
        old_module = self.current_module_name
        # Bug C 修复：预评估失败不应污染 issue_tracker（导致 STAGE 7 契约校验误报错误）。
        # 保存当前错误计数，预评估完成后恢复（预评估是尽力而为优化，其失败
        # 诊断不得影响正式编译诊断）。
        saved_error_count = self.issue_tracker._error_count
        saved_diag_count = len(self.issue_tracker._diagnostics)

        for name, ib_class in self.registry.get_all_classes().items():
            if getattr(ib_class.spec, 'provenance', Provenance.USER_DEFINED) != Provenance.USER_DEFINED:
                continue

            # 遍历所有默认字段并尝试预求值
            for field_name, val_info in ib_class.default_fields.items():
                if not isinstance(val_info, IbClassField) or val_info.static_val is not None:
                    continue

                # 通过 VMExecutor（CPS 主路径）预求值复杂表达式 (如 1+2, "hello".upper())。
                # 关键修复：设置正确的模块上下文，确保符号查找正确。
                # 使用 _get_vm_executor().run() 预求值（CPS 主路径）。
                self.current_module_name = val_info.module_name
                try:
                    evaluated = self._get_vm_executor().run(val_info.val_uid)
                    val_info.static_val = evaluated
                except Exception as e:
                    # 预评估失败是允许的，留待实例化时 (instantiate) 再次尝试
                    # （职责分离 fallback——实例化路径完整重试 + fail-fast）。
                    # 记录诊断（observability 门控，不静默、不刷屏）。
                    kernel_diagnostic(
                        code=KDIAG_RUNTIME_PRE_EVAL_FALLBACK,
                        detail={
                            "class": name,
                            "field": field_name,
                            "error": repr(e),
                        },
                        message=(
                            f"Pre-evaluation of field default '{name}.{field_name}' "
                            f"failed; will evaluate at instantiation: {e!r}"
                        ),
                    )

        # 恢复 issue_tracker 状态：预评估期间产生的任何错误都是误报
        self.issue_tracker._error_count = saved_error_count
        self.issue_tracker._diagnostics = self.issue_tracker._diagnostics[:saved_diag_count]

        self.current_module_name = old_module

    def _hydrate_host_classes(self):
        """STAGE 5：注册宿主类型绑定（bind class）为运行期类。

        扫描 artifact 各模块根 body 中的 ``IbHostImport`` 节点，按其
        ``bind class`` 声明导入裸 Python 模块并创建 ``HostClassBinding`` 注册
        （机制与 ArtifactLoader 枚举 impl 块同构）。须先于 ``_hydrate_user_classes``
        的 impl 方法水化执行——impl 水化经 ``registry.get_class`` 查宿主类目标。
        """
        modules = self.artifact_dict.get("modules", {})
        for module_name, module_data in modules.items():
            if not isinstance(module_data, dict):
                continue
            root_node_uid = module_data.get("root_node_uid")
            root_node = self.node_pool.get(root_node_uid) if root_node_uid else None
            if not root_node:
                continue
            for stmt_uid in root_node.get("body", []):
                stmt_data = self.node_pool.get(stmt_uid)
                if not stmt_data or stmt_data.get("_type") != "IbHostImport":
                    continue
                self._register_host_classes_from_node(stmt_data, module_name)

    def _register_host_classes_from_node(self, stmt_data: Mapping[str, Any], module_name: str):
        """从一个 IbHostImport 节点注册其全部 ``bind class`` 宿主类型。"""
        import importlib

        py_module_name = stmt_data.get("module_name")
        try:
            py_module = importlib.import_module(py_module_name)
        except ImportError as e:
            raise RuntimeError(
                f"Host binding: cannot import Python module '{py_module_name}': {e}"
            )
        for b_uid in stmt_data.get("bindings", []):
            bdata = self.get_node_data(b_uid)
            if not bdata or not bdata.get("is_class"):
                continue
            cls_name = bdata.get("name")
            py_cls = getattr(py_module, cls_name, None)
            if py_cls is None:
                raise RuntimeError(
                    f"Host binding: Python module '{py_module_name}' has no class "
                    f"'{cls_name}' declared in bind class."
                )
            if not callable(py_cls):
                raise RuntimeError(
                    f"Host binding: '{py_module_name}.{cls_name}' is not callable "
                    f"but declared as class."
                )
            # bind 成员声明（编译期已校验签名；运行期构建 per-instance vtable 并
            # 校验成员在宿主类上真实存在——显式声明式绑定，契约外 fail-fast）
            bind_methods = []
            bind_whitelist = []
            param_meta_map = {}
            for m_uid in bdata.get("members", []):
                mdata = self.get_node_data(m_uid)
                if not mdata:
                    continue
                mname = mdata.get("name")
                if not hasattr(py_cls, mname):
                    raise RuntimeError(
                        f"Host binding: '{py_module_name}.{cls_name}' has no member "
                        f"'{mname}' declared in bind class."
                    )
                if mdata.get("is_method"):
                    if not callable(getattr(py_cls, mname)):
                        raise RuntimeError(
                            f"Host binding: '{py_module_name}.{cls_name}.{mname}' "
                            f"is not callable but declared as method."
                        )
                    bind_methods.append(mname)
                    param_meta = []
                    for p_uid in mdata.get("params", []):
                        pdata = self.get_node_data(p_uid)
                        if not pdata:
                            continue
                        param_meta.append((pdata.get("name"), "POSITIONAL_OR_KEYWORD", None))
                    param_meta_map[mname] = param_meta
                else:
                    bind_whitelist.append(mname)

            spec = self.registry.get_metadata_registry().resolve(cls_name, module=module_name)
            if spec is None:
                raise RuntimeError(
                    f"VM: Hydration Leak: host class spec '{cls_name}' (module "
                    f"'{module_name}') was not rehydrated from the artifact."
                )
            object_factory = self.service_context.object_factory
            host_cls = HostClassBinding(
                name=cls_name,
                registry=self.registry,
                object_factory=object_factory,
                py_class=py_cls,
                bind_method_names=bind_methods,
                bind_whitelist=bind_whitelist,
                param_meta_map=param_meta_map,
            )
            self.registry.register_class(cls_name, host_cls, self._kernel_token, spec=spec)

    def _hydrate_user_classes(self, class_to_node: Dict[Any, Any], impl_blocks: Optional[list] = None):
        """ STAGE 5 后期：为预水合的类实体填充方法与初始字段定义"""
        old_module = self.current_module_name
        # class_to_node 键 = (module_name, name) 元组（跨模块同名类不碰撞）。
        # 解析为运行期类键：统一 qualified（S2 类身份统一——入口模块类不再裸名，
        # 与运行期类表 qualified 键对齐：main.Box / geo.Box 独立绑定方法与字段）。
        def _class_key(module_name: Optional[str], name: str) -> str:
            return f"{module_name}.{name}" if module_name else name

        resolved = {}
        for (module_name, name), info in class_to_node.items():
            resolved[_class_key(module_name, name)] = info
        # 特化类（geo.Box[int]）与基类（geo.Box）共享 AST 节点：把以 "Name[" 开头的
        # 特化类也映射到基类节点，复用同一方法/字段绑定逻辑。get_all_classes 键
        # 已 module 化（qualified），"[" 前缀解析仍正确。
        for name, ib_class in self.registry.get_all_classes().items():
            if "[" in name and ib_class.spec and getattr(ib_class.spec, "provenance", None) == Provenance.USER_DEFINED:
                base = name.split("[", 1)[0]
                if base in resolved:
                    resolved.setdefault(name, resolved[base])
        for name, info in resolved.items():
            node_uid, module_name = info if isinstance(info, tuple) else (info, "main")
            self.current_module_name = module_name
            
            ib_class = self.registry.get_class(name)
            if not ib_class or getattr(ib_class.spec, 'provenance', Provenance.USER_DEFINED) != Provenance.USER_DEFINED:
                continue
            
            node_data = self.get_node_data(node_uid)
            if not node_data: continue
            
            body = node_data.get("body", [])
            for stmt_uid in body:
                stmt_data = self.get_node_data(stmt_uid)
                if not stmt_data: continue
                
                if stmt_data["_type"] in ("IbFunctionDef", "IbLLMFunctionDef"):
                    is_llm = stmt_data["_type"] == "IbLLMFunctionDef"
                    declared_type = self._method_declared_spec(stmt_uid)
                    method_name = stmt_data["name"]
                    user_func = IbUserFunction(
                        stmt_uid, self._execution_context, spec=declared_type,
                        owner_class=ib_class,
                        callable_kind="llm_function" if is_llm else "user_function",
                        display_name="LLMFunction" if is_llm else None,
                    )
                    user_func.is_generator = bool(stmt_data.get("is_generator"))
                    ib_class.register_method(method_name, user_func)

                    # 显式绑定运算符方法（统一初始化路径；LLM 方法不参与）
                    # 如果方法名是运算符dunder方法（如__add__、__eq__等），
                    # 通过公理系统显式绑定到运算符符号，确保运算符派发正确工作
                    if not is_llm and self._is_operator_method(method_name):
                        self._bind_operator_method(ib_class, method_name, user_func)
                elif stmt_data["_type"] == "IbAssign":
                    # 使用 IbClassField 统一管理
                    val_uid = stmt_data.get("value")
                    for target_uid in stmt_data.get("targets", []):
                        target_name = self._extract_name_id(target_uid)
                        if target_name:
                            val_data = self.get_node_data(val_uid) if val_uid else None
                            static_val = None
                            if val_data and val_data["_type"] == "IbConstant":
                                static_val = self.registry.box(self._resolve_value(val_data.get("value")))
                            
                            ib_class.default_fields[target_name] = IbClassField(
                                val_uid=val_uid, 
                                static_val=static_val, 
                                module_name=module_name
                            )

        # 填充类字段声明类型缓存（member_types）：从 spec.members 的字段
        # MemberSpec.type_ref 解析为 IbSpec。统一 Optional 值模型依赖字段声明
        # 类型在运行时可查（字段默认值求值/字段赋值的 Optional 值包装）。
        # spec.members 由 artifact 水化（type_ref 结构化），此处一次性解析缓存。
        spec_reg = self.registry.get_metadata_registry()
        for name, ib_cls in self.registry.get_all_classes().items():
            if not ib_cls or getattr(ib_cls.spec, 'provenance', Provenance.USER_DEFINED) != Provenance.USER_DEFINED:
                continue
            if spec_reg is None:
                continue
            for m_name, m in (getattr(ib_cls.spec, "members", None) or {}).items():
                if getattr(m, "kind", None) != "field":
                    continue
                type_ref = getattr(m, "type_ref", None)
                if type_ref is None:
                    continue
                field_spec = spec_reg.resolve_typeref(type_ref)
                if field_spec is not None:
                    ib_cls.member_types[m_name] = field_spec

        # retroactive impl 方法水化（封印前）：impl 块补充的方法注册到目标类。
        # 与类方法水化同构（node_to_symbol → declared_type → IbUserFunction，
        # owner_class 绑定；运算符 dunder 同样显式绑定）；注册先于封印与
        # auto-init 生成（impl 补 __init__ 时 auto-init 跳过，与"用户显式
        # 构造器优先"同语义），lookup_method 走既有继承链。
        for impl_stmt_uid, impl_module in impl_blocks or []:
            impl_data = self.get_node_data(impl_stmt_uid)
            if not impl_data:
                continue
            type_name = impl_data.get("type_name")
            target = self.registry.get_class(type_name, module=impl_module)
            if target is None:
                raise RuntimeError(
                    f"VM: Hydration Leak: impl target class '{type_name}' "
                    f"(module '{impl_module}') was not hydrated."
                )
            self.current_module_name = impl_module
            for method_uid in impl_data.get("body", []):
                stmt_data = self.get_node_data(method_uid)
                if not stmt_data:
                    continue
                if stmt_data.get("_type") not in ("IbFunctionDef", "IbLLMFunctionDef"):
                    continue
                declared_type = self._method_declared_spec(method_uid)
                is_llm = stmt_data.get("_type") == "IbLLMFunctionDef"
                user_func = IbUserFunction(
                    method_uid, self._execution_context, spec=declared_type,
                    owner_class=target,
                    callable_kind="llm_function" if is_llm else "user_function",
                    display_name="LLMFunction" if is_llm else None,
                )
                user_func.is_generator = bool(stmt_data.get("is_generator"))
                method_name = stmt_data.get("name")
                target.register_method(method_name, user_func)
                if not is_llm and self._is_operator_method(method_name):
                    self._bind_operator_method(target, method_name, user_func)

        # 第二 pass：无显式 __init__ 的类自动生成位置参数构造器（chain-aware）——
        # 构造器参数 = 继承链上全部有效无默认值字段（父类优先、子类同名覆盖）。
        # 与 instantiate 的字段收集同构（消除"auto-init 只收自身 body"的机制分裂）。
        # 须在全部类字段 hydrate 完成后执行（父类 default_fields 已填充），
        # 故独立于主循环之外。
        # B4 声明化：不生成运行时闭包——字段名清单注册到 ib_cls.auto_init_fields
        # （声明），执行经共享实现 _auto_init_impl（interpreter.py 模块级），
        # 参数数量校验由 _init_expected_arity（spec.members['__init__'] 声明）
        # 单一权威承担（消三处并存校验）。
        spec_reg = self.registry.get_metadata_registry()
        for name in resolved:
            ib_cls = self.registry.get_class(name)
            if not ib_cls or getattr(ib_cls.spec, 'provenance', Provenance.USER_DEFINED) != Provenance.USER_DEFINED:
                continue
            if '__init__' in ib_cls.methods:
                continue  # 用户显式构造器优先
            field_names = self._collect_chain_decl_only_fields(ib_cls)
            if not field_names:
                continue  # 链上无无默认值字段：经 lookup_method 继承父类构造器
            # 声明 1：类属性注册字段名清单（共享实现读取）
            ib_cls.auto_init_fields = field_names
            # 声明 2：spec.members['__init__'] 参数签名（成员表权威——
            # _init_expected_arity 经此判定参数数量；参数类型 = 字段声明类型）
            if spec_reg is not None and ib_cls.spec is not None:
                param_refs = []
                for fname in field_names:
                    f_member = (ib_cls.spec.members or {}).get(fname)
                    f_ref = getattr(f_member, "type_ref", None)
                    param_refs.append(f_ref if f_ref is not None else TypeRef.of("any"))
                ib_cls.spec.members["__init__"] = MethodMemberSpec(
                    name="__init__",
                    kind="method",
                    return_type=TypeRef.of("void"),
                    param_types=param_refs,
                )
            # 声明 3：运行期函数对象（共享实现，无闭包捕获）
            auto_init_fn = IbNativeFunction(
                _auto_init_impl,
                unbox_args=False,
                is_method=True,
                name=f"{name}.__init__",
                ib_class=ib_cls,
                param_meta=[
                    (fname, "POSITIONAL_OR_KEYWORD", None)
                    for fname in field_names
                ],
            )
            ib_cls.register_method('__init__', auto_init_fn)

        self.current_module_name = old_module

    def _collect_chain_decl_only_fields(self, ib_class) -> list:
        """收集类构造器需绑定的继承链无默认值字段（父类优先、子类同名覆盖）。

        与 :meth:`instantiate`（ib_class.py ``all_default_fields`` 收集）同构：
        沿继承链 Object → ... → 自身遍历，子类同名字段覆盖父类；最终仅保留
        仍为无默认值声明（``IbClassField`` 且 ``val_uid``/``static_val`` 均为空）的
        字段——这些字段须经构造器位置参数赋值。
        """
        chain = []
        cls = ib_class
        while cls is not None:
            chain.append(cls)
            cls = cls.parent
        effective = {}
        for ancestor in reversed(chain):
            for fname, finfo in ancestor.default_fields.items():
                effective[fname] = finfo
        return [
            fname
            for fname, finfo in effective.items()
            if isinstance(finfo, IbClassField)
            and finfo.val_uid is None
            and finfo.static_val is None
        ]

    def _method_declared_spec(self, stmt_uid: str) -> Optional[Any]:
        """方法 def 的声明 spec（函数签名 spec，单一权威）。

        从符号池按 ``node_uid == stmt_uid`` 匹配 FUNCTION/LLM_FUNCTION 符号
        并水化其 type_uid——方法对象 spec 为**函数 spec**（参数/返回签名，
        与顶层函数一致；普通方法经 node_to_symbol→self 符号解析成类
        spec，与 LLM 方法（node→func_sym）不一致，且使 __init__ 签名契约
        校验失效）。匹配失败回退旧路径（node_to_symbol 解析），保持防御。
        """
        if self.symbol_pool:
            for sym_data in self.symbol_pool.values():
                if sym_data.get("node_uid") == stmt_uid and sym_data.get("kind") in ("FUNCTION", "LLM_FUNCTION"):
                    type_uid = sym_data.get("type_uid")
                    if type_uid:
                        return self.type_hydrator.hydrate(type_uid)
        sym_uid = self.get_side_table("node_to_symbol", stmt_uid)
        return self._resolve_type_from_symbol(sym_uid)

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

    def _is_operator_method(self, method_name: str) -> bool:
        """检查方法名是否为运算符 dunder 方法。

        运算符集合从 ``op_constants`` 单一权威源派生（R2-D3 收敛：
        此处硬编码一份镜像会造成与 op_constants 双写真相）。
        ``__not__`` 属 base 协议（非运算符语法绑定），排除。
        """
        if self._OPERATOR_METHODS is None:
            self._OPERATOR_METHODS = set(OP_MAPPING.values()) | {
                UNARY_OP_MAPPING[k] for k in ("-", "+", "~")
            }
        return method_name in self._OPERATOR_METHODS

    def _bind_operator_method(self, ib_class: 'IbClass', method_name: str, user_func: Any) -> None:
        """显式绑定用户类的运算符方法到运算符符号

        **架构说明**：用户类与内置类的运算符绑定机制本质不同：

        1. **内置类**（primitive_initializer.py:_auto_bind_operators）：
           - 有 Python 实现类（如 IbInteger）
           - 通过 getattr(py_impl_cls, magic_name) 获取 Python 方法
           - 显式调用 _reg_native() 注册到 IbClass.methods

        2. **用户类**（本方法）：
           - 没有 Python 实现类，方法定义在 IBCI AST 中
           - 方法已通过 register_method() 注册到 IbClass.methods
           - 运算符派发通过 receive() 机制自动工作

        **编译时保证**：
        - SpecRegistry.resolve_op() 在编译期检查 spec.members 中的运算符方法
        - 类型检查确保运算符方法签名正确

        **运行时派发**：
        - VM 执行二元运算时，通过 IbObject.receive(magic_name, args) 调用
        - receive() 查找 vtable（即 IbClass.methods），找到用户定义的方法

        本方法存在的意义是**架构对称性**和**显式声明**：
        虽然当前实现中无需额外操作（方法已注册），但保留此函数确保：
        1. 代码意图清晰：明确标记"这是运算符方法"
        2. 未来扩展点：如需增强运算符派发逻辑，在此处统一修改
        3. 与 primitive_initializer.py 的对称性：两处都有 "bind operator" 步骤

        参数:
            ib_class: 用户定义的类对象
            method_name: 运算符方法名（如 '__add__'）
            user_func: 用户定义的方法函数对象（IbUserFunction）
        """
        # 验证方法已正确注册（防御性检查）
        if method_name not in ib_class.methods:
            from core.kernel.issue import InterpreterError
            raise InterpreterError(
                f"Internal error: operator method {method_name} not registered for class {ib_class.name}"
            )

        # 当前架构下，用户类运算符通过 receive() 自动工作，无需额外绑定步骤
        # 未来如需运算符特殊处理（如优化、类型转换），可在此扩展

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

    def is_truthy(self, value: IbObject) -> bool:
        """UTS: 使用 to_bool 协议判断真值。

        LLM-aware: 当字符串变量在 llmexcept 保护帧内被用于布尔判定时（如 ``if str_var:``），
        执行严格的布尔语义匹配。模糊值（如 "maybe"）返回 ``IbLLMCallResult(is_certain=False)``
        不确定容器，由条件消费者（if/while/for）触发 llmexcept 重试。此逻辑从
        IbString.to_bool() 迁移至此，因为 LLM 不确定性检测属于解释器层职责，
        不应由原始包装层越层访问 runtime_context。
        """
        # 不确定容器直接透传（供表达式 handler 传播到语句层消费者）
        if isinstance(value, IbLLMCallResult) and value.is_uncertain:
            return value
        # 先检查是否为字符串值在 llmexcept 帧内的模糊布尔判定
        if isinstance(value, IbObject) and value.ib_class and value.ib_class.name == "str":
            # 任务本地 runtime_context：线程 worker 内
            # llmexcept 帧检测须读任务本地上下文（coordinator 已 set
            # current execution_context），而非主 interpreter 的共享 runtime
            # context——否则任务内 ``if str_var:`` 的 LLM 模糊布尔判定误读
            # 主线程帧状态。
            ec = get_current_execution_context()
            rc = ec.runtime_context if ec is not None else self.runtime_context
            if rc is not None and rc.get_current_llm_except_frame() is not None:
                raw_val = value.to_native() if isinstance(value, IbObject) else str(value)
                val = raw_val.strip().lower() if isinstance(raw_val, str) else str(raw_val).strip().lower()
                if val in ("1", "true", "yes", "on"):
                    return True
                if val in ("0", "false", "no", "off", "null", "none", ""):
                    return False
                # 模糊回复触发不确定性标志：返回不确定容器而非 False
                ib_cls = self._registry.get_class("llm_call_result")
                if ib_cls is None:
                    raise RuntimeError("Registry missing 'llm_call_result' class")
                return IbLLMCallResult(
                    ib_class=ib_cls,
                    is_certain=False,
                    raw_response=raw_val,
                    retry_hint=f"模糊的布尔判定结果: '{raw_val}'。期望 'true'/'false'/'yes'/'no'/'1'/'0'。",
                )

        res = value.receive('to_bool', [])
        return res.to_native() != 0
