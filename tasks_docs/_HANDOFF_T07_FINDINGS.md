# 交接：T07 新发现三项 P1 修复 + 文档同步（下一 session 主任务）

> 2026-08-14 编制。承接 T07 批判性对抗试用 + 旧套件全量重跑（`trials/T07_fixes_critical_stress/`，
> 43 用例 28 PASS + 12 GUARD + 3 KERNEL_ISSUE；旧套件 238 用例重跑零回归）。
> **用户指示（2026-08-14）：先登记任务，交接给下一 session 接手；本任务为代码修复任务**
> （T07 试用阶段纪律已解除——试用只记录，修复是下一 session 的事）。
>
> 基线：unsafe-vibe-dev HEAD a63a692b，全量 2665 passed / 1 skipped。
> LLM 服务在线：qwen3.6-35b-a3b @ 127.0.0.1:1234（思考已禁用，响应 <1-2s）。

---

## 〇、接手起点

1. 读本文件 + `tasks_docs/NEXT_STEPS.md` + `tasks_docs/PENDING_TASKS.md` §〇（本交接三行 🟡 置顶）
2. 读 `tasks_docs/trials/T07_fixes_critical_stress/REGISTER.md` §二（触发用例/证据日志）+ `REPORT.md`
3. 复现触发用例：`python tasks_docs/trials/_toolkit/run_one.py cases/D2-09.ibci --label X --dim D --doc '' --expected '' --timeout 60 --root tasks_docs/trials/T07_fixes_critical_stress --repo-root <仓库根>`
4. 每项修复走 code-workflow Phase 0-5 + 全量 pytest 零回归 + tests/ 判别性回归（Phase D 收敛义务）+ 回归试用核销
5. 全程本地 commit、禁 push；不触碰 main。

---

## 一、三项 P1 KERNEL_ISSUE 修复交接

> 三项均围绕 KI-2 统一 Optional 值模型改动面（47 文件 +1617 行），验证用户此前警告
> "Optional 可能藏更深根源"。**根因待下一 session 分析（本交接只给行为事实与修复方向建议，
> 不查内核）**。修复须含 tests/ 判别性回归 + 触发用例核销（PHASE_D）。

### 1.1 KERNEL_ISSUE-OPTIONAL-SCOPE-1（P1）— 函数作用域内 Optional 先 None 后赋值，unwrap()/is_some() 报 Object of type None

- **触发用例**：`trials/T07_fixes_critical_stress/cases/D2-09.ibci`（expect-out: 405 未达成，exit 1）
- **最小复现**：
  ```
  func work() -> int:
      Optional[int] tag = None
      tag = 405
      return tag.unwrap()
  print(work())   # → [ERROR][RUN_ATTRIBUTE_ERROR]: Object of type 'None' has no method '__call__'
  ```
- **行为事实矩阵（探针实证，2026-08-14）**：
  | 路径 | 代码 | 结果 |
  |------|------|------|
  | 模块顶层 | `Optional[int] x = 5; x.unwrap()` | 5 ✓ |
  | 模块顶层 | `Optional[int] tag = None; tag = 405; tag.unwrap()` | 405 ✓（u3） |
  | 函数内 | `Optional[int] tag = None; tag = 405; tag.unwrap()` | **RUN_ATTRIBUTE_ERROR**（v1/v2） |
  | 函数内 | `Optional[int] tag = None; tag = 405; return tag` | 405 ✓（t5，int 返回上下文自动解包） |
  | 函数内 | `tag.is_some()`（先 None 后赋值） | **RUN_ATTRIBUTE_ERROR**（w3） |
  | lambda 捕获 | `x.is_some()`（x 外层 Optional） | True ✓（D2-07） |
  | 参数路径 | `f(Optional[int] p = None) ... p.unwrap()` | 5 ✓（t10） |
  | 容器元素 | `list[Optional[int]] xs=[5]; xs[0].unwrap()` | 5 ✓（t9） |
  | 线程 worker | 函数内同代码 | ThreadFailed（内部同 RUN_ATTRIBUTE_ERROR） |
  | 空值 unwrap | `Optional[int] tag = None; tag.unwrap()` | RUN_ATTRIBUTE_ERROR（v3，空值解封行为未定义） |
