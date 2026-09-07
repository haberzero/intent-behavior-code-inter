# _diagnostic_design — 诊断面打包：错误定位链设计（P0-1 · 线 1）

> **定位**：设计阶段文档（临时，实现落地后按治理删除、决策收敛进 `docs/architecture/` 与
> `docs/syntax/15_diagnostics.md`）。覆盖"错误定位链"三段 + 错误对象渲染：
> ① 编译期类型检查覆盖（KERNEL_ISSUE-SEM-1 比较运算符起点，同类漏检面一次审完）；
> ② 运行期错误对象携带 ibci 源行列（B1）；③ 解析错误位置漂移修正（P2）；
> ④ 错误对象渲染质量（LLMParseError repr 直漏）。
>
> **出口标准**：设计定稿 → 分批改道实现 → 全量 pytest 零回归 → 三形态复现脚本全转回归测试
> （`.tmp_verify/p11*.ibci` 编译期拦截；repro1-3 位置归位；B1 运行错误带源行渲染）→
> 落账（INDEX/WORKLOG/handoff）。

---

## 一、现状审计（根因链 + 实证，全部 file:行 已核）

### 1.1 段 ① SEM-1：编译期比较类型检查缺失（结构性缺口）

**节点分流事实**：比较/相等 `< <= > >= == !=`、`in`、`is` 解析为 **IbCompare** 单一节点
（`core/compiler/parser/components/expression.py:492-566`；链式 `a<b<c` 合并为一节点
`ops=['<','<'], comparators=[b,c]`，AST `core/kernel/ast.py:501-504`）；算术/位/幂解析为
IbBinOp。**`str >= int` 走 IbCompare，不经 visit_IbBinOp。**

**根因链（三层）**：

1. **`visit_IbCompare` 无 operator 级检查**（`core/compiler/semantic/passes/_expression_visitors.py:388-419`）：
   唯一 `resolve_op(left_type, node.ops[0], **None**)`（:412）——other 恒传 None、只看左类型与
   首 op；兜底恒 bind bool（:418-419），**无 SEM_TYPE_MISMATCH 发射路径**。链中后续
   (op, comparator) 对从不校验。
2. **公理层比较分支对 other_name 无条件**：`IntAxiom`（`core/kernel/axioms/primitives/numeric.py:70-71`）、
   `FloatAxiom`（numeric.py:141-142）、`StrAxiom`（`core/kernel/axioms/primitives/sequences.py:80-81`）、
   `BoolAxiom`（无比较分支）——`if op in (">",">=","<","<=","==","!="): return "bool"` 忽略右类型。
   实跑 `resolve_op(str,'>=',int)=bool`。
3. **IbBinOp 算术兜底过宽**（_expression_visitors.py:236-250）：`resolve_op` 返回 None 时
   "任一操作数为 str → 结果 str"（:241-242）无条件放行——`int + "x"` 在 BinOp 层不报，
   仅靠下游赋值类型检查拦（`int a = 1 + "x"` 报 "Cannot assign 'str' to 'int'"，`any a = 1 + "x"` 静默过）。

**同类漏检面盘点（subagent 全量审计结论）**：

| 面 | 现状 | 判定 |
|----|------|------|
| 排序比较 `< <= > >=`（IbCompare） | 完全未检查 | **本设计修复** |
| 相等 `== !=`（IbCompare） | 未检查 | **维持**（运行期跨型合法：`5 == "x"` → False，Python 语义） |
| `is`（IbCompare） | 未检查 | **维持**（身份比较恒合法，KNOWN_LIMITS 契约） |
| `in`（IbCompare） | 未检查（运行期 `int in "abc"` ERR） | **分组挂起**（检查面大、低价值；登记后续项） |
| 算术/位（IbBinOp） | 弱检查（仅"双非数值且非 str"else 兜底报） | **收紧**（去无条件 fallback，公理层权威化） |
| 一元（IbUnaryOp） | 无专属检查（`~"x"` 运行期才报） | **收紧**（同 BinOp 机制，随批） |
| `and/or`（IbBoolOp） | 未检查 | **维持**（操作数不求值判定，语义为短路布尔） |
| if/while/for 条件 | 非 bool 条件不拦 | **非缺陷**（一切值可 bool 化 = `to_bool` 通用能力，`if [1]:` 运行期合法） |
| 链式比较每对 | 仅首对（且首对也不查） | **本设计修复**（逐对检查） |

