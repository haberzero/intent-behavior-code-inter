# _REAL_LLM_TRIAL_REPORT_20260812 — 真实 LLM 全面压力试用重启报告（修复后代码）

> 2026-08-12。**重启** 2026-08-11 被中断的真实 LLM 全面试用，基于**修复后代码**（U1-U7 /
> 意图纠错 7339220 / T1-T5 / PT-AUDIT-3 / dispatch 观测 d6d28e1 / run_batch 观测 df1a896）。
> 本报告 = 完整语法全面试用（D1）+ 交叉/正交/多层次/多可能性/多文件压力试用（D2）+
> 批判检测（D3，含 C1-C4）的**全量结果**，替代旧报告 `_REAL_LLM_E2E_REPORT.md` §四/§五 的
> 修复前结论。**本任务是试用与记录任务，缺陷只记录不修复**。
> 完整证据：`tasks_docs/_LLM_TRIAL_20260812/REGISTER.md` + `logs/` + `cases/`。

## 一、执行环境与保护机制

| 项 | 值 |
|----|-----|
| LLM 端点 | `http://localhost:1234/v1`（LM Studio，qwen3.6-35b-a3b 非思考模型） |
| 配置 | 引擎自动加载 `api_config.json`（providers/models/defaults，reasoning:false，timeout=30，retry=3） |
| 保护 | **三层死循环保护强制**：OS 进程级硬超时（SIGKILL 进程组）+ `--max-inst` + LLM 调用级超时；harness 无超时不运行 |
| 记录 | 确定性文件化：`logs/<case>.log` + `logs/register.jsonl` + `REGISTER.md` |
| 运行数 | 104 个 cases 文件 / 113 次 harness 运行（含冒烟/死循环保护验证）；全经保护 |
| 全量 pytest | **2210 passed / 1 skipped**（试用零回归，未改内核） |

## 二、D1 全语法遍历结果（docs/syntax/01-15 每章真实 LLM）

