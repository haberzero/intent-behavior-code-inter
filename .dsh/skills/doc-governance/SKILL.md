---
name: doc-governance
description: Use ONLY when the user asks to audit, govern, check, or improve the IBCI documentation system for compliance with docs/WRITING_GUIDE.md. Covers an 8-phase workflow from initial self-review of the writing guide through full-system parallel audit, phased execution, cross-verification, reader-perspective evaluation, and system building. Triggers on "check the docs", "document governance", "文档治理", "文档检查", "文档体系改进", "写作指导合规", "doc audit".
---

# 文档治理工作流

> 规范 AI 智能体执行文档审计、格式治理、内容补充或体系建设的流程。治理的"尺子"是项目书写规范（`docs/WRITING_GUIDE.md`）；本 skill 只提供"如何系统化地用这把尺子"的流程，不重述尺子内容。

## 一、流程总览

```
Phase 0 理解上下文 -> Phase 1 规范自审 -> Phase 2 全量健康检查（并行 subagent）
-> Phase 3 汇总与规划 -> Phase 4 分阶段执行 -> Phase 5 交叉核验
-> Phase 6 读者视角评估 -> Phase 7 体系建设 -> Phase 8 最终复查与清理
```

## 二、各阶段

### Phase 0: 理解上下文
读 `AGENTS.md`（治理纪律）、项目书写规范（`docs/WRITING_GUIDE.md`）、文档导航（`docs/README.md`）。确认治理域（哪些文件受检）与规则集（书写规范）。若无书写规范，先与用户确认是否建立--治理需要尺子。

**读者定位红线（强制）**：`docs/` 定位为**人类手册**（指导手册 / 技术手册 / 参考手册），**绝对不允许存在任何关于本工作智能体相关的元信息**（工作流 / 过程 / agent 指令 / skill 引用 / DSH 配置）。此类信息只应存在于 `AGENTS.md` 与 `.dsh/skills/` 工作流层。治理 `docs/` 时发现任何此类信息一律**移除**（不改写为人类可读表述——从原则上它就不应存在）。

### Phase 1: 规范自审
把书写规范的每条规则应用到规范自身，检查自洽性（文件身份、定位段、红线禁令、示例配对、主动语态）。输出规范自身合规报告 + 改进建议。

### Phase 2: 全量健康检查（并行 subagent）
**禁止抽检，必须全覆盖。** 按目录拆分，每个 subagent 用同一套检查标准（从书写规范提取，不自行发挥）。额外一个 subagent 做体系结构分析（四分法覆盖、概念归属唯一、读者旅程、跨文件一致性）。输出结构化违规报告：文件路径 / 违规文本 / 违反规则编号 / 严重级别。

### Phase 3: 汇总与规划
合并去重，分三优先级：P0 立即修复（断链、事实矛盾、缺失核心结构）/ P1 本阶段（红线违规、格式不一致、跨层泄漏）/ P2 后续（超长拆分、模块补齐）。区分"格式问题"（可机械修复）与"结构问题"（需判断）。创建临时任务文档 `tasks_docs/_<task>.md` 追踪。事实矛盾以源代码为最高真相。

### Phase 4: 分阶段执行
从最高优先级逐项修复，扎实推进不跳过。修断链用实际路径；修矛盾以代码事实为准；补缺失元素遵守书写规范格式。大批量修改用 subagent 并行。

### Phase 5: 交叉核验与遗漏修复
**最关键阶段，跳过即治理失败。** 重新通读规范全文（不凭记忆）。逐一对照原始报告验证每条是否已修复。用 grep 扫描残留违规模式--扫描 pattern 从书写规范红线派生，不写死项目专属 token。在"已修复"与"扫描结果"间做差距分析，每条遗漏须有理由（豁免或补修）。重复直至扫描干净。

### Phase 6: 读者视角评估
脱离作者视角：30 秒读者能否从定位段获益？带问题的读者 5 分钟能否找到答案？文档间是否有合理阅读路径？以技术写作者视角评估体系：四分法是否完整、是否按读者旅程组织、跨文档信任度。给出分级改进建议。

### Phase 7: 体系建设与补充
对体系缺口提建设方案（缺 Tutorial 层则建分步教程等）。新建内容须遵守与已有内容相同的书写规范。教程设计：每章"你将会学到"开头、"你现在能做什么"结尾，顺序推进，最小示例，完整规范引用 Reference 层。配套修改索引与导航。

### Phase 8: 最终复查与清理
重读所有新建/修改文件（不只扫标题）。验证导航链闭环、格式一致、引用有效。确认临时任务文档全部勾选。向用户汇报治理结果。经用户确认后删除临时任务文档（过程产物，状态由 git 承载）。同步更新配套索引（如 `AGENTS.md`）。

## 三、关键模式

- **并行 subagent 审计**：按目录拆分 + 统一检查标准 + 统一输出格式 + 一个跨文件体系分析 subagent。
- **自动化扫描**：Phase 5 用 grep 快速发现遗漏，pattern 从书写规范红线派生，排除治理范围外目录与规范文档自身示例。
- **读者-作者双视角**：先作者视角（规则驱动）后读者视角（体验驱动），互补。
- **事实矛盾裁决**：源代码 > 测试 > 设计文档 > 标记"待验证"不擅改。
- **临时任务文档**：`tasks_docs/_<task>.md`，下划线前缀，Phase 8 经确认后必须删除，禁止长期留存。
