# _ENUM_SWITCH_COMPLETION_HANDOFF — enum/switch 补全评估 + KNOWN_LIMITS 分类交接

> 2026-08-12 编制。供下一 session 进一步核查与完善开发。本文档 = enum/switch 能力增强
> 与机制补全的地基评估 + KNOWN_LIMITS 全量分类（历史遗留 vs 设计限制 vs 环境限制）+
> 下一 session 交接清单。**本文档只评估，未改代码。**

---

## 一、enum 现状盘点（2026-08-12 全实测）

### 1.1 已可用（全部实测通过）

| 能力 | 状态 |
|------|------|
| 声明（继承 Enum + 类型化成员） | ✅ |
| 成员访问 `Color.RED` | ✅ |
| `==` / `!=` 比较 | ✅ |
| switch/case | ✅ |
| **任意类型成员**（int/float/bool/str） | ✅ **语法已放开**（KNOWN_LIMITS §二 过时） |
| 容器使用（list[Color]/dict[Color,int]） | ✅ |
| 函数参数/返回值 | ✅ |
| 变量插值到 LLM（__to_prompt__） | ✅ |
| MOCK 模式 | ✅ |
| **静态类型身份**（`str s = c` 报 SEM_TYPE_MISMATCH，Color≠str） | ✅ 一等类型 |

### 1.2 仍不可用/受限

| 限制 | 实测 | KNOWN_LIMITS |
|------|------|-------------|
| 迭代 `for v in Color:` | ❌ `VM: Object is not iterable` | §二 记录 |
| 数量/序数 `len(Color)` | ❌ `Class 'Color' has no attribute 'len'` | §二 记录 |
| 自定义方法 | ❌ `None has no method '__call__'` | **未记录** |
| **int/float/bool 枚举 LLM 集成** | ❌ 成员名≠值 → 解析错 + switch 失配 | **未记录** |

### 1.3 核心缺陷：非 str 枚举 LLM 集成不工作（新发现）

```ibci
class Code(Enum):
    int OK = 200
    int ERR = 500

Code c = @~ ...只输出 OK、ERR ~   # LLM 返回成员名 "OK"
(str)c → "OK"        # str，不是 200
c == Code.OK → False # "OK" vs 200
switch c → 全失配
```

**根因**（已追到实现）：
- `EnumAxiom.from_prompt`（`core/kernel/axioms/primitives/enum.py:89-115`）把 raw_response
  解析为**成员名**（`if upper in index_map: return (True, upper)`），不查成员值。
- **str 枚举碰巧工作**：str 成员值==名（`str RED = "RED"`），解析出的名恰等于值。
- **值映射缺失**：`spec.members` 是 `MemberSpec`（只有 `type_ref` 类型，无值）；运行时
  值在 `ib_class.default_fields[name].static_val`（int 200）。axiom 在 kernel 层拿不到值。

### 1.4 enum 补全的地基条件（全部就绪）

| 所需机制 | 地基 | 先例 |
|---------|------|------|
| 方法注册（to_list/len） | `get_method_specs` + `has_iter_cap` | `GeneratorAxiom`（generator.py）、`sequences.py`（len/to_list） |
| prompt 协议 | `from_prompt`/`__outputhint_prompt__`/`__to_prompt__` | `BaseAxiom` + 各 axiom |
| 成员值扩展 | `MemberSpec.metadata` dict（可放 value） | — |
| 类型身份 | 枚举是一等类型（Color≠str 编译期区分） | 已验证 |
| 迭代 | `has_iter_cap = True` + 值对象 `to_list` | sequences/sentinels |

**结论**：enum 补全（迭代/数量/方法/LLM 集成）**地基已充分**，可正式实现。此前因泛型/OOP
不完善搁置的限制，在 axiom 体系、GenericTypeRegistry、prompt 协议、CPS 驱动成熟后均已消除。

---

## 二、switch 设计评估（2026-08-12）

**结论：维持"自动跳出"设计，不引入 C 模式 fall-through。**

理由：
1. IBCI 是 Python 风格语言——自动跳出与 `if/elif/else` 同构，符合用户直觉。
2. C 模式唯一收益是"多值共享分支"（fall-through 合并多个 case），但这是 C 历史包袱
   （漏 break 是经典 bug 源）。
3. 当前 switch 已稳定（值/字符串/Enum/default/break no-op/continue 透传全验证）。

**可选增强（未来）**：多值 case `case 1, 2:` —— 覆盖 fall-through 唯一真实收益的安全替代。
当前语法层不支持（`case` 后跟单 pattern），需 parser + AST + VM 扩展。

---

## 三、KNOWN_LIMITS 全量分类（25 章）

### 分类标准
- **H（历史遗留）**：因实现不完整/重构丢失导致不可用，非设计限制——**具备实现条件**。
- **D（设计限制）**：有意的语言设计决策，不实现。
- **E（环境/固有）**：宿主/进程级固有边界，IBCI 无法改变。
- **O（过时）**：文档描述与实现不符（实现已放开/已修复）。

