## 15. 诊断码参考

> 本章描述 IBCI 的全部诊断码：每个码的**触发条件**（何时产生）、**严重级别**与**修复方式**（如何消除）。面向需要诊断与修复编译/运行错误的开发者。覆盖词法 `LEX_` / 语法 `PAR_` / 语义 `SEM_` / 依赖 `DEP_` / 内部 `INT_` / 运行时 `RUN_` / 内核诊断 `KDIAG_` / 词嵌入 `EMB_` / 知识注册表 `KNW_` / 层级记忆 `MEM_` / 配置 `CFG_` 各域。

### 诊断工具

编译产物（符号表 / 类型绑定）与编译性能可通过 CLI 诊断导出与基准测量：

```bash
python main.py inspect <entry.ibci> --format json   # 符号表 + 类型绑定 JSON
python main.py inspect <entry.ibci> --format dot    # 符号表作用域图 + 类型绑定边
python main.py semantic <entry.ibci> --format dot   # 同上（semantic 为 inspect 别名语义）
python main.py inspect <entry.ibci> -o symbols.json # 写文件（默认 stdout）
python main.py bench <entry.ibci> --runs 10 --warmup 2  # 编译时间基准（min/avg/max/stdev）
```

- **JSON**：`symbols`（作用域树递归，每条 name/kind/uid/type/provenance）+ `type_bindings`（节点类型+位置 → 类型名）。
- **dot**：作用域为 `subgraph cluster`、符号为节点、作用域父子/类型绑定为边；可用 `dot -Tpng symbols.dot -o symbols.png` 渲染。
- **bench**：warmup 后重复编译 N 次，报告 min/avg/max（可加 stdev）；编译失败按诊断码格式报错并以非零码退出。
- CLI 命令：`inspect` / `semantic`（导出）与 `bench`（基准）。

**run 命令可观测面**：

- **输出行级 flush**：`python main.py run <entry.ibci>` 的 ibci `print` 输出为
  **行级 flush**——每行 print 即时可见（非 TTY 管道/重定向下同为行缓冲），长 run
  （LLM 批次 / 大语料扫描）进度可观测，可区分"慢"与"挂"。
- **LLM 调用 journal（默认开）**：每次 `run` 将全部 LLM 调用 append-only 记录到
  项目根 `llm_journal/<run-id>.jsonl`（首行 run 元数据 + 每调用一行：
  prompt 全文 / raw 响应 / model / finish_reason / generation / usage / 时间戳）。
  启动提示走 stderr（不入 stdout 数据面）。`--no-journal` 关闭。
  ```bash
  python main.py run app.ibci                 # 默认写 journal
  python main.py run app.ibci --no-journal    # 关闭
  ```
- **确定性重放**：`--replay <journal>` 让 LLM 调用全部来自记录（同一入口代码 +
  同一 journal = 同一执行轨迹；真实 provider 不加载、无需 API key）。复测/审计零
  LLM 成本。调用次数超记录 = fail-fast（确定性契约违背）；提前结束 = 合法。
  ```bash
  python main.py run app.ibci --replay llm_journal/20260908T120000Z-a1b2.jsonl
  ```
- **run 级 LLM 预算**：`api_config.json` 顶层可选 `budget` 节——
  `{"max_tokens": 100000, "max_calls": 500, "max_wall_s": 600, "on_exceed": "warn"|"fail"}`
  （各阈值可选）。`warn`（默认）= 每维度首次超限 stderr 告警一次、run 继续；
  `fail` = 超限在**下一次 LLM 调用的 provider 调用前**拦截
  （`RUN_BUDGET_EXCEEDED`，被拦调用不发出）。无 `budget` 节 = 无预算核算。
- **确定性执行模式**：`--deterministic` 启用 run 级**零 LLM 不变量**——任何
  LLM 调用（`@~...~`）在**调用汇点、provider 调用前**结构性拦截
  （`RUN_DETERMINISTIC_LLM_CALL`，被拦调用不发出、无 API key 消耗）；适用于
  判定/验证路径的确定性 run（同输入逐字节可复现）。与 `--replay` 互斥
  （矛盾组合 = 启动期拒绝）。边界：拦截面 = LLM 调用汇点（同 journal/budget；
  流式 `ai.stream_call` 与 `meta.eval` 子进程不经守卫，见 `docs/KNOWN_LIMITS.md`
  §二十七 / 第二十六）。
  ```bash
  python main.py run app.ibci --deterministic --result-json
  # trailer: "deterministic": {"enforced": true, "llm_calls": 0}（审计凭证，机读）
  ```
- **机器可读结果 trailer**：`--result-json` 在 stdout **末行**输出一行 JSON
  （验收机 `tail -n1` 即得；数据面 = 末行之前）：
  `{"v":1, "exit_status":"ok"|"error", "exception":null|{"code","message",
  "source":{"file","line","column","snippet"}}, "journal":..., "budget":
  {"calls","tokens","wall_s","exceeded"}|null, "replay":
  {"source","consumed","total"}|null, "deterministic":
  {"enforced","llm_calls"}|null}`。
  ```bash
  python main.py run app.ibci --result-json
  ```

### 如何阅读

- **触发条件**：该诊断在何种输入下产生（精确判断）。
- **修复指引**：如何消除该诊断。
- **严重级别**：编译期诊断（LEX/PAR/SEM/DEP/INT）为 `ERROR`（编译中止），除标注 `WARNING` 者外（`SEM_IMPORT_CONFLICT` / `SEM_INTENT_STATIC_CALL`）。运行时（RUN）诊断在执行时抛出。内核诊断（KDIAG）为运行时告警/事件，不阻断执行。
- **说明/修复文本的权威源**：诊断码的"说明/修复"文本以 `core/base/diagnostics/catalog.py`（`CODE_CATALOG`）为准，`DiagnosticFormatter` 渲染错误时从该目录附加。本文档的码集合与目录保持一致（`tests/contracts/test_diagnostic_catalog.py` CAT-6 对账强制），冲突时以 catalog 为准。

---

### 词法（LEX_）

源码扫描阶段的诊断。

#### `LEX_INVALID_CHAR`
遇到了源码中不被语言接受的字符。
- **触发条件**：词法器遇到语言字符集之外的字符。
- **严重级别**：ERROR。
- **修复方式**：删除或替换该字符；确需表示反斜杠时用转义序列，行为表达式内用 `\$` 表示字面 `$`。

#### `LEX_UNTERMINATED_STRING`
字符串字面量没有闭合引号（或提前换行）。
- **触发条件**：字符串字面量缺少结尾引号，或在闭合前遇到换行。
- **严重级别**：ERROR。
- **修复方式**：补上结尾引号；多行文本请使用行为表达式（`@~ ... ~`）而非跨行字符串。

