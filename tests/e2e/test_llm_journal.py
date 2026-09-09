"""
tests/e2e/test_llm_journal.py

LLM journal（append-only run 级审计）契约——R3-⑤ 批 1
（journal append-only 可观测子系统 e2e 面）：

- schema v1：首行 type=run 元数据 + 每调用一行 type=call（seq 单调）；
- 汇点覆盖：成功面（prompts/content/raw/finish_reason/generation/usage）与
  失败面（MOCK:ERROR → error 字段非空）均记录；
- 未挂载（无 journal_writer）行为与现状完全一致（零侵入）；
- CLI 面：默认开（llm_journal/<run-id>.jsonl + stderr 提示行）/ --no-journal
  关闭（无目录无提示）。
- 白箱面（写失败降级/并发 seq/run-id 形态）见 tests/runtime/test_llm_journal.py
  （e2e 黑箱红线不覆盖私有面）。
"""
import json
import os
import subprocess
import sys

from tests.conftest import _default_root, AI_MOCK_PREFIX

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def read_journal(path):
    with open(path, encoding="utf-8") as f:
        lines = [json.loads(l) for l in f if l.strip()]
    return lines


def _run_with_journal(code, tmp_path, ai=True):
    from core.engine import IBCIEngine
    from core.runtime.observability.llm_journal import LLMJournalWriter
    jpath = str(tmp_path / "j" / "run.jsonl")
    writer = LLMJournalWriter(jpath, entry="test.ibci")
    engine = IBCIEngine(root_dir=_default_root())
    lines = []
    full = (AI_MOCK_PREFIX if ai else "") + code
    engine.run_string(full, output_callback=lambda t: lines.append(str(t)),
                      silent=True, journal_writer=writer)
    writer.close()
    return lines, jpath


class TestJournalSchema:
    def test_header_and_call_recorded(self, tmp_path):
        code = (
            "class Q:\n"
            "    func __llm_call__(self) -> dict:\n"
            '        return {"user_prompt": "MOCK:STR:answer1"}\n'
            "Q q = Q()\n"
            "str v = q()\n"
            "print(v)\n"
        )
        lines, jpath = _run_with_journal(code, tmp_path)
        assert lines == ["answer1"]
        recs = read_journal(jpath)
        header, call = recs[0], recs[1]
        # 首行 = run 元数据
        assert header["v"] == 1 and header["type"] == "run"
        assert header["run_id"] == os.path.basename(jpath)
        assert header["entry"] == "test.ibci"
        assert header["replay_of"] is None
        assert "started_at" in header
        # 调用行 = 全字段
        assert call["type"] == "call" and call["seq"] == 0
        assert "node_uid" in call  # 行为表达式节点有值；llm 可调用类调用可为 None
        assert "target_model" in call  # mock 模式为空串；真实模式 = 模型 ID
        assert "user_prompt" in call and "MOCK:STR:answer1" in call["user_prompt"]
        assert "sys_prompt" in call
        assert call["content"] == "answer1"
        assert call["raw_response"]
        assert call["error"] is None
        assert "ts" in call and "ts_mono" in call
        assert len(recs) == 2

    def test_seq_monotonic(self, tmp_path):
        code = (
            "class Q:\n"
            "    func __llm_call__(self) -> dict:\n"
            '        return {"user_prompt": "MOCK:STR:a1"}\n'
            "Q q = Q()\n"
            "Q r = Q()\n"
            "str v = q()\n"
            "str w = r()\n"
            "print(v + w)\n"
        )
        lines, jpath = _run_with_journal(code, tmp_path)
        assert lines == ["a1a1"]
        calls = [r for r in read_journal(jpath) if r["type"] == "call"]
        assert [c["seq"] for c in calls] == [0, 1]

    def test_error_path_recorded(self, tmp_path):
        # MOCK:ERROR:<status> = provider 传输失败 → _call_llm 异常面
        #（LLMCallError 直接上抛，llmexcept 重试对其无效）→ journal error
        # 字段非空（审计完整性：重放时同形态 raise）
        code = (
            "class Q:\n"
            "    func __llm_call__(self) -> dict:\n"
            '        return {"user_prompt": "MOCK:ERROR:500"}\n'
            "Q q = Q()\n"
            "try:\n"
            "    str v = q()\n"
            "except Exception as e:\n"
            "    print(\"caught\")\n"
        )
        lines, jpath = _run_with_journal(code, tmp_path)
        assert "caught" in lines
        calls = [r for r in read_journal(jpath) if r["type"] == "call"]
        assert calls, "error 路径调用应被记录"
        assert calls[0]["error"], f"error 字段应非空: {calls[0]}"
        assert calls[0]["content"] == ""

    def test_no_writer_behavior_unchanged(self, tmp_path):
        """未挂载 journal = 行为与现状完全一致（零侵入）。"""
        from core.engine import IBCIEngine
        code = (
            "class Q:\n"
            "    func __llm_call__(self) -> dict:\n"
            '        return {"user_prompt": "MOCK:STR:ok"}\n'
            "Q q = Q()\n"
            "str v = q()\n"
            "print(v)\n"
        )
        engine = IBCIEngine(root_dir=_default_root())
        lines = []
        engine.run_string(AI_MOCK_PREFIX + code,
                          output_callback=lambda t: lines.append(str(t)),
                          silent=True)
        assert lines == ["ok"]


class TestCliJournal:
    def _write_entry(self, tmp_path):
        p = tmp_path / "entry.ibci"
        p.write_text(
            "import ai\n"
            "ai.set_mock_mode()\n"
            "class Q:\n"
            "    func __llm_call__(self) -> dict:\n"
            '        return {"user_prompt": "MOCK:STR:cli-answer"}\n'
            "Q q = Q()\n"
            "str v = q()\n"
            "print(v)\n",
            encoding="utf-8",
        )
        return p

    def _run_cli(self, tmp_path, *extra):
        return subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "main.py"),
             "run", str(tmp_path / "entry.ibci"), "--root", str(tmp_path), *extra],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )

    def test_default_journal_on(self, tmp_path):
        self._write_entry(tmp_path)
        r = self._run_cli(tmp_path)
        assert r.returncode == 0, r.stderr
        assert "cli-answer" in r.stdout
        # stderr 提示行（不入 stdout 数据面）
        assert "journal: llm_journal/" in r.stderr
        # 文件生成 + schema
        jdir = tmp_path / "llm_journal"
        files = list(jdir.glob("*.jsonl"))
        assert len(files) == 1
        recs = read_journal(str(files[0]))
        assert recs[0]["type"] == "run"
        assert any(rec["type"] == "call" and rec["content"] == "cli-answer"
                   for rec in recs)

    def test_no_journal_flag(self, tmp_path):
        self._write_entry(tmp_path)
        r = self._run_cli(tmp_path, "--no-journal")
        assert r.returncode == 0, r.stderr
        assert "cli-answer" in r.stdout
        assert "journal: llm_journal/" not in r.stderr
        assert not (tmp_path / "llm_journal").exists()