**运行期行为矩阵（实测基准，编译期检查 = 其静态近似，严格对齐防误报）**：

| 形态 | 运行期行为 | 编译期目标 |
|------|-----------|-----------|
| `int/float/bool < int/float/bool` | OK | → bool（放行） |
| `int/float/bool < str` | ERR（TypeError） | **SEM_TYPE_MISMATCH** |
| `str < str` | OK | → bool（放行） |
| `str < int/float/bool` | ERR | **SEM_TYPE_MISMATCH** |
| `list/dict < any` | ERR（无 `__lt__`） | **SEM_TYPE_MISMATCH** |
| `== !=` 跨型 | OK（False/True） | 放行 |
| `int/bool * str` | OK（字符串重复，`5 * "x"` = `"xxxxx"`、`True * "x"` = `"x"`，实测） | **必须放行**（IntAxiom/BoolAxiom 须声明，否则收紧 fallback 后误报！） |
| `float * str` | ERR（float 无重复语义，实测） | **SEM_TYPE_MISMATCH**（FloatAxiom 不声明 str） |
| `str * int` | OK | 放行（StrAxiom 已声明） |
| `int + str` / `int - str` / `int / str` 等 | ERR | **SEM_TYPE_MISMATCH**（现靠下游赋值拦；`any` 接收时静默过——收紧后编译期拦） |
| `in`/`is` | 见上 | 不动 |
| 任一操作数 `any`/`auto`/behavior 适配 | 运行期裁决 | **放行**（is_dynamic 惯例，全链路一致） |

### 1.2 段 ② B1：运行期/编译期错误无 ibci 源行（四段断点）

1. **编译侧（一般性根因，SEM_ 全部中招）**：AST 节点自带位置
   （`IbASTNode.lineno/col_offset` + `get_location()`，`core/kernel/ast.py:18-30`，解析期
   `_loc` 附着），但语义 pass 的 `error()/warn()` 构造 Diagnostic 时**不填 line/column**
   （5 处同形实现：`_type_checking_base.py:102,296`、`scoped_visitor.py:99,107`、
   `type_resolution_pass.py:70`、`binding_analysis_pass.py:609`、
    `symbol_collection_pass.py:113`）；适配器 `diag.line or 0`
   （`core/compiler/semantic/adapter.py:41-61`）→ **所有 SEM_ 诊断报 `0:0`**。
   实证：`dict[str,int] d = {}; d[42] = 1` → `SEM_TYPE_MISMATCH: --> file:0:0`。
   （PAR_ 错误不受影响——直接取失败 token 位置；`inspect` 导出的 type_bindings 有位置——
   node_to_loc 侧表保真，断点仅在语义 error() 未提取。）
2. **运行侧（B1 主体）**：值层异常（如 `IbStr.__ge__` 抛
   `InterpreterError("TypeError: Cannot compare ...")`，`core/runtime/objects/primitives/strings.py:154`）
   **无 location、error_code 落 RUN_GENERIC_ERROR 兜底** → VM CPS 循环 `except Exception`
   弹栈原样上抛（`core/runtime/vm/vm_executor.py:265-269`）——**每个 VMTask 携带 node_uid**
   （`vm_executor.py:362-364`）但弹栈时丢弃 → `interpreter.run()` 原样 re-raise
   （interpreter.py:469-472）→ engine 层 `print("Runtime Error: {str(e)}")`
   （engine.py:408）→ **main.py run 无顶层捕获，未捕获异常直落 Python 默认输出**（完整
   traceback，用户看到的全是 Python 帧）。
   位置补位机制已存在但仅 handler 主动上报路径使用（`_report_error(message, node_uid)`，
   interpreter.py:559-587，node_to_loc 侧表查询 + issue_tracker 上报）；值层异常从不经此。
   诊断码精确化：值层 throw 点无码（RUN_GENERIC_ERROR 兜底）；幽灵码机制
   `_runtime_error_code_for`（`core/runtime/objects/kernel/functions.py:17-32`）仅覆盖
   4 类原生异常且仅原生调用路径使用（leaf.py:437）。
3. **CLI 渲染侧**：`main.py` run 命令仅捕获 FileNotFoundError（main.py:111-114），
   InterpreterError 直落 Python 默认 traceback；编译错误侧渲染是金标准形态
   （`DiagnosticFormatter`：code + 说明/修复 + `--> file:line:col` + 源行 + caret，
   `core/compiler/diagnostics/formatter.py:25-71`，数据驱动诊断目录
   `core/base/diagnostics/catalog.py`），运行错误未接入。
