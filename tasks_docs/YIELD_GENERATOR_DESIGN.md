# YIELD_GENERATOR_DESIGN — 阶段 5: yield 惰性生成器设计

> **性质**：阶段 5 设计冻结文档（tasks_docs/，独立分支 exp/yield-generator 实验）。
> **定位**：语言级惰性生成器（PT-FEAT-1 剩余部分，D-08 定案——无 async 关键字；含 `yield` 的函数自动为生成器）。
> **权威**：`EXEC_FOUNDATION_DESIGN.md` §5.2。
> **最后更新**：2026-08-08
> **状态**：**已实现（独立分支 exp/yield-generator，全量 2043 passed / 1 skipped）**，待手动应用 unsafe-vibe-dev。

---

## 〇、目标语义

- 含 `yield` 的函数 = **惰性生成器**（可迭代序列）：`yield x` 挂起产出值，迭代恢复。
- `yield` 可在循环/条件内，挂起须保留**整个帧状态**（循环位置、局部变量）。
- 与 `await` 正交可组合：生成器体内可 `await`（可挂起生成器，等待 Waitable）。
- 无 async 关键字（D-08）：`yield` 自标记函数种类。

## 一、语言面

```ibci
func count(int n) -> int:   # 含 yield → 惰性生成器（返回类型=generator[int]）
    int i = 0
    while i < n:
        yield i
        i = i + 1
    return 0

for int x in count(3):
    print(x)           # 0 1 2
```

- 生成器函数调用返回**生成器对象**（惰性，不执行体）。
- 迭代：`for x in gen` / `auto g = gen()` 后再迭代。
- 生成器也可作为可迭代值传递。
- `yield` 低优先级解析操作数：`yield x + 1` 产出 `x + 1`（与 Python 一致，yield 是低优先级语句级关键字）。

## 二、管线触面（全量，已实现）

| 层 | 改动 |
|----|------|
| 词法 | `yield` 关键字 → `TokenType.YIELD` |
| 语法 | `yield` 表达式（前缀，`parse_precedence(LOWEST)`）；函数声明 `is_generator` 标记经语义检测 |
| AST | `IbYieldExpr(IbExpr)`（value）+ `IbFunctionDef.is_generator` 标记字段 |
| 语义 | ① 含 `yield` 的函数自动标 `is_generator`（`_contains_yield` 扫描函数体，排除嵌套函数定义）；② 生成器函数返回类型 = `generator[元素类型]`；③ yield 只能在函数体内（`SEM_YIELD_OUTSIDE_FUNCTION`） |
| 类型 | `GENERATOR` TypeKind + `generator[T]` 泛型（factory/generic 声明/type_ref/artifact_rehydrator 全链路） |
| VM | `vm_handle_IbYieldExpr`——求值后 yield `GeneratorYield(value)` 标记 |
| 运行时 | `IbGenerator` 值对象（`kernel/generator.py`）+ `_drive_generator_loop` 单可恢复驱动 + `for` 迭代 |

## 三、架构要点（EXEC_FOUNDATION_DESIGN §5.2）

**生成器体必须为单可恢复驱动**：`yield` 在循环/条件内，挂起保留整个帧状态（循环位置、局部变量）。
故生成器体**不能**"逐语句 run()"（`_vm_execute_stmt_sequence` 每语句独立 run），必须由**单一可恢复
驱动生成器**承载（同 `_drive_loop_gen` 模型）——在 `yield` 点暂停交付值、迭代恢复。

**驱动机制（已实现）**：生成器函数体经 `_vm_call_user_function`（CPS 帧准备 + 逐语句 yield）作为
**单一** VMTask 压栈，由 `_drive_generator_loop`（可恢复驱动，与 `_drive_loop_gen` 同构）推进。
`vm_handle_IbYieldExpr` 求值后 yield `GeneratorYield(value)` 标记（shared/signals.py 新增，非 child uid）；
驱动循环识别该标记：**挂起向外交付** value（`yield` 给迭代方），迭代恢复（`send`）后继续推进——保持
循环位置/局部变量。向外 yield 仅两类：`GeneratorYield`（语言产出）+ `Waitable`（宿主等待）。

**调用路径**：`vm_handle_IbCall` 对 `is_generator` 的 `IbUserFunction` 经 `UserFunctionCall` 请求 driver
创建（`make_generator_driver`）；`_drive_loop_gen` 对生成器函数返回可恢复驱动，包装为 `IbGenerator`
值对象（承载 `callable` 类 + driver）。

**与 await 组合**：生成器驱动循环处理 `Waitable`（`_drive_generator_loop` 的 Waitable 分支）——生成器
体内可挂起 LLM 行为（e2e 验证 `@~...~` 在生成器内）。

## 四、实现步骤（已完成，独立分支 exp/yield-generator）

| 步骤 | 内容 | 验证 |
|------|------|------|
| A | 词法 + 语法 + AST：`yield` 表达式解析、函数 is_generator 标记 | ✅ 编译期测试 |
| B | 语义/类型：生成器函数标记传播 + 类型检查（yield 仅函数体内）+ `generator[T]` 泛型 | ✅ 语义测试 |
| C | 运行时：`IbGenerator` 对象 + 单可恢复驱动 + 迭代（`for`/`to_list`） | ✅ 运行时/VM 测试 |
| D | VM：`vm_handle_IbYieldExpr` 挂起交付 + 迭代恢复 | ✅ e2e 测试 |
| E | 与 await 组合验证 + e2e 测试（9 项） | ✅ 全量 pytest |

## 五、风险与边界

- **生成器体驱动**是全新执行形态（非"逐语句 run"），经 `_drive_generator_loop` 独立验证挂起/恢复正确性。✅
- `yield` 与 `for`/`while`/`if` 内状态保留（循环位置、局部变量）——由单可恢复驱动保证。✅
- 生成器与 `await` 组合：驱动区分语言级 yield（`GeneratorYield`）与 Waitable yield。✅
- **不做**：跨引擎/序列化挂起生成器（瞬态挂起，EXEC_FOUNDATION §七）；`yield from`；`next()` 内建
  （当前经 `for`/`to_list` 迭代；`next()` 内建按需后续加）；裸 `generator` 注解（须 `generator[T]`）。