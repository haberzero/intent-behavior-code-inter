# _next_phase_targets — 阶段 E 目标汇总（真实使用暴露 + 灰盒愿景需求单）

> **定位**：下一阶段（阶段 E）主攻目标的**汇总与映射文档**（临时任务文档；条目正式化进
> `PENDING_TASKS.md` 后按治理删除，git 承载历史）。正式总条目 = `PENDING_TASKS.md` VISION-7；
> 各项开工时按 `PT-<域>-<n>` 模板注册独立条目。
>
> **两个来源**：
> ① 本机真实 LLM 试用与端点迁移工作（本 session）实证暴露的缺陷/易用性问题（§二）；
> ② 外部灰盒自动机需求单 `ref/IBCI_REQUIREMENTS.md`（本地未入库资产，用户保留）——
> "灰盒自然语言自动机全部在 ibci 内完成、**ibci 不寄生 Python**"愿景的 P0-P2 需求（§三）。

## 一、阶段性质与验收基调

- 阶段 E 是**整改 + 对齐**双线：把真实使用暴露的工程/易用性问题清干净（配置体系、脚本
  通道、harness），同时让 IBCI 向"能自己构建灰盒自动机"的语言愿景补齐关键缺口。
- ref 需求单的验收基调（其 §4）：六项 P0（C1/C2/C3/C4/B1/A3）落地后，外部灰盒自动机
  项目可在 IBCI 内开工，不再寄生 Python。

## 二、本次工作实证发现（含证据）

### T1 配置体系碎片化（架构级；单一权威源违反）

- **事实**：trial 运行时配置 `api_config.json` 共 61 份本地副本（gitignored）：43 份含
  provider 块（迁移前 base_url/model 多种值并存：`localhost:1234` / `127.0.0.1:1234` ×
  mock 真/假）、16 份仅 `defaults`；T06 用例目录配置缺 `default_model` 键（schema 面
  不一致，加载器静默容忍）。
- **实证代价**：本 session 端点迁移（旧 LM Studio :1234 → vLLM :8001）需要脚本批量改写
  43 份。单点真理是**文档**（`trials/_toolkit/LLM_SERVICE.md`），运行时真相是 43 份
  副本——**双写真相**。
- **已有基础**：配置层已支持 `{env:VAR}` 插值（fail-fast，`ibci_modules/ibci_ai/config_loader.py`），
  但**无发现/继承机制**（没有"向上查找项目根单源配置"），密钥只能逐份复制或逐份插值。
- **分类与处置方向**：架构漂移（同一概念多套真相）→ 配置**单源收敛**（发现/继承 +
  env 优先密钥通道），而不是再造一个同步脚本。

### T2 语言层无环境变量通道 + "env" 命名冲突（设计语言割裂）

- **事实**：IBCI 脚本读 OS 环境变量的唯一通道 = python 宿主绑定样板（`import python "os"`
  + `bind getenv`，每个需要机器事实的用例重复一遍）；`docs/syntax/07_behavior_expressions.md`
  曾示例裸 `env("KEY")`——内核**不存在的机制**（本 session 已修正为宿主绑定真实用法）。
- **命名冲突**：`idbg.env()` 是运行时诊断（call_stack_depth / active_intents，
  `ibci_modules/ibci_idbg/core.py`），与"环境变量"直觉冲突——同名不同物。
- **分类**：语言小缺口（机器事实/密钥读取的一等通道，含沙箱边界考量）+ 命名统一问题。
  与 ref C3（模块工程化）、D1（idbg 增强）关联。

### T3 trial harness 可用性（工具链）

- `run_one.py` 脚本路径 = root 相对拼接：绝对路径 / 仓库相对路径被错误拼接（本 session
  两次冒烟失败实证）；快跑单用例需 6 个必填参数（`--label/--dim/--doc/--expected/--timeout/--root`）。
- 端点可用性探测 = 手工 curl（`LLM_SERVICE.md` §七已列 probe 子命令为未来任务，本实证维持其有效性）。
- **分类**：易用性；低风险，可先行。

### T4 provider 配置面缺口

- `max_tokens=4096` 硬编码（`ibci_modules/ibci_ai/provider_impl.py`）；api_config 无
  per-model 参数面（现有 timeout/retry/reasoning，无生成上限/温度类声明位）。
- **分类**：配置面完整性；小。

### T5 文档示例无验证闭环

- `env("KEY")` 漂移暴露：docs 代码块没有"与内核对账"机制（诊断/语法有契约测试，
  文档示例没有）。
- **分类**：治理缺口；可评估"文档示例抽取冒烟验证"的机制可行性。

### T6 次要观察（记录备查）

- pyproject 版本提升后 editable 安装元数据滞留旧版（本 session 0.1.0 → 0.2.0 重装同步）；
  版本单源在 pyproject，安装面需手工同步——发布流程注记。
- `tests/runtime/test_set_mock_mode_switch.py` 的 api_config fixture 用任意旧端点值——
  合法（机制测试用任意值），无需处理。
- **正面实证**（机制按设计生效，保持不动）：`{env:}` 缺失 fail-fast；未注册命名路由
  报错精确；mock 显式进入；harness 超时 SIGKILL；思考抑制失败一次性告警。

## 三、ref 需求单整合映射（`ref/IBCI_REQUIREMENTS.md` A1-E2）

