# _PHASE_E_HANDOFF — 阶段 E 交接全景（临时文档：接手智能体必读，交接消化后按治理删除）

> **目的**：向接手智能体完整移交阶段 E 全部工作上下文。本文档是唯一需要通读的交接件；
> 其余状态以各常驻文档为权威（本文不复制其正文，只给指针 + 补充细节）。
> **必读顺序**：`AGENTS.md`（工作纪律）→ 本文件 → 按需深入各指针。
> **硬约束提醒**：禁止 push（除非用户显式授权）；工作模式定论凌驾一切；全量测试唯一命令
> `python -m pytest tests/`；单点真理纪律（状态看 PENDING_TASKS、主线看 NEXT_STEPS）。

## 一、环境事实（本机，全部不入库；权威源 = `AGENTS.local.md`）

- **Python**：conda env `ibci`，解释器绝对路径 `/home/haber/miniconda3/envs/ibci/bin/python`
  （Python 3.12.13）；激活 `conda activate ibci`；脚本免激活直用绝对路径。
  注意：远端 AGENTS.md 规范 recipe = venv + editable，**本机按用户裁定用 conda**（等价形态，
  editable 安装指向本仓库，dev 依赖齐备）。pyproject 版本变更后需重装同步 editable 元数据
  （曾现 0.1.0→0.2.0 漂移）。
- **LLM 端点**：`http://localhost:8001/v1`（vLLM 0.28.0，OpenAI 兼容，强制 Bearer 鉴权，
  无/错凭证 401）。用户裁定：接下来及未来所有试用均用此端点。
- **模型红线（用户裁定）**：只允许 `Qwen3.6-35B-A3B`（非思考基线）；**禁止
  `Qwen3.8-27B-NVFP4`**。模型 ID 以服务端 `/v1/models` 精确大小写为准。
- **API key**：明文在 `AGENTS.local.md` + 仓库根 `api_config.json`（均 gitignored）。
  tracked 文件零密钥（实证纪律，任何改动后用 `git diff | grep <key>` 复查）。
- **命名路由用例密钥通道**：环境变量 `IBCI_TRIAL_LLM_KEY`，tracked 用例经宿主绑定
  `import python "os" as oslib: bind getenv(key: str) -> str` 读取；运行前
  `export IBCI_TRIAL_LLM_KEY=<key>`（导出行在 AGENTS.local.md）。
- **LLM 服务陷阱（实证）**：顶层 `enable_thinking` 被 vLLM **静默忽略**（模型照旧思考）；
  关思考必须走 `chat_template_kwargs: {"enable_thinking": false}`。内置默认 provider
  双形态同发已兼容（`ibci_modules/ibci_ai/provider_impl.py`）。非思考响应亚秒级、
  `reasoning_tokens=0`；思考内容被服务端 reasoning parser 隔离进 `message.reasoning`。

## 二、项目现状快照（截至交接）

- 分支 `unsafe-vibe-dev`，本地领先 origin 约 20 commit（**未 push**——用户已口头授权 push，
  交接动作含 push，见 §九）。
- 测试基线：3198 passed / 1 skipped（以实跑为准）。
- 主线状态：见 `tasks_docs/NEXT_STEPS.md`（阶段 E · 真实使用整改与灰盒愿景整合）。
- 任务台账：`tasks_docs/PENDING_TASKS.md`（VISION-7 总条目 + PT-FEAT-16 embedding +
  PT-DECIDE-2 已解封）。
- 试用体系：`trials/INDEX.md`（缺陷映射表 + 恶意边界清单进度）；服务规范
  `trials/_toolkit/LLM_SERVICE.md`（已去机器化，服务无关）。

## 三、本 session 全部工作（commit 序）

