from typing import Any, Dict, Optional, List, TYPE_CHECKING, Callable
import os
import json

# =============================================================================
# 架构边界说明：HostService（DynamicHost）= 编排者，不亲自执行 IBCI 代码
# =============================================================================
# HostService 是 IBCI 宿主子系统的编排者（orchestrator）。
# 职责：管理运行现场的持久化（Artifact 序列化/反序列化）、
# 子解释器实例的隔离执行调度，以及元编程能力的暴露接口。
#
# HostService 本身不执行任何 IBCI 代码；执行始终发生在 Interpreter 内部。
# HostService 通过 IInterpreterFactory 创建 Interpreter 实例，
# 然后将执行委托给这些实例，自身只负责协调和状态管理。
# =============================================================================
from core.runtime.serialization.runtime_serializer import RuntimeSerializer, RuntimeDeserializer
from core.runtime.serialization.immutable_artifact import ImmutableArtifact
from core.runtime.exception_record import build_exception_record
from core.runtime.interfaces import ServiceContext, IHostService, IInterpreterFactory, InterOp, IExecutionContext, IKernelOrchestrator
from core.kernel.host_interface import HostInterface
from core.kernel.registry import KernelRegistry
from core.runtime.objects.kernel import IbObject
from core.kernel.issue import InterpreterError
from core.runtime.host.awaitable import HostAwaitable
from core.extension.ibcext import IbStatefulPlugin

# 序列化格式约定：save_state 外化资产时用此哨兵占位，load_state 据此回填。
_EXTERNAL_FILE_REF_SENTINEL = "__EXTERNAL_FILE_REF__"

# quote/eval 表达式结果槽（内部命名空间，单一权威源 = _wrap_expression）：
# 双下划线顶层变量（IBCI 合法变量名），quote 验证门与 eval 执行侧共享同一
# 包装形态；子进程导出变量通道据此取回表达式值。
_EVAL_RESULT_SLOT = "__qeval__"

