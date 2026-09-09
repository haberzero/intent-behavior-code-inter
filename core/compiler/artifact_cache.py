"""
core/compiler/artifact_cache.py — 持久 artifact 缓存（P5 编译期上修）。

**定位**：编译期性能上修——为相同源码 + 相同内核版本的编译产物（``CompilationArtifact``
蓝图）提供磁盘缓存，命中时跳过 5 阶段编译管线（扫描/依赖图/拓扑/语义/序列化），直接
加载缓存产物。

**缓存键**：``sha256(源码内容 + entry_module_name + kernel_version + project_root)``——
源码内容（非 tempfile 路径）保证 run_string 场景可复现；kernel_version 保证内核变更后
缓存失效；project_root 保证跨项目缓存隔离。

**缓存存储**：``<project_root>/.ibci_cache/artifact_<key>.pkl``——pickle 序列化
（``CompilationArtifact`` 是 dataclass + AST + SymbolTable）。

**安全加固（防 pickle 反序列化篡改 → 任意代码执行）**：
- **白名单反序列化**（``_SafeUnpickler``）：仅允许已知模块的类（core.kernel.blueprint /
  core.compiler.ast / core.runtime.objects.kernel / builtins 基础类型）——禁用其他模块
  的类实例化（防恶意 pickle 流经 ``find_class`` 注入任意代码）。
- **0600/0700 权限**：payload 0600（仅属主读写）+ 缓存目录 0700（仅属主访问）。
- **启用门**：``IBCI_ARTIFACT_CACHE=1``（env）启用；默认关闭（零侵入既有行为）。

**缓存验证**：键含 kernel_version + entry_module_name；源码变更 → 键变更 → 未命中。
"""

from __future__ import annotations

import hashlib
import os
import pickle
from typing import Any, Optional

# 内核版本标识（缓存键组件）——core 包版本 + Python 版本（保证跨版本缓存失效）
_KERNEL_VERSION = "ibci-2026.09-py312"

# 缓存目录名（project_root 下）
_CACHE_DIR_NAME = ".ibci_cache"

# 白名单反序列化允许模块（防 pickle find_class 注入任意代码）
# ——CompilationArtifact/CompilationResult（blueprint）+ AST 节点（compiler.ast）+
# SymbolTable（runtime.objects.kernel）+ builtins 基础类型（dict/list/tuple/str/int/
# float/bool/NoneType）。其他模块（os/sys/subprocess 等）的类禁用。
_ALLOWED_MODULES = frozenset({
    "core.kernel.blueprint",
    "core.compiler.ast",
    "core.runtime.objects.kernel",
    "builtins",
})


class _UnsafePickleError(Exception):
    """白名单反序列化拒绝（非允许模块的类）——内部信号，非运行时错误。"""


class _SafeUnpickler(pickle.Unpickler):
    """白名单反序列化——仅允许已知模块的类（防任意代码执行）。

    ``find_class`` 在 pickle 流实例化类时调用；非白名单模块 → 抛
    ``_UnsafePickleError``（加载视为未命中，不抛穿编译流程）。
    """

    def find_class(self, module: str, name: str):
        if module not in _ALLOWED_MODULES:
            raise _UnsafePickleError(f"disallowed pickle module: {module}.{name}")
        return super().find_class(module, name)


def _cache_enabled() -> bool:
    """缓存启用门（env IBCI_ARTIFACT_CACHE=1 启用；默认关闭零侵入）。"""
    return os.environ.get("IBCI_ARTIFACT_CACHE", "") in ("1", "true", "True")


def compute_cache_key(source: str, entry_module_name: Optional[str], project_root: str) -> str:
    """计算缓存键：sha256(源码 + entry_module_name + kernel_version + project_root)。

    源码内容（非 tempfile 路径）保证 run_string 场景可复现；kernel_version 保证内核
    变更后缓存失效；project_root 保证跨项目缓存隔离。
    """
    h = hashlib.sha256()
    h.update(source.encode("utf-8"))
    h.update(b"\x00")
    h.update((entry_module_name or "").encode("utf-8"))
    h.update(b"\x00")
    h.update(_KERNEL_VERSION.encode("utf-8"))
    h.update(b"\x00")
    h.update(project_root.encode("utf-8"))
    return h.hexdigest()[:32]


def _cache_path(project_root: str, key: str) -> str:
    """缓存 payload 路径：<project_root>/.ibci_cache/artifact_<key>.pkl。"""
    cache_dir = os.path.join(project_root, _CACHE_DIR_NAME)
    return os.path.join(cache_dir, f"artifact_{key}.pkl")


def load_cached_artifact(project_root: str, key: str) -> Optional[Any]:
    """加载缓存的 CompilationArtifact；未命中/损坏/白名单拒绝 → None。

    白名单反序列化（_SafeUnpickler）——非允许模块的类 → 加载拒绝（未命中）。
    """
    if not _cache_enabled():
        return None
    path = _cache_path(project_root, key)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as f:
            return _SafeUnpickler(f).load()
    except Exception:
        # 缓存损坏/不可反序列化/白名单拒绝 → 未命中（不抛穿编译流程）
        return None


def save_artifact(project_root: str, key: str, artifact: Any) -> bool:
    """保存 CompilationArtifact 到磁盘缓存（0600/0700 权限）；失败 → False。"""
    if not _cache_enabled():
        return False
    try:
        path = _cache_path(project_root, key)
        cache_dir = os.path.dirname(path)
        os.makedirs(cache_dir, mode=0o700, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(artifact, f)
        os.chmod(path, 0o600)
        return True
    except Exception:
        return False
