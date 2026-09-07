# 知识注册表（knowledge）

> IBCI 的一等内置值类型 `knowledge` = 语言自动机的**知识层**：机器持有的
> 已验证知识是**类型化、门控、可审计**的。本页描述其地位、语义不变量、
> 条目模型、方法面与惯用法。

## 地位：知识层（in-language knowledge database）

IBC 结构 = 稳定可靠的语言自动机。"验证过的知识从非确定性层毕业到确定性
层"是该自动机的核心动力学：新对象经 LLM 提案与确定性裁判验证后提交为
知识，后续查询不再经过 LLM 调用。`knowledge` 类型让该机制成为**语言级
机制**，而非外部 Python 里的约定。

三个系统支柱的分工：

| 支柱 | 职责 | 载体 |
|------|------|------|
| 意图（intent 体系） | 认知作用域（改写解释） | 既有（intent_context 等） |
| 模型 I/O（ai 模块） | LLM 调用 / embedding 调用（纯模型交互） | 既有 `ai` |
| **知识（本类型）** | **已验证知识的持有/查询/更正/审计** | **`knowledge`（一等值类型）** |

## 语义不变量（硬约束）

1. **`@~...~` 行为描述语句 = LLM 调用**，语义不因本类型改变。本类型**不
   提供**任何"查表命中则跳过 LLM"的语句内隐式路由——一切知识操作都是
   **显式程序操作**（普通值方法调用，代码可见、可审计、可测试）。
2. "先查知识库再决定是否调 LLM"是**用户的控制流**（显式 if/else），不是
   引擎的隐式行为（见下方惯用法）。
3. 验证门（check）必须是**确定性验证**：谓词体内含 LLM 调用或不透明
   （编译器无法证明其确定性）在**编译期**即拒绝（`SEM_KNW_CHECK_LLM` /
   `SEM_KNW_CHECK_OPAQUE`）——不纯度不可证明即拒绝，不做运行期探测兜底。

## 类型形态

- **一等内置值类型**：可构造（`k = knowledge()`）、可多实例（程序持有多个
  知识库，如 dict）、可传参/可存变量/可进 `save_state`。
- **混合语义**（显式声明）：
  - 知识库对象本身 = **可变值对象**（引用语义，同 dict：共享、传参、
    save_state 值语义）；
  - 条目值 = **冻结快照**——store 入时深克隆 + get 出时深克隆
    （"知识库可变，知识不可变"：修改取回值或登记后的原值，均不污染
    知识库，审计链不被引用陷阱污染）。

## 条目模型

```
键（str，显式）→ 条目 {
  value:   深克隆冻结快照
  check:   登记时的验证谓词（审计"经谁验证"）
  events:  append-only 事件流 [ {seq, kind: store|amend, value, reason} ]
           （seq = 引擎事件序号，单调，可复现——非墙钟）
}
```

## 方法面

| 方法 | 语义 | 纪律 |
|------|------|------|
| `k.store(key, value, check)` | 登记（首次写入） | 引擎求值 `check(value)`：假 = 运行期错误 `KNW_CHECK_REJECTED`；键已存在 = `KNW_KEY_EXISTS`（"登记"与"更正"机器强制区分） |
| `k.get(key)` | 查询当前值 | 未登记 → `null`（合法状态非错误）；返回深克隆快照 |
| `k.amend(key, new_value, reason)` | 更正 | `reason` 强制非空（`KNW_REASON_EMPTY`）；新值再过 check 门；append-only（原值保留于事件流，当前值指针切换） |
| `k.history(key)` | 审计 | 事件序列 `list`（元素为 `{seq, kind, value, reason}` dict）；未登记 → 空 list |
| `k.keys()` | 枚举键 | `list[str]`（容器约定与 dict 同构） |
| `k.len()` | 计数 | `int`（容器约定与 dict 同构） |

## 惯用法（canonical idiom）

"先查知识库再决定是否调 LLM"——用户控制流的确定性验证门模式：

```python
knowledge kb = knowledge()

func verify(str x) -> bool:
    # 确定性验证（文本/格式/长度检查；不得含 LLM 调用）
    return x.len() > 0

key = "term:" + user_input
any known = kb.get(key)
if known == None:
    # 未命中：走 LLM 提案 + 确定性验证 + 登记
    str candidate = @~ 给出: user_input 的定义 ~
    if verify(candidate):
        kb.store(key, candidate, verify)
        answer = candidate
    else:
        answer = candidate   # 验证不过：不登记，直接答复
else:
    answer = (str)known      # 命中：0 次 LLM 调用（机器持有的知识）
```

要点：
- check 谓词 = **本模块显式定义的函数**（编译器遍历其函数体证明确定性）；
- 登记前验证与登记门是**同一个谓词**（提案先自证，过门才提交）；
- 命中路径完全不调用 LLM——这就是"用得越久越确定"的语言级落地。

## 状态恢复（save_state / load_state）

- 知识库经 `ihost.save_state` / `load_state` 持久化：条目值、审计事件流、
  事件序号保真；save 后的变更在 load 后丢弃（状态回退到快照）。
- **边界**：`load_state` 为**同入口程序 / 同会话**的状态恢复机制（快照的
  变量身份绑定编译期符号表；跨入口文件的快照恢复不受支持）。
- **边界**：验证谓词引用**不入值快照**（函数非值快照）。恢复后条目仍可
  `get`/`history`，但 `amend` 因谓词引用丢失而 fail-fast
  （`KNW_CHECK_REJECTED`）——需重新 `store` 登记。

## 并发语义

知识库对象是值对象：同一实例可被多线程/多协程共享（引用语义，同 dict）。
**只读共享**（`get`/`history`/`keys`/`len`）可并发；**写操作**（`store`/
`amend`）的并发互斥由用户的控制流纪律保证（与 dict 等容器同纪律——语言
不提供内置锁面）。

## 不做什么（边界）

- 不做向量检索面（embedding 检索走 `ai.retrieve`；知识条目查询 = 显式键，
  无语义相似度隐式路由）。
- 不做谓词引用跨快照恢复（见上；登记与快照是两个面）。
- 不做隐式路由/短路（语义不变量 1）。
