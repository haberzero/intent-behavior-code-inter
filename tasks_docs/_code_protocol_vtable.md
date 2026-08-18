# 临时任务文档：protocol_vtable 数据结构落地（P6 核心，决策 1 B）

> **性质**：临时任务控制文档（code-workflow §五，多修改单元追踪）。落地后删除（git 承载）。
> **承接**：`NEXT_STEPS.md` 候选 #1「protocol_vtable 数据结构（P6 核心）」，设计权威
> `_five_foundation_P1_design.md` §五（含 WORKLOG 形状修正）。

## 〇、任务范围（本单元）

在 `exp/protocol-vtable` 分支上落地 **per-IbClass 协议方法表**（决策 1 B，形状修正后）：

1. `ProtocolSlot` 数据结构（消息名槽：native 原生处理器 + overlay 影子条目 + overlay_enabled）。
2. `IbClass.protocol_vtable` 槽（消息名 → ProtocolSlot），`lookup_protocol_slot` 沿父链查表。
3. `_dispatch_protocol_message` 改为查表分派（native 按值 Python 类解析并记忆化）。
4. 全量 pytest 零回归（2980）+ 补充判别性测试 + commit。

**不做**（后续 P2-②/③、P5、P6 剩余）：overlay 激活接线、D2 to_prompt 激活、D1 双注册表收敛、
D3 spec.members↔vtable 双表同步桥（运行期协议成员查询）。

## 一、形状修正结论（WORKLOG 实证，设计地基）

- `receive` 协议分派按**消息名（dunder 方法名）**查 `_dispatch_<name>`——处理器是
  **值 Python 实现类上的实例方法**（`IbObject._dispatch_call` / `IbClass._dispatch_call` /
  `IbSuperProxy._dispatch_call` …），非 `IbClass.methods` 里的 IbFunction。
- `dunder_names()` 是扁平并集、丢"方法→协议"归属；多协议共方法（`__getattr__`→attribute、
  `cast_to`→converter、`__eq__`→operator）须按**消息名**索引。
- **多态值类（关键约束，本单元实证）**：同一 IbClass 可宿主多个值 Python 类且各自覆写
  `_dispatch_*`：
  - `callable` → `IbFunction` 族（native 经 MRO 落 `IbObject._dispatch_call`）**且**
    `IbSuperProxy`（自有 `_dispatch_call`）；二者 `ib_class` 均为 `callable`。
  - `Type` → `IbClass`（自有 `_dispatch_call/getattr/getitem`）**且** `HostClassBinding`
    （自有 `_dispatch_call`）。
  - 类对象（`Box`）与其实例共用 `ib_class`（`Box.ib_class = Box` 自指），但类对象分派须走
    `type(Box)=IbClass._dispatch_call`（元类语义），实例分派走 `type(instance)=IbObject._dispatch_*`。
  - **结论**：native 处理器解析必须按**值实际 Python 类**（`type(self)`）记忆化，
    不能按 IbClass 静态烘焙单一处理器——否则 super proxy / HostClassBinding / 类对象分派被破坏。

## 二、数据结构定稿

```python
class ProtocolSlot:
    __slots__ = ("message", "_native_by_class", "overlay", "overlay_enabled")
    # message: 协议消息名（dunder 方法名，如 __call__ / cast_to）
    # _native_by_class: Dict[值Python类, handler]  —— native 按值类记忆化（多态安全）
    # overlay / overlay_enabled: 覆层影子条目（决策 2，默认不参与分派；P2-② 启用接线）

    def native_handler(self, value):
        cls = type(value)
        if cls not in self._native_by_class:
            self._native_by_class[cls] = getattr(cls, f"_dispatch_{self.message.strip('_')}", None)
        return self._native_by_class[cls]

    def active_handler(self, value):
        if self.overlay_enabled and self.overlay is not None:
            return self.overlay
        return self.native_handler(value)
```

`IbClass.__slots__` 增 `protocol_vtable: Dict[str, ProtocolSlot]`（惰性建槽，仅对协议消息）。

- `lookup_protocol_slot(message)`：本类表 → 父链（机制同构 `lookup_method`，为 overlay 继承预留）。
- `ensure_protocol_slot(message)`：dunder_names 门控（协议消息才建槽），本类表惰性创建。

## 三、分派接线（_dispatch_protocol_message）

```python
def _dispatch_protocol_message(self, message, args):
    if message not in self._protocol_message_names():      # 协议消息门控（注册表单一权威）
        return None
    slot = self.ib_class.ensure_protocol_slot(message)     # 惰性建槽 + 父链查表
    if slot is None:
        return None
    handler = slot.active_handler(self)                    # overlay 优先（未启用则 native）
    if handler is None:
        return None
    result = handler(self, message, args)                  # 存的是未绑定函数，传入值
    if result is not None:
        return result
    return None
```

语义保持：handler 返回 None = 无特殊行为 → 继续普通路由（vtable `lookup_method`），与现状一致。

## 四、验证门

- 全量 `python -m pytest tests/` 零回归（当前 2980 passed / 1 skipped）。
- 判别性测试：super proxy 分派、类对象特化、Optional 委托、FnCallable 内部消息保持；
  protocol_vtable 消息名键形状、多态 native 解析（callable→IbFunction vs IbSuperProxy）、
  overlay 默认不参与分派。
- 本地 commit（禁 push）。

## 五、决策记录（自主，工作模式定论 + design-philosophy）

- **native 按值类记忆化而非 IbClass 静态烘焙**：形状修正 + 本单元多态实证（super proxy /
  HostClassBinding / 类对象自指 ib_class）。若按 IbClass 烘焙单一处理器将破坏
  `test_super_proxy_dispatch_preserved` 等判别性契约——质量红线（兜底/双通道）反向约束：
  "查表"必须仍按值分派，记忆化即消除逐次 getattr 能力探测（D5），同时保持多态正确。
- **协议消息门控保留 dunder_names**：注册表是"哪些消息存在"的单一权威（协议注册表）；
  per-IbClass 表承载"该类如何分派 + overlay 挂载 + 后续 D3 桥"，二者职责分层，非双通道。
- **ProtocolSlot 含 overlay 字段但默认不启用**：P1 §5.3 定稿的数据形态（native+overlay+
  enabled），"默认态不参与分派"即规格语义，非死字段（P2-② 启用接线，不在此半接通）。
- **overlay 激活 / to_prompt 激活 / D3 桥 / D1 双注册表** 均按 NEXT_STEPS 归 P2-②/P5 后续，
  本单元不做，避免半接通/双通道。