4. **错误对象渲染侧（LLMParseError repr 直漏）**：`str(e)` = 类调用 `__call__` →
   `_str_call` 走 **`__to_prompt__`** 协议（`core/runtime/bootstrap/primitive_initializer.py:493-499`），
   而 int/float/bool 的 `__call__` 走 **`cast_to`**（:460-471、:474-491、:500-505）——**机制不对称**。
   异常公理（`core/kernel/axioms/primitives/errors.py:35-39,76-85`）未声明 `__to_prompt__`
   → 落 base.py:285-293 默认 fallback → **`str(e)` = `<Instance of LLMParseError>`**（实证），
   字段信息（message/raw_response/type_name）全部不可经 `str()` 获取。
   附带缺陷：`IbException.cast_to` 无法转换时**静默 `return self`**
   （`core/runtime/objects/primitives/exceptions.py:14-21`）——`int(e)` 返回异常自身而非报错
   （实证：`int(e)` → `<Instance of LLMParseError>`），fail-fast 违例（base.py:280-283 通用
   cast_to 链是 fail-fast 的，IbException 覆写引入了静默回落）。

### 1.3 段 ③ P2：解析错误位置漂移（跨行构造的"卡住点"归位）

**根因链（双 subagent 独立实证一致）**：

1. **词法器隐式续行吞 NEWLINE**（`core/compiler/lexer/core_scanner.py:192-196`）：行尾
   `paren_level > 0` 时消费 `\n` 不发射 NEWLINE token（and/or 行尾续行同理 :198-203,
   :734-742）。paren_level 是**整数计数器**（:18），不携带开括号位置。
2. **解析失败位置 = `consume` 失败时刻的 `peek()`**（`core/compiler/parser/core/token_stream.py:46-50`）——
   "卡住点"语义（失败时当前 token），不是"出错构造起点"。NEWLINE 被吞后表达式跨行继续，
   卡住点 = 下一行首 token。
3. **废弃 cast 路径**（`core/compiler/parser/components/expression.py:192-242`）：speculate 内
   消费整个 `@~...~` 块后检出 behavior 值 → PCFE 隔离（该路径**不恢复 checkpoint**，恢复仅
   在 :242 普通分组回退分支）→ :234 发 `PAR_DEPRECATED_CAST_SYNTAX` 位置 = `stream.peek()`
   = `~` 之后 token（若悬挂 `(` 吞行 = 下一行）。

**复现证据（最小案例，`main.py check` 实跑）**：

| 案例 | 实际错误 | 报错位置 | 期望 |
|------|---------|---------|------|
| 行1 `print("a=" + (str)n`（缺 `)`）/ 行2 `print("DONE")` | `Expect ')' after arguments` | **2:1**（行2） | 行1 的 `print(` 起点 |
| 行1 `x = ((int) @~do it~` / 行2 `print(x)` | `PAR_DEPRECATED_CAST_SYNTAX` | **2:1**（行2） | 行1 的 cast 起点 |
| 行1 `x = (int) @~do it~`（单行） | `PAR_DEPRECATED_CAST_SYNTAX` | 1:1（行对、列漂行首） | 行1 的 `(` |

**多行续行是合法特性**（paren_level 机制承载多行表达式/容器；P1 队列"多行容器尾逗号"
依赖之）——**不可禁止跨行**，修正方向 = 错误位置归位，非解析行为变更。

**附带的词法位置失真**（影响行为表达式错误定位精度，同链修正）：闭合 `~`
BEHAVIOR_MARKER 复用开启 marker 的陈旧 start 位（core_scanner.py:464-472 未 `start_token()`）；
RAW_TEXT token 用文本**结束**位且 end 字段为 0（:523, :180, :223-229）。

### 1.4 死代码/半接通（审计发现，机械批处置）

- `ParserError`/`LexerError`/`SemanticError` 异常类（`core/kernel/issue.py:55-84`）**零消费者**——
  实际错误通道 = `ParseControlFlowError` + `IssueTracker` → `CompilerError`。
- `LogicalCallStack.get_backtrace()`（`core/runtime/interpreter/call_stack.py:57-59`）**零消费者**
  （栈本身仅维护 module 级帧，供 idbg 的 `IStackInspector`：`get_call_stack_depth` /
  `get_current_script_path`，`execution_context.py:280-301`——真实消费者存活，仅 backtrace 死）。
