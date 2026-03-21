from typing import Optional, List
from dataclasses import dataclass

class ExtensionError(Exception):
    pass

class PluginError(ExtensionError):
    pass

class InterpreterError(ExtensionError):
    pass

class CompilerError(ExtensionError):
    pass
