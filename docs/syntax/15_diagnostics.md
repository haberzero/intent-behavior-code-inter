# 15 · 诊断码参考

> 全量诊断码的用户友好参考：每个码的**触发条件**（什么时候产生）与**修复指引**（如何消除）。
> **机器权威源**：`core/base/diagnostics/catalog.py`（`CODE_CATALOG`）——`DiagnosticFormatter` 渲染错误时即从该目录附加"说明/修复"段。**本文档是人类参考页**：目录（code → title/fix）以 catalog 为单一事实来源；本文档在目录之上补充人类阅读所需的**触发条件**与**严重级别**，且与目录保持**码集合一致**（`tests/contracts/test_diagnostic_catalog.py` CAT-6 强制文档码集合 == 目录码集合，防新增码漏登记/孤儿）。说明/修复文本如与 catalog 冲突，以 catalog 为准。
>
> 诊断码分域：词法 `LEX_` / 语法 `PAR_` / 语义 `SEM_` / 依赖 `DEP_` / 内部 `INT_` / 运行时 `RUN_` / 内核诊断 `KDIAG_`。

## 诊断工具

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

## 如何阅读

- **触发条件**：该诊断在何种输入下产生（精确判断）。
- **修复指引**：如何消除该诊断。
- 严重级别：编译期诊断（LEX/PAR/SEM/DEP/INT）为 `ERROR`（编译中止）；运行时（RUN）在执行时抛出；内核诊断（KDIAG）为运行时告警/事件（不阻断执行）。

---

## 词法（LEX_）

源码扫描阶段的诊断。

### `LEX_INVALID_CHAR`
遇到了源码中不被语言接受的字符。
- **触发条件**：词法器遇到语言字符集之外的字符。
- **严重级别**：ERROR。
- **修复方式**：删除或替换该字符；确需表示反斜杠时用转义序列，行为表达式内用 `\$` 表示字面 `$`。

### `LEX_UNTERMINATED_STRING`
字符串字面量没有闭合引号（或提前换行）。
- **触发条件**：字符串字面量缺少结尾引号，或在闭合前遇到换行。
- **严重级别**：ERROR。
- **修复方式**：补上结尾引号；多行文本请使用行为表达式（`@~ ... ~`）而非跨行字符串。

### `LEX_UNTERMINATED_BLOCK`
块结构没有闭合（如行为表达式内的 `[` 未配 `]`）。
- **触发条件**：行为表达式内的方括号等块结构未闭合。
- **严重级别**：ERROR。
- **修复方式**：补上缺失的闭括号，保持括号配对。

### `LEX_INVALID_NUMBER`
数字字面量格式非法（如多余小数点、非法进制前缀）。
- **触发条件**：数字字面量不符合语言格式规则。
- **严重级别**：ERROR。
- **修复方式**：按语言数字字面量规则书写（如 `0x`/`0b` 前缀、单一小数点）。

### `LEX_INVALID_ESCAPE`
字符串内使用了无效的转义序列。
- **触发条件**：字符串中出现语言不支持的转义序列。
- **严重级别**：ERROR。
- **修复方式**：使用语言支持的转义（`\n` `\t` `\\` `\"` `\'` 等）；未知转义改为合法写法或字面字符。

### `LEX_UNTERMINATED_BEHAVIOR`
行为表达式（`@~ ... ~`）没有闭合标记 `~`。
- **触发条件**：`@~` 开始后未遇到结束标记 `~`。
- **严重级别**：ERROR。
- **修复方式**：补上结束标记 `~`，确保 `@~` 与 `~` 成对出现。

---

## 语法（PAR_）

解析阶段的诊断。

### `PAR_EXPECTED_TOKEN`
语法解析到这里预期某个特定符号，但出现了别的内容。
- **触发条件**：解析器在该位置预期特定 token（如冒号、右括号、关键字）。
- **严重级别**：ERROR。
- **修复方式**：按报错位置的预期补全符号。

