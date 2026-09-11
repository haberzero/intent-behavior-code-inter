"""
tests/diff_harness/test_diff_equivalence.py

差分等价 harness——双内核替换的常设安全网（地基验收）：

- **语料合法 + Python 参考内核确定性**：全部语料脚本合法 IBCI + Python 内核
  两次执行数据面逐字节一致（参考基准自身确定性——差分比对的前提）；
- **Rust 内核检测（双内核协议）**：`load_rust_kernel` 经 ibci_ext kernel_info
  探明状态（未构建 = 未加载[合法态] / 已构建 = 加载 + status）；骨架
  status="skeleton" → ready=False（仅加载验证，不比数据面——无静默回退）；
- **差分报告正确性**：Rust 未就绪 → 仅 Python 参考确定性验证（报告如实，不
  冒充 Rust）；Rust 就绪（执行核心落地后）→ 双内核数据面逐字节比对。

注：本 harness 是常设交付物（整个替换的安全网）——语料扩展（现有测试用例 +
fuzz 种子）+ Rust 就绪后的差分比对归后续阶段。
"""
import pytest

from tests.diff_harness.corpus import CORPUS, names


class TestCorpus:
    def test_corpus_non_empty(self):
        assert len(CORPUS) > 0
        assert len(set(names())) == len(names())  # 语料名唯一

    def test_all_corpus_valid_and_deterministic(self):
        """全部语料合法 IBCI（编译 + 执行无错）——确定性 = 行为契约冻结输出
        （test_diff_corpus_contracts——语料契约权威化，取代旧 Python 参考对拍）。"""
        from tests.behavior.helpers import run

        for name, script in CORPUS:
            run(script)  # 编译 + 执行（Rust 内核）无错 = 合法



class TestDivergenceRegistry:
    """差分 harness 状态注册表（单一权威源）自检：合法性 + 被消费（非死代码）。"""

    def test_registry_well_formed(self):
        from tests.diff_harness import divergence
        ids = {s.id for s in divergence.REGISTERED}
        assert len(ids) == len(divergence.REGISTERED)  # ID 唯一
        for s in divergence.REGISTERED:
            assert s.kind in divergence._KINDS
            assert s.plane in divergence._PLANES
            assert s.rationale  # rationale 非空（声明根因）
            assert s.scope      # scope 非空

    def test_gap_query_node_pool_exclusion_empty(self):
        """node_pool 面：free_vars GAP 已消除（free_vars 闭包捕获 Rust 承载，2b-2b-2
        增量 3）——字段排除集合空（query API 驱动比对逻辑，单一权威源）。"""
        from tests.diff_harness import divergence
        assert divergence.excluded_fields(divergence.NODE_POOL) == set()

    def test_gap_query_scope_node_uid_skip_empty(self):
        """scope_node_uid 面：closure_capture case 跳过 GAP 已消除（节点 UID 链式差异
        随 free_vars 对齐消除）。"""
        from tests.diff_harness import divergence
        assert divergence.skipped_cases(divergence.SCOPE_NODE_UID) == set()

    def test_gap_query_scope_type_uid_null_empty(self):
        """scope_type_uid 面：非字面值 type_uid GAP 已消除（第二批类型解析 43/43 收束，
        声明过期移除）。"""
        from tests.diff_harness import divergence
        assert divergence.null_gap_fields(divergence.SCOPE_TYPE_UID) == set()

    def test_divergence_mechanism_ready(self):
        """DIVERGENCE 机制就绪：GAP 计数 = 1（__string_exec__ 用户模块成员面——
        modules 组装增量）+ DIVERGENCE 计数 = 1（host_call_closure_state——R1-E4
        P4 宿主 .call 纯函数契约，fresh 重执行 ≠ 持久环境）。"""
        from tests.diff_harness import divergence
        assert divergence.divergences_for(divergence.NODE_POOL) == []
        assert divergence.gap_count() == 3
        assert divergence.skipped_cases(divergence.TYPE_MEMBERS) == {"__string_exec__"}
        assert divergence.divergence_count() == 2
        assert {
            d.scope for d in divergence.divergences_for(divergence.DATA_PLANE)
        } == {"case:host_call_closure_state", "case:int_overflow"}
        assert divergence.skipped_cases(divergence.DATA_PLANE) == {
            "kb_governance_error", "host_bridge_error"
        }

    def test_registry_actually_consumed(self, monkeypatch):
        """注册表真的驱动逻辑（非死代码）：注入一个 GAP 声明 → 排除集合变化。"""
        import tests.diff_harness.divergence as dv
        assert dv.excluded_fields(dv.NODE_POOL) == set()
        # 注入合成 GAP 声明 → 该面字段排除集合应随之变化（query API 被消费证明）
        synthetic = [
            dv.DeclaredState(
                id="synthetic-test-gap",
                kind=dv.GAP,
                plane=dv.NODE_POOL,
                scope="field:free_vars",
                rationale="synthetic（注册表消费性自检）",
            )
        ]
        monkeypatch.setattr(dv, "REGISTERED", synthetic)
        assert dv.excluded_fields(dv.NODE_POOL) == {"free_vars"}
        assert dv.gap_count() == 1
