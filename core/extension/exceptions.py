class ExtensionError(Exception):
    pass

class PluginError(ExtensionError):
    pass

class CompilerError(ExtensionError):
    pass