### `PAR_UNEXPECTED_TOKEN`
解析器在该位置遇到了不应出现的符号。
- **触发条件**：该位置出现多余/错放的 token。
- **严重级别**：ERROR。
- **修复方式**：检查该符号是否多余或放错位置（如多余右括号、多余逗号）。

### `PAR_INVALID_SYNTAX`
该位置的写法不符合语言的语法规则。
- **触发条件**：语句/表达式形态不符合语法规则。
- **严重级别**：ERROR。
- **修复方式**：对照语法文档检查语句形态；确认关键字、运算符、缩进写法正确。

### `PAR_UNEXPECTED_EOF`
文件提前结束，还有未完成的语法结构。
- **触发条件**：文件在语法结构完整前结束。
- **严重级别**：ERROR。
- **修复方式**：补齐未闭合的语句/块/括号/行为表达式。

### `PAR_INDENTATION_ERROR`
缩进不符合语言规则（块结构依赖缩进表达层级）。
- **触发条件**：缩进层级不一致或空格/制表符混用。
- **严重级别**：ERROR。
- **修复方式**：统一使用一致的缩进（空格/制表符不要混用），对齐所属块的缩进级别。

### `PAR_MULTIPLE_INTENTS`
同一位置出现了多个意图声明。
- **触发条件**：同一语句/块位置出现多个意图注释。
- **严重级别**：ERROR。
- **修复方式**：每条语句/块只保留一个意图注释。

### `PAR_DEPRECATED_CAST_SYNTAX`
使用了已废弃的强制类型转换语法。
- **触发条件**：使用旧式强制转换写法。
- **严重级别**：ERROR。
- **修复方式**：改用现行语法，详见语法文档。

### `PAR_POSITIONAL_AFTER_KEYWORD`
位置实参出现在具名实参之后。
- **触发条件**：调用中位置实参排在具名实参之后。
- **严重级别**：ERROR。
- **修复方式**：把位置实参全部放到具名实参之前。

---

## 语义（SEM_）

语义检查阶段的诊断。

### `SEM_UNDEFINED_SYMBOL`
引用了未定义的变量/函数/模块名。
- **触发条件**：名称在使用前未声明，或导入遗漏/拼写错误。
- **严重级别**：ERROR。
- **修复方式**：在使用前声明该名称，或检查拼写/导入是否遗漏。

### `SEM_REDEFINITION`
同一作用域内重复声明了同名符号。
- **触发条件**：同一作用域内同名符号重复声明。
- **严重级别**：ERROR。
- **修复方式**：删除重复声明，或改用不同名称；注意与内建/已导入名的冲突。

### `SEM_IMPORT_CONFLICT`
导入的名称与已有符号冲突。
- **触发条件**：导入名与当前作用域符号冲突。
- **严重级别**：ERROR。
- **修复方式**：改用别名导入（`as`）或调整本地声明，消除命名冲突。

### `SEM_TYPE_MISMATCH`
赋值/实参/运算两侧的类型不兼容。
- **触发条件**：赋值、实参传递或二元运算两侧类型不兼容。
- **严重级别**：ERROR。
- **修复方式**：把一侧显式转换为另一侧类型，或改用兼容类型。

### `SEM_ARG_COUNT_MISMATCH`
调用提供的实参数量与被调用的形参数量不符。
- **触发条件**：实参数量与形参数量不符（且无默认值/可变参数承接）。
- **严重级别**：ERROR。
- **修复方式**：补齐/删减实参，或为缺省参数提供默认值。

### `SEM_DUAL_ASSIGNABLE`
方法重写（override）签名与父类约束不兼容。
- **触发条件**：重写方法的参数/返回类型与父类声明不兼容。
- **严重级别**：ERROR。
- **修复方式**：保持重写方法的参数/返回类型与父类声明兼容。

### `SEM_CAST_NO_CONVERTER`
目标类型没有提供从源类型的转换能力。
- **触发条件**：类型转换目标缺少源类型→目标类型的转换协议。
- **严重级别**：ERROR。
- **修复方式**：为目标类型实现转换协议，或改用可转换的类型路径。

