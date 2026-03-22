import unittest
import os
from core.base.diagnostics.debugger import (
    DebugLevel,
    CoreModule,
    CoreDebugger,
    core_debugger,
    core_trace,
    core_enter,
    core_exit,
)


class TestDebugLevel(unittest.TestCase):
    """测试 DebugLevel 枚举"""

    def test_debug_level_values(self):
        """验证 DebugLevel 枚举值"""
        self.assertEqual(DebugLevel.NONE.value, 0)
        self.assertEqual(DebugLevel.BASIC.value, 1)
        self.assertEqual(DebugLevel.DETAIL.value, 2)
        self.assertEqual(DebugLevel.DATA.value, 3)

    def test_debug_level_ordering(self):
        """验证 DebugLevel 值的排序"""
        self.assertLess(DebugLevel.NONE, DebugLevel.BASIC)
        self.assertLess(DebugLevel.BASIC, DebugLevel.DETAIL)
        self.assertLess(DebugLevel.DETAIL, DebugLevel.DATA)


class TestCoreModule(unittest.TestCase):
    """测试 CoreModule 枚举"""

    def test_core_module_values(self):
        """验证 CoreModule 枚举值"""
        self.assertEqual(CoreModule.LEXER.value, 1)
        self.assertEqual(CoreModule.PARSER.value, 2)
        self.assertEqual(CoreModule.SEMANTIC.value, 3)
        self.assertEqual(CoreModule.INTERPRETER.value, 4)
        self.assertEqual(CoreModule.LLM.value, 5)
        self.assertEqual(CoreModule.SCHEDULER.value, 6)
        self.assertEqual(CoreModule.UTS.value, 7)
        self.assertEqual(CoreModule.GENERAL.value, 8)

    def test_core_module_count(self):
        """验证 CoreModule 枚举成员数量"""
        members = list(CoreModule)
        self.assertEqual(len(members), 8)

    def test_core_module_names(self):
        """验证 CoreModule 枚举成员名称"""
        names = [m.name for m in CoreModule]
        self.assertIn("LEXER", names)
        self.assertIn("PARSER", names)
        self.assertIn("SEMANTIC", names)
        self.assertIn("INTERPRETER", names)
        self.assertIn("LLM", names)
        self.assertIn("SCHEDULER", names)
        self.assertIn("UTS", names)
        self.assertIn("GENERAL", names)