| 章 | 特性域 | 结果 | 备注 |
|----|--------|------|------|
| 01 类型 | 基础/泛型/Optional/转换/None/any | ✅ 全 PASS | |
| 02 变量 | auto/裸赋值/元组解包/global/nonlocal/内建遮蔽 | ⚠ 部分缺陷 | **global 失效（KERNEL-ISSUE-001）**；A2 遮蔽重验 PASS |
| 03 运算符 | 算术/位/比较/逻辑/成员/身份/三元 | ✅ 全 PASS | |
| 04 控制流 | if/while/for/switch/异常/pass | ✅ 全 PASS | 自定义异常+类型窄化 PASS |
| 05 函数 | 默认值/*args/splat/递归/嵌套/fn 签名/内省 | ✅ 全 PASS | callable 内省 type(f)/__return_type__ 正确 |
| 05 生成器 | yield/yield from/to_list/next | ✅ 全 PASS | A3 重验 PASS |
| 06 OOP | 类/继承/super/Enum/协议方法 | ✅ 全 PASS | Enum+LLM 输出解析 PASS |
| 07 行为表达式 | 即时/类型约束/布尔上下文/lambda/snapshot/run_batch/命名路由 | ✅ 全 PASS | A1/A5 重验 PASS |
| 08 LLM 函数 | llm...llmend/__llmretry__ | ✅ 全 PASS | |
| 09 意图 | @/@!/@+/intent_context | ✅ 全 PASS | A1 赋值路径实证（r1=收到） |
| 10 健壮性 | llmexcept/llmretry/快照隔离 | ✅ 全 PASS | 编译期拦截 SEM_LLMEXCEPT_* 生效 |
| 11 模块 | import/ai/isys/idbg/ihost/file/json/插件 | ⚠ 部分缺陷 | **整模块 import 崩溃（KERNEL-ISSUE-002）**；B1 隔离 PASS |
| 12 内建 | 转换/序列辅助/方法/遮蔽 | ✅ 全 PASS | A2 相关 PASS |
| 13 MOCK | 未启用时真实行为 | ✅ PASS | MOCK 需显式启用（文档一致） |
| 14 并发 | chan/slot/subscriber/thread/await | ✅ 全 PASS | await thread→thread_result 正确 |
| 15 诊断 | 诊断码说明/修复 | ✅ PASS | catalog 集成生效 |

## 三、A1-A5 重验点（修复后代码真实 LLM）

| # | 重验点 | 结果 | 证据 |
|---|--------|------|------|
| A1 | 意图 @/@! 赋值路径真实效果（7339220） | ✅ **实证进入 prompt**：`@ 冷酷极简`→r1=收到；`@!`→b1=True；`@+`→a1/a2 短、@- 后 a3 长 | D1-09-001, D3-40 |
| A2 | 内建遮蔽 + LLM 表达式初始化（f58d525） | ✅ `int sum = @~3+4~`→7；`int len=5` 遮蔽生效 | D1-02-006 |
| A3 | generator.to_list() 显式调用（U1） | ✅ to_list_len=4 / generic_next / type(generator) | D1-05-008b |
| A4 | dispatch 赋值后 idbg 观测（d6d28e1） | ✅ 赋值后立即可查 info_keys=[sys_prompt,user_prompt,response,...] | D1-11-001 |
| A5 | run_batch 批路径观测（df1a896） | ✅ batch_len=3 + call_info 完整 | D1-07-005, D3-C4 |

**B 类补正式记录**：B1 ihost 隔离（D1-11-005/D2-50，child 需自带 api_config.json →
BOUNDARY-003）；B2 内建（D1-12-001，纯确定性 PASS）；B3 异常（D1-04-002，try/except/raise 真实路径 PASS）。

## 四、D2 压力试用结果（交叉/正交/多层次/多可能性/多文件）

| 维度 | 用例 | 结果 |
|------|------|------|
| 交叉 | 生成器+意图+llmexcept（D2-01）、thread+chan+run_batch（D2-02）、类+LLM+slot（D2-03）、闭包+生成器+LLM（D2-60）、LLM 函数三级链（D2-61） | ✅ 全 PASS |
| 正交 | @+持久+run_batch（D2-80）、双批并发（D2-81）、snapshot vs lambda 意图（D2-40） | ✅ 全 PASS |
| 多层次 | 高阶 lambda 调用点意图（D2-41）、循环体 LLM+llmexcept（D2-70） | ✅ 全 PASS |
| 多可能性 | 边界值/除零/空输入（D2-10）、类型名/内建遮蔽拒绝（D2-11/12）、str'0'真值（D2-71） | ✅ 全 PASS（符合文档） |
| 多文件 | 循环导入 DEP_CIRCULAR_IMPORT（D2-20）、插件（D2-21）、隔离子项目+LLM（D2-50）、子类 auto-init（D2-30） | ⚠ 隔离需自带配置（BOUNDARY-003） |

## 五、D3 批判检测结果（C1-C4 + 对抗场景）

| 场景 | 结果 | 备注 |
|------|------|------|
| 格式服从（-> int/bool/float/list） | ✅ 稳定 | D1-07-002，多次一致 |
| C1 长提示/复杂 __to_prompt__ | ✅ 注入完整 | PROMPT_CONTAINS_TITLE/SECTION=True |
| C2 非确定性多次差异 | ✅ 稳定 | t=1/1/1 b=True/True |
| C3 超时/断连 | ⚠ **KERNEL-ISSUE-003** | LLMCallError 逃逸 try/except（P1） |
| C4 并发扩展 | ✅ 无竞态 | 8 路 batch + 4 线程（D3-C4）、双批（D2-81） |
| llmexcept 收敛 | ✅ 真实收敛 | retry hint 引导模型返回可解析值 |
| 重试耗尽 | ✅ LLMRetryExhaustedError + max_retry | D3-22（MOCK 确定性） |
| 意图注入 | ✅ 真实生效 | A1 实证 + 全局意图（D3-30） |

## 六、暴露问题清单（记录，不修复）

**KERNEL_ISSUE（真实缺陷候选，4 项）**：

| # | 标题 | 级别 | 复现 |
|---|------|------|------|
| 001 | `global` 写访问函数内 `RUN_UNDEFINED_VARIABLE` | P1 | D1-02-003b |
| 002 | 整模块 `import mod`+成员访问 → `INT_INTERNAL_ERROR` | P1 | D1-11-002d/e |
| 003 | 真实 LLM provider 失败 `LLMCallError` 逃逸 `try/except` | P1 | D3-C3/d/e |
| 004 | `ai.get_retry()`/`is_auto_intent_injection_enabled()` vtable 未注册 | P1 | D3-50/51 |

**DOC_ISSUE（7 项）**：001 02_variables 示例缺返回标注 / 002 9 处 `__init__` 缺返回标注 /
003 14.6 await thread 示例矛盾 / 004 stream_call 签名缺失 / 005 howto thread_result `.value` /
006 SEM_INTENT_STATIC_CALL 警告未现 / 007 __from_prompt__ 契约未注明。
**BOUNDARY（5 项）**：001 for=to_list 物化 / 002 生成器 await chan 未复现 KNOWN_LIMITS §二十四 /
003 隔离子环境不继承 LLM 配置 / 004 @! 在 run_batch 仅首调用生效 / 005 probe_model 误判推理模型。

> 全部缺陷已登记 PENDING_TASKS（PT-DEBT-25~28 + DOC/BOUNDARY 清单），**本任务不修复**。

## 七、合并条件重估（基于修复后代码）

| 合并条件（`_MAIN_MERGE_PLAN.md` §一） | 状态 |
|------|------|
| 真实 LLM 检测通过（无 P0 阻断缺陷） | ✅ **全语法遍历 + 交叉/多文件压力 + 批判检测全部跑通**；无 P0；4 项 P1 KERNEL_ISSUE 均**不阻断正常功能主路径**（global 语句 / 整模块 import / provider 失败捕获 / 2 个 ai 内省 API），且不触发崩溃死循环。**A1-A5 全部重验通过** |
| 全量 pytest 零回归 | ✅ **2210 passed / 1 skipped**（试用全程未改内核） |
| 文档/README 就绪 | ✅（沿用 `_MERGE_READY_REPORT.md` 结论） |
| 用户显式授权 push/合并 | ⏳ **未授予**（禁 push 硬原则；阶段 3 合并动作须用户显式授权） |

**结论**：合并的"检测维度"已基于修复后代码完整确认（12 类遍历 + 交叉/正交/多层次/多文件 +
批判检测 C1-C4 + A1-A5 重验）。**建议**：4 项 P1 KERNEL_ISSUE 属独立窗口修复项（PT-DEBT-25~28），
按惯例登记待独立窗口，不构成合并硬阻断；是否阻断由用户权衡。**合并/推行动作仍须用户显式授权**。

## 八、遗留与建议

- **PT-DEBT-25~28**（KERNEL_ISSUE 001-004）：独立窗口按 code-workflow 根因修复，修复时补测试。
- **DOC-ISSUE-001~007**：文档同步，多数是示例/契约缺标注，低风险，可随文档治理窗口批量处置。
- **BOUNDARY-001~005**：与文档语义核对后决定是文档修订还是保留记录。
- **KNOWN_LIMITS §二十四** 描述或已过时（生成器 await chan 实测可用），待内核复核。
