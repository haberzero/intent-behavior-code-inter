# INDEX — IBCI 试用地基跨套索引

> 规范：`_toolkit/CLASSIFICATION.md`（分类/级别/编号/骨架/运行入口单一权威源）。
> 新增试用地基必须：遵循命名 `T<nn>_<主题>`、引用 `_toolkit/run_one.py`（软链非复制）、
> 更新本索引、缺陷编号全局唯一。
>
> **试用环境基线**：所有开发试用均在**本地 `Qwen3.6-35B-A3B` 非思考模式**（vLLM
> OpenAI 兼容端点 @ `localhost:8001`，`reasoning: false`）下进行；mock 仅用于无
> LLM 依赖用例。服务细节见 `_toolkit/LLM_SERVICE.md`。

## 一、试用地基一览

| 套 | 主题 | 日期 | 用例 | 结果概览 | 主要缺陷（新编号） |
|----|------|------|------|----------|--------------------|
| `T01_llm_full` | 真实 LLM 全语法/压力/批判试用（原 `_LLM_TRIAL_20260812`） | 2026-08-12 | 104 cases / 113 运行 | D1-D3 全过；A1-A5/C1-C4 验证 | `KERNEL_ISSUE-VM-1`~`CONFIG-1`（已修）、`DOC-ISSUE-001~007`（已处置）、`BOUNDARY-*-*`（已记录） |
| `T02_enum_import` | enum 补全 + 嵌套包 import 用户试用（原 `_LLM_TRIAL_ENUM_IMPORT_20260812`） | 2026-08-12 | 9 例 | 全 PASS / 1 LIMIT（2026-08-13 重构断言，映射有效性） | 无 |
| `T02_enum_import`（2026-08-14 全量核查重跑） | — | 2026-08-14 | 9 例（mock 6 + LLM 3） | mock 5 PASS + 1 LIMIT；LLM 2 PASS + **1 LLM_BEHAVIOR**（T5-enum-value-ne-name 间歇格式偏离，非内核缺陷） | 无 |
| `T03_user_class_generics` | 用户类泛型压力/恶意试用（原 `_GENERICS_TRIAL_20260812`） | 2026-08-12 | 30 运行 | 23 PASS + 6 GUARD + 1 HARNESS（smoke；2026-08-14 重跑 D2-07 chan 迁普适写法转 PASS） | `KERNEL_ISSUE-GEN-1/2/3`、`BOUNDARY-GEN-1`（已修）、`KERNEL_ISSUE-GEN-6`（**已修 2026-08-13**） |
| `T04_generics_fix_regression` | 泛型修复回归试用（原 `_GENERICS_TRIAL_FIX_20260812`） | 2026-08-12 | 33 例 | 26 PASS + 7 GUARD + 1 HARNESS（smoke；2026-08-14 重跑 R5-03 chan 迁普适写法转 PASS） | `KERNEL_ISSUE-GEN-4`（已修）、`BOUNDARY-GEN-2`（已修，用例重构核销）、`KERNEL_ISSUE-GEN-5`（**已修 2026-08-13**） |
| `T05_critical_stress` | 批判性压力试用（跨模块类表 module 化后内核 + 真实 LLM + 文档全量核验） | 2026-08-14 | 40 用例 | 37 PASS + 1 GUARD + 2 KERNEL_ISSUE | `KERNEL_ISSUE-CROSSMOD-THREAD-1`（**已核销 2026-08-14，D1-10 .ibci expect-class→PASS**）、`KERNEL_ISSUE-OPTIONAL-ISNONE-1`（**已核销 2026-08-14，D2-03 转 PASS True|True|False**）、`DOC_ISSUE-1~23`（代码联动项已修，文档部分已治理） |
| `T06_class_identity` | 统一类身份模型回归 + 真实试用（Task1 S1-S4 根治验证 + T05 KI-1 核销） | 2026-08-14 | 20 用例 | 18 PASS + 2 KERNEL_ISSUE（同一根因） | `KERNEL_ISSUE-CROSSMOD-LLM-1`（**已核销 2026-08-14，T07 D3 重验**） |
| `T07_fixes_critical_stress` | 四项修复批判性对抗 + 旧套件 T01-T06 全量重跑（用户强调） + 泛型边界复测 | 2026-08-14 | 43 用例 + 旧套件 238 重跑 | 28 PASS + 12 GUARD + 3 KERNEL_ISSUE；旧套件 202 PASS + 24 GUARD + 1 LIMIT + 1 KERNEL_ISSUE(陈旧断言) + 9 HARNESS | `KERNEL_ISSUE-OPTIONAL-SCOPE-1`、`KERNEL_ISSUE-OPTIONAL-CONTAINER-1`、`KERNEL_ISSUE-ATTR-READ-1`（均**已修复 2026-08-14，触发用例核销**） |
| `T07_fixes_critical_stress`（E 批判补充批次，2026-08-14 第二 session 复核） | 三项 P1 修复有效性 + 边界挑刺（T07 后置独立批） | 2026-08-14 | +8 用例（E1-E8） | **5 PASS + 1 BOUNDARY + 2 DOC_ISSUE**（委托链全矩阵 PASS；空值错误码不一致 + 嵌套函数返回类型边界）→ **E1-E8 全 PASS**（2026-08-14 修复后核销） | `DOC-29`（空 Optional 错误码，**已修复 19920d39**）、`BOUNDARY-NESTED-FUNC-1`（返回类型校验，**已修复 19920d39**） |
| `T08_llm_pressure` | LLM 全能力真实压力试用（第一轮，本地 qwen3.6-35b-a3b 非思考模式） | 2026-08-15 | 41 例 | 32 PASS + 2 GUARD + 4 LLM_BEHAVIOR + 2 BOUNDARY + 1 LIMIT | `KERNEL_ISSUE-LLM-2`（**已修复**）、`KERNEL_ISSUE-LLM-3`（**已修复**）、`DOC_ISSUE-30`、`BOUNDARY-LLM-2`、`BOUNDARY-LLM-3` |
| `T09_protocol_kernel_impact` | 协议化内核大重构影响确认（既有套件真实 LLM 回归 + 新能力试用） | 2026-08-16 | 既有 108 例回归 + 新 8 例 | 回归分类与重构前基线逐类一致（**零回归**）；新能力 N1-N8 全 PASS（impl LLM 方法 / 泛型 bound / LLM 函数第一等值 / 长 prompt / 并发 dispatch / llmexcept 真实重试 / 类内 LLM 方法 / __from_prompt__） | 无新增；BOUNDARY-LLM-2/3 与未读赋值 LIMIT 为已登记项复现 |
| `T10_llm_callable` | 五大地基新特性：llm 可调用类全面（直接调用/装配/解析/`__intent__` 三层改写/`__retry__` 高阶化/run_batch 逐项参数化） | 2026-08-21 | 13 例（mock 层） | 9 PASS + 4 GUARD（mock 层确定性全绿） | `BOUNDARY-LLM-4`（新登记）；LLM 层回归待运行 |
| `T11_stream_batch` | 五大地基新特性：stream 流式消费面（stream_call/stream_channel 逐块）+ run_batch 批量（行为逐项绑参/llm 实例逐项参数化） | 2026-08-21 | 5 例（mock 层）+ 迁移 4 例 | 5 PASS（mock 层全绿）；**修复**进程内 mock 流式分块保真缺口（provider test_mode 丢 chunks，回归测试 +1）；迁移 4 个旧字符串形态 stream 用例 | 无新缺陷；D5-01/D5-02/D5-08/D2-35 迁移 |
| `T12_overlay_protocol` | 五大地基新特性：覆层机制（overlay 端到端/嵌套/守卫，既有套件零覆盖→基本覆盖）+ prompt 协议族（to_prompt/from_prompt/outputhint 确定性 + 形状违约守卫） | 2026-08-21 | 9 例（mock 层） | 6 PASS + 3 GUARD（mock 层全绿）；契约确认：__from_prompt__ 形状违约→LLMParseError（PT-DECIDE-3 ① 一致） | 无新缺陷 |
| `T13_intent_ctx` | 五大地基新特性：意图一等值嵌入（@+ $x eager/按值移除）+ snapshot 冻结 vs lambda live + intent_context OOP 方法族（文档工作流 + 缺参 fail-fast） | 2026-08-21 | 5 例（mock 层） | 4 PASS + 1 GUARD（mock 层全绿）；语义确认 use= fork 拷贝 | `BOUNDARY-LLM-5`（新登记：进程内 mock call_info 无 sys_prompt 键） |
| `KERNEL_ISSUE-LLM-4` | llm-callable `expected_type`=裸用户类名不解析：装配直接传裸名 → VTableParsingStrategy `get_class` miss 运行时类键（module 限定）→ `__from_prompt__` 不生效、退化返回 str（docs §8.5 宣称用户类经 __from_prompt__ 解析） | **已修复（2026-08-21）**：装配时按 callable 类 module 限定裸 expected_type（对齐行为路径 node_to_type 语义）；回归测试 +2（test_llm_callable_unified.py）；T08 D4-05 真实 LLM 转 PASS；另修 D4-01 `\\"` 转义用例 bug | `T08/.../D4-05-llmfunc-userclass.ibci` + `T10/.../probe`（已删，回归测试承载） |
| `T14_fs_optional` | 五大地基新特性：fs 模块全接口（open/read/read_bytes/write new+overwrite/exists/remove + 只读/沙箱守卫）+ Optional 值模型/容器元素 + 值语义 | 2026-08-21 | 9 例（mock） | 7 PASS + 2 GUARD（全绿）；沙箱越界写被 RUN_PERMISSION_ERROR 拒（无漏洞）；file_handle 只读守卫 | 无新缺陷 |
| `T15_edge_malicious` | 恶意边界测试（起点清单 33 项逐条核对 + 自行扩展：容器==/意图窗口/装配键/参数/协议异常/retry/泛型/递归/retry 体内文件写禁/线程 LLM 等；未测项见下「恶意边界后续未测项」） | 2026-08-21 | 22 例 | 14 PASS + 7 GUARD + 1 LIMIT（无内核缺陷；fail-fast + 编译期守卫全生效；>4k token/多轮/批量并发真实 LLM 全 PASS） | 无；待文档复核项（装配 dict 未知键静默忽略） |