| 章 | 条目 | 分类 | 判定 |
|----|------|------|------|
| 一 | 可调用类实例 __call__ 协议 | H→已修 | 2026-08-12 O1 修复（_UserCallDrive CPS 驱动），已更新 |
| **二** | **Enum 语法** | **H** | **str 成员限制过时（int/float/bool 可用）；迭代/数量/方法/LLM 集成待补** |
| 三 | Uncertain 内部哨兵 | D | 设计内部机制 |
| 四 | 行为表达式不可 return | H→已修 | 2026-08-12 拦截随迁 v2（visit_IbReturn） |
| 五 | 引用语义局限性 | D | 与 Python 一致的设计 |
| 六 | 子类 auto-init 不含父字段 | D | 与 Python 一致 |
| 七 | auto/fn/any/裸赋值对比 | D | 设计 |
| 八 | 容器多类型声明 | D | 无 union 类型机制 |
| 九 | 已废弃语法 | D | 硬编译错误（设计） |
| 十 | 泛型与容器限制（dict 键不校验） | D | 设计取舍 |
| 十一 | Switch 使用约束 | D→已更新 | 2026-08-12 更新为"基本可用 + 使用约束" |
| 十二 | intent_context 静态调用静默无效 | D | 设计（有 SEM_INTENT_STATIC_CALL 警告意图） |
| 十三 | @ 意图注释放置约束 | D | 设计 |
| **十四** | **用户类能力差距（泛型/运算符）** | **H** | **运算符覆盖有限（§十四 #2 部分 H，未逐核）；用户类泛型参数 = 语法层未实现（AST 无 type_params），地基已备** |
| 十五 | DDG 并发调度行为边界 | D/E | 设计边界 + MOCK 能力固有 |
| 十六 | MOCK 无法验证的 LLM 功能 | E | 固有（需真实 LLM） |
| 十七 | 设计排除语法（walrus 等） | D | 设计 |
| 十八 | 禁止循环导入 | D | 与 Rust/Go 一致 |
| 十九 | 插件可见性隔离 | E/D | 进程级固有 + 设计 |
| 二十 | llmexcept retry 禁文件写 | D/E | 磁盘快照固有 + 设计约束 |
| 二十一 | 布尔上下文行为定型 | D | 设计（显式优于隐式） |
| 二十二 | 通信原语面（signal 非关键字） | D | 设计 |
| 二十三 | 递归深度受宿主栈限制 | E | 宿主 RecursionError 固有（已保留根因） |
| 二十四 | 生成器消费同步阻塞 | D/E | 设计边界（已更新描述） |
| 二十五 | yield from 序列委托静态类型 | D | 类型绑定取舍 |

### 分类汇总

| 分类 | 数量 | 章节 |
|------|------|------|
| **H（历史遗留，具备实现条件）** | **3** | 二（enum 补全）、十四 #2（运算符覆盖度核对）、十四 #1（用户类泛型参数） |
| D（设计限制） | 15 | 三/五/六/七/八/九/十/十一/十二/十三/十七/十八/二十一/二十二/二十五 |
| E（环境/固有） | 4 | 十六/十九/二十/二十三 |
| D/E（混合） | 2 | 十五/二十四 |
| H→已修 | 2 | 一/四 |

---

## 四、下一 session 交接清单（进一步核查 + 完善开发）

### 4.1 建议优先：enum 补全（地基充分，含 2 缺陷修复 + 3 能力增强）

**缺陷修复（易用性陷阱）**：
1. **非 str 枚举 LLM 集成**（核心）：
   - 方向：编译期把成员值写入 `MemberSpec.metadata["value"]`（symbol_collection_pass 填充
     `Color.OK` 的值 200），`EnumAxiom.from_prompt` 解析成员名后映射回值。
   - 需核查：① symbol_collection_pass 是否可访问成员字面量值；② spec.members 序列化
     （serializer.py:260 members_uids）是否需携带 metadata；③ 对 str 枚举保持零回归
     （值==名，映射后仍相等）。
2. **枚举自定义方法**（`func is_done(self)` 报 `None has no method`）：
   - 方向：核对枚举类方法注册路径（与用户类方法对齐）。可能是枚举类构造/方法表缺失。

**能力增强（地基已备）**：
3. **迭代** `for v in Color:`：`EnumAxiom.has_iter_cap = True` + `get_method_specs` 注册
   `to_list`，运行时枚举类提供成员值列表（参照 `GeneratorAxiom`）。
4. **数量/序数** `len(Color)`：`get_method_specs` 注册 `len`，运行时枚举类提供成员数。
5. **（可选）switch 多值 case** `case 1, 2:`：parser + AST + VM 扩展（独立于 enum）。

**需核查**：KNOWN_LIMITS §二 更新（删"仅支持 str"过时；补迭代/数量/方法/LLM 集成状态；
修"LLM 输出支持"表述）。

### 4.2 次优先：KNOWN_LIMITS 用户类能力差距（§十四）

- §十四 #2 运算符覆盖度：实测 `__eq__`/`__add__` 已可，需逐核 `<`/`in`/`is`/一元运算
  的用户类覆写——补齐覆盖或文档精确化。
- §十四 #1 用户类泛型参数：地基已备（GenericTypeRegistry 支持任意泛型声明），但需
  语法层（lexer/parser/AST `type_params`）+ 语义层 + 序列化扩展——**独立大任务**，建议
  单独评估，不与 enum 补全混做。

### 4.3 核查方法建议

1. enum 补全前先写契约测试（参照 `test_generator_ibclass.py` 的 GEN-1~4 模式）。
2. 每项改动走 code-workflow Phase 0-5 + 全量 pytest 零回归。
3. LLM 集成修复后：真实 LLM 跑 int 枚举 + switch 组合（修复前 sw_other 失配）。
4. 完成后更新 KNOWN_LIMITS §二（删除过时，记录新能力）。

---

## 五、约束

- 全程本地 commit，禁 push（硬原则）。
- 破坏性变更按"独立分支 + 零风险直接合并/大风险 cherry-pick"政策。
- enum 补全是机制补全（有先例 GeneratorAxiom），非 tricky/兼容层。
