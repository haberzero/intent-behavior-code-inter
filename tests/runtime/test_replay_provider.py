"""
tests/runtime/test_replay_provider.py

确定性重放白箱契约（tests/runtime 层；CLI 黑箱面见 tests/e2e/test_replay.py）：

- ReplayJournal 加载期校验（fail-fast，不部分消费）：头行/版本/seq 严格递增/
  必填字段/未知 type/JSON 损坏/空文件/缺文件 各拒绝面；
- ReplayLLMProvider：seq 序重放 / error 行同形态 raise / 耗尽 fail-fast
  （消息携带语义）/ 流式诚实拒绝 / 内省面（replayed 标记）/ 消费计数。
"""
import json

import pytest

from core.runtime.replay import ReplayJournal, ReplayLLMProvider, JournalFormatError
from core.base.llm_protocol.llm_call import LLMCallRequest


def _write_journal(path, header=None, calls=None):
    with open(path, "w", encoding="utf-8") as f:
        if header is None:
            header = {"v": 1, "type": "run", "run_id": "t", "entry": "e.ibci",
                      "started_at": "2026-01-01T00:00:00+00:00", "replay_of": None}
        f.write(json.dumps(header) + "\n")
        for c in calls or []:
            f.write(json.dumps(c) + "\n")
    return str(path)


def _call(seq=0, **overrides):
    rec = {
        "v": 1, "type": "call", "seq": seq, "ts": 1.0, "ts_mono": 1.0,
        "node_uid": "n0", "target_model": "m",
        "sys_prompt": "sp", "user_prompt": "up",
        "content": "c", "raw_response": "raw",
        "finish_reason": "stop", "generation": None, "usage": None, "error": None,
    }
    rec.update(overrides)
    return rec


class TestJournalValidation:
    def test_valid_load(self, tmp_path):
        p = _write_journal(tmp_path / "j.jsonl", calls=[_call(0), _call(1)])
        j = ReplayJournal(p)
        assert j.total_calls == 2 and j.run_id == "t"
        assert j.consumed_calls == 0

    def test_missing_file(self, tmp_path):
        with pytest.raises(JournalFormatError, match="not found"):
            ReplayJournal(str(tmp_path / "nope.jsonl"))

    def test_empty_file(self, tmp_path):
        p = tmp_path / "empty.jsonl"
        p.write_text("", encoding="utf-8")
        with pytest.raises(JournalFormatError, match="empty"):
            ReplayJournal(str(p))

    def test_missing_header(self, tmp_path):
        p = _write_journal(tmp_path / "j.jsonl",
                           header={"v": 1, "type": "call", "seq": 0},
                           calls=[_call(0)])
        with pytest.raises(JournalFormatError, match="run header"):
            ReplayJournal(str(p))

    def test_version_mismatch(self, tmp_path):
        p = _write_journal(tmp_path / "j.jsonl",
                           header={"v": 99, "type": "run"}, calls=[])
        with pytest.raises(JournalFormatError, match="unsupported journal schema"):
            ReplayJournal(str(p))

    def test_seq_gap(self, tmp_path):
        p = _write_journal(tmp_path / "j.jsonl", calls=[_call(0), _call(2)])
        with pytest.raises(JournalFormatError, match="seq"):
            ReplayJournal(str(p))

    def test_missing_field(self, tmp_path):
        bad = _call(0)
        del bad["user_prompt"]
        p = _write_journal(tmp_path / "j.jsonl", calls=[bad])
        with pytest.raises(JournalFormatError, match="missing fields"):
            ReplayJournal(str(p))

    def test_unknown_type(self, tmp_path):
        p = _write_journal(tmp_path / "j.jsonl",
                           calls=[_call(0, type="weird")])
        with pytest.raises(JournalFormatError, match="unknown type"):
            ReplayJournal(str(p))

    def test_corrupt_json_line(self, tmp_path):
        p = tmp_path / "j.jsonl"
        p.write_text('{"v": 1, "type": "run"}\n{broken\n', encoding="utf-8")
        with pytest.raises(JournalFormatError, match="not valid JSON"):
            ReplayJournal(str(p))


class TestReplayProvider:
    def _provider(self, tmp_path, calls):
        p = _write_journal(tmp_path / "j.jsonl", calls=calls)
        return ReplayLLMProvider(ReplayJournal(p))

    def test_seq_order_replay(self, tmp_path):
        prov = self._provider(tmp_path, [_call(0, content="a"), _call(1, content="b")])
        req = LLMCallRequest(node_uid="n", target_model="m", user_prompt="up")
        r1 = prov.call(req)
        r2 = prov.call(req)
        assert r1.content == "a" and r2.content == "b"
        assert r1.finish_reason == "stop"
        info = prov.get_current_call_info()
        assert info.get("replayed") is True
        assert info["response"] == "b"

    def test_error_record_replayed(self, tmp_path):
        prov = self._provider(tmp_path, [_call(0, error="MOCK:ERROR injected (500)")])
        req = LLMCallRequest(node_uid="n", target_model="m", user_prompt="up")
        with pytest.raises(RuntimeError, match="500"):
            prov.call(req)

    def test_exhaustion_fails_fast(self, tmp_path):
        prov = self._provider(tmp_path, [_call(0)])
        req = LLMCallRequest(node_uid="n", target_model="m", user_prompt="up")
        prov.call(req)
        with pytest.raises(RuntimeError, match="exhausted at call #2"):
            prov.call(req)

    def test_stream_rejected(self, tmp_path):
        prov = self._provider(tmp_path, [_call(0)])
        with pytest.raises(NotImplementedError, match="replay mode"):
            prov.stream(LLMCallRequest(node_uid="n", target_model="m", user_prompt="up"))

    def test_protocol_surface(self, tmp_path):
        prov = self._provider(tmp_path, [])
        assert prov.get_retry() == 3
        assert prov.is_auto_intent_injection_enabled() is True
        assert prov.get_current_call_info() == {}