### 恶意边界后续未测项（专项/LLM 层，承接已删起点清单）

> 阶段 C 恶意试用逐条核对 33 项起点清单后遗留的未测/部分项（mock 不可确定观测或需专项），
> 随主线顺带补齐；补测时按本表逐项设计对抗性用例，发现即按 INDEX 生命周期登记分类。
> （起点清单 `_trial_edge_catalog.md` 已按治理删除，git 承载历史。）

| # | 主题 | 状态 | 目标窗口 |
|---|------|------|----------|
| 6 | snapshot 内嵌 LLM 调用交叉（冻结 vs 调用点 live） | ✅ **已测（2026-09-05）**：T15-E-M24 snapshot 捕获容器自由变量（定义时深克隆），定义后变异原容器不泄漏进快照调用（frozen1/frozen2 双断言）——冻结语义零缺陷 | `T15/.../T15-E-M24-snapshot-frozen-capture.ibci` |
| 14 | 流式中断 / llmexcept 组合错误传播 | ✅ **已测（2026-09-05）**：T15-E-M25 流式 provider 层失败经 except Exception 干净传播（不吞、无部分结果）；T15-E-M26 llmexcept 附着流式 await → 编译期 `SEM_LLMEXCEPT_BINDING` fail-fast（流式失败属非解析不确定域，不经 retry——与 KERNEL_ISSUE-LLM-1 处置一致） | `T15/.../T15-E-M25/M26-*.ibci` |
| 15 | intent_context 类字段 deep_clone 路径 | ⏸ 未测 | 后续专项（需先确认 snapshot 多语句体/类字段捕获观测面） |
| 16 | 序列化 round-trip inherited_smear/override 槽 | ⏸ 未测 | 后续专项 |
| 17 | 跨引擎序列化/水化（特化类/枚举/意图上下文） | ⏸ 未测 | 后续专项 |
| 19 | overlay 与序列化/snapshot/retry 交互 | ⏸ 未测 | 后续专项 |
| 22 | 动态宿主 collect 错误传播/超时（ihost） | ✅ **已测（2026-09-05）**：T15-E-M27（PR5_ihost 目录用例）四断言——正常子环境变量字典承载子变量 / 子环境运行期失败 collect 点 RuntimeError fail-fast / 子环境编译失败同传播 / 未知句柄 Unknown spawn handle fail-fast——全 GUARD 生效零缺陷 | `T15/.../PR5_ihost/` |
| 23 | bind 白名单/vtable 强制/registry 隔离 | ✅ **已测（2026-09-05）**：T15-E-M20（绑定期缺失成员报错）/ M21（成员门控 + 别名隔离，RUN_ATTRIBUTE_ERROR）/ M22（非可调用成员声明为方法绑定期拒绝）——三守卫全 GUARD 生效，零缺陷 | `T15/.../T15-E-M20~M22-*.ibci` |
| 33 | `_pending_futures` 长会话累积（内存面） | ⏸ 未测 | 后续专项（与 KERNEL_ISSUE-LLM-5 同子系统，随其修复后观测） |

