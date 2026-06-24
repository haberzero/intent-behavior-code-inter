from typing import Optional, Dict, Mapping, Any, List, TYPE_CHECKING

from core.kernel.registry import KernelRegistry
from core.kernel.issue import InterpreterError
from core.kernel.spec import IbSpec, TypeKind
from core.base.diagnostics.debugger import CoreModule, DebugLevel, core_debugger

from ..ib_type_mapping import register_ib_type
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
        instance = IbObject(self)

        # Bug D 修复：收集完整的字段继承链（父类字段 + 子类字段）
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
                        core_debugger.trace(
                            CoreModule.INTERPRETER, DebugLevel.BASIC,
                            f"Field initializer for '{name}' failed: {e}"
                        )
                        instance.fields[name] = self.registry.get_none()
                else:
                    instance.fields[name] = self.registry.get_none()
            else:
                # [Active Defense] 仅支持 IbClassField，确保字段初始化的一致性
                instance.fields[name] = val_info

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

        return instance

    def receive(self, message: str, args: List['IbObject']) -> 'IbObject':
        """
        类对象的特殊消息处理：
        1. __call__ -> 实例化 (Instantiate) 或 类级别的 __call__
        2. __getattr__ -> 访问类字段 (default_fields)
        3. 其他 -> 正常消息处理 (查找静态方法等)
        """
        from .functions import IbBoundMethod
        if message == "__call__":
            # 类作为构造器调用时，始终使用 instantiate 创建新实例。
            # 用户定义的 __call__ 是实例方法（使实例可调用），不覆盖构造器。
            # 实例的 __call__ 通过 IbObject.receive 中的 vtable 查找分发。
            context = self.registry.get_execution_context()
            return self.instantiate(args, context=context)

        if message == "__getattr__" and len(args) > 0:
            attr_name = args[0].to_native()
            # 优先查找类字段 (default_fields)
            if attr_name in self.default_fields:
                val_info = self.default_fields[attr_name]
                if val_info is not None:
                    if hasattr(val_info, 'static_val') and val_info.static_val is not None:
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
