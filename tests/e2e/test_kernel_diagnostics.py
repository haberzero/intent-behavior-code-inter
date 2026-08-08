"""
tests/e2e/test_kernel_diagnostics.py
======================================

诊断面（PT-FEAT-9）端到端事件投影测试。

验证三件事（黑盒，经 Python 侧订阅引擎级事件总线 + pytest.warns 断言警告投影）：
1. 协议回退站点：真实执行中 ``__snapshot__`` 协议失败 → 同时产生
   ``UserWarning``（文案逐字）与 ``kernel_diagnostic`` 事件（code/detail/message）。
2. 策略忽略站点：kernel-native 覆盖被忽略 → ``KDIAG_POLICY_MODULE_OVERRIDE``
   事件或警告（该站点在 engine 加载期调用，无活跃 EC → 仅警告面，fail-open）。
3. 门控：``runtime.configure(observability=False)`` 关闭后诊断事件不再发射，
   但警告投影保留（开发者可见性不受记录开关控制）。
"""
import json
import os
import warnings

import pytest

from core.engine import IBCIEngine
from tests.conftest import AI_MOCK_PREFIX, REPO_ROOT


def _run_and_collect(code: str, *, root_dir=None):
    """运行 IBCI 代码，返回 ``(out_lines, warnings, kernel_diag_events)``。

    事件经引擎级事件总线 Python 侧订阅（公开访问器，非 internals 穿透）。
    """
    eng = IBCIEngine(root_dir=root_dir or REPO_ROOT, auto_sniff=False)
    sub = eng.registry.get_event_bus().subscribe()
    out: list = []

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            eng.run_string(code, output_callback=lambda t: out.append(str(t)), silent=True)
        except Exception as exc:  # 测试断言失败由调用方处理
            caught_exc = exc
        else:
            caught_exc = None

    kernel_diag = []
    while True:
        ok, ev = sub.recv_nowait()
        if not ok:
            break
        if ev["type"] == "kernel_diagnostic":
            kernel_diag.append(ev["data"])

    return out, [str(w.message) for w in caught], kernel_diag, caught_exc


class TestProtocolFallbackEvents:
    """协议回退站点：警告 + 事件双投影。"""

    def test_snapshot_fallback_emits_event_and_warning(self):
        code = AI_MOCK_PREFIX + """
class Watcher:
    int val

    func __snapshot__(self) -> int:
        int z = 1 / 0
        return self.val

    func __restore__(self, int s) -> auto:
        self.val = s

Watcher w = Watcher(7)
str r = @~ MOCK:SEQ:[FAIL,DONE] ~
llmexcept:
    retry "hint"
print("final:" + (str)w.val)
"""
        out, warns, kd, exc = _run_and_collect(code)
        assert exc is None
        assert any("final:7" in line for line in out)

        # 警告投影：文案逐字（含协议回退语义）
        assert any("__snapshot__ protocol call failed for" in wmsg for wmsg in warns)

        # 事件投影：kernel_diagnostic 事件携带 code/detail/message
        snap_events = [d for d in kd if d["code"] == "KDIAG_PROTOCOL_SNAPSHOT_FALLBACK"]
        assert snap_events, f"expected KDIAG_PROTOCOL_SNAPSHOT_FALLBACK events, got {kd}"
        event = snap_events[0]
        assert "name" in event["detail"]
        assert "__snapshot__ protocol call failed for" in event["message"]

    def test_event_has_structured_code_and_detail(self):
        """事件 data 含稳定机器标识 code 与 JSON-safe detail。"""
        code = AI_MOCK_PREFIX + """
class Watcher:
    int val

    func __snapshot__(self) -> int:
        int z = 1 / 0
        return self.val

    func __restore__(self, int s) -> auto:
        self.val = s

Watcher w = Watcher(7)
str r = @~ MOCK:SEQ:[FAIL,DONE] ~
llmexcept:
    retry "hint"
"""
        _out, _warns, kd, exc = _run_and_collect(code)
        assert exc is None
        snap_events = [d for d in kd if d["code"] == "KDIAG_PROTOCOL_SNAPSHOT_FALLBACK"]
        assert snap_events
        detail = snap_events[0]["detail"]
        assert isinstance(detail["error"], str)  # JSON-safe（repr 化）
        assert isinstance(detail["name"], str)


