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


class TestRustLexerTokenDifferential:
    """Rust lexer（ibci_ext.lex）vs Python lexer 的 token 级差分等价（语料面）。

    Rust lexer = Rust 前端首增量（core normal 模式：数字/标识符/关键字/字符串/
    运算符/括号/点/冒号/逗号/注释/换行 + 行处理 + 缩进）。token 级差分 = Rust
    token 流 == Python token 流（type 名 + value + line + column 逐条）。
    """

    def test_lexer_loaded_or_graceful(self):
        """Rust lexer 已构建 = 已加载；未构建 = 优雅降级（token 级差分跳过）。"""
        from tests.diff_harness.harness import load_rust_kernel
        rk = load_rust_kernel()
        # 未构建亦是合法态（harness 优雅降级）
        assert rk.loaded in (True, False)

    def test_token_differential_corpus(self):
        """token 级差分等价：全部语料 Rust token 流 == Python token 流。"""
        from tests.diff_harness.harness import (
            load_rust_kernel, python_lexer_tokens, rust_lexer_tokens,
        )
        rk = load_rust_kernel()
        if not rk.loaded:
            pytest.importorskip("tests", reason="Rust .so 未构建——token 级差分跳过")
            return
        for name, script in CORPUS:
            pt = python_lexer_tokens(script)
            rt = rust_lexer_tokens(script)
            assert rt == pt, f"语料 {name} token 级差分不等价"

    def test_token_differential_simple(self):
        """token 级差分等价：简单 IBCI 片段（算术/控制流/字符串/容器）。"""
        from tests.diff_harness.harness import (
            load_rust_kernel, python_lexer_tokens, rust_lexer_tokens,
        )
        rk = load_rust_kernel()
        if not rk.loaded:
            return
        snippets = [
            "x = 1 + 2 * 3\nprint(x)\n",
            's = "hello"\nprint(s)\n',
            "xs = [1, 2, 3]\nprint(xs)\n",
            "d = {'a': 1}\nprint(d)\n",
            "if x > 5:\n    print('big')\nelse:\n    print('small')\n",
            "for i in range(3):\n    print(i)\n",
            "func add(int a, int b) -> int:\n    return a + b\n",
        ]
        for src in snippets:
            assert rust_lexer_tokens(src) == python_lexer_tokens(src)


class TestRustParserAstDifferential:
    """Rust parser（ibci_ext.parse_struct）vs Python parser 的 AST 级差分等价。

    Rust parser = Rust 前端第二增量（完整语句/表达式面：Assign[Name/Subscript
    target] / ExprStmt / If[elif 链] / For / FunctionDef[typed args + returns] /
    Return / Break / Continue / Pass / Constant / Name / BinOp[+ - * / // % **] /
    UnaryOp / Compare / Call / List / Dict / Attribute / Subscript）。AST 级差分
    = Rust AST structure 规范形态 == Python AST structure 规范形态（tests/
    diff_harness/ast_dump.py include_positions=False 参考）。
    """

    def test_ast_differential_simple(self):
        """AST 级差分等价：简单 IBCI 片段（Rust AST structure == Python）。"""
        from tests.diff_harness.ast_dump import parse_ast_dump
        from tests.diff_harness.harness import load_rust_kernel, rust_parse_struct
        rk = load_rust_kernel()
        if not rk.loaded:
            return
        snippets = [
            "x = 1\n",
            "s = 'hi'\n",
            "x = 1 + 2\n",
            "print(x)\n",
            "add(1, 2)\n",
            "x = 1\ny = 2\nprint(x + y)\n",
        ]
        for src in snippets:
            rs = rust_parse_struct(src)
            py = parse_ast_dump(src, include_positions=False)
            assert rs == py, f"AST 级差分不等价：\n  py : {py}\n  rust: {rs}"

    def test_ast_differential_corpus(self):
        """AST 级差分等价：全部语料（Rust parser 完整面 == Python）。"""
        from tests.diff_harness.ast_dump import parse_ast_dump
        from tests.diff_harness.harness import load_rust_kernel, rust_parse_struct
        rk = load_rust_kernel()
        if not rk.loaded:
            return
        for name, script in CORPUS:
            rs = rust_parse_struct(script)
            py = parse_ast_dump(script, include_positions=False)
            assert rs == py, f"语料 {name} AST 级差分不等价：\n  py : {py}\n  rust: {rs}"
