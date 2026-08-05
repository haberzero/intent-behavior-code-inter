# thread 架构硬编码分支与类型系统/公理体系隐患 —— 深度调查

> 状态：**调查完成**（2026-08-04 会话 9）
> 触发：用户观察——thread 实例/类处理存在特殊 if-else 分支；公理/底层方法与现存机制不统一；
> 怀疑 thread 架构设计缺陷 + 底层类型系统/公理体系隐患。
> 缺陷特征：通用型、全对称、全协议化的处理流程中，突兀出现针对特定类型的硬编码分支。
> 登记项见 `PENDING_REVIEW_ITEMS.md` §四 T1-T3。

---

## 一、结论摘要

1. **用户观察确认成立**：存在多处针对 thread 的突兀硬编码分支，且 thread 公理/底层机制与 chan/slot 等现存机制**构造路径不统一**。
2. **类型系统/公理体系隐患确有其事，但需精确归因**：不是 thread 独有的 bug，而是 **"泛型成员特化机制缺失"** 的系统性模式——`thread[T].join()→thread_result[T]` 只是该缺失机制的最新受害者。list/dict/Optional 早已用同一 if/elif 级联补丁，thread 加入后级联继续膨胀。
3. thread 真正**突兀**的点：它是唯一一个"普通调用构造 + 手工 `__init__` 原生函数 + 序列化瞬态存根"三合一特殊处理的 kernel 类型（chan/slot 走专用 AST 节点构造，构造机制双轨）。

---

## 二、确认存在的状况（逐条验证）

### A. 针对 thread 的突兀硬编码分支（thread 特有）

| # | 位置 | 内容 | 突兀性证据 |
|---|------|------|-----------|
| A1 | `runtime_serializer.py:196` | `if obj.ib_class.name == "thread" and not isinstance(obj, IbClass)` → thread_transient 存根 | **插在通用 `cls_name` 分发链之前**（structurally 特殊）；thread 是唯一有瞬态存根的 kernel 类型——chan/slot/subscriber 实测序列化为空 object（数据丢失），file_handle/media 走 storage_model 协议。**处理不对称** |
| A2 | `runtime_serializer.py:271` | `cls_name == "thread_result"` 专用分支（status/value/error） | 因 thread_result 有 `_status` 额外状态，需专用序列化形态 |
| A3 | `primitive_initializer.py:605-650` | `_thread_init` 手工注册段：**唯一**注册 `__init__` 原生构造函数的 kernel 类型；内部 `args[0]/args[1]` 索引读取 + 手工解包 list + coordinator 查找 | chan/slot 构造在 handler 直接 new；media/file_handle 注册的是静态方法/协议。构造契约无 spec 校验（review G7 同指） |
| A4 | `ib_class.py:88` | instantiate `impl_cls = get_ib_implementation(self.name)` + `_create_blank` 钩子 | 协议驱动（非硬编码），但 thread 是**唯一覆写 `_create_blank`** 的类——单消费者协议 |
| A5 | `ThreadAxiom.has_call_cap=True` + `resolve_return_type_name` | thread 是可构造内核类型中唯一走"普通调用"路径的 | chan/slot 用专用 AST 节点（IbChannelExpr/IbSlotExpr）绕过 has_call_cap；thread 走 instantiate + `__init__` |

### B. 系统性模式（thread 只是最新成员）

| # | 位置 | 内容 | 说明 |
|---|------|------|------|
| B1 | `_members.py:53-140` | `resolve_member` per-type if/elif 级联：LIST/DICT/OPTIONAL/**THREAD**/**THREAD_RESULT** | thread 是第 4/5 个成员，级联持续膨胀 |
| B2 | `serializer.py:188/194` | thread/thread_result value_type 持久化分支 | 与 list/dict/Optional 的字段持久化同类 |
| B3 | `type_ref.py:133-191` | `from_spec` kind 分发：LIST/TUPLE/DICT/CALLABLE_INSTANCE/OPTIONAL/**THREAD**/**THREAD_RESULT** | thread 是其一 |
| B4 | `artifact_rehydrator.py:142/146/220` | shell_creators kind→lambda 分发 + value fill | thread 是其一 |
| B5 | `_axiom_name` 泛型路由 | fn_callable/behavior/thread/thread_result/enum | **通用机制**（非 thread 特有） |

### C. 公理/底层机制不统一点

1. **构造机制三轨并存**：
   - chan/slot/subscriber：专用 AST 节点（IbChannelExpr/IbSlotExpr）+ handler 直接 new 实现类实例
   - thread：普通函数调用 `thread(...)` → has_call_cap + instantiate + 类 `__init__`（`_thread_init` 原生函数）→ 写槽位
   - thread_result：`t.join()` Python 直接构造 `IbThreadResult(...)`（不经语言构造路径）
