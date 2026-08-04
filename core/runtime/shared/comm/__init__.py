"""
core.runtime.shared.comm — 统一通信内核（PT-MT-3）。

两个正交通信域（用户裁定 §三，不能用一个超抽象覆盖；Signal 控制流域已移除，
见 WORKLOG 会话 8）：
- Channel（数据流：stream / message / pubsub）
- Slot（共享状态：具名原子读写）

共享线程安全 bounded buffer（CommBuffer）与可寻址注册表（CommRegistry）。

本包为纯 Python 线程安全原语，不依赖 core.runtime.objects（IbObject 在
object 层）——语言层 ``IbChannel`` / ``IbSlot`` 在 ``core/runtime/objects/``
定义并引用本包核心，避免循环导入。
"""
