# 向后兼容垫片 — 实际定义已移至 core/kernel/host_interface.py
# HostInterface 仅依赖 core.kernel.*（无 runtime 依赖），
# 移至 kernel 层以消除 compiler → runtime 层级反转。
from core.kernel.host_interface import HostInterface, HostModuleRegistry

__all__ = ["HostInterface", "HostModuleRegistry"]