2. **成员返回类型"any 兜底"**：ThreadAxiom `join/cancel ret="any"`、ThreadResultAxiom `unwrap ret="any"`、ChannelAxiom `recv ret="any"`——都靠 `_members.py` 级联特化"纠正"（如 join→thread_result[T]、unwrap→Optional[T]、recv 未特化仍 any）。这是泛型成员特化机制缺失的体现。

---

## 三、深层根本成因

1. **统一泛型模型半落地（核心根因）**：`generic.py`（任务 B）建立了 `GenericTypeDeclaration` 统一模型，覆盖泛型类型的 **build（创建）/ to_typeref（序列化）/ restore（还原）** 三操作。但 **`resolve_member` 的成员返回类型特化没有纳入该模型**——仍是 `_members.py` 里 per-type if/elif 级联。thread[T] 的 join/thread_result[T] 的 unwrap 只是这个缺失机制的最新受害者。**每次新增泛型类型都强制向级联加分支**——正是"过程式硬编码分发"（工作模式定论第 4 条明令禁止）+ 违反 design-philosophy"机制同构/单一权威源"。
2. **axiom 声明能力受限**：`_m(name, params, ret)` 只能用固定 TypeRef（`_m("join", ret="any")`），**无法声明"返回类型 = 泛型参数 T"**。泛型依赖的返回类型只能 any + 外部特化。这是公理体系的表达能力缺口，迫使后续特化补丁。
3. **值对象承载模式未完全统一**（G1 根因延续）：阶段 2 已统一 thread/thread_result，但 IbOptional 双载（`_inner`+payload）、IbChannel/IbSubscriber 的 core/view 槽仍在。序列化/内省需按类型特殊处理。
4. **kernel 类型构造/初始化路径分裂**：primitive_initializer 集中式特殊段（intent_context/thread/media/file_handle 各一段），构造机制三轨（AST 节点/普通调用/静态工厂）。thread 选择了"普通调用"这一轨，因而额外需要 has_call_cap/instantiate/__init__/瞬态存根四件套。
5. **瞬态 vs 持久类型无统一协议**：serializer 对"含运行时句柄的瞬态类型"没有统一处理——thread 因含 coordinator 引用（会无限递归）被单独加存根；其它瞬态类型（chan/slot/subscriber）因不递归而被**遗漏**（空 object 数据丢失）。thread 有存根、chan 没有——处理不对称本身即是碎片证据。

---

## 四、系统性隐患评估（是否类型系统/公理体系层面）

**结论：是，但归因需精确。**

- ✅ **确实存在系统层隐患**：泛型成员特化机制缺失 → `_members.py` 级联持续膨胀 → 每新增泛型类型（thread、subscriber、未来用户泛型类 PT-4.4）都强制硬编码分支。这是"类型系统表达能力不足 → 用过程式硬编码补丁"的结构性问题，属 design-philosophy 明确反对的碎片化。
- ✅ **确实存在机制不统一**：kernel 可构造类型的构造路径三轨并存；瞬态类型序列化处理不对称。
- ⚠️ **但 thread 并非"公理体系本身有 bug"**：ThreadAxiom 遵循了既有的 axiom 协议（get_method_specs/is_compatible/has_call_cap 均是标准接口）；其"突兀"来自①选择了普通调用构造路径（chan/slot 用 AST 节点避开）②泛型成员特化机制缺失（join ret="any" 与 list pop ret="any" 同类）。thread 是"症状暴露最充分的成员"，不是"独立病灶"。

**触发警报的缺陷特征（用户归纳）验证**：在通用 `resolve_member`/`_collect_instance`/`from_spec`/`shell_creators` 流程中，针对特定类型的硬编码分支——**确认存在**（B1-B4 + A1/A2），且已呈级联扩张趋势。

---

## 五、建议方向（供用户决策，非本轮实施）

1. **成员特化协议化**（治本）：将 `resolve_member` 的泛型成员特化纳入 `GenericTypeDeclaration`（新增 `member_resolve` 回调），`_members.py` 级联收敛为注册表驱动。thread/subscriber/未来泛型类型均经声明生效。
2. **kernel 构造机制统一**：chan/slot/thread 走同一构造路径（统一"可构造 kernel 类型"协议），消除 has_call_cap 与 AST 节点双轨。
3. **瞬态类型序列化协议化**：thread/chan/slot/subscriber 统一瞬态存根处理（含 `_state` 等状态），消除不对称。
4. **公理返回类型正确化**：若成员特化机制落地，ThreadAxiom join/cancel、ThreadResultAxiom unwrap 可声明正确类型，取消 any 兜底。

> 上述建议与本清单 L1-L7（PENDING_REVIEW_ITEMS.md §二）有交叠，处理顺序由用户裁定。
