# _SWITCH_ENUM_ASSESSMENT_20260812 — switch 设计评估 + enum/switch 现状盘点

> 2026-08-12。两个问题：① 是否维持当前 switch 设计思路（自动跳出）还是改用 C 模式
> （显式 break + fall-through）；② enum/switch 现状盘点（此前因泛型/OOP 不完善搁置，
> 需评估现在的可用性与易用性）。全部结论实测验证。

---

## 一、switch 设计思路评估

### 1.1 当前设计（自动跳出，无 fall-through）

```ibci
switch x:
    case 1:
        print("one")
    case 2:
        print("two")
    default:
        print("other")
```

- 命中分支执行后**自动跳出** switch（无 C 语言 fall-through）
- case 内 `break` 是冗余但合法的 no-op（2026-08-12 已修复，消费为 no-op）
- case 内 `continue` 透传给外层循环
- 语义与 Python 的 `if/elif/else` 天然对应

### 1.2 C 模式（显式 break + fall-through）能带来什么

| 维度 | 当前（自动跳出） | C 模式（显式 break） |
|------|-----------------|---------------------|
| 语义安全 | ✅ 无 fall-through 意外穿透 | ⚠️ 漏写 break 导致意外 fall-through（C 经典 bug 源） |
| 与 Python 亲和 | ✅ `if/elif/else` 同构 | ❌ 与 Python 直觉相悖 |
| 多值共享分支 | 需重复 case（如 `case 1: case 2:` 需嵌套） | ✅ 天然支持 fall-through 共享 |
| 代码量 | 更少（无需 break） | 更多（每 case 需 break） |
| 调试风险 | 低 | 中（fall-through 难查） |

### 1.3 评估结论：**维持当前设计（自动跳出）**

**理由**：
1. **IBCI 定位是 Python 风格语言**——自动跳出与 `if/elif/else` 同构，符合用户直觉；
   C 模式的 fall-through 是 C 语言历史包袱（漏 break 是 C 经典 bug）。
2. **C 模式唯一收益是"多值共享分支"**（fall-through 合并多个 case）——但 Python 风格
   语言可通过 `case 1: case 2:` 多模式（未来可加）或 `or` 条件实现，不需要引入
   fall-through 的全部风险。
3. **当前设计已稳定**（2026-08-12 验证值/字符串/Enum/default/break no-op/continue 透传
   全部正常），改动需重新设计 KNOWN_LIMITS/测试/文档，收益不足以覆盖风险。
4. **C 模式收益场景罕见**：多值共享分支在 LLM 语言（IBCI 定位）中出现频率低。

**结论**：维持"自动跳出"设计。**可选增强**（未来）：多值 case（`case 1, 2:`）以覆盖
"多值共享分支"场景而不引入 fall-through——这是 C 模式唯一真实收益的安全替代。

---

## 二、enum 现状盘点

### 2.1 已可用的能力（实测全部验证）

| 能力 | 实测 | 状态 |
|------|------|------|
| 声明（继承 Enum + 类型化成员） | ✅ | 完整 |
| 成员访问 `Color.RED` | ✅ | 完整 |
| `==` / `!=` 比较 | ✅ | 完整 |
| switch/case（推荐控制流） | ✅ | 完整 |
| **任意类型成员**（int/float/bool/str） | ✅ | **已放开**（KNOWN_LIMITS §二 过时） |
| LLM 输出解析（str 枚举） | ✅ | 完整（成员名→成员值，因 str 成员值==名） |
| 容器使用（list[Color]/dict[Color,int]） | ✅ | 完整 |
| 函数参数/返回值 | ✅ | 完整 |
| 变量插值到 LLM 提示词（__to_prompt__） | ✅ | 完整 |
| MOCK 模式 | ✅ | 完整 |

### 2.2 仍不可用/受限的（实测）

