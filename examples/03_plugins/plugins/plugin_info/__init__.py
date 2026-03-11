class PluginMetadata:
    def __init__(self):
        self.version = "2.0.0"
        self.author = "IBCI-Inter Team"
        # [SECURITY] IES 2.0 要求显式声明属性白名单
        self._ibci_whitelist = ["version", "author"]

implementation = PluginMetadata()