class HostService(IHostService):
    """
    IBCI 2.0 内核级宿主服务子系统。
    负责运行现场的持久化、隔离执行以及元编程能力。
    """
    def __init__(self,
                 registry: KernelRegistry,
                 execution_context: IExecutionContext,
                 interop: InterOp,
                 setup_context_callback: Callable,
                 get_current_module_callback: Callable):
        self.registry = registry
        self.execution_context = execution_context
        self.interop = interop
        self._orchestrator = None
        self._service_context = None
        self.setup_context_callback = setup_context_callback
        self.get_current_module_callback = get_current_module_callback

    def set_service_context(self, service_context) -> None:
        """ServiceContext 注入（scheduler 装配期——host_call 懒 setup 用）。"""
        self._service_context = service_context

    def get_host_module(self, name: str):
        """宿主模块解析（Rust 内核 import 桥接调用面——经 interop/host_interface
        单一权威；返回 = 宿主模块对象[Python]）。"""
        return self.interop.get_package(name)

    def host_getattr(self, obj, attr):
        """宿主属性访问（Rust 桥接面——D2）：经对象系统 ``__getattr__`` 协议
        （字段 → 类方法 → 默认——Python VM 同路径）；裸 Python 对象 = 直接
        属性；结果原样返回（Rust from_py 消费）。"""
        if hasattr(obj, "receive"):
            return obj.receive("__getattr__", [self.registry.box(attr)])
        return getattr(obj, attr, None)

    def host_call(self, obj, method, args):
        """宿主调用分派（Rust 内核桥接面——D2 关键路径）。

        - 模块方法：懒 setup(capabilities) 保障（同 loader 装配协议——Rust
          执行路径不触发 loader 装配，首次调用注入）+ 裸属性调用；
        - 对象方法：裸属性（IbFileHandle.read 等直接方法）或 receive 分派；
        - 错误 = 显式传播（旧 call_host_method unwrap_or 吞错——D2 清零）；
        - 结果 = 原样返回（Rust from_py 消费：数据值 → typed；IbObject → Host）。
        """
        # 模块懒 setup（capabilities 注入——同 loader._setup_implementation）
        if hasattr(obj, "setup") and not getattr(obj, "_ibci_host_call_setup", False):
            from core.extension.capabilities import ExtensionCapabilities

            caps = ExtensionCapabilities(
                _registry=self.registry, _capability_registry=None
            )
            caps.service_context = self._service_context
            caps.execution_context = self.execution_context
            caps._plugin_id = type(obj).__name__
            obj.setup(capabilities=caps)
            setattr(obj, "_ibci_host_call_setup", True)
        target = getattr(obj, method, None)
        if target is None:
            # 对象方法 receive 分派（vtable 面——裸属性缺失时）
            if hasattr(obj, "receive"):
                # 参数装箱（IBCI 值 → 对象系统）——标量经 registry.box
                boxed = [self.registry.box(a) for a in args]
                result = obj.receive(method, boxed)
                return result
            raise RuntimeError(f"host_call: {type(obj).__name__} 无方法 '{method}'")
        result = target(*args)
        return result

    @property
    def orchestrator(self) -> Optional[IKernelOrchestrator]:
        """内核协调器（由 ServiceContext.set_orchestrator 统一注入）。"""
        return self._orchestrator

    @orchestrator.setter
    def orchestrator(self, value: Optional[IKernelOrchestrator]) -> None:
        self._orchestrator = value

    @staticmethod
    def _contains_disk_backed_instance(execution_context: IExecutionContext) -> bool:
        """扫描当前及外层作用域，检查是否存在 disk-backed 实例（file/media）。

        仅检查**实例**（值为 IbClass 的类型对象不算——类是类型定义，非
        disk-backed 数据）；class file_handle/audio/image/video 的类对象
        常驻 prelude，若误判会导致 save_state 永久拒绝。
        """
        from core.runtime.objects.kernel.ib_class import IbClass

        runtime_context = execution_context.runtime_context
        if runtime_context is None:
            return False
        scope = runtime_context.get_current_scope()
        while scope is not None:
            for sym in scope.get_all_symbols().values():
                val = sym.value
                if val is None:
                    continue
                if isinstance(val, IbClass):
                    # 类型对象（类）不是实例，跳过。
                    continue
                ib_class = getattr(val, "ib_class", None)
                spec = getattr(ib_class, "spec", None)
                if spec is not None and getattr(spec, "is_disk_backed", False):
                    return True
            scope = getattr(scope, "parent", None)
        return False

    def save_state(self, path: str):
        """深度序列化当前运行时上下文并保存到磁盘"""
        # 路径经 IbPath 规范化；资产外化布局委托 SnapshotLayout（策略集中化）。
        # 注：save_state 是宿主级特权操作（用户显式调用），不经 PermissionManager 沙箱校验--
        # 这是有意设计（host op 应能写用户指定位置），非安全缺口。
        # 注：assets 的 "__EXTERNAL_FILE_REF__" 哨兵是序列化格式约定。
        from core.kernel.path import IbPath, SnapshotLayout

        # 在序列化之前扫描活跃变量，若存在磁盘型容器则直接拒绝。
        if self._contains_disk_backed_instance(self.execution_context):
            raise InterpreterError(
                "save_state is not supported when the execution context contains "
                "active file_handle/audio/image/video variables. "
                "Use file.write to persist artifacts explicitly."
            )

        # 线程对象/容器是瞬态；save_state 时检测到未完成线程直接失败。
        runtime_context = self.execution_context.runtime_context
        coordinator = runtime_context.peek_runtime_coordinator() if runtime_context is not None else None
        if coordinator is not None:
            unfinished = coordinator.unfinished_handles()
            if unfinished:
                raise InterpreterError(
                    "save_state is not supported while threads are running: "
                    f"unfinished thread(s) {unfinished}. "
                    "Join or cancel all threads before saving state."
                )

        data = self.snapshot()

        save_path = IbPath.from_native(path).resolve_dot_segments()
        abs_path = save_path.to_native()
        base_dir = (save_path.parent.to_native() if save_path.parent else "")
        if base_dir:
            os.makedirs(base_dir, exist_ok=True)

        # 文本资产外部化持久化（布局走 SnapshotLayout）
        assets = data["pools"].get("assets", {})
        if assets:
            asset_dir_path = SnapshotLayout.asset_dir_for(save_path)
            os.makedirs(asset_dir_path.to_native(), exist_ok=True)
            for uid, content in assets.items():
                asset_path = SnapshotLayout.asset_file(asset_dir_path, uid).to_native()
                with open(asset_path, "w", encoding="utf-8") as af:
                    af.write(content)
            data["pools"]["assets"] = {uid: _EXTERNAL_FILE_REF_SENTINEL for uid in assets}

        with open(abs_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_state(self, path: str):
        """从磁盘加载快照并恢复当前现场"""
        from core.kernel.path import IbPath, SnapshotLayout
        save_path = IbPath.from_native(path).resolve_dot_segments()
        abs_path = save_path.to_native()
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"State file not found: {abs_path}")

        with open(abs_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 恢复外部文本资产（布局走 SnapshotLayout，与 save_state 一致）
        asset_dir_path = SnapshotLayout.asset_dir_for(save_path)
        asset_dir = asset_dir_path.to_native()
        if os.path.exists(asset_dir):
            assets = data["pools"].get("assets", {})
            for uid in assets:
                asset_path = SnapshotLayout.asset_file(asset_dir_path, uid).to_native()
                if os.path.exists(asset_path):
                    with open(asset_path, "r", encoding="utf-8") as af:
                        assets[uid] = af.read()
                        
        deserializer = RuntimeDeserializer(self.registry, factory=self.execution_context.factory)
        new_ctx = deserializer.deserialize_context(data)
        
        # 重新绑定环境能力 (Intrinsics & Plugins)
        plugin_states = data.get("plugin_states", {}) if isinstance(data, dict) else {}
        self._rebind_environment(new_ctx, deserializer, plugin_states=plugin_states)
        
        # 强制同步到当前解释器实例 (通过容器更新)
        self.execution_context.runtime_context = new_ctx

    def snapshot(self) -> Dict[str, Any]:
        """内存快照原语。同时捕获有状态插件的状态。"""
        serializer = RuntimeSerializer(self.registry)
        snapshot = serializer.serialize_context(
            self.execution_context.runtime_context,
            execution_context=self.execution_context
        )
        # 收集所有有状态插件的快照
        plugin_states: Dict[str, Any] = {}
        for name in self.interop.get_all_package_names():
            pkg = self.interop.get_package(name)
            if pkg and isinstance(pkg, IbStatefulPlugin):
                # 显式持久化契约：插件状态保存失败必须暴露（fail-fast），
                # 不静默降级为哨兵——否则 save_state 用户无感知地丢数据。
                plugin_states[name] = pkg.save_plugin_state()
        if plugin_states:
            snapshot["plugin_states"] = plugin_states
        return snapshot

    def _rebind_environment(self, context: Any, deserializer: Optional[Any] = None, plugin_states: Optional[Dict[str, Any]] = None):
        """
        环境重绑定：将快照中的“空壳”重新链接到当前物理环境的功能实现。
        对 IbStatefulPlugin 插件，额外调用 restore_plugin_state() 恢复其内部状态。
        """
        # 1. 重新注入内置函数 (Intrinsics) - 使用特权覆盖 (通过回调)
        self.setup_context_callback(context, force=True)
        
        # 2. 重新注入原生插件 (Native Plugins)
        # 模块对象按 import 路径同构构造（vtable/白名单契约 + IbModule 包装）——
        # 缺契约的裸 NativeObject 会在成员访问时被模块契约门拒绝。
        live_modules: Dict[str, Any] = {}
        for name in self.interop.get_all_package_names():
            pkg = self.interop.get_package(name)
            if pkg:
                if not isinstance(pkg, IbObject):
                    # 使用工厂创建 Native 对象，消除对 kernel.IbNativeObject 的直接依赖
                    contract = self.interop.get_native_contract(name)
                    native_obj = self.execution_context.factory.create_native_object(
                        pkg,
                        self.registry.get_class("Object"),
                        vtable=contract[0] if contract else None,
                        whitelist=contract[1] if contract else None,
                        registry_id=self.interop.get_registry_id(name),
                    )
                    pkg_obj = self.execution_context.factory.create_module(name, native_obj)
                else:
                    pkg_obj = pkg
                live_modules[name] = pkg_obj
                # 强制覆盖常量符号
                context.global_scope.define(name, pkg_obj, is_const=True, force=True)

        # 2.5 恢复作用域树中的内核原生模块绑定（KERNEL_ISSUE-SER-1）：import 产生的
        # 模块变量位于模块作用域（非 global），其值经快照反序列化为 scope_native 空
        # scope 占位（见 runtime_serializer._collect_module 契约：实现由本方法重绑）。
        # 重绑必须覆盖全部已恢复作用域——仅修 global 时，模块作用域的死占位会遮蔽
        # 活绑定，load 后模块成员访问 AttributeError。
        # 就地变更符号值（不重建符号）：编译期符号 UID 与运行期 uid 键是同一符号的
        # 多别名，重建会触发别名清理丢失编译期键。
        if deserializer is not None and live_modules:
            for scope in deserializer.restored_scopes():
                for sym in scope.get_all_symbols_by_uid().values():
                    live_obj = live_modules.get(sym.name)
                    if live_obj is not None:
                        sym.value = live_obj
                        sym.current_type = type(live_obj)
                for sym in scope.get_all_symbols().values():
                    live_obj = live_modules.get(sym.name)
                    if live_obj is not None:
                        sym.value = live_obj
                        sym.current_type = type(live_obj)

        # 3. 恢复有状态插件的内部状态（fail-fast：恢复失败必须暴露，不静默跳过）
        if plugin_states:
            for name, saved in plugin_states.items():
                pkg = self.interop.get_package(name)
                if pkg and isinstance(pkg, IbStatefulPlugin):
                    pkg.restore_plugin_state(saved)

    def run_isolated(self, path: str, policy: Dict[str, Any]) -> "HostAwaitable":
        """
        隔离执行：在独立子引擎中运行 ``path``，返回 ``HostAwaitable``（可等待句柄）。

        语义与 ``spawn_isolated`` 统一——子引擎在后台线程中运行；本方法返回
        ``HostAwaitable``，VM 调度器对它 ``yield`` 挂起并等待完成，经 ``result()``
        取回子环境导出的变量字典（多返回值）。对脚本而言即"阻塞式"运行并等待。

        父与子之间不做隐式内存交互，变量不跨隔离边界继承；父->子 数据传递应
        通过显式 file 读写完成。
        """
        if not self.orchestrator:
            raise RuntimeError("Kernel Orchestrator not available. Isolated execution cannot be performed.")

        abs_path = self._resolve_isolated_path(path)
        handle = self.orchestrator.request_spawn_isolated(abs_path, policy, silent=False)
        return HostAwaitable(self.orchestrator, handle)

    def spawn_isolated(self, path: str, policy: Dict[str, Any]) -> str:
        """
        非阻塞隔离执行。通过内核协调器在后台线程中启动子引擎，立即返回 handle。
        调用方随后通过 collect(handle) 等待完成并取回结果变量。
        """
        if not self.orchestrator:
            raise RuntimeError("Kernel Orchestrator not available. Spawned execution cannot be performed.")

        abs_path = self._resolve_isolated_path(path)
        return self.orchestrator.request_spawn_isolated(abs_path, policy)

    def collect(self, handle: str) -> "HostAwaitable":
        """
        返回 ``HostAwaitable``（可等待句柄）：VM 调度器对它 ``yield`` 挂起，等待
        对应 ``spawn_isolated`` 子执行完成，经 ``result()`` 取回子环境导出的变量
        字典。handle 消费后失效；重复 collect 同一 handle 将抛出 RuntimeError。
        """
        if not self.orchestrator:
            raise RuntimeError("Kernel Orchestrator not available.")

        return HostAwaitable(self.orchestrator, handle)

    def run_file(self, path: str, policy: Dict[str, Any]) -> "IbRunResult":
        """
        独立子进程运行另一个 .ibci 文件并捕获执行结果（结果记录消费面）。

        与 ``run_isolated``（变量交换消费面：错误作异常 + 导出变量字典）互补：
        ``run_file`` 返回 ``run_result`` 值类型（三字段 ``exit_status``/``stdout``/
        ``exception``；**错误作值**；子 print 输出被捕获、不经父 stdout）。同一
        spawn 核心（``request_spawn_isolated`` 文件源）+ 同步 collect——本方法在
        VM 线程被调，子线程经独立引擎执行（不依赖父 VM 线程，无循环等待）。

        ``exception`` 字段 = ``None`` 或结构化 dict ``{code, message,
        source{file,line,column,snippet}}``（与 CLI ``--result-json`` exception 面
        同构，单一权威源 ``core/runtime/exception_record.py``）。

        防卡死：collect_timeout 经 policy 传递（IsolationPolicy 既有面）；
        默认 None = 无界（与 run_isolated 一致）。
        """
        return self._spawn_and_capture(entry_path=self._resolve_isolated_path(path),
                                       policy=policy)

    def run_code(self, code: str, policy: Dict[str, Any]) -> "IbRunResult":
        """
        独立子进程运行一段 IBCI 代码字符串并捕获执行结果（结果记录消费面，字符串源）。

        与 ``run_file`` **机制同构**（同一 spawn 核心字符串源：子 project_root =
        父 project_root，合成 entry ``__string_exec__`` 锚定；同一 E1 LLM 继承 /
        沙箱 / 防卡死 / 输出捕获 / 错误作值纪律）——消除试用方"手写临时文件 +
        run_file"的胶水绕路。返回 ``run_result`` 值类型（字段面同 run_file）。

        防卡死：collect_timeout 经 policy 传递（IsolationPolicy 既有面）。
        """
        return self._spawn_and_capture(code=code, policy=policy)

    def _spawn_and_capture(self, *, entry_path: Optional[str] = None, code: Optional[str] = None,
                           policy: Optional[Dict[str, Any]] = None) -> "IbRunResult":
        """run_file / run_code 共享的 spawn + 结果捕获核心（两源形式）。

        源形式：``entry_path``（文件源）XOR ``code``（字符串源）——经
        ``request_spawn_isolated`` 单一 spawn 核心。子 print 经 ``output_callback``
        捕获（不经父 stdout）；子异常/超时经 ``request_collect`` 的 ``RuntimeError``
        上抛，此处捕获并经 ``build_exception_record`` 结构化（``__cause__`` = 子
        原始异常[编译/运行期]；超时 = 无 ``__cause__`` → 取 RuntimeError 自身）。
        """
        if not self.orchestrator:
            raise RuntimeError(
                "Kernel Orchestrator not available. run_file/run_code cannot be performed.")

        chunks: List[str] = []
        handle = self.orchestrator.request_spawn_isolated(
            entry_path, policy, silent=True, output_callback=chunks.append, code=code)
        exit_status = "ok"
        exception_record = None
        try:
            self.orchestrator.request_collect(handle)
        except RuntimeError as e:
            exit_status = "error"
            # __cause__ = 子线程原始异常（编译 CompilerError / 运行 IBCBaseException /
            # ThrownException）；超时 RuntimeError 无 __cause__ → 取自身。
            exception_record = build_exception_record(e.__cause__ if e.__cause__ is not None else e)
        return self._make_run_result(exit_status, "\n".join(chunks), exception_record)

    def _make_run_result(self, exit_status: str, stdout: str,
                         exception_record: Optional[Dict[str, Any]]) -> "IbRunResult":
        """装箱 run_result 值对象（经 box 透传，非 dict 装箱——单一权威源）。"""
        from core.runtime.objects.primitives.run_result import IbRunResult
        run_result_cls = self.registry.get_class("run_result")
        return IbRunResult(run_result_cls, exit_status=exit_status, stdout=stdout,
                           exception=exception_record)

    def _sub_engine_compile(self, code: str) -> Any:
        """子引擎 compile-only（**单一编译门核心**：meta.compile / meta.quote 共享）。

        新 IBCIEngine（父 project_root 锚定，合成 entry 同名同源；**零父状态污染**
        ——父程序可能自身即字符串运行；compile-only 无需 LLM 继承/防卡死[编译不
        执行]）。仅经运行中的父 VM 调用（父 root 必已确立）。

        成功返回编译产物；编译失败 fail-fast：首个诊断（根因面）经
        ``InterpreterError`` 上抛（携带 ibci 源定位——合成 entry 标记 + line/
        column，IBCI ``try/except`` 可捕获）——与 CLI ``check`` 面同构
        （compile-only + 失败即断）。源定位 file_path 从 tempfile 载体重写为
        合成 entry 标记（字符串源可辨识）。
        """
        from core.engine import IBCIEngine
        from core.kernel.issue import CompilerError

        parent_root = getattr(self.orchestrator, "root_dir", None)
        if parent_root is None:
            raise InterpreterError(
                "子引擎编译须父 project_root 已确立（经运行中的父 VM 调用）。", None)
        sub_engine = IBCIEngine(root_dir=parent_root)
        try:
            return sub_engine.compile_string(code, silent=True)
        except CompilerError as e:
            diags = e.diagnostics or []
            d = diags[0] if diags else None
            if d is None:
                raise InterpreterError("子引擎编译失败。", None) from e
            loc = getattr(d, "location", None)
            if loc is not None:
                loc.file_path = self._string_source_marker(parent_root)
            raise InterpreterError(d.message, loc, error_code=d.code) from e

    def meta_compile(self, code: str) -> Dict[str, Any]:
        """meta.compile：代码字符串进程内 **compile-only** 静态校验 + **返回编译产物值**
        （行为作值，TYPE-1：可检查/可作值返回/可组合）。

        经 ``_sub_engine_compile`` 单一编译门核心（子引擎 compile-only，零父状态
        污染；失败 fail-fast 经 ``InterpreterError`` 上抛携带 ibci 源定位——与 CLI
        ``check`` 面同构）。

        **成功返回编译产物摘要（dict）**（行为作值 TYPE-1）：
        ok/n_modules/entry_module/n_top_stmts/n_funcs/func_names/n_classes/class_names——
        系统可持已编译行为为值，确定性内省（D1）其结构（定义了几何函数/类、顶层规模），
        为"代码自修改台阶 4"（LLM 生成代码→编译作值→确定性验证→持有/观测）提供承载。
        """
        from core.kernel.ast import IbFunctionDef, IbClassDef

        artifact = self._sub_engine_compile(code)

        # 行为作值（TYPE-1）：提取入口模块编译产物摘要（确定性内省其结构）。
        n_top = 0
        n_funcs = 0
        n_classes = 0
        func_names: List[str] = []
        class_names: List[str] = []
        entry = artifact.entry_module
        entry_result = artifact.get_module(entry) if entry else None
        if entry_result is not None:
            body = entry_result.module_ast.body
            n_top = len(body)
            for stmt in body:
                if isinstance(stmt, IbFunctionDef):
                    n_funcs += 1
                    func_names.append(stmt.name)
                elif isinstance(stmt, IbClassDef):
                    n_classes += 1
                    class_names.append(stmt.name)

        return {
            "ok": True,
            "n_modules": len(artifact.modules) if hasattr(artifact, "modules") else 1,
            "entry_module": entry or "",
            "n_top_stmts": n_top,
            "n_funcs": n_funcs,
            "func_names": func_names,
            "n_classes": n_classes,
            "class_names": class_names,
        }

    # ------------------------------------------------------------------ #
    # quote/eval（数据/命令二元：meta.quote 验证门 / meta.eval 值通道）
    # ------------------------------------------------------------------ #

    @staticmethod
    def _wrap_expression(source: str) -> str:
        """表达式源串 → 验证/执行包装码（**单一包装源**：quote 门与 eval 执行侧共享）。

        形态 = ``__qeval__ = <source>``（``_EVAL_RESULT_SLOT`` 结果槽）。包装本身
        即**表达式性门**：语句源在 ``=`` 位置编译失败（fail-fast，非表达式 =
        quote 拒绝面）。
        """
        return f"{_EVAL_RESULT_SLOT} = {source}\n"

    def quote_expression(self, source: str):
        """meta.quote：表达式源串经**单一验证门**冻结为 ``quoted`` 值（数据形态）。

        验证门 = ``_sub_engine_compile`` 编译门核心（同 meta.compile 路径）对包装体
        ``__qeval__ = <source>`` compile-only——语法/语义/**表达式性**/**自包含性**
        （fresh scope：引用父模块自由名的源在此门即 fail-fast，无隐式捕获面）一次
        门尽。失败上抛 ``InterpreterError``（首个诊断 + ibci 源定位，IBCI
        ``try/except`` 可捕获）。

        成功返回 ``quoted`` 不可变值（字段 ``source`` = 完整源串——可打印其自身/
        精确对比逐字节/可序列化/可跨引擎移植）。**良构由构造成立**：quoted 值
        必已通过验证门（无未验证的 quoted 构造面——str→quoted 不经 cast，仅本
        方法入口）。零 LLM（compile-only）。执行侧配对原语 = ``eval_quoted``。
        """
        from core.runtime.objects.primitives.quoted import IbQuoted
        if not isinstance(source, str) or not source.strip():
            raise InterpreterError("meta.quote 须非空 str 表达式源串。", None)
        self._sub_engine_compile(self._wrap_expression(source))
        quoted_cls = self.registry.get_class("quoted")
        return IbQuoted(quoted_cls, source=source)

    def eval_quoted(self, source: str) -> Any:
        """meta.eval：quoted 值的表达式源串执行并取回其**值**（命令形态）。

        机制同构（与 ihost.run_code 同一 spawn 核心，**值交换消费面**）：子进程
        独立引擎（fresh scope + 进程级隔离 + LLM 态继承）运行包装体
        ``__qeval__ = <source>``；collect 取回导出变量（JSON 原生值）的结果槽。
        **返回值而非 stdout 文本**——stdout 通道 = run_code 的观察面，值通道 =
        eval 的取值面（两面对应两种意图，非双通道）。

        错误面（**fail-fast**，与 run_code 错误作值互补——不同概念不同面）：
        子编译/运行错误经 collect 上抛（携带 error_code）→ 本方法翻译为
        ``InterpreterError``（IBCI ``try/except`` 可捕获）；**结果槽缺失** = 显式
        上抛（结果不可经值通道序列化——复杂值/函数值，或表达式无值）。``None``
        是合法值（结果槽存在 → 取值，含 None）。
        """
        if not isinstance(source, str) or not source.strip():
            raise InterpreterError("meta.eval 须非空 str 表达式源串。", None)
        if not self.orchestrator:
            raise InterpreterError(
                "Kernel Orchestrator is not available. meta.eval cannot be performed.", None)
        handle = self.orchestrator.request_spawn_isolated(
            None, {}, silent=True, code=self._wrap_expression(source))
        try:
            variables = self.orchestrator.request_collect(handle)
        except RuntimeError as e:
            err_code = getattr(e, "error_code", None)
            raise InterpreterError(f"meta.eval 执行失败: {e}", None,
                                   error_code=err_code) from e
        if not isinstance(variables, dict) or _EVAL_RESULT_SLOT not in variables:
            raise InterpreterError(
                f"meta.eval: 表达式值不可经值通道取回（复杂值/函数值非 JSON 可序列化）"
                f"或表达式无值。source={source!r}", None)
        return variables[_EVAL_RESULT_SLOT]

    @staticmethod
    def _string_source_marker(parent_root: str) -> str:
        """字符串源定位的合成 entry 标记（``<parent_root>/__string_exec__.ibci``）。

        与 ``compile_string`` 的 entry 锚定同源（稳定 + 可辨识"字符串源"）；替代
        compile_string 的 tempfile 载体路径（实现细节，不应暴露给用户源定位面）。
        """
        from core.kernel.path import IbPath
        return (IbPath.from_native(parent_root) / "__string_exec__.ibci").to_native()

    def _resolve_isolated_path(self, path: str) -> str:
        """
        把 ``ihost.run_isolated``/``spawn_isolated`` 传入的脚本路径解析为绝对路径。

        委托规范解析器 ``PathResolver``（entry_dir 单锚点契约），与
        ``ExecutionContextImpl.resolve_path`` / ``file.read`` 的相对入口目录语义一致。
        """
        from core.kernel.path import PathResolver, IbPath
        entry_dir = self.execution_context.get_entry_dir()
        resolver = PathResolver(entry_dir=IbPath.from_native(entry_dir) if entry_dir else None)
        return resolver.resolve(path).to_native()

    def get_source(self) -> str:
        """元编程：获取当前运行模块的源代码"""
        current_mod = self.get_current_module_callback()
        provider = getattr(self.execution_context.service_context, 'source_provider', None)
        if provider:
            return provider.get_module_source(current_mod) or ""
        return ""

    def getenv(self, key: str) -> str:
        """读取宿主 OS 环境变量（一等语言面通道；缺失返回空串——
        对齐 os.getenv(key, "") 语义，语言层 str 类型无需空值分支）。"""
        import os
        return os.environ.get(key, "")
