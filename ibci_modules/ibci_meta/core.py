"""
ibci_modules/ibci_meta/core.py

IBCI Meta 核心级元编程插件实现。

meta 是 IBCI 核心级插件（Core-Level Plugin）：暴露"代码作值"的**编译门**原语
（安全执行架构的编译门：

- ``compile(code)``：代码字符串进程内**编译作值**（compile-only 静态校验，**不执行**）——
  语法/语义错误 fail-fast 抛 ``CompilerError``（diagnostics 带 ibci 源定位：合成 entry
  标记 + line/column），成功静默（void）。与 CLI ``check`` 面同构。

- ``quote(source)``：表达式源串经**验证门**冻结为 ``quoted`` 值（数据/命令二元的
  **数据形态**：可查询/可打印其自身/精确对比逐字节；自包含性由构造成立）
- ``eval(expr)``：执行 quoted 值的表达式并取回其**值**（**命令形态**；值通道，
  非 stdout 文本；fail-fast）

meta 通过 capabilities.kernel_registry.get_host_service() 委托内核 HostService
（meta_compile / quote_expression / eval_quoted）——自身不持有运行时状态
（同 ihost 模式）。
"""
from core.extension.ibcext import IbPlugin, ExtensionCapabilities
from typing import Any, Optional


class MetaPlugin(IbPlugin):
    """Meta 元编程插件（编译门原语）。"""

    def __init__(self):
        super().__init__()
        self._capabilities: Optional[ExtensionCapabilities] = None

    @property
    def plugin_id(self) -> str:
        return "ibc:meta"

    def setup(self, capabilities: ExtensionCapabilities) -> None:
        super().setup(capabilities)
        self._capabilities = capabilities

    # ------------------------------------------------------------------
    # ibci 暴露接口
    # ------------------------------------------------------------------

    def compile(self, code: str) -> Any:
        """代码字符串进程内编译校验（compile-only，**不执行**）+ **返回编译产物值**。

        语法/语义错误 fail-fast 抛 ``CompilerError``（diagnostics 带 ibci 源定位：
        合成 entry ``__string_exec__`` 标记 + line/column）。成功**返回编译产物摘要
        dict**（行为作值 TYPE-1）：ok/n_modules/entry_module/n_top_stmts/n_funcs/
        func_names/n_classes/class_names——系统可持已编译行为为值、确定性内省其结构。
        经 HostService.meta_compile：子引擎 compile-only（零父状态污染）。
        """
        hs = self._host_service()
        if not hs:
            raise RuntimeError("Meta service not available; cannot meta.compile.")
        return hs.meta_compile(code)

    def quote(self, source: str) -> Any:
        """表达式源串经**单一验证门**冻结为 ``quoted`` 值（数据/命令二元的数据形态）。

        验证门 = 子引擎 compile-only（同 meta.compile 编译门路径）：语法/语义/
        表达式性/自包含性（fresh scope——引用父模块自由名的源即 fail-fast）一次
        门尽；失败上抛（IBCI ``try/except`` 可捕获，message 含 ibci 源定位）。
        成功返回 ``quoted`` 不可变值（字段 ``source`` = 完整源串；``q.source``
        精确对比逐字节；print 渲染完整源串）。零 LLM（compile-only）。
        """
        hs = self._host_service()
        if not hs:
            raise RuntimeError("Meta service not available; cannot meta.quote.")
        return hs.quote_expression(source)

    def eval(self, expr: str) -> Any:
        """执行 quoted 值的表达式并取回其**值**（数据/命令二元的命令形态）。

        入参经边界拆箱 = quoted 的 ``source`` 源串（spec 面静态强制入参类型为
        ``quoted``——str 直调 = 编译期类型错，无隐式通道）。子进程独立引擎
        执行（fresh scope + 进程级隔离 + LLM 态继承），经值交换通道取回
        表达式值（**返回值，非 stdout 文本**）。错误面 fail-fast（子编译/运行
        失败、结果槽缺失——复杂值/函数值不可经值通道序列化——均上抛，IBCI
        ``try/except`` 可捕获）。转换路径零 LLM；表达式自身若为 ``@~`` 行为
        表达式则按 LLM 语义执行（确定性模式断言归横切面）。
        """
        hs = self._host_service()
        if not hs:
            raise RuntimeError("Meta service not available; cannot meta.eval.")
        return hs.eval_quoted(expr)

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _host_service(self) -> Optional[object]:
        """通过 KernelRegistry 稳定钩子获取内核 HostService 实例。"""
        if self._capabilities:
            kr = self._capabilities.kernel_registry
            if kr:
                return kr.get_host_service()
        return None


def create_implementation() -> MetaPlugin:
    """工厂函数：创建 MetaPlugin 实例。"""
    return MetaPlugin()
