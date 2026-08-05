# L6 瞬态序列化协议化 —— 设计

> 状态：**设计待实施**（2026-08-04 会话 10）
> 依据：`THREAD_ARCH_HARDCODE_INVESTIGATION.md` §五 建议 3 + `PENDING_REVIEW_ITEMS.md` L6
> 原则：工作模式定论（禁 per-type 硬编码分支/禁双通道）+ design-philosophy（机制同构/
> 单一权威源/协议驱动）+ 用户立场（不删也不修 = 不可接受）
> 最后更新：2026-08-04

---

## 一、问题（L6）

运行时序列化（`runtime_serializer._collect_instance`）对"含运行时句柄的瞬态对象"
处理**不对称**：

| 类型 | 现状 | 问题 |
|------|------|------|
| thread | `thread_transient` 专用分支（按 `ib_class.name == "thread"` 硬编码，插在通用分发链之前） | 硬编码分支（调查 A1） |
| chan | 无处理 → 落通用 object 分支 → 空 fields | **数据全丢**（mode/subscriber_count 等） |
| slot | 无处理 → 空 fields | **数据全丢**（name/value） |
| subscriber | 无处理 → 空 fields | **数据全丢**（closed/qsize） |

这是真实数据丢失缺陷（快照/序列化后 chan/slot/subscriber 状态归零）+ 处理不对称碎片。

## 二、设计（协议驱动，消除 per-type 分支）

### D1. 瞬态协议方法 `__transient_state__() -> dict`

瞬态对象实现公开 dunder 协议方法，返回**纯状态 dict**（无递归引用；值可为 IbObject，
由 serializer 递归处理）：

- `IbThread.__transient_state__()` → `{"state": self._state, "done": bool(spawned done)}`
- `IbChannel.__transient_state__()` → `self.core.snapshot()`（mode/name/closed/qsize 或 subscriber_count）
- `IbSlot.__transient_state__()` → `self.core.snapshot()`（name/value）
- `IbSubscriber.__transient_state__()` → `self.view.snapshot()`（qsize/maxsize/closed）

### D2. serializer 统一 `transient` 存根（协议检测，非 per-type 分支）

`_collect_instance` 中（原 thread_transient 位置），以**鸭子协议检测**（与 disk_backed
的 `hasattr(descriptor, "to_native")` 先例一致）：

```python
# 瞬态对象协议（L6 统一）：实现 __transient_state__ 的对象序列化为纯状态存根，
# 不递归运行时句柄。thread 原 thread_transient 专用分支由此协议取代。
if not isinstance(obj, IbClass) and hasattr(obj, "__transient_state__"):
    state = obj.__transient_state__()
    data["_type"] = "transient"
    data["state"] = {k: self._process_value(v) for k, v in state.items()}
    self.instance_pool[uid] = data
    return uid
```

- **删除 `thread_transient` 专用分支**（A1 消除）。
- `_process_value` 递归处理 state 中嵌套 IbObject（如 slot 的值、thread 状态为普通 str/bool 原样）。
- 检测用 hasattr（公开协议方法，非私有穿透；与 disk_backed 先例一致），非类名/kind 分支。

### D3. 反序列化统一 `transient` 分支

```python
elif _type == "transient":
    # 瞬态对象不可复活（活体句柄/队列），重建为携带已知状态的占位 IbObject，
    # 供内省（快照恢复后仍可读取 mode/name/value/state 等）。
    obj = IbObject(ib_class)
    self.instance_cache[uid] = obj
    obj.fields["_transient_state"] = {
        k: self._deserialize_value(v) for k, v in data.get("state", {}).items()
    }
```

- 与现状（空 object）相比改进：状态保留（可内省）。
- 不再落通用 object 分支（数据不再归零）。

### D4. 状态值递归

`__transient_state__` 返回 dict 的值经 `_process_value`（序列化）/ `_deserialize_value`
（还原）处理——嵌套 IbObject（如 slot 值）保持完整往返，非 IbObject（str/int/bool）原样。

## 三、涉及文件

| 文件 | 变化 |
|------|------|
| `core/runtime/objects/thread.py` | `__transient_state__()` 方法 |
| `core/runtime/objects/kernel/comm.py` | IbChannel/IbSlot/IbSubscriber `__transient_state__()` 方法 |
| `core/runtime/serialization/runtime_serializer.py` | 序列化 transient 协议分支（删 thread_transient）；反序列化 transient 分支 |
| 测试 | 各瞬态类型序列化往返保真 + 快照状态断言 |

## 四、验证

- 每步全量 `python -m pytest tests/` 零回归。
- 关键断言：chan/slot/subscriber 序列化后 `_type == "transient"` 且 state 保真；
  thread 仍为 transient（协议取代专用分支）；slot 的 IbObject 值经递归完整往返。

## 五、决策记录

- 协议检测用 hasattr（公开 dunder 协议），与 disk_backed 鸭子先例一致，非 per-type 分支。
- 反序列化不复活活体（瞬态语义），重建为带 `_transient_state` 的占位对象。
- 独立分支：本改动仅涉 serializer 协议分支 + 4 个方法，边界清晰、危害可控（非语义核心），
  直接在主分支推进（不属"无法确认边界"的重构）。
