from typing import Callable, Optional, List, Any

from core.base.enums import RegistrationState
from core.kernel.issue import InterpreterError
from core.kernel.spec import IbSpec
from core.runtime.exceptions import ThrownException

from .base import IbObject, unbox


class IbFunction(IbObject):
    """
    可调用对象的基类 (语言层表现为 callable)。
    """
    def __init__(self, ib_class: 'IbClass'):
        super().__init__(ib_class)

    def call(self, receiver: IbObject, args: List[IbObject]) -> IbObject:
        raise NotImplementedError()

class IbNativeFunction(IbFunction):
    """
    包装 Python 原生函数的 IBC 函数。
    用于引导阶段注入基础运算（如 int.__add__）。
    """
    def __init__(self, py_func: Callable, unbox_args: bool = False, is_method: bool = False, ib_class: Optional['IbClass'] = None, name: Optional[str] = None, logic_id: Optional[str] = None, spec: Optional[IbSpec] = None, param_meta: Optional[List[Any]] = None):
        # 强制绑定到协议类，移除静默兜底
        reg = ib_class.registry if ib_class else None
        target_class = ib_class

        if not target_class and reg:
            if reg.state_level >= RegistrationState.STAGE_2_CORE_TYPES.value:
                target_class = reg.get_class("callable")
                if not target_class and reg.state_level >= RegistrationState.STAGE_4_PLUGIN_IMPL.value:
                    raise InterpreterError(f"Core Error: 'callable' class missing during STAGE {RegistrationState(reg.state_level).name}. ")

        super().__init__(target_class)
        self.py_func = py_func
        self.unbox_args = unbox_args
        self.is_method = is_method
        self.logic_id = logic_id
        self._name = name or (py_func.__name__ if hasattr(py_func, '__name__') else "anonymous")
        self._spec = spec
        # 声明参数元数据（(name, kind, default_src) 序列），供统一实参绑定器做具名/默认解析
        self.param_meta = param_meta

    @property
    def spec(self) -> Optional[IbSpec]:
        return self._spec if self._spec is not None else self.ib_class.spec

    def call(self, receiver: IbObject, args: List[IbObject]) -> IbObject:
        # 如果 py_func 本身就是 IbObject (例如是一个 Proxy)，直接转发消息
        if isinstance(self.py_func, IbObject):
            return self.py_func.receive('__call__', args)

        final_args = args
        if self.unbox_args:
            final_args = [unbox(arg) for arg in args]

        try:
            if self.is_method:
                res = self.py_func(receiver, *final_args)
            else:
                res = self.py_func(*final_args)
            return self.ib_class.registry.box(res)
        except Exception as e:
            if isinstance(e, InterpreterError):
                raise
            # ThrownException 是用户代码主动抛出的语言级异常（如
            # LLMParseError 等），必须穿透原生函数边界，由 IbTry / 顶层
            # try-except 体系处理；不可被包装为 InterpreterError。
            if isinstance(e, ThrownException):
                raise
            raise InterpreterError(f"Native function '{self._name}' failed: {e}") from e


class IbBoundMethod(IbFunction):
    """绑定了接收者的函数 (模拟 C++ 虚表调用的 this 绑定)"""
    def __init__(self, receiver: Optional[IbObject], method: IbFunction):
        # 优先查找 bound_method 类，如果没注册（如引导期）则回退到 callable
        cls = method.ib_class.registry.get_class("bound_method") or method.ib_class.registry.get_class("callable")
        super().__init__(cls)
        self.receiver = receiver
        self.method = method

    @property
    def spec(self) -> Optional[IbSpec]:
        """Synthesise a TypeDef for this bound method."""
        spec_reg = self.ib_class.registry.get_metadata_registry()
        if spec_reg:
            r_name = self.receiver.ib_class.name if self.receiver else ""
            m_name = self.method.ib_class.name
            return spec_reg.factory.create_bound_method(r_name, m_name)
        return self.ib_class.spec

    def call(self, _receiver: IbObject, args: List[IbObject]) -> IbObject:
        if self.receiver is None:
            raise InterpreterError("BoundMethod has no receiver (initialization failed or corrupt snapshot)")
        return self.method.call(self.receiver, args)

    def __repr__(self):
        return f"<BoundMethod {self.method} bound to {self.receiver}>"


class IbSuperProxy(IbObject):
    """
    super() 代理对象。

    在 IBCI 方法体内调用 super() 时创建此对象。
    - receiver：当前 self（方法接收者）
    - owner_class：定义当前方法的类（编译期/hydration 期绑定）
    - parent_class：owner_class 的父类，方法查找从此处开始

    使用方式：
        super().method_name(args)  ← super() 返回此代理；.method_name 通过 __getattr__ 返回绑定了 receiver 的父类方法
    """
    def __init__(self, receiver: IbObject, parent_class: Optional['IbClass']):
        # 借用 callable class 作为宿主类型（super() 是纯运行时内核概念，无对应 axiom）
        ib_cls = receiver.ib_class.registry.get_class("callable") or receiver.ib_class
        super().__init__(ib_cls)
        self._receiver = receiver
        self._parent_class = parent_class

    def receive(self, message: str, args: List['IbObject']) -> 'IbObject':
        if message == '__getattr__' and args:
            attr_name = args[0].to_native()
            if self._parent_class:
                method = self._parent_class.lookup_method(attr_name)
                if method:
                    return IbBoundMethod(self._receiver, method)
            raise AttributeError(f"super(): parent class has no method '{attr_name}'")
        if message == '__call__':
            # super() called directly (not super().method()) — not meaningful; return self
            return self
        raise AttributeError(f"super() proxy does not support message '{message}'")

    def __repr__(self):
        parent_name = self._parent_class.name if self._parent_class else "<no parent>"
        return f"<super: <class '{parent_name}'>, <{self._receiver.ib_class.name} object>>"
