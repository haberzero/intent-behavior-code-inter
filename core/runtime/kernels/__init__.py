"""Rust 执行内核（ibci_ext）加载面——双内核协议内核选择的入口。

P1 能力声明协议（架构 v2 R0 §三）：路由判定 = 能力清单查询
（``core.runtime.kernels.capability`` 的 ArtifactRouter——节点类型/内征/模块
⊆ Rust 声明集 **且** 无已用未移植角），零谓词堆零硬编码集合（审计 3.1 收敛）。

``.so`` = 可再生构建产物（``scripts/build_rust_ext.sh``，gitignored）；缺失
= 显式报错（双内核协议：无静默回退——Python 运行时不做数据面兜底）。
"""

import importlib.util
import os
import sys

_SO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ibci_ext.so")


class KernelUnavailableError(RuntimeError):
    """Rust 内核不可用（.so 缺失）——构建：``bash scripts/build_rust_ext.sh``。"""


def kernel_available() -> bool:
    """Rust 内核（.so）在位。"""
    return os.path.exists(_SO_PATH)


def load_kernel():
    """加载 Rust 内核模块（进程级缓存——单一实例）。

    .so 缺失 = 显式 KernelUnavailableError（双内核协议：无静默回退）。
    """
    if "ibci_ext" in sys.modules:
        return sys.modules["ibci_ext"]
    if not os.path.exists(_SO_PATH):
        raise KernelUnavailableError(
            "ibci_ext.so 缺失——构建：bash scripts/build_rust_ext.sh"
            "（双内核协议：无静默回退）"
        )
    spec = importlib.util.spec_from_file_location("ibci_ext", _SO_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["ibci_ext"] = module
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------- #
# 路由判定（P1 能力声明查询——单一入口）
# --------------------------------------------------------------------------- #
_router = None


def _get_router():
    """进程级单例 ArtifactRouter（能力声明缓存——.so 重建后新进程生效）。"""
    global _router
    if _router is None:
        from core.runtime.kernels.capability import ArtifactRouter, load_capability

        _router = ArtifactRouter(load_capability())
    return _router


def artifact_is_rust_executable(artifact_dict: dict) -> bool:
    """⑦ 面分区路由判定：artifact 特征 ⊆ Rust 能力声明 **且** 无已用未移植角
    = 数据面源（Rust 可执行）；否则 = Python 语义宿主（全源 Python 执行，
    单一内核归属纪律）。判定 = 能力清单查询结果（零谓词堆零硬编码集合）。"""
    from core.runtime.kernels.capability import ArtifactView

    return _get_router().can_execute(ArtifactView(artifact_dict))
