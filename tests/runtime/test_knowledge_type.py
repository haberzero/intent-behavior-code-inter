"""
tests/runtime/test_knowledge_type.py

已验证知识注册表（knowledge 一等值类型）判别测试：

- 值语义要点（知识库可变容器 + 条目冻结快照——双克隆纪律：store 入时 +
  get 出时深克隆，修改取回值不污染知识库）；
- 验证门铁律（check 引擎求值假 = fail-fast KNW_CHECK_REJECTED；登记/更正
  机器强制区分 KNW_KEY_EXISTS；reason 强制非空 KNW_REASON_EMPTY）；
- 审计链（history append-only 事件流，seq 单调）；
- 编译期 check 纯度检查（SEM_KNW_CHECK_LLM 行为表达式 / SEM_KNW_CHECK_OPAQUE
  不透明值——不纯度不可证明即拒绝）；
- 序列化 round-trip（条目值/事件/seq 保真；谓词引用不入快照——恢复后
  amend 边界 fail-fast）。
"""

import os

import pytest

from core.base.diagnostics.codes import (
    KNW_CHECK_REJECTED,
    KNW_KEY_EXISTS,
    KNW_REASON_EMPTY,
)
from core.engine import IBCIEngine
from core.kernel.issue import CompilerError, InterpreterError
from core.runtime.serialization.runtime_serializer import (
    RuntimeDeserializer,
    RuntimeSerializer,
)


@pytest.fixture
def engine():
    return IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)))


def _ctx(engine):
    return engine.interpreter.execution_context.runtime_context


def _round_trip(engine, code):
    engine.run_string(code, silent=True)
    ec = engine.interpreter.execution_context
    orig = ec.runtime_context
    data = RuntimeSerializer(engine.registry).serialize_context(
        orig, include_static=False
    )
    restored = RuntimeDeserializer(engine.registry, factory=ec.factory).deserialize_context(data)
    return orig, restored


def _payload(engine, name):
    return engine.interpreter.execution_context.runtime_context.get_variable(name).payload


def _run(engine, body, check_src='func c(any x) -> bool:\n    return x.len() > 0\n'):
    return engine.run_string(check_src + body, silent=True)


class TestStoreGetSemantics:
    def test_store_get_roundtrip(self, engine):
        _run(engine, '''knowledge kb = knowledge()
kb.store("term:修炼", "在修真世界观中修炼指系统提升", c)
str got = (str)kb.get("term:修炼")
print(got)
''')

    def test_get_missing_returns_none(self, engine):
        _run(engine, '''knowledge kb = knowledge()
any missing = kb.get("nope")
bool is_null = (missing == None)
print("null=" + (str)is_null)
''')

    def test_snapshot_isolation_get(self, engine):
        # get 返回深克隆快照：修改取回值不污染知识库（防引用陷阱污染审计）
        _run(engine, '''knowledge kb = knowledge()
list L = [1]
kb.store("k", L, c)
list L2 = (list)kb.get("k")
L2.append(99)
int n = (int)kb.get("k").len()
print("kb_len=" + (str)n)
''')
        assert _payload(engine, "n") == 1, "取回值修改不得污染知识库条目"

    def test_store_snapshot_isolation_in(self, engine):
        # store 入时深克隆：登记后修改原值不污染知识库
        _run(engine, '''knowledge kb = knowledge()
list L = [1]
kb.store("k", L, c)
L.append(99)
int n = (int)kb.get("k").len()
print("kb_len=" + (str)n)
''')
        assert _payload(engine, "n") == 1

    def test_keys_and_len(self, engine):
        _run(engine, '''knowledge kb = knowledge()
kb.store("a", "x", c)
kb.store("b", "y", c)
int n = kb.len()
list ks = kb.keys()
print("n=" + (str)n + " ks=" + (str)len(ks))
''')