## 二、缺陷编号映射表（旧 → 新）与生命周期状态机

> 统一格式见 `CLASSIFICATION.md` §三。**生命周期状态机**（CONTRACT_FORMAT §五）：
> `发现 → 登记 → 修复（tests/ 补回归）→ 回归试用（触发用例核销）→ 已修复/已核销`。
> 本表为状态单一权威源；REGISTER/PENDING_TASKS 引用一致。触发用例 `expect-class:
> KERNEL_ISSUE` + `expect-out: <修复后期望>` 为核销判据（达成即转 PASS 待核销）。

### 域 GEN（泛型，T03/T04）

| 旧 | 新 | 主题 | 状态 | 触发用例 |
|----|----|------|------|----------|
| KERNEL-ISSUE-G1 | `KERNEL_ISSUE-GEN-1` | 泛型方法体内类型参数运行时失效（运行期） | 已修复 32484fe | — |
| KERNEL-ISSUE-G2 | `KERNEL_ISSUE-GEN-2` | 泛型类自引用字段特化替换失效（编译期） | 已修复 32484fe | — |
| 双通道 descriptors | `KERNEL_ISSUE-GEN-3` | 特化方法参数 descriptors 两套实现 | 已修复 32484fe | — |
| KERNEL-ISSUE-G3 | `KERNEL_ISSUE-GEN-4` | 继承特化父类字段丢失（auto-init 只收自身） | 已修复 b0f4d74（2026-08-13） | R1-05/R5-01 已重构为修复后语义（2026-08-13，PASS 核销） |
| — | `KERNEL_ISSUE-GEN-5` | 用户泛型类下标表达式位置特化未注册 | **已修复 2026-08-13**（visit_IbSubscript 复用 _resolve_type 递归；触发用例 GEN5-01 PASS 核销） | `T04/.../GEN5-01-nested-specialization.ibci` |
| — | `KERNEL_ISSUE-GEN-6` | 泛型运算符方法参数含 T 的特化未生效（G1 修复不完整） | **已修复 2026-08-13**（解析端 resolve_typeref + 构造端 from_spec 统一；触发用例 D2-01 PASS 核销） | `T03/.../D2-01-operator-override.ibci` |
| BOUNDARY-G1 | `BOUNDARY-GEN-1` | 非法特化实参（Box[42]/Box[None]）编译期未拦 | 已修复 3fe98d6 | — |
| BOUNDARY-G2 | `BOUNDARY-GEN-2` | 自引用链 while"类型退化"（实为用例无效 + any 复查缺口） | 已修复 b0f4d74（2026-08-13） | R5-04 已重构为合法遍历（2026-08-13，PASS 核销） |

