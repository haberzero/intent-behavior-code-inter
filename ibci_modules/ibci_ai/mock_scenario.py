"""``MockScenarioEngine`` —— MOCK 指令语言的单点实现。

从 :class:`AIPlugin` 内联 mock 路径提取的指令解析器，传输无关
（内联 provider 与 HTTP mock 服务共用）。线程安全：seq/retry 计数状态
以 ``RLock`` 保护，并发 dispatch 下序列确定性有保证。

指令语义与既有 ``AIPlugin._handle_mock_response`` 完全一致（值指令 /
seq / repair / 分支场景），并扩展控制指令 ``SLEEP:<ms>`` / ``ERROR:<status>``
供服务传输层承载延迟与基础设施失败注入。
"""

from __future__ import annotations

import re
import threading
import warnings
from dataclasses import dataclass
from typing import Dict, Optional

from core.base.llm_protocol.llm_call import (
    MOCK_REPAIR_SENTINEL,
    MOCK_AMBIGUOUS_SENTINEL,
)

_SLEEP_RE = re.compile(r"MOCK:SLEEP:(\d+)")
_ERROR_RE = re.compile(r"MOCK:ERROR:(\d{3})")
_STREAM_RE = re.compile(r"MOCK:STREAM:(.+)")


@dataclass
class MockScenarioResult:
    """指令解析结果：内容 + 传输层控制参数。"""

    content: str
    delay_ms: int = 0
    error_status: Optional[int] = None
    chunks: Optional[List[str]] = None  # MOCK:STREAM:a|b|c 分块（流式）


