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


class _UserCallDrive:
    """用户类实例协议方法（``__call__`` 等）的帧内 CPS 驱动 Waitable。

    由 :meth:`IbObject.receive` 对"含用户定义协议方法的类实例"返回；VM
    ``vm_handle_IbCall`` 识别其为 ``Waitable`` + ``CPSDrivable`` 后 ``yield from
    cps_drive``——用户方法经 ``UserFunctionCall`` trampoline 压栈帧内驱动
    （替代 ``method.call`` 新建嵌套 TaskScheduler：EXEC-1 深递归 Python 深度
    恒定的保证恢复、方法含 Waitable 时由调度器协作挂起而非阻塞主线程）。
    宿主/线程体无活跃 VM 时 ``try_result``/``result`` 走同步 ``_drive_generator``
    兜底（与 :class:`_ClassInstantiateDrive` 同构）。

    ``receive`` 保持唯一协议分派入口（返回本 drive，而非 VM 侧加特判分支）。
    """

    def __init__(self, method, args, receiver):
        self._method = method
        self._args = args
        self._receiver = receiver
        self._done = False
        self._result = None

    @property
    def is_done(self) -> bool:
        return self._done

    def _drive(self):
        # 宿主同步兜底：委托 IbUserFunction.call（现对生成器方法返回 IbGenerator、
        # 普通方法经 _drive_generator 驱动），与 VM 主路径语义对齐——避免本类
        # 再实现一份生成器/普通分派（消双写）。
        self._result = self._method.call(self._receiver, self._args)
        self._done = True
        return self._result

    def cps_drive(self, executor):
        from core.runtime.shared.user_call import UserFunctionCall
        from core.runtime.objects.kernel.generator import IbGenerator

        call = UserFunctionCall(self._method, self._args, self._receiver)
        # 生成器方法：_drive_loop_gen 经 make_generator_driver 返回驱动生成器，
        # 包装为 IbGenerator（与 VM 主路径 vm_handle_IbCall 的 is_generator 分支
        # 同构），不驱动函数体。普通方法：trampoline 压栈驱动到完成。
        if getattr(self._method, "is_generator", False):
            driver = yield call
            gen_class = executor.registry.get_class("generator")
            if gen_class is None:
                raise RuntimeError("generator class not registered (bootstrap invariant violated)")
            self._result = IbGenerator(gen_class, driver)
            self._done = True
            return self._result
        self._result = yield call
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

    @property
    def module_path(self) -> Optional[str]:
        """类的模块限定（自 spec 派生，单点真理）。"""
        return self._spec.module_path if self._spec is not None else None

    @property
    def qualified_name(self) -> str:
        """运行期类注册键：module_path 非空时 ``f"{module}.{name}"``，否则裸名。

        与编译期 spec 身份 ``(module_path, name)`` 对齐——跨模块同名类
        （geo.Box / graph.Box）以此区分，消除运行期类表裸名坍缩。IbClass.name
        保留裸名（type() 显示 / 方法查找 / _impl_cls）。
        """
        mp = self.module_path
        return f"{mp}.{self.name}" if mp else self.name

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

    def _impl_cls(self) -> Any:
        """解析值对象的 Python 实现类。

        优先按类名精确匹配（``get_ib_implementation(name)``）；特化类
        （``list[int]`` / ``Box[int]``）的 name 无直接实现注册，沿 spec 基类名
        解析（LIST kind → ``list`` 等，经 ``get_base_name``），使特化类实例化
        复用基类实现（机制同构于用户类泛型特化类的父链继承）。
        """
        impl = get_ib_implementation(self.name)
        if impl is not None:
            return impl
        if self._spec is not None:
            base = self._spec.get_base_name()
            impl = get_ib_implementation(base)
            if impl is not None:
                return impl
        return None

    def instantiate(self, args: List[IbObject], context: Optional['IExecutionContext'] = None) -> IbObject:
        # 值对象类型化构造钩子：实现类覆写 _create_blank 则产生
        # 其类型化实例（如 IbThread），否则默认普通 IbObject（既有行为）。
        impl_cls = self._impl_cls()
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

    def _wrap_field_value(self, name: str, value: Any) -> Any:
        """按字段声明类型包装 Optional 值（统一 Optional 值模型）。

        字段声明为 ``Optional[T]`` 时，写入前按字段类型包装空值
        （``IbOptional(is_some=False)``），与局部变量/参数/返回路径一致。
        字段类型经 ``member_types`` 缓存（spec.members 水化时填充）——
        沿继承链向上查找（子类字段 / 父类字段均命中），避免继承字段漏包装。
        无缓存 / 非 Optional 原样返回。
        """
        field_spec = None
        cls = self
        while cls is not None:
            field_spec = getattr(cls, "member_types", {}).get(name)
            if field_spec is not None:
                break
            cls = cls.parent
        if field_spec is None:
            return value
        from core.runtime.objects.primitives.optional import wrap_optional

        return wrap_optional(value, field_spec, self.registry)

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
                    # 避免所有实例共享同一容器对象。用递归深克隆（try_deep_clone）——
                    # 补全"每实例独立默认值"的既有意图：此前仅 list/dict 首层浅拷贝，
                    # 内层 list 与用户对象默认值跨实例共享（静默泄漏）。
                    # 深克隆失败（函数/行为等不可克隆）→ 回退共享引用（值语义等价）。
                    from core.runtime.objects.deep_clone import try_deep_clone
                    cloned = try_deep_clone(val_info.static_val)
                    if cloned is not None:
                        instance.fields[name] = self._wrap_field_value(name, cloned)
                    else:
                        instance.fields[name] = self._wrap_field_value(name, val_info.static_val)
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
                        instance.fields[name] = self._wrap_field_value(name, evaluated)
                        val_info.static_val = evaluated
                    except Exception as e:
                        # 实例化时字段默认值求值失败是真实错误——fail-fast，
                        # 静默置 None 会掩盖初始化 bug 产生错误对象。
                        raise InterpreterError(
                            f"Field initializer for '{name}' failed: {e}",
                        ) from e
                else:
                    instance.fields[name] = self._wrap_field_value(
                        name, self.registry.get_none()
                    )
            else:
                # [Active Defense] 仅支持 IbClassField，确保字段初始化的一致性
                instance.fields[name] = self._wrap_field_value(name, val_info)

    def _init_expected_arity(self, init_method) -> Optional[int]:
        """``__init__`` 声明的非 self 参数数量（成员表权威；None=无法判定跳过校验）。

        成员表（MethodMemberSpec.param_types）恒不含 self——编译期单一权威。
        方法函数 spec 经阶段 B1 统一为同样不含 self（与成员表同构），spec 回退
        直接取参数数量，无 self 偏移判定。
        """
        member = (getattr(self.spec, "members", None) or {}).get("__init__")
        if member is not None and getattr(member, "param_types", None) is not None:
            return len(member.param_types)
        spec = getattr(init_method, "spec", None)
        if spec is None or spec.kind not in (TypeKind.FUNCTION.value, TypeKind.CALLABLE_SIG.value):
            return None
        return len(spec.param_types or [])

    def _invoke_init(self, instance: 'IbObject', args: List['IbObject']) -> None:
        """调用用户 ``__init__``（宿主侧 ``init_method.call``）。

        契约校验 ``__init__`` 参数数量；无 ``__init__`` 却传参视为契约违背。
        已知问题：``init_method.call`` 为宿主侧薄包装（``_vm_call_user_function``
        + ``_drive_generator`` 新建 TaskScheduler），``__init__`` 含 Waitable 时
        会阻塞主调度线程（类构造未接入 VM 帧内 CPS 驱动）。
        """
        init_method = self.lookup_method('__init__')
        if init_method:
            # 契约一致性校验：校验 __init__ 参数数量（成员表权威，见
            # _init_expected_arity——方法 spec 现为函数 spec，签名校验生效）
            expected_count = self._init_expected_arity(init_method)
            if expected_count is not None and len(args) != expected_count:
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
        impl_cls = self._impl_cls()
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
                    # 递归深克隆可变默认值（与 _eval_field_defaults 同步版一致）：
                    # 补全每实例独立默认值意图；不可克隆 → 共享引用。
                    from core.runtime.objects.deep_clone import try_deep_clone
                    cloned = try_deep_clone(val_info.static_val)
                    if cloned is not None:
                        instance.fields[name] = self._wrap_field_value(name, cloned)
                    else:
                        instance.fields[name] = self._wrap_field_value(name, val_info.static_val)
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
                    instance.fields[name] = self._wrap_field_value(name, evaluated)
                    val_info.static_val = evaluated
                else:
                    instance.fields[name] = self._wrap_field_value(
                        name, self.registry.get_none()
                    )
            else:
                instance.fields[name] = self._wrap_field_value(name, val_info)

    def _invoke_init_cps(self, instance: 'IbObject', args: List['IbObject']) -> Any:
        """CPS 版 :meth:`_invoke_init`：用户 ``__init__`` 经 ``UserFunctionCall`` 帧内驱动。"""
        from core.runtime.shared.user_call import UserFunctionCall
        from .user_functions import IbUserFunction

        init_method = self.lookup_method('__init__')
        if init_method:
            # 契约一致性校验：校验 __init__ 参数数量（同 _invoke_init）
            expected_count = self._init_expected_arity(init_method)
            if expected_count is not None and len(args) != expected_count:
                raise InterpreterError(f"TypeError: {self.name}.__init__() expected {expected_count} arguments, but got {len(args)}")

            if isinstance(init_method, IbUserFunction):
                yield UserFunctionCall(init_method, args, instance)
            else:
                init_method.call(instance, args)
        elif args:
            raise InterpreterError(f"TypeError: {self.name}() takes no arguments, but {len(args)} were given")

    def _slice_type_objs(self, slice_obj: 'IbObject') -> List['IbObject']:
        """从类型特化下标 slice 提取类型标识对象列表。

        ``Box[int]`` → [int 类对象]；``Pair[str,int]`` → [str, int]（IbTuple
        经 to_native 得 tuple）。非类型下标（普通值下标）返回 []。
        """
        if isinstance(slice_obj, IbClass):
            return [slice_obj]
        try:
            native = slice_obj.to_native()
        except Exception:
            return []
        if isinstance(native, tuple):
            items = native
        elif isinstance(native, list):
            items = native
        else:
            return [slice_obj]
        out = []
        for it in items:
            if isinstance(it, IbClass):
                out.append(it)
            else:
                out.append(self.registry.box(it))
        return out

    def _specialize(self, type_objs: List['IbObject']) -> 'IbObject':
        """类型特化下标 ``Box[int]`` → 特化类对象（IbClass）。

        ``Box[int]`` 表达式中 slice ``int`` 求值为类型标识（IbClass）。据此
        拼接特化名 ``"Box[int]"`` 并从注册表查/建特化类：

        - 已注册（编译期 resolve_specialization + artifact rehydrate 已建
          特化 spec 与 IbClass）→ 直接返回。
        - 未注册（无编译期特化、运行时首次遇到）→ 从 metadata registry
          解析特化 spec 并 ``create_subclass``。
        - 内置泛型类（list/dict/Optional 等）作下标（``list[int]`` 表达式、
          ``Box[list[int]]`` 嵌套实参）→ 水化为特化类（缺陷二根治：内置泛型
          特化 spec 与用户类泛型同构地水化为运行时特化类）。
        - 非泛型类下标（Box[42]）→ AttributeError（不是类型特化）。
        """
        if not type_objs:
            raise AttributeError(
                f"Class '{self.name}' subscript expects type identifier(s) "
                f"(e.g. {self.name}[int]), got a value."
            )
        type_names = [self._type_ref_name(o) for o in type_objs]
        if any(n is None for n in type_names):
            raise AttributeError(
                f"Class '{self.name}' subscript expects type identifier(s) "
                f"(e.g. {self.name}[int]), got a value."
            )
        # 特化名带 module 限定（geo.Box[int]）：与运行期类表 qualified 键对齐，
        # 跨模块同名类特化不坍缩（S5 运行期根治）。
        specialized_name = f"{self.qualified_name}[{','.join(type_names)}]"
        existing = self.registry.get_class(specialized_name)
        if existing is not None:
            return existing

        spec_reg = self.registry.get_metadata_registry()
        specialized_spec = spec_reg.resolve(specialized_name) if spec_reg else None
        if specialized_spec is None:
            # 无 type_params 的内置泛型类（list/dict/Optional 等）作嵌套实参
            # （``Box[list[int]]``）：编译期未注册特化 spec 时，boxed 特化名
            # 字符串供外层特化提取（保留既有契约）。
            if not self._spec or not getattr(self._spec, "type_params", None):
                type_names_b = [self._type_ref_name(o) for o in type_objs]
                if all(n is not None for n in type_names_b) and type_names_b:
                    return self.registry.box(f"{self.name}[{','.join(type_names_b)}]")
            raise AttributeError(
                f"Class '{self.name}' is not generic; cannot subscript it."
            )
        # 内置泛型特化类（list[int]）：水化阶段（loader）已预创建；此处仅作
        # 兜底。registry 已封印时不可 create_subclass——回落 boxed 特化名
        # 字符串（嵌套实参语义：供外层特化提取），不抛错（与既有 boxed 路径
        # 行为一致；水化阶段缺失的类表示该特化未在编译产物中使用）。
        if not getattr(self._spec, "type_params", None):
            if self.registry.is_sealed:
                return self.registry.box(specialized_name)
            base_cls = self.registry.get_class(self.name)
            if base_cls is not None:
                try:
                    return self.registry.create_subclass(
                        specialized_name, specialized_spec, self.name
                    )
                except Exception:
                    return self.registry.box(specialized_name)
        # 父类：若 parent_type 带泛型实参（class Sub[T](Box[T]) → Box[int]），
        # parent 类名须用特化名（继承链对齐特化类，非裸基类）。父类与子类同模块
        # （parser 仅支持单标识符父名）；parent_type 缺 module 时权威解析——
        # 内置泛型父（list[T] 等，module 恒 None）不加前缀；同模块用户父以特化
        # spec 的 module 补全，使 ``get_class`` 命中 qualified 键。
        if specialized_spec.parent_type is not None and specialized_spec.parent_type.args:
            p_ref = specialized_spec.parent_type
            if p_ref.module is None:
                parent_module = self.registry.resolve_class_module(
                    p_ref.head, specialized_spec.module_path
                )
                if parent_module:
                    p_ref = p_ref.with_module(parent_module)
            parent_name = p_ref.qualified_name
        elif not getattr(self._spec, "type_params", None):
            # 内置泛型特化类（list[int]）的 parent = 基类（list）——特化类
            # 继承基类实现与方法（get_ib_implementation 沿基类名解析）。
            parent_name = self.name
        elif specialized_spec.parent_type is not None:
            p_ref = specialized_spec.parent_type
            if p_ref.module is None:
                parent_module = self.registry.resolve_class_module(
                    p_ref.head, specialized_spec.module_path
                )
                if parent_module:
                    p_ref = p_ref.with_module(parent_module)
            parent_name = p_ref.qualified_name
        else:
            parent_name = "Object"
        return self.registry.create_subclass(
            specialized_name, specialized_spec, parent_name
        )

    @staticmethod
    def _type_ref_name(type_obj: 'IbObject') -> Optional[str]:
        """从类型标识对象取类型名（IbClass → name；原生类型对象 → str）。"""
        if isinstance(type_obj, IbClass):
            return type_obj.name
        try:
            native = type_obj.to_native()
        except Exception:
            return None
        if isinstance(native, str):
            return native
        return None

    def receive(self, message: str, args: List['IbObject']) -> 'IbObject':
        """
        类对象的特殊消息处理（协议处理器覆写，见 ``_dispatch_*``）：
        1. __call__ -> 实例化 (Instantiate) 或 类级别的 __call__
        2. __getattr__ -> 访问类字段 (default_fields)
        3. __getitem__ -> 泛型类型特化下标（Box[int] → 特化类对象）
        4. 其他 -> 正常消息处理 (查找静态方法等)
        """
        return super().receive(message, args)

    def _dispatch_call(self, message: str, args: List['IbObject']):
        """类对象 ``__call__``：类自身原生 __call__ 优先，否则实例化。"""
        from .functions import IbNativeFunction

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

    def _dispatch_getitem(self, message: str, args: List['IbObject']):
        """类对象 ``__getitem__``：类型特化下标（``Box[int]`` 表达式）。"""
        if len(args) > 0:
            # slice 求值为类型标识（IbClass，如 int 类对象）或类型元组
            # （``Pair[str,int]``）→ 查/建特化类。
            type_objs = self._slice_type_objs(args[0])
            return self._specialize(type_objs)
        return None

    def _dispatch_getattr(self, message: str, args: List['IbObject']):
        """类对象 ``__getattr__``：类字段 (default_fields) → 类方法。"""
        from .functions import IbBoundMethod

        if len(args) > 0:
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
        return None

    def __repr__(self):
        return f"<Class '{self.name}'>"