| commit | 内容 |
|--------|------|
| `4e91c46c` | LLM 端点迁移 vLLM @ localhost:8001：43 份 gitignored api_config.json 批量迁移；D1-07-006/D5-03 命名路由用例改环境变量密钥通道；LLM_SERVICE.md 重写；§7.5 `env("KEY")` 幽灵机制文档修正（改宿主绑定 os.getenv 真实用法）；双用例真实 LLM 亚秒 PASS |
| `9c9d8bd3` | 用户裁定落账：C1 embedding 解封立项（PT-FEAT-16）+ PT-DECIDE-2 解封 + 全自动自主运行 |
| `c6dc31cb` | **T1 配置单源收敛**（详见 §四） |
| `dda586b8` | **T3 harness**：probe.py + run_batch --probe + _common.find_repo_root 单源化 |
| `5c0e70c5` | **T4** max_tokens 进配置面全链路 |
| `7fbfc787` | **清场复跑 233 例** + 7 处用例修正 + LLM-5/IMPORT-2 登记 + rerun_old_suites 修复 |
| `5f40ee9c` | 批 0 落账 |
| `82f6233a` | 恶意边界 #23 三用例（M20/M21/M22） |
| `c3cc391d` | #23 核销登记 |
| `2922e3b4` | 恶意边界 #6/#14/#22 核销（M24/M25/M26/M27） |
| `9787c856` | LLM-5 压测记录（34 连净，转事件驱动） |
| `296ecfa1` | **PT-FEAT-16 embedding 设计文档 v1**（`tasks_docs/_embedding_design.md`） |
| `ee137d83` | 恶意边界 #16 部分核销 + **SER-1 登记**（M28 复现用例） |
| `5a76aa14` | **SER-1 修复**（详见 §五） |
| `3bd2c213` | SER-1 修复登记 + #16 核销 |
| `de3256db` | NEXT_STEPS 状态刷新 |
| （待提交） | 涂抹语义裁定落账 + LLM_SERVICE.md 去机器化 + 本交接文档 |

## 四、配置契约（T1 重构后的新语义——必须掌握）

- **发现机制**：`ibci_modules/ibci_ai/config_source_adapter.py::discover_config_path(project_root)`
  ——自 project_root 逐级向上找最近的 `api_config.json`（就近覆盖：子目录差异化配置可用），
  搜索上界 = 含 `.git` 的目录（该目录自身仍参与匹配），不拾取仓库外配置。
- **单源布局**：仓库根 `api_config.json`（gitignored）服务全部 trial；trial 本地副本已全删
  （59 份：43 份 provider 块与根等价、13 份 defaults-only 零消费者——用例均
  `ai.set_mock_mode()` 显式进 mock、T06 用例目录配置为误导性死重 expect-llm 配 mock:true
  且 harness 从不消费）。
- **契约不变式**：`ai.load_project_config()` 显式加载；界内无配置 = 合法 no-op；
  `{env:VAR}` 插值 fail-fast（CFG_CONFIG_ENV_VAR_MISSING）。
- **单位**：`defaults.timeout` 为**秒**（默认 30.0）。旧个别 trial 根有 45（旧端点校准），
  收敛后统一 30，233 例复跑实证无超时。
- **run_one 路径解析**：绝对 → CWD 相对 → trial 根相对（三级）；修复前 repo 相对路径会被
  根拼接翻倍。配置前置检查复用 adapter 发现逻辑（单点真理不在 harness 复刻）。

## 五、缺陷台账细节（INDEX.md 有正式登记；此处给根因与机制细节）

### SER-1（已修复，`5a76aa14`）
- 症状：`import ai` 后 `save_state`/`load_state` → `ai` 全体成员 AttributeError。
- 根因双层：① 内核原生模块（scope_native）反序列化为空 scope 占位（设计如此，实现由重绑
  恢复）；② `_rebind_environment` 只重绑 global scope，而 import 绑定在**模块作用域**
  （遮蔽 global 的活值）。
- 修复三件套（`core/runtime/host/service.py::_rebind_environment` +
  `runtime_serializer.py::restored_scopes`）：
  1. `restored_scopes()` 公开物化入口（uid 去重幂等）——全部作用域树；
  2. 就地变更符号值（`sym.value = live_obj`）——**不可重建符号**：编译期符号 UID 与运行期
     uid 键是同一符号的多别名，`define(uid=)` 会触发别名清理丢失编译期键（探针实证）；
  3. 模块对象按 import 路径同构构造：`create_native_object(vtable=契约, whitelist=契约) +
     create_module 包装`——缺契约的裸 NativeObject 成员访问会被模块契约门拒绝
     （既有 global 重绑就有此潜伏缺陷，一并修正）。
- 回归门：`trials/T15_edge_malicious/cases/T15-E-M28-state-roundtrip-intent.ibci`
  （持久意图保真 / save 后变更丢弃 / 插件状态 round-trip 三断言）。

### LLM-5（未修，事件驱动监视）
- 症状：`Resp r = inst()`（llm 可调用类 + expected_type 用户类 + `__from_prompt__`）约 1/6
  概率绑定未解包包装物——渲染 `Resp(result='OK')`（Python 侧镜像类 repr，非 IbObject 渲染）、
  `.text` 读不到用户字段。失败日志：当时 RR-3。
