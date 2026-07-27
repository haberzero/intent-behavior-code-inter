# HostInterface 定义位于 core/kernel/host_interface.py；本模块 re-export 以维持 import 路径。
# HostInterface 仅依赖 core.kernel.*（无 runtime 依赖），
# 位于 kernel 层以消除 compiler → runtime 层级反转。
from core.kernel.host_interface import HostInterface, HostModuleRegistry

__all__ = ["HostInterface", "HostModuleRegistry"]