### `SEM_CONTAINER_METHOD_HINT`
容器类型上访问了不存在或不适用的方法。
- **触发条件**：容器对象上调用其不支持的方法。
- **严重级别**：ERROR。
- **修复方式**：检查容器实际类型，改用其支持的方法。

### `SEM_PROTOCOL_SIGNATURE`
提示协议方法的签名与协议约定不符。
- **触发条件**：协议方法（如提示协议）签名与约定不符。
- **严重级别**：WARNING。
- **修复方式**：按协议约定的参数个数/返回类型修正签名。

### `SEM_SUPER_OUTSIDE_METHOD`
`super` 只在类方法体内可用。
- **触发条件**：在非类方法上下文使用 `super`。
- **严重级别**：ERROR。
- **修复方式**：把 `super` 调用移入类方法，或检查是否在错误的作用域使用。

### `SEM_YIELD_OUTSIDE_FUNCTION`
`yield` / `yield from` 只能在函数体内使用。
- **触发条件**：模块顶层或非函数上下文出现 `yield`/`yield from`。
- **严重级别**：ERROR。
- **修复方式**：把 `yield` 移入函数（`func`）体；含 `yield` 的函数即惰性生成器。

### `SEM_UNRESOLVED_TYPE`
类型注解中的类型名称无法解析。
- **触发条件**：注解引用的类型未定义/未导入。
- **严重级别**：ERROR。
- **修复方式**：确认该类型已定义/导入，且名称拼写正确。

### `SEM_DUPLICATE_KEYWORD`
调用中同一具名参数被重复提供。
- **触发条件**：同一具名实参出现多次。
- **严重级别**：ERROR。
- **修复方式**：移除重复的具名实参。

### `SEM_UNKNOWN_KEYWORD`
调用提供了被调函数不认识的具名实参。
- **触发条件**：具名实参名与被调函数参数名不匹配。
- **严重级别**：ERROR。
- **修复方式**：使用被调函数声明的参数名，或为函数增加该参数。

### `SEM_MISSING_REQUIRED_ARG`
调用缺少必填的实参。
- **触发条件**：必填参数未被提供。
- **严重级别**：ERROR。
- **修复方式**：提供全部必填实参，或为该参数提供默认值。

### `SEM_DEFAULT_TYPE_MISMATCH`
参数默认值的类型与参数注解不一致。
- **触发条件**：默认值类型与参数类型注解不符。
- **严重级别**：ERROR。
- **修复方式**：把默认值改为与参数类型一致的类型。

### `SEM_TOO_MANY_POSITIONAL`
调用提供了过多的位置实参。
- **触发条件**：位置实参数超过形参数（无 `*args` 承接）。
- **严重级别**：ERROR。
- **修复方式**：删减位置实参；其余需求用具名实参或可变参数承载。

### `SEM_MISSING_RETURN_ANNOTATION`
函数声明缺少返回类型注解。
- **触发条件**：函数（含 lambda）声明缺少 `->` 返回类型。
- **严重级别**：ERROR。
- **修复方式**：为函数补充 `->` 返回类型（显式类型、`auto` 或 `any`）。

### `SEM_MULTI_TYPE_LIST_REMOVED`
多类型列表声明语法已移除。
- **触发条件**：使用已移除的多类型列表声明语法。
- **严重级别**：ERROR。
- **修复方式**：改用单一元素类型 `list[T]`，异构内容用 `tuple` 或显式转换表达。

### `SEM_INVALID_SCOPE`
声明出现在不允许的作用域（如模块顶层 vs 函数内错位）。
- **触发条件**：声明位置与作用域规则不符。
- **严重级别**：ERROR。
- **修复方式**：把声明移到合法作用域；检查变量/函数归属层级。

