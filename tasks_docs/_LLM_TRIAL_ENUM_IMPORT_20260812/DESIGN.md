# _LLM_TRIAL_ENUM_IMPORT_20260812 — enum 补全 + 嵌套包 import + 运算符覆写 用户试用

> 2026-08-12 编制（enum 补全 / 嵌套包 import / 运算符覆写批次落地后）。
> 本任务 = **试用与记录任务**（用户要求"内核代码修改结束后自建新试用任务做用户试用覆盖"）。
> 覆盖本次新增/变更能力在真实用户用法下的行为；**发现的缺陷只记录、登记，不在本任务修复**。

## 一、约束（沿用 2026-08-12 定案）

| 约束 | 内容 |
|------|------|
| 死循环保护 | 所有用例经 `harness/run_one.py`（OS 进程级 SIGKILL + `--max-inst` + LLM 调用超时）三层兜底；timeout 必需参数，harness 无超时不运行 |
| 记录优先 | logs/<case>.log + register.jsonl + REGISTER.md；只记录不修复 |
| 文档为主要来源 | 按 docs/（KNOWN_LIMITS §二 / 05_functions / 11_modules / 09_intent_system 等）撰写用例 |
| 禁 push | 全程本地 commit；禁 push |

## 二、覆盖范围（本次内核变更）

| 能力 | 变更批次 | 文档 |
|------|---------|------|
| 非 str 枚举 LLM 集成（成员名→值映射） | enum 补全 | KNOWN_LIMITS §二 |
| str 枚举 LLM 集成回归（值==名） | enum 补全 | KNOWN_LIMITS §二 |
| str 枚举值≠名（成员名→值） | enum 补全 | KNOWN_LIMITS §二 |
| 枚举迭代 `for v in Color:` | enum 补全 | KNOWN_LIMITS §二 |
| 枚举数量 `len(Color)` | enum 补全 | KNOWN_LIMITS §二 |
| 枚举自定义方法边界（值模型） | enum 补全（文档化） | KNOWN_LIMITS §二 §2.4 |
| 嵌套包 `import subpkg.util` + 成员访问 | 嵌套包 import 根治 | 11_modules §11.1 |
| 同包多导入合并 | 嵌套包 import 根治 | 11_modules §11.1 |
| 用户类运算符覆写（比较/算术/一元/成员） | KNOWN_LIMITS §十四 #2 核对 | KNOWN_LIMITS §十四 |

## 三、用例清单

| # | 用例 | 维度 | 说明 |
|---|------|------|------|
| T1 | cases/T1-enum-iter.ibci | 枚举 | `for v in Color:` 输出成员值 |
| T2 | cases/T2-enum-len.ibci | 枚举 | `len(Color)` 成员数 |
| T3 | cases/T3-enum-int-llm.ibci | 枚举+LLM | 非 str 枚举 LLM 输出成员名 → 值 200 + switch 命中（真实 LLM） |
| T4 | cases/T4-enum-str-llm.ibci | 枚举+LLM | str 枚举 LLM 回归（值==名） |
| T5 | cases/T5-enum-value-ne-name.ibci | 枚举+LLM | str 枚举值≠名 LLM 集成 |
| T6 | cases/T6-enum-method-boundary.ibci | 枚举边界 | 成员值上调用自定义方法 → 预期报错（LIMIT） |
| T7 | cases/T7-nested-import.ibci | 嵌套 import | `import subpkg.util` + `subpkg.util.util_fn()` |
| T8 | cases/T8-nested-multi-import.ibci | 嵌套 import | 同包多导入合并 |
| T9 | cases/T9-operator-override.ibci | 运算符 | 用户类 `==`/`+`/`<`/`in`/一元 覆写 |

## 四、确定性记录

- `logs/<case>.log`：完整运行证据（命令、退出码、超时、时长、stdout+stderr）。
- `logs/register.jsonl`：每例一行机械字段；分类/级别由试用者审阅后回填 REGISTER.md。
- `REGISTER.md`：结果总表（分类 + 严重级别 + 结论）。

## 五、执行

```bash
cd /home/haber/proj/intent-behavior-code-inter/tasks_docs/_LLM_TRIAL_ENUM_IMPORT_20260812
# 每例：
~/miniconda3/envs/ibci/bin/python harness/run_one.py cases/<case>.ibci \
  --label <LABEL> --dim ENUM/IMPORT/OP --doc <doc-ref> \
  --expected "<期望>" --timeout 90
```
