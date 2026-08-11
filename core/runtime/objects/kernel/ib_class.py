from typing import Optional, Dict, Mapping, Any, List, TYPE_CHECKING

from core.kernel.registry import KernelRegistry
from core.kernel.issue import InterpreterError
from core.kernel.spec import IbSpec, TypeKind

from ..ib_type_mapping import register_ib_type, get_ib_implementation
from .base import IbObject, IbValue

if TYPE_CHECKING:
    from core.runtime.interfaces import IExecutionContext


class IbClassField:
    """类字段描述符：存储 AST 节点 UID 及其可能的预评估快照。"""
    def __init__(self, val_uid: str, static_val: Optional[IbObject] = None, module_name: Optional[str] = None):
        self.val_uid = val_uid
        self.static_val = static_val
        self.module_name = module_name

    def __repr__(self):
        return f"<ClassField {self.val_uid} (static={self.static_val})>"

class _ClassInstantiateDrive:
    """用户类构造的帧内 CPS 驱动 Waitable（类构造嵌套调度器根治）。

    由 :meth:`IbClass.receive` 对不含原生 ``__init__`` 的类返回；VM
    ``vm_handle_IbCall`` 识别其为 ``Waitable`` + ``CPSDrivable`` 后 ``yield from
    cps_drive``——字段默认值求值 + 用户 ``__init__`` 经 yield 嵌入当前 VM 帧栈
    （替代 ``instantiate`` 的 ``vm.run`` 嵌套驱动循环与 ``init_method.call``
    新建 TaskScheduler）。宿主/线程体无活跃 VM 时 ``try_result``/``result`` 走
    同步 ``instantiate`` 兜底（与 :class:`_RunBatchDrive` 同构）。

    注意：``thread(...)`` 的 ``__init__`` 为原生函数（不走本类），返回
    ``IbThread`` 句柄（纯 ``Waitable``，非 ``CPSDrivable``），VM 不 auto-yield。
    """

    def __init__(self, cls, args, context):
        self._cls = cls
        self._args = args
        self._context = context
        self._done = False
        self._result = None

    @property
    def is_done(self) -> bool:
        return self._done

    def _drive(self):
        self._result = self._cls.instantiate(self._args, context=self._context)
        self._done = True
        return self._result

    def cps_drive(self, executor):
        self._result = yield from self._cls._instantiate_cps(
            self._args, self._context
        )
        self._done = True
        return self._result

    def try_result(self):
        if self._done:
            return (True, self._result)
        self._drive()
        return (True, self._result)

    def result(self):
        self._drive()
        return self._result

    def register_wake(self, event) -> None:
        event.set()


