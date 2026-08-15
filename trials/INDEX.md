# INDEX — IBCI 试用地基跨套索引

> 规范：`_toolkit/CLASSIFICATION.md`（分类/级别/编号/骨架/运行入口单一权威源）。
> 新增试用地基必须：遵循命名 `T<nn>_<主题>`、引用 `_toolkit/run_one.py`（软链非复制）、
> 更新本索引、缺陷编号全局唯一。

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
| `T08_llm_pressure` | LLM 全能力真实压力试用（第一轮，本地 qwen） | 2026-08-15 | 41 例 | 32 PASS + 2 GUARD + 4 LLM_BEHAVIOR + 2 BOUNDARY + 1 LIMIT | `KERNEL_ISSUE-LLM-2`（**已修复**）、`KERNEL_ISSUE-LLM-3`（**已修复**）、`DOC_ISSUE-30`、`BOUNDARY-LLM-2`、`BOUNDARY-LLM-3` |

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

| 编号 | 主题 | 状态 | 触发用例 |
|------|------|------|----------|
| `KERNEL_ISSUE-LLM-2` | LLM 函数返回 `list[int]` / `dict[str,int]` 未按容器解析，默认退化为 str | **已修复（2026-08-15）**：`_get_expected_type_hint` 读取 returns `node_to_type` 覆盖 IbSubscript；Optional 保持旧路径。回归 `test_llm_basic.py::TestE2ELLMFunctionContainerReturn` | `T08/.../D4-01-llmfunc-typed.ibci`（已转 PASS） |
| `KERNEL_ISSUE-LLM-3` | `ai.set_retry(0)` + `llmexcept` 不抛 `LLMRetryExhaustedError`，把不确定容器赋给目标导致 `RUN_TYPE_MISMATCH` | **已修复（2026-08-15）**：`_retry_llm_uncertain` 在 `max_retry<=0` 时立即抛耗尽。回归 `test_llmexcept.py::TestE2ELLMExceptZeroRetry` | `T08/.../D6-04-retry-edge.ibci`（已转 PASS） |
| `DOC_ISSUE-30` | `docs/syntax/09_intent_system.md` 称 `@!` + run_batch 仅首调用生效；实现（28540336）对批内每个调用注入 one-shot 意图 | **已同步（2026-08-15）**：文档改为“当前实现为批内每个调用独立 fork 意图快照” | `T08/.../D3-08-runbatch-oneshot-obs.ibci` |
| `BOUNDARY-LLM-2` | LLM 函数 `-> void` 编译通过但运行期 `LLMParseError`，文档未声明支持 | 记录，待评估 | `T08/.../D4-04-llmfunc-void.ibci` |
| `BOUNDARY-LLM-3` | `stream_call` / `stream_channel` 后 `ai.get_current_call_info()` 为空，观测 API 未覆盖流式调用 | 记录，待评估 | `T08/.../D5-08-stream-call-info.ibci` |

## 三、登记前分诊闸门（强制，见 CLASSIFICATION §四）

> 非 PASS 用例在登记前必须对照 `docs/KNOWN_LIMITS.md` 与设计文档分诊。
> 命中已知限制 ≠ 免罪——登记为 `LIMIT` 并进待修候选池（先例：G3 原为 KNOWN_LIMITS §六，实证后按真实缺陷修复）。

## 四、运行入口

```bash
python trials/_toolkit/run_one.py cases/<case>.ibci \
    --label <case_id> --dim <dim> --doc <章节> --expected <描述> \
    --timeout <秒，必填> --root trials/T<nn>_<主题>
```