- `node_to_loc` 侧表**丢弃终点**（end_line/end_column 不入侧表，
  `core/compiler/semantic/passes/integrity_check_pass.py:40-48`）——渲染 caret 宽度依赖
  end_column（formatter.py:61-63），侧表缺失时 fallback 用 token length。登记为**已知局限**
  （不属本设计范围：补终点入侧表涉 artifact 契约面，收益=caret 精度，归后续项）。

---

## 二、设计裁定

> 裁决基准：design-philosophy（单一权威源/机制同构/统一设计语言）+ code-quality
> （双通道禁止/fail-fast/死代码清理）+ user-principles（原则优先于行为维持）。

### 2.1 段 ① SEM-1：比较/算术检查权威源 = 公理层运算符声明（条件化）

**裁定 A1（单一权威源）**：运算符×类型兼容性的权威源**不新建**——沿用既有机制
`registry.resolve_op` → `axiom.resolve_operation_type_name(op, other_name)`
（`core/kernel/spec/registry/_inference.py:211-260`）。registry 层新增兼容矩阵 = 与公理层
双通道（code-quality 红线）。公理层声明语义从"结果类型推断"完善为
**"op + 左类型 + 右类型 → 结果类型，None = 不兼容"**（声明面不变，行为条件化）。

**裁定 A2（比较分支条件化）**：

| 公理 | 排序比较 `< <= > >=`（现状无条件 bool） | `== !=`（维持无条件 bool） |
|------|------------------------------------------|---------------------------|
| IntAxiom / FloatAxiom | other ∈ {int, float, bool} → bool；other 其它 → **None** | 不动 |
| BoolAxiom（静态类型 bool，运行期 int 语义） | other ∈ {int, float, bool} → bool；其它 → **None**（现无比较分支 → 补） | 不动（已有） |
| StrAxiom | other = str → bool；其它 → **None**（与运行期 `_require_str_other` 对齐） | 不动 |
| ListAxiom / DictAxiom / 容器族 | 排序比较 → **None**（运行期无 `__lt__`）；`== !=` 维持（运行期恒 False 合法） | 不动 |
| Optional / 用户类 / any | any 侧放行（is_dynamic 惯例）；用户类走既有 `get_operators` 覆写面 | 不动 |

**裁定 A3（IbCompare 逐对检查 + SEM 发射路径）**：`visit_IbCompare` 改为链上**每对**
(op, 左值/上一 comparator 类型, comparator 类型) 经 resolve_op 判定：
- 排序比较 op 且判定 None（且双侧非 dynamic）→ `SEM_TYPE_MISMATCH`
  （message 携带 op 与两侧类型名，与 BinOp 兜底报错同形态）；
- `== !=` / `is` 不判定（维持）；`in` 不判定（分组挂起，裁定 A5）；
- behavior 操作数适配（:394-408）与 any 放行（:202-204 同惯例）保持；
- 链结果类型恒 bind bool（现有语义不变）。

**裁定 A4（IbBinOp/IbUnaryOp 兜底收紧）**：删除 `visit_IbBinOp` "任一 str 操作数 → 结果
str"无条件兜底（:241-242）与数值兜底（:239-240，公理层 Int/Float 算术分支已完整覆盖）——
`resolve_op` 返回 None 即 SEM_TYPE_MISMATCH（现 :244-249 路径前置为唯一路径）。
**防误报前置（必做）**：IntAxiom 与 **BoolAxiom** 的 `*` 分支补 `other_name = "str"` →
`"str"`（字符串重复，运行期合法，实测 `5 * "x"` = `"xxxxx"`、`True * "x"` = `"x"`）；
FloatAxiom **不补**（实测 `1.5 * "x"` 运行期 ERR）——否则收紧兜底后误报/漏报。
一元 `visit_IbUnaryOp`（:261-263）同收紧：`resolve_op` None 即报（`~"x"` 编译期拦截，
对齐运行期 `Object of type 'str' has no method '__invert__'`）。

**裁定 A5（分组：in / if 条件不扩）**：
- `in` 运算符编译期检查**不做**（挂起登记）：检查面 = 容器类型 × 元素类型矩阵
  （str 要求 str 元素、list 恒合法），价值低（运行期错误经值层已有消息），误报面大；
  登记后续项（INDEX），与 P2 队列"dict 可 for 迭代"同批评估。