class TestCoreDebugger(unittest.TestCase):
    """测试 CoreDebugger 类"""

    def setUp(self):
        """每个测试前创建新的 debugger 实例"""
        self.debugger = CoreDebugger()

    def test_initialization(self):
        """测试初始化"""
        self.assertFalse(self.debugger.enabled)
        self.assertEqual(self.debugger.indent_level, 0)
        self.assertFalse(self.debugger.silent)
        self.assertTrue(self.debugger.show_colors)

    def test_configure_valid(self):
        """测试有效配置"""
        config = {"LEXER": "BASIC", "PARSER": "DETAIL"}
        self.debugger.configure(config)
        self.assertTrue(self.debugger.enabled)
        self.assertEqual(self.debugger.config[CoreModule.LEXER], DebugLevel.BASIC)
        self.assertEqual(self.debugger.config[CoreModule.PARSER], DebugLevel.DETAIL)

    def test_configure_none(self):
        """测试 None 配置"""
        self.debugger.configure(None)
        self.assertFalse(self.debugger.enabled)

    def test_configure_invalid_module(self):
        """测试无效模块名"""
        config = {"INVALID": "BASIC"}
        self.debugger.configure(config)
        self.assertFalse(self.debugger.enabled)

    def test_configure_invalid_level(self):
        """测试无效级别"""
        config = {"LEXER": "INVALID"}
        self.debugger.configure(config)
        self.assertFalse(self.debugger.enabled)

    def test_enable_module(self):
        """测试 enable_module"""
        self.debugger.enable_module(CoreModule.LEXER, DebugLevel.DATA)
        self.assertTrue(self.debugger.enabled)
        self.assertEqual(self.debugger.config[CoreModule.LEXER], DebugLevel.DATA)

    def test_enable_all(self):
        """测试 enable_all"""
        self.debugger.enable_all(DebugLevel.BASIC)
        self.assertTrue(self.debugger.enabled)
        for module in CoreModule:
            self.assertEqual(self.debugger.config[module], DebugLevel.BASIC)

    def test_enter_exit_scope(self):
        """测试 enter_scope 和 exit_scope"""
        outputs = []
        self.debugger.output_callback = outputs.append
        self.debugger.enable_module(CoreModule.GENERAL, DebugLevel.BASIC)

        self.debugger.enter_scope(CoreModule.GENERAL, "test scope")
        self.assertEqual(self.debugger.indent_level, 1)

        self.debugger.exit_scope(CoreModule.GENERAL, "end scope")
        self.assertEqual(self.debugger.indent_level, 0)

    def test_trace_output(self):
        """测试 trace 输出"""
        outputs = []
        self.debugger.output_callback = outputs.append
        self.debugger.enable_module(CoreModule.GENERAL, DebugLevel.BASIC)

        self.debugger.trace(CoreModule.GENERAL, DebugLevel.BASIC, "test message")

        self.assertEqual(len(outputs), 1)
        self.assertIn("test message", outputs[0])

    def test_trace_no_output_when_disabled(self):
        """测试禁用时不输出"""
        outputs = []
        self.debugger.output_callback = outputs.append
        self.debugger.trace(CoreModule.GENERAL, DebugLevel.BASIC, "should not appear")
        self.assertEqual(len(outputs), 0)

    def test_trace_data_at_data_level(self):
        """测试在 DATA 级别输出数据"""
        outputs = []
        self.debugger.output_callback = outputs.append
        self.debugger.enable_module(CoreModule.GENERAL, DebugLevel.DATA)

        self.debugger.trace(CoreModule.GENERAL, DebugLevel.DATA, "with data", {"key": "value"})

        self.assertEqual(len(outputs), 1)
        self.assertIn("with data", outputs[0])
        self.assertIn("key", outputs[0])

    def test_trace_ignore_data_below_data_level(self):
        """测试在低于 DATA 级别时忽略数据"""
        outputs = []
        self.debugger.output_callback = outputs.append
        self.debugger.enable_module(CoreModule.GENERAL, DebugLevel.DETAIL)

        self.debugger.trace(CoreModule.GENERAL, DebugLevel.DATA, "with data", {"key": "value"})

        self.assertEqual(len(outputs), 0)

    def test_reset(self):
        """测试 reset"""
        self.debugger.enable_module(CoreModule.LEXER, DebugLevel.DATA)
        self.debugger.enter_scope(CoreModule.GENERAL)
        self.debugger.reset()

        self.assertFalse(self.debugger.enabled)
        self.assertEqual(self.debugger.indent_level, 0)
        self.assertEqual(self.debugger.config[CoreModule.LEXER], DebugLevel.NONE)

    def test_enter_scope_negative_indent(self):
        """测试 exit_scope 不会使 indent_level 变为负数"""
        self.debugger.indent_level = 0
        self.debugger.exit_scope(CoreModule.GENERAL)
        self.assertEqual(self.debugger.indent_level, 0)


class TestGlobalFunctions(unittest.TestCase):
    """测试全局函数"""

    def test_core_debugger_singleton(self):
        """验证 core_debugger 是单例"""
        self.assertIsInstance(core_debugger, CoreDebugger)

    def test_core_trace_function(self):
        """测试 core_trace 函数"""
        outputs = []
        original_callback = core_debugger.output_callback
        try:
            core_debugger.output_callback = outputs.append
            core_debugger.enable_module(CoreModule.GENERAL, DebugLevel.BASIC)
            core_trace(CoreModule.GENERAL, DebugLevel.BASIC, "global trace")
            self.assertEqual(len(outputs), 1)
        finally:
            core_debugger.output_callback = original_callback
            core_debugger.reset()


class TestDebuggerColors(unittest.TestCase):
    """测试调试器颜色配置"""

    def test_colors_defined(self):
        """验证所有模块都有颜色配置"""
        for module in CoreModule:
            self.assertIn(module, CoreDebugger.COLORS)

    def test_colors_are_strings(self):
        """验证颜色是 ANSI 转义序列字符串"""
        for module, color in CoreDebugger.COLORS.items():
            self.assertIsInstance(color, str)
            self.assertTrue(color.startswith("\033"))


if __name__ == "__main__":
    unittest.main()
