"""
core/runtime/async — 内部草稿模块，不对外暴露。

llm_tasks.py 是 LLM 异步调度的内部草稿，当前实现为同步调用伪装成 Future 模式，
无真正并发能力，且存在 execution_context=None NPE 问题。

⚠️  此包内的任何符号均不应在用户接口、SDK 文档或 ibci_modules 插件中引用。
   真正的异步 LLM 调度依赖 VM CPS 调度循环（Step 9）和 Layer 1 LLM 流水线（Step 10）。
   详见 docs/PENDING_TASKS_VM.md。
"""

# 不导出任何公共符号，防止外部代码意外依赖本包。
__all__: list = []
