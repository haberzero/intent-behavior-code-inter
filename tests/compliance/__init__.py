"""
tests/compliance/
=================

IBCI VM 合规测试套件（M6）。

本目录包含跨实现（Compliance Test Suite）验证测试，覆盖 IBCI VM 规范
（docs/VM_SPEC.md）的核心契约：

* ``test_execution_isolation.py``：多 Interpreter 实例的执行隔离（M4）
* ``test_concurrent_llm.py``：LLM dispatch-before-use 行为确定性（M5c）
* ``test_memory_model.py``：IbCell 生命周期 + snapshot 自包含性（M1/M2）

每个测试文件独立可运行，仅依赖 ``core.engine.IBCIEngine`` 公开接口与
标准 Python 库，不依赖任何内部私有实现细节——这保证了未来其他宿主实现
（Rust/Go/C++ 等）可以用相同测试套件验证合规性。
"""