### `SEM_NONLOCAL_NOT_FOUND`
`nonlocal` 引用的外层变量不存在。
- **触发条件**：`nonlocal` 声明的名称在直接外层作用域未声明。
- **严重级别**：ERROR。
- **修复方式**：确认该变量在直接外层作用域已声明。

### `SEM_INTENT_PLACEMENT`
意图注释放在了不允许的位置。
- **触发条件**：意图注释位置不合法。
- **严重级别**：ERROR。
- **修复方式**：把意图注释移到合法位置（语句/块的意图槽）。

### `SEM_INTENT_STATIC_CALL`
意图上下文方法被静态（类级）调用。
- **触发条件**：类级静态调用意图相关方法。
- **严重级别**：ERROR。
- **修复方式**：通过实例访问意图相关方法，而非类级静态调用。

### `SEM_BEHAVIOR_OUTPUT_NOT_PARSEABLE`
行为表达式声明了具体类型，但该类型没有 LLM 输出解析能力。
- **触发条件**：`-> T` 的 T 无 `__from_prompt__`/parser 能力。
- **严重级别**：ERROR。
- **修复方式**：为该类型实现 `__from_prompt__` 解析协议，或改用可解析类型（`int`/`str`/`list` 等）。

### `SEM_LLMEXCEPT_BODY_WRITE`
`llmexcept` 体内禁止写参与 LLM 调用的变量。
- **触发条件**：`llmexcept` 体写入参与插值/赋值的变量。
- **严重级别**：ERROR。
- **修复方式**：在 `llmexcept` 体内只写非参与变量，避免污染重试快照。

### `SEM_LLMEXCEPT_BINDING`
`llmexcept` 绑定形式不符合约定（缺失/多余绑定）。
- **触发条件**：`llmexcept` 绑定形式不合法。
- **严重级别**：ERROR。
- **修复方式**：按 `llmexcept` 绑定语法补全或移除绑定。

### `SEM_LLMEXCEPT_SCOPE_BINDING`
`llmexcept` 的作用域绑定写法不合法。
- **触发条件**：作用域绑定语句写法错误。
- **严重级别**：ERROR。
- **修复方式**：检查 `llmexcept` 作用域绑定语句的写法与位置。

### `SEM_LLMEXCEPT_MUTATING_CALL`
`llmexcept` 保护区域内调用了可能突变参与变量的函数。
- **触发条件**：保护区域内调用会突变参与变量的函数。
- **严重级别**：ERROR。
- **修复方式**：避免在保护区域内做副作用突变，或把调用移到 `llmexcept` 之外。

### `SEM_LLMEXCEPT_FILE_WRITE`
`llmexcept` 保护区域内执行了文件写操作（快照隔离下不允许）。
- **触发条件**：保护区域内执行文件写。
- **严重级别**：ERROR。
- **修复方式**：把文件写移到 `llmexcept` 保护区域之外。

### `SEM_UNCATEGORIZED`
未归类语义错误（无专属码）。
- **触发条件**：语义错误无对应专属诊断码。
- **严重级别**：ERROR。
- **修复方式**：按报错消息的具体内容定位并修复。

### `SEM_INTERNAL_SENTINEL`
内部哨兵值泄漏到了用户可见的错误面。
- **触发条件**：内部哨兵值泄漏（编译器内部错误信号）。
- **严重级别**：ERROR。
- **修复方式**：通常表示编译器内部 bug；请记录触发代码供维护者排查。

---

## 依赖（DEP_）

模块导入与依赖图阶段的诊断。

### `DEP_MODULE_NOT_FOUND`
导入的模块找不到。
- **触发条件**：模块路径不存在或不在搜索路径。
- **严重级别**：ERROR。
- **修复方式**：确认模块路径正确、模块文件存在且在项目根/插件搜索路径内。

### `DEP_FILE_NOT_FOUND`
引用/入口文件不存在。
- **触发条件**：引用的文件路径不存在。
- **严重级别**：ERROR。
- **修复方式**：确认文件路径拼写与存在性。

