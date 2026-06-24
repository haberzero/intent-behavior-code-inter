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
        # 显式持有虚表，消除对 py_obj 的动态属性依赖
        self.vtable = vtable if vtable is not None else getattr(py_obj, '_ibci_vtable', {})
        # [SECURITY] 属性访问白名单
        self.whitelist = whitelist if whitelist is not None else getattr(py_obj, '_ibci_whitelist', [])

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
            attr = self.vtable[message]
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
                    raise InterpreterError("Core Error: 'callable' class not found in registry. Builtins initialization failed? ")

                return IbNativeFunction(
                    self.vtable[target_name],
                    ib_class=callable_cls,
                    name=target_name
                )

            # [SECURITY] 仅允许访问白名单属性
            if target_name in self.whitelist:
                if hasattr(self.py_obj, target_name):
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
    持有一个作用域 (Scope)，并根据 UTS 协议通过消息传递暴露成员。
    """
    def __init__(self, name: str, scope: Any, registry: KernelRegistry):
        super().__init__(registry.get_class("module") or registry.get_class("Object"))
        self.name = name
        self.scope = scope

    def receive(self, message: str, args: List['IbObject']) -> 'IbObject':
        """
         模块级消息传递核心。
        """
        # 1. 处理 __getattr__ 协议
        if message == '__getattr__' and len(args) > 0:
            target_name = args[0].to_native()

            # 优先从 Native 虚表或实现中查找
            if hasattr(self.scope, 'receive'):
                try:
                    return self.scope.receive('__getattr__', args)
                except AttributeError:
                    pass

            # 其次查找模块级定义的变量/函数 (Scope 模式)
            if hasattr(self.scope, 'get'):
                try:
                    return self.scope.get(target_name)
                except (KeyError, AttributeError):
                    pass

        # 2. 尝试通过 IbNativeObject 的虚表直接执行 (如果是 Native 模块)
        if hasattr(self.scope, 'receive'):
            try:
                return self.scope.receive(message, args)
            except AttributeError:
                pass

        # 3. 查找模块级定义的变量/函数 (Scope 模式)
        if hasattr(self.scope, 'get'):
            try:
                return self.scope.get(message)
            except (KeyError, AttributeError):
                pass

        # 4. 后备：降级到基类公理 (如 __to_prompt__ 等)
        return super().receive(message, args)

    def __repr__(self):
        return f"<Module '{self.name}'>"
