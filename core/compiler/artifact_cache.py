"""
core/compiler/artifact_cache.py — 持久 artifact 缓存（P5 编译期上修）。

**定位**：编译期性能上修——为相同源码 + 相同内核版本的编译产物（``CompilationArtifact``
蓝图）提供磁盘缓存，命中时跳过 5 阶段编译管线（扫描/依赖图/拓扑/语义/序列化），直接
加载缓存产物。

**缓存键**：``sha256(源码内容 + entry_module_name + kernel_version)``——源码内容（非
tempfile 路径）保证 run_string 场景可复现；kernel_version 保证内核变更后缓存失效。

**缓存存储**：``<project_root>/.ibci_cache/artifact_<key>.pkl``——pickle 序列化
（``CompilationArtifact`` 是 dataclass + AST + SymbolTable，pickle 可序列化）。

**缓存验证**：键含 kernel_version + entry_module_name；源码变更 → 键变更 → 缓存未命中。

**启用门**：``IBCI_ARTIFACT_CACHE=1``（env）启用；默认关闭（零侵入既有行为）。
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
    """缓存文件路径：<project_root>/.ibci_cache/artifact_<key>.pkl。"""
    cache_dir = os.path.join(project_root, _CACHE_DIR_NAME)
    return os.path.join(cache_dir, f"artifact_{key}.pkl")


def load_cached_artifact(project_root: str, key: str) -> Optional[Any]:
    """加载缓存的 CompilationArtifact；未命中/损坏/不可序列化 → None。"""
    if not _cache_enabled():
        return None
    path = _cache_path(project_root, key)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except Exception:
        # 缓存损坏/不可反序列化 → 未命中（不抛穿编译流程）
        return None


def save_artifact(project_root: str, key: str, artifact: Any) -> bool:
    """保存 CompilationArtifact 到磁盘缓存；失败 → False（不抛穿编译流程）。"""
    if not _cache_enabled():
        return False
    try:
        path = _cache_path(project_root, key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(artifact, f)
        return True
    except Exception:
        return False
