"""
tests/e2e/test_budget_cli.py

CLI LLM 预算黑箱契约（round3 需求 R-3；设计 §四）：

- api_config.json budget 节驱动：fail 模式超限 = 运行期 RUN_BUDGET_EXCEEDED
  （provider 调用前拦截，零浪费）；warn 模式 = stderr 告警不阻断；
- 无 budget 节 = 行为不变（零侵入对照）；
- budget 节形态错误 = CLI 启动期 [CFG_CONFIG_INVALID_BUDGET] 拒绝（exit 1）。

mock 模式（ai.set_mock_mode）不经 provider 配置面——临时项目仅需 api_config.json
的 budget 节（真实 provider 配置不被加载）。
"""
import json
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ENTRY_THREE_CALLS = (
    "import ai\n"
    "ai.set_mock_mode()\n"
    "class Q:\n"
    "    func __llm_call__(self) -> dict:\n"
    '        return {"user_prompt": "MOCK:STR:x"}\n'
    "Q q = Q()\n"
    "print(q())\n"
    "print(q())\n"
    "print(q())\n"
)


def _run_cli(tmp_path, budget=None, budget_key="api_config.json"):
    if budget is not None:
        (tmp_path / budget_key).write_text(
            json.dumps(budget), encoding="utf-8"
        )
    return subprocess.run(
        [sys.executable, os.path.join(REPO_ROOT, "main.py"),
         "run", str(tmp_path / "entry.ibci"), "--root", str(tmp_path),
         "--no-journal"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )


def _x_lines(stdout):
    return len([l for l in stdout.splitlines() if l.strip() == "x"])


class TestCliBudget:
    def _write_entry(self, tmp_path):
        (tmp_path / "entry.ibci").write_text(ENTRY_THREE_CALLS, encoding="utf-8")

    def test_no_budget_zero_intrusion(self, tmp_path):
        self._write_entry(tmp_path)
        r = _run_cli(tmp_path)  # 无 api_config.json
        assert r.returncode == 0, (r.stdout, r.stderr)
        assert _x_lines(r.stdout) == 3

    def test_fail_mode_intercepts(self, tmp_path):
        self._write_entry(tmp_path)
        r = _run_cli(tmp_path, budget={"budget": {"max_calls": 2, "on_exceed": "fail"}})
        assert r.returncode != 0
        combined = r.stdout + r.stderr
        assert "RUN_BUDGET_EXCEEDED" in combined, combined[:400]
        # 拦截前完成 2 次（零浪费：第 3 次未发出）
        assert _x_lines(r.stdout) == 2

    def test_warn_mode_continues(self, tmp_path):
        self._write_entry(tmp_path)
        r = _run_cli(tmp_path, budget={"budget": {"max_calls": 2, "on_exceed": "warn"}})
        assert r.returncode == 0, (r.stdout, r.stderr)
        assert _x_lines(r.stdout) == 3           # run 完整
        assert "budget exceeded" in r.stderr     # 告警显形

    def test_invalid_budget_rejected(self, tmp_path):
        self._write_entry(tmp_path)
        r = _run_cli(tmp_path, budget={"budget": {"max_calls": -1}})
        assert r.returncode == 1
        assert "CFG_CONFIG_INVALID_BUDGET" in r.stdout
