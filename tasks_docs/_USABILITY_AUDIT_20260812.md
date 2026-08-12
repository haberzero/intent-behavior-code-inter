# _USABILITY_AUDIT_20260812 — 试用易用性问题审计

> 2026-08-12。用户观察试用过程发现"`while true` 无法工作"，要求系统审查试用历史中的
> 易用性问题——重点是"因语法/功能不支持，试用不得不绕行"的场景。本文档记录所有发现
> （均已实测验证）+ 根源调查 + 修复状态。**2026-08-12 二次深入：根源追溯（git 历史）+
> 架构健康修复已落地**。

## 修复状态（2026-08-12，全量 2270 passed / 1 skipped，独立复核 PASS）

| # | 问题 | 根源 | 处置 |
|---|------|------|------|
| 1 | `true`/`false` 小写不支持 | **有意 Python 对齐**（3c6d137 把 true→True，与 Python 字面量一致） | **不推翻设计**；错误信息加"Did you mean 'True'?"引导 |
| 2 | `return @~` 文档说禁止实际通过 | **v1→v2 重构丢失**（afe9644 删 v1 code 时拦截未随迁） | **补全拦截**（visit_IbReturn 报 SEM_TYPE_MISMATCH） |
| 3 | `switch` 内 `break` 运行时报错 | IBCI switch 无 fall-through（匹配后自动跳出），break 是 C 冗余 | **消费 BREAK 为 no-op**，CONTINUE 透传 |
| 4 | KNOWN_LIMITS §十一"switch 暂不使用" | 过度保守（switch 实测完整） | **更新**为"基本可用 + 使用约束" |

详见本文档各节与 commit 61e987a。

---

## 一、重点确认：`while true`（小写）无法工作（用户发现）

**现象**：`while true:` 编译报 `SEM_UNDEFINED_SYMBOL: Undefined symbol 'true'`；
`while True:`（大写）正常工作。

**根因**：lexer（`core/compiler/lexer/core_scanner.py:60`）只把 `'True'`/`'False'`（大写）
注册为布尔字面量关键字；小写 `true`/`false` 是普通标识符 → 未定义变量错误。

**易用性伤害（高）**：
1. **与 Python 惯用写法强烈冲突**：IBCI 是 Python 风格语言，且 `not`/`and`/`or` 都是
   小写关键字（Python 风格）——唯独布尔字面量必须大写。用户几乎必然写 `while true:`。
2. **错误信息无引导**：报 `Undefined symbol 'true'`（通用未定义变量），不提示
   "布尔字面量应为 `True`/`False`"——用户不知道如何修正。
3. **死循环探针被迫绕行**：试用中死循环保护探针最初写 `while true:` 失败后，改为
   `while i >= 0:` 绕行（`cases/deadloop_probe.ibci`）。

**修复方向**（供决策）：
- 方案 A（推荐）：lexer 把 `true`/`false`（小写）也注册为布尔字面量（与 Python 兼容），
  `True`/`False` 保留。零风险，纯 lexer 增补。
- 方案 B：仅改进错误信息（`true` 未定义时 hint "布尔字面量是 True/False"）。
- 方案 C：维持现状（IBCI 明确用大写，文档已声明）——但不符合"Python 风格语言"定位。

---

## 二、发现 2：`return @~...~` 文档声称禁止但实际编译通过（运行时才爆类型错）

**现象**：`func f() -> int: return @~...~` **编译通过**，运行时按字符串 box，
`Cannot assign 'str' to 'int'`（RUN_TYPE_MISMATCH）。

**文档**：KNOWN_LIMITS §四 声称"编译器禁止此写法，报 `SEM_TYPE_MISMATCH` 错误"、
"正确用法是先赋值给有类型局部变量"。

**实际**：`_statement_visitors.py:393` `visit_IbReturn` 直接 `visit(node.value)` 访问行为
表达式，**没有任何针对 `@~` 的拦截**——文档描述的行为（编译期报错）不存在。

**易用性伤害（中）**：
- 文档让用户**绕行**（先局部变量再 return），但实际直接写也可编译——文档与实现漂移。
- 更糟：直接写时类型约束**不生效**（`-> int` 不驱动 LLM 输出解析），运行时才爆类型错，
  是"静默错误流入"的隐蔽形态。文档说的"语义清晰、无歧义"设计意图是对的，但**实现没有
  落地编译期拦截**，导致该保护形同虚设。

**修复方向**（供决策）：二选一——
- 让文档正确化（KNOWN_LIMITS §四 改为"编译通过但返回类型不驱动 LLM 解析，运行时类型错"）——
  但这是**留下静默陷阱**，不推荐。
- 落地文档声明的编译期拦截（`visit_IbReturn` 遇 `@~` 报 `SEM_TYPE_MISMATCH`）——实现设计
  意图，fail-fast。需注意与现有测试兼容（若有依赖直接 return 行为）。

---

## 三、发现 3：文档声称的"不可用"特性实际可用（文档保守过度）

以下特性 KNOWN_LIMITS 声称不可用/暂不使用，但**实测完全可用**——文档过度保守，
可能让用户不必要地绕行：

| 特性 | 文档声称 | 实测 | 易用性影响 |
|------|---------|------|-----------|
| `switch`/`case` | KNOWN_LIMITS §十一"暂不在生产代码中使用" | ✅ 正常匹配/默认/Enum 均可 | 用户被劝退绕行 if/else |
| 用户类运算符 `__eq__`/`__add__` | §十四 #2 旧版"无法重载，== 退化为身份比较" | ✅ 实测可重载（本轮已修文档） | 已修正 |
| 生成器体内 `await chan.recv()` | §二十四 旧版"报 unexpected event" | ✅ 可用（阻塞消费） | 已修正（本轮） |

