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
from tests.diff_harness.corpus import CORPUS, names
from tests.diff_harness.harness import differential_check, load_rust_kernel, python_kernel_data_plane


class TestCorpus:
    def test_corpus_non_empty(self):
        assert len(CORPUS) > 0
        assert len(set(names())) == len(names())  # 语料名唯一

    def test_all_corpus_valid_and_deterministic(self):
        """全部语料合法 IBCI + Python 内核两次执行数据面逐字节一致。"""
        for name, script in CORPUS:
            d1 = python_kernel_data_plane(script)
            d2 = python_kernel_data_plane(script)
            assert d1 == d2, f"语料 {name} Python 内核非确定性"


class TestRustKernelDetection:
    def test_load_handles_absent_so(self, tmp_path, monkeypatch):
        """Rust 未构建（.so 缺失）= 未加载（合法态，不崩）。"""
        import tests.diff_harness.harness as h
        monkeypatch.setattr(h, "_SO_PATH", str(tmp_path / "nope.so"))
        rk = h.load_rust_kernel()
        assert rk.loaded is False
        assert rk.ready is False

    def test_load_detects_skeleton(self):
        """Rust 已构建（.so 存在）= 加载 + kernel_info 探明状态。

        骨架 status="skeleton" → ready=False（仅加载验证）。若 .so 未
        构建（环境未跑 build_rust_ext.sh）= 未加载（合法态），断言不崩。
        """
        rk = load_rust_kernel()
        if rk.loaded:
            assert rk.name == "rust"
            assert rk.stage >= 1
            # 骨架未就绪（执行核心未落地）——ready 仅当 status == "ready"
            assert rk.ready is (rk.status == "ready")
        # 未加载亦是合法态（harness 优雅降级到仅 Python 参考）


class TestDifferentialReport:
    def test_report_python_reference_only_when_rust_not_ready(self):
        """Rust 未就绪 → 报告 = 仅 Python 参考确定性验证（14/14），不冒充 Rust。"""
        report = differential_check(CORPUS)
        assert report.total == len(CORPUS)
        assert report.python_deterministic == len(CORPUS)  # 参考内核全确定性
        assert not report.mismatches or all(
            m["kind"] != "differential" for m in report.mismatches
        )
        # Rust 就绪时才有差分比对（骨架 → compared=0）
        if not report.rust_ready:
            assert report.compared == 0
        summary = report.summary()
        assert "差分 harness" in summary
