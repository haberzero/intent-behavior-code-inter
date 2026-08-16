# NEXT_STEPS — 当前最紧要项

> 本文件**只**记录当前最紧要、可立即开工的下一步；长期规划见 `tasks_docs/PENDING_TASKS.md`。
> 历史完成条目从本文件移除（git 承载）；任务控制治理见 `tasks_docs/GOVERNANCE.md`。

---

## 🔴 当前主线

**内核协议化收尾与双轨收敛（体系化重构）——阶段 A-D 已完成，理论问题清理完毕。**

| 阶段 | 状态 | 内容 | 验证 |
|------|------|------|------|
| A OOP 侧协议化 | ✅ 完成 | receive dunder 协议注册表化（20 处硬编码归零）、attribute 协议、op_constants 一致性 | 全量 3006/1 + 复核 P1/P2 闭环 + LLM 复跑一致 |
| B 双轨收敛 | ✅ 完成 | self 形态统一 / 特化身份结构化 / 成员单一权威 / auto-init 声明化 / F3 预评估诊断 | 同上（B2 独立分支+复核放行） |
| C 公理声明+判定链双协议化 | ✅ 完成 | 协议条目判定声明数据驱动 satisfies、消费端收敛 | 复核 317 项对拍 0 差异 + LLM 复跑一致 |
| D KNOWN_LIMITS 26 节处置 | ✅ 完成 | 归类终判、独立专项登记（PT-DEBT-29/30/31）、候选处置 | 26 节全部有明确归属 |
| E 宣发前置 | ⏳ **待用户确认范围** | E1 运行期基准 / E2 调试器·包管理 / E3 文档旅程补齐 / E4 版本评估 | 准备性评估已登记（PENDING_TASKS VISION-2） |

**下一步候选**（等待用户指示，按序）：
1. 阶段 E 实施（需确认范围）；
2. 独立专项窗口（PT-DEBT-29/30/31、PT-DECIDE-2/3、PT-DEBT-4/5）；
3. 真实 LLM 压力试用扩展（VISION-3）；
4. 文档体系持续治理（按 `docs/WRITING_GUIDE.md` + `tasks_docs/GOVERNANCE.md`）。

---

## ✅ 最近完成

- **2026-08-16 文档体系系统化重构与正规化（四大任务完成）**：① docs/ 全量审计
  （5 并行 general agent，43 文件）+ 重构——红线清理（日期戳/任务编号/历史叙述/
  自治豁免/断链）、内容漂移修正（跟随阶段 A-D 代码事实：协议化体系归属 03 §4.0、
  receive 分派/self 形态/特化身份/member_types 派生/satisfies 数据驱动/auto-init
  声明化/预评估诊断码/copy·deepcopy 内建/chan 签名/运算符重载/全局意图/快照警告）、
  章节排布与编号统一、LANGUAGE_DESIGN_EVOLUTION 恢复保留（审计复核：正文为有
  价值规划内容，降格为演进评估参考、删红线附录与自治豁免定位、重新登记 README
  目录树与单点真理表）；② tasks_docs 正规化
  （GOVERNANCE 治理章程 + PENDING_TASKS 八股化 + NEXT_STEPS/WORKLOG/HANDOFF 清洗
  + 临时文档删除）；③ KNOWN_LIMITS 体系化（26 节真实性查验 + 类型标注 + 条目
  结构说明）；④ 根目录清洁（auto/example_api.json 删除）。全量 3006/1 零回归。
  详见 WORKLOG。
- **2026-08-16 内核协议化收尾与双轨收敛（阶段 A-D + 独立候选）**：OOP 协议化 /
  双轨收敛 / 判定链协议化 / 边界处置 / copy·deepcopy 内建落地。全量 3006 passed /
  1 skipped 零回归；每阶段独立复核（general agent）放行 + 真实 LLM 复跑
  （T09 8/8 + T01 54/57）与基线逐类一致。