#### `LEX_UNTERMINATED_BLOCK`
块结构没有闭合（如行为表达式内的 `[` 未配 `]`）。
- **触发条件**：行为表达式内的方括号等块结构未闭合。
- **严重级别**：ERROR。
- **修复方式**：补上缺失的闭括号，保持括号配对。

#### `LEX_INVALID_NUMBER`
数字字面量格式非法（如多余小数点、非法进制前缀）。
- **触发条件**：数字字面量不符合语言格式规则（如 `0x` 无十六进制数字、`12abc` 数字后紧跟字母）。
- **严重级别**：ERROR。
- **修复方式**：按语言数字字面量规则书写（如 `0x`/`0b` 前缀、单一小数点）。

#### `LEX_INVALID_ESCAPE`
字符串内使用了无效的转义序列。
- **触发条件**：字符串中出现语言不支持的转义序列。
- **严重级别**：ERROR。
- **修复方式**：使用语言支持的转义（`\n` `\t` `\\` `\"` `\'` 等）；未知转义改为合法写法或字面字符。

#### `LEX_UNTERMINATED_BEHAVIOR`
行为表达式（`@~ ... ~`）没有闭合标记 `~`。
- **触发条件**：`@~` 开始后未遇到结束标记 `~`。
- **严重级别**：ERROR。
- **修复方式**：补上结束标记 `~`，确保 `@~` 与 `~` 成对出现。

---

### 语法（PAR_）

解析阶段的诊断。

#### `PAR_EXPECTED_TOKEN`
语法解析到这里预期某个特定符号，但出现了别的内容。
- **触发条件**：解析器在该位置预期特定 token（如冒号、右括号、关键字）。
- **严重级别**：ERROR。
- **修复方式**：按报错位置的预期补全符号。

#### `PAR_UNEXPECTED_TOKEN`
解析器在该位置遇到了不应出现的符号。
- **触发条件**：该位置出现多余/错放的 token。
- **严重级别**：ERROR。
- **修复方式**：检查该符号是否多余或放错位置（如多余右括号、多余逗号）。遇 `INDENT`/`DEDENT`（缩进错乱：顶层缩进或块内缩进层级不符）时附定向缩进修复提示（顶层语句须顶格、块内同级缩进一致）。

#### `PAR_INVALID_SYNTAX`
该位置的写法不符合语言的语法规则。
- **触发条件**：语句/表达式形态不符合语法规则。
- **严重级别**：ERROR。
- **修复方式**：对照语法文档检查语句形态；确认关键字、运算符、缩进写法正确。

#### `PAR_UNEXPECTED_EOF`
文件提前结束，还有未完成的语法结构。
- **触发条件**：文件在语法结构完整前结束。
- **严重级别**：ERROR。
- **修复方式**：补齐未闭合的语句/块/括号/行为表达式。

#### `PAR_INDENTATION_ERROR`
缩进不符合语言规则（块结构依赖缩进表达层级）。
- **触发条件**：缩进层级不一致或空格/制表符混用。
- **严重级别**：ERROR。
- **修复方式**：统一使用一致的缩进（空格/制表符不要混用），对齐所属块的缩进级别。

#### `PAR_DEPRECATED_CAST_SYNTAX`
使用了已废弃的强制类型转换语法。
- **触发条件**：使用旧式强制转换写法。
- **严重级别**：ERROR。
- **修复方式**：改用现行语法，详见语法文档。

#### `PAR_POSITIONAL_AFTER_KEYWORD`
位置实参出现在具名实参之后。
- **触发条件**：调用中位置实参排在具名实参之后。
- **严重级别**：ERROR。
- **修复方式**：把位置实参全部放到具名实参之前。

---

### 语义（SEM_）

语义检查阶段的诊断。

#### `SEM_UNDEFINED_SYMBOL`
引用了未定义的变量/函数/模块名。
- **触发条件**：名称在使用前未声明，或导入遗漏/拼写错误。
- **严重级别**：ERROR。
- **修复方式**：在使用前声明该名称，或检查拼写/导入是否遗漏。小写布尔/空字面量（`true`/`false`/`none`）附 did-you-mean 提示（IBCI 字面量须大写 `True`/`False`/`None`）。

#### `SEM_REDEFINITION`
同一作用域内重复声明了同名符号。
- **触发条件**：同一作用域内同名符号重复声明。
- **严重级别**：ERROR。
- **修复方式**：删除重复声明，或改用不同名称；注意与内建/已导入名的冲突。

#### `SEM_IMPORT_CONFLICT`
导入的名称与已有符号冲突。
- **触发条件**：导入名与当前作用域符号冲突。
- **严重级别**：WARNING。
- **修复方式**：改用别名导入（`as`）或调整本地声明，消除命名冲突。

#### `SEM_TYPE_MISMATCH`
赋值/实参/运算两侧的类型不兼容。
- **触发条件**：赋值、实参传递或二元运算两侧类型不兼容。
- **严重级别**：ERROR。
- **定位面**：赋值型诊断定位 RHS 值节点（实际违约源）；二元运算定位运算符位置。
- **修复方式**：把一侧显式转换为另一侧类型，或改用兼容类型。

#### `SEM_ARG_COUNT_MISMATCH`
调用提供的实参数量与被调用的形参数量不符。
- **触发条件**：实参数量与形参数量不符（且无默认值/可变参数承接）。
- **严重级别**：ERROR。
- **修复方式**：补齐/删减实参，或为缺省参数提供默认值。

#### `SEM_DUAL_ASSIGNABLE`
方法重写（override）签名与父类约束不兼容。
- **触发条件**：重写方法的参数/返回类型与父类声明不兼容。
- **严重级别**：ERROR。
- **修复方式**：保持重写方法的参数/返回类型与父类声明兼容。

#### `SEM_CAST_NO_CONVERTER`
目标类型没有提供从源类型的转换能力。
- **触发条件**：类型转换目标缺少源类型→目标类型的转换协议。
- **严重级别**：ERROR。
- **修复方式**：为目标类型实现转换协议，或改用可转换的类型路径。

#### `SEM_CONTAINER_METHOD_HINT`
容器类型上访问了不存在或不适用的方法。
- **触发条件**：容器对象上调用其不支持的方法。
- **严重级别**：ERROR。
- **修复方式**：检查容器实际类型，改用其支持的方法。

#### `SEM_PROTOCOL_SIGNATURE`
提示协议方法的签名与协议约定不符。
- **触发条件**：required 协议方法（提示协议族 5 成员）签名与约定不符。
- **严重级别**：ERROR（编译中止，fail-fast；required 协议成员契约破坏）。
- **修复方式**：按协议约定的参数个数/返回类型修正签名。
- 注：optional 协议成员（`__intent__`/`__retry__`）不经此路径，运行期 fail-fast 校验。

