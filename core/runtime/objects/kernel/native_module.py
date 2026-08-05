from typing import Any, Optional, Dict, List

from core.kernel.registry import KernelRegistry
from core.base.enums import RegistrationState
from core.kernel.issue import InterpreterError
from core.runtime.exceptions import RegistryIsolationError

from ..ib_type_mapping import register_ib_type
from .base import IbObject
from .functions import IbNativeFunction


class IbNativeObject(IbObject):
    """
    包装 Python 原生对象的 IBC 对象。
    用于桥接 Python 扩展和标准库。
    """
    def __init__(self, py_obj: Any, ib_class: 'IbClass', vtable: Optional[Dict[str, Any]] = None, whitelist: Optional[List[str]] = None):
        super().__init__(ib_class)
        self.py_obj = py_obj
        # 显式持有虚表与属性白名单（由 InterOp.bind_native_contract 承载，无私有属性注入）
        self.vtable = vtable or {}
        self.whitelist = whitelist or []

    def get(self, name: str) -> Any:
        """模块作用域协议成员访问：经 ``receive('__getattr__')`` 分发。

        与 ``ScopeImpl.get`` 对齐——不存在抛 ``KeyError``。
        """
        try:
            return self.receive('__getattr__', [self.ib_class.registry.box(name)])
        except AttributeError:
            raise KeyError(name)

    def receive(self, message: str, args: List['IbObject']) -> 'IbObject':
        """
         Native 消息分发核心。
        强制通过虚表映射，禁止任何非预期的 Python 属性穿透。
        """
        # [Registry Isolation] 校验对象所属 Registry 身份
        if hasattr(self.py_obj, '_ibci_registry_id'):
            if self.py_obj._ibci_registry_id != id(self.ib_class.registry):
                raise RegistryIsolationError(f"Security Violation: Native object from another engine instance detected. ")

        # 1. 如果消息本身就在虚表中 (方法直接调用)
        if message in self.vtable:
            attr = self.vtable[message][0]
            # Proxy VTable 由 ModuleLoader 完成自动装箱转换
            return attr(*args)

        # 2. 处理 __getattr__ 协议 (属性/方法获取)
        if message == '__getattr__' and len(args) > 0:
            target_name = args[0].to_native()

            # 如果是虚表方法，包装为 IbNativeFunction 导出
            if target_name in self.vtable:
                reg = self.ib_class.registry
                # 强制通过 Gatekeeper 获取协议类
                reg.verify_level_at_least(RegistrationState.STAGE_2_CORE_TYPES.value)

                callable_cls = reg.get_class("callable")
                if not callable_cls:
                    # 如果进入了插件加载阶段（STAGE 4+），callable 缺失属于严重初始化错误
                    reg.verify_level_at_least(RegistrationState.STAGE_4_PLUGIN_IMPL.value)
                    raise InterpreterError("Core Error: 'callable' class not found in registry. Primitive initialization failed? ")

                func, param_meta = self.vtable[target_name]
                return IbNativeFunction(
                    func,
                    ib_class=callable_cls,
                    name=target_name,
                    param_meta=param_meta,
                )

            # [SECURITY] 仅允许访问白名单属性
            # 白名单成员已在绑定期校验实现对象必须含该属性（loader._validate_and_bind），
            # 此处直接 getattr；缺失即抛契约异常。
            if target_name in self.whitelist:
                return self.ib_class.registry.box(getattr(self.py_obj, target_name))

            # 未在契约或白名单声明的成员，坚决抛出异常
            raise AttributeError(f"Plugin Error: '{target_name}' is not defined in module contract (_spec.py)")

        # 3. 降级到基类公理 (如 __to_prompt__ 等)
        return super().receive(message, args)

    def to_native(self, memo: Optional[Dict[int, Any]] = None) -> Any:
        return self.py_obj

    def __repr__(self):
        return f"<NativeObject {self.py_obj}>"

@register_ib_type("module")
class IbModule(IbObject):
    """
    IBC-Inter 模块对象。
    持有一个作用域 (IModuleScope)，并根据 UTS 协议通过消息传递暴露成员。
    """
    def __init__(self, name: str, scope: 'IModuleScope', registry: KernelRegistry):
        super().__init__(registry.get_class("module") or registry.get_class("Object"))
        self.name = name
        self.scope = scope

    def receive(self, message: str, args: List['IbObject']) -> 'IbObject':
        """
         模块级消息传递核心。
         经 ``IModuleScope`` 协议统一分派（scope 两形态均实现 get/receive）。
        """
        scope = self.scope  # IModuleScope

        # 1. 处理 __getattr__ 协议（成员访问统一走 scope.get）
        if message == '__getattr__' and len(args) > 0:
            target_name = args[0].to_native()
            try:
                return scope.get(target_name)
            except KeyError:
                pass

        # 2. 其他消息经 scope.receive 转发（两形态均实现）
        try:
            return scope.receive(message, args)
        except (KeyError, AttributeError):
            pass

        # 3. 后备：降级到基类公理 (如 __to_prompt__ 等)
        return super().receive(message, args)

    def __repr__(self):
        return f"<Module '{self.name}'>"