**易用性伤害（低-中）**：KNOWN_LIMITS 部分条目"宁可说不可用"，误导用户绕行已可用的
特性。§十一 switch 是最典型——文档直接建议"优先 if/elif"，但 switch 实测稳定。

---

## 四、发现 4：显式类型标注的强制要求（Python 用户摩擦）

**现象**：函数/类/变量大量场景要求显式 `-> TYPE` / `-> auto`，缺失即
`SEM_MISSING_RETURN_ANNOTATION`。这是设计决策（fail-fast），但试用中反复触发：
- 9 处文档示例 `func __init__(...)` 缺返回标注（DOC-ISSUE-002，文档问题）；
- 02_variables §2.6 示例 `func increment():` 缺返回标注（DOC-ISSUE-001，文档问题）；
- 试用中所有函数都必须显式 `-> void`（连无返回值函数都要写 `-> void`）。

**易用性伤害（中）**：对 Python 用户，"无返回值函数"写 `-> void` 是额外负担（Python
不要求）。但这是**明确的设计决策**（KNOWN_LIMITS 与 05_functions §5.1），非缺陷。
文档示例的错误才是真问题（已登记 DOC-ISSUE-001/002）。

---

## 五、发现 5：`(str)x` 强制转换 vs `str(x)` 内建的并存（轻微困惑）

**现象**：186 处 `(str)x` 用于字符串拼接。两种写法都可用：
- `"count: " + str(x)` ✅（Python 风格）
- `"count: " + (str)x` ✅（强制转换语法）

**易用性伤害（低）**：并存不是缺陷（IBCI 两种都支持），但 `(Type)expr` 语法对 Python
用户陌生。文档已说明（01_types §1.4）。试用者习惯用 `(str)x`（因 IBCI 强转是特色），
非绕行。

---

## 六、发现 6：`for` 消费生成器是 to_list 急物化（文档张力，已修）

KNOWN_LIMITS §5.8 的"break 提前终止（生成器不再推进）"已修正为"for 消费 to_list
一次性物化"。这是**语义特性**（非缺陷），但文档曾误导（已修）。试用中 D2-31 曾因此
观察 GEN_FINISHED 打印。

---

## 七、发现 7：`switch` 内 `break` 运行时报错（C 语言惯用写法踩坑）

**现象**：
- `switch` 无 break：✅ 正常（匹配 case 2 后自动跳过其余 case，fall-through 拦截）
- `switch` 内写 `break`：❌ 报 `RUN_GENERIC_ERROR: Control flow statement used outside of function or loop`

**根因**：IBCI 的 `switch` 是**自动匹配后跳过**语义（无需 break），但 `break` 关键字
在 switch 内不被识别为合法控制流——VM 把它当作"函数/循环外使用"报错。

**易用性伤害（中-高）**：C/Java/Python 用户（尤其 C 系）几乎必然在 case 末尾写
`break`（C 语言惯例）。IBCI 语义上不需要 break，但写了 break 得到的是**运行时错误**
而非"被忽略"——用户会困惑"我的 switch 明明写对了为什么崩"。

**修复方向**（供决策）：
- 方案 A：`switch` 内 `break` 被识别为合法（no-op，因为 switch 本就自动跳过）——与
  C 语言习惯兼容，消除运行时报错。
- 方案 B：编译期对 switch 内 break 给出友好提示（"IBCI switch 自动匹配后跳过，无需
  break"），而非运行时错误。
- 方案 C：维持现状（文档已说"暂不使用 switch"）——不推荐，因为 switch 实测可用且
  KNOWN_LIMITS 过度保守。

---

## 八、汇总与建议

### 已实证的易用性问题（按影响排序）

| # | 问题 | 影响 | 状态 |
|---|------|------|------|
| 1 | **`true`/`false` 小写不支持**（`while true:` 失败） | 高——Python 惯用写法必然踩 | **待修（方案 A 推荐）** |
| 2 | **`return @~...~` 文档说禁止实际编译通过+运行时类型错** | 中——文档漂移 + 静默陷阱 | **待决策（落地拦截 or 改文档）** |
| 3 | **`switch` 内 `break` 运行时报错**（C 惯用写法踩坑） | 中-高——C/Python 用户必然写 break | **待修（方案 A/B 推荐）** |
| 4 | **KNOWN_LIMITS 过度保守**（switch 等实际可用被劝退） | 低-中——用户绕行可用特性 | 文档修订 |
| 5 | 显式 `-> void` 强制 | 中——设计决策非缺陷，文档示例错误才是 | 文档（已登记） |
| 6 | `(str)x` vs `str(x)` 并存 | 低——非缺陷 | 维持 |

### 建议行动
1. **方案 A（`true`/`false` 小写支持）**：最符合"Python 风格语言"定位，纯 lexer 增补，
   零风险。或至少方案 B（错误信息 hint）。
2. **`return @~...~`**：落地文档声明的编译期拦截（fail-fast），消除静默陷阱——
   这是设计意图的完整实现，非新限制。
3. **`switch` 内 break**：识别为合法 no-op（C 兼容）或编译期友好提示——消除运行时错误。
4. **KNOWN_LIMITS 过度保守条目**：核实 switch 等后放宽表述（可加"实测可用"标注）。

> 全部发现均实测验证；本文档只读，未改任何代码。修复与否由用户决策。