- if/while/for 非 bool 条件**非缺陷**：一切值可 bool 化（`to_bool` 通用能力，
  `interpreter.is_truthy` 协议分派），`if [1]:` 运行期合法——不加检查（防误报裁决）。
  behavior 条件特型化（`_bind_condition_behavior_types`）维持现状。

### 2.2 段 ② B1：位置/码/渲染 三单一权威源

**裁定 B1-①（编译侧位置）**：语义 pass 的 `error()/warn()` 填
`line=node.lineno, column=node.col_offset`（node 位置是解析期 `_loc` 附着的单一权威源；
5 处同形实现统一补——不新建共享基类，各处一行，避免改类层级联）。
Diagnostic（`core/compiler/semantic/result.py:23-33`）line/column 字段已存在，
adapter（adapter.py:41-61）自动消费。**效果**：全部 SEM_ 诊断 `0:0` → 实际源行列。
（注意：这是行为变更——既有 expect-code 测试若断言位置需同步核；全量 pytest 门。）

**裁定 B1-②（运行侧翻译点）**：在 VM CPS 驱动循环的**首次捕获点**
（`vm_executor._drive_loop_gen` `except Exception` 弹栈处，:265-269——此时 `task.node_uid`
可精确获得）做位置补位：

```
异常 e 穿透本帧（被弹栈）时：
  若 e 不是 ThrownException（用户语言级异常值，穿透纪律）
  且 e 不是环境限制异常（handle_environment_limit 已判定）
  且 isinstance(e, IBCBaseException) 且 e.location is None：
      e.location = Location(node_to_loc[task.node_uid])   # 内层帧 = 出错现场
      issue_tracker.report(ERROR, e.error_code, e.message, e.location)  # 与 _report_error 同协议
```

- **同一异常对象沿栈上传**（`gen.throw` 投递同一对象）——已补位（location 非 None）不再改；
  外层帧 handler 重新抛出**新**异常时按新现场补位（语义正确：再抛点 = 新错误位置）。
- **诊断码权威源 = throw 点**（值层语义自知）：翻译点只补位置，**不猜码**（防双权威）。
- 值层 throw 点补码（对齐运行期语义）：比较/运算类型不匹配
  （strings.py:142,149,154；numbers.py 比较路径；collections.py:188,203）→
  `RUN_TYPE_MISMATCH`（既有码，catalog 语义"运行时类型不匹配"精确对应；
  SEM_TYPE_MISMATCH/RUN_TYPE_MISMATCH 编译/运行期成对 = 统一设计语言）。
- 幽灵码机制 `_runtime_error_code_for` 维持现状（原生调用路径，异常类型→码），不扩展。

**裁定 B1-③（CLI 渲染）**：`main.py` run 命令顶层捕获 IBCBaseException：
- InterpreterError 类（含编译期泄漏的）→ 经 `DiagnosticFormatter` 渲染（与编译错误同形态：
  code + 说明/修复 + `--> file:line:col` + 源行 + caret），exit 1；
- 位置来源 = 异常对象 location（B1-② 已补）；无 location（宿主侧直抛等）→ 渲染码 + 消息，
  省略位置段（formatter 既有行为）；
- **engine 层 `print("Runtime Error: {str(e)}")` 维持**（宿主侧/非 CLI 消费者展示面，
  零行为变更）；CLI 渲染不重复消息行，只补定位上下文——渲染单一权威源 =
  DiagnosticFormatter（编译期/运行期共用，统一设计语言）；
- Python 默认 traceback 不再出现（捕获后不再向上传播未处理）。

**裁定 B1-④（错误对象渲染）**：
- 异常公理（`ExceptionAxiom` + `_LLMErrorAxiomBase`）`get_method_specs` 增
  `__to_prompt__`（ret=str）；`IbException` 实现 `__to_prompt__` =
  `"<TypeName>: <message>"`（message 字段为权威；类型名经 ib_class.name）。
  **效果**：`str(e)` 出 `<LLMParseError: MOCK:FAIL - ...>` 而非 `<Instance of ...>`；
  LLM prompt 视角渲染（P4c/G5 设计语言：`__to_prompt__` = 值渲染统一契约）同步受益。
  `_str_call` 维持走 `__to_prompt__`（不动 int/float/bool 的 cast_to 通道——
  两通道差异是既有设计，本项不扩面）。
