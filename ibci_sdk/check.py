"""
ibci_sdk/check.py

插件预检查工具（无需启动完整 IBCI 引擎）。

在插件开发阶段提前发现常见错误，避免到运行时才暴露问题。

检查项：
1. _spec.py 存在性
2. __ibcext_metadata__ 函数存在且返回合法 dict
3. __ibcext_vtable__ 函数存在且返回合法 dict
4. 实现类存在 create_implementation() 工厂函数
5. setup(capabilities) 方法签名合规
6. vtable 中声明的每个方法在实现类上存在
7. 方法参数数量与 spec 声明一致
8. IbStatefulPlugin 实现类必须实现 save_plugin_state / restore_plugin_state
9. __to_prompt__ 如果在 vtable 中声明，实现类上也必须存在

所有检查均为纯 Python 静态/动态反射，不依赖 core.* 模块。
"""
import importlib
import importlib.util
import inspect
import os
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class CheckResult:
    """插件预检查结果。"""
    plugin_dir: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def __str__(self) -> str:
        lines = [f"[ibci_sdk check] Plugin: {self.plugin_dir}"]
        if self.ok:
            lines.append("  ✅  All checks passed")
        else:
            for e in self.errors:
                lines.append(f"  ❌  ERROR: {e}")
        for w in self.warnings:
            lines.append(f"  ⚠️   WARN:  {w}")
        return "\n".join(lines)


def check_plugin(plugin_dir: str) -> CheckResult:
    """
    对指定插件目录执行预检查，返回 CheckResult。

    参数：
        plugin_dir  插件目录路径（如 'ibci_modules/ibci_math'）
    """
    result = CheckResult(plugin_dir=plugin_dir)
    errors = result.errors
    warnings = result.warnings

    abs_dir = os.path.abspath(plugin_dir)
    if not os.path.isdir(abs_dir):
        errors.append(f"Plugin directory does not exist: {abs_dir}")
        return result

    # 自动检测项目根目录（向上寻找包含 core/ 或 ibci_modules/ 的目录）
    extra_paths: List[str] = []
    candidate = abs_dir
    for _ in range(6):
        candidate = os.path.dirname(candidate)
        if os.path.isdir(os.path.join(candidate, "core")) or \
           os.path.isdir(os.path.join(candidate, "ibci_modules")):
            extra_paths = [candidate]
            break

    # 1. _spec.py 存在性
    spec_path = os.path.join(abs_dir, "_spec.py")
    if not os.path.exists(spec_path):
        errors.append("_spec.py not found")
        return result

    # 2. 加载 _spec.py
    spec_module = _load_module("_spec", spec_path, extra_paths)
    if spec_module is None:
        errors.append("Failed to import _spec.py")
        return result

    # 3. __ibcext_metadata__
    if not hasattr(spec_module, "__ibcext_metadata__"):
        errors.append("_spec.py missing __ibcext_metadata__() function")
    else:
        try:
            meta = spec_module.__ibcext_metadata__()
            if not isinstance(meta, dict):
                errors.append("__ibcext_metadata__() must return a dict")
            else:
                for key in ("name", "version", "description"):
                    if key not in meta:
                        warnings.append(f"__ibcext_metadata__() missing key: '{key}'")
                    elif not isinstance(meta[key], str):
                        errors.append(f"__ibcext_metadata__()['{key}'] must be a str")
        except Exception as e:
            errors.append(f"__ibcext_metadata__() raised an exception: {e}")

    # 4. __ibcext_vtable__
    vtable_spec: Optional[dict] = None
    if not hasattr(spec_module, "__ibcext_vtable__"):
        errors.append("_spec.py missing __ibcext_vtable__() function")
    else:
        try:
            vtable_spec = spec_module.__ibcext_vtable__()
            if not isinstance(vtable_spec, dict):
                errors.append("__ibcext_vtable__() must return a dict")
                vtable_spec = None
        except Exception as e:
            errors.append(f"__ibcext_vtable__() raised an exception: {e}")

    if vtable_spec is not None:
        functions = vtable_spec.get("functions", {})
        variables = vtable_spec.get("variables", {})
        if not isinstance(functions, dict):
            errors.append("__ibcext_vtable__()['functions'] must be a dict")
        else:
            for fname, fspec in functions.items():
                if not isinstance(fspec, dict):
                    errors.append(f"vtable function '{fname}' spec must be a dict")
                    continue
                if "param_types" not in fspec:
                    warnings.append(f"vtable function '{fname}' missing 'param_types'")
                elif not isinstance(fspec["param_types"], list):
                    errors.append(f"vtable function '{fname}' 'param_types' must be a list")
                if "return_type" not in fspec:
                    warnings.append(f"vtable function '{fname}' missing 'return_type'")
                elif not isinstance(fspec["return_type"], str):
                    errors.append(f"vtable function '{fname}' 'return_type' must be a str")

    # 5. __init__.py / create_implementation
    init_path = os.path.join(abs_dir, "__init__.py")
    if not os.path.exists(init_path):
        errors.append("__init__.py not found")
        return result

    impl_module = _load_module("__init__", init_path, extra_paths)
    if impl_module is None:
        errors.append("Failed to import __init__.py (check for syntax errors in core.py or __init__.py)")
        return result

    if not hasattr(impl_module, "create_implementation"):
        errors.append("__init__.py (or core.py) missing create_implementation() factory function")
        return result

    try:
        impl = impl_module.create_implementation()
    except Exception as e:
        errors.append(f"create_implementation() raised an exception: {e}")
        return result

    # 6. setup(capabilities) 合规性
    if hasattr(impl, "setup"):
        sig = inspect.signature(impl.setup)
        params = list(sig.parameters.keys())
        if "capabilities" not in params:
            errors.append("setup() method must accept 'capabilities' parameter")

    # 7. vtable 方法存在性 & 参数数量
    if vtable_spec is not None:
        functions = vtable_spec.get("functions", {})
        variables = vtable_spec.get("variables", {})
        for fname, fspec in functions.items():
            if fname.startswith("__"):
                # 协议方法（如 __to_prompt__），允许不在 vtable 参数检查范围内
                if not hasattr(impl, fname):
                    errors.append(f"Protocol method '{fname}' declared in vtable but not found in implementation")
                continue
            if not hasattr(impl, fname):
                errors.append(f"Method '{fname}' declared in vtable but not found in implementation")
                continue
            py_func = getattr(impl, fname)
            if not callable(py_func):
                errors.append(f"'{fname}' exists but is not callable")
                continue
            # 参数数量检查
            if isinstance(fspec, dict) and "param_types" in fspec:
                expected_count = len(fspec["param_types"])
                sig = inspect.signature(py_func)
                fixed_params = [
                    p for k, p in sig.parameters.items()
                    if k != "self"
                    and p.kind not in (
                        inspect.Parameter.VAR_POSITIONAL,
                        inspect.Parameter.VAR_KEYWORD,
                    )
                ]
                if len(fixed_params) < expected_count:
                    errors.append(
                        f"Method '{fname}': spec declares {expected_count} param(s), "
                        f"but implementation only has {len(fixed_params)}"
                    )

        for vname in variables:
            if not hasattr(impl, vname):
                errors.append(f"Variable '{vname}' declared in vtable but not found in implementation")

    # 8. IbStatefulPlugin 协议完整性
    try:
        # 不 import core.* — 直接检查方法名
        is_stateful = (
            hasattr(impl, "save_plugin_state") and
            hasattr(impl, "restore_plugin_state")
        )
        is_stateless_marker = type(impl).__name__ in dir(type(impl).__mro__)
        # 如果有其中一个但没有另一个，报警告
        has_save = hasattr(impl, "save_plugin_state")
        has_restore = hasattr(impl, "restore_plugin_state")
        if has_save and not has_restore:
            errors.append("save_plugin_state() found but restore_plugin_state() missing (IbStatefulPlugin incomplete)")
        if has_restore and not has_save:
            errors.append("restore_plugin_state() found but save_plugin_state() missing (IbStatefulPlugin incomplete)")
    except Exception:
        pass

    return result