#### `SEM_OVERLAY_UNUSED`
声明了覆层（`impl overlay`）但从未被 `with overlay` 作用域启用。
- **触发条件**：`impl overlay for <类型>` 声明的覆层方法从未被 `with overlay(<类型>.<协议方法>)` 引用。
- **严重级别**：WARNING。
- **修复方式**：为该覆层添加 `with overlay(<类型>.<协议方法>):` 作用域块启用，或删除未用的覆层声明。

#### `SEM_SUPER_OUTSIDE_METHOD`
`super` 只在类方法体内可用。
- **触发条件**：在非类方法上下文使用 `super`。
- **严重级别**：ERROR。
- **修复方式**：把 `super` 调用移入类方法，或检查是否在错误的作用域使用。

#### `SEM_YIELD_OUTSIDE_FUNCTION`
`yield` / `yield from` 只能在函数体内使用。
- **触发条件**：模块顶层或非函数上下文出现 `yield`/`yield from`。
- **严重级别**：ERROR。
- **修复方式**：把 `yield` 移入函数（`func`）体；含 `yield` 的函数即惰性生成器。

#### `SEM_UNRESOLVED_TYPE`
类型注解中的类型名称无法解析。
- **触发条件**：注解引用的类型未定义/未导入。
- **严重级别**：ERROR。
- **修复方式**：确认该类型已定义/导入，且名称拼写正确。

#### `SEM_DECLARATION_WITHOUT_INITIALIZER`
语句域裸类型声明（无初始值）——如 `int x`。
- **触发条件**：语句域（顶层 / 函数局部）出现仅声明类型而无初始值的赋值语句（`int x` / `str s`）。IBCI 语句域变量**无 None 缺省初始化语义**（fail-fast）：未初始化的类型化变量读取即类型违约，故编译期拒绝、精确定位到声明语句。
- **严重级别**：ERROR。
- **修复方式**：补充初始值（`int x = 0`）。**类字段裸声明**（`class P: int v`）= 构造器必填参数（`P(3)`），为合法形态，不受此限；`for` 循环变量 / 函数形参的声明亦为合法形态。

#### `SEM_KNW_CHECK_LLM`
knowledge 登记验证谓词（check）体内含 LLM 调用。
- **触发条件**：`knowledge.store`/`amend` 的 check 参数为同模块函数引用，且其函数体含 LLM 调用（行为表达式/LLM 面调用）——登记门须为确定性验证。
- **严重级别**：ERROR。
- **修复方式**：把 LLM 调用移出 check 函数体（check 只做确定性判定：文本包含/格式/长度检查等）；LLM 调用留在调用方的显式控制流中。

#### `SEM_KNW_CHECK_OPAQUE`
knowledge 登记验证谓词（check）为不透明值。
- **触发条件**：`knowledge.store`/`amend` 的 check 参数无法静态证明确定性（变量传递/跨模块引用/运行时构造的函数值）。
- **严重级别**：ERROR。
- **修复方式**：check 改为本模块内显式定义且不含 LLM 调用的函数引用（编译器可遍历函数体证明纯度；不纯度不可证明即拒绝）。

#### `SEM_DUPLICATE_KEYWORD`
调用中同一具名参数被重复提供。
- **触发条件**：同一具名实参出现多次。
- **严重级别**：ERROR。
- **修复方式**：移除重复的具名实参。

#### `SEM_UNKNOWN_KEYWORD`
调用提供了被调函数不认识的具名实参。
- **触发条件**：具名实参名与被调函数参数名不匹配。
- **严重级别**：ERROR。
- **修复方式**：使用被调函数声明的参数名，或为函数增加该参数。

#### `SEM_MISSING_REQUIRED_ARG`
调用缺少必填的实参。
- **触发条件**：必填参数未被提供。
- **严重级别**：ERROR。
- **修复方式**：提供全部必填实参，或为该参数提供默认值。

#### `SEM_DEFAULT_TYPE_MISMATCH`
参数默认值的类型与参数注解不一致。
- **触发条件**：默认值类型与参数类型注解不符。
- **严重级别**：ERROR。
- **修复方式**：把默认值改为与参数类型一致的类型。

#### `SEM_TOO_MANY_POSITIONAL`
调用提供了过多的位置实参。
- **触发条件**：位置实参数超过形参数（无 `*args` 承接）。
- **严重级别**：ERROR。
- **修复方式**：删减位置实参；其余需求用具名实参或可变参数承载。

#### `SEM_MISSING_RETURN_ANNOTATION`
函数声明缺少返回类型注解。
- **触发条件**：函数（含 lambda）声明缺少 `->` 返回类型。
- **严重级别**：ERROR。
- **修复方式**：为函数补充 `->` 返回类型（显式类型、`auto` 或 `any`）。

#### `SEM_MULTI_TYPE_LIST_REMOVED`
多类型列表声明语法已移除。
- **触发条件**：使用已移除的多类型列表声明语法。
- **严重级别**：ERROR。
- **修复方式**：改用单一元素类型 `list[T]`，异构内容用 `tuple` 或显式转换表达。

#### `SEM_INVALID_SCOPE`
声明出现在不允许的作用域（如模块顶层 vs 函数内错位）。
- **触发条件**：声明位置与作用域规则不符。
- **严重级别**：ERROR。
- **修复方式**：把声明移到合法作用域；检查变量/函数归属层级。

#### `SEM_NONLOCAL_NOT_FOUND`
`nonlocal` 引用的外层变量不存在。
- **触发条件**：`nonlocal` 声明的名称在直接外层作用域未声明。
- **严重级别**：ERROR。
- **修复方式**：确认该变量在直接外层作用域已声明。

#### `SEM_INTENT_PLACEMENT`
意图注释放在了不允许的位置。
- **触发条件**：意图注释位置不合法。
- **严重级别**：ERROR。
- **修复方式**：把意图注释移到合法位置（语句/块的意图槽）。

#### `SEM_INTENT_STATIC_CALL`
意图上下文方法被静态（类级）调用。
- **触发条件**：类级静态调用意图相关方法。
- **严重级别**：WARNING。
- **修复方式**：通过实例访问意图相关方法，而非类级静态调用。

#### `SEM_BEHAVIOR_OUTPUT_NOT_PARSEABLE`
行为表达式声明了具体类型，但该类型没有 LLM 输出解析能力。
- **触发条件**：`-> T` 的 T 无 `__from_prompt__`/parser 能力。
- **严重级别**：ERROR。
- **修复方式**：为该类型实现 `__from_prompt__` 解析协议，或改用可解析类型（`int`/`str`/`list` 等）。

