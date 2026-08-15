# T02_enum_import — REGISTER（结果总表）

> 2026-08-12。enum 补全 + 嵌套包 import + 运算符覆写批次落地后自建用户试用。
> 证据：`logs/<case>.log` + `logs/register.jsonl`。分类体系见 `DESIGN.md` §四。
> **规范（2026-08-13 迁移）**：本套现位于 `trials/T02_enum_import/`；分类/级别/编号
> 规范见 `trials/_toolkit/CLASSIFICATION.md`。本套无缺陷编号（全部 PASS/LIMIT）。
> **断言重构（2026-08-13）**：用户原则——套件不冻结历史资产，问题直接重构（唯一底线：
> 不为规避缺陷改套件）。T3/T4/T5 真实 LLM 用例断言从"固定成员"改为"映射有效性"——
> 具体成员由模型选择非确定（本次重跑 T3 输出 ERR→500、T4 输出 BLUE），断言改为验证
> 成员名→值映射契约成立（`c == 任一成员` 为 True），消除 LLM 非确定性导致的假 HARNESS。

## 一、运行环境

| 项 | 值 |
|----|-----|
| LLM 端点 | `http://localhost:1234/v1`（LM Studio，qwen3.6-35b-a3b 非思考模型） |
| 配置 | `api_config.json`（providers/models/defaults，reasoning:false，timeout=30，retry=3） |
| 保护 | 两层死循环保护：OS 进程级 SIGKILL + LLM 调用超时 |
| 全量 pytest | **2307 passed / 1 skipped**（试用零回归，未改内核） |

## 二、结果总表

| # | 用例 | 维度 | 结果 | 输出（节选） | 分类 |
|---|------|------|------|-------------|------|
| T1 | T1-enum-iter.ibci | 枚举 | ✅ | RED / GREEN / BLUE / --- / found-green | PASS |
| T2 | T2-enum-len.ibci | 枚举 | ✅ | 3 / True | PASS |
| T3 | T3-enum-int-llm.ibci | 枚举+真实LLM | ✅ | mapped=True（成员名→值映射契约：OK→200 / ERR→500，2026-08-13 重构断言） | PASS |
| T4 | T4-enum-str-llm.ibci | 枚举+真实LLM | ✅ | mapped=True（str 枚举成员名→值映射契约，2026-08-13 重构断言） | PASS |
| T5 | T5-enum-value-ne-name.ibci | 枚举+真实LLM | ✅ | mapped=True（值≠名映射契约 ACTIVE→a / INACTIVE→i，2026-08-13 重构断言） | PASS |
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
