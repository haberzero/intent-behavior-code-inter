# _LLM_TRIAL_20260812 — 真实 LLM 全面压力试用设计（重启版）

> 2026-08-12。本任务 = **试用与记录任务，不是修复任务**。目标：完整语法的全面试用 + 对 IBCI
> 语言/功能各层面的交叉、正交、多层次、多可能性、多文件压力试用（略带挑刺/略带恶意地试探边界
> 与可能存在 bug 的思路），尽可能全面暴露现阶段内核功能的边界与隐性问题，确认语法可用性 /
> 功能边界 / 内核能力边界。**发现的缺陷只记录、登记，不在本任务修复。**

## 一、工作模式与硬约束（用户 2026-08-12 定案）

| 约束 | 内容 |
|------|------|
| 死循环保护 | **所有试用例必须经 OS 进程级硬超时（SIGKILL 进程组）+ IBCI 指令上限（--max-inst）+ LLM 调用级超时（config）三层兜底**；任何试用不得绕过；harness 无超时不运行（强制参数） |
| 记录优先 | 优先记录问题，通过文件化确定性记录（logs/ + register.jsonl + REGISTER.md）溯源；不优先解决；**原则上禁止修改内核代码** |
| 文档为主要来源 | 按 docs/ 技术手册撰写用例；**非必要不直接探索内核代码**；手册问题（错误/过时/矛盾/缺失）记录为 DOC-ISSUE；仅当手册有误且某功能必须使用时才读内核代码确认正确用法并记录 |
| 溯源纪律 | 每例记录 = 用例脚本 + 文档引用 + 期望 vs 实际 + 退出码/时长 + 分类 + 严重级别 + 证据日志 |
| 禁 push | 全程本地 commit；禁 push（硬原则） |

## 二、三层死循环保护设计（用户强制，最坏情况检测）

1. **OS 进程级硬超时（根本手段）**：`harness/run_one.py` 用 `subprocess.Popen(start_new_session=True)`
   建立独立进程组，`communicate(timeout=...)` 超时后 `os.killpg(pid, 9)` SIGKILL 整组——
   无论死循环在 VM、线程体、生成器驱动还是 LLM 客户端 worker，都能被强制终止。
   **timeout 为必需参数**，未显式给出即拒绝运行（零遗漏）。
2. **IBCI 指令上限**：CLI `--max-inst`（默认 5e6），VM 内部第二种防护；死循环先触指令上限报错，
   进程级超时兜底。
3. **LLM 调用级超时**：`api_config.json` `defaults.timeout=30` + `retry=3`——单次 LLM 调用最坏
   120s 收敛；长 LLM 密集用例适当放大 OS 超时但始终有界。

> 冒烟验证：`cases/deadloop_probe.ibci`（`while i>=0` 无限自增）→ 8s 超时被 SIGKILL
> （exit=-9, timed_out=True, 无输出）。harness 强制参数路径已固化。

## 三、确定性记录体系

- **logs/<case_id>.log**：每次运行的完整证据（命令行、退出码、超时标志、时长、stdout+stderr 合并）。
- **logs/register.jsonl**：每例一行 JSON（case_id/script/dim/doc/expected/timeout_s/exit_code/
  timed_out/duration_s/out_head），机械字段由 harness 写入，分类字段由试用 agent 审阅后回填。
- **REGISTER.md**：人工可读总表（由 jsonl 整理），供决策与汇报。
- **PENDING_TASKS.md**：确凿缺陷登记（不修复，注明候选级别）。

## 四、分类体系（审阅后回填）

| 分类 | 含义 |
|------|------|
| PASS | 行为与文档一致（含预期报错） |
| KERNEL_ISSUE | 内核/VM/语义/运行时缺陷（真实 bug 候选） |
| DOC_ISSUE | 技术手册错误/过时/矛盾/缺失（与代码行为不符） |
| LLM_BEHAVIOR | 真实 LLM 非确定性/服从性问题，非内核缺陷 |
| LIMIT | 文档化 KNOWN_LIMITS / 设计冻结行为 |
| BOUNDARY | 边界/隐性问题，暂未定性 |
| HARNESS | harness 或环境问题 |

严重级别：P0（崩溃/死循环/数据损坏）/ P1（明确缺陷，重要语义错误）/ P2（缺陷，较轻）/
P3（文档/体验问题）。

## 五、试用维度

- **D1 全语法遍历**：docs/syntax/01-15 每个特性一个真实 LLM 用例（含 A1-A5 重验 + B1-B3 补记录）。
- **D2 压力试用**：交叉/正交（生成器+LLM+意图+llmexcept、类+thread+chan+slot、file+json+模块、
  隔离+插件、enum+LLM、await+生成器等）、多层次（同特性不同宿主层级）、多可能性（类型错配/
  边界值/空输入/畸形提示/保留名遮蔽/循环导入/非确定性/超时断连/深嵌套/并发扩展）、多文件
  （多模块项目、sub-project、plugins、隔离子环境）。
- **D3 批判检测**：格式服从 / llmexcept 收敛 / 意图注入实证(A1) / 长提示复杂 `__to_prompt__`(C1) /
  非确定性多次差异(C2) / 超时断连(C3) / 并发扩展(C4)。

## 六、用例命名约定

`cases/<D|dim>-<chapter/feature>-<nnn>.ibci`；每文件头部注释含：用途、文档引用、预期行为。

## 七、执行流程

1. 读全技术手册 → 构建 D1 用例矩阵（记录文档疑点）。
2. D1 遍历（每例真实 LLM 跑一遍，harness 保护，审阅回填分类）。
3. D2 压力试用（组合/恶意用例，含多文件项目）。
4. D3 批判检测（C1-C4 + 对抗场景）。
5. REGISTER 汇总 + 缺陷登记 PENDING_TASKS（不修复）。
6. 刷新 `_REAL_LLM_E2E_REPORT.md` §四/§五/§七 + NEXT_STEPS/WORKLOG 同步 + 本地 commit。

## 八、本任务不做的（明确边界）

- 不修复任何内核缺陷（只记录/登记）。
- 不进行破坏性重构、不合并、不 push。
- 不把临时探针脚本或日志误当交付物（logs/ 与 cases/ 归本 trial 目录）。