#### `SEM_LLMEXCEPT_BODY_WRITE`
`llmexcept` 体内禁止写参与 LLM 调用的变量。
- **触发条件**：`llmexcept` 体写入参与插值/赋值的变量。
- **严重级别**：ERROR。
- **修复方式**：在 `llmexcept` 体内只写非参与变量，避免污染重试快照。

#### `SEM_LLMEXCEPT_BINDING`
`llmexcept` 绑定形式不符合约定（缺失/多余绑定）。
- **触发条件**：`llmexcept` 绑定形式不合法。
- **严重级别**：ERROR。
- **修复方式**：按 `llmexcept` 绑定语法补全或移除绑定。

#### `SEM_LLMEXCEPT_SCOPE_BINDING`
`llmexcept` 的作用域绑定写法不合法。
- **触发条件**：作用域绑定语句写法错误。
- **严重级别**：ERROR。
- **修复方式**：检查 `llmexcept` 作用域绑定语句的写法与位置。

#### `SEM_LLMEXCEPT_MUTATING_CALL`
`llmexcept` 保护区域内调用了可能突变参与变量的函数。
- **触发条件**：保护区域内调用会突变参与变量的函数。
- **严重级别**：ERROR。
- **修复方式**：避免在保护区域内做副作用突变，或把调用移到 `llmexcept` 之外。

#### `SEM_LLMEXCEPT_FILE_WRITE`
`llmexcept` 保护区域内执行了文件写操作（快照隔离下不允许）。
- **触发条件**：保护区域内执行文件写。
- **严重级别**：ERROR。
- **修复方式**：把文件写移到 `llmexcept` 保护区域之外。

#### `SEM_GENERIC_TYPE_NEEDS_ARGS`
泛型类未提供类型参数即作类型使用（如裸 `Box`）。
- **触发条件**：`class Box[T]` 后直接 `Box b = ...`（无类型实参）。
- **严重级别**：ERROR。
- **修复方式**：特化使用，提供类型实参，如 `Box[int]`。

#### `SEM_GENERIC_TYPE_ARG_COUNT`
泛型类类型实参数量与声明不符。
- **触发条件**：`class Box[T]` 后 `Box[int, str]`（实参数与声明参数数不等）。
- **严重级别**：ERROR。
- **修复方式**：按类声明补全/裁剪类型实参（`class Box[T]` → `Box[int]`）。

#### `SEM_UNCATEGORIZED`
未归类语义错误（无专属码）。
- **触发条件**：语义错误无对应专属诊断码。
- **严重级别**：ERROR。
- **修复方式**：按报错消息的具体内容定位并修复。

#### `SEM_INTERNAL_SENTINEL`
内部哨兵值泄漏到了用户可见的错误面。
- **触发条件**：内部哨兵值泄漏（编译器内部错误信号）。
- **严重级别**：ERROR。
- **修复方式**：通常表示编译器内部 bug；请记录触发代码供维护者排查。

---

### 依赖（DEP_）

模块导入与依赖图阶段的诊断。

#### `DEP_MODULE_NOT_FOUND`
导入的模块找不到。
- **触发条件**：模块路径不存在或不在搜索路径。
- **严重级别**：ERROR。
- **修复方式**：确认模块路径正确、模块文件存在且在项目根搜索路径内。

#### `DEP_FILE_NOT_FOUND`
引用/入口文件不存在。
- **触发条件**：引用的文件路径不存在。
- **严重级别**：ERROR。
- **修复方式**：确认文件路径拼写与存在性。

#### `DEP_INVALID_IMPORT_POSITION`
`import` 语句出现在文件非头部位置。
- **触发条件**：`import` 出现在其它语句之后。
- **严重级别**：ERROR。
- **修复方式**：把所有 `import` 移到文件开头（其它语句之前）。

#### `DEP_GRAPH_ERROR`
依赖图构建失败（模块依赖关系无法解析）。
- **触发条件**：模块依赖关系无法构建。
- **严重级别**：ERROR。
- **修复方式**：检查模块间依赖声明的合法性。

#### `DEP_FAILED_DEPENDENCY`
被依赖的模块编译失败，连带本模块报错。
- **触发条件**：依赖模块编译失败。
- **严重级别**：ERROR。
- **修复方式**：先修复被依赖模块的编译错误。

#### `DEP_SECURITY_ERROR`
导入被安全策略拒绝（越界/不可信路径）。
- **触发条件**：导入路径超出安全策略允许范围。
- **严重级别**：ERROR。
- **修复方式**：调整导入路径或安全策略，使导入在允许范围内。

#### `DEP_CIRCULAR_IMPORT`
模块间存在循环导入。
- **触发条件**：模块依赖图出现环。
- **严重级别**：ERROR。
- **修复方式**：打破循环：把共享部分抽到独立模块，或改为延迟导入。

---

### 内部（INT_）

解释器内部错误（编译器未能归类的内部异常）。

#### `INT_INTERNAL_ERROR`
编译器内部错误（不应出现在正常输入下）。
- **触发条件**：编译器内部断言/不变量失败。
- **严重级别**：ERROR。
- **修复方式**：请记录触发代码与上下文，提交给维护者。

#### `ICE_TYPE_LEAK`
内部类型泄漏到用户可见面。
- **触发条件**：编译器内部类型表示泄漏到用户可见错误。
- **严重级别**：ERROR。
- **修复方式**：编译器内部类型表示问题；请记录触发代码提交维护者。

---

### 运行时（RUN_）

执行阶段的运行时错误。

#### `RUN_GENERIC_ERROR`
未归类运行时错误。
- **触发条件**：运行时异常无对应专属码。
- **严重级别**：ERROR。
- **修复方式**：按报错消息的具体内容定位并修复。

#### `RUN_TYPE_MISMATCH`
运行时发现类型不匹配（编译期类型与运行值不符）。
- **触发条件**：运行值与编译期类型契约不符。
- **严重级别**：ERROR。
- **修复方式**：检查产生该值的路径，确保类型契约成立。

#### `RUN_UNDEFINED_VARIABLE`
运行时读取了未定义的变量。
- **触发条件**：读取未赋值/未定义的变量。
- **严重级别**：ERROR。
- **修复方式**：确保变量在使用前已赋值（含所有分支路径）。

#### `RUN_DIVISION_BY_ZERO`
除数为零。
- **触发条件**：执行除法/取模时除数为零。
- **严重级别**：ERROR。
- **修复方式**：在除法前校验除数非零，或调整算法避免除零。

#### `RUN_ATTRIBUTE_ERROR`
对象上没有该属性/方法，或对空 `Optional` 执行不可用操作。
- **触发条件**：访问对象不存在的属性/方法——属性**读取**（`p.missing`）与
  方法**调用**（`p.missing()`）路径均报此码（属性缺失显式报错，不静默返回
  None）；**空 `Optional` 上执行不可用操作**（`unwrap()` / `len` / 下标 /
  `for` 迭代 / `next()`）亦报此码（`docs/architecture/03_type_system.md` §8
  "Optional 容器委托"：空值操作 fail-fast，不静默返回错误值）。
