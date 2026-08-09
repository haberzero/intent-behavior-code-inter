# _code_yield_from — P0 阶段5增量：`yield from` 惰性生成器委托

> **性质**：临时任务文档（code-workflow §五）。Phase 5 汇报后经用户确认删除。
> **定位**：阶段 5 yield 惰性生成器的自然补全增量（`YIELD_GENERATOR_DESIGN.md` §五"不做"清单项，
> 也是 NEXT_STEPS/PENDING_TASKS §〇 P0 项"阶段 5 增量（next() 内建 + yield from）"的第二项；
> `next()` 内建已落地 c61a6e0）。

---

## 一、目标语义（与 Python 对齐）

```ibci
func inner(int n) -> int:
    yield 1
    yield 2
    return 9

func outer(int n) -> int:
    yield from inner(n)      # 委托：透传 inner 的全部产出
    return 0

for int x in outer(1):
    print(x)                 # 1 2
```

- `yield from <expr>` 委托到子迭代对象：**逐值透传**（当前生成器把子迭代的每个产出作为自己的产出交付给消费者）。
- **表达式值** = 子生成器的 `return` 值（子生成器为 `IbGenerator` 时，`StopIteration.value`）；对序列/其它可迭代为 `None`。
- 子迭代对象可以是：`IbGenerator`（嵌套生成器委托）、序列（list/tuple）、有 `__iter__`/`to_list` 的对象（与 `for` 迭代解析同协议）。
- 惰性由消费方决定：`next()` 逐值惰性推进（外层 break/停止消费时子迭代不继续）；`for` 消费经 `_resolve_iterable`→`to_list` **一次性急物化**（与 `yield` 生成器消费一致，预存行为）。委托机制本身逐值（`generic_next`），非急物化。

## 二、管线触面

| 层 | 改动 |
|----|------|
| 词法 | 无新 token。`yield from` = `YIELD` 关键字 + 既有 `FROM`（import 已用）。语法层区分 |
| 语法 | `yield_expr` 解析 `yield` 后 `match(FROM)`：命中则解析操作数 → `IbYieldFromExpr`，否则 `IbYieldExpr` |
| AST | 新增 `IbYieldFromExpr(IbExpr)`（字段 `value: Optional[IbExpr]`） |
| 语义 | ① `_contains_yield` 同时识别 `IbYieldFromExpr`（仅含 `yield from` 无 `yield` 的函数仍标生成器）；② `visit_IbYieldFromExpr`：仅函数体内（复用 `SEM_YIELD_OUTSIDE_FUNCTION`）、操作数须可迭代、节点类型 = 操作数元素类型 |
| 类型 | `resolve_iter_element` 补 `GENERATOR` kind（`generator[T]` → `T`，经 `value_type`）——当前仅 LIST/TUPLE/axiom-iter |
| VM | 新增 `vm_handle_IbYieldFromExpr`：操作数求值 → 子迭代解析 → 逐值 `yield GeneratorYield(v)`；子生成器 `StopIteration.value` 为表达式值 |
| 运行时 | **缺陷修复（前置依赖）**：`_drive_generator_loop` 的 `UserFunctionCall` 分支缺 `is_generator → make_generator_driver`（`_drive_loop_gen` 有）→ 生成器体内调用生成器函数目前损坏，`yield from inner()` 依赖此修复 |
| 序列化 | 无改动（generic `vars(node)` 反射自动覆盖） |
| 测试 | e2e：基础委托 / 委托表达式值（子生成器 return）/ 嵌套委托 / 委托 list / 委托 + break 提前终止 / 生成器体内调用生成器函数（缺陷修复验证）/ 编译期（`yield from` 非函数体报错） |

## 三、关键决策

1. **复用既有迭代协议而非新机制**：子生成器经 `IbGenerator.generic_next()` 逐值推进（与 `next()` 内建/`for` 同协议），不新造"委托驱动"——同一机制，语言自然补全。`StopIteration` 裸 re-raise 保留 `.value`（已实测验证），子生成器 return 值可捕获。
2. **缺陷修复并入（非半修复）**：`_drive_generator_loop` UserFunctionCall 分支对齐 `_drive_loop_gen`（is_generator → `make_generator_driver`）。这是 `yield from inner()` 的前置依赖（操作数求值 `inner()` 是生成器函数调用），也是独立存在的 bug（生成器体内调用生成器函数）。全量 pytest 验证。
3. **迭代解析收敛（单一权威源）**：`for` 的迭代解析（is_sequence_value / IbGenerator→to_list / `__iter__` / `to_list` 四分支）抽为 `_shared._resolve_iterable(executor, obj)`，`for` 与 `yield from` 共用——机制同构、去双写。行为不变（原逻辑逐字提取），全量 pytest 零回归验证。
4. **委托目标优先级**：`IbGenerator` 优先（惰性逐值 + return 值捕获）；其余走 `_resolve_iterable`（序列/`__iter__`/`to_list`，一次性物化，表达式值 None）。
5. **`yield from` 仅在生成器函数体内**（D-08 自标记）：语义检查与 `yield` 一致（`SEM_YIELD_OUTSIDE_FUNCTION`），非函数体报错。
6. **不做**（保持设计边界）：`yield from` 跨引擎/序列化挂起（瞬态）；子生成器 send/throw 语义（IBCI 生成器无 send 契约，迭代即 next）。**Waitable 边界**：子生成器体内显式 `await` Waitable（如 `await c.recv()`）在委托/`for`/`next`/`to_list` 消费路径下均会触发 `generic_next` 的 "unexpected event"——这是**既有迭代协议共有的预存限制**（LLM 行为 `@~...~` 在生成器体内同步解析、不产生 Waitable，故不触达）；`yield from` 复用同一 `generic_next` 协议，行为与既有迭代一致，不新造例外。

## 四、修改文件

- `core/kernel/ast.py`：`IbYieldFromExpr`
- `core/compiler/parser/components/expression.py`：`yield_expr` 区分 `yield from`
- `core/compiler/semantic/passes/_declaration_visitors.py`：`_contains_yield` 识别新节点
- `core/compiler/semantic/passes/_expression_visitors.py`：`visit_IbYieldFromExpr`
- `core/kernel/spec/registry/_inference.py`：`resolve_iter_element` 补 GENERATOR
- `core/runtime/vm/handlers/_shared.py`：`_resolve_iterable`（从 control_flow 提取）
- `core/runtime/vm/handlers/control_flow.py`：`vm_handle_IbFor` 改用 `_resolve_iterable`
- `core/runtime/vm/handlers/leaf.py`：`vm_handle_IbYieldFromExpr`
- `core/runtime/vm/handlers/dispatch.py`：注册 `IbYieldFromExpr`
- `core/runtime/vm/vm_executor.py`：`_drive_generator_loop` UserFunctionCall 分支补 is_generator
- `tests/e2e/test_yield_generator.py`：新测试类 `TestYieldFrom`
- 文档：`docs/syntax/05_functions.md` §5.8 增 `yield from`；`tasks_docs/YIELD_GENERATOR_DESIGN.md` §五"不做"更新（yield from 已落地）；`NEXT_STEPS/PENDING_TASKS/HANDOFF/WORKLOG` 同步

## 五、验证

- 每批全量 `~/miniconda3/envs/ibci/bin/python -m pytest tests/` 零回归。
- e2e 新增覆盖 + 编译期覆盖。
- 变更前后（实现 + 测试 + 文档）记录于 WORKLOG。