- 已排除：rebind 路径（`Resp` 无 `[` 不触发 S3 物化）；IbObject/IbLLMCallResult 渲染链。
- 已做：34 连净未复现（直跑/harness 双路径）；失败窗口疑似与 LLM 服务负载相关。
- 监视：D4-05 用例保留，任何批次运行经 batch judge 自动暴露复发；复发时带插桩
  （`core/runtime/interpreter/llm_parsing_strategy.py::VTableParsingStrategy.parse` 构造点
  打印实例 fields/类型）压测追因。

### IMPORT-2（待 C3 设计定案，非 bug 修复）
- 事实：`import geo`（用户 .ibci 模块）解析锚定 **project_root** 而非入口文件目录。
  多文件用例在 project_root ≠ 用例目录时 `DEP_MODULE_NOT_FOUND`；历史靠"root=用例目录"
  隐性耦合通过；配置单源收敛后暴露。
- 短期处置：harness 对目录型用例 root=用例目录（rerun_old_suites 与 run_one 均已如此；
  `collect_cases` 注释写明"目录型用例 = 自包含多文件工程"）。
- 长期：锚点语义（project_root vs entry_dir、搜索顺序）与 ref C3（用户模块路径解析
  文档化）统一设计——这是 C3 的核心输入之一。

### 涂抹消费语义（用户已裁定，非缺陷）
- `@`/`@!` one-shot 绑定"下一条语句执行窗口"：**任何语句**（含非 LLM/非 ai 语句）都
  消费/清空窗口——与 `docs/syntax/09_intent_system.md` 既有文档一致；M28 观测实证
  （`ai.set_return_type_prompt` 间隔使涂抹不达 save）。语言不做强制检查；消费检查由
  ibci 使用者负责。设计 trials 意图用例时注意此语义（持久意图用 `ctx.push`）。

## 六、恶意边界清单状态（trials/INDEX.md「恶意边界后续未测项」表）

| # | 主题 | 状态 | 用例与要点 |
|---|------|------|-----------|
| 6 | snapshot 内嵌 LLM 交叉 | ✅ | M24：snapshot 捕获容器（定义时深克隆），定义后变异不泄漏（call_info user_prompt 观测） |
| 14 | 流式中断/llmexcept 组合 | ✅ | M25 流式 provider 失败经 except 干净传播；M26 llmexcept 附着流式 await → 编译期 SEM_LLMEXCEPT_BINDING fail-fast |
| 16 | 序列化 round-trip 意图槽 | ✅ | M28（SER-1 回归门 + 插件状态保真） |
| 22 | ihost collect 错误传播 | ✅ | M27（PR5_ihost 目录用例）：子环境变量字典/运行期失败/编译失败/未知句柄四断言全 fail-fast |
| 23 | bind 强制/隔离 | ✅ | M20 绑定缺失成员报错 / M21 成员门控+双别名隔离（RUN_ATTRIBUTE_ERROR）/ M22 非可调用声明为方法拒绝 |
| 15 | intent_context 类字段 deep_clone | ⏸ | 前置：snapshot 多语句体/类字段捕获观测面确认（快照体为单行为表达式，类字段捕获路径未验证） |
| 17 | 跨引擎序列化/水化 | ⏸ | SER-1 已修，可做；涉及特化类/枚举/意图上下文水化 |
| 19 | overlay 与序列化/snapshot/retry 交互 | ⏸ | 参考 T12_overlay_protocol 既有面 |
| 33 | _pending_futures 长会话累积 | ⏸ | 与 LLM-5 同子系统（llm_executor）；`pending_futures_count()` 为 Python 侧内省，语言层观测面需先设计 |

用例书写纪律（从已核销案例提炼）：**先观测后冻结断言**；断言取稳定可判定部分（禁整句
精确匹配/机器特定值/非确定渲染）；守卫类用 expect-class GUARD + 精确错误行；缺陷复现用
expect-class KERNEL_ISSUE + 修复后期望（判 HARNESS=缺陷仍在，转 PASS=待核销）。

## 七、ref 需求单（灰盒愿景）完整映射

