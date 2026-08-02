# 局部 import 审计 — 独立分支任务（技术债）

> **来源**：2026-08-02 用户裁定。无意义的局部 import、为打破循环导入而内联的 import（及同类 import 组织异味）属技术债，需独立分支核对分析。
> **状态**：待执行（独立分支，不与主线混置）
> **方法**：AST 全仓扫描局部 import（函数/方法体内 import）→ 逐处判定动机（循环导入打破 / 惰性可选依赖 / 无理由）→ 证据驱动处置；每批 `python -m pytest tests/` 全量零回归。
> **核验基准**：工作模式定论（禁止胶水/tricky——用局部 import 掩盖循环依赖即胶水变体）+ 依赖规则（kernel→base 单向，runtime→kernel）。

---

## 一、局部 import 全仓清单（AST 扫描，35 处）

> 标注：**【循环打破】**=内联以绕开模块级循环导入｜**【惰性依赖】**=可选/重依赖按需加载｜**【可提升】**=无循环风险，应移至顶层｜**【待核验】**=动机不明

### 1.1 循环导入打破（核心怀疑对象）

| # | 位置 | import | 判定 |
|---|---|---|---|
| L1 | `objects/kernel/base.py:31/32` | `from functions import` / `from ib_class import` | **循环打破**（base↔functions/ib_class 循环）。评估：用 TYPE_CHECKING + 延迟解析 / 重构依赖方向替代 |
| L2 | `objects/kernel/ib_class.py:165` | `from functions import` | **循环打破**（ib_class↔functions） |
| L3 | `kernel/spec/type_ref.py:128` | `from base import TypeKind` | **循环打破**（base↔type_ref 互导，已用函数内延迟）。可评估 TYPE_CHECKING 常量引用替代 |
| L4 | `kernel/spec/registry/_members.py:121` | `from base import TypeDef` | **循环打破** |
| L5 | `kernel/spec/registry/_runtime.py:90` | 相对导入 | **循环打破** |
| L6 | `interpreter/interpreter.py:466` | `from vm.vm_executor import` | **循环打破**（interpreter↔vm）。评估延迟属性引用替代 |
| L7 | `objects/kernel/user_functions.py:42/79/140` | `from ..primitives import` / `from ..cell import` / `from ..signals import` | **循环打破** |
| L8 | `shared/llm_result.py:56/130` | `from ..objects.primitives/kernel import` | **循环打破** |
| L9 | `runtime/path/install.py:36/40` | `import ibci_modules` / `import core` | **循环打破**（模块加载期） |
| L10 | `ibci_ai/core.py:298` | `from core.runtime.frame import` | **循环打破**（插件↔core） |

### 1.2 惰性可选依赖（设计内）

| # | 位置 | import | 判定 |
|---|---|---|---|
| L11 | `ibci_ai/core.py:83/154` | `from openai import OpenAI` | **惰性依赖**（openai 可选包，避免顶部硬依赖）——合理保留 |

### 1.3 无理由可提升（疑似异味）

| # | 位置 | import | 判定 |
|---|---|---|---|
| L12 | `interpreter/intrinsics/io.py:23` | `import sys`（重复 2 次） | **可提升**【已处置 2026-08-02：提升至模块顶部；实测仅 1 处局部 import，审计"重复 2 次"为陈旧标注，已修正】 |
| L13 | `semantic/passes/base_pass.py:58` | `import traceback` | **可提升**【已处置 2026-08-02：提升至模块顶部】 |
| L14 | `ibci_ai/core.py:454` | `import re` | **可提升**【已处置 2026-08-02：提升至模块顶部（顶部现含 `import re`）】 |

### 1.4 动机待核验

| # | 位置 | import | 判定 |
|---|---|---|---|
| L15 | `engine.py:119/123` | kernel_native_modules / file_impl | 待核验（可能构造期避免循环） |
| L16 | `extension/auto_discovery.py:56` | `from core.runtime.path import` | 待核验 |
| L17 | `semantic/context.py:117/118` | passes.prelude / base.enums | 待核验 |
| L18 | `bootstrap/kernel_native_modules.py:75` | `from kernel.host_interface import` | 待核验 |
| L19 | `loader/artifact_loader.py:69`、`bootstrapper.py:49`、`runtime_context.py:74`、`_declaration_visitors.py:86/316` | `from core.base.enums import` 等 | 待核验（base.enums 无循环风险，多数应可提升）【已处置 2026-08-02：base.enums 为叶子纯枚举模块，5 文件 6 处局部 import 全部提升至模块顶部；`context.py` 中仅提升 base.enums，`prelude` 局部 import 属真实循环打破，保留】 |
| L20 | `kernel/axioms/intent_context.py:24`、`intent.py:28` | `from core.kernel.spec.member import` | 待核验 |

---

## 二、我的工程经验补充判断（超出用户列举的两类）

1. **局部 import 是循环依赖的症状而非解药**：循环打破类（L1-L10）应优先重构依赖方向（下沉共享纯核心 / 接口上移），而非长期依赖内联 import 掩盖循环——后者属"胶水实现"变体，违反工作模式定论。逐处评估是否有比"内联 import"更正确的结构。
2. **TYPE_CHECKING + 延迟解析替代**：纯类型引用（TypeDef/IbSpec 等）应走 `if TYPE_CHECKING` 块 + 字符串注解，运行时零开销且不掩盖循环——L3/L4 为重点候选。
3. **性能路径重复 import**：函数体内 import 在 Python 有 `sys.modules` 缓存，名称解析开销小但非零；**热路径**（VM 循环 / 序列化 / 每符号调用）中的局部 import 应统计调用频次评估（L7 user_functions、L8 llm_result、L6 interpreter 为热路径）。
4. **重复局部 import**：同一函数/文件内多处重复 import 同一模块（`io.py:23` 同函数 2 次）——明确异味，应合并提升。
5. **延迟 import 的正确场景**：可选第三方依赖（openai）、巨型模块按需加载（引导期）、避免环的可接受兜底——这些是合法延迟 import 模式，保留并注释动机。
6. **模块级依赖清单可读性**：顶部 import 块是模块依赖契约；局部 import 破坏契约可读性（"这个模块到底依赖什么"不可一眼看清）——重构后应让顶部清单完整。

---

## 三、核验流程

1. 逐处判定动机（1.1 循环打破 / 1.2 惰性依赖 / 1.3 可提升 / 1.4 待核验），用"删除该局部 import、临时提升到顶部→全量测试"禁用验证确认循环风险是否真实。
2. 处置：可提升（L12-L14）直接提升；循环打破（L1-L10）逐处评估 TYPE_CHECKING 替代或依赖方向重构（方案需对照工作模式定论，禁止用更深的胶水）；待核验（L15-L20）定案后归入对应类。
3. 每批 `python -m pytest tests/` 全量零回归；收尾定案回写本清单。