- `IbException.cast_to` 静默 `return self`（exceptions.py:21）→ **fail-fast**
  （InterpreterError，对齐 base.py:280-283 通用链纪律）。`int(e)` 由"静默返回异常自身"
  改为显式错误——缺陷修复，非行为偏好（该行为无合法消费者：返回的非 int 值赋给 int
  变量必在赋值点报错，`any` 接收则是类型谎言）。

### 2.3 段 ③ P2：错误位置归位规则（卡住点 → 构造起点，仅跨行）

**裁定 P2-①（归位规则）**：解析错误位置 = **出错构造的起点**，而非失败时刻的卡住点；
同卡住点时维持现状（同行内卡住点列号精确，不劣化）：

- **跨行续行态**（NEWLINE 被 paren_level 吞、当前 peek 与构造起点不同行）：
  位置归位到**构造起点**（行 = 起点行，列 = 起点列）。构造起点 = 最内层未闭合构造的
  开括号 / 语句起点。
- **同行**：维持卡住点（现状正确）。

**裁定 P2-②（机制：paren_level 计数器 → 位置栈）**：词法器 `paren_level: int`
升级为 `paren_stack: List[(line, col)]`（开括号压入其 token 起点，闭括号弹出）；
暴露"最内层未闭合构造起点"查询。and/or 行尾续行（:198-203）同理记录续行起点。
**解析器归位消费**：`TokenStream.error(token, ...)` 增加归位判定——token 与当前
"未闭合构造起点"跨行时，位置取构造起点（构造起点由词法器经 token 流共享状态提供，
单点真理：词法器是括号的唯一感知者）。

**裁定 P2-③（废弃 cast 专项）**：`PAR_DEPRECATED_CAST_SYNTAX` 位置显式取
**cast 起点 token**（grouping 的 `(`，即 speculate checkpoint 处 token——checkpoint
机制已存在，expression.py:193），不取 `stream.peek()`（:234 修正）。
（该码本身是"废弃语法"提示，位置指 cast 起点对用户最精确。）

**裁定 P2-④（词法位置失真同链修）**：闭合 `~` BEHAVIOR_MARKER 补 `start_token()`
（core_scanner.py:464-472）；RAW_TEXT token 起点修正为文本起始位（:523, :180,
:223-229 语义核正）。行为表达式未闭合/位置类错误定位精度随修。

**非目标**：`synchronize()` 恢复点策略、多错误报告（单错误即停）不变；
node_to_loc 侧表补终点（artifact 契约面）不属本设计（1.4 登记）。

### 2.4 段 〇 死代码清理（机械批）

- 删除 `ParserError`/`LexerError`/`SemanticError`（issue.py:55-84，零消费者；
  保留 CompilerError/FatalCompilerError/IBCBaseException/InterpreterError/PluginError
  ——有消费者）。
- 删除 `LogicalCallStack.get_backtrace()`（零消费者；栈本体与 idbg 内省面维持）。
- 删除前先全仓 grep 消费者复核（含 tests/ trials/ ibci_modules/）。

---

## 三、批次计划（每批 = 独立 commit + 全量 pytest 零回归 + 落账）

| 批 | 内容 | 门 | 依赖 |
|----|------|----|------|
| **0** | 死代码清理（2.4） | 全量 pytest（纯删除，零语义） | — |
| **1** | B1 编译侧位置：语义 error()/warn() 填 line/col（2.2 B1-①） | 全量 pytest（SEM_ 位置 0:0→实际值；核 expect-code 测试无位置断言） | — |
| **2** | B1 运行侧翻译点：VM 首次捕获点位置补位 + 值层 throw 点补 RUN_TYPE_MISMATCH（2.2 B1-②） | 全量 pytest + SEM-1 三形态实跑（错误带 ibci 源行，码 = RUN_TYPE_MISMATCH） | — |
| **3** | B1 CLI 渲染 + 错误对象渲染：main.py run 结构化渲染（B1-③）+ 异常 `__to_prompt__` 注册（B1-④）+ cast_to fail-fast（B1-④） | 全量 pytest + LLMParseError 渲染判别（str(e) 含 message；int(e) 报错） | 批 2（渲染消费 location） |
| **4** | **SEM-1 编译期检查**：公理比较分支条件化（A2，含 int*str 防误报前置）+ visit_IbCompare 逐对（A3）+ BinOp/UnaryOp 兜底收紧（A4） | **语义错误集变更 → 全量 pytest 破坏面评估**（新失败用例 = 误报面，按 1.1 矩阵逐核修复）+ 三形态转编译期拦截回归测试 | **批 1**（新 SEM 错误需位置） |
| **5** | P2 位置归位：paren 位置栈 + 跨行归位（P2-①②）+ 废弃 cast 专项（P2-③）+ 词法失真（P2-④） | 全量 pytest（PAR_ 位置断言漂移核）+ repro1-3 归位回归测试 | — |

