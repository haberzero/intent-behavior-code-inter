"""
tests/runtime/test_llm_journal.py

LLM journal writer 白箱契约（tests/runtime 层——e2e 黑箱红线不覆盖私有面，
白箱断言归本层；schema/CLI 黑箱面见 tests/e2e/test_llm_journal.py）：

- 写入失败 = 观测侧信道降级（不阻断调用方；告警显形不静默，write_failed 标记）；
- 线程安全：并发 record_call 的 seq 分配无重复无丢失（锁保护）；
- run-id 形态（UTC 时间戳 + 4 hex）。
"""
import json
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor

from core.runtime.observability.llm_journal import LLMJournalWriter, make_run_id


def _read_records(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


class TestJournalWriteFailure:
    def test_write_failure_degrades_not_blocks(self, tmp_path):
        """写失败后 record_call 静默降级（不抛、不阻断）+ write_failed 标记。"""
        jpath = str(tmp_path / "run.jsonl")
        writer = LLMJournalWriter(jpath, entry="t.ibci")
        writer._fh.close()  # 模拟文件句柄失效（白箱面）
        # 不应抛异常
        writer.record_call(node_uid=None, target_model="m",
                           sys_prompt="", user_prompt="p")
        assert writer.write_failed
        writer.close()
        # 幂等 close
        writer.close()

    def test_closed_writer_ignores_records(self, tmp_path):
        jpath = str(tmp_path / "run.jsonl")
        writer = LLMJournalWriter(jpath, entry="t.ibci")
        writer.close()
        writer.record_call(node_uid=None, target_model="m",
                           sys_prompt="", user_prompt="p")
        recs = _read_records(jpath)
        assert len(recs) == 1 and recs[0]["type"] == "run"  # 仅首行


class TestJournalConcurrentSeq:
    def test_concurrent_record_seq_unique(self, tmp_path):
        """并行 dispatch 场景：并发 record_call 的 seq 单调唯一（锁保护）。"""
        jpath = str(tmp_path / "run.jsonl")
        writer = LLMJournalWriter(jpath, entry="t.ibci")
        n = 64

        def _record(i):
            writer.record_call(node_uid=f"n{i}", target_model="m",
                               sys_prompt="", user_prompt=f"p{i}")

        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(_record, range(n)))
        writer.close()
        calls = [r for r in _read_records(jpath) if r["type"] == "call"]
        assert len(calls) == n
        assert sorted(c["seq"] for c in calls) == list(range(n))


class TestRunId:
    def test_run_id_format(self):
        rid = make_run_id()
        assert re.fullmatch(r"\d{8}T\d{6}Z-[0-9a-f]{4}", rid), rid