class MockScenarioEngine:
    """MOCK 指令语言解析器（线程安全）。

    状态：
    - ``_seq_counters``：``MOCK:SEQ`` 的 per-key 调用序号
    - ``_retry_counts``：``MOCK:REPAIR`` / ``MOCK:REPAIR:<fallback>`` 的轮次
    """

    def __init__(self) -> None:
        self._seq_counters: Dict[str, int] = {}
        self._retry_counts: Dict[str, int] = {}
        self._lock = threading.RLock()

    def reset(self) -> None:
        """清空全部有状态指令计数（测试隔离）。"""
        with self._lock:
            self._seq_counters.clear()
            self._retry_counts.clear()

    # ------------------------------------------------------------------
    # 公共入口
    # ------------------------------------------------------------------

    def handle(self, prompt: str) -> MockScenarioResult:
        """解析一条 LLM user prompt，返回内容与传输控制。

        内容解析（含 seq/retry 状态变更）在锁内完成；控制指令
        （``SLEEP`` / ``ERROR``）为纯扫描，在锁外完成。
        """
        content = self._resolve(prompt)
        delay_ms = 0
        error_status: Optional[int] = None
        chunks: Optional[List[str]] = None
        if _SLEEP_RE.search(prompt):
            delay_ms = int(_SLEEP_RE.search(prompt).group(1))
        error_m = _ERROR_RE.search(prompt)
        if error_m:
            error_status = int(error_m.group(1))
        stream_m = _STREAM_RE.search(prompt)
        if stream_m:
            raw = stream_m.group(1)
            # 以 | 分隔多个块；空块剔除
            chunks = [c for c in raw.split("|") if c]
            if chunks:
                content = "".join(chunks)
        return MockScenarioResult(
            content=content,
            delay_ms=delay_ms,
            error_status=error_status,
            chunks=chunks,
        )

    # ------------------------------------------------------------------
    # 内容解析（指令语言本体，与既有语义一致）
    # ------------------------------------------------------------------

    def _resolve(self, prompt: str) -> str:
        with self._lock:
            return self._resolve_locked(prompt)

    def _resolve_locked(self, prompt: str) -> str:
        if not prompt.startswith("MOCK:"):
            # Validation: warn if a MOCK directive appears somewhere in the
            # prompt but is not the sole content.
            if "MOCK:" in prompt:
                warnings.warn(
                    "A MOCK: directive was found in the LLM prompt but is not at the start. "
                    "A MOCK directive must be the sole content of the prompt "
                    "(a single 'MOCK:<directive>' line with no other text). "
                    "The directive will be ignored and a generic mock response will be used instead.",
                    UserWarning,
                    stacklevel=4,
                )
            return f"[MOCK] {prompt}"

        content_after_mock = prompt[5:].strip()
        first_line_after_mock = content_after_mock.split("\n", 1)[0].strip()

        # 1. 二级类型指令 (MOCK:INT:xxx, MOCK:STR:xxx, etc.)
        if ":" in first_line_after_mock:
            type_parts = first_line_after_mock.split(":", 2)
            if len(type_parts) >= 2:
                mock_type = type_parts[0]
                mock_value = (
                    type_parts[1] if len(type_parts) == 2 else ":".join(type_parts[1:])
                )

                if mock_type == "INT":
                    int_val = mock_value.split()[0] if mock_value.split() else mock_value
                    return str(int(int_val))
                if mock_type == "STR":
                    if len(mock_value) >= 2 and (
                        (mock_value[0] == '"' and '"' in mock_value[1:])
                        or (mock_value[0] == "'" and "'" in mock_value[1:])
                    ):
                        q = mock_value[0]
                        close = mock_value.index(q, 1)
                        return mock_value[1:close]
                    str_val = mock_value.split()[0] if mock_value.split() else mock_value
                    return str_val
                if mock_type == "FLOAT":
                    float_val = mock_value.split()[0] if mock_value.split() else mock_value
                    return str(float(float_val))
                if mock_type == "BOOL":
                    bool_val = mock_value.split()[0] if mock_value.split() else mock_value
                    return "1" if bool_val == "TRUE" else "0"
                if mock_type == "LIST":
                    if mock_value.startswith("["):
                        close = mock_value.find("]")
                        if close != -1:
                            return mock_value[: close + 1]
                    return f"[{mock_value.split()[0] if mock_value.split() else mock_value}]"
                if mock_type == "DICT":
                    if mock_value.startswith("{"):
                        close = mock_value.find("}")
                        if close != -1:
                            return mock_value[: close + 1]
                    return "{" + (mock_value.split()[0] if mock_value.split() else mock_value) + "}"
                if mock_type == "REPAIR":
                    repair_fallback = mock_value
                    retry_key = f"_repair_ext_{repair_fallback}"
                    count = self._retry_counts.get(retry_key, 0)
                    if count == 0:
                        self._retry_counts[retry_key] = 1
                        return MOCK_REPAIR_SENTINEL
                    self._retry_counts[retry_key] = 0
                    if repair_fallback:
                        return self._resolve_locked(f"MOCK:{repair_fallback}")
                    return "1"
                if mock_type == "SEQ":
                    mv = mock_value.strip()
                    if mv.startswith("[") and "]" in mv:
                        bracket_end = mv.index("]")
                        seq_values_str = mv[1:bracket_end]
                        remainder = mv[bracket_end + 1 :].strip()
                        seq_key = remainder if remainder else ""
                    else:
                        warnings.warn(
                            "MOCK:SEQ requires bracket format: MOCK:SEQ:[v1,v2,...] optional_key. "
                            "Bare comma-separated values are no longer supported and will be ignored. "
                            f"Got: MOCK:SEQ:{mv!r}",
                            UserWarning,
                            stacklevel=2,
                        )
                        return ""
                    values = [v.strip() for v in seq_values_str.split(",") if v.strip()]
                    counter_key = f"_seq_{seq_key}"
                    idx = self._seq_counters.get(counter_key, 0)
                    self._seq_counters[counter_key] = idx + 1
                    val = values[idx] if idx < len(values) else (values[-1] if values else "")
                    if val == "FAIL":
                        return MOCK_AMBIGUOUS_SENTINEL
                    if val == "TRUE":
                        return "1"
                    if val == "FALSE":
                        return "0"
                    return val

        # 2. 命名指令（区分大小写，必须全大写）
        parts = first_line_after_mock.split(" ", 1)
        mock_cmd = parts[0] if parts else ""
        mock_content = parts[1] if len(parts) > 1 else ""

        if mock_cmd == "FAIL":
            return MOCK_AMBIGUOUS_SENTINEL
        if mock_cmd == "TRUE":
            return "1"
        if mock_cmd == "FALSE":
            return "0"
        if mock_cmd == "REPAIR":
            retry_key = f"_repair_{mock_content}"
            count = self._retry_counts.get(retry_key, 0)
            if count == 0:
                self._retry_counts[retry_key] = 1
                return MOCK_REPAIR_SENTINEL
            self._retry_counts[retry_key] = 0
            return "1"

        return f"[MOCK] {prompt}"