### 域 OPTIONAL/ATTR（T07，2026-08-14 新登记，本任务修复交接，下一 session 修复）

| 新 | 主题 | 状态 | 触发用例 |
|----|------|------|----------|
| `KERNEL_ISSUE-OPTIONAL-SCOPE-1` | 函数作用域内 Optional 先 None 后赋值，unwrap()/is_some() 报 `Object of type 'None'`（顶层/lambda 正常，文档 §8"任何路径可用"不成立） | **已修复（2026-08-14，D2-09 PASS 核销，.ibci expect-class→PASS）** | `T07/.../D2-09.ibci` |
| `KERNEL_ISSUE-OPTIONAL-CONTAINER-1` | Optional[list[int]] 有值包装后 len()/下标不可用（`no method 'len'`/`'__getitem__'`） | **已修复（2026-08-14，D2-10 PASS 核销，.ibci expect-class→PASS）** | `T07/.../D2-10.ibci` |
| `KERNEL_ISSUE-ATTR-READ-1` | 未声明属性读取静默返回 None（仅调用路径报 RUN_ATTRIBUTE_ERROR，15_diagnostics 触发条件不符） | **已修复（2026-08-14，D1-13 PASS 核销，.ibci expect-class→PASS）** | `T07/.../D1-13.ibci` |