class TestPolicyOverrideSite:
    """策略忽略站点（kernel 层，无活跃 EC → 警告面保持）。"""

    @staticmethod
    def _write_fake_isys(dest_dir: str) -> None:
        os.makedirs(dest_dir, exist_ok=True)
        with open(os.path.join(dest_dir, "_spec.py"), "w", encoding="utf-8") as f:
            f.write(
                "def __ibcext_metadata__():\n"
                '    return {"name": "isys", "kind": "method_module", "version": "1.0.0"}\n\n'
                "def __ibcext_vtable__():\n"
                '    return {"functions": {"entry_path": {"param_types": [], "return_type": "str"}}}\n'
            )
        with open(os.path.join(dest_dir, "core.py"), "w", encoding="utf-8") as f:
            f.write(
                "class FakeISys:\n"
                '    def entry_path(self):\n'
                '        return "/fake_override"\n\n'
                "def create_implementation():\n"
                "    return FakeISys()\n"
            )
        with open(os.path.join(dest_dir, "__init__.py"), "w", encoding="utf-8") as f:
            f.write("from .core import create_implementation\n")

    def test_override_protection_warns_without_event_when_no_ec(self, tmp_path):
        """kernel-native 覆盖被忽略：警告投影保持；站点无活跃 EC → 事件面跳过（fail-open）。"""
        fake_dir = tmp_path / "fake_isys"
        self._write_fake_isys(str(fake_dir))
        (tmp_path / "ibci.json").write_text(
            json.dumps({"plugin_paths": [str(tmp_path)]}),
            encoding="utf-8",
        )
        (tmp_path / "main.ibci").write_text(
            "import isys\nprint(isys.entry_path())\n",
            encoding="utf-8",
        )

        eng = IBCIEngine(root_dir=str(tmp_path), auto_sniff=False)
        sub = eng.registry.get_event_bus().subscribe()
        out = []
        with pytest.warns(UserWarning, match="reserved for kernel-native module"):
            eng.run(str(tmp_path / "main.ibci"), output_callback=lambda s: out.append(str(s)), silent=True)
        assert not any("/fake_override" in line for line in out)

        # 覆盖站点发生在 engine 加载期（无活跃 EC）→ 事件面可不触发，但机制不报错
        ok, _ = sub.recv_nowait()
        # 不强制断言事件；仅确认 warning 投影保持（fail-open 契约）

    def test_override_in_active_ec_emits_event(self, engine):
        """注入链路：活跃 EC 下 kernel-native 覆盖经注入发射器发出警告+事件。

        覆盖检测由 kernel 层 HostInterface 完成，经注入的 emitter（runtime 层
        kernel_diagnostic）发射双投影；无活跃 EC 时仅警告（fail-open）。
        """
        engine.run_string("int seed = 1\n", silent=True)
        from core.runtime.frame import set_current_execution_context, reset_current_execution_context
        ec = engine.interpreter.execution_context
        ec.runtime_context = engine.interpreter.runtime_context
        token = set_current_execution_context(ec)
        try:
            sub = engine.registry.get_event_bus().subscribe()
            with pytest.warns(UserWarning, match="reserved for kernel-native module"):
                engine.host_interface.register_module("isys", object(), discovery_name="fake_isys")
            ok, ev = sub.recv_nowait()
            assert ok
            assert ev["type"] == "kernel_diagnostic"
            assert ev["data"]["code"] == "KDIAG_POLICY_MODULE_OVERRIDE"
        finally:
            reset_current_execution_context(token)


class TestEnvLimitDiagnostic:
    """环境限制分类（PT-DEBT-9）：栈溢出根因保留 + 诊断事件双投影。"""

    def test_recursion_error_emits_classified_diagnostic(self):
        """深递归触底：RecursionError 根因传播，且发射 KDIAG_RUNTIME_ENV_LIMIT 事件。"""
        code = """
func f(int n) -> int:
    if n <= 1:
        return 1
    return f(n - 1) + 1

print(f(5000))
"""
        out, warns, kd, exc = _run_and_collect(code)
        assert isinstance(exc, RecursionError), (
            f"expected RecursionError root cause, got {type(exc).__name__}: {exc}"
        )
        # 警告投影：环境限制分类信息可见
        assert any("环境限制异常 RecursionError" in wmsg for wmsg in warns)
        # 事件投影：KDIAG_RUNTIME_ENV_LIMIT 携带 exc_type/message
        ev = [d for d in kd if d["code"] == "KDIAG_RUNTIME_ENV_LIMIT"]
        assert ev, f"expected KDIAG_RUNTIME_ENV_LIMIT events, got {kd}"
        assert ev[0]["detail"]["exc_type"] == "RecursionError"


class TestDiagnosticGate:
    """门控：observability 关 → 事件停止，警告保留。"""

    def test_observability_off_suppresses_event_keeps_warning(self):
        code = (
            "import iruntime\n"
            "import ai\n"
            'ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")\n'
            "iruntime.configure(observability=False)\n"
            """
class Watcher:
    int val

    func __snapshot__(self) -> int:
        int z = 1 / 0
        return self.val

    func __restore__(self, int s) -> auto:
        self.val = s

Watcher w = Watcher(7)
str r = @~ MOCK:SEQ:[FAIL,DONE] ~
llmexcept:
    retry "hint"
"""
        )
        _out, warns, kd, exc = _run_and_collect(code)
        assert exc is None
        # 警告投影保留（不门控）
        assert any("__snapshot__ protocol call failed for" in wmsg for wmsg in warns)
        # 事件投影被 observability 开关抑制
        assert not any(d["code"] == "KDIAG_PROTOCOL_SNAPSHOT_FALLBACK" for d in kd), (
            f"expected no kernel_diagnostic events with observability off, got {kd}"
        )
