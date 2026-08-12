# _LLM_TRIAL_ENUM_IMPORT_20260812 — REGISTER（结果总表）

> 2026-08-12。enum 补全 + 嵌套包 import + 运算符覆写批次落地后自建用户试用。
> 证据：`logs/<case>.log` + `logs/register.jsonl`。分类体系见 `DESIGN.md` §四。

## 一、运行环境

| 项 | 值 |
|----|-----|
| LLM 端点 | `http://localhost:1234/v1`（LM Studio，qwen3.6-35b-a3b 非思考模型） |
| 配置 | `api_config.json`（providers/models/defaults，reasoning:false，timeout=30，retry=3） |
| 保护 | 三层死循环保护：OS 进程级 SIGKILL + `--max-inst` + LLM 调用超时 |
| 全量 pytest | **2307 passed / 1 skipped**（试用零回归，未改内核） |

## 二、结果总表

| # | 用例 | 维度 | 结果 | 输出（节选） | 分类 |
|---|------|------|------|-------------|------|
| T1 | T1-enum-iter.ibci | 枚举 | ✅ | RED / GREEN / BLUE / --- / found-green | PASS |
| T2 | T2-enum-len.ibci | 枚举 | ✅ | 3 / True | PASS |
| T3 | T3-enum-int-llm.ibci | 枚举+真实LLM | ✅ | **200 / got-ok**（模型输出成员名 OK → 映射为值 200 → switch 命中） | PASS |
| T4 | T4-enum-str-llm.ibci | 枚举+真实LLM | ✅ | RED / False（c=RED≠GREEN，正确） | PASS |
| T5 | T5-enum-value-ne-name.ibci | 枚举+真实LLM | ✅ | **a / True**（模型输出成员名 ACTIVE → 映射为值 "a"） | PASS |
| T6 | T6-enum-method-boundary.ibci | 枚举边界 | ⚠ 预期报错 | `Object of type 'None' has no method '__call__'` | **LIMIT**（KNOWN_LIMITS §二 §2.4 文档化边界） |
| T7 | T7-nested-import.ibci | 嵌套 import | ✅ | util-value / 7（`import subpkg.util` + 成员访问） | PASS |
| T8 | T8-nested-multi-import.ibci | 嵌套 import | ✅ | c-value / d-value（同包多导入合并） | PASS |
| T9 | T9-operator-override.ibci | 运算符 | ✅ | True/3/True/-1/True/False/True（`is` 身份比较 False/True） | PASS |

## 三、结论

- **enum 补全全部实证**：迭代/数量/非 str LLM 集成（真实模型成员名→值映射）/str 值≠名映射均正常。
- **嵌套包 import 根治实证**：`import subpkg.util` + 成员访问、3 层嵌套、同包多导入合并均正常。
- **运算符覆写**：比较/算术/一元/成员覆写正常；`is` 恒为身份比较（Python 一致）。
- **T6 枚举自定义方法**：值模型下成员值是底层值非实例 → 方法不可调用，属 KNOWN_LIMITS §二 §2.4
  文档化设计边界（实例化枚举为未来设计方向）。
- **无新增缺陷**：本次试用未发现新 KERNEL_ISSUE / DOC_ISSUE。

## 四、遗留

- 实例化枚举（成员携带 name/value 与方法）为设计候选，独立设计窗口（见 `tasks_docs/_code_enum_completion.md`）。
