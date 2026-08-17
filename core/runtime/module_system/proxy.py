"""
core/runtime/module_system/proxy.py

Native 成员代理（unbox → 调 Python → box）的单一权威构造。

原内嵌于 ``ModuleLoader._validate_and_bind``（_spec.py 插件路径）；F1 宿主绑定
（``import python "pkg" as lib: bind ...``）也需要同一代理机制，故提取为模块级
工厂，两个绑定源（插件 metadata / 用户 IBCI bind 声明）共用——消除双通道。
"""

import inspect
from typing import Any, Callable, Optional, Tuple

from core.kernel.issue import InterpreterError
from core.runtime.objects.kernel.base import unbox


def _is_callable_object(obj: Any) -> bool:
    """判断对象是否为可调用实例（behavior / fn_callable / callable）。

    可调用实例不是数据值：应原样透传给插件实现层，而非拆箱成 native
    （未执行的可调用对象 ``to_native()`` 会显式抛错）。
    """
    cls = getattr(obj, "ib_class", None)
    if cls is None:
        return False
    name = getattr(cls, "name", "") or ""
    return (
        name in ("behavior", "fn_callable", "callable")
        or name.startswith("fn_callable[")
        or name.startswith("behavior[")
    )


def create_proxy(
    target_func: Callable,
    reg: Any,
    param_meta: Optional[list],
    has_declared_varkw: bool = False,
) -> Tuple[Callable, Optional[list]]:
    """构造 (proxy_wrapper, param_meta)：把 Python callable 包装为 IBCI 成员代理。

    - unbox：IbObject → native（可调用实例原样透传）。
    - 绑定器把 ``**kwargs`` 归集的 dict 装箱为声明序末位的位置实参；声明了
      VAR_KEYWORD 时把它分传为 ``**kwargs`` 交给原生实现。
    - 调用原生函数后把结果 ``reg.box`` 回装箱。
    """
    def _unbox(value):
        # UTS: 自动拆箱 (IbObject -> Native)
        # 可调用实例（behavior/fn_callable/callable）不是数据值，
        # 原样透传，避免误拆箱触发未执行 callable 的 to_native() 抛错。
        if _is_callable_object(value):
            return value
        return unbox(value)

    def proxy_wrapper(*args, **kwargs):
        if has_declared_varkw and args:
            positional, varkw_arg = args[:-1], args[-1]
        else:
            positional, varkw_arg = args, None

        native_args = [_unbox(a) for a in positional]
        native_kwargs = {k: _unbox(v) for k, v in kwargs.items()}
        if varkw_arg is not None:
            varkw_fields = getattr(varkw_arg, "fields", None)
            if isinstance(varkw_fields, dict):
                varkw_items = varkw_fields.items()
            elif isinstance(varkw_arg, dict):
                varkw_items = varkw_arg.items()
            else:
                raise InterpreterError(
                    f"Host binding: member expected **kwargs dict, "
                    f"got {type(varkw_arg).__name__}."
                )
            for k, v in varkw_items:
                native_kwargs[k] = _unbox(v)

        result = target_func(*native_args, **native_kwargs)
        return reg.box(result)

    return proxy_wrapper, param_meta