| 限制 | 实测 | KNOWN_LIMITS 记录 |
|------|------|-----------------|
| 迭代 `for v in Color:` | ❌ `VM: Object is not iterable` | ✅ §二 记录 |
| 数量/序数 `len(Color)` | ❌ `Class 'Color' has no attribute 'len'` | ✅ §二 记录 |
| 自定义方法 | ❌ `Object of type 'None' has no method '__call__'` | ❌ **未记录** |
| **int 枚举 LLM 集成** | ❌ **成员名≠值，解析错 + switch 失配** | ❌ **未记录** |

### 2.3 核心缺陷：int/float/bool 枚举的 LLM 集成不工作（新发现）

**现象**（实测）：
```ibci
class Code(Enum):
    int OK = 200
    int ERR = 500

Code c = @~ ...只输出 OK、ERR... ~   # LLM 输出成员名
print((str)c)     # "OK"（str，不是 200）
bool eq = c == Code.OK   # False（"OK" 字符串 vs 200 int）
switch c:  # 全部失配 → default
```

**根因**：`EnumAxiom.from_prompt`（`core/kernel/axioms/primitives/enum.py`）把 raw_response
解析为**成员名**（`if upper in index_map: return (True, upper)`），但对非 str 枚举，
成员名 ≠ 成员值——LLM 输出成员名"OK"被当作枚举值，与 `Code.OK`（int 200）不相等。

**str 枚举为何碰巧工作**：str 枚举的成员值 == 成员名（`str RED = "RED"`），所以解析出的
成员名恰好等于枚举值。这是**巧合**，非设计正确性。

**影响**：KNOWN_LIMITS §二 声称"LLM 函数可以直接输出枚举成员名称并自动解析"——只对 str
枚举成立。int 枚举是 KNOWN_LIMITS §二 声称"不支持 int 成员"与"支持 LLM 输出"之间的**语义
半成品**：语法允许 int 成员，但 LLM 集成没跟上。

### 2.4 根因追溯

- **成员类型放开**：symbol_collection_pass / 声明层允许任意类型字段作为枚举成员（语法层
  无 str 限制）——这是"限制放松"但 **LLM 解析路径未同步**。
- **EnumAxiom.from_prompt**：设计为"返回成员名"，未考虑非 str 成员的值映射。
- **KNOWN_LIMITS §二**：声称"仅支持 str 成员"已过时（int/float/bool 实测可用），但
  "支持 LLM 输出"的说法对非 str 也过时（实际不工作）。

### 2.5 可用性/易用性总体评价

- **str 枚举**：成熟可用（声明/访问/比较/switch/LLM/容器/插值全通过），是当前实际可用形态。
- **非 str 枚举**：语法已放开但**语义半成品**——成员本身可用（int 值正确、比较正确），
  但 LLM 集成不工作。这是"文档说支持、实现半支持"的典型易用性陷阱。
- **缺失能力**：迭代/数量/自定义方法（KNOWN_LIMITS §二 部分记录；自定义方法未记录）。

---

## 三、建议

### switch
- **维持"自动跳出"设计**（不引入 C fall-through）
- 可选增强：多值 case `case 1, 2:`（覆盖 fall-through 唯一真实收益的安全替代）

### enum
1. **修复 int/float/bool 枚举 LLM 集成**（核心，易用性陷阱）：
   `EnumAxiom.from_prompt` 对非 str 成员，把成员名映射回成员值（查 index_map 后返回
   spec.members[name] 的值）。这样 `Code.OK`（200）与 LLM 解析结果一致，switch 正确匹配。
2. **KNOWN_LIMITS §二 更新**：删除"仅支持 str 成员"（已过时），补"迭代/数量/自定义方法
   不支持"（自定义方法未记录需补），修正"LLM 输出支持"为"仅 str 枚举"（或修复后全支持）。
3. **迭代/数量查询**：如需，可让 EnumAxiom 提供 `to_list`/`len`（与 GENERATOR 的
   to_list 机制同构）——但这是新功能，非缺陷修复。

> 本文档只读评估 + 实测，未改代码。修复与否由用户决策。