### `DEP_INVALID_IMPORT_POSITION`
`import` 语句出现在文件非头部位置。
- **触发条件**：`import` 出现在其它语句之后。
- **严重级别**：ERROR。
- **修复方式**：把所有 `import` 移到文件开头（其它语句之前）。

### `DEP_GRAPH_ERROR`
依赖图构建失败（模块依赖关系无法解析）。
- **触发条件**：模块依赖关系无法构建。
- **严重级别**：ERROR。
- **修复方式**：检查模块间依赖声明的合法性。

### `DEP_FAILED_DEPENDENCY`
被依赖的模块编译失败，连带本模块报错。
- **触发条件**：依赖模块编译失败。
- **严重级别**：ERROR。
- **修复方式**：先修复被依赖模块的编译错误。

### `DEP_SECURITY_ERROR`
导入被安全策略拒绝（越界/不可信路径）。
- **触发条件**：导入路径超出安全策略允许范围。
- **严重级别**：ERROR。
- **修复方式**：调整导入路径或安全策略，使导入在允许范围内。

### `DEP_CIRCULAR_IMPORT`
模块间存在循环导入。
- **触发条件**：模块依赖图出现环。
- **严重级别**：ERROR。
- **修复方式**：打破循环：把共享部分抽到独立模块，或改为延迟导入。

---

## 内部（INT_）

解释器内部错误（编译器未能归类的内部异常）。

### `INT_INTERNAL_ERROR`
编译器内部错误（不应出现在正常输入下）。
- **触发条件**：编译器内部断言/不变量失败。
- **严重级别**：ERROR。
- **修复方式**：请记录触发代码与上下文，提交给维护者。

### `ICE_TYPE_LEAK`
内部类型泄漏到用户可见面。
- **触发条件**：编译器内部类型表示泄漏到用户可见错误。
- **严重级别**：ERROR。
- **修复方式**：编译器内部类型表示问题；请记录触发代码提交维护者。

---

## 运行时（RUN_）

执行阶段的运行时错误。

### `RUN_GENERIC_ERROR`
未归类运行时错误。
- **触发条件**：运行时异常无对应专属码。
- **严重级别**：ERROR。
- **修复方式**：按报错消息的具体内容定位并修复。

### `RUN_TYPE_MISMATCH`
运行时发现类型不匹配（编译期类型与运行值不符）。
- **触发条件**：运行值与编译期类型契约不符。
- **严重级别**：ERROR。
- **修复方式**：检查产生该值的路径，确保类型契约成立。

### `RUN_UNDEFINED_VARIABLE`
运行时读取了未定义的变量。
- **触发条件**：读取未赋值/未定义的变量。
- **严重级别**：ERROR。
- **修复方式**：确保变量在使用前已赋值（含所有分支路径）。

### `RUN_DIVISION_BY_ZERO`
除数为零。
- **触发条件**：执行除法/取模时除数为零。
- **严重级别**：ERROR。
- **修复方式**：在除法前校验除数非零，或调整算法避免除零。

### `RUN_ATTRIBUTE_ERROR`
对象上没有该属性/方法。
- **触发条件**：访问对象不存在的属性/方法。
- **严重级别**：ERROR。
- **修复方式**：确认对象类型，使用其真实存在的成员。

### `RUN_INDEX_ERROR`
索引越界或键不存在。
- **触发条件**：下标越界或字典键不存在。
- **严重级别**：ERROR。
- **修复方式**：访问前校验索引范围/键存在性。

### `RUN_CALL_ERROR`
函数调用失败（函数体执行抛出）。
- **触发条件**：被调函数体执行抛出异常。
- **严重级别**：ERROR。
- **修复方式**：按报错上下文定位函数体内的异常根因。

### `RUN_LIMIT_EXCEEDED`
执行超过资源/指令上限。
- **触发条件**：超过指令数/资源上限。
- **严重级别**：ERROR。
- **修复方式**：检查是否存在死循环或超大数据；必要时调整执行上限配置。

