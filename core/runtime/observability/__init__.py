"""
core.runtime.observability — 内省层。

快照式（``runtime.snapshot()``）与事件流（``runtime.subscribe()``）两者都提供。
快照聚合各可观测源的 ``snapshot()``；事件流经 ``EventSource``
协议把状态变更推入订阅者的 Channel。

定位：对标 Python ``sys.settrace``/``inspect``、``asyncio.all_tasks()``、
OpenTelemetry spans——通用、可复用、不过时，非 LLM 专有伪设计（设计 §四.3）。
"""