### 域 CHAN（BOUNDARY，2026-08-14 记录）

| 编号 | 主题 | 状态 |
|------|------|------|
| `BOUNDARY-CHAN-ARGS-1` | `chan(T, name, ...)` 的 T 实参传**特化类对象**（如 `chan(Box[int], “message”)`）时特化实参被降级为裸类（`chan[Box]`，type() 实证）；裸类型实参（`chan(str, “stream”)` → `chan[str]`）与无参声明式（`chan[E] ch = chan()`）均正常。普适写法 = 类型在声明处，构造只传运行时参数。文档 `14_concurrency.md` 宜补充说明 | 记录（非缺陷，待文档同步） |

### 域 E 批判补充（T07 后置，2026-08-14 第二 session 复核登记）

| 编号 | 主题 | 状态 | 触发用例 |
|------|------|------|----------|
| `DOC-29` | 空 Optional 操作（`for x in e` / `next(e)` / `e.unwrap()`）抛 `RUN_GENERIC_ERROR`，文档 arch/03 §8 承诺 `RUN_ATTRIBUTE_ERROR`；委托链空值路径（optional.py:174）与迭代/`unwrap` 路径（iterable.py:39 / optional.py:90）码不一致 | **已修复（2026-08-14，19920d39）**：iterable.py/optional.py 补 error_code=RUN_ATTRIBUTE_ERROR，三处收敛；E1/E2 核销 PASS | `T07/.../E1-empty-optional-code.ibci` / `E2-empty-optional-unwrap-code.ibci` |
| `BOUNDARY-NESTED-FUNC-1` | 函数返回嵌套函数（`return inner`）赋 `fn_callable[T]` 运行时 `RUN_TYPE_MISMATCH`。**深度分析修正定性**：真实根因=编译期 `visit_IbReturn` 返回类型校验整体缺失 | **已修复（2026-08-14，19920d39）**：`visit_IbReturn` 补可调用返回类型 is_assignable 校验；E3 转编译期 SEM_TYPE_MISMATCH 核销 PASS | `T07/.../E3-nested-func-return.ibci` |
### 域 LLM/VM/IMPORT/CONFIG/SEQ/ASYNC（T01）

