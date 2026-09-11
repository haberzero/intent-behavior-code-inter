"""HOST-EXT：用户 Python 扩展协议（架构 v2 R4，用户战略点①）。

**目标**：保留"用户写 Python 代码实现自己的功能/逻辑"的易用性——协议化为一等
宿主扩展，IBCI 代码可 ``import`` 并调用。

**用法**（首次执行前注册）：
    from core.host_ext import register_host_extension

    class MyExt:
        def double(self, x: int) -> int:
            return x * 2

    engine = IBCIEngine(root_dir="...")
    register_host_extension(engine, "myext", MyExt())
    engine.run_string("import myext\\nprint(myext.double(21))\\n", silent=True)

**机制**（复用既有宿主模块装配链，零碎片）：
1. 构造期：从实现对象成员签名**自动构建 IBCI TypeDef**（inspect 内省：
   Python 类型注解 → IBCI TypeRef；无注解 = any 动态）→
   ``HostInterface.register_module(name, implementation, metadata=spec)``。
2. 编译期：scheduler 对元数据注册表中有 MODULE kind TypeDef 的模块跳过文件
   解析（scheduler.py resolve 路径）。
3. 装配期：module_loader.load_and_register_all 对有实现的模块自动绑定
   vtable/白名单（interop.bind_native_contract）。
4. 运行期：import_module → interop.get_package → IbNativeObject（vtable 分发）
   → ``myext.double(21)`` 调用 Python 实现。

**值转换契约**（P2 typed 精神）：IBCI 实参经 VM 宿主调用路径解箱为 Python
原生值；返回值经 registry.box 装箱回 IBCI 值（原生标量/容器直通；其余 =
宿主对象句柄）。扩展函数异常 → InterpreterError（宿主面错误契约）。

**生命周期**：模块注册 = engine 级（跨会话复用经注册器）；函数 = 普通 Python
callable（无 unsafe 句柄注册表）。
"""

from __future__ import annotations

import inspect
from typing import Any, Dict, List, Optional, Tuple, get_args, get_origin

from core.base.enums import Provenance, Visibility
from core.kernel.spec import (
    MethodMemberSpec,
    ParamDescriptor,
    TypeDef,
    TypeKind,
    TypeRef,
)

# Python 类型 → IBCI 类型名（基础映射；无注解/未知 = any 动态）
_PRIMITIVE_TYPES = {
    int: "int",
    str: "str",
    float: "float",
    bool: "bool",
    list: "list",
    dict: "dict",
}


def _py_type_to_ibci(annotation: Any, *, is_return: bool = False) -> str:
    """Python 类型注解 → IBCI 类型名（容器泛型 → list[T]/dict[K,V]；显式
    ``-> None`` = void[仅返回]；无注解/未知 = any 动态）。"""
    if annotation is inspect.Parameter.empty or annotation is Any:
        return "any"  # 无注解 = 动态（参数与返回同；显式 None 才 = void）
    if annotation is type(None):  # 显式 None 返回 = void
        return "void" if is_return else "any"
    if annotation in _PRIMITIVE_TYPES:
        return _PRIMITIVE_TYPES[annotation]
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin in (list, List) and args:
        return f"list[{_py_type_to_ibci(args[0])}]"
    if origin in (dict, Dict) and len(args) == 2:
        return f"dict[{_py_type_to_ibci(args[0])},{_py_type_to_ibci(args[1])}]"
    if origin in (tuple, Tuple):
        return "tuple"
    if origin in (Optional,):
        return "any"  # Optional 包装 = 动态面（IBCI Optional 值语义）
    # 未知类型 = 动态（保持易用性——类型检查放宽，运行期按值面）
    return "any"


def _build_members(implementation: Any) -> Dict[str, MethodMemberSpec]:
    """从实现对象成员签名自动构建 MethodMemberSpec 表。

    仅收集公开方法（非 ``_`` 开头）；绑定方法去掉 self；参数 = 位置或
    关键字（默认值 → has_default）。返回注解缺失 → any（动态）。
    """
    members: Dict[str, MethodMemberSpec] = {}
    for name in dir(implementation):
        if name.startswith("_"):
            continue
        attr = getattr(implementation, name)
        if not callable(attr):
            continue
        try:
            sig = inspect.signature(attr)
        except (TypeError, ValueError):
            continue
        params = [
            p
            for p in sig.parameters.values()
            if p.name != "self"
            and p.kind
            in (p.POSITIONAL_OR_KEYWORD, p.POSITIONAL_ONLY, p.KEYWORD_ONLY)
        ]
        param_types = [_py_type_to_ibci(p.annotation) for p in params]
        ret = _py_type_to_ibci(sig.return_annotation, is_return=True)
        descriptors = [
            ParamDescriptor(
                name=p.name,
                kind=(
                    "KEYWORD_ONLY"
                    if p.kind == p.KEYWORD_ONLY
                    else "POSITIONAL_OR_KEYWORD"
                ),
                type_ref=TypeRef.of(_py_type_to_ibci(p.annotation)),
                has_default=p.default is not p.empty,
                default_value=None if p.default is p.empty else p.default,
            )
            for p in params
        ]
        members[name] = MethodMemberSpec(
            name=name,
            kind="method",
            type_ref=TypeRef.of(ret),
            param_types=[TypeRef.of(t) for t in param_types],
            return_type=TypeRef.of(ret),
            param_descriptors=descriptors,
        )
    return members


def register_host_extension(
    engine,
    name: str,
    implementation: Any,
    *,
    description: str = "",
) -> None:
    """注册用户 Python 扩展模块（IBCI 可 import + 调用）。

    须在引擎**首次执行前**调用（注册进 host_interface 元数据注册表 +
    实现；装配期 loader 自动绑定 vtable）。IBCI 侧用法：
    ``import <name>`` → ``<name>.<member>(<args>)``。

    :param engine: IBCIEngine 实例（构造后、首次 run 前）
    :param name: IBCI 模块名（import 名）
    :param implementation: Python 对象（方法 = 扩展函数，签名注解 → IBCI 类型）
    :param description: 模块描述（元数据）
    """
    if getattr(engine, "interpreter", None) is not None:
        raise RuntimeError(
            "register_host_extension 须在引擎首次执行前调用"
            "（registry 密封后无法注册新模块）。"
        )
    members = _build_members(implementation)
    if not members:
        raise ValueError(
            f"register_host_extension: '{name}' 无可公开方法"
            "（须至少一个非 _ 开头的方法）。"
        )
    spec = TypeDef(
        name=name,
        kind=TypeKind.MODULE.value,
        provenance=Provenance.USER_DEFINED,
        visibility=Visibility.IMPORT_GATED,
        members=members,
    )
    engine.host_interface.register_module(name, implementation, metadata=spec)
