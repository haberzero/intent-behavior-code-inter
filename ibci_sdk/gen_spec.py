"""
ibci_sdk/gen_spec.py

自动从 Python 类生成 _spec.py 内容。

利用 inspect + typing.get_type_hints() 提取方法签名和实例变量，
自动映射到 ibci 类型系统并生成 __ibcext_vtable__ 函数体。

限制：
- 仅支持 Python 内置类型到 ibci 基础类型的映射（str/int/float/bool/list/dict/None）
- 复杂类型（Optional[X]、Union[X,Y]）映射为 "any"
- 不解析 *args / **kwargs（变参在 ibci 中不支持）

用法：
    from ibci_sdk.gen_spec import gen_spec, gen_spec_file

    class MyPlugin:
        def hello(self, name: str) -> str: ...
        def add(self, a: int, b: int) -> int: ...

    print(gen_spec(MyPlugin, name="myplugin", version="1.0.0"))
"""
import inspect
import typing
from typing import Any, Dict, List, Optional, Type


# Python 类型 → ibci 类型名的映射表
_IBCI_TYPE_MAP: Dict[Any, str] = {
    str:        "str",
    int:        "int",
    float:      "float",
    bool:       "bool",
    list:       "list",
    dict:       "dict",
    type(None): "void",
    None:       "void",
}

# 字符串形式类型名映射（用于 get_type_hints 失败时的回退）
_IBCI_STR_MAP: Dict[str, str] = {
    "str":   "str",
    "int":   "int",
    "float": "float",
    "bool":  "bool",
    "list":  "list",
    "dict":  "dict",
    "None":  "void",
    "none":  "void",
    "void":  "void",
    "Any":   "any",
    "any":   "any",
    "List":  "list",
    "Dict":  "dict",
}


def _py_type_to_ibci(py_type: Any) -> str:
    """将 Python 类型标注映射到 ibci 类型名。无法识别时返回 'any'。"""
    if py_type is inspect.Parameter.empty:
        return "any"
    # 直接命中
    if py_type in _IBCI_TYPE_MAP:
        return _IBCI_TYPE_MAP[py_type]
    # 字符串类型（forward reference）
    if isinstance(py_type, str):
        return _IBCI_STR_MAP.get(py_type, "any")
    # typing.List[X] / typing.Dict[K,V] → list / dict
    origin = getattr(py_type, "__origin__", None)
    if origin is list or origin is List:
        return "list"
    if origin is dict or origin is Dict:
        return "dict"
    # Optional[X] = Union[X, None] → "any" (ibci 没有 nullable 声明)
    return "any"


def gen_spec(
    cls: type,
    name: Optional[str] = None,
    version: str = "1.0.0",
    description: str = "",
    skip_private: bool = True,
    skip_setup: bool = True,
) -> str:
    """
    从 Python 类自动生成 _spec.py 文件内容字符串。

    参数：
        cls          目标类
        name         ibci 模块名（默认取 cls.__name__.lower()）
        version      版本号
        description  描述
        skip_private 是否跳过以 _ 开头的方法（默认 True）
        skip_setup   是否跳过 setup() 方法（默认 True，setup 是框架钩子）
    """
    module_name = name or cls.__name__.lower()

    functions: Dict[str, Dict[str, Any]] = {}
    variables: Dict[str, str] = {}

    # 从 __init__ 的 self.xxx: type 注解提取实例变量
    try:
        init_hints = typing.get_type_hints(cls.__init__) if hasattr(cls.__init__, "__annotations__") else {}
    except Exception:
        init_hints = {}

    # 从 class body 的 __annotations__ 提取类级别变量
    class_annotations = getattr(cls, "__annotations__", {})
    for field_name, field_type in class_annotations.items():
        if skip_private and field_name.startswith("_"):
            continue
        variables[field_name] = _py_type_to_ibci(field_type)

    # 处理方法
    for method_name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
        if skip_private and method_name.startswith("_"):
            continue
        if skip_setup and method_name == "setup":
            continue

        try:
            hints = typing.get_type_hints(method)
        except Exception:
            hints = getattr(method, "__annotations__", {})

        sig = inspect.signature(method)
        params = [
            p for k, p in sig.parameters.items()
            if k not in ("self", "cls")
            and p.kind not in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            )
        ]

        param_types = [_py_type_to_ibci(hints.get(p.name, Any)) for p in params]
        return_type = _py_type_to_ibci(hints.get("return"))

        doc = inspect.getdoc(method) or ""
        # 取第一行作为 description
        short_desc = doc.split("\n")[0].strip() if doc else ""

        entry: Dict[str, Any] = {
            "param_types": param_types,
            "return_type": return_type,
        }
        if short_desc:
            entry["description"] = short_desc

        functions[method_name] = entry

    # 生成代码
    lines = [
        '"""',
        f'自动生成的 _spec.py - {module_name} 插件规范',
        f'由 ibci_sdk.gen_spec 自动生成，可在此基础上手动补充描述。',
        '"""',
        "",
        "from typing import Dict, Any",
        "",
        "",
        "def __ibcext_metadata__() -> Dict[str, Any]:",
        "    return {",
        f'        "name": "{module_name}",',
        f'        "version": "{version}",',
        f'        "description": "{description}",',
        '        "dependencies": [],',
        "    }",
        "",
        "",
        "def __ibcext_vtable__() -> Dict[str, Any]:",
        "    return {",
        '        "functions": {',
    ]

    for fname, fspec in functions.items():
        params_repr = repr(fspec["param_types"])
        ret_repr = repr(fspec["return_type"])
        if "description" in fspec:
            lines.append(f'            "{fname}": {{"param_types": {params_repr}, "return_type": {ret_repr}, "description": {repr(fspec["description"])}}},')
        else:
            lines.append(f'            "{fname}": {{"param_types": {params_repr}, "return_type": {ret_repr}}},')

    lines.append("        },")

    if variables:
        lines.append('        "variables": {')
        for vname, vtype in variables.items():
            lines.append(f'            "{vname}": "{vtype}",')
        lines.append("        },")

    lines += [
        "    }",
        "",
    ]

    return "\n".join(lines)


def gen_spec_file(cls: type, output_path: str, **kwargs) -> None:
    """
    从 Python 类生成 _spec.py 并写入文件。

    参数：
        cls          目标类
        output_path  输出路径（如 'ibci_modules/ibci_myplugin/_spec.py'）
        **kwargs     传递给 gen_spec() 的其他参数
    """
    content = gen_spec(cls, **kwargs)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[ibci_sdk] Generated: {output_path}")