源：`ref/IBCI_REQUIREMENTS.md`（外部灰盒自动机需求单，本地资产）。愿景："灰盒自然语言
自动机全部在 ibci 内完成、ibci 不寄生 Python"。完整映射表见
`tasks_docs/_next_phase_targets.md` §三（A1-E2 逐项：IBCI 现状/关联/批次）。速览：

- **批 1（P0 语言大项）**：C1 embedding（PT-FEAT-16，设计进行中）/ C2 结构化 LLM 输出契约 /
  C3 用户模块路径解析（IMPORT-2 是核心输入）/ C4 ibci 内测试设施 / B1 运行时源码行号 /
  A3 容器字面量尾逗号（触及语义错误集，需全量评估）/ A1 用户协议一等公民 / B3 一等环境对象
- **批 2（P1）**：A2 泛型约束 / A4 返回注解缺省 / A5 模式匹配（与 VISION-4 重合）/ B2 惰性 /
  B4 编译错误定位 / C5 思考抑制重估（PT-DECIDE-2 已解封，缺口收窄为"后端强制思考"）/
  D1 idbg 增强（含 idbg.env 命名冲突收敛）/ E1 ihost 配置继承 / E2 save_state 覆盖 Environment
- **批 3（P2）**：A6 tagged union（VISION-4 重合）/ B5 并发 / C6 流式批量文档 / C7 性能内省 /
  D2 CLI inspect / D3 诊断码配套
- **阶段 C 残留**：恶意边界余项（§六）
- 正式登记：VISION-7（总条目）；各项开工时按 `PT-<域>-<n>` 注册进 PENDING_TASKS。

## 八、embedding 设计现状（PT-FEAT-16，下阶段主攻）

- 设计文档：`tasks_docs/_embedding_design.md`（v1）——先例剖析（LLM 五层骨架同构：
  契约包/推荐实现/模块面/配置单源/mock 指令）、系统角色定位、vector 值类型候选决策
  （不可变/值语义/vtable 方法面/无字面量暂缓/无隐式归一化）、EmbeddingProvider 契约
  候选签名、全元素交互协议清单、批次与验收。
- **开放问题 Q1-Q4（收口时裁决，按 design-philosophy 自裁并记录）**：
  Q1 载体模块（并入 ai vs 独立 iembed）；Q2 相似度/检索归属（vector 方法面 + 线性扫描
  最小闭包起步）；Q3 LLM expected_type=vector 边界（倾向否——向量来自嵌入服务非文本解析）；
  Q4 诊断码域（新 EMB_ vs 归 RUN_）。
- 补充证据（本轮新增）：端点 embeddings 可用性未实测（`/v1/embeddings` 是否暴露待验证，
  实现 provider 前先 curl 实测）；配置 schema 形态需与 T4 的 max_tokens 先例一致
  （模型条目可选字段 + fail-fast 校验白名单透传）。
- **设计纪律（用户明确，不可降级）**：embedding 不是"一种数据结构或一个库函数"——语言形态/
  职责/数据结构/系统角色/全元素交互协议系统级设计先行；实现批次见设计文档 §七。

## 九、交接动作与下一步计划

1. **本交接提交后 push `unsafe-vibe-dev` 到 origin**（用户已显式授权；仅此一次动作，
   后续仍默认禁 push）。
2. 推荐优先序：
   a. 恶意边界 #17（跨引擎水化）/#19（overlay 交互）——SER-1 已清，可做；
   b. **embedding 设计收口**（Q1-Q4 裁决 → 契约包 + vector 类型 + provider 实现，
      按 §七批次，每步全量 pytest）；
   c. 批 1 其余大项（C3 时把 IMPORT-2 一起定案；C4 测试设施落地后恶意边界余项可迁入
      ibci 内测试形态）。
3. 工作方式：按 AGENTS.md 自主工作循环（理解→设计质询→自主决策→实现→自反馈→纠错→
   交付自查→收尾）；小问题按工作制度自裁（用户明确指示勿频繁请示）；仅公理层/语义
   错误集/对外契约/真正无法决断项上报。
4. 试运行速查：
   - 全量：`python -m pytest tests/`（conda 激活后）
   - 探测：`python trials/_toolkit/probe.py`
   - 单套件：`python trials/_toolkit/run_batch.py trials/<T> --probe --timeout 60`
   - 单用例：`python trials/_toolkit/run_one.py cases/<c>.ibci --label L --dim D --doc "" --expected "" --timeout 60 --root <trial根>`
   - 命名路由用例前：`export IBCI_TRIAL_LLM_KEY=<key>`
