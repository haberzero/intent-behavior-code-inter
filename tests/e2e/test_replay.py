"""
tests/e2e/test_replay.py

CLI 确定性重放黑箱契约（round3 需求 R-1 子系统，批 2；
设计：tasks_docs/_run_observability_design.md §五）：

- 记录 run（mock）→ 同代码 --replay = 同输出（确定性轨迹）；
- 真实 provider 不加载（临时项目无 api_config 亦成功——replay 自足）;
- 耗尽（代码请求 > 记录）= fail-fast（LLMCallError 消息携带 exhausted 语义）;
- 提前结束（代码请求 < 记录）= 合法（剩余行未消费）;
- 损坏 journal = 加载期拒绝（exit 1，不部分消费）;
- 重放 run 仍写新 journal（replay_of 指向源——审计链完整）。
"""
import json
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ENTRY_TWO_CALLS = (
    "import ai\n"
    "ai.set_mock_mode()\n"
    "class Q:\n"
    "    func __llm_call__(self) -> dict:\n"
    '        return {"user_prompt": "MOCK:STR:first"}\n'
    "class R:\n"
    "    func __llm_call__(self) -> dict:\n"
    '        return {"user_prompt": "MOCK:STR:second"}\n'
    "Q q = Q()\n"
    "R r = R()\n"
    "str a = q()\n"
    "str b = r()\n"
    'print(a + "-" + b)\n'
)

ENTRY_ONE_CALL = (
    "import ai\n"
    "ai.set_mock_mode()\n"
    "class Q:\n"
    "    func __llm_call__(self) -> dict:\n"
    '        return {"user_prompt": "MOCK:STR:first"}\n'
    "Q q = Q()\n"
    "str a = q()\n"
    "print(a)\n"
)


def _run_cli(tmp_path, entry, *extra):
    return subprocess.run(
        [sys.executable, os.path.join(REPO_ROOT, "main.py"),
         "run", str(tmp_path / entry), "--root", str(tmp_path), *extra],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )


def _read_journal(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


class TestCliReplay:
    def _record(self, tmp_path, entry_code, entry_name="record.ibci"):
        (tmp_path / entry_name).write_text(entry_code, encoding="utf-8")
        r = _run_cli(tmp_path, entry_name)
        assert r.returncode == 0, (r.stdout, r.stderr)
        journals = sorted((tmp_path / "llm_journal").glob("*.jsonl"))
        assert len(journals) == 1
        return str(journals[0])

    def test_record_then_replay_deterministic(self, tmp_path):
        src = self._record(tmp_path, ENTRY_TWO_CALLS)
        src_recs = _read_journal(src)
        assert sum(1 for x in src_recs if x["type"] == "call") == 2
        (tmp_path / "replay.ibci").write_text(ENTRY_TWO_CALLS, encoding="utf-8")
        r = _run_cli(tmp_path, "replay.ibci", "--replay", src, "--no-journal")
        assert r.returncode == 0, (r.stdout, r.stderr)
        assert "first-second" in r.stdout  # 与记录 run 同输出（确定性轨迹）
        assert "replay:" in r.stderr

    def test_replay_without_api_config(self, tmp_path):
        # 临时项目无 api_config.json——真实 provider 不加载，replay 自足
        src = self._record(tmp_path, ENTRY_ONE_CALL)
        assert not (tmp_path / "api_config.json").exists()
        (tmp_path / "replay.ibci").write_text(ENTRY_ONE_CALL, encoding="utf-8")
        r = _run_cli(tmp_path, "replay.ibci", "--replay", src, "--no-journal")
        assert r.returncode == 0, (r.stdout, r.stderr)
        assert "first" in r.stdout

    def test_replay_exhaustion_fails_fast(self, tmp_path):
        # 记录 1 调用，重放 2 调用代码 → 第 2 次调用耗尽 fail-fast
        src = self._record(tmp_path, ENTRY_ONE_CALL)
        (tmp_path / "two.ibci").write_text(ENTRY_TWO_CALLS, encoding="utf-8")
        r = _run_cli(tmp_path, "two.ibci", "--replay", src, "--no-journal")
        assert r.returncode != 0
        combined = r.stdout + r.stderr
        assert "exhausted" in combined, combined[:400]

    def test_replay_early_end_ok(self, tmp_path):
        # 记录 2 调用，重放 1 调用代码 → 提前结束合法（剩余行未消费）
        src = self._record(tmp_path, ENTRY_TWO_CALLS)
        (tmp_path / "one.ibci").write_text(ENTRY_ONE_CALL, encoding="utf-8")
        r = _run_cli(tmp_path, "one.ibci", "--replay", src, "--no-journal")
        assert r.returncode == 0, (r.stdout, r.stderr)
        assert "first" in r.stdout

    def test_replay_run_writes_journal_with_source(self, tmp_path):
        # 重放 run 仍写新 journal（审计链完整：replay_of 指向源）
        src = self._record(tmp_path, ENTRY_ONE_CALL)
        (tmp_path / "replay.ibci").write_text(ENTRY_ONE_CALL, encoding="utf-8")
        r = _run_cli(tmp_path, "replay.ibci", "--replay", src)
        assert r.returncode == 0, (r.stdout, r.stderr)
        journals = sorted((tmp_path / "llm_journal").glob("*.jsonl"))
        assert len(journals) == 2
        replayed = [
            _read_journal(str(j))[0] for j in journals
            if _read_journal(str(j))[0].get("replay_of")
        ]
        assert len(replayed) == 1
        assert replayed[0]["type"] == "run"
        assert replayed[0]["replay_of"] in (src, os.path.abspath(src)), replayed[0]

    def test_invalid_journal_rejected(self, tmp_path):
        bad = tmp_path / "bad.jsonl"
        bad.write_text("garbage not json\n", encoding="utf-8")
        (tmp_path / "one.ibci").write_text(ENTRY_ONE_CALL, encoding="utf-8")
        r = _run_cli(tmp_path, "one.ibci", "--replay", str(bad))
        assert r.returncode == 1
        # CLI 错误面惯例 = stdout（FileNotFoundError 同形态）
        assert "Error:" in r.stdout