- **核心矛盾**：函数内 `return tag`（int 上下文）正常返回 405，但函数内 `tag.unwrap()`/`tag.is_some()`
  报 "Object of type 'None'"——同一变量在"方法调用"路径与"值返回"路径读取结果不同。
- **文档依据**：`docs/architecture/03_type_system.md` §8 "is_none()/is_some()/unwrap()/or_else() **在任何路径可用**"。
- **修复方向建议（行为观察推断，非内核结论）**：
  1. 检查函数作用域内局部 Optional 变量"先 None 后赋值"后变量读取路径的包装对象身份（可能重新赋值未走
     `wrap_optional` 单一权威，或方法调用接收者解析为 None/裸值）；
  2. 与顶层/lambda/参数/容器路径对齐（这些路径均正常）；
  3. 空值 unwrap 行为需明确定义（报错？返回 None？文档同步）。
- **判别性回归建议**：函数内 `tag=405; tag.unwrap()` == 405；函数内 `tag.is_some()` == True；
  线程 worker 内同组合；顶层/函数对照。

### 1.2 KERNEL_ISSUE-OPTIONAL-CONTAINER-1（P1）— Optional[list[int]] 有值包装后 len()/下标不可用

- **触发用例**：`trials/T07_fixes_critical_stress/cases/D2-10.ibci`（expect-out: 3 未达成，exit 1）
- **最小复现**：
  ```
  Optional[list[int]] b = [1, 2, 3]
  print(b is None)   # False（有值包装正常）
  print(len(b))      # → RUN_ATTRIBUTE_ERROR: Object of type 'Optional[list[int]]' has no method 'len'
  print(b[1])        # → 无 '__getitem__'
  ```
- **行为事实**：`b is None` False、`len(b)`/`b[1]` 均报 no method；同一容器无 Optional 包装时正常。
- **文档依据**：`docs/architecture/03_type_system.md` §8 "Optional[T] 接受 T" + 统一值模型（容器元素亦包装）——
  用户按 T 语义使用容器方法必然失败；文档未说明需先解封。
- **修复方向建议**：
  1. Optional 包装对象委托底层容器方法（len/`__getitem__` 等透传），或
  2. 明确"容器方法需先解封（unwrap/or_else）"并文档同步（但 `unwrap` 尚有 SCOPE-1 缺陷，需联动）；
  3. 对齐统一值模型承诺（任意路径可用）。
- **判别性回归建议**：`Optional[list[int]]` 有值 `len(b)==3`、`b[0]` 访问；None 值时 len/下标行为定义。

### 1.3 KERNEL_ISSUE-ATTR-READ-1（P1）— 未声明属性读取静默返回 None（仅调用路径报 RUN_ATTRIBUTE_ERROR）

- **触发用例**：`trials/T07_fixes_critical_stress/cases/D1-13.ibci`（expect-code RUN_ATTRIBUTE_ERROR 未达成，exit 0）
- **最小复现**：
  ```
  class Point:
      int x
      func __init__(self, int x) -> auto:
          self.x = x
  Point p = Point(1)
  print(p.y)           # → None（exit 0，静默！）
  print(p.missing())   # → RUN_ATTRIBUTE_ERROR: Object of type 'None' has no method '__call__'
  ```
