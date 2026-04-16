"""
ibci_sdk - IBCI 插件开发工具包

提供：
- gen_spec   自动从 Python 类生成 _spec.py 内容
- check      插件预检查（无需启动完整引擎）
- StatelessPlugin / StatefulPlugin   便捷导出
"""
from .gen_spec import gen_spec, gen_spec_file
from .check import check_plugin, CheckResult

__all__ = [
    "gen_spec",
    "gen_spec_file",
    "check_plugin",
    "CheckResult",
]
