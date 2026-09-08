"""
core.runtime.replay.journal_reader — 重放 journal 读取与加载期校验。

校验在加载期 fail-fast（损坏/不合法 = 整体拒绝，不部分消费）：
- 首行 = type=run 元数据（v 与 writer schema 版本兼容）；
- 其后每行 = type=call（seq 严格递增、必填字段存在）；
- 其余形态行（未知 type / 缺字段 / JSON 损坏）= 拒绝。
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List


class JournalFormatError(Exception):
    """重放 journal 格式不合法（加载期 fail-fast；不部分消费）。"""


# call 行必填字段（缺失 = 记录不完整，重放确定性不成立）
_REQUIRED_CALL_FIELDS = (
    "seq", "node_uid", "target_model", "user_prompt",
    "content", "raw_response", "error",
)


class ReplayJournal:
    """已加载并重放就绪的 journal（call 记录按 seq 序）。"""

    SUPPORTED_V = 1

    def __init__(self, path: str):
        if not os.path.isfile(path):
            raise JournalFormatError(f"replay journal not found: {path}")
        try:
            with open(path, encoding="utf-8") as f:
                raw_lines = [l for l in f if l.strip()]
        except (OSError, UnicodeDecodeError) as e:
            raise JournalFormatError(f"replay journal unreadable: {path} ({e})") from e

        if not raw_lines:
            raise JournalFormatError(f"replay journal is empty: {path}")

        records: List[Dict[str, Any]] = []
        for i, line in enumerate(raw_lines, start=1):
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as e:
                raise JournalFormatError(
                    f"replay journal line {i} is not valid JSON: {path} ({e})"
                ) from e
            if not isinstance(rec, dict):
                raise JournalFormatError(f"replay journal line {i} is not an object: {path}")
            records.append(rec)

        header = records[0]
        if header.get("type") != "run":
            raise JournalFormatError(
                f"replay journal line 1 must be the run header (type=run): {path}"
            )
        if header.get("v") != self.SUPPORTED_V:
            raise JournalFormatError(
                f"unsupported journal schema v={header.get('v')} "
                f"(supported: {self.SUPPORTED_V}): {path}"
            )

        self._calls: List[Dict[str, Any]] = []
        expected_seq = 0
        for i, rec in enumerate(records[1:], start=2):
            if rec.get("type") != "call":
                raise JournalFormatError(
                    f"replay journal line {i} has unknown type={rec.get('type')!r}: {path}"
                )
            if rec.get("v") != self.SUPPORTED_V:
                raise JournalFormatError(
                    f"replay journal line {i} has unsupported v={rec.get('v')}: {path}"
                )
            missing = [k for k in _REQUIRED_CALL_FIELDS if k not in rec]
            if missing:
                raise JournalFormatError(
                    f"replay journal line {i} missing fields {missing}: {path}"
                )
            if rec["seq"] != expected_seq:
                raise JournalFormatError(
                    f"replay journal line {i} seq={rec['seq']} but expected {expected_seq} "
                    f"(seq must be strictly increasing from 0): {path}"
                )
            expected_seq += 1
            self._calls.append(rec)

        self.source_path = path
        self.run_id = header.get("run_id")
        self.entry = header.get("entry")
        self._consumed = 0

    @property
    def total_calls(self) -> int:
        return len(self._calls)

    @property
    def consumed_calls(self) -> int:
        """已消费的 call 数（result-json replay 面用；批 4）。"""
        return self._consumed

    def next_call(self) -> Dict[str, Any]:
        """取下一条记录（耗尽 = 由 provider 侧判定的 fail-fast 语义）。"""
        rec = self._calls[self._consumed]
        self._consumed += 1
        return rec
