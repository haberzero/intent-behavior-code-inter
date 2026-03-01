import unittest
import os
import json
from typing import Optional, Dict, Any
from core.engine import IBCIEngine
from core.support.diagnostics.core_debugger import core_debugger

class IBCTestCase(unittest.TestCase):
    """
    IBC-Inter 增强型测试基类。
    提供对 core_debug 机制的自动化支持，允许在测试运行期间精细化控制内核调试输出。
    """
    
    # 子类可以通过覆盖此属性来定义默认的内核调试配置
    # 示例: core_debug_config = {"INTERPRETER": "DETAIL", "LLM": "DATA"}
    core_debug_config: Optional[Dict[str, str]] = None

    def get_core_debug_config(self) -> Optional[Dict[str, str]]:
        """
        获取当前测试的内核调试配置。
        优先级：环境变量 IBC_TEST_CORE_DEBUG > 类属性 core_debug_config
        """
        config = (self.core_debug_config or {}).copy()
        
        env_config_str = os.environ.get("IBC_TEST_CORE_DEBUG")
        if env_config_str:
            try:
                # 支持 JSON 字符串
                env_config = json.loads(env_config_str)
                config.update(env_config)
            except json.JSONDecodeError:
                # 支持简单的 MODULE:LEVEL,MODULE:LEVEL 格式
                for item in env_config_str.split(','):
                    if ':' in item:
                        items = item.split(':', 1)
                        if len(items) == 2:
                            mod, level = items
                            config[mod.strip().upper()] = level.strip().upper()
        
        return config if config else None

    def create_engine(self, root_dir: Optional[str] = None, auto_sniff: bool = True) -> IBCIEngine:
        """
        创建一个带有正确调试配置的 IBCIEngine 实例。
        """
        debug_config = self.get_core_debug_config()
        # 创建引擎，它会自动创建并配置其私有的 CoreDebugger 实例
        return IBCIEngine(root_dir=root_dir, auto_sniff=auto_sniff, core_debug_config=debug_config)

    def setUp(self):
        """
        默认 setUp 实现。子类如果覆盖此方法，请务必调用 super().setUp()。
        """
        super().setUp()
        # 默认引擎初始化，如果子类需要自定义参数，可以使用 self.create_engine()
        self.engine = self.create_engine()

    def tearDown(self):
        """
        默认 tearDown 实现。确保调试状态被重置。
        """
        if hasattr(self, 'engine') and self.engine.debugger:
            self.engine.debugger.reset()
        super().tearDown()

    def run_silent(self, code: str, variables: Optional[Dict[str, Any]] = None, output_callback=None) -> bool:
        """
        静默运行代码，不向 stdout 打印错误信息。
        如果发生错误，会抛出异常供测试捕获。
        """
        return self.engine.run_string(code, variables=variables, output_callback=output_callback, silent=True)