- **严重级别**：ERROR。
- **修复方式**：确认对象类型，使用其真实存在的成员；空 `Optional` 先经
  `is_some()`/`is_none()` 判空或 `or_else(default)` 提供兜底值再操作。

#### `RUN_INDEX_ERROR`
索引越界或键不存在。
- **触发条件**：下标越界或字典键不存在。
- **严重级别**：ERROR。
- **修复方式**：访问前校验索引范围/键存在性。

#### `RUN_CALL_ERROR`
函数调用失败（函数体执行抛出）。
- **触发条件**：被调函数体执行抛出异常。
- **严重级别**：ERROR。
- **修复方式**：按报错上下文定位函数体内的异常根因。

#### `RUN_LIMIT_EXCEEDED`
执行超过资源/指令上限。
- **触发条件**：超过指令数/资源上限。
- **严重级别**：ERROR。
- **修复方式**：检查是否存在死循环或超大数据；必要时调整执行上限配置。

#### `RUN_LLM_ERROR`
LLM 调用失败（网络/密钥/提供者错误）。
- **触发条件**：LLM 调用网络/鉴权/提供者返回错误。
- **严重级别**：ERROR。
- **修复方式**：检查 LLM 配置（endpoint/key/model）、网络连通性与额度。

#### `RUN_LLM_CALLABLE`
llm 可调用类契约违约。
- **触发条件**：`__llm_call__`/`__intent__`/`__retry__` 返回或签名不符（装配 dict 非 dict / 缺 `user_prompt` / 参数数不符 / 层值或策略值类型错）、值不满足 LLMCallable 协议（缺 `__llm_call__`）、`__llm_call__` 非用户方法。
- **严重级别**：ERROR。
- **修复方式**：按 `docs/syntax/08_llm_callable.md` §8.1/§8.4 核对——`__llm_call__(self, ...) -> dict` 返回装配 dict 且含必需 `user_prompt`；`__intent__(self, dict) -> dict`；`__retry__(self) -> dict`（`max_retry` ≥ 1 int / `hint` str）。

#### `RUN_LLM_EMPTY_CONTENT`
LLM 返回空内容（仅有思考内容、无最终答案）。
- **触发条件**：调用响应 content 为空且 reasoning 非空（思考抑制失效或模型行为形态异常）。
- **严重级别**：ERROR。
- **修复方式**：显式声明 reasoning 模式（api_config model 条目 `reasoning: true`）或使用非思考模型端点。该错误不再静默以思考内容替代答案——"模型只想了没答"是确定的运行状态，须显式诊断。

#### `LLM_ASSEMBLY_UNKNOWN_KEY`
llm 可调用类装配 dict 含契约外字段。
- **触发条件**：llm 可调用类调用时的装配 dict 含契约字段之外的键（疑似拼写错误/废弃字段）。
- **严重级别**：WARNING（不阻断调用）。
- **修复方式**：按装配契约修正字段名（`user_prompt`[必需] / `output_hint` / `expected_type` / `model` / `prompt_slots`）。未知字段不再静默忽略——拼写错误须可见（可见性纪律）；扩展字段属调用方约定，警告仅作提示。

#### `RUN_PERMISSION_ERROR`
运行时操作被权限策略拒绝。
- **触发条件**：操作超出权限策略允许范围。
- **严重级别**：ERROR。
- **修复方式**：调整权限策略或避开被禁止的操作。

#### `RUN_LLMEXCEPT_SNAPSHOT_VIOLATION`
运行时违反了 `llmexcept` 快照隔离约束。
- **触发条件**：快照隔离区域内执行被禁止的写入/副作用。检测到篡改时发出本警告并恢复黄金快照，继续重试（警告不阻断重试）。
- **严重级别**：WARNING。
- **修复方式**：避免在快照隔离区域内执行被禁止的写入/副作用。

#### `RUN_BUDGET_EXCEEDED`
LLM 运行预算超限（run 级 tokens / 调用次数 / 墙钟核算）。
- **触发条件**：`api_config.json` `budget` 节声明 `on_exceed: "fail"` 且累计超限（max_tokens / max_calls / max_wall_s）——拦截发生在**下一次 LLM 调用的 provider 调用前**（被拦调用不发出，零浪费）。`on_exceed: "warn"`（默认）不触发本码：stderr 告警一次 + run 继续。无 budget 节 = 无预算核算（零侵入）。
- **严重级别**：ERROR。
- **修复方式**：调整 `budget` 节阈值（max_tokens / max_calls / max_wall_s），或改 `on_exceed: "warn"` 仅告警。

#### `RUN_DETERMINISTIC_LLM_CALL`
确定性执行模式（`run --deterministic`）下尝试 LLM 调用。
- **触发条件**：以 `--deterministic` 启动的 run 中发生任何 LLM 调用（`@~...~` 行为表达式执行）——零 LLM 不变量在**调用汇点、provider 调用前**结构性拦截（被拦调用不发出，无部分 LLM 态）。与 `RUN_BUDGET_EXCEEDED` 分面：本码 = run 级零容忍不变量（无阈值、无 warn 面），预算码 = 用户配置阈值。
- **严重级别**：ERROR。
- **修复方式**：移除/改写触发 LLM 的 `@~...~` 调用点（确定性模式的目标正是判定/验证路径零 LLM），或去掉 `--deterministic` 以允许 LLM。边界：拦截面 = LLM 调用汇点（同 journal/budget）；流式 `ai.stream_call` 与 `meta.eval` 子进程不经本守卫（见 `docs/KNOWN_LIMITS.md`）。

#### `RUN_JSON_PARSE_ERROR`
JSON 解析/序列化失败（malformed JSON / 不可序列化值）。
- **触发条件**：`json.parse` 遇非法 JSON；`json.stringify`/`json.pretty` 遇不可序列化值（如循环引用）。fail-fast 抛可捕获异常（经 `try/except` 处理），不静默返回空值、无 print 副作用。
- **严重级别**：ERROR。
- **修复方式**：检查 JSON 字符串格式合法性（引号、逗号、括号配对）；如需"失败 = 显式可判"的宽松形态，改用 `json.parse_or_none(s)`（malformed 返回 `None`，无副作用）。

---

### 内核诊断（KDIAG_）

> 经 `kernel_diagnostic` 事件发射的运行时异常/降级/策略点；一般为**警告/事件**（不阻断执行）。

#### `KDIAG_PROTOCOL_TO_PROMPT_FALLBACK`
协议回退：`to_prompt` 能力缺失，回退默认提示词构造。
- **触发条件**：类型未实现 `to_prompt` 协议。
- **严重级别**：WARNING。
- **修复方式**：如需定制提示，为类型实现协议方法；回退不阻断执行。

