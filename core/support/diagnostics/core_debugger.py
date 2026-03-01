import os
import json
from enum import IntEnum
from typing import Any, Dict, Optional, Set

class DebugLevel(IntEnum):
    NONE = 0
    BASIC = 1    # Flow control, major steps
    DETAIL = 2   # Fine-grained steps, internal states
    DATA = 3     # Full data structures, prompts, tokens

class CoreModule(IntEnum):
    LEXER = 1
    PARSER = 2
    SEMANTIC = 3
    INTERPRETER = 4
    LLM = 5
    SCHEDULER = 6
    GENERAL = 7

class CoreDebugger:
    """
    IBC-Inter 内核调试器 (Internal Core Debugger)。
    提供非破坏性的、分模块、分级别的内部追踪能力。
    """
    def __init__(self):
        self._init_config()

    def _init_config(self):
        self.config: Dict[CoreModule, DebugLevel] = {m: DebugLevel.NONE for m in CoreModule}
        self.enabled = False
        
        # Try to load from environment variable
        env_config = os.environ.get("IBC_CORE_DEBUG")
        if env_config:
            try:
                self.configure(json.loads(env_config))
            except:
                pass

    def reset(self):
        """重置所有调试配置为 NONE"""
        self.config = {m: DebugLevel.NONE for m in CoreModule}
        self.enabled = False
        # 重新加载环境变量，确保基础配置仍然有效
        self._init_config()

    def configure(self, config_dict: Optional[Dict[str, str]]):
        """
        根据字典配置各模块的调试级别。
        示例: {"LEXER": "BASIC", "INTERPRETER": "DATA"}
        """
        if config_dict is None:
            return

        for mod_name, level_name in config_dict.items():
            try:
                mod = CoreModule[mod_name.upper()]
                level = DebugLevel[level_name.upper()]
                self.config[mod] = level
                if level > DebugLevel.NONE:
                    self.enabled = True
            except (KeyError, AttributeError):
                continue

    def trace(self, module: CoreModule, level: DebugLevel, message: str, data: Any = None):
        """
        输出调试信息。
        """
        if not self.enabled:
            return
            
        target_level = self.config.get(module, DebugLevel.NONE)
        if level <= target_level:
            prefix = f"[CORE_DBG][{module.name}][{level.name}]"
            output = f"{prefix} {message}"
            
            if data is not None and target_level >= DebugLevel.DATA:
                try:
                    import pprint
                    formatted_data = pprint.pformat(data, indent=2, width=120)
                    output += f"\nDATA:\n{formatted_data}"
                except:
                    output += f" (Data: {str(data)})"
            
            print(output)

# Singleton instance
core_debugger = CoreDebugger()

def core_trace(module: CoreModule, level: DebugLevel, message: str, data: Any = None):
    """全局追踪快捷函数"""
    core_debugger.trace(module, level, message, data)
