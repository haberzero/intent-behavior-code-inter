"""
Isolated Plugin - 子项目隔离插件
"""


class IsolatedPlugin:
    """子项目隔离插件"""

    def setup(self, capabilities):
        """插件设置"""
        self.capabilities = capabilities

    def get_isolation_info(self) -> dict:
        """获取隔离信息"""
        script_dir = self.capabilities.stack_inspector.get_current_script_dir()
        return {
            "plugin_name": "isolated_plugin",
            "location": "子项目隔离环境",
            "scope": "仅限 sub_project 目录"
        }


def create_implementation():
    """插件工厂函数"""
    return IsolatedPlugin()
