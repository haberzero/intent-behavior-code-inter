# VERIFICATION — 完整 IBCI 真实代码试用核查（2026-08-14）

> 核查任务（非修复）：确认近期代码改动对已知试用代码的影响。近期改动：
> ① 函数/可调用类型身份架构断层根治；② fn/callable 方向 A（callable 内部化 + fn 参数/返回
> 强制可调用）；③ CALLABLE_SIG（fn[(...)->...]）签名模型根治。
> 试用地基全量重跑：T01-T07 全部已知用例。

## 一、方法与范围

- **运行工具**：`tasks_docs/trials/_toolkit/run_batch.py`（mock 批 + LLM 批）+ `run_one.py`
  （子目录用例，--root=用例目录）。
- **mock 批次**：run_batch --mock-only（T01-T07 平铺用例），parallel=8。
- **真实 LLM 批次**：run_batch --llm-only（T01/T02/T07 expect-llm）+ T05/T06 子目录用例
  （--root=用例目录，T06 为真实 LLM / T05 为 mock）。
- **判定**：用例头部 expect-class 断言，harness 自动判定。
- **LLM 服务**：qwen3.6-35b-a3b @ 127.0.0.1:1234（在线，reasoning=false）。

## 二、结果总表（全量）

| 套 | mock | LLM | 结果（与 INDEX 期望对比） |
|----|------|-----|---------------------------|
| T01_llm_full | 47：37 PASS + 6 GUARD + 4 HARNESS（smoke/helper/deadloop 支持/探针文件） | 57：55 PASS + 2 GUARD | ✅ 与 INDEX 一致 |
| T02_enum_import | 6：5 PASS + 1 LIMIT（T6 枚举方法边界） | 3：2 PASS + 1 **LLM_BEHAVIOR**（T5 间歇失败） | ✅ 一致 + T5 记录 |
| T03_user_class_generics | 30：23 PASS + 6 GUARD + 1 HARNESS（smoke_deadloop 故意超时） | — | ✅ 与 INDEX 一致 |
| T04_generics_fix_regression | 35：26 PASS + 8 GUARD + 1 HARNESS（smoke_deadloop） | — | ✅ 与 INDEX 一致 |
| T05_critical_stress | 平铺 19：18 PASS + 1 GUARD；子目录 13：**13 PASS** | — | ✅ 一致（含 D1-10 CROSSMOD-THREAD-1 核销） |
| T06_class_identity | 子目录 20：**20 PASS**（真实 LLM 混合） | — | ✅ 一致（含 D3-02 CROSSMOD-LLM-1 核销） |
| T07_fixes_critical_stress | 44：32 PASS + 12 GUARD | 7：7 PASS | ✅ 一致（OPTIONAL-SCOPE/CONTAINER/ATTR-READ 核销） |

**结论：近期代码改动（方向 A / CALLABLE_SIG / 断层根治）对已知试用代码零回归**——
所有 INDEX 期望的 PASS/GUARD/LIMIT 用例保持原分类，所有核销触发用例转 PASS。

## 三、发现

### 3.1 过期试用代码（已更新，4 例核销触发用例）
以下触发用例的缺陷已修复、当前 PASS，但 .ibci 仍声明 `expect-class: KERNEL_ISSUE`——
已更新为 `expect-class: PASS`（缺陷触发用例保留，契约更新为修复后正确行为）：
- `T05/cases/D1-10/main.ibci`（CROSSMOD-THREAD-1，期望 405|thread-ok）
- `T07/cases/D1-13.ibci`（ATTR-READ-1，期望 RUN_ATTRIBUTE_ERROR + nonzero）
- `T07/cases/D2-09.ibci`（OPTIONAL-SCOPE-1，期望 405）
- `T07/cases/D2-10.ibci`（OPTIONAL-CONTAINER-1，期望 3）

### 3.2 真实 LLM 间歇失败（深挖后定性为机制 bug，2026-08-14 后续调查）
- **T02 T5-enum-value-ne-name**：`Status c = @~...~` 枚举成员名→底层值映射，真实 LLM
  间歇输出格式偏离 → 严格解析器 LLMParseError（3 次 2 败 1 过）。
- **深挖结论**：**非单纯模型非确定性**——实证为机制 bug：枚举 `__outputhint_prompt__`
  （"Reply with exactly one of: ACTIVE, INACTIVE."）**未注入提示词**（`_get_llmoutput_hint`
  裸名 resolve 断链，S2/S5 module 化后注入端未升级；实际 sys_prompt 无 `[输出格式要求]`），
  加上三结构性弱点（程序化调用纪律缺失 / 期望类型不注入 / retry 无自动错误回喂）。
  详见 `_HANDOFF_LLM_PROMPT_MECHANISM.md`。记录不修复（核查任务纪律）。

### 3.3 无新增内核缺陷 / 边界 / 文档问题
本次全量重跑未发现近期改动引入的新 KERNEL_ISSUE / BOUNDARY / DOC_ISSUE。

## 四、试用代码卫生（用户要求核对）

- 全量检查未发现"为绕过 IBCI 缺陷书写的特定代码"——已知用例均为一般编程语言
  体验/习惯导向（函数/容器/泛型/OOP/并发/LLM 集成等普适场景）。
- 缺陷触发用例（KERNEL_ISSUE 触发类）忠实保留其场景，仅契约随修复更新为
  期望正确行为（核销），非规避。
- 已确认无 `callable` 用户类型残留使用（方向 A 无破坏面）。

## 五、操作记录

- 全量 mock + LLM 批次运行，日志/register 落各套 logs/。
- 4 例过期触发用例 .ibci 更新（expect-class KERNEL_ISSUE → PASS）。
- INDEX.md 同步（见 §二）。
