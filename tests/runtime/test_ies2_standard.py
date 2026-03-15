import unittest
import os
from tests.base import BaseIBCTest

class TestIES2Standard(BaseIBCTest):
    """
    验证 IES 2.0 插件系统标准的实现情况。
    1. 强制使用 _spec.py
    2. 强制使用 get_vtable
    3. 权限注入
    """

    def test_idbg_standard_loading(self):
        """测试新版 idbg 插件加载"""
        code = """
        import idbg
        int x = 42
        dict v = idbg.vars()
        print(v.len())
        """
        # 运行代码，如果能正常导入并调用 idbg.vars()，说明 discovery 和 loader 都已对齐新标准
        self.run_code(code)
        # v 应该包含 x，长度为 1
        self.assert_output("1")

    def test_ai_standard_loading(self):
        """测试新版 ai 插件加载"""
        code = """
        import ai
        ai.set_config("TESTONLY", "NONE", "NONE")
        print(ai.get_decision_map().len())
        """
        self.run_code(code)
        # 默认 decision_map 长度应为 8 (见 ai/core.py)
        self.assert_output("8")

    def test_legacy_spec_rejection(self):
        """验证旧版 spec.py 被静默忽略或拒绝 (因为 discovery 只看 _spec.py)"""
        # 创建一个只有 spec.py 的模拟插件
        plugin_dir = os.path.join("ibc_modules", "legacy_plugin")
        os.makedirs(plugin_dir, exist_ok=True)
        with open(os.path.join(plugin_dir, "spec.py"), "w") as f:
            f.write("spec = None")
        
        code = "import legacy_plugin"
        from core.domain.issue import CompilerError
        with self.assertRaises(CompilerError):
            with self.silent_mode():
                self.compile_code(code)

if __name__ == "__main__":
    unittest.main()
