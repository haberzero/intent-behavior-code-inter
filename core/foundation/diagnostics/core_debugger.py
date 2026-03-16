import os
import json
import pprint
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
    UTS = 7
    GENERAL = 8

class CoreDebugger:
    """
    IBC-Inter 内核调试器 (Internal Core Debugger) 2.0。
    提供非破坏性的、分模块、分级别、支持树状缩进和 ANSI 色彩的内部追踪能力。
    """
    
    # ANSI Colors
    COLORS = {
        CoreModule.LEXER: "\033[94m",       # Blue
        CoreModule.PARSER: "\033[92m",      # Green
        CoreModule.SEMANTIC: "\033[93m",    # Yellow
        CoreModule.INTERPRETER: "\033[95m", # Magenta
        CoreModule.LLM: "\033[96m",        # Cyan
        CoreModule.SCHEDULER: "\033[90m",   # Grey
        CoreModule.UTS: "\033[38;5;208m",   # Orange
        CoreModule.GENERAL: "\033[0m",      # Reset
    }
    RESET = "\033[0m"
    BOLD = "\033[1m"

    def __init__(self):
        self._init_config()
        self.output_callback = None
        self.indent_level = 0
        self.show_colors = True
        self.silent = False

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
        self.indent_level = 0
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

    def enable_module(self, module: CoreModule, level: DebugLevel = DebugLevel.BASIC):
        """代码级快捷开启模块调试"""
        self.config[module] = level
        self.enabled = True

    def enable_all(self, level: DebugLevel = DebugLevel.BASIC):
        """开启所有模块的调试"""
        for m in CoreModule:
            self.config[m] = level
        self.enabled = True

    def enter_scope(self, module: CoreModule, message: str = ""):
        """进入一个追踪作用域，增加缩进"""
        if message:
            self.trace(module, DebugLevel.BASIC, f"--> {message}")
        self.indent_level += 1

    def exit_scope(self, module: CoreModule, message: str = ""):
        """退出一个追踪作用域，减少缩进"""
        self.indent_level = max(0, self.indent_level - 1)
        if message:
            self.trace(module, DebugLevel.BASIC, f"<-- {message}")

    def trace(self, module: CoreModule, level: DebugLevel, message: str, data: Any = None):
        """
        输出调试信息。
        """
        if not self.enabled or self.silent:
            return
            
        target_level = self.config.get(module, DebugLevel.NONE)
        if level <= target_level:
            indent = "  " * self.indent_level
            
            if self.show_colors:
                color = self.COLORS.get(module, "")
                prefix = f"{color}[{module.name}][{level.name}]{self.RESET}"
                msg_body = f"{indent}{message}"
            else:
                prefix = f"[{module.name}][{level.name}]"
                msg_body = f"{indent}{message}"
                
            output = f"{prefix} {msg_body}"
            
            if data is not None and target_level >= DebugLevel.DATA:
                try:
                    formatted_data = pprint.pformat(data, indent=2, width=120)
                    # 数据部分也跟随缩进
                    data_lines = formatted_data.splitlines()
                    indented_data = "\n".join([f"{indent}  {line}" for line in data_lines])
                    output += f"\n{indent}DATA:\n{indented_data}"
                except:
                    output += f" (Data: {str(data)})"
            
            if self.output_callback:
                self.output_callback(output)
            else:
                print(output)

# Singleton instance
core_debugger = CoreDebugger()

def core_trace(module: CoreModule, level: DebugLevel, message: str, data: Any = None):
    """全局追踪快捷函数"""
    core_debugger.trace(module, level, message, data)

def core_enter(module: CoreModule, message: str = ""):
    """全局进入作用域快捷函数"""
    core_debugger.enter_scope(module, message)

def core_exit(module: CoreModule, message: str = ""):
    """全局退出作用域快捷函数"""
    core_debugger.exit_scope(module, message)