#### `KDIAG_PROTOCOL_FROM_PROMPT_FALLBACK`
协议回退：`from_prompt` 解析能力缺失，回退默认解析。
- **触发条件**：类型未实现 `from_prompt` 解析协议。
- **严重级别**：WARNING。
- **修复方式**：如需定制解析，为类型实现协议方法；回退通常保持兼容行为。

#### `KDIAG_PROTOCOL_PAYLOAD_PROMPT_FALLBACK`
协议回退：payload 提示构造能力缺失，使用默认 payload。
- **触发条件**：类型未实现 payload 提示构造协议。
- **严重级别**：WARNING。
- **修复方式**：需定制时实现协议方法；否则回退即可。

#### `KDIAG_PROTOCOL_VALIDATE_FALLBACK`
协议回退：输出校验能力缺失，跳过自定义校验。
- **触发条件**：类型未实现输出校验协议。
- **严重级别**：WARNING。
- **修复方式**：需强校验时实现协议方法；回退是 fail-open 行为。

#### `KDIAG_PROTOCOL_SNAPSHOT_FALLBACK`
协议回退：快照能力缺失，使用默认快照机制。
- **触发条件**：类型未实现快照协议。
- **严重级别**：WARNING。
- **修复方式**：需定制快照语义时实现协议方法。

#### `KDIAG_PROTOCOL_RESTORE_FALLBACK`
协议回退：恢复能力缺失，使用默认恢复机制。
- **触发条件**：类型未实现恢复协议。
- **严重级别**：WARNING。
- **修复方式**：需定制恢复语义时实现协议方法。

#### `KDIAG_POLICY_MODULE_OVERRIDE`
策略：非 kernel-native 注册尝试覆盖 kernel-native 保留名被忽略。
- **触发条件**：以非 kernel-native 元数据注册了与 kernel-native 保留名同名的模块。
- **严重级别**：WARNING。
- **修复方式**：换用不与内核原生模块重名的注册名。

#### `KDIAG_RUNTIME_COLLECT_SKIP`
运行时降级：`collect` 目标被跳过。
- **触发条件**：`collect` 目标不可收集时降级跳过。
- **严重级别**：WARNING。
- **修复方式**：检查 `collect` 目标的可收集性；降级为尽力而为。

#### `KDIAG_RUNTIME_STAGE_SKIP`
运行时降级：某执行阶段被跳过。
- **触发条件**：执行阶段因条件不满足被跳过。
- **严重级别**：WARNING。
- **修复方式**：按阶段上下文判断是否需补全该阶段能力。

#### `KDIAG_RUNTIME_ENV_LIMIT`
运行时环境限制异常（栈溢出/内存/系统错误）根因保留。
- **触发条件**：`RecursionError`/`MemoryError`/`SystemError` 被判定为环境限制异常。
- **严重级别**：WARNING。
- **修复方式**：按真实根因处理（如提升宿主递归上限、优化内存使用）。

#### `KDIAG_RUNTIME_PRE_EVAL_FALLBACK`
运行时降级：类字段默认值预评估失败，留待实例化时求值。
- **触发条件**：STAGE 6 前类字段默认值预评估（尽力而为优化）失败（表达式依赖运行期状态等）。
- **严重级别**：WARNING。
- **修复方式**：属正常回退（实例化路径完整重试 + fail-fast）；仅当实例化时报错才需排查默认值表达式。

#### `KDIAG_RUNTIME_SPECIALIZATION_FALLBACK`
运行时降级：跨引擎 round-trip 特化类重建失败（注册表封印），值回落基类。
- **触发条件**：目标引擎已编译基类但封印后不可 `create_subclass` 重建特化类（`docs/KNOWN_LIMITS.md §十` 契约：特化跨引擎身份保真须目标引擎已编译该类）。
- **严重级别**：WARNING。
- **修复方式**：回退后值字段与基类方法可用，仅特化身份丢失；如需身份保真须目标引擎先编译该类。

### 宿主隔离（HOST_）

> ihost 隔离子环境（独立 Engine 子 run）的宿主侧降级/边界事件；均为运行时告警，不阻断执行。

#### `HOST_ISOLATE_LLM_INHERIT_FAILED`
ihost 隔离子环境 LLM 配置继承应用失败（spawn 时点父配置快照未能应用到子 provider）。
- **触发条件**：子环境 on_ready 钩子应用继承快照时失败——子 provider 不支持状态恢复（自定义/replay provider 等非 stateful 形态）或快照内容异常。
- **严重级别**：WARNING（不阻断：子 run 照常执行，其 LLM 调用按自身配置状态得清晰错误）。
- **修复方式**：排查子项目插件发现面（子 provider 形态）或父环境 LLM 配置状态；继承语义见 docs/syntax/11_modules.md §11.6。

### 词嵌入（EMB_）

> embedding 调用是一等 I/O 面（机制同构 LLM 面）：契约违约/服务失败/维度保序违约等错误面独立可定位。均为运行时诊断，fail-fast 不静默回退。

#### `EMB_CONFIG_MISSING`
embedding 配置缺失（端点/凭据/模型未提供且未进入 mock 模式）。
- **触发条件**：调用 embedding 面时 `base_url` / `api_key` / `model` 任一缺失（或 openai 客户端依赖未安装）。
- **严重级别**：ERROR。
- **修复方式**：配置 embedding 端点凭据与模型（`ai` 模块面 / provider `set_config`），或进入 `MOCK:VEC` 确定性 mock 模式。

#### `EMB_SERVICE_ERROR`
embedding 服务调用失败（网络/客户端初始化/供应商错误）。
- **触发条件**：`POST /v1/embeddings` 请求失败（连接错误、鉴权失败、供应商侧异常）。
- **严重级别**：ERROR。
- **修复方式**：检查端点连通性、密钥有效性与供应商侧错误信息。

#### `EMB_BATCH_ORDER`
embedding 批量保序契约违约（响应与请求不匹配）。
- **触发条件**：供应商响应数量 ≠ 请求文本数（保序不可恢复）；mock `SEQ` 场景缓冲余量小于请求数。
- **严重级别**：ERROR。
- **修复方式**：供应商响应须与请求文本按序一一对应；mock `SEQ` 序列长度须覆盖全部消费批次的请求数。

#### `EMB_DIMENSION_MISMATCH`
embedding 维度失配。
- **触发条件**：批内向量维度不一致；检索查询与语料维度不同；mock `SEQ` 向量维度与目标不符。
- **严重级别**：ERROR。
- **修复方式**：同一批/同一检索面的向量须同维度；`dimensions` 请求位与供应商实际输出保持一致。

