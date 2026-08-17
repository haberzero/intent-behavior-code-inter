"""
core/runtime/objects/kernel/host_class.py

宿主类型绑定（bind class）运行期类：把裸 Python 类包装为一等 IBCI 类型。

F2 机制（与 F1 模块成员绑定同构）：
- 编译期注册 EXTERNAL_MODULE CLASS spec（member 表来自 bind class 嵌套声明 +
  impl 补充）；运行期经 STAGE 5 水化创建本类，包装裸 Python 类（``py_class``）。
- ``instantiate(args)``：调用裸 Python 类构造实例 → 包装为 IbNativeObject，
  vtable = bind 方法成员的 per-instance 绑定方法 proxy。impl 方法（STAGE 5 经
  ``register_method`` 进 ``self.methods``）不并入 vtable——经
  IbNativeObject._dispatch_getattr 的类方法回落导出为 IbBoundMethod（注入
  receiver，与用户对象方法同构）。
- bind 属性成员 → whitelist（IbNativeObject 强制 vtable/whitelist 门控）。
- bind 方法返回宿主 ``py_class`` 实例时重新包装为宿主实例（一等类型语义：
  Python datetime 就是 IBCI datetime，vtable/whitelist 契约随返回对象延续）。
"""

from typing import Dict, List, Optional, Any

from core.runtime.objects.kernel.ib_class import IbClass
from core.runtime.module_system.proxy import create_proxy


class HostClassBinding(IbClass):
    """宿主类型绑定运行期类。

    ``bind class Name: <嵌套 bind 成员>`` 绑定裸 Python 类：类型本身作
    一等 IBCI 类型（``Name(...)`` 构造 / 类型注解 / impl 目标），实例为
    IbNativeObject（持 per-instance vtable：bind 方法成员）。
    """

    __slots__ = (
        "py_class",
        "bind_method_names",
        "bind_whitelist",
        "param_meta_map",
        "object_factory",
    )

    def __init__(
        self,
        name: str,
        registry: Any,
        object_factory: Any,
        py_class: type,
        bind_method_names: List[str],
        bind_whitelist: List[str],
        param_meta_map: Dict[str, list],
    ):
        super().__init__(name, parent=None, registry=registry)
        self.py_class = py_class
        self.bind_method_names = bind_method_names
        self.bind_whitelist = bind_whitelist
        self.param_meta_map = param_meta_map
        self.object_factory = object_factory

    def _dispatch_call(self, message: str, args: List[Any]):
        """类对象 ``__call__``：宿主类型恒走 instantiate（构造裸 Python 实例）。

        覆写 IbClass._dispatch_call（其默认经 _ClassInstantiateDrive CPS 驱动
        用户类字段/__init__）——宿主类型无 IBCI 字段/__init__，直接同步实例化。
        """
        return self.instantiate(args)

    def instantiate(self, args: List[Any], context: Optional[Any] = None) -> Any:
        """实例化：调用裸 Python 类构造实例 → 包装为 IbNativeObject。

        - 构造实参 unbox（IbObject → native）。
        - vtable：bind 方法成员 = 该实例的绑定方法 proxy（per-instance）。
        - bind 属性成员 → whitelist。
        """
        py_args = []
        for a in args:
            to_native = getattr(a, "to_native", None)
            py_args.append(to_native() if to_native else a)
        py_instance = self.py_class(*py_args)
        return self._wrap_instance(py_instance)

    def _wrap_instance(self, py_instance: Any) -> Any:
        """把裸 Python 实例包装为宿主实例（IbNativeObject + per-instance vtable）。"""
        vtable: Dict[str, Any] = {}
        for mname in self.bind_method_names:
            py_bound = getattr(py_instance, mname)
            vtable[mname] = self._make_bound_proxy(
                py_bound, self.param_meta_map.get(mname, [])
            )
        return self.object_factory.create_native_object(
            py_instance,
            self,
            vtable=vtable,
            whitelist=list(self.bind_whitelist),
        )

    def _make_bound_proxy(self, py_bound: Any, param_meta: list):
        """构建 per-instance 绑定方法 proxy（F1 create_proxy + 宿主返回重包装）。

        原生方法返回值若为宿主 ``py_class`` 实例（如 ``datetime.replace`` 返回
        新 datetime），重新包装为宿主实例——否则 vtable/whitelist 契约随对象丢失
        （一等类型语义断裂）。
        """
        proxy, meta = create_proxy(py_bound, self.registry, param_meta)

        def host_proxy_wrapper(*args: Any, **kwargs: Any):
            boxed = proxy(*args, **kwargs)
            native = getattr(boxed, "py_obj", None)
            if isinstance(native, self.py_class):
                return self._wrap_instance(native)
            return boxed

        return host_proxy_wrapper, meta
