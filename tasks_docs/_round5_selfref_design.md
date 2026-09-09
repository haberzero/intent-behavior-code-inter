# _round5_selfref_design — Phase C 自指性架构一等化（`self` 模块）系统级设计

> 设计阶段临时文档（落地后删除，收敛 docs/）。权威需求源 =
> `/home/dsh/proj/ibci-trial/docs/ibci_round5_selfref_requirements.md`（SR-1..5）+
> round4（SELF/OBS/COST）。实证参考 = 试用方 e50/e51/e52（自描述 + 显式生成器 PoC）。
> 本设计对照：design-philosophy（单一权威/机制同构/协议驱动）+ 9 项 VM 不变量 +
> 工作模式定论九条 + self-grill。

---

## 0. 核心认识（为何这样设计）

**自指性体系架构**（横切原则）：可靠性与自指性来自**确定性代码/架构**，非 LLM 智力。
- LLM = 低阈值基础细胞（仅语义选择/分类/草稿/先验，**不产结构/不写 ibci/不做判定**）
- 架构 = 确定性计算机（结构 + 记忆 + **显式代码生成器** + 验证 + 观测 + 成本）

试用方实证轨迹（教训）：
- e49：LLM 写 ibci → 3/3 语法伪迹（**失败**：依赖 LLM 知 ibci）
- e50/e51：LLM 低阈值语义选择 + 架构确定性组装 → 无伪迹 + 自修改 Δ>0（**修正**）
- e52：把 ad-hoc `assemble_*` 提升为**可复用生成器**（多模板 + 共同验证门），
  证明对多种行为通用（**SR-2 成立**）

**关键洞察**：e50 的"自描述"是硬编码字符串（SR-1 明确要消除）；e52 的生成器是 ad-hoc
函数（SR-2 要一等化）。本设计把这两者提升为 IBCI **一等组件**——一个统一的 `self`
模块承载整个自指性架构。

---

## 1. 架构总览：`selfref` 模块（core-level plugin）

> **命名裁定**：模块名 = `selfref`（非 `self`）——IBCI 类方法首参即 `self`
> （`func m(self, ...)`），模块名 `self` 会与该方法参数概念冲突（混淆命名，code-odor）。
> `selfref` 对齐 round5 需求 ID（SR = SELF-REF），无歧义。用法 = `import selfref` 后
> `selfref.describe()` 等。

**单一权威**：自指性架构的所有原语集中在一个 `selfref` 模块（同 `meta`/`idbg` 的
core-level plugin 形态），非散落各处。机制同构：
- 模板注册/查询 → 协议驱动（同 knowledge/memory 的注册表模式）
- 组装/验证 → 确定性（零 LLM，D1 铁律）
- 自修改 → 经验证门 + 回滚（同 memory 的 append-only 审计）

`self` 模块方法面（按 SR 组织）：

| 方法 | SR | 语义 |
|------|----|----|
| `self.describe()` | SR-1 | **真内省**：从系统实际结构组装结构化自描述值（非硬编码字符串） |
| `self.constitution()` | SR-3 | 系统宪法（不变量集，结构化——自修改的边界） |
| `self.register_template(name, body)` | SR-2 | 注册行为模板（代码模板 + 参数位） |
| `self.templates()` | SR-2 | 已注册模板名列表（供 describe 内省） |
| `self.render(name, params)` | SR-2 | 确定性组装：模板 + 语义参数 → 合法 ibci 源串 |
| `self.verify(code, test_call, expected)` | SR-3 | 验证门：编译 + 执行 + 结果校验（三关，非仅编译） |
| `self.modify(name, params, test_call, expected)` | SR-3 | 自修改：render → verify → 采纳/拒绝（确定性，含审计） |

**LLM 边界（SR-5）**：`self` 模块**零 LLM**（组装/验证/判定全确定性）。LLM 仅在
*调用方*提供低阈值语义参数（如 e50 选标记词），参数经 `render` 进入确定性组装。
`self` 不直接调 LLM——这是 SR-5 的结构性保证。

---

## 2. SR-1 自描述（真内省，非硬编码）

**设计**：`self.describe() -> dict` 从系统**实际结构**组装自描述（每次查询实时内省）：

```
{
  "modules": [...],        # 已注册 builtin 模块（经 registry 内省——真，非硬编码）
  "constitution": [...],   # 系统不变量集（结构化——自修改边界，递归含"我如何被修改"）
  "templates": [...],      # 已注册行为模板名（经 self 模板注册表内省）
  "memory": {...},         # 若绑定了 memory（经 memory.snapshot()）——可选
}
```

**递归性**：`describe` 含 `constitution`（不变量）——即"我的修改规则"。系统能描述
"我有哪些行为模板 + 我受哪些不变量约束 + 我可如何被修改"。

**实现要点**：
- `modules`：经 KernelRegistry 内省已注册模块（真 introspection，非字符串）
- `constitution`：`self` 模块持有的结构化不变量集（见 §4）
- `templates`：`self` 模块的模板注册表
- `memory`：调用方可传入 memory 实例（`self.describe(memory=mem)`）→ 纳入 snapshot

> **与 e50 的区别**：e50 的 self_desc 是硬编码字符串；本设计的 describe 是**查询
> 实际结构**（模块/不变量/模板）组装的 dict——满足 SR-1"一等 introspection 原语
> （非硬编码字符串）"。

---

## 3. SR-2 显式生成器（一等组件）

**设计**：模板注册 + 确定性组装 + 验证门（对齐 §十一"显式 IBCI 生成器"）。

