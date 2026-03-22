import unittest
from typing import Any, Optional, List, Dict
from core.base.interfaces import (
    ISourceProvider,
    ICompilerService,
    IssueTracker,
    IStateReader,
    ISymbolView,
    ILLMProvider,
    ILLMExecutor,
    IIntentManager,
)


class MockSourceProvider:
    """ISourceProvider 的模拟实现"""
    def __init__(self):
        self._sources = {}

    def get_line(self, file_path: str, lineno: int) -> Optional[str]:
        source = self._sources.get(file_path, "")
        lines = source.splitlines()
        if 0 < lineno <= len(lines):
            return lines[lineno - 1]
        return None

    def get_full_source(self, file_path: str) -> Optional[str]:
        return self._sources.get(file_path)


class MockIssueTracker:
    """IssueTracker 的模拟实现"""
    def __init__(self):
        self._issues = []

    def report(self, severity: Any, code: str, message: str,
               location: Optional[Any] = None, hint: Optional[str] = None) -> None:
        self._issues.append({
            "severity": severity,
            "code": code,
            "message": message,
            "location": location,
            "hint": hint
        })

    def has_errors(self) -> bool:
        return any(i["severity"].name == "ERROR" for i in self._issues)


class MockLLMProvider:
    """ILLMProvider 的模拟实现"""
    def __init__(self):
        self._last_call_info = {}

    def __call__(self, sys_prompt: str, user_prompt: str, scene: str = "general") -> str:
        self._last_call_info = {
            "sys_prompt": sys_prompt,
            "user_prompt": user_prompt,
            "scene": scene
        }
        return "Mock LLM response"

    def get_last_call_info(self) -> Dict[str, Any]:
        return self._last_call_info

    def set_retry_hint(self, hint: str) -> None:
        pass

    def get_retry_prompt(self, node_type: str) -> Optional[str]:
        return None


class MockIntentManager:
    """IIntentManager 的模拟实现"""
    def __init__(self):
        self._global_intents = []
        self._active_intents = []

    def set_global_intent(self, intent: str) -> None:
        self._global_intents = [intent]

    def clear_global_intents(self) -> None:
        self._global_intents = []

    def remove_global_intent(self, intent: str) -> None:
        if intent in self._global_intents:
            self._global_intents.remove(intent)

    def get_global_intents(self) -> List[Any]:
        return self._global_intents

    def get_active_intents(self) -> List[Any]:
        return self._active_intents

    def push_intent(self, intent: str, mode: str = "+", tag: Optional[str] = None) -> None:
        self._active_intents.append({"intent": intent, "mode": mode, "tag": tag})


class TestISourceProvider(unittest.TestCase):
    """测试 ISourceProvider 接口"""

    def test_interface_compliance(self):
        """验证 Mock 实现符合 ISourceProvider 协议"""
        provider = MockSourceProvider()
        self.assertTrue(isinstance(provider, ISourceProvider))

    def test_get_line_found(self):
        """测试 get_line 找到行"""
        provider = MockSourceProvider()
        provider._sources["test.ibci"] = "line1\nline2\nline3"
        result = provider.get_line("test.ibci", 2)
        self.assertEqual(result, "line2")

    def test_get_line_not_found(self):
        """测试 get_line 未找到"""
        provider = MockSourceProvider()
        result = provider.get_line("nonexistent.ibci", 1)
        self.assertIsNone(result)

    def test_get_full_source(self):
        """测试 get_full_source"""
        provider = MockSourceProvider()
        provider._sources["test.ibci"] = "line1\nline2"
        result = provider.get_full_source("test.ibci")
        self.assertEqual(result, "line1\nline2")


class TestILLMProvider(unittest.TestCase):
    """测试 ILLMProvider 接口"""

    def test_interface_compliance(self):
        """验证 Mock 实现符合 ILLMProvider 协议"""
        provider = MockLLMProvider()
        self.assertTrue(isinstance(provider, ILLMProvider))

    def test_call_returns_string(self):
        """测试 __call__ 返回字符串"""
        provider = MockLLMProvider()
        result = provider("sys", "user")
        self.assertIsInstance(result, str)

    def test_get_last_call_info(self):
        """测试 get_last_call_info"""
        provider = MockLLMProvider()
        provider("sys prompt", "user prompt", "general")
        info = provider.get_last_call_info()
        self.assertEqual(info["sys_prompt"], "sys prompt")
        self.assertEqual(info["user_prompt"], "user prompt")
        self.assertEqual(info["scene"], "general")


class TestIIntentManager(unittest.TestCase):
    """测试 IIntentManager 接口"""

    def test_interface_compliance(self):
        """验证 Mock 实现符合 IIntentManager 协议"""
        manager = MockIntentManager()
        self.assertTrue(isinstance(manager, IIntentManager))

    def test_global_intent_operations(self):
        """测试全局意图操作"""
        manager = MockIntentManager()
        manager.set_global_intent("test intent")
        self.assertEqual(manager.get_global_intents(), ["test intent"])
        manager.clear_global_intents()
        self.assertEqual(manager.get_global_intents(), [])

    def test_push_intent(self):
        """测试 push_intent"""
        manager = MockIntentManager()
        manager.push_intent("new intent", "+", "tag1")
        intents = manager.get_active_intents()
        self.assertEqual(len(intents), 1)
        self.assertEqual(intents[0]["intent"], "new intent")
        self.assertEqual(intents[0]["mode"], "+")

    def test_remove_global_intent(self):
        """测试移除全局意图"""
        manager = MockIntentManager()
        manager.set_global_intent("to remove")
        manager.remove_global_intent("to remove")
        self.assertEqual(manager.get_global_intents(), [])


if __name__ == "__main__":
    unittest.main()
