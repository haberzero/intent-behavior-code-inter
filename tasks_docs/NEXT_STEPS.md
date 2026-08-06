# NEXT_STEPS - 当前最紧要项

> 本文件**只**记录当前最紧要、可立即开工的下一步；长期规划见 `tasks_docs/PENDING_TASKS.md`。
>
> **最后更新**：2026-08-05（任务控制文档全面重整，任务代号按性质分域）

---

## 🔴 下一阶段主线：PT-INTRO-1 运行时内省体系剩余

> `type(x)` 内建已落地（返回 `ib_class.name` 规范类型名）。下一阶段完成剩余两项：
>
> 1. **fn/behavior 签名形态**：`type(f)` 对 fn_callable/behavior 返回含签名类型名
>    （如 `fn_callable[()->int]`）——需内省 `type_ref` 的 params + return。
> 2. **返回类型查询 API**：草案 `f.__return_type__()`（独立签名查询形态）。
>
> 完整设计要点见 `PENDING_TASKS.md` §一。约束：每批全量 `python -m pytest tests/` 零回归；
> commit 留痕（仅本地，禁 push）；设计先写 `tasks_docs/`，落地后收敛进 `docs/`。

---

## 📋 交接要点（下一 session）

- **主线**：PT-INTRO-1 剩余（见上）。
- **待讨论**：PT-DECIDE-1（LLM 解析默认策略语义，原 B-D2）——下一 session 待讨论项，仅记录。
- **待选**：PT-DEBT-1/2/3（内核接口协议化，原 C-D3/C-D7/B-D10）——同性质可合并实施。
- **长期周期**：PT-AUDIT-1/2（代码异味 / 分支嵌套审计）——时不时启动，独立分支执行。
- **保留规划**：PT-TEST-1（测试体系重构，未来做）、PT-FEAT-1（语言级协程，保持现状）。
- 完整清单见 `PENDING_TASKS.md`。

---

## ✅ 已完成：本 session 交付（2026-08-05，会话 17）

> 全部落地 unsafe-vibe-dev（本地 commit，未 push）。commit 明细见 git 历史。

- **PT-ARCH-31 序列化档位 A+B**：闭包序列化 + fn_callable round-trip 修复（作用域 cell 重建 +
  post-pass 按 sym_uid 重链；value_meta/expected_type JSON 安全）。
- **PT-ARCH-32 Axiom 家族分裂**：IntentAxiom/IntentContextAxiom 并入 BaseAxiom。
- **PT-ARCH-33 EnumAxiom 双通道**：收敛 str 契约 + fail-fast。
- **PT-ARCH-34 use_intent_context**：删恒真守卫 + 可读错误。
- **PT-SMELL-R3 四 Zone 处置**：修 19 + 复核定案保留 10 + 设计确认保留 6。
- **B-D6 根治重构**：import-* 精确成员枚举（编译器记录 + 运行时枚举）+ **IBC 文件跨模块导入
  三层断裂修复**（TypeDef 别名 NameError / Lazy 描述符 members 恒空 / IbModule.get_variable）。
- **PT-INTRO-1 type() 落地**：`type(x)` 内建。
- **任务控制文档全面重整**：任务代号按性质分域（FEAT/DEBT/REV/DOC/TEST/AUDIT/DECIDE/SEALED），
  删除已完成/无价值条目与无用设计决策，清理注释任务代号/历史说明。

---

## ⛔ 工作模式定论（强制，凌驾于本文件一切任务之上）

> **扎实推进，禁止任何形式的快速实现 / 兼容层 / 胶水实现 / tricky 实现。**

1. 禁止 compat shim / 兼容层：新设计就是真设计，旧代码要么真合并、要么真删除。
2. 禁止胶水实现：不在两个不统一的子系统之间塞字符串拼接 / 魔法哨兵 / 隐式约定。
3. 禁止 tricky 实现：不靠隐式字符串变换承载语义；不靠"凑巧相等"；不靠书写顺序掩盖数据依赖。
4. 禁止过程式硬编码分发：同一决策只通过协议驱动（`receive()` / vtable），不写 `if 能力标志位`。
5. 质量优先于速度：技术债必须先清；潜伏 bug 不允许过渡修复。
6. 原则优先于行为维持：既有行为违反一般工程/架构原则时，以原则为准，不以"保持已有行为"为主。
7. 可推翻 IBCI 自身设计缺陷：即使设计思路已在文档记录，也可按更普适、实践更合理的方案重建。
8. 破坏性重构授权：符合一般工程经验且经分析优于现有体系时默认已授权自主推进，详记决策。
9. 大范围破坏性重构分支政策：无法确认边界/危害程度的重构 100% 授权在独立分支实验；
   独立分支禁止直接合并到 unsafe-vibe-dev 或 main；永远不触碰 main。

---

## 当前测试基线

```bash
conda activate ibci
python -m pytest tests/
```

> 基线以实跑为准，不冻结数字。

---

## 独立并行任务

- **测试体系重构**：PT-TEST-1（`TEST_REFACTOR.md`），独立低优先级。
- **技术债审计**：PT-AUDIT-1/2（`CODE_SMELL_AUDIT.md` / `BRANCH_NESTING_AUDIT.md`），独立分支执行。
- **media Phase 4**：PT-SEALED-1，彻底封存（恢复需显式解封）。

---

## 工作规则

- 每次开新分支前，先复跑 `python -m pytest tests/`，把 pass/fail 计数写在 PR 描述里。
- 同一时刻只主推一个 P0 阶段。
- 工作模式定论优先；改动公理层或语义错误集的任务需全量 pytest 评估破坏面。
- 每阶段完成后用描述性 commit 记录，并把对应条目从本文件移除。
- 本文件不冻结具体测试通过数字。
- 重大架构决策记录在技术文档（`docs/ARCHITECTURE.md`、`docs/architecture/02_metadata_ast.md`、
  `docs/architecture/01_principles.md`），不再使用独立 ADR 文件。
