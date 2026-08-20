# -*- coding: utf-8 -*-
"""
tests/e2e/test_intent_value_stack.py
=====================================

（G5 意图值栈）：意图段在注释/栈操作执行点 eager 求值为**一等值**，
`@-` 按**值派生渲染文本**匹配（修复动态意图按退化字符串匹配失效）。

判别维度：
- eager 值捕获：`@+ $x` 压入当时 x 的值；之后重赋值 x 不影响已压入意图。
- 按值匹配：`@+ $x` 后 `@- $x` / `@- <同值字面量>` 移除；不同值不移除。
- 解析修复：`@- "text"`（带空格）不再被误判为 pop_top（PAR_EXPECTED_TOKEN）。
"""
from tests.conftest import run_ibci


def _resolve_view(code: str) -> str:
    """运行代码并返回 ``ctx.resolve()`` 渲染视图（含尾段）。"""
    lines = run_ibci(code)
    assert len(lines) == 1, f"expected single view line, got {lines}"
    return lines[0]


class TestIntentEagerValueCapture:
    def test_push_captures_value_at_push_time(self):
        """G5：``@+ $x`` 压入当时值；重赋值后已压入意图不变。"""
        code = '''
str x = "captured"
@+ $x
x = "changed"
intent_context ctx = intent_context.get_current()
print((str)ctx.resolve())
'''
        assert "captured" in _resolve_view(code)
        assert "changed" not in _resolve_view(code)

    def test_push_then_reassign_removal_needs_original_value(self):
        """G5：eager 捕获后按原值移除（重赋值后的新值不移除原意图）。"""
        code = '''
str x = "captured"
@+ $x
x = "changed"
@- "changed"
intent_context ctx = intent_context.get_current()
print((str)ctx.resolve())
'''
        assert "captured" in _resolve_view(code)


class TestIntentValueMatching:
    def test_remove_by_var_value(self):
        """G5：``@- $x`` 按值移除 ``@+ $x``。"""
        code = '''
str style = "formal"
@+ $style
@- $style
intent_context ctx = intent_context.get_current()
print((str)ctx.resolve())
'''
        assert _resolve_view(code) == "[]"

    def test_remove_by_literal_value(self):
        """G5：``@- 42`` 按值移除 ``@+ $n``（n=42，跨类型字面量同值）。"""
        code = '''
int n = 42
@+ $n
@- 42
intent_context ctx = intent_context.get_current()
print((str)ctx.resolve())
'''
        assert _resolve_view(code) == "[]"

    def test_remove_does_not_remove_different_value(self):
        """G5：值不同不移除。"""
        code = '''
str x = "formal"
@+ $x
str y = "other"
@- $y
intent_context ctx = intent_context.get_current()
print((str)ctx.resolve())
'''
        assert "formal" in _resolve_view(code)

    def test_remove_string_with_space_parses(self):
        """解析修复：``@- "text"``（带空格）不被误判 pop_top。"""
        code = '''
@+ "A"
@- "A"
intent_context ctx = intent_context.get_current()
print((str)ctx.resolve())
'''
        assert _resolve_view(code) == "[]"

    def test_static_string_behavior_unchanged(self):
        """回归：静态字符串意图 push/remove 行为不变。"""
        code = '''
@+ "A"
@+ "B"
@- "A"
intent_context ctx = intent_context.get_current()
print((str)ctx.resolve())
'''
        view = _resolve_view(code)
        assert "B" in view
        assert "A" not in view