- **行为事实**：属性**读取**路径返回 None（静默错误值）；**调用**路径报 RUN_ATTRIBUTE_ERROR。
- **文档依据**：`docs/syntax/15_diagnostics.md` RUN_ATTRIBUTE_ERROR "触发条件：访问对象不存在的属性/方法"。
- **修复方向建议**：
  1. 属性读取路径对未声明成员报 RUN_ATTRIBUTE_ERROR（根治静默错误值，符合工作模式定论）；
  2. 或文档精确化"读取返回 None、调用报错"——但静默错误值按工程原则应根治为报错；
  3. 注意与幽灵码修复（2026-08-14 只覆盖调用路径）的关联。
- **判别性回归建议**：未声明属性读取报 RUN_ATTRIBUTE_ERROR（主线程 + 线程内）；已声明属性读取不受影响。

---

## 二、BOUNDARY-CHAN-ARGS-1（记录 + 文档同步，非缺陷）

- **登记**：`trials/INDEX.md` 域 CHAN（2026-08-14）。
- **事实**：`chan(T, name, ...)` 的 T 实参传**特化类对象**（`chan(Box[int], "message")`）被降级为裸类
  （`chan[Box]`，type() 实证）；裸类型实参（`chan(str, "stream")` → `chan[str]`）与无参声明式
  （`chan[E] ch = chan()`，含 await）均正常。
- **定性**：按"朴素普适性（成熟语言惯例：类型在声明处、构造只传运行时参数）"核实为**非内核缺陷**——
  普适写法全通；T03 D2-07 / T04 R5-03 用例已迁普适写法转 PASS。
- **文档同步建议**：`docs/syntax/14_concurrency.md` `chan(T, name, ...)` 条目补充说明：T 宜传裸类型类对象；
  特化类对象实参当前降级为裸类，应使用声明式 `chan[E] ch = chan()`。

---

## 三、DOC-24~28 文档同步批次（正文修改待用户确认后执行）

| # | 文件 | 内容 | 联动 |
|---|------|------|------|
| DOC-24 | arch/03_type_system §8 | "unwrap/is_some/is_none 在任何路径可用"不成立 | 与 SCOPE-1 修复联动 |
| DOC-25 | arch/03_type_system §8 | Optional 容器方法不可用未说明 | 与 CONTAINER-1 修复联动 |
| DOC-26 | 15_diagnostics RUN_ATTRIBUTE_ERROR | 触发条件与实现不符（读取路径静默 None） | 与 ATTR-READ-1 修复联动 |
| DOC-27 | KNOWN_LIMITS §10.2 | 建议补 qualified 路径实证（裸名退化表述仍成立） | 独立 |
| DOC-28 | 14_concurrency | chan(T,...) 补充特化类对象说明 | 同 BOUNDARY-CHAN-ARGS-1 |

> 处理纪律：doc-governance Phase 0-8，修文档保持实现（先例：DOC-1/2 mock 值语义决断）；
> DOC-24/25/26 在对应 KI 修复后同步措辞（修复改变行为则文档跟随，避免二次漂移）。

---

## 四、其它交接（长期项指针，非本轮主任务）

- 供应商感知模型思考禁用机制（P2，独立设计窗口）：`PENDING_TASKS` + `_toolkit/LLM_SERVICE.md` §五。
- 5 处旧套件陈旧断言**已修复**（2026-08-14 用户授权，见 WORKLOG）——后续若再遇陈旧断言，
  按 PHASE_D "语义变更→用例重构为新语义"处理。
- 试用体系：`trials/INDEX.md` 缺陷编号全局唯一；新缺陷从 `KERNEL_ISSUE-<域>-<n>` 续编。

## 五、验证基线

- 全量 pytest：`~/miniconda3/envs/ibci/bin/python -m pytest tests/`（当前 2665 passed / 1 skipped）。
- 回归试用核销：触发用例 expect-out 达成 → harness 自动判 PASS 待核销 → INDEX 状态更新。
- 每项修复 = 根因修复 + tests/ 判别性回归 + 触发用例核销（PHASE_D 双交付义务）。

---
全程本地 commit、禁 push；不触碰 main。