- **模板** = 代码骨架 + 参数占位（如 `assemble_classify` 的标记词列表位）。
  `register_template(name, body)`：body = 含参数占位的 ibci 代码模板串。
- **确定性组装** `render(name, params)`：把 params 填充进模板 → 合法 ibci 源串。
  纯确定性（字符串组装 + 结构保证），LLM 只提供 params（低阈值语义值）。
- **参数来源**：LLM 阈值任务（调用方负责，如选标记词）→ 解析为 params → render。

**合法性保证**（e49 教训的架构解）：模板由**架构作者**编写（合法 ibci 骨架），
参数是**值**（非代码），填充后仍是合法 ibci——LLM 永不直接产码，故无 e49 伪迹。

**与 e52 的区别**：e52 的模板是 ad-hoc 函数（`assemble_classify` 硬编码在脚本）；
本设计的模板是**注册的一等值**（`register_template`），可被 describe 内省、被
modify 复用、可序列化——生成器从脚本内 ad-hoc → 系统一等组件。

---

## 4. SR-3 自指性自修改安全

**设计**：宪法不变量 + 确定性验证门（编译+执行+结果）+ 自修改由自描述规则驱动 + 回滚。

- **宪法（constitution）**：`self` 模块持有的结构化不变量集（系统可被修改的边界）。
  如："自修改须经 verify 三关通过"、"修改对象须是已注册模板"、"不变量本身受保护
  （不可被 modify 修改）"。宪法是**自修改的元规则**——系统自描述自己"应如何被修改"
  （SR-1 递归性的落点）。
- **验证门 `verify(code, test_call, expected)`**：三关（对齐 e52 的 `verify`）：
  1. 形式/编译：`meta.compile(code)` 成功（+ 可检查结构摘要）
  2. 执行：`ihost.run_code(code + test_call)` 成功（exit_status=ok）
  3. 结果：stdout 含 expected（**非仅编译**——e49 证明仅编译不足）
- **自修改 `modify(name, params, test_call, expected)`**：
  render(name, params) → verify(...) → 通过则采纳（更新模板/记录审计）/ 拒绝（不变）。
  全确定性，审计 append-only（同 memory 模式）。
- **回滚**：经 memory 快照（MEM-5）——自修改前快照，失败/需回滚时恢复。

**不变量保护**：constitution 本身不可被 `modify` 修改（元层保护）——防止系统修改
自己的修改规则（自指的边界；元层自修改是更进一步的待推进项）。

---

## 5. SR-5 LLM 阈值纪律

**设计**：LLM 边界形式化为可核查原则。
- **结构性保证**：`self` 模块零 LLM（组装/验证/判定路径不含 LLM 调用）——SR-5 的
  核心是"结构/判定路径零 LLM"，本设计以模块边界保证（`self` 不 import 不调 llm）。
- **调用方纪律**：LLM 仅产低阈值语义值（params），经 render 进入确定性组装。
  未来可加 `self` 面的 role 注解（semantic/content/prior）静态检查——C4 深化。

---

## 6. SR-4 行为值直接执行（Phase D）

当前经 `ihost.run_code`（源串）执行。SR-4 要 `meta.compile` 产物（行为值）直接可执行
+ 可组合。归 Phase D（依赖 SR-3 验证门 + 行为值一等化）。本设计预留接口。

---

## 7. 批次规划（Phase C）

- **C1（本轮）**：`self` 模块地基 + SR-1 自描述 + SR-2 模板注册/组装 + constitution
  结构。落地：plugin + spec + 注册 + 判别测试。这是 SR-1..5 的承载基座。
- **C2**：SR-2 生成器完整化（render 参数化 + 多模板）+ SR-3 verify 三关门。
- **C3**：SR-3 modify（自修改 + 审计 + 回滚经 memory 快照）+ 不变量保护。
- **C4**：SR-5 LLM 阈值纪律（role 注解 + 静态检查）。
- **C5**：OBS 深化（自修改审计/召回决策审计面）。
- 每批：全量 pytest 零回归 + commit + 文档同步。

---

## 8. 硬约束对照

- **9 VM 不变量**：`self` 经统一执行入口（plugin 协议）；自修改经 ihost（#4 LLM 通道
  唯一 + #8 阻塞即挂起由 ihost 子进程承载）；组装/验证零 LLM（D1）。
- **工作模式定论**：协议驱动（receive/vtable，非 if 能力位）；非 tricky（模板是结构
  化的，参数是值）；非胶水（self 是独立核心模块，非跨子系统字符串拼接）。
- **design-philosophy**：单一权威（自指性架构集中 self 模块）；机制同构（模板注册同
  knowledge、审计同 memory、验证同 meta）；命名统一（self.describe/register_template/
  render/verify/modify 动词式）。

## 9. 开放问题裁定

- **Q1：self 是 core-level plugin 还是用户模块？** 裁 = core-level plugin（同 meta/
  idbg）——自描述/宪法是系统级能力，非用户可随意注册的扩展。
- **Q2：constitution 内容初版？** 裁 = 最小集（自修改边界不变量：须 verify 三关 /
  对象须已注册模板 / constitution 自身不可 modify）。后续 C3 扩展。
- **Q3：describe 是否含 memory？** 裁 = 可选（`self.describe(memory=mem)`）——memory
  是调用方持有的一等值，self 不隐式持有（保持自包含 + 无隐式全局状态）。
- **Q4：模板 body 参数占位语法？** 裁 = 初版用显式占位（如 `{markers}`）+ render 做
  受控替换（fail-fast：未注册模板/未定义占位 → 报错，非静默）。避免 tricky 字符串魔法。