| 旧 | 新 | 主题 | 状态 |
|----|----|------|------|
| KERNEL-ISSUE-001 | `KERNEL_ISSUE-VM-1` | global 写访问失效 | 已修（PT-DEBT-25） |
| KERNEL-ISSUE-002 | `KERNEL_ISSUE-IMPORT-1` | 整模块 import+成员访问 | 已修（PT-DEBT-26） |
| KERNEL-ISSUE-003 | `KERNEL_ISSUE-LLM-1` | LLM provider 失败异常逃逸 | 已修（PT-DEBT-27） |
| KERNEL-ISSUE-004 | `KERNEL_ISSUE-CONFIG-1` | ai vtable 未注册 | 已修（PT-DEBT-28） |
| BOUNDARY-001 | `BOUNDARY-SEQ-1` | for=to_list 物化 | 已记录 |
| BOUNDARY-002 | `BOUNDARY-ASYNC-1` | 生成器 await chan | 已记录 |
| BOUNDARY-003 | `BOUNDARY-CONFIG-1` | 隔离不继承 LLM 配置 | 已记录 |
| BOUNDARY-004 | `BOUNDARY-LLM-1` | @! run_batch 粒度 | 已记录 |
| BOUNDARY-005 | `BOUNDARY-CONFIG-2` | probe_model 误判 | 已记录 |
| DOC-ISSUE-001~007 | `DOC-ISSUE-001~007` | 文档批次 | 已处置 6f8506d |

### 域 LLM（T08，2026-08-15 第一轮压力试用）
| `DOC_ISSUE-31` | KNOWN_LIMITS §十二 漂移：intent_context 类静态调用文档称"静默无效"，B3 强化后实为编译期 SEM_INTENT_STATIC_CALL 告警 + 运行期 fail-fast（缺 _ctx 不变量） | **已登记（2026-08-21，T01 D3-60）**：fail-fast 优于静默无效（工作模式原则），文档阶段 C 末复核修正 | `T01/.../D3-60-intent-static.ibci`（已转 GUARD） |