### `RUN_LLM_ERROR`
LLM 调用失败（网络/密钥/提供者错误）。
- **触发条件**：LLM 调用网络/鉴权/提供者返回错误。
- **严重级别**：ERROR。
- **修复方式**：检查 LLM 配置（endpoint/key/model）、网络连通性与额度。

### `RUN_PERMISSION_ERROR`
运行时操作被权限策略拒绝。
- **触发条件**：操作超出权限策略允许范围。
- **严重级别**：ERROR。
- **修复方式**：调整权限策略或避开被禁止的操作。

### `RUN_LLMEXCEPT_SNAPSHOT_VIOLATION`
运行时违反了 `llmexcept` 快照隔离约束。
- **触发条件**：快照隔离区域内执行被禁止的写入/副作用。
- **严重级别**：ERROR。
- **修复方式**：避免在快照隔离区域内执行被禁止的写入/副作用。

---

## 内核诊断（KDIAG_）

> 经 `kernel_diagnostic` 事件发射的运行时异常/降级/策略点；一般为**警告/事件**（不阻断执行）。

### `KDIAG_PROTOCOL_TO_PROMPT_FALLBACK`
协议回退：`to_prompt` 能力缺失，回退默认提示词构造。
- **触发条件**：类型未实现 `to_prompt` 协议。
- **严重级别**：WARNING。
- **修复方式**：如需定制提示，为类型实现协议方法；回退不阻断执行。

### `KDIAG_PROTOCOL_FROM_PROMPT_FALLBACK`
协议回退：`from_prompt` 解析能力缺失，回退默认解析。
- **触发条件**：类型未实现 `from_prompt` 解析协议。
- **严重级别**：WARNING。
- **修复方式**：如需定制解析，为类型实现协议方法；回退通常保持兼容行为。

### `KDIAG_PROTOCOL_PAYLOAD_PROMPT_FALLBACK`
协议回退：payload 提示构造能力缺失，使用默认 payload。
- **触发条件**：类型未实现 payload 提示构造协议。
- **严重级别**：WARNING。
- **修复方式**：需定制时实现协议方法；否则回退即可。

### `KDIAG_PROTOCOL_VALIDATE_FALLBACK`
协议回退：输出校验能力缺失，跳过自定义校验。
- **触发条件**：类型未实现输出校验协议。
- **严重级别**：WARNING。
- **修复方式**：需强校验时实现协议方法；回退是 fail-open 行为。

### `KDIAG_PROTOCOL_SNAPSHOT_FALLBACK`
协议回退：快照能力缺失，使用默认快照机制。
- **触发条件**：类型未实现快照协议。
- **严重级别**：WARNING。
- **修复方式**：需定制快照语义时实现协议方法。

### `KDIAG_PROTOCOL_RESTORE_FALLBACK`
协议回退：恢复能力缺失，使用默认恢复机制。
- **触发条件**：类型未实现恢复协议。
- **严重级别**：WARNING。
- **修复方式**：需定制恢复语义时实现协议方法。

### `KDIAG_POLICY_MODULE_OVERRIDE`
策略：用户插件覆盖了 kernel-native 模块。
- **触发条件**：用户插件注册了与 kernel-native 同名的模块。
- **严重级别**：WARNING。
- **修复方式**：若覆盖为有意为之可忽略；否则移除插件避免覆盖。

### `KDIAG_POLICY_MODULE_NO_EXPORT`
策略：模块没有可导出的成员（导出表为空）。
- **触发条件**：模块导出表为空。
- **严重级别**：WARNING。
- **修复方式**：确认模块确实需要导出内容；否则属正常策略信息。

### `KDIAG_RUNTIME_COLLECT_SKIP`
运行时降级：`collect` 目标被跳过。
- **触发条件**：`collect` 目标不可收集时降级跳过。
- **严重级别**：WARNING。
- **修复方式**：检查 `collect` 目标的可收集性；降级为尽力而为。

