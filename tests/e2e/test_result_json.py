"""
tests/e2e/test_result_json.py

CLI result trailer（--result-json）黑箱契约（round3 需求 R-4；
--result-json trailer 结果捕获 e2e 面）：

- stdout 末行 = 单行 JSON（v1 契约：exit_status / exception{code,message,
  source} / journal / budget / replay）；数据面（print 输出）= 末行之前，
  验收机 `tail -n1` 即得结果；
- 三 exit 面：ok / 运行期 error（码复用异常对象，无新渲染）/ 编译期 error
  （首个诊断 = 根因面）；
- journal/budget/replay 面联动（无对应面 = null）；
- 非 --result-json 默认行为不变（无 trailer 行——零侵入）。
"""
import json
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ENTRY_OK = (
    "import ai\n"
    "ai.set_mock_mode()\n"
    "class Q:\n"
    "    func __llm_call__(self) -> dict:\n"
    '        return {"user_prompt": "MOCK:STR:ok"}\n'
    "Q q = Q()\n"
    "str v = q()\n"
    'print(v)\n'
)

ENTRY_RUNTIME_ERR = (
    "int a = 1\n"
    "int b = 0\n"
    "int c = a / b\n"
    "print(c)\n"
)

ENTRY_COMPILE_ERR = (
    "print(undefined_var)\n"
)


def _run_cli(tmp_path, entry, *extra):
    (tmp_path / "entry.ibci").write_text(entry, encoding="utf-8")
    return subprocess.run(
        [sys.executable, os.path.join(REPO_ROOT, "main.py"),
         "run", str(tmp_path / "entry.ibci"), "--root", str(tmp_path), *extra],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )


def _trailer(r):
    """末行解析（验收机同形态：tail -n1）。"""
    lines = [l for l in r.stdout.splitlines() if l.strip()]
    return json.loads(lines[-1])


class TestResultJson:
    def test_ok_run_trailer(self, tmp_path):
        r = _run_cli(tmp_path, ENTRY_OK, "--result-json")
        assert r.returncode == 0, (r.stdout, r.stderr)
        trailer = _trailer(r)
        assert trailer["v"] == 1
        assert trailer["exit_status"] == "ok"
        assert trailer["exception"] is None
        assert trailer["journal"].startswith("llm_journal/") and trailer["journal"].endswith(".jsonl")
        assert trailer["budget"] is None
        assert trailer["replay"] is None
        # 数据面不受影响：trailer 之前的行含 print 输出；trailer = 末行
        assert "ok" in r.stdout
        assert json.loads(r.stdout.splitlines()[-1]) == trailer

    def test_no_flag_zero_intrusion(self, tmp_path):
        # 默认无 trailer（行为不变）
        r = _run_cli(tmp_path, ENTRY_OK, "--no-journal")
        assert r.returncode == 0
        lines = [l for l in r.stdout.splitlines() if l.strip()]
        assert all(not l.strip().startswith('{"v":') for l in lines)

    def test_runtime_error_trailer(self, tmp_path):
        r = _run_cli(tmp_path, ENTRY_RUNTIME_ERR, "--result-json", "--no-journal")
        assert r.returncode != 0
        trailer = _trailer(r)
        assert trailer["exit_status"] == "error"
        exc = trailer["exception"]
        assert exc["code"] == "RUN_DIVISION_BY_ZERO"
        assert exc["message"]
        # trailer = 末行（错误渲染文本在其前）
        assert json.loads(r.stdout.splitlines()[-1]) == trailer

    def test_compile_error_trailer(self, tmp_path):
        r = _run_cli(tmp_path, ENTRY_COMPILE_ERR, "--result-json", "--no-journal")
        assert r.returncode != 0
        trailer = _trailer(r)
        assert trailer["exit_status"] == "error"
        exc = trailer["exception"]
        assert exc["code"], f"编译错误应携带诊断码: {exc}"
        assert "SEM_" in exc["code"] or "PAR_" in exc["code"] or "LEX_" in exc["code"]
        assert exc["source"] is not None
        assert exc["source"]["line"] is not None
        assert "entry.ibci" in (exc["source"].get("file") or "")

    def test_budget_field_linked(self, tmp_path):
        (tmp_path / "api_config.json").write_text(
            json.dumps({"budget": {"max_calls": 100}}), encoding="utf-8"
        )
        r = _run_cli(tmp_path, ENTRY_OK, "--result-json", "--no-journal")
        assert r.returncode == 0
        trailer = _trailer(r)
        assert trailer["budget"] is not None
        assert trailer["budget"]["calls"] == 1

    def test_replay_field_linked(self, tmp_path):
        # 先记录一个 run 的 journal，再以 --replay 跑 → replay 面联动
        (tmp_path / "record.ibci").write_text(ENTRY_OK, encoding="utf-8")
        r1 = subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "main.py"),
             "run", str(tmp_path / "record.ibci"), "--root", str(tmp_path)],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert r1.returncode == 0, (r1.stdout, r1.stderr)
        journals = list((tmp_path / "llm_journal").glob("*.jsonl"))
        assert len(journals) == 1
        src = str(journals[0])
        (tmp_path / "replay.ibci").write_text(ENTRY_OK, encoding="utf-8")
        r2 = subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "main.py"),
             "run", str(tmp_path / "replay.ibci"), "--root", str(tmp_path),
             "--replay", src, "--result-json"],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert r2.returncode == 0, (r2.stdout, r2.stderr)
        trailer = _trailer(r2)
        assert trailer["replay"]["total"] == 1
        assert trailer["replay"]["consumed"] == 1
        assert "ok" in r2.stdout  # 数据面 = 重放输出
