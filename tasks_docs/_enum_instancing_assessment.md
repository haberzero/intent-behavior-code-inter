# _enum_instancing_assessment — 实例化枚举设计候选评估

> 2026-08-12。enum 补全（PT-FEAT-2）值模型定论后，对"实例化枚举"（成员携带 name/value/方法）
> 做可行性/爆炸半径评估，产出设计候选结论。**只评估，未改代码。**

## 一、现状（值模型，2026-08-12 全实测）

| 事实 | 证据 |
|------|------|
| `Color.RED` 返回 `default_fields[name].static_val`（底层值装箱，非实例） | ib_class.py:411 `__getattr__` |
| `Enum(value)` 构造器可创建实例（设置 `_value` 字段） | primitive_initializer.py:174-177 |
| `__eq__` 比较 `_value`（实例间/实例与值） | primitive_initializer.py:190-208 |
| 实例无 `cast_to`：`(str)Code(200)` 报 "Cannot cast 'Code' to 'str'" | 实测 |
| 成员访问不返回实例 → 自定义方法不可达（`c.is_done()` 分派到底层类型） | KNOWN_LIMITS §二 §2.4 |
| LLM 集成：`EnumAxiom.from_prompt` 返回成员值 → `registry.box` 装箱为原始值 | llm_parsing_strategy.py:126-129 |

**结论**：实例机制为**半成品**（构造器 + `__eq__` 存在，成员访问/LLM 集成/序列化均绕过实例），
与 Python 实例化枚举模型有结构差距。

## 二、实例化枚举（成员 = 枚举实例）需改动面

| 面 | 现状 | 实例化需改 | 爆炸半径 |
|----|------|-----------|---------|
| 成员访问 `Color.RED` | 返回 static_val 原始值 | 返回实例（包裹 static_val 为 `_value`） | 中——改 `IbClass.__getattr__` + 实例构造 |
| `(str)Color.RED` / `(int)Code.OK` | 原始值 cast 天然可用 | 需 Enum 基类 `cast_to`（返回 `_value` 按目标类型） | 小——新增 Enum cast_to |
| `c == Color.RED` | 原始值 `==` | 实例 `__eq__`（已存在，比较 `_value`） | 小——已具备 |
| switch/case | 原始值 `==` | 实例 `__eq__` 继承 | 小——已具备 |
| **LLM 集成 `Color c = @~...~`** | from_prompt 返回值 → box 原始值，赋给 c | **c 须为实例**：from_prompt（kernel 层）无法构造运行时实例；解析策略（通用）需按声明类型包裹枚举 | **大**——需通用 LLM 解析路径特判/类型感知包裹，侵入泛型解析 |
| 迭代 `for v in Color` | to_list 返回成员值（原始值） | to_list 返回实例列表 | 小——运行时 Enum.to_list 改包实例 |
| 序列化 round-trip | 成员值为原始值，序列化为原始值 | 枚举实例序列化（`_value` 承载） | 中——runtime_serializer 增枚举实例形态 + 兼容旧值形态 |
| 既有测试契约 | `(str)Color.RED`→"RED"、`(int)Code.OK`→"200"、`c==Color.RED`、switch | 需全部保持（cast/__eq__ 补上后可行） | 中——回归面覆盖测试需核对 |

## 三、关键矛盾：LLM 集成

- `EnumAxiom.from_prompt` 在 **kernel 层**，无法构造运行时枚举实例（kernel 禁依赖 runtime）。
- 解析策略 `llm_parsing_strategy.parse` 是**通用**路径：from_prompt 成功 → `registry.box(result)`。
  若返回原始值 → c 是原始值（非实例）；若要让 c 是实例，需解析策略按声明类型包裹枚举——
  在通用路径里特判枚举（违背"禁止过程式硬编码分发"）或引入类型感知包裹层（侵入泛型解析）。
- 结果：**LLM 赋值的枚举值与成员访问的枚举值形态不一致**是实例化的硬伤，需设计级方案
  （如从_prompt 返回值 + 运行时声明类型包裹钩子），非局部补丁可解。

## 四、收益 vs 成本

| 收益 | 成本 |
|------|------|
| 成员自定义方法可达（`c.is_done()`） | LLM 集成改造（大，侵入通用解析路径） |
| `.name`/`.value` 访问器 | 成员访问/序列化/测试契约改动（中） |
| 与 Python 枚举模型对齐 | 值模型文档（KNOWN_LIMITS §二）+ 既有行为语义反转 |

## 五、结论（自主决断，2026-08-12）

**维持现状（值模型）**，实例化枚举列为**独立设计窗口**（未来设计冻结候选），不在本批次实施：

1. **爆炸半径不确定**：LLM 集成改造为核心硬伤（kernel 层无法构造实例 + 通用解析路径需
   类型感知包裹），属"无法确认边界/危害程度"的破坏性重构——按分支政策应独立分支实验，
   且需先做设计冻结（实例语义 + LLM 包裹方案 + 序列化契约）。
2. **收益场景 niche**：枚举成员通常为数据（值比较/switch/LLM 解析），自定义方法/实例访问器
   使用频率低；当前值模型文档化清晰（KNOWN_LIMITS §二 §2.4）。
3. **半成品实例机制**（`Enum(value)`/`__eq__`）保留——它们支撑 `Enum(value)` 构造与实例比较，
   未来实例化方案可复用；不在本批次补齐 cast/成员访问（避免制造新的半成品状态）。

## 六、未来设计窗口要点（解封时核查）

1. 设计冻结：枚举实例语义（`name`/`value`/方法）、成员访问返回实例。
2. LLM 集成包裹方案：声明类型感知包裹 vs from_prompt 构造（后者需 kernel→runtime 通道，禁）。
3. 序列化契约：枚举实例 round-trip + 旧值形态兼容。
4. 既有测试契约保持（`(str)`/`==`/switch 全绿）。
5. 修改 KNOWN_LIMITS §二 §2.4（值模型边界 → 实例语义）。
