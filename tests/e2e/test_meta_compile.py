"""
tests/e2e/test_meta_compile.py

meta.compile（编译门原语，代码作值 M2）E2E 契约（设计：
`_meta_layer_design.md` §二/§三/§8.4 M2）：

- **compile-only**：代码字符串进程内静态校验（**不执行**）——子引擎（零父状态污染：
  父程序可能自身即字符串运行[合成 entry 同名冲突面]）；
- **fail-fast**：编译失败抛可被 IBCI ``try/except`` 捕获的错误（首个诊断 = 根因面，
  携带 ibci 源定位——合成 entry 标记 + line/column），成功静默（void）；
- **与 CLI check 面同构**（compile-only + 失败即断）；
- 源定位 file_path = 合成 entry ``<project_root>/__string_exec__.ibci``（稳定可辨识
  "字符串源"，替代 compile_string 的 tempfile 载体路径）；
- 无 LLM 依赖（compile-only，mock 模式行为一致）。
"""
import os

from tests.conftest import run_ibci, TESTS_ROOT


def _ibci_str(code: str) -> str:
    """把一段 IBCI 代码转为 IBCI 双引号字符串字面量（供 meta.compile 内嵌）。"""
    return code.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


MARKER = os.path.join(TESTS_ROOT, "__string_exec__.ibci")


class TestMetaCompile:
    def test_ok_silent(self):
        """正常编译：静默通过（void，无输出），父程序继续。"""
        code = (
            "import meta\n"
            "meta.compile(\"" + _ibci_str("str a = '1'\nprint(a)\n") + "\")\n"
            "print('after-compile-ok')\n"
        )
        out = run_ibci(code)
        # 静默（void）：父输出仅 after-compile-ok（meta.compile 自身无输出）
        assert out == ["after-compile-ok"]

    def test_syntax_error_caught(self):
        """语法错误：fail-fast，IBCI try/except 可捕获（不抛穿父，父存活）。"""
        code = (
            "import meta\n"
            "try:\n"
            "    meta.compile(\"" + _ibci_str("int x = = 5") + "\")\n"
            "    print('no-error-wrong')\n"
            "except:\n"
            "    print('caught')\n"
            "print('parent-alive')\n"
        )
        out = run_ibci(code)
        assert "caught" in out
        assert "no-error-wrong" not in out
        assert "parent-alive" in out

    def test_semantic_error_caught(self):
        """语义错误（类型违约）：fail-fast，IBCI try/except 可捕获。"""
        code = (
            "import meta\n"
            "try:\n"
            "    meta.compile(\"" + _ibci_str("str a = 5\n") + "\")\n"
            "    print('no-error-wrong')\n"
            "except:\n"
            "    print('caught')\n"
            "print('parent-alive')\n"
        )
        out = run_ibci(code)
        assert "caught" in out
        assert "parent-alive" in out

    def test_error_message_has_ibci_source_location(self):
        """错误面：catch 到的异常 message 含 ibci 源定位（合成 entry 标记 +
        line/column）。"""
        code = (
            "import meta\n"
            "try:\n"
            "    meta.compile(\"" + _ibci_str("int x = = 5") + "\")\n"
            "except Exception as e:\n"
            "    print(e.message)\n"
        )
        out = run_ibci(code)
        joined = "\n".join(out)
        # 合成 entry 标记（字符串源可辨识，非 tempfile 载体路径）
        assert "__string_exec__.ibci" in joined
        # ibci 源定位（line/column）
        assert "line 1" in joined and "column 9" in joined
        # 诊断码
        assert "PAR_UNEXPECTED_TOKEN" in joined

    def test_zero_parent_pollution(self):
        """父状态零污染：meta.compile 后父变量不变（子引擎独立，非父状态变异）。"""
        code = (
            "import meta\n"
            "meta.compile(\"" + _ibci_str("str b = 'child'") + "\")\n"
            "str c = 'parent-var'\n"
            "print(c)\n"
        )
        out = run_ibci(code)
        assert out == ["parent-var"]
        # 子编译的符号（b）不泄漏父环境
        assert "child" not in "\n".join(out)

    def test_compile_only_no_execution(self):
        """compile-only：meta.compile 不执行代码（有副作用的代码仅校验不运行）。"""
        # 若执行，print 会进父 stdout；compile-only 下父 stdout 无子 print
        code = (
            "import meta\n"
            "meta.compile(\"" + _ibci_str("print('should-not-print')\n") + "\")\n"
            "print('done')\n"
        )
        out = run_ibci(code)
        assert "should-not-print" not in out
        assert out == ["done"]

    def test_mock_mode_no_llm_dependency(self):
        """mock 模式行为一致：compile-only 无 LLM 依赖（mock 态下编译校验同行为）。"""
        code = (
            "import ai\n"
            "import meta\n"
            "ai.set_mock_mode()\n"
            "meta.compile(\"" + _ibci_str("str a = '1'\n") + "\")\n"
            "print('ok-in-mock')\n"
        )
        out = run_ibci(code)
        assert out == ["ok-in-mock"]