@register_ib_type("Type")
@register_ib_type("Class")
class IbClass(IbObject):
    """
    IBC-Inter class object (meta-object).
    Everything is an object — classes themselves are objects.
    Holds the IbSpec (pure-data type description) and the runtime method vtable.
    """
    __slots__ = ('name', 'methods', 'parent', 'default_fields', 'member_types', 'registry', '_spec')

    def __init__(self, name: str, parent: Optional['IbClass'] = None, registry: Optional[KernelRegistry] = None):
        if not registry:
            raise ValueError("Registry is required for IbClass creation")
        self.registry = registry
        IbObject.__init__(self, self)
        self.name = name
        self.methods: Dict[str, 'IbFunction'] = {}
        self.parent = parent
        self.default_fields: Mapping[str, Any] = {}
        self.member_types: Dict[str, Any] = {}
        self._spec: Optional[IbSpec] = None

    @property
    def spec(self) -> Optional[IbSpec]:
        return self._spec

    @spec.setter
    def spec(self, value: Optional[IbSpec]) -> None:
        self._spec = value

    def lookup_method(self, name: str) -> Optional['IbFunction']:
        """在虚表中查找方法 (支持继承)"""
        if name in self.methods:
            return self.methods[name]
        if self.parent:
            return self.parent.lookup_method(name)
        return None

    def is_assignable_to(self, other: 'IbClass') -> bool:
        """Runtime type compatibility check (UTS protocol)."""
        if self is other:
            return True
        if other is None:
            return False
        spec_reg = self.registry.get_metadata_registry()
        if spec_reg and self._spec and other._spec:
            return spec_reg.is_assignable(self._spec, other._spec)
        return False

    def register_method(self, name: str, method: 'IIbFunction') -> None:
        # 封印校验：禁止在 Registry READY 状态下修改虚表
        if self.registry.is_sealed:
            raise PermissionError(f"Sealed Registry Violation: Cannot register method '{name}' to class '{self.name}' in READY state.")
        self.methods[name] = method

    def register_field(self, name: str, default_value: 'IbObject') -> None:
        # 封印校验
        if self.registry.is_sealed:
            raise PermissionError(f"Sealed Registry Violation: Cannot register field '{name}' to class '{self.name}' in READY state.")
        self.default_fields[name] = default_value

    def instantiate(self, args: List[IbObject], context: Optional['IExecutionContext'] = None) -> IbObject:
        # 值对象类型化构造钩子：实现类覆写 _create_blank 则产生
        # 其类型化实例（如 IbThread），否则默认普通 IbObject（既有行为）。
        impl_cls = get_ib_implementation(self.name)
        instance = impl_cls._create_blank(self) if impl_cls is not None else IbObject(self)

        # 收集完整的字段继承链（父类字段 + 子类字段）
        # 父类字段先初始化，子类同名字段会覆盖父类字段
        all_default_fields = {}
        # 从继承链顶部开始收集（最远祖先优先）
        ancestors = []
        cls = self
        while cls is not None:
            ancestors.append(cls)
            cls = cls.parent
        for ancestor in reversed(ancestors):
            for name, val_info in ancestor.default_fields.items():
                all_default_fields[name] = val_info

        # 延迟执行字段初始化 (Item 2.1 Audit)
        self._eval_field_defaults(instance, all_default_fields, context)
        self._invoke_init(instance, args)
        return instance

    def _eval_field_defaults(
        self, instance: 'IbObject', all_default_fields: dict, context: Any
    ) -> None:
        """求值类字段默认值写入实例字段。

        ``static_val`` 非空用预评估快照（可变容器 list/dict 每次浅拷贝新实例
        避免共享）；无快照但有 ``val_uid`` 时经 ``vm.run`` 动态求值（JIT caching：
        首次求值后回写 ``static_val`` 供后续实例复用，非每次构造都重入调度器）；
        否则置 None。字段默认值求值失败为真实错误——fail-fast，不静默置 None。
        """
        for name, val_info in all_default_fields.items():
            if isinstance(val_info, IbClassField):
                if val_info.static_val is not None:
                    # 优先使用预评估好的快照，但可变容器（list/dict）必须每次创建新实例，
                    # 避免所有实例共享同一容器对象（浅拷贝快照，元素引用共享）。
                    sv = val_info.static_val
                    # 可变容器（list/dict）需每次创建新实例以避免共享——
                    # 使用 type(sv)(...) 保持多态性，无需引入具体类名。
                    if isinstance(sv, IbValue) and sv.ib_class.name == "list":
                        instance.fields[name] = type(sv)(list(sv.elements), sv.ib_class)
                    elif isinstance(sv, IbValue) and sv.ib_class.name == "dict":
                        instance.fields[name] = type(sv)(dict(sv.fields), sv.ib_class)
                    else:
                        instance.fields[name] = sv
                elif val_info.val_uid and context:
                    # 动态求值并尝试更新描述符以供后续实例复用 (JIT caching)
                    try:
                        vm = context.vm_executor
                        if vm is None:
                            raise RuntimeError("IbClass.instantiate: vm_executor not available")
                        old_module = context.current_module_name
                        context.current_module_name = val_info.module_name
                        try:
                            evaluated = vm.run(val_info.val_uid)
                        finally:
                            context.current_module_name = old_module
                        instance.fields[name] = evaluated
                        val_info.static_val = evaluated
                    except Exception as e:
                        # 实例化时字段默认值求值失败是真实错误——fail-fast，
                        # 静默置 None 会掩盖初始化 bug 产生错误对象。
                        raise InterpreterError(
                            f"Field initializer for '{name}' failed: {e}",
                        ) from e
                else:
                    instance.fields[name] = self.registry.get_none()
            else:
                # [Active Defense] 仅支持 IbClassField，确保字段初始化的一致性
                instance.fields[name] = val_info

    def _invoke_init(self, instance: 'IbObject', args: List['IbObject']) -> None:
        """调用用户 ``__init__``（宿主侧 ``init_method.call``）。

        契约校验 ``__init__`` 参数数量；无 ``__init__`` 却传参视为契约违背。
        已知问题：``init_method.call`` 为宿主侧薄包装（``_vm_call_user_function``
        + ``_drive_generator`` 新建 TaskScheduler），``__init__`` 含 Waitable 时
        会阻塞主调度线程（类构造未接入 VM 帧内 CPS 驱动）。
        """
        init_method = self.lookup_method('__init__')
        if init_method:
            # 契约一致性校验：校验 __init__ 参数数量
            # 注意：描述符中的参数列表通常不包含 self (除非是特殊定义的)
            if init_method.spec and init_method.spec.kind in (TypeKind.FUNCTION.value, TypeKind.CALLABLE_SIG.value):
                expected_count = len(init_method.spec.param_types)
                if len(args) != expected_count:
                    raise InterpreterError(f"TypeError: {self.name}.__init__() expected {expected_count} arguments, but got {len(args)}")

            init_method.call(instance, args)
        elif args:
            # 如果没有定义 __init__ 但传了参数，也是一种契约违背
            raise InterpreterError(f"TypeError: {self.name}() takes no arguments, but {len(args)} were given")

    def _instantiate_cps(self, args: List['IbObject'], context: Any) -> Any:
        """CPS 版 :meth:`instantiate`：字段默认值 + 用户 ``__init__`` 经 yield 嵌入 VM 帧栈。

        与 :meth:`instantiate` 同语义，但动态字段默认值用 ``yield val_uid``（由外层
        ``_drive_loop_gen`` 帧内求值，替代 ``vm.run`` 嵌套驱动循环），用户
        ``__init__`` 经 ``UserFunctionCall`` trampoline 压栈帧内驱动（替代
        ``init_method.call`` 新建 TaskScheduler）。类构造并入统一 CPS 执行模型，
        ``__init__``/字段默认值含 Waitable 时由调度器协作挂起而非阻塞主线程。
        调用方（:class:`_ClassInstantiateDrive.cps_drive`）须 ``yield from``。
        """
        impl_cls = get_ib_implementation(self.name)
        instance = impl_cls._create_blank(self) if impl_cls is not None else IbObject(self)

        all_default_fields: dict = {}
        ancestors = []
        cls = self
        while cls is not None:
            ancestors.append(cls)
            cls = cls.parent
        for ancestor in reversed(ancestors):
            for name, val_info in ancestor.default_fields.items():
                all_default_fields[name] = val_info

        yield from self._eval_field_defaults_cps(instance, all_default_fields, context)
        yield from self._invoke_init_cps(instance, args)
        return instance

    def _eval_field_defaults_cps(
        self, instance: 'IbObject', all_default_fields: dict, context: Any
    ) -> Any:
        """CPS 版 :meth:`_eval_field_defaults`：动态字段默认值经 ``yield`` 帧内求值。"""
        for name, val_info in all_default_fields.items():
            if isinstance(val_info, IbClassField):
                if val_info.static_val is not None:
                    sv = val_info.static_val
                    if isinstance(sv, IbValue) and sv.ib_class.name == "list":
                        instance.fields[name] = type(sv)(list(sv.elements), sv.ib_class)
                    elif isinstance(sv, IbValue) and sv.ib_class.name == "dict":
                        instance.fields[name] = type(sv)(dict(sv.fields), sv.ib_class)
                    else:
                        instance.fields[name] = sv
                elif val_info.val_uid and context:
                    old_module = context.current_module_name
                    context.current_module_name = val_info.module_name
                    try:
                        try:
                            evaluated = yield val_info.val_uid
                        finally:
                            context.current_module_name = old_module
                    except Exception as e:
                        raise InterpreterError(
                            f"Field initializer for '{name}' failed: {e}",
                        ) from e
                    instance.fields[name] = evaluated
                    val_info.static_val = evaluated
                else:
                    instance.fields[name] = self.registry.get_none()
            else:
                instance.fields[name] = val_info

    def _invoke_init_cps(self, instance: 'IbObject', args: List['IbObject']) -> Any:
        """CPS 版 :meth:`_invoke_init`：用户 ``__init__`` 经 ``UserFunctionCall`` 帧内驱动。"""
        from core.runtime.shared.user_call import UserFunctionCall
        from .user_functions import IbUserFunction

        init_method = self.lookup_method('__init__')
        if init_method:
            if init_method.spec and init_method.spec.kind in (TypeKind.FUNCTION.value, TypeKind.CALLABLE_SIG.value):
                expected_count = len(init_method.spec.param_types)
                if len(args) != expected_count:
                    raise InterpreterError(f"TypeError: {self.name}.__init__() expected {expected_count} arguments, but got {len(args)}")

            if isinstance(init_method, IbUserFunction):
                yield UserFunctionCall(init_method, args, instance)
            else:
                init_method.call(instance, args)
        elif args:
            raise InterpreterError(f"TypeError: {self.name}() takes no arguments, but {len(args)} were given")

    def receive(self, message: str, args: List['IbObject']) -> 'IbObject':
        """
        类对象的特殊消息处理：
        1. __call__ -> 实例化 (Instantiate) 或 类级别的 __call__
        2. __getattr__ -> 访问类字段 (default_fields)
        3. 其他 -> 正常消息处理 (查找静态方法等)
        """
        from .functions import IbBoundMethod, IbNativeFunction
        if message == "__call__":
            # 类自身声明的原生 __call__（如 int()/str()/float()/bool() 类型转换
            # 构造器）优先于 instantiate；用户类的 __call__ 是实例方法（经
            # IbObject.receive vtable 分发给实例），不覆盖类构造器。
            own_call = self.methods.get("__call__")
            if isinstance(own_call, IbNativeFunction):
                return own_call.call(self, args)
            # 用户类构造器：instantiate 创建新实例。
            context = self.registry.get_execution_context()
            init_method = self.lookup_method('__init__')
            # 不含原生 __init__（用户 __init__ 或未定义）→ 返回 CPSDrivable drive，
            # VM 帧内驱动字段默认值 + __init__（类构造接入统一 CPS 执行模型）。
            # 含原生 __init__（如 thread）→ 同步 instantiate（返回句柄，不 auto-yield）。
            if not isinstance(init_method, IbNativeFunction):
                return _ClassInstantiateDrive(self, args, context)
            return self.instantiate(args, context=context)

        if message == "__getattr__" and len(args) > 0:
            attr_name = args[0].to_native()
            # 优先查找类字段 (default_fields)
            if attr_name in self.default_fields:
                val_info = self.default_fields[attr_name]
                if val_info is not None:
                    # static_val 仅定义于 IbClassField（isinstance 精确判别，与同文件其它处一致）
                    if isinstance(val_info, IbClassField) and val_info.static_val is not None:
                        return val_info.static_val
                    return self.registry.box(val_info)
            # 降级查找类方法
            method = self.lookup_method(attr_name)
            if method:
                return IbBoundMethod(self, method)
            raise AttributeError(f"Class '{self.name}' has no attribute '{attr_name}'")

        return super().receive(message, args)

    def __repr__(self):
        return f"<Class '{self.name}'>"