#### `EMB_ZERO_NORM`
零范数向量（余弦相似度未定义）。
- **触发条件**：相似度/检索计算遇全零向量；mock 派生退化为零范数（实际不可达）。
- **严重级别**：ERROR。
- **修复方式**：避免全零向量输入检索/相似度计算。

#### `EMB_INVALID_INPUT`
embedding/检索非法输入。
- **触发条件**：空文本批、空检索语料、`k` 非正整数、向量含非有限值（NaN/Inf）、空向量、mock 指令非法（`SEQ` 载荷非二维数组/JSON 解析失败）。
- **严重级别**：ERROR。
- **修复方式**：检查输入面：texts 非空、k 为正整数、向量元素为有限浮点数、mock 指令载荷合法。

### 知识注册表（KNW_）

> 已验证知识注册表（一等值类型 `knowledge`）的运行期契约违约：登记/更正/审计面 +
> 世界模型 KB 面（词表治理门/事实日志契约）。均为运行时诊断，fail-fast 不静默降级。

#### `KNW_CHECK_REJECTED`
知识登记/更正未过验证门，或谓词引用跨快照丢失。
- **触发条件**：`knowledge.store`/`amend` 时验证谓词 `check(value)` 求值为假；或条目经 `save_state`/`load_state` 恢复后验证谓词引用丢失再 `amend`。
- **严重级别**：ERROR。
- **修复方式**：先让值通过确定性验证再登记；跨快照恢复后条目须重新 `store`（谓词引用不入值快照，属已知边界）。

#### `KNW_KEY_EXISTS`
`knowledge.store` 键已登记或键非法。
- **触发条件**：对已登记键 `store`（"登记"与"更正"机器强制区分）；或键非非空 str。
- **严重级别**：ERROR。
- **修复方式**：已登记条目的更新走 `amend`（附非空 reason 审计）；检查键为非空字符串。

#### `KNW_REASON_EMPTY`
`knowledge.amend` / `amend_fact` / `retract` 理由为空，或键/fact_id 未登记。
- **触发条件**：`amend`/`amend_fact`/`retract` 的 reason 为空字符串（审计链完整性要求）；或对未登记键/未知 fact_id 执行。
- **严重级别**：ERROR。
- **修复方式**：更正/墓碑必须附非空理由；操作仅适用于已登记条目/已登记事实。

#### `KNW_VOCAB_UNREGISTERED`
`knowledge.add_fact` 引用未注册词表项（KB 治理门）。
- **触发条件**：`add_fact` 的世界/关系类型/主语词/对象词任一未在治理词表注册（allowlist 机器强制，确定性零 LLM）。
- **严重级别**：ERROR。
- **修复方式**：先经 `register_world`/`register_relation`/`register_word` 注册对应词表项，再 `add_fact`。

#### `KNW_VOCAB_EXISTS`
`knowledge.register_word` / `register_relation` / `register_world` 重复注册。
- **触发条件**：对已注册词表项再次登记（词表单一权威源，KB 值面无更正通道）。
- **严重级别**：ERROR。
- **修复方式**：已注册项经 `word`/`relation`/`world` 查询其记录；治理更正归调用方流程，KB 值面只有登记。

#### `KNW_VOCAB_MALFORMED`
`knowledge` 词表/事实方法参数形态非法。
- **触发条件**：词表名/事实字段非非空 str、`is_set`/`transitive`/`multi_valued` 非 bool、`members` 非 list、`entries` 非 dict、`size_rank` 非 int（动态 `any` 面穿透静态类型时）。
- **严重级别**：ERROR。
- **修复方式**：按方法签名提供正确形态的值。

#### `KNW_FACT_DUPLICATE`
`knowledge.add_fact` 重复 active 事实（去重机器强制）。
- **触发条件**：同 `(world, s, r, o)` 已有 status 为 `active` 的事实（`by_triple` 索引成员检查）。
- **严重级别**：ERROR。
- **修复方式**：事实已存在则经 `get_fact`/`lookup_pair` 查询其记录；更正走 `amend_fact`（附 reason），废止走 `retract`（附 reason）。

#### `KNW_FACT_NOT_FOUND`
`knowledge` 事实面操作引用未知 fact_id。
- **触发条件**：`get_fact`/`source`/`history_fact`/`expand`/`compare`/`retract`/`amend_fact` 的 fact_id 不在事实日志（或 fact_id 非 str）。
- **严重级别**：ERROR。
- **修复方式**：fact_id 须为 `add_fact` 返回值（或经 `facts` 枚举确认）；查询面未知 id 经 `get_fact` 返回 null 预检。

#### `KNW_FACT_RETRACTED`
对已 `retract`（墓碑）事实再 `retract` / `amend_fact`。
- **触发条件**：目标事实 status 已为 `retracted`（append-only 纪律：墓碑只读）。
- **严重级别**：ERROR。
- **修复方式**：墓碑事实只读（`get_fact`/`facts`/`history_fact` 仍可查全史）；恢复语义 = 登记新事实（不复活的版本是新事实）。

#### `KNW_KB_ARTIFACT_MALFORMED`
`world_model.load_kb` / `save_kb` 的 KB artifact 结构非法。
- **触发条件**：artifact 非合法 JSON / 顶层非对象 / 缺封套字段（`schema_version`/`content_hash`/`facts`/`vocab`/`seq`）/ facts-vocab 记录缺必填字段或形态错 / `seq` 非负 int 违约。
- **严重级别**：ERROR。
- **修复方式**：经 `world_model.save_kb` 重新导出合规 artifact（`save_kb` 保存前同构结构门——畸形 KB 面在此即 fail-fast）。

#### `KNW_KB_SCHEMA_VERSION`
`world_model.load_kb` 遇到未知 `schema_version`。
- **触发条件**：artifact 的 `schema_version ≠ 1`（当前唯一支持版本；无自动迁移面）。
- **严重级别**：ERROR。
- **修复方式**：以支持该版本的引擎加载，或由导出方按当前版本重新导出。

#### `KNW_KB_HASH_MISMATCH`
`world_model.load_kb` 的 `content_hash` 验证失败（内容寻址完整性门）。
- **触发条件**：canonical 载荷（facts/vocab/seq 规范形态）重算 sha256 ≠ artifact 所载 `content_hash`——数据损坏或被篡改。
- **严重级别**：ERROR。
- **修复方式**：重新导出（`save_kb` 返回值 = 钉扎基准 hash）；跨传输场景以 hash 比对检出损坏后重传。

### 层级记忆基底（MEM_）

> 一等值类型 `memory` 的运行期契约违约：分层/容量/键存在性。均为运行时诊断，fail-fast 不静默降级。

