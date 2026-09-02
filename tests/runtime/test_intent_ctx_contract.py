"""
tests/runtime/test_intent_ctx_contract.py
==========================================

``intent_context`` 封装对象的 ``fields['_ctx']`` 槽单一权威访问契约（PT-DEBT-35）。

修复背景（2026-08-20）：``_ctx`` 槽是全仓 ~20 处共享的半文档化内部契约，各调用点
散落 ``fields.get("_ctx")`` 字段探测（双轨判别），任何恰有非 None ``_ctx`` 字段的
普通对象都可能误激活。本次将读写收敛为 ``intent_context.get_intent_ctx`` /
``set_intent_ctx`` 单一入口（isinstance(IbIntentContext) 精确判别），全仓调用点
统一走此入口，消除字段探测双轨。

判别维度：
- get_intent_ctx：intent_context 实例返回其 IbIntentContext；普通对象（含
  伪造 _ctx 字段）返回 None（类型判别，不误激活）；
- set_intent_ctx：写入后 get_intent_ctx 可读回（round-trip）。
"""
import os

from core.engine import IBCIEngine
from core.runtime.objects.intent_context import get_intent_ctx, set_intent_ctx, IbIntentContext

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _new_engine():
    return IBCIEngine(root_dir=_ROOT)


class TestGetIntentCtxContract:
    def test_intent_context_instance_returns_ctx(self):
        """intent_context 实例经 get_intent_ctx 返回其底层 IbIntentContext。"""
        eng = _new_engine()
        out = []
        eng.run_string(
            "intent_context c = intent_context()\nprint(\"ok\")\n",
            output_callback=lambda s: out.append(str(s)),
            silent=True,
        )
        assert out == ["ok"]
        # 直接构造封装对象验证契约访问器
        cls = eng.registry.get_class("intent_context")
        from core.runtime.objects.kernel import IbObject

        obj = IbObject(cls)
        set_intent_ctx(obj, IbIntentContext())
        assert get_intent_ctx(obj) is not None
        assert isinstance(get_intent_ctx(obj), IbIntentContext)

    def test_plain_object_with_fake_ctx_returns_none(self):
        """普通对象伪造 _ctx 字段 → get_intent_ctx 返回 None（isinstance 判别不误激活）。

        回归：修复前字段探测（``fields.get("_ctx") is not None``）会让任何带
        非 None _ctx 字段的普通对象误判为意图上下文。
        """
        from core.runtime.objects.kernel import IbObject

        class Fake:
            pass

        cls = _new_engine().registry.get_class("Object")
        obj = IbObject(cls)
        obj.fields["_ctx"] = object()  # 伪造非 IbIntentContext 的 _ctx
        assert get_intent_ctx(obj) is None

    def test_non_object_returns_none(self):
        """非 IbObject（裸 Python 值）→ get_intent_ctx 返回 None。"""
        assert get_intent_ctx(42) is None
        assert get_intent_ctx("ctx") is None

    def test_set_get_roundtrip(self):
        """set_intent_ctx 写入后 get_intent_ctx 读回同一实例（round-trip）。"""
        eng = _new_engine()
        cls = eng.registry.get_class("intent_context")
        from core.runtime.objects.kernel import IbObject

        obj = IbObject(cls)
        ctx = IbIntentContext()
        set_intent_ctx(obj, ctx)
        assert get_intent_ctx(obj) is ctx

    def test_set_none_clears(self):
        """set_intent_ctx(obj, None) 清除 _ctx（get_intent_ctx 返回 None）。"""
        eng = _new_engine()
        cls = eng.registry.get_class("intent_context")
        from core.runtime.objects.kernel import IbObject

        obj = IbObject(cls)
        set_intent_ctx(obj, IbIntentContext())
        set_intent_ctx(obj, None)
        assert get_intent_ctx(obj) is None
