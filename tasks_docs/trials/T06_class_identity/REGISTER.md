# REGISTER — T06_class_identity 统一类身份模型回归 + 真实试用

> 2026-08-14。基线：unsafe-vibe-dev（Task1 后），全量 2616 passed / 1 skipped。
> 分类/级别规范见 `_toolkit/CLASSIFICATION.md`。死循环保护：每例经 harness
> SIGKILL + --max-inst + LLM 调用超时。

## 一、总览

- **用例总数**：20（D1×5 + D2×8 + D3×5 + D4×2）
- **PASS**：18
- **KERNEL_ISSUE**：2（D2-05 / D3-02，同一根因）
- **HARNESS**：0（断言全部达成；2 例 KERNEL_ISSUE 为真实缺陷触发）
- **零死循环 / 零超时**。

## 二、缺陷登记

### KERNEL_ISSUE-CROSSMOD-LLM-1（P1）— 跨模块用户类作行为表达式 LLM 输出目标失败

- **现象**：`geo.Counter c = @~ 给一个数字 ~`（跨模块用户类作 LLM 输出目标）运行时抛
  `VM: Call failed: Object of type 'None' has no method '__call__'`。
- **证据**：`cases/D2-05/main.ibci`（跨模块 hint）、`cases/D3-02/main.ibci`（跨模块
  __from_prompt__）。触发时 `_get_expected_type_hint` 返回 `'behavior'` 而非
  `'geo.Counter'`。
- **根因（编译期实证）**：行为表达式赋值给模块限定类型（annotation 为 `IbAttribute`
  点号限定，如 `geo.Counter`）时，编译器未把目标类型绑定到行为节点
  `node_to_type`（`_statement_visitors.py:110-117` 的 bind_type 对 IbName 目标生效，
  但 `_resolve_target_name_and_type` → `_resolve_type(IbAttribute 注解)` 未解析出
  geo.Counter spec）→ 行为节点 node_to_type = `type_root.behavior` → LLM parse 链
  type_hint='behavior' → VTable/Axiom 无法解析 → 运行时 `__call__ on None`。
- **对照**：入口类 `Point p = @~...~`（annotation 为 `IbName Point`）正确绑定
  `main.Point` → D2-03/D3-01 PASS。
- **定性**：**pre-existing 缺陷**（base 7ed9d274 同现，非 S2 引入）。与 KNOWN_LIMITS
  §10.2 登记的"跨模块 LLM 类型解析需模块限定声明"相关但**更严重**——不是 graceful
  退化而是运行时崩溃，且根因是编译器未传播点号限定注解的类型。
- **修复方向**（待独立窗口）：`_resolve_type` 支持 `IbAttribute` 点号限定注解解析为
  目标 spec（或 behavior 绑定路径对 module 限定注解补全），使行为节点 node_to_type
  = `geo.Counter`。
- **判别性回归（建议）**：`geo.Counter c = @~...~` → c.value() 正常（与入口类对称）。
- **状态**：待修（独立窗口）。

## 三、逐例明细

| case | 分类 | 目标 |
|------|------|------|
| D1-01 | PASS | 入口类 type() 裸名显示 |
| D1-02 | PASS | 入口类与 geo.Box 隔离（5/401 各自方法表） |
| D1-03 | PASS | run_string 入口模块名稳定 |
| D1-04 | PASS | 入口类 + 导入类不误配 |
| D1-05 | PASS | 单类表 Enum 正确 |
| D2-01 | PASS | 入口类泛型特化 qualified |
| D2-02 | PASS | 入口类继承链（父 module 补全） |
| D2-03 | PASS | 入口类 __from_prompt__（真实 LLM） |
| D2-04 | PASS | 线程 worker 入口+导入双路径 |
| D2-05 | **KERNEL_ISSUE** | 跨模块类 LLM hint（node_to_type 未传播） |
| D2-06 | PASS | 三模块 + 入口类 4 路隔离 |
| D2-07 | PASS | 入口类特化值身份 |
| D2-08 | PASS | 入口类作 list 实参 |
| D3-01 | PASS | 入口类 __from_prompt__ 真实 LLM |
| D3-02 | **KERNEL_ISSUE** | 跨模块类 __from_prompt__ 真实 LLM（同根因） |
| D3-03 | PASS | 意图 + 入口类（真实 LLM） |
| D3-04 | PASS | 线程 + LLM + geo 类（KI-1 同族） |
| D3-05 | PASS | mock↔真实 + 入口类 |
| D4-01 | PASS | **T05 D1-10 核销**（线程 worker geo.Box=405） |
| D4-02 | PASS | T05 D1-12 入口遮蔽回归 |

## 四、结论

- **统一类身份模型（Task1 S1-S4）回归稳健**：入口类 qualified、单类表、get_class
  回落收窄、KI-1 线程侧表、is_truthy 任务本地化全部验证通过；T05 KI-1 触发用例
  核销（D4-01：线程 worker 内 geo.Box(5).get()=405）。
- **新暴露 1 项 pre-existing 缺陷**：KERNEL_ISSUE-CROSSMOD-LLM-1（跨模块用户类作
  行为表达式 LLM 输出目标 node_to_type 未传播，运行时崩溃）。登记 PENDING_TASKS。
- 环境事实：真实 LLM 响应 <1-2s，reasoning_tokens=0（思考已禁用）。