#### `MEM_KEY_EXISTS`
`memory.encode` 键已存在或键非法。
- **触发条件**：对已存在键 `encode`（跨层均检测）；或键非非空 str。
- **严重级别**：ERROR。
- **修复方式**：重复键须先 `prune` 或 `promote`/`demote` 到其它层再 `encode`；键须为非空字符串。

#### `MEM_KEY_NOT_FOUND`
`memory` 操作引用未登记键。
- **触发条件**：`promote`/`demote`/`content_hash` 等对未 `encode` 的键操作。
- **严重级别**：ERROR。
- **修复方式**：确认键已 `encode` 登记；跨层操作前用 `tier()` 确认条目位置。

#### `MEM_TIER_FULL`
`memory` 层容量已满，拒绝写入。
- **触发条件**：`encode`/`promote` 目标层条目数已达 `set_capacity` 设定的上限。
- **严重级别**：ERROR。
- **修复方式**：先 `prune`（遗忘）或 `demote`（降级）腾出空间；或 `set_capacity` 扩大容量。

#### `MEM_TIER_UNKNOWN`
`memory` 操作引用了非法层名。
- **触发条件**：层名参数非 `working_set`/`session`/`knowledge`/`long_term` 四值之一。
- **严重级别**：ERROR。
- **修复方式**：层名须为固定四值之一。

### 配置（CFG_）

`api_config.json` 加载与校验失败的诊断码（`ai.load_project_config` / `ai.load_config` / `ai.apply_config`）。校验失败 fail-fast raise `InterpreterError`，不静默回退 mock。配置加载为显式动作：`ai.load_project_config()` 对缺失文件为 no-op（合法态），存在但校验失败则 fail-fast。

#### `CFG_CONFIG_NOT_FOUND`
配置加载指定的配置文件不存在。
- **触发条件**：`ai.load_config` 指定路径下无 api_config.json（`load_project_config` 对缺失文件 no-op，不触发本码）。
- **严重级别**：ERROR。
- **修复方式**：确认路径正确（相对路径锚定 project_root），或创建 api_config.json。

#### `CFG_CONFIG_INVALID_JSON`
配置文件不是合法的 JSON。
- **触发条件**：api_config.json 内容 JSON 解析失败。
- **严重级别**：ERROR。
- **修复方式**：检查 JSON 语法（引号、逗号、括号配对）。

#### `CFG_CONFIG_NOT_OBJECT`
配置文件顶层不是 JSON 对象（dict）。
- **触发条件**：api_config.json 顶层非对象。
- **严重级别**：ERROR。
- **修复方式**：配置必须是对象，如 `{"default_model": {...}}`。

#### `CFG_CONFIG_MISSING_DEFAULT`
配置缺少 default_model 字段。
- **触发条件**：api_config.json 无 default_model 字段。
- **严重级别**：ERROR。
- **修复方式**：添加 default_model 字段（对象形态或命名模型引用字符串）。

#### `CFG_CONFIG_MODEL_NOT_OBJECT`
模型条目不是 JSON 对象（dict）。
- **触发条件**：default_model 或 models 的某条目非对象。
- **严重级别**：ERROR。
- **修复方式**：每个模型条目必须是对象，含 base_url/api_key/model（或 provider 引用）。

#### `CFG_CONFIG_MISSING_FIELD`
模型条目缺少必要字段（base_url/api_key/model 或 provider 引用）。
- **触发条件**：模型条目缺必需字段。
- **严重级别**：ERROR。
- **修复方式**：补全缺失字段；model 必需，连接信息经 provider 引用或直接 base_url/api_key。

#### `CFG_CONFIG_INVALID_FIELD_TYPE`
配置字段类型错误（如 base_url 不是字符串、timeout 不是数字）。
- **触发条件**：字段值类型不符 schema。
- **严重级别**：ERROR。
- **修复方式**：按字段类型要求修正：base_url/api_key/model 为 str，timeout 为 number，reasoning 为 bool。

#### `CFG_CONFIG_UNKNOWN_MODEL_REF`
default_model 引用的命名模型在 models 中不存在。
- **触发条件**：default_model 为字符串但 models 无该键。
- **严重级别**：ERROR。
- **修复方式**：确认 default_model 字符串与 models 的键名一致（区分大小写）。

#### `CFG_CONFIG_UNKNOWN_PROVIDER`
模型引用的 provider 在 providers 中不存在。
- **触发条件**：model 的 provider 字段在 providers 中无对应键。
- **严重级别**：ERROR。
- **修复方式**：确认 model 的 provider 字段与 providers 的键名一致（区分大小写）。

#### `CFG_CONFIG_ENV_VAR_MISSING`
配置中 `{env:VAR}` 引用的环境变量未设置。
- **触发条件**：providers/models 的 base_url/api_key 含 `{env:VAR}` 但 VAR 未设置。
- **严重级别**：ERROR。
- **修复方式**：设置对应环境变量，或移除 `{env:VAR}` 引用改为直接写值。

#### `CFG_CONFIG_UNKNOWN_FIELD`
api_config model 条目含未知字段。
- **触发条件**：model 条目出现允许集之外的字段（拼写错误/废弃字段）。
- **严重级别**：ERROR。
- **修复方式**：按报错消息列出的允许字段修正（model 条目允许：model/provider/base_url/api_key/timeout/reasoning/max_tokens/temperature/top_p/top_k/seed/extra_body/kind）。未知字段不再静默丢弃——配置面的拼写错误须显式暴露（可审计性纪律）。

#### `CFG_CONFIG_INVALID_BUDGET`
api_config.json `budget` 节形态错误。
- **触发条件**：`budget` 节存在但形态非法——阈值（max_tokens / max_calls / max_wall_s）非正数、`on_exceed` 非 `"warn"|"fail"`、含未知字段。CLI `run` 启动期校验（budget 节自身形态 = 本码责任面；文件级 JSON 有效性归其他 CFG_ 码）。用户显式写了预算且写错须 fail-fast 显形，不静默忽略。
- **严重级别**：ERROR。
- **修复方式**：`budget` 节修正为 `{"max_tokens": 正数, "max_calls": 正数, "max_wall_s": 正数, "on_exceed": "warn"|"fail"}`（各阈值可选）；或移除该节（无预算核算）。

---

## 深入指引

- 语言级限制与诊断码对应的行为边界：docs/KNOWN_LIMITS.md
- 异常类型层次与 `try/except` 捕获（LLM 错误兜底）：docs/syntax/04_control_flow.md
- llmexcept 快照隔离与 `RUN_LLMEXCEPT_SNAPSHOT_VIOLATION`：docs/syntax/10_robustness.md
- LLM 可调用类契约（`RUN_LLM_CALLABLE` 相关）：docs/syntax/08_llm_callable.md
- 意图注释放置诊断（`SEM_INTENT_PLACEMENT` 等）：docs/syntax/09_intent_system.md
