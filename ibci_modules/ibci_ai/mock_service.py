"""``MockServer`` —— OpenAI 兼容的 MOCK HTTP 服务（测试仪器）。

线程内 ``ThreadingHTTPServer``，监听 127.0.0.1 随机端口。协议面与真实
OpenAI Chat Completions 兼容，因此 IBCI 现有 ``OpenAI`` 客户端代码路径
（``AIPlugin._init_client`` + ``chat.completions.create``）可原样打到本服务，
作为 LLM 并行化等机制测试的完整传输彩排。

每个请求由 :class:`MockScenarioEngine` 按 prompt 指令解析：
- 值指令（``STR``/``INT``/``SEQ``/``FAIL``/...）：返回对应内容
- ``MOCK:SLEEP:<ms>``：响应前延迟（并发时序测试）
- ``MOCK:ERROR:<status>``：返回 HTTP 错误状态（基础设施失败注入）
- ``stream=true``：SSE 流式分块响应

统计（``stats``）记录活跃请求数 / 最大并发 / 请求记录，供并发鲁棒性断言。
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional, Type

from ibci_modules.ibci_ai.mock_scenario import MockScenarioEngine, MockScenarioResult

_PATH_CHAT_COMPLETIONS = "/v1/chat/completions"


class MockServerStats:
    """请求统计：活跃数 / 最大并发 / 请求记录。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.total_requests = 0
        self.completed_requests = 0
        self.active = 0
        self.max_concurrent = 0
        self.requests: List[Dict[str, Any]] = []

    def record_start(self, user_prompt: str, stream: bool) -> None:
        with self._lock:
            self.total_requests += 1
            self.active += 1
            self.max_concurrent = max(self.max_concurrent, self.active)
            self.requests.append(
                {
                    "user_prompt": user_prompt,
                    "stream": stream,
                    "start": time.monotonic(),
                    "end": None,
                    "status": None,
                }
            )

    def record_end(self, status: int) -> None:
        with self._lock:
            self.active -= 1
            self.completed_requests += 1
            for req in reversed(self.requests):
                if req["end"] is None:
                    req["end"] = time.monotonic()
                    req["status"] = status
                    break


class MockServer:
    """可编程 MOCK LLM 服务（线程内，127.0.0.1 随机端口）。

    用法::

        server = MockServer()
        server.start()
        ai.set_config(server.url, "sk-test", "mock")
        ...
        server.stop()
    """

    def __init__(self, engine: Optional[MockScenarioEngine] = None) -> None:
        self._engine = engine if engine is not None else MockScenarioEngine()
        self.stats = MockServerStats()
        handler = _make_handler(self._engine, self.stats)
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._port = int(self._httpd.server_address[1])
        self._thread: Optional[threading.Thread] = None

    @property
    def url(self) -> str:
        """服务根地址（不含 /v1 后缀）。"""
        return f"http://127.0.0.1:{self._port}"

    @property
    def engine(self) -> MockScenarioEngine:
        return self._engine

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._thread is None:
            return
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=5)
        self._thread = None

    def __enter__(self) -> "MockServer":
        self.start()
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.stop()


def _make_handler(
    engine: MockScenarioEngine, stats: MockServerStats
) -> Type[BaseHTTPRequestHandler]:
    """构造绑定指定 engine/stats 的请求处理类（每服务实例独立）。"""

    class _MockRequestHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        _engine = engine
        _stats = stats

        def log_message(self, *args: Any) -> None:
            pass

        # ------------------------------------------------------------------
        # 路由
        # ------------------------------------------------------------------

        def do_POST(self) -> None:
            if self.path != _PATH_CHAT_COMPLETIONS:
                self._respond_json({"error": {"message": "not found", "type": "invalid_request_error", "code": 404}}, status=404)
                return
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length).decode("utf-8"))
            except (ValueError, json.JSONDecodeError):
                self._respond_json({"error": {"message": "invalid JSON body", "type": "invalid_request_error", "code": 400}}, status=400)
                return
            self._handle_chat_completion(body)

        def do_GET(self) -> None:
            if self.path == "/health":
                self._respond_json({"status": "ok"}, status=200)
                return
            self._respond_json({"error": {"message": "not found", "type": "invalid_request_error", "code": 404}}, status=404)

        # ------------------------------------------------------------------
        # Chat Completions 处理
        # ------------------------------------------------------------------

        def _handle_chat_completion(self, body: Dict[str, Any]) -> None:
            stream = bool(body.get("stream", False))
            user_prompt = self._extract_user_prompt(body)
            self._stats.record_start(user_prompt, stream)
            status = 200
            try:
                result = self._engine.handle(user_prompt)
                if result.error_status is not None:
                    status = result.error_status
                    self._respond_json(
                        {
                            "error": {
                                "message": f"MOCK:ERROR injected ({result.error_status})",
                                "type": "server_error",
                                "code": result.error_status,
                            }
                        },
                        status=result.error_status,
                    )
                    return
                if result.delay_ms:
                    time.sleep(result.delay_ms / 1000.0)
                model = body.get("model", "mock")
                if stream:
                    self._respond_stream(result.content, model, chunks=result.chunks)
                else:
                    self._respond_json(self._completion_body(result.content, model), status=200)
            finally:
                self._stats.record_end(status)

        @staticmethod
        def _extract_user_prompt(body: Dict[str, Any]) -> str:
            messages = body.get("messages", [])
            # 取首个 user 消息（原始任务）。retry 多轮对话会在其后追加
            # assistant/user 历史；MOCK 指令始终位于首轮 user 任务中，
            # 不应被末轮纠错 user 消息覆盖。
            for message in messages:
                if message.get("role") == "user":
                    content = message.get("content")
                    if isinstance(content, str):
                        return content
                    if isinstance(content, list):
                        parts: List[str] = []
                        for block in content:
                            if isinstance(block, str):
                                parts.append(block)
                            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                                parts.append(block["text"])
                        return "".join(parts)
            return ""

        @staticmethod
        def _completion_body(content: str, model: str) -> Dict[str, Any]:
            return {
                "id": f"chatcmpl-mock",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }

        @staticmethod
        def _chunk_body(content: Optional[str], model: str, finish: Optional[str]) -> Dict[str, Any]:
            delta: Dict[str, Any] = {}
            if content is not None:
                delta["content"] = content
            return {
                "id": "chatcmpl-mock",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
            }

        # ------------------------------------------------------------------
        # 响应写出
        # ------------------------------------------------------------------

        def _respond_json(self, payload: Dict[str, Any], status: int) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(data)

        def _respond_stream(self, content: str, model: str, chunks: Optional[List[str]] = None) -> None:
            """SSE 流式响应。

            有 ``chunks`` 时逐块流式发送（模拟真实流式），块间微小延迟；
            否则单块发送完整内容。
            """
            payload_parts = []
            if chunks:
                for chunk in chunks:
                    payload_parts.append(
                        f"data: {json.dumps(self._chunk_body(chunk, model, None), ensure_ascii=False)}\n\n"
                    )
            else:
                payload_parts.append(
                    f"data: {json.dumps(self._chunk_body('', model, None), ensure_ascii=False)}\n\n"
                )
                payload_parts.append(
                    f"data: {json.dumps(self._chunk_body(content, model, None), ensure_ascii=False)}\n\n"
                )
            payload_parts.append(
                f"data: {json.dumps(self._chunk_body(None, model, 'stop'), ensure_ascii=False)}\n\n"
            )
            payload_parts.append("data: [DONE]\n\n")
            payload = "".join(payload_parts).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(payload)

    return _MockRequestHandler