def _load_module(name: str, path: str, extra_sys_paths: Optional[List[str]] = None):
    """
    安全加载 Python 模块文件，失败返回 None。

    对 __init__.py（含相对导入的包），使用 importlib.import_module() 方式加载。
    对独立文件（如 _spec.py），使用 spec_from_file_location 方式加载。
    """
    import sys
    added = []
    try:
        if extra_sys_paths:
            for p in extra_sys_paths:
                if p not in sys.path:
                    sys.path.insert(0, p)
                    added.append(p)

        # __init__.py 必须用 importlib.import_module 处理相对导入
        if os.path.basename(path) == "__init__.py":
            pkg_dir = os.path.dirname(path)
            pkg_name = os.path.basename(pkg_dir)
            # 推断父包名（如 ibci_modules.ibci_math）
            parent_dir = os.path.dirname(pkg_dir)
            parent_name = os.path.basename(parent_dir)
            # 检查 parent_dir 是否是 Python 包（有 __init__.py）
            if os.path.exists(os.path.join(parent_dir, "__init__.py")):
                full_name = f"{parent_name}.{pkg_name}"
                # 确保 parent_dir 的父目录在 sys.path 中
                grandparent = os.path.dirname(parent_dir)
                inserted = False
                if grandparent and grandparent not in sys.path:
                    sys.path.insert(0, grandparent)
                    added.append(grandparent)
                    inserted = True
                return importlib.import_module(full_name)
            else:
                # parent_dir 不是包，直接将 parent_dir 加入 sys.path
                if parent_dir and parent_dir not in sys.path:
                    sys.path.insert(0, parent_dir)
                    added.append(parent_dir)
                return importlib.import_module(pkg_name)

        # 独立文件（_spec.py 等）
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None
    finally:
        for p in added:
            if p in sys.path:
                sys.path.remove(p)