| ref | 需求 | IBCI 现状 / 关联 | 批次建议 |
|-----|------|------------------|----------|
| A1 | 用户自定义协议/类型类一等公民 | 内置协议族为封闭集合（dunder/契约方法）；`docs/LANGUAGE_DESIGN_EVOLUTION.md` §3.1 已规划 | 批 1（P0） |
| A2 | 泛型约束/泛型函数 | 当前泛型无约束；§3.4 重合 | 批 2 |
| A3 | 多行容器字面量尾逗号 | PAR 语法面变更；**触及语义错误集，须全量 pytest 评估破坏面** | 批 1（P0） |
| A4 | 无显式返回缺省 void/auto | 现无缺省；样板负担 | 批 2 |
| A5 | 结构化解构/模式匹配 | 与 VISION-4 `match` 方向重合，整合推进 | 批 2 |
| A6 | Enum/tagged union 增强 | 与 VISION-4 ADT 方向重合，整合推进 | 批 3 |
| B1 | 运行时错误携带 ibci 源码行号 | RUN_* 诊断有码无行，traceback 全 Python 帧（本 session 冒烟实证 RUN_INDEX_ERROR）；诊断体系承载增强 | 批 1（P0） |
| B2 | 惰性/短路求值结构 | 生成器消费协作化已做；∀/∃ 推导惰性结构缺 | 批 2 |
| B3 | 一等环境/作用域对象（可快照/嵌套） | intent_context 已结构化但偏提示词注入；world/mode/discourse 环境对象缺 | 批 1-2（P0-P1） |
| B4 | 编译错误定位准确 | 诊断体系增强项 | 批 2 |
| B5 | 并发原语成熟化 | chan/slot/thread + run_batch 已有基础 | 批 3 |
| C1 | **embedding/向量一等能力**（vector 类型/相似度/检索/外部接入） | 全仓无向量能力；ref 主张"语义内容缝 ≠ media"，请求独立立项——**与 PT-SEALED-1 media 封存边界需用户裁定** | 批 1（P0，愿景关键） |
| C2 | 结构化 LLM 输出契约（schema 生成/稳健解析/自动重试） | `expected_type` 单值解析已修；复杂嵌套 schema 支持弱、`json.parse` 脆弱、无自动重试闭环 | 批 1（P0） |
| C3 | 用户模块路径解析完善与文档化 | .ibci 用户模块机制存在；路径解析未文档化、多文件工程未验证；与 T2/T1（工程化）协同 | 批 1（P0） |
| C4 | ibci 内测试设施（assert/test 模块 + 运行器 + 行号） | 语言无 assert/test 设施；现有 trials harness 是 Python 侧 | 批 1（P0） |
| C5 | 供应商感知思考抑制 | PT-DECIDE-2（sealed）；**新实证：双字段抑制对新端点 vLLM 有效（非思考亚秒、无告警），缺口收窄为"后端强制思考"场景**——解封重估待裁定 | 批 2（重估后） |
| C6 | 流式/批量/多模型编排完善 | stream/run_batch/命名路由已有（T11/T08）；多模型组合文档弱 | 批 3 |
| C7 | 性能内省（单调时钟/调用级埋点） | time 模块有；单调时钟与埋点缺 | 批 3 |
| D1 | idbg 增强（意图栈/环境/world register 可视化、UID 反查源码行） | 现有 intents/env(运行时诊断)/show_*；**idbg.env 命名冲突（T2）一并收敛** | 批 2 |
| D2 | CLI inspect/check 导出 | 无 | 批 3 |
| D3 | 新能力配套诊断码 | 诊断体系已有（codes/catalog），随新能力配套 | 批 3（随批 1 大项） |
| E1 | ihost 完善（子环境 LLM 配置继承/隔离边界/调试体验） | run_isolated/spawn_isolated/collect 已有；配置继承缺 | 批 2 |
| E2 | save/load_state 覆盖 Environment（world/mode/话语） | 现仅变量级 | 批 2 |

## 四、批次结构建议

- **批 0（清场 + 铺路）**：阶段 C 残留 LLM 项（恶意边界未测 9 项 + 全量 LLM 回归复跑，
  环境已就位）+ T1 配置单源收敛 + T3 harness 可用性 + T4/T5 小项。
- **批 1（ref P0 语言大项）**：C1（裁定后）/ C2 / C3 / C4 / B1 / A3 / A1 / B3。
- **批 2（P1）**：A2 / A4 / A5 / B2 / B4 / C5 重估 / D1 / E1 / E2。
- **批 3（P2）**：A6 / B5 / C6 / C7 / D2 / D3。

## 五、需用户裁定项（已全部裁定，2026-09-05）

1. **C1 embedding**：✅ 必须、解封独立立项（PT-FEAT-16，P0）；media 封存边界切出。
   **附加纪律**：系统级架构设计先行——语言形态/职责/数据结构/系统角色/全元素交互，
   与 LLM 同等严肃对待（`tasks_docs/_embedding_design.md`）。
2. **PT-DECIDE-2**：✅ 解封，重估聚焦"后端强制思考"场景。
3. **批 0 先行**：✅ 按工程经验自主推进（授权全自动自主运行）。
4. **ref 来源项目协同**：✅ 授权按工程经验自主决策；当前处置 = 以本需求单为阶段 E
   验收基线（六项 P0 落地 = 愿景可开工），来源项目切换主线事项待其可运行时再评估。

## 六、正式登记状态

- `PENDING_TASKS.md` VISION-7 已登记（阶段 E 总条目）。
- 各项开工时按 `PT-<域>-<n>` 注册：T1→DEBT、T2/T3/T4→FEAT、T5→DOC/TEST、
  ref 语言大项→FEAT（或并 VISION-4 重合项），状态与优先级届时定。
