"""
tests/e2e/test_ihost_run_code.py

ihost.run_code（字符串源进程内子 run + 结果捕获）E2E 契约——与 run_file
**机制同构**（同一 spawn 核心字符串源：子 project_root = 父 project_root，合成
entry ``__string_exec__`` 锚定；同一 E1 LLM 继承 / 沙箱 / 防卡死 / 输出捕获 /
错误作值纪律）。判别面（批次 M1）：

- 正常路径：输出捕获（r.stdout）+ exit_status=ok；
- 运行期异常路径：错误作值（exit_status=error + 结构化 exception{code,source}，
  不抛穿父）；
- 字符串源编译错误：PAR_ 码经 exception 值面传递（父不受影响）；
- 超时路径：collect_timeout；
- 沙箱边界：字符串代码 fs 操作限父 project_root（内 = ok，外 = RUN_PERMISSION_ERROR）；
- E1 继承：字符串源子环境继承父 LLM 配置（spawn 时点快照，经同一 on_ready 钩子）。

消除试用方"手写临时文件 + run_file"的胶水绕路。
"""
import os

from tests.conftest import run_ibci, TESTS_ROOT


def _ibci_str(code: str) -> str:
    """把一段 IBCI 代码转为 IBCI 双引号字符串字面量（供 run_code 内嵌）。"""
    return code.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


class TestRunCode:
    def test_ok_record(self):
        """字符串源子 run 成功：exit_status=ok + stdout 捕获。"""
        child = "print('hello-child')\n"
        code = (
            "import ihost\n"
            f'run_result r = ihost.run_code("{_ibci_str(child)}", {{}})\n'
            "print(r.exit_status)\n"
            "print(r.stdout)\n"
        )
        out = run_ibci(code)
        joined = "\n".join(out)
        assert "ok" in out
        assert "hello-child" in joined

    def test_runtime_error_structured(self):
        """字符串源运行期失败：exit_status=error + 结构化 code + 父存活。"""
        child = "int a = 1\nint b = 0\nint c = a / b\nprint(c)\n"
        code = (
            "import ihost\n"
            f'run_result r = ihost.run_code("{_ibci_str(child)}", {{}})\n'
            "print(r.exit_status)\n"
            "dict ex = r.exception\n"
            'print(ex["code"])\n'
            "print('parent-alive')\n"
        )
        out = run_ibci(code)
        joined = "\n".join(out)
        assert "error" in out
        assert "RUN_DIVISION_BY_ZERO" in joined
        assert "parent-alive" in out

    def test_compile_error_captured(self):
        """字符串源编译错误（语法）：PAR_ 码经 exception 值面传递，父存活。"""
        child = "int x = = 5\n"
        code = (
            "import ihost\n"
            f'run_result r = ihost.run_code("{_ibci_str(child)}", {{}})\n'
            "print(r.exit_status)\n"
            "dict ex = r.exception\n"
            'print(ex["code"])\n'
            "print('parent-alive')\n"
        )
        out = run_ibci(code)
        joined = "\n".join(out)
        assert "error" in out
        assert "PAR_UNEXPECTED_TOKEN" in joined
        assert "parent-alive" in out

    def test_collect_timeout_policy(self):
        """防卡死：policy collect_timeout 有限 → 超时 = exception.message 携带
        timed out（子线程 daemon 孤儿语义既有，不阻断父）。"""
        # 循环规模裁定：P4 v1.5 cond-codegen 后 VM 实测 ~100000 迭代 ≈ 2.4s（>
        # collect_timeout 1s，触发超时判别）；此前（CPS 路径）~20000 迭代 ≈ 3.75s——
        # codegen 加速 ~5×，迭代数相应上调保超时判别成立。孤儿线程（daemon）总寿命
        # ~2.4s——远小于 run_file 的 ~100k/18s，压低套件 GC 收尾的孤儿负载（防看门狗
        # 误杀）。
        child = "int i = 0\nwhile i < 100000:\n    i = i + 1\n"
        code = (
            "import ihost\n"
            f'run_result r = ihost.run_code("{_ibci_str(child)}", '
            '{"collect_timeout": 1})\n'
            "print(r.exit_status)\n"
            "dict ex = r.exception\n"
            'print(ex["message"])\n'
        )
        out = run_ibci(code)
        joined = "\n".join(out)
        assert "error" in out
        assert "timed out" in joined

    def test_fs_within_project_root(self):
        """沙箱内：字符串源子代码 fs 写父 project_root 内相对路径 = ok。"""
        child = (
            "import fs\n"
            "fs.write('./_run_code_child_out.txt', 'from-string-child')\n"
            "print('wrote')\n"
        )
        try:
            code = (
                "import ihost\n"
                f'run_result r = ihost.run_code("{_ibci_str(child)}", {{}})\n'
                "print(r.exit_status)\n"
                "print(r.stdout)\n"
            )
            out = run_ibci(code)
            joined = "\n".join(out)
            assert "ok" in out
            assert "wrote" in joined
        finally:
            # run_ibci root_dir = TESTS_ROOT；子 ./ 相对路径锚定 TESTS_ROOT
            p = os.path.join(TESTS_ROOT, "_run_code_child_out.txt")
            if os.path.exists(p):
                os.unlink(p)

    def test_fs_outside_project_root_rejected(self):
        """沙箱外：字符串源子代码 fs 写父 project_root 外（../）= RUN_PERMISSION_ERROR
        经 exception 值面（错误作值，父存活）。"""
        child = (
            "import fs\n"
            "fs.write('../_run_code_escape.txt', 'escape')\n"
        )
        try:
            code = (
                "import ihost\n"
                f'run_result r = ihost.run_code("{_ibci_str(child)}", {{}})\n'
                "print(r.exit_status)\n"
                "dict ex = r.exception\n"
                'print(ex["code"])\n'
                "print('parent-alive')\n"
            )
            out = run_ibci(code)
            joined = "\n".join(out)
            assert "error" in out
            assert "RUN_PERMISSION_ERROR" in joined
            assert "parent-alive" in out
        finally:
            # ../ 相对 TESTS_ROOT = REPO_ROOT；沙箱外写被拒（不落地），防御性清理
            p = os.path.join(TESTS_ROOT, "..", "_run_code_escape.txt")
            if os.path.exists(p):
                os.unlink(p)

    def test_e1_llm_inheritance(self):
        """E1 继承：父 mock 态 → 字符串源子 LLM 调用（无自身 api_config）经
        继承 mock 供数（同一 spawn 核心 on_ready 钩子，机制同构）。"""
        child = (
            "import ai\n"
            "class Q:\n"
            "    func __llm_call__(self) -> dict:\n"
            '        return {"user_prompt": "MOCK:STR:child-inherits"}\n'
            "Q q = Q()\n"
            "str val = q()\n"
            "print(val)\n"
        )
        code = (
            "import ai\n"
            "import ihost\n"
            "ai.set_mock_mode()\n"
            f'run_result r = ihost.run_code("{_ibci_str(child)}", {{}})\n'
            "print(r.stdout)\n"
        )
        out = run_ibci(code)
        assert any("child-inherits" in line for line in out)