### `KDIAG_RUNTIME_STAGE_SKIP`
运行时降级：某执行阶段被跳过。
- **触发条件**：执行阶段因条件不满足被跳过。
- **严重级别**：WARNING。
- **修复方式**：按阶段上下文判断是否需补全该阶段能力。

### `KDIAG_RUNTIME_ENV_LIMIT`
运行时环境限制异常（栈溢出/内存/系统错误）根因保留。
- **触发条件**：`RecursionError`/`MemoryError`/`SystemError` 被判定为环境限制异常。
- **严重级别**：WARNING。
- **修复方式**：按真实根因处理（如提升宿主递归上限、优化内存使用）。

## 配置（CFG_）

`api_config.json` 加载与校验失败的诊断码（`ai.load_config` / `ai.apply_config` / 引擎自动加载）。校验失败 fail-fast raise `InterpreterError`，不静默回退 mock。

### `CFG_CONFIG_NOT_FOUND`
`ai.load_config` 指定的配置文件不存在。
- **触发条件**：load_config 的路径下无 api_config.json。
- **严重级别**：ERROR。
- **修复方式**：确认路径正确（相对路径锚定入口文件目录），或创建 api_config.json。

### `CFG_CONFIG_INVALID_JSON`
配置文件不是合法的 JSON。
- **触发条件**：api_config.json 内容 JSON 解析失败。
- **严重级别**：ERROR。
- **修复方式**：检查 JSON 语法（引号、逗号、括号配对）。

### `CFG_CONFIG_NOT_OBJECT`
配置文件顶层不是 JSON 对象（dict）。
- **触发条件**：api_config.json 顶层非对象。
- **严重级别**：ERROR。
- **修复方式**：配置必须是对象，如 `{"default_model": {...}}`。

### `CFG_CONFIG_MISSING_DEFAULT`
配置缺少 default_model 字段。
- **触发条件**：api_config.json 无 default_model 字段。
- **严重级别**：ERROR。
- **修复方式**：添加 default_model 字段（对象形态或命名模型引用字符串）。

### `CFG_CONFIG_MODEL_NOT_OBJECT`
模型条目不是 JSON 对象（dict）。
- **触发条件**：default_model 或 models 的某条目非对象。
- **严重级别**：ERROR。
- **修复方式**：每个模型条目必须是对象，含 base_url/api_key/model（或 provider 引用）。

### `CFG_CONFIG_MISSING_FIELD`
模型条目缺少必要字段（base_url/api_key/model 或 provider 引用）。
- **触发条件**：模型条目缺必需字段。
- **严重级别**：ERROR。
- **修复方式**：补全缺失字段；model 必需，连接信息经 provider 引用或直接 base_url/api_key。

### `CFG_CONFIG_INVALID_FIELD_TYPE`
配置字段类型错误（如 base_url 不是字符串、timeout 不是数字）。
- **触发条件**：字段值类型不符 schema。
- **严重级别**：ERROR。
- **修复方式**：按字段类型要求修正：base_url/api_key/model 为 str，timeout 为 number，reasoning 为 bool。

### `CFG_CONFIG_UNKNOWN_MODEL_REF`
default_model 引用的命名模型在 models 中不存在。
- **触发条件**：default_model 为字符串但 models 无该键。
- **严重级别**：ERROR。
- **修复方式**：确认 default_model 字符串与 models 的键名一致（区分大小写）。

### `CFG_CONFIG_UNKNOWN_PROVIDER`
模型引用的 provider 在 providers 中不存在。
- **触发条件**：model 的 provider 字段在 providers 中无对应键。
- **严重级别**：ERROR。
- **修复方式**：确认 model 的 provider 字段与 providers 的键名一致（区分大小写）。

### `CFG_CONFIG_ENV_VAR_MISSING`
配置中 `{env:VAR}` 引用的环境变量未设置。
- **触发条件**：providers/models 的 base_url/api_key 含 `{env:VAR}` 但 VAR 未设置。
- **严重级别**：ERROR。
- **修复方式**：设置对应环境变量，或移除 `{env:VAR}` 引用改为直接写值。
