# INDEX — IBCI 试用地基跨套索引

> 规范：`_toolkit/CLASSIFICATION.md`（分类/级别/编号/骨架/运行入口单一权威源）。
> 新增试用地基必须：遵循命名 `T<nn>_<主题>`、引用 `_toolkit/run_one.py`（软链非复制）、
> 更新本索引、缺陷编号全局唯一。

## 一、试用地基一览

| 套 | 主题 | 日期 | 用例 | 结果概览 | 主要缺陷（新编号） |
|----|------|------|------|----------|--------------------|
| `T01_llm_full` | 真实 LLM 全语法/压力/批判试用（原 `_LLM_TRIAL_20260812`） | 2026-08-12 | 104 cases / 113 运行 | D1-D3 全过；A1-A5/C1-C4 验证 | `KERNEL_ISSUE-VM-1`~`CONFIG-1`（已修）、`DOC-ISSUE-001~007`（已处置）、`BOUNDARY-*-*`（已记录） |
| `T02_enum_import` | enum 补全 + 嵌套包 import 用户试用（原 `_LLM_TRIAL_ENUM_IMPORT_20260812`） | 2026-08-12 | 9 例 | 全 PASS / 1 LIMIT（2026-08-13 重构断言，映射有效性） | 无 |
| `T03_user_class_generics` | 用户类泛型压力/恶意试用（原 `_GENERICS_TRIAL_20260812`） | 2026-08-12 | 30 运行 | 23 PASS + 6 GUARD + 1 HARNESS（smoke；2026-08-14 重跑 D2-07 chan 迁普适写法转 PASS） | `KERNEL_ISSUE-GEN-1/2/3`、`BOUNDARY-GEN-1`（已修）、`KERNEL_ISSUE-GEN-6`（**已修 2026-08-13**） |
| `T04_generics_fix_regression` | 泛型修复回归试用（原 `_GENERICS_TRIAL_FIX_20260812`） | 2026-08-12 | 33 例 | 26 PASS + 7 GUARD + 1 HARNESS（smoke；2026-08-14 重跑 R5-03 chan 迁普适写法转 PASS） | `KERNEL_ISSUE-GEN-4`（已修）、`BOUNDARY-GEN-2`（已修，用例重构核销）、`KERNEL_ISSUE-GEN-5`（**已修 2026-08-13**） |
| `T05_critical_stress` | 批判性压力试用（跨模块类表 module 化后内核 + 真实 LLM + 文档全量核验） | 2026-08-14 | 40 用例 | 37 PASS + 1 GUARD + 2 KERNEL_ISSUE | `KERNEL_ISSUE-CROSSMOD-THREAD-1`（**已核销 2026-08-14，T07 D1-10 转 PASS**）、`KERNEL_ISSUE-OPTIONAL-ISNONE-1`（**已核销 2026-08-14，D2-03 转 PASS True|True|False**）、`DOC_ISSUE-1~23`（代码联动项已修，文档部分已治理） |
| `T06_class_identity` | 统一类身份模型回归 + 真实试用（Task1 S1-S4 根治验证 + T05 KI-1 核销） | 2026-08-14 | 20 用例 | 18 PASS + 2 KERNEL_ISSUE（同一根因） | `KERNEL_ISSUE-CROSSMOD-LLM-1`（**已核销 2026-08-14，T07 D3 重验**） |
| `T07_fixes_critical_stress` | 四项修复批判性对抗 + 旧套件 T01-T06 全量重跑（用户强调） + 泛型边界复测 | 2026-08-14 | 43 用例 + 旧套件 238 重跑 | 28 PASS + 12 GUARD + 3 KERNEL_ISSUE；旧套件 202 PASS + 24 GUARD + 1 LIMIT + 1 KERNEL_ISSUE(陈旧断言) + 9 HARNESS | `KERNEL_ISSUE-OPTIONAL-SCOPE-1`、`KERNEL_ISSUE-OPTIONAL-CONTAINER-1`、`KERNEL_ISSUE-ATTR-READ-1`（均待修，本任务只登记） |

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

### 域 OPTIONAL/ATTR（T07，2026-08-14 新登记，本任务只登记不修复）

| 新 | 主题 | 状态 | 触发用例 |
|----|------|------|----------|
| `KERNEL_ISSUE-OPTIONAL-SCOPE-1` | 函数作用域内 Optional 先 None 后赋值，unwrap()/is_some() 报 `Object of type 'None'`（顶层/lambda 正常，文档 §8"任何路径可用"不成立） | 待修（P1） | `T07/.../D2-09.ibci` |
| `KERNEL_ISSUE-OPTIONAL-CONTAINER-1` | Optional[list[int]] 有值包装后 len()/下标不可用（`no method 'len'`/`'__getitem__'`） | 待修（P1） | `T07/.../D2-10.ibci` |
| `KERNEL_ISSUE-ATTR-READ-1` | 未声明属性读取静默返回 None（仅调用路径报 RUN_ATTRIBUTE_ERROR，15_diagnostics 触发条件不符） | 待修（P1） | `T07/.../D1-13.ibci` |

### 域 CHAN（BOUNDARY，2026-08-14 记录）

| 编号 | 主题 | 状态 |
|------|------|------|
| `BOUNDARY-CHAN-ARGS-1` | `chan(T, name, ...)` 的 T 实参传**特化类对象**（如 `chan(Box[int], “message”)`）时特化实参被降级为裸类（`chan[Box]`，type() 实证）；裸类型实参（`chan(str, “stream”)` → `chan[str]`）与无参声明式（`chan[E] ch = chan()`）均正常。普适写法 = 类型在声明处，构造只传运行时参数。文档 `14_concurrency.md` 宜补充说明 | 记录（非缺陷，待文档同步） |
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

## 三、登记前分诊闸门（强制，见 CLASSIFICATION §四）

> 非 PASS 用例在登记前必须对照 `docs/KNOWN_LIMITS.md` 与设计文档分诊。
> 命中已知限制 ≠ 免罪——登记为 `LIMIT` 并进待修候选池（先例：G3 原为 KNOWN_LIMITS §六，实证后按真实缺陷修复）。

## 四、运行入口

```bash
python tasks_docs/trials/_toolkit/run_one.py cases/<case>.ibci \
    --label <case_id> --dim <dim> --doc <章节> --expected <描述> \
    --timeout <秒，必填> --root tasks_docs/trials/T<nn>_<主题>
```