**批内顺序说明**：0→1→2→3 先成"定位链"（位置 + 码 + 渲染能力就位），4/5 再加
"检查链"——批 4 新增的编译期错误天然带批 1 的位置能力。批 5 独立但置末（解析层变更
影响面大，且其回归案例与批 4 的诊断渲染协同验收）。

## 四、影响面评估与风险

1. **批 4 = 唯一语义错误集变更**：既有"运行期才报错"的脚本形态（`any a = 1 + "x"`、
   `s < 0` 类）转为编译期报错。方向正确（编译期 > 运行期，错误更早更准），但：
   - 全量 pytest 新增失败用例 = 误报面证据，**逐一按 1.1 矩阵核**（合法运行期行为
     被新拦 = 公理声明缺口，补声明而非放行）；
   - trials 套件（真实 LLM 用例含 ibci 脚本）同步评估——L3 层用例若含此类形态，
     编译期拦截后需改脚本（脚本修正登记，非缺陷规避）；
   - `== !=`/`is`/`in`/if 条件**不动**（裁定 A3/A5 防误报边界）。
2. **批 2 值层补码**：`RUN_TYPE_MISMATCH` 替代 `RUN_GENERIC_ERROR` 出现在错误消息——
   断言错误消息的测试/trials（expect-class 类）需核（码变更，消息主体不变）。
3. **批 3 cast_to fail-fast**：`int(<异常值>)` 由静默返回变报错——全仓搜 `int(` 消费点
   核实无合法消费者（预期零：现有用例不转换异常值）。
4. **批 5 词法器 paren 栈**：词法器是位置敏感面，`start_token()` 修正可能影响既有
   token 位置断言（测试层 expect 位置值）——全量核。
5. **批 1 位置填充**：`0:0` → 实际值若被任何测试/文档断言（"报 0:0"的说明文本），
   同步修（docs 侧 15_diagnostics 不复制位置值，预期零影响）。

## 五、验收基线（出口标准对照）

| 项 | 验收 |
|----|------|
| SEM-1 三形态 | `.tmp_verify/p11b/p11c/p11_cast.ibci` → **编译期** `SEM_TYPE_MISMATCH` + ibci 源行列 + 说明/修复；`p11_no_cast` 对照组仍正常 |
| 链式比较 | `s < a < c`（str 混入）逐对拦截 |
| `int * "x"` 重复 | 仍合法（编译期 → str，运行期 OK）——防误报回归 |
| B1 运行错误 | 任意值层 TypeError 形态 → `file:line:col` + 源行 + caret + 码（RUN_TYPE_MISMATCH 类），无 Python traceback |
| SEM_ 位置 | `d[42]=1`（dict[str,int]）→ 实际行列非 0:0 |
| P2 | repro1（缺 `)`）报行1 `print(` 起点；repro2/3（废弃 cast）报 cast 起点 |
| str(e) | `<LLMParseError: <message>>`（含字段语义）；`int(e)` fail-fast 报错 |
| 全量 | 每批 `python -m pytest tests/` 零回归（基线以实跑为准，当前 3219 passed / 1 skipped） |
| 落账 | INDEX：KERNEL_ISSUE-SEM-1 转已修复 + B1/P2 登记核销 + `in` 运算符检查挂起登记；WORKLOG 裁定行；handoff/NEXT_STEPS 同步 |

## 六、待决 / 非目标

- **`in` 运算符编译期检查**：挂起（A5 裁定），登记 INDEX 后续项（与 dict for 迭代同批评估）。
- **node_to_loc 侧表补终点**（end_line/end_column）：登记已知局限，非本设计（artifact 契约面）。
- **词法 RAW_TEXT/BEHAVIOR_MARKER 位置之外的其它 token 位置失真**：批 5 只修影响错误
  定位的两处（P2-④），系统性词法位置审计归质量维护面。
- 批 4 若全量评估揭露误报面过大（>10 处合法形态被拦）：回设计复核 A2 矩阵，
  不强行推进（工作模式定论 5：质量优先于速度）。