| 编号 | 主题 | 状态 | 触发用例 |
|------|------|------|----------|
| `KERNEL_ISSUE-LLM-2` | LLM 函数返回 `list[int]` / `dict[str,int]` 未按容器解析，默认退化为 str | **已修复（2026-08-15）**：`_get_expected_type_hint` 读取 returns `node_to_type` 覆盖 IbSubscript；Optional 保持旧路径。回归 `test_llm_basic.py::TestE2ELLMFunctionContainerReturn` | `T08/.../D4-01-llmfunc-typed.ibci`（已转 PASS） |
| `KERNEL_ISSUE-LLM-3` | `ai.set_retry(0)` + `llmexcept` 不抛 `LLMRetryExhaustedError`，把不确定容器赋给目标导致 `RUN_TYPE_MISMATCH` | **已修复（2026-08-15）**：`_retry_llm_uncertain` 在 `max_retry<=0` 时立即抛耗尽。回归 `test_llmexcept.py::TestE2ELLMExceptZeroRetry` | `T08/.../D6-04-retry-edge.ibci`（已转 PASS） |
| `DOC_ISSUE-30` | `docs/syntax/09_intent_system.md` 称 `@!` + run_batch 仅首调用生效；实现（28540336）对批内每个调用注入 one-shot 意图 | **已同步（2026-08-15）**：文档改为“当前实现为批内每个调用独立 fork 意图快照” | `T08/.../D3-08-runbatch-oneshot-obs.ibci` |
| `BOUNDARY-LLM-2` | LLM 函数 `-> void` 编译通过但运行期 `LLMParseError`，文档未声明支持 | **已解决（2026-08-19，P4c 机制演进）**：`-> void` 是旧 `llm func` 语法特性，随 P4c llm 函数机制删除而消失；新 llm 可调用类以 `expected_type` 声明输出目标（无声明按 str 解析、副作用调用用行为表达式），边界已文档化于 `docs/syntax/08_llm_callable.md` | `T08/.../D4-04-llmfunc-void.ibci`（已迁 llm 可调用类形态） |
| `BOUNDARY-LLM-3` | `stream_call` / `stream_channel` 后 `ai.get_current_call_info()` 为空，观测 API 未覆盖流式调用 | **已登记（KNOWN_LIMITS §十五）**：流式调用不入观测为已知边界，观测 API 对流式覆盖属待评估 | `T08/.../D5-08-stream-call-info.ibci` |
| `BOUNDARY-LLM-4` | llm_callable 契约违约（返回非 dict / 签名不符）以原始 Python traceback 直漏、无语言级诊断码 | **已处置（2026-08-21）**：引入 `RUN_LLM_CALLABLE` 诊断码，违约点改抛带码 InterpreterError（`Runtime Error: [ERROR][RUN_LLM_CALLABLE]: ...`），VM 调用处理器透传带码错误不包装；15_diagnostics/catalog 登记；T10 守卫改 expect-code | `T10/.../T10-G1~G4-*.ibci`（expect-code RUN_LLM_CALLABLE） |
| `BOUNDARY-LLM-5` | 进程内 mock（ai.set_mock_mode）下 `get_current_call_info()` 无 `sys_prompt` 键（真实模式有） | **已登记（2026-08-21，T13）**：观测设施缺口（意图三层 intents 始终可用，T13 已改用其断言）；供阶段 C 文档复核评估观测 API 对 mock 的覆盖。**补充实证（2026-09-05，T08 复跑）**：真实模式下 dispatch-before-use 的 future 若从未被语言层消费，单写槽停留在 dispatch 快照形态（同样无 `sys_prompt`，response 为空）——resolve 点覆盖只在消费时发生；用例先消费再读即可观测完整 call_info（D3-09/D3-10 已修用例消费顺序） | `T13/.../T13-I-M1-*.ibci` + `T08/.../D3-09/D3-10` |
| `KERNEL_ISSUE-LLM-5` | llm 可调用类 + 声明用户类赋值竞态（约 1/6 复现）：`Resp r = inst()`（expected_type + `__from_prompt__`）偶发绑定未解包的 llm 结果包装物——声明类型名特化渲染 `Resp(result='OK')`、`.text` 读不到用户字段；非确定（同文件多次运行时好时坏） | **已登记（2026-09-05，T08 复跑实证）**：待根因定位（疑似赋值绑定点的特化 rebind 与 expected_type 解包的竞争）；复现 = 该用例经 harness 反复运行 | `T08/.../D4-05-llmfunc-userclass.ibci`（RR-3 失败日志） |
| `KERNEL_ISSUE-IMPORT-2` | 模块 `import` 解析锚定 **project_root** 而非入口文件目录：多文件用例（main.ibci + 同目录模块）在 project_root ≠ 用例目录时 `DEP_MODULE_NOT_FOUND`；历史经"root=用例目录"的隐性耦合而通过，配置单源收敛后暴露 | **已定位（2026-09-05）**：与 ref C3"用户模块路径解析未文档化"直接关联——锚点语义（project_root vs entry_dir 及搜索顺序）待 C3 设计时统一定案并文档化；短期 harness 按"目录型用例 = 自包含工程"以用例目录为 root 运行 | `T06/.../D1-02`（DEP_MODULE_NOT_FOUND 日志） |

## 三、登记前分诊闸门（强制，见 CLASSIFICATION §四）

> 非 PASS 用例在登记前必须对照 `docs/KNOWN_LIMITS.md` 与设计文档分诊。
> 命中已知限制 ≠ 免罪——登记为 `LIMIT` 并进待修候选池（先例：G3 原为 KNOWN_LIMITS §六，实证后按真实缺陷修复）。

## 四、运行入口

```bash
python trials/_toolkit/run_one.py cases/<case>.ibci \
    --label <case_id> --dim <dim> --doc <章节> --expected <描述> \
    --timeout <秒，必填> --root trials/T<nn>_<主题>
```