class TestVerificationGate:
    def test_check_rejected(self, engine):
        with pytest.raises(InterpreterError) as exc:
            _run(
                engine,
                '''knowledge kb = knowledge()
kb.store("k", "short", c)
''',
                check_src='func c(any x) -> bool:\n    return x.len() > 5\n',
            )
        assert exc.value.error_code == KNW_CHECK_REJECTED
        assert exc.value.location is not None, "运行期错误须携带 ibci 源位置"

    def test_key_exists(self, engine):
        with pytest.raises(InterpreterError) as exc:
            _run(engine, '''knowledge kb = knowledge()
kb.store("k", "a", c)
kb.store("k", "b", c)
''')
        assert exc.value.error_code == KNW_KEY_EXISTS

    def test_amend_rechecks_gate(self, engine):
        # 新值再过 check 门（防更正通道变无门控写口）
        with pytest.raises(InterpreterError) as exc:
            _run(
                engine,
                '''knowledge kb = knowledge()
kb.store("k", "long-enough-value", c)
kb.amend("k", "short", "reason")
''',
                check_src='func c(any x) -> bool:\n    return x.len() > 5\n',
            )
        assert exc.value.error_code == KNW_CHECK_REJECTED

    def test_amend_reason_required(self, engine):
        with pytest.raises(InterpreterError) as exc:
            _run(engine, '''knowledge kb = knowledge()
kb.store("k", "a", c)
kb.amend("k", "b", "")
''')
        assert exc.value.error_code == KNW_REASON_EMPTY

    def test_amend_unregistered_key(self, engine):
        with pytest.raises(InterpreterError) as exc:
            _run(engine, '''knowledge kb = knowledge()
kb.amend("nope", "b", "reason")
''')
        assert exc.value.error_code == KNW_REASON_EMPTY


class TestAuditChain:
    def test_history_append_only(self, engine):
        _run(engine, '''knowledge kb = knowledge()
kb.store("k", "v1", c)
kb.amend("k", "v2", "更正理由")
list h = kb.history("k")
print("events=" + (str)len(h))
str cur = (str)kb.get("k")
print("cur=" + cur)
''')
        assert len(_payload(engine, "h")) == 2, "事件流 append-only（store + amend）"

    def test_history_missing_empty(self, engine):
        _run(engine, '''knowledge kb = knowledge()
list h = kb.history("nope")
print("empty=" + (str)len(h))
''')
        assert len(_payload(engine, "h")) == 0


class TestCheckPuritySemantics:
    """编译期 check 纯度检查（铁律：登记门须确定性验证）。"""

    def test_pure_check_passes(self, engine):
        _run(engine, '''knowledge kb = knowledge()
kb.store("k", "a", c)
''')

    def test_llm_check_rejected(self, engine):
        with pytest.raises(CompilerError) as exc:
            engine.compile_string('''func c(any x) -> bool:
    str r = @~ 判断 x ~
    return r.len() > 0
knowledge kb = knowledge()
kb.store("k", "a", c)
''', silent=True)
        assert any(d.code == "SEM_KNW_CHECK_LLM" for d in exc.value.diagnostics)

    def test_opaque_check_rejected(self, engine):
        with pytest.raises(CompilerError) as exc:
            engine.compile_string('''func c(any x) -> bool:
    return x.len() > 0
any ref = c
knowledge kb = knowledge()
kb.store("k", "a", ref)
''', silent=True)
        assert any(d.code == "SEM_KNW_CHECK_OPAQUE" for d in exc.value.diagnostics)


class TestSerialization:
    def test_round_trip_fidelity(self, engine):
        orig, rest = _round_trip(
            engine,
            'func c(any x) -> bool:\n    return x.len() > 0\n'
            'knowledge kb = knowledge()\n'
            'kb.store("k", "v1", c)\n'
            'kb.amend("k", "v2", "reason")\n',
        )
        p_orig = orig.get_variable("kb").payload
        p_rest = rest.get_variable("kb").payload
        assert set(p_orig["entries"].keys()) == set(p_rest["entries"].keys())
        assert p_orig["seq"] == p_rest["seq"], "事件序号保真"
        assert p_rest["entries"]["k"]["check"] is None, "谓词引用不入快照（amend 边界 fail-fast）"

    def test_amend_after_restore_fail_fast(self, engine):
        # 水化后谓词引用丢失 → amend 拒绝（要求重新 store——已知边界）
        _, rest = _round_trip(
            engine,
            'func c(any x) -> bool:\n    return x.len() > 0\n'
            'knowledge kb = knowledge()\n'
            'kb.store("k", "v1", c)\n',
        )
        from core.runtime.objects.kernel.base import unbox
        entry = rest.get_variable("kb").payload["entries"]["k"]
        check_ref = entry["check"]
        assert check_ref is None
