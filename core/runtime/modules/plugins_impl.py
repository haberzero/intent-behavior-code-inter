"""plugins 宿主模块——Rust 插件协议网关（架构 v2 R6 ④层）。

**定位**：IBCI 与外部 Rust 插件的交互面。外部 Rust 作者依赖 `ibci-sdk`（C-ABI
值模型 + 注册 API）把纯函数编译为 cdylib；本模块经内核加载（libloading）与
调用（内核 GIL-free，插件 = 纯函数面，不触碰 Python/GIL）。

**协议**：
- ``load(path)``：加载插件 cdylib（调用其 ``ibci_plugin_register`` 入口，函数
  入内核插件注册表）。路径 = 宿主文件系统绝对/相对路径（可信构建产物）。
- ``call(name, args)``：调用已注册插件函数（args = 标量/列表原生数据；结果 =
  标量原生数据；R6-1 值面：int/float/bool/null + 扁平列表实参）。

**GIL 纪律**：插件函数 = 内核 GIL-free 执行（调用期不持 GIL）；本模块仅做
宿主边界参数/结果编组。
"""

from __future__ import annotations

from typing import Any


class PluginsLib:
    """Rust 插件网关（宿主模块实现——经 host_interface.register_module 挂载）。"""

    def __init__(self):
        self._kernel = None

    def _k(self):
        if self._kernel is None:
            from core.runtime.kernels import load_kernel

            self._kernel = load_kernel()
        return self._kernel

    def load(self, path: Any) -> Any:
        """加载 Rust 插件 cdylib（ibci-sdk 协议）——注册其函数。返回注册数。"""
        p = str(path)
        return self._k().load_plugin(p)

    def call(self, name: Any, args: Any) -> Any:
        """调用已注册插件函数（args = 标量原生数据；结果 = 原生标量）。"""
        n = str(name)
        return self._k().call_plugin(n, _to_native_list(args))


def _to_native_list(v: Any) -> Any:
    """宿主边界值 → 原生列表（IbObject 拆箱 + 列表递归；标量直通）。"""
    if isinstance(v, (list, tuple)):
        return [_to_native_list(x) for x in v]
    if hasattr(v, "to_native"):
        try:
            return v.to_native()
        except Exception:
            pass
    return v
