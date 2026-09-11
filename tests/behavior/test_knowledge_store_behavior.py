"""语言行为层：knowledge 一等值类型（验证知识注册表）——R3-C5 迁移（原
tests/runtime/test_knowledge_type.py 白盒断言 → 可观察断言面）。

**迁移映射**：store/get 往返 + 快照隔离（取回修改不污染/入时克隆）+ keys/len
+ 审计链 + 验证门（check 拒绝/键已存在/reason 强制）→ 数据面 + 诊断码断言；
编译期 check 纯度（LLM 行为/不透明引用）→ 编译诊断码断言；ihost 状态往返 →
宿主面层（tests/host/）；legacy RuntimeSerializer round-trip = ⑦ 路径删除 +
契约登记（Rust artifact 契约面）。
"""

from core.kernel.issue import CompilerError

from tests.behavior.helpers import assert_error, assert_output, run

_CHECK = "func c(any x) -> bool:\n    return x.len() > 0\n"


class TestStoreGetSemantics:
    def test_store_get_roundtrip(self):
        assert_output(
            _CHECK
            + "knowledge kb = knowledge()\n"
            "kb.store('term:修炼', '在修真世界观中修炼指系统提升', c)\n"
            "str got = (str)kb.get('term:修炼')\n"
            "print(got)\n",
            ["在修真世界观中修炼指系统提升"],
        )

    def test_get_missing_returns_none(self):
        assert_output(
            _CHECK
            + "knowledge kb = knowledge()\n"
            "any missing = kb.get('nope')\n"
            "print(missing == None)\n",
            ["True"],
        )

    def test_snapshot_isolation_get(self):
        # get 返回深克隆快照：修改取回值不污染知识库（防引用陷阱污染审计）
        assert_output(
            _CHECK
            + "knowledge kb = knowledge()\n"
            "list L = [1]\n"
            "kb.store('k', L, c)\n"
            "list L2 = (list)kb.get('k')\n"
            "L2.append(99)\n"
            "print(kb.get('k').len())\n",
            ["1"],
        )

    def test_snapshot_isolation_in(self):
        # store 入时深克隆：登记后修改原值不污染知识库
        assert_output(
            _CHECK
            + "knowledge kb = knowledge()\n"
            "list L = [1]\n"
            "kb.store('k', L, c)\n"
            "L.append(99)\n"
            "print(kb.get('k').len())\n",
            ["1"],
        )

    def test_keys_and_len(self):
        assert_output(
            _CHECK
            + "knowledge kb = knowledge()\n"
            "kb.store('a', 'x', c)\n"
            "kb.store('b', 'y', c)\n"
            "print(kb.len())\n"
            "print(len(kb.keys()))\n",
            ["2", "2"],
        )


class TestVerificationGate:
    """验证门铁律（check 引擎求值假 = fail-fast；键已存在/reason 强制）。"""

    def test_check_rejected(self):
        assert_error(
            "func c(any x) -> bool:\n    return x.len() > 5\n"
            "knowledge kb = knowledge()\n"
            "kb.store('k', 'short', c)\n",
            "KNW_CHECK_REJECTED",
            line=4,
        )

    def test_key_exists(self):
        assert_error(
            _CHECK
            + "knowledge kb = knowledge()\n"
            "kb.store('k', 'a', c)\n"
            "kb.store('k', 'b', c)\n",
            "KNW_KEY_EXISTS",
            line=5,
        )

    def test_amend_rechecks_gate(self):
        # 新值再过 check 门（防更正通道变无门控写口）
        assert_error(
            "func c(any x) -> bool:\n    return x.len() > 5\n"
            "knowledge kb = knowledge()\n"
            "kb.store('k', 'long-enough-value', c)\n"
            "kb.amend('k', 'short', 'reason')\n",
            "KNW_CHECK_REJECTED",
            line=5,
        )

    def test_amend_reason_required(self):
        assert_error(
            _CHECK
            + "knowledge kb = knowledge()\n"
            "kb.store('k', 'a', c)\n"
            "kb.amend('k', 'b', '')\n",
            "KNW_REASON_EMPTY",
            line=5,
        )

    def test_amend_unregistered_key(self):
        assert_error(
            _CHECK + "knowledge kb = knowledge()\nkb.amend('nope', 'b', 'reason')\n",
            "KNW_REASON_EMPTY",
            line=4,
        )


class TestAuditChain:
    def test_history_append_only(self):
        assert_output(
            _CHECK
            + "knowledge kb = knowledge()\n"
            "kb.store('k', 'v1', c)\n"
            "kb.amend('k', 'v2', '更正理由')\n"
            "print(len(kb.history('k')))\n"
            "print(kb.get('k'))\n",
            ["2", "v2"],
        )

    def test_history_missing_empty(self):
        assert_output(
            _CHECK + "knowledge kb = knowledge()\nprint(len(kb.history('nope')))\n",
            ["0"],
        )


class TestCheckPuritySemantics:
    """编译期 check 纯度检查（登记门须确定性验证）。"""

    def test_pure_check_passes(self):
        assert_output(
            _CHECK + "knowledge kb = knowledge()\nkb.store('k', 'a', c)\nprint('ok')\n",
            ["ok"],
        )

    def test_llm_check_rejected(self):
        try:
            run(
                "func c(any x) -> bool:\n"
                "    str r = @~ 判断 x ~\n"
                "    return r.len() > 0\n"
                "knowledge kb = knowledge()\n"
                "kb.store('k', 'a', c)\n"
            )
            raise AssertionError("Expected SEM_KNW_CHECK_LLM")
        except CompilerError as e:
            codes = [d.code for d in getattr(e, "diagnostics", [])]
            assert "SEM_KNW_CHECK_LLM" in codes, f"diags={codes}"

    def test_opaque_check_rejected(self):
        try:
            run(
                "func c(any x) -> bool:\n"
                "    return x.len() > 0\n"
                "any ref = c\n"
                "knowledge kb = knowledge()\n"
                "kb.store('k', 'a', ref)\n"
            )
            raise AssertionError("Expected SEM_KNW_CHECK_OPAQUE")
        except CompilerError as e:
            codes = [d.code for d in getattr(e, "diagnostics", [])]
            assert "SEM_KNW_CHECK_OPAQUE" in codes, f"diags={codes}"
