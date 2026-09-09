"""
core.runtime.observability.llm_journal — LLM 调用 journal（append-only JSONL）。

run 级 LLM 调用审计基底（round3 需求 R-1/R-3/R-4 子系统，设计见
run 级 journal append-only 可观测子系统）：

- 一 run 一文件（``<root_dir>/llm_journal/<run-id>.jsonl``）；首行 = run 元数据
  （type=run），其后每行一次 LLM 调用（type=call，seq 单调递增）；
- append + flush 每行：写入后立即可读，崩溃不丢已 flush 行（append-only 语义）；
- 写入失败不阻断 run（观测侧信道，尽力而为定位与事件总线一致；失败显形 =
  kernel_diagnostic 事件 + stderr 告警，不静默也不崩溃）；
- 线程安全：并行 dispatch（worker 线程经同一汇点记录）由锁保护 seq 分配与
  文件写入；
- schema 版本化（v 字段）：重放读取方按 v 校验（v 不兼容 = fail-fast，不部分
  消费）。
"""

from __future__ import annotations

import json
import os
import secrets
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def make_run_id() -> str:
    """生成 run-id（UTC 时间戳 + 4 hex 随机，如 ``20260908T120000Z-a1b2``）。"""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{secrets.token_hex(2)}"


class LLMJournalWriter:
    """append-only LLM 调用 journal 写入器（run 级单实例）。

    由 CLI（``main.py run``）创建并经引擎挂接到 LLM 调用汇点
    （``LLMExecutorCore._call_llm``）；Python API 显式传入方（测试）同路径。
    """

    SCHEMA_V = 1

    def __init__(self, path: str, entry: str, replay_of: Optional[str] = None):
        """打开 journal 文件并写入 run 元数据首行（创建失败 = fail-fast 上抛）。"""
        self._path = path
        self._lock = threading.Lock()
        self._seq = 0
        self._write_failed = False
        self._closed = False
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self._fh = open(path, "a", encoding="utf-8")
        self._append({
            "v": self.SCHEMA_V,
            "type": "run",
            "run_id": os.path.basename(path),
            "entry": entry,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "replay_of": replay_of,
        })

    @property
    def path(self) -> str:
        return self._path

    @property
    def write_failed(self) -> bool:
        """是否发生过写入失败（失败不阻断 run；收尾时由调用方决定告警面）。"""
        return self._write_failed

    def record_call(
        self,
        *,
        node_uid: Optional[str],
        target_model: str,
        sys_prompt: str,
        user_prompt: str,
        content: str = "",
        raw_response: str = "",
        finish_reason: Optional[str] = None,
        generation: Optional[Dict[str, Any]] = None,
        usage: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """记录一次 LLM 调用（成功/失败两面；失败面 content 等为空、error 非空）。"""
        with self._lock:
            if self._closed:
                return
            seq = self._seq
            self._seq += 1
        self._append({
            "v": self.SCHEMA_V,
            "type": "call",
            "seq": seq,
            "ts": time.time(),
            "ts_mono": time.monotonic(),
            "node_uid": node_uid,
            "target_model": target_model,
            "sys_prompt": sys_prompt,
            "user_prompt": user_prompt,
            "content": content,
            "raw_response": raw_response,
            "finish_reason": finish_reason,
            "generation": generation,
            "usage": usage,
            "error": error,
        })

    def close(self) -> None:
        """关闭文件（收尾幂等）。"""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            try:
                self._fh.close()
            except OSError:
                pass

    # ------------------------------------------------------------------ #

    def _append(self, record: Dict[str, Any]) -> None:
        line = json.dumps(record, ensure_ascii=False) + "\n"
        try:
            self._fh.write(line)
            self._fh.flush()
        except (OSError, ValueError):
            # 观测侧信道：写失败不阻断 run（stderr 告警显形，与事件总线尽力
            # 而为同定位）；标记 write_failed 供收尾面报告。
            if not self._write_failed:
                self._write_failed = True
                print(
                    f"warning: LLM journal write failed ({self._path}); "
                    "audit recording degraded (run continues)",
                    file=sys.stderr,
                )
