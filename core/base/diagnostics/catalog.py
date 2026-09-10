"""
core.base.diagnostics.catalog — 诊断码用户友好目录。

把机器可读的诊断码（LEX_/PAR_/SEM_/DEP_/INT_/RUN_/KDIAG_）映射为人类可读的
**友好说明**（什么情况产生）+ **修复指引**（如何消除）。是错误用户友好化的
单一权威源：`DiagnosticFormatter` 渲染时经本目录附加说明，参考文档
`docs/syntax/15_diagnostics.md` 由本目录数据驱动（数字纪律：单一事实来源，
文档不复制正文）。

每个码条目字段：
- ``title``：一句话定位（何时产生，用户第一眼理解）。
- ``fix``：修复指引（如何消除该诊断）。

新增诊断码时，除在 ``codes.py`` 注册常量外，必须同步在本目录登记条目——
``tests/contracts/test_diagnostic_catalog.py`` 强制覆盖完备（每个码都有条目，
无孤儿条目）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class CodeInfo:
    """单个诊断码的用户友好条目。"""

    title: str
    fix: str


# 码 → 条目（单点真理；键必须与 codes.py 常量一一对应）
CODE_CATALOG: Dict[str, CodeInfo] = {
    # ==================== 词法 (LEX_) ====================
    "LEX_INVALID_CHAR": CodeInfo(
        title="遇到了源码中不被语言接受的字符。",
        fix="删除或替换该字符；确需表示反斜杠时用转义序列，行为表达式内用 \\$ 表示字面 $。",
    ),
    "LEX_UNTERMINATED_STRING": CodeInfo(
        title="字符串字面量没有闭合引号（或提前换行）。",
        fix="补上结尾引号；多行文本请使用行为表达式（@~ ... ~）而非跨行字符串。",
    ),
    "LEX_UNTERMINATED_BLOCK": CodeInfo(
        title="块结构没有闭合（如行为表达式内的 '[' 未配 ']'）。",
        fix="补上缺失的闭括号，保持括号配对。",
    ),
    "LEX_INVALID_NUMBER": CodeInfo(
        title="数字字面量格式非法（如多余小数点、非法进制前缀）。",
        fix="按语言数字字面量规则书写（如 0x/0b 前缀、单一小数点）。",
    ),
    "LEX_INVALID_ESCAPE": CodeInfo(
        title="字符串内使用了无效的转义序列。",
        fix="使用语言支持的转义（\\n \\t \\\\ \\\" \\' 等）；未知转义改为合法写法或字面字符。",
    ),
    "LEX_UNTERMINATED_BEHAVIOR": CodeInfo(
        title="行为表达式（@~ ... ~）没有闭合标记 '~'。",
        fix="补上结束标记 '~'，确保 @~ 与 ~ 成对出现。",
    ),
    # ==================== 语法 (PAR_) ====================
    "PAR_EXPECTED_TOKEN": CodeInfo(
        title="语法解析到这里预期某个特定符号，但出现了别的内容。",
        fix="按报错位置的预期补全符号（常见：缺冒号、缺右括号、缺语句关键字）。",
    ),
    "PAR_UNEXPECTED_TOKEN": CodeInfo(
        title="解析器在该位置遇到了不应出现的符号。",
        fix="检查该符号是否多余或放错位置（如多余右括号、多余逗号）。",
    ),
    "PAR_INVALID_SYNTAX": CodeInfo(
        title="该位置的写法不符合语言的语法规则。",
        fix="对照语法文档检查语句形态；确认关键字、运算符、缩进写法正确。",
    ),
    "PAR_UNEXPECTED_EOF": CodeInfo(
        title="文件提前结束，还有未完成的语法结构。",
        fix="补齐未闭合的语句/块/括号/行为表达式。",
    ),
    "PAR_INDENTATION_ERROR": CodeInfo(
        title="缩进不符合语言规则（块结构依赖缩进表达层级）。",
        fix="统一使用一致的缩进（空格/制表符不要混用），对齐所属块的缩进级别。",
    ),
    "PAR_DEPRECATED_CAST_SYNTAX": CodeInfo(
        title="使用了已废弃的强制类型转换语法。",
        fix="改用现行语法（如 (Type)expr 的新形式），详见语法文档。",
    ),
    "PAR_POSITIONAL_AFTER_KEYWORD": CodeInfo(
        title="位置实参出现在具名实参之后。",
        fix="把位置实参全部放到具名实参之前。",
    ),
    # ==================== 语义 (SEM_) ====================
    # -- 符号解析 --
    "SEM_UNDEFINED_SYMBOL": CodeInfo(
        title="引用了未定义的变量/函数/模块名。",
        fix="在使用前声明该名称，或检查拼写/导入是否遗漏。",
    ),
    "SEM_REDEFINITION": CodeInfo(
        title="同一作用域内重复声明了同名符号。",
        fix="删除重复声明，或改用不同名称；注意与内建/已导入名的冲突。",
    ),
    "SEM_IMPORT_CONFLICT": CodeInfo(
        title="导入的名称与已有符号冲突。",
        fix="改用别名导入（as）或调整本地声明，消除命名冲突。",
    ),
    # -- 类型系统 --
    "SEM_TYPE_MISMATCH": CodeInfo(
        title="赋值/实参/运算两侧的类型不兼容。",
        fix="把一侧显式转换为另一侧类型，或改用兼容类型。",
    ),
    "SEM_ARG_COUNT_MISMATCH": CodeInfo(
        title="调用提供的实参数量与被调用的形参数量不符。",
        fix="补齐/删减实参，或为缺省参数提供默认值。",
    ),
    "SEM_DUAL_ASSIGNABLE": CodeInfo(
        title="方法重写（override）签名与父类约束不兼容。",
        fix="保持重写方法的参数/返回类型与父类声明兼容。",
    ),
    "SEM_CAST_NO_CONVERTER": CodeInfo(
        title="目标类型没有提供从源类型的转换能力。",
        fix="为目标类型实现转换协议，或改用可转换的类型路径。",
    ),
    "SEM_CONTAINER_METHOD_HINT": CodeInfo(
        title="容器类型上访问了不存在或不适用的方法。",
        fix="检查容器实际类型，改用其支持的方法（如 list/dict/str 各自的方法集）。",
    ),
    "SEM_PROTOCOL_SIGNATURE": CodeInfo(
        title="提示协议方法的签名与协议约定不符。",
        fix="按协议约定的参数个数/返回类型修正签名。",
    ),
    "SEM_OVERLAY_UNUSED": CodeInfo(
        title="声明了覆层（impl overlay）但从未被 with overlay 作用域启用。",
        fix="为该覆层添加 with overlay(<类型>.<协议方法>): 作用域块启用，或删除未用的覆层声明。",
    ),
    "SEM_SUPER_OUTSIDE_METHOD": CodeInfo(
        title="super 只在类方法体内可用。",
        fix="把 super 调用移入类方法，或检查是否在错误的作用域使用。",
    ),
    "SEM_YIELD_OUTSIDE_FUNCTION": CodeInfo(
        title="yield / yield from 只能在函数体内使用。",
        fix="把 yield 移入函数（func）体；含 yield 的函数即惰性生成器。",
    ),
    "SEM_UNRESOLVED_TYPE": CodeInfo(
        title="类型注解中的类型名称无法解析。",
        fix="确认该类型已定义/导入，且名称拼写正确。",
    ),
    "SEM_DECLARATION_WITHOUT_INITIALIZER": CodeInfo(
        title="语句域裸类型声明（无初始值）——如 `int x`。",
        fix="补充初始值（`int x = 0`）。IBCI 语句域变量无 None 缺省初始化语义（fail-fast：未初始化的类型化变量无合法运行期语义，编译期拒绝）。类字段裸声明（`class P: int v`）= 构造器必填参数，为合法形态，不受此限。",
    ),
    # -- 知识注册表（check 纯度铁律，编译期） --
    "SEM_KNW_CHECK_LLM": CodeInfo(
        title="knowledge.store/amend 的验证谓词（check）体内含 LLM 调用——不纯度不可接受，登记门须为确定性验证。",
        fix="把 LLM 调用移出 check 函数体（check 只做确定性判定，如文本包含/格式/长度检查）；LLM 调用放在调用方的显式控制流中。",
    ),
    "SEM_KNW_CHECK_OPAQUE": CodeInfo(
        title="knowledge.store/amend 的验证谓词（check）为不透明值（变量/跨模块引用）——静态无法证明其确定性，fail-fast 拒绝。",
        fix="把 check 改为本模块内显式定义且不含 LLM 调用的函数引用（编译器可遍历其函数体证明纯度）。",
    ),
    # -- 函数参数绑定 --
    "SEM_DUPLICATE_KEYWORD": CodeInfo(
        title="调用中同一具名参数被重复提供。",
        fix="移除重复的具名实参。",
    ),
    "SEM_UNKNOWN_KEYWORD": CodeInfo(
        title="调用提供了被调函数不认识的具名实参。",
        fix="使用被调函数声明的参数名，或为函数增加该参数。",
    ),
    "SEM_MISSING_REQUIRED_ARG": CodeInfo(
        title="调用缺少必填的实参。",
        fix="提供全部必填实参，或为该参数提供默认值。",
    ),
    "SEM_DEFAULT_TYPE_MISMATCH": CodeInfo(
        title="参数默认值的类型与参数注解不一致。",
        fix="把默认值改为与参数类型一致的类型。",
    ),
    "SEM_TOO_MANY_POSITIONAL": CodeInfo(
        title="调用提供了过多的位置实参。",
        fix="删减位置实参；其余需求用具名实参或可变参数承载。",
    ),
    "SEM_MISSING_RETURN_ANNOTATION": CodeInfo(
        title="函数声明缺少返回类型注解。",
        fix="为函数补充 -> 返回类型（显式类型、auto 或 any）。",
    ),
    "SEM_MULTI_TYPE_LIST_REMOVED": CodeInfo(
        title="多类型列表声明语法已移除。",
        fix="改用单一元素类型 list[T]，异构内容用 tuple 或显式转换表达。",
    ),
    # -- 作用域 --
    "SEM_INVALID_SCOPE": CodeInfo(
        title="声明出现在不允许的作用域（如模块顶层 vs 函数内错位）。",
        fix="把声明移到合法作用域；检查变量/函数归属层级。",
    ),
    "SEM_NONLOCAL_NOT_FOUND": CodeInfo(
        title="nonlocal 引用的外层变量不存在。",
        fix="确认该变量在直接外层作用域已声明。",
    ),
    # -- 意图系统 --
    "SEM_INTENT_PLACEMENT": CodeInfo(
        title="意图注释放在了不允许的位置。",
        fix="把意图注释移到合法位置（语句/块的意图槽）。",
    ),
    "SEM_INTENT_STATIC_CALL": CodeInfo(
        title="意图上下文方法被静态（类级）调用。",
        fix="通过实例访问意图相关方法，而非类级静态调用。",
    ),
    # -- LLM 输出契约 --
    "SEM_BEHAVIOR_OUTPUT_NOT_PARSEABLE": CodeInfo(
        title="行为表达式声明了具体类型，但该类型没有 LLM 输出解析能力。",
        fix="为该类型实现 __from_prompt__ 解析协议，或改用可解析类型（int/str/list 等）。",
    ),
    # -- 隔离与快照 --
    "SEM_LLMEXCEPT_BODY_WRITE": CodeInfo(
        title="llmexcept 体内禁止写参与 LLM 调用的变量。",
        fix="在 llmexcept 体内只写非参与变量，避免污染重试快照。",
    ),
    "SEM_LLMEXCEPT_BINDING": CodeInfo(
        title="llmexcept 绑定形式不符合约定（缺失/多余绑定）。",
        fix="按 llmexcept 绑定语法补全或移除绑定。",
    ),
    "SEM_LLMEXCEPT_SCOPE_BINDING": CodeInfo(
        title="llmexcept 的作用域绑定写法不合法。",
        fix="检查 llmexcept 作用域绑定语句的写法与位置。",
    ),
    "SEM_LLMEXCEPT_MUTATING_CALL": CodeInfo(
        title="llmexcept 保护区域内调用了可能突变参与变量的函数。",
        fix="避免在保护区域内做副作用突变，或把调用移到 llmexcept 之外。",
    ),
    "SEM_LLMEXCEPT_FILE_WRITE": CodeInfo(
        title="llmexcept 保护区域内执行了文件写操作（快照隔离下不允许）。",
        fix="把文件写移到 llmexcept 保护区域之外。",
    ),
    # -- 用户类泛型 --
    "SEM_GENERIC_TYPE_NEEDS_ARGS": CodeInfo(
        title="泛型类未提供类型参数即作类型使用（如裸 Box）。",
        fix="特化使用：提供类型实参，如 Box[int]（或 Box[str]）。",
    ),
    "SEM_GENERIC_TYPE_ARG_COUNT": CodeInfo(
        title="泛型类类型实参数量与声明不符。",
        fix="按类声明补全/裁剪类型实参（class Box[T] → Box[int]）。",
    ),
    # -- 特殊 --
    "SEM_UNCATEGORIZED": CodeInfo(
        title="未归类语义错误（无专属码）。",
        fix="按报错消息的具体内容定位并修复。",
    ),
    "SEM_INTERNAL_SENTINEL": CodeInfo(
        title="内部哨兵值泄漏到了用户可见的错误面。",
        fix="这通常表示编译器内部 bug；请记录触发代码供维护者排查。",
    ),
    # ==================== 依赖 (DEP_) ====================
    "DEP_MODULE_NOT_FOUND": CodeInfo(
        title="导入的模块找不到。",
        fix="确认模块路径正确、模块文件存在且在项目根/插件搜索路径内。",
    ),
    "DEP_FILE_NOT_FOUND": CodeInfo(
        title="引用/入口文件不存在。",
        fix="确认文件路径拼写与存在性。",
    ),
    "DEP_INVALID_IMPORT_POSITION": CodeInfo(
        title="import 语句出现在文件非头部位置。",
        fix="把所有 import 移到文件开头（其它语句之前）。",
    ),
    "DEP_GRAPH_ERROR": CodeInfo(
        title="依赖图构建失败（模块依赖关系无法解析）。",
        fix="检查模块间依赖声明的合法性。",
    ),
    "DEP_FAILED_DEPENDENCY": CodeInfo(
        title="被依赖的模块编译失败，连带本模块报错。",
        fix="先修复被依赖模块的编译错误。",
    ),
    "DEP_SECURITY_ERROR": CodeInfo(
        title="导入被安全策略拒绝（越界/不可信路径）。",
        fix="调整导入路径或安全策略，使导入在允许范围内。",
    ),
    "DEP_CIRCULAR_IMPORT": CodeInfo(
        title="模块间存在循环导入。",
        fix="打破循环：把共享部分抽到独立模块，或改为延迟导入。",
    ),
    # ==================== 内部 (INT_) ====================
    "INT_INTERNAL_ERROR": CodeInfo(
        title="编译器内部错误（不应出现在正常输入下）。",
        fix="请记录触发代码与上下文，提交给维护者。",
    ),
    "ICE_TYPE_LEAK": CodeInfo(
        title="内部类型泄漏到用户可见面。",
        fix="编译器内部类型表示问题；请记录触发代码提交维护者。",
    ),
    # ==================== 运行时 (RUN_) ====================
    "RUN_GENERIC_ERROR": CodeInfo(
        title="未归类运行时错误。",
        fix="按报错消息的具体内容定位并修复。",
    ),
    "RUN_TYPE_MISMATCH": CodeInfo(
        title="运行时发现类型不匹配（编译期类型与运行值不符）。",
        fix="检查产生该值的路径，确保类型契约成立。",
    ),
    "RUN_UNDEFINED_VARIABLE": CodeInfo(
        title="运行时读取了未定义的变量。",
        fix="确保变量在使用前已赋值（含所有分支路径）。",
    ),
    "RUN_DIVISION_BY_ZERO": CodeInfo(
        title="除数为零。",
        fix="在除法前校验除数非零，或调整算法避免除零。",
    ),
    "RUN_ATTRIBUTE_ERROR": CodeInfo(
        title="对象上没有该属性/方法。",
        fix="确认对象类型，使用其真实存在的成员。",
    ),
    "RUN_INDEX_ERROR": CodeInfo(
        title="索引越界或键不存在。",
        fix="访问前校验索引范围/键存在性。",
    ),
    "RUN_CALL_ERROR": CodeInfo(
        title="函数调用失败（函数体执行抛出）。",
        fix="按报错上下文定位函数体内的异常根因。",
    ),
    "RUN_LIMIT_EXCEEDED": CodeInfo(
        title="执行超过资源/指令上限。",
        fix="检查是否存在死循环或超大数据；必要时调整执行上限配置。",
    ),
    "RUN_LLM_ERROR": CodeInfo(
        title="LLM 调用失败（网络/密钥/提供者错误）。",
        fix="检查 LLM 配置（endpoint/key/model）、网络连通性与额度。",
    ),
    "RUN_LLM_CALLABLE": CodeInfo(
        title="llm 可调用类契约违约（__llm_call__/__intent__/__retry__ 返回或签名不符、值不满足 LLMCallable 协议）。",
        fix="按 docs/syntax/08_llm_callable.md §8.1/§8.4 核对：__llm_call__ 返回装配 dict 且含必需 user_prompt；__intent__(self, dict) -> dict；__retry__(self) -> dict（max_retry≥1 / hint str）。",
    ),
    "RUN_PERMISSION_ERROR": CodeInfo(
        title="运行时操作被权限策略拒绝。",
        fix="调整权限策略或避开被禁止的操作。",
    ),
    "RUN_LLMEXCEPT_SNAPSHOT_VIOLATION": CodeInfo(
        title="运行时违反了 llmexcept 快照隔离约束。",
        fix="避免在快照隔离区域内执行被禁止的写入/副作用。",
    ),
    "RUN_BUDGET_EXCEEDED": CodeInfo(
        title="LLM 运行预算超限（tokens / 调用次数 / 墙钟，on_exceed=fail 时在 provider 调用前拦截）。",
        fix="在 api_config.json budget 节调整阈值（max_tokens / max_calls / max_wall_s）或 on_exceed=warn 改为仅告警。",
    ),
    "RUN_DETERMINISTIC_LLM_CALL": CodeInfo(
        title="确定性执行模式（run --deterministic）下尝试 LLM 调用——零 LLM 不变量在调用汇点结构性拦截。",
        fix="本 run 要求零 LLM（D1：判定/验证路径确定性）：移除/改写触发 LLM 的 @~...~ 调用点，或去掉 --deterministic 以允许 LLM。与 RUN_BUDGET_EXCEEDED 分面（零容忍不变量 vs 用户配置阈值）。",
    ),
    "RUN_JSON_PARSE_ERROR": CodeInfo(
        title="JSON 解析/序列化失败（malformed JSON / 不可序列化值）。",
        fix="检查 JSON 字符串格式合法性（引号、逗号、括号配对）；改用 `json.parse_or_none(s)` 以显式宽松形态处理（失败返回 None，无副作用）。",
    ),
    # ==================== 内核诊断 (KDIAG_) ====================
    "KDIAG_PROTOCOL_TO_PROMPT_FALLBACK": CodeInfo(
        title="协议回退：to_prompt 能力缺失，回退默认提示词构造。",
        fix="如需定制提示，为类型实现协议方法；回退不阻断执行。",
    ),
    "KDIAG_PROTOCOL_FROM_PROMPT_FALLBACK": CodeInfo(
        title="协议回退：from_prompt 解析能力缺失，回退默认解析。",
        fix="如需定制解析，为类型实现协议方法；回退通常保持兼容行为。",
    ),
    "KDIAG_PROTOCOL_PAYLOAD_PROMPT_FALLBACK": CodeInfo(
        title="协议回退：payload 提示构造能力缺失，使用默认 payload。",
        fix="需定制时实现协议方法；否则回退即可。",
    ),
    "KDIAG_PROTOCOL_VALIDATE_FALLBACK": CodeInfo(
        title="协议回退：输出校验能力缺失，跳过自定义校验。",
        fix="需强校验时实现协议方法；回退是 fail-open 行为。",
    ),
    "KDIAG_PROTOCOL_SNAPSHOT_FALLBACK": CodeInfo(
        title="协议回退：快照能力缺失，使用默认快照机制。",
        fix="需定制快照语义时实现协议方法。",
    ),
    "KDIAG_PROTOCOL_RESTORE_FALLBACK": CodeInfo(
        title="协议回退：恢复能力缺失，使用默认恢复机制。",
        fix="需定制恢复语义时实现协议方法。",
    ),
    "KDIAG_POLICY_MODULE_OVERRIDE": CodeInfo(
        title="策略：用户插件覆盖了 kernel-native 模块。",
        fix="若覆盖为有意为之可忽略；否则移除插件避免覆盖。",
    ),
    "KDIAG_RUNTIME_COLLECT_SKIP": CodeInfo(
        title="运行时降级：collect 目标被跳过。",
        fix="检查 collect 目标的可收集性；降级为尽力而为。",
    ),
    "KDIAG_RUNTIME_STAGE_SKIP": CodeInfo(
        title="运行时降级：某执行阶段被跳过。",
        fix="按阶段上下文判断是否需补全该阶段能力。",
    ),
    "KDIAG_RUNTIME_ENV_LIMIT": CodeInfo(
        title="运行时环境限制异常（栈溢出/内存/系统错误）根因保留。",
        fix="按真实根因处理（如提升宿主递归上限、优化内存使用）。",
    ),
    "KDIAG_RUNTIME_PRE_EVAL_FALLBACK": CodeInfo(
        title="运行时降级：类字段默认值预评估失败，留待实例化时求值。",
        fix="属尽力而为优化的正常回退（实例化路径完整重试 + fail-fast）；仅当实例化时报错才需排查默认值表达式。",
    ),
    "KDIAG_RUNTIME_SPECIALIZATION_FALLBACK": CodeInfo(
        title="运行时降级：跨引擎 round-trip 特化类重建失败（注册表封印），值回落基类。",
        fix="KNOWN_LIMITS §十 契约：特化跨引擎身份保真须目标引擎已编译该类；回退后值字段与基类方法可用，仅特化身份丢失。如需保真须目标引擎先编译该类。",
    ),
    # ==================== 宿主隔离 (HOST_) ====================
    "HOST_ISOLATE_LLM_INHERIT_FAILED": CodeInfo(
        title="ihost 隔离子环境 LLM 配置继承应用失败（spawn 时点父配置快照未能应用到子 provider）。",
        fix="不阻断子执行（子照常运行）；子环境 LLM 调用将按其自身配置状态得清晰错误。排查：子项目 api_config/插件发现面或快照内容异常。",
    ),
    # ==================== 词嵌入 (EMB_) ====================
    "EMB_CONFIG_MISSING": CodeInfo(
        title="embedding 配置缺失（base_url/api_key/model 未提供且未进入 mock 模式）。",
        fix="调用 set_config(base_url, api_key, model) 提供端点凭据，或 set_mock_mode() 进入 MOCK:VEC 确定性 mock 模式。",
    ),
    "EMB_SERVICE_ERROR": CodeInfo(
        title="embedding 服务调用失败（网络/客户端初始化/供应商错误）。",
        fix="检查 embedding 端点连通性、密钥有效性与供应商侧错误信息。",
    ),
    "EMB_BATCH_ORDER": CodeInfo(
        title="embedding 批量保序契约违约（响应数量与请求文本数不一致、mock SEQ 缓冲余量不足）。",
        fix="供应商响应须与请求文本按序一一对应；mock SEQ 序列长度须覆盖全部消费批次的请求数。",
    ),
    "EMB_DIMENSION_MISMATCH": CodeInfo(
        title="embedding 维度失配（批内向量维度不一致、查询与语料维度不同、mock SEQ 向量维度与目标不符）。",
        fix="同一批/同一检索面的向量须同维度；dimensions 请求位与供应商实际输出保持一致。",
    ),
    "EMB_ZERO_NORM": CodeInfo(
        title="零范数向量（余弦相似度未定义；mock 派生退化）。",
        fix="避免全零向量输入检索/相似度计算；mock 派生零范数为契约违约（实际不可达）。",
    ),
    "EMB_INVALID_INPUT": CodeInfo(
        title="embedding/检索非法输入（空批、空语料、k 非正整数、向量含非有限值 NaN/Inf、mock 指令非法）。",
        fix="检查输入面：texts 非空、k 为正整数、向量元素为有限浮点数、mock 指令载荷合法。",
    ),
    # ==================== 知识注册表 (KNW_) ====================
    "KNW_CHECK_REJECTED": CodeInfo(
        title="知识登记/更正未过验证门（check(value) 为假），或跨 save/load 恢复后验证谓词引用丢失。",
        fix="先让值通过确定性验证再 store；amend 同样须过原验证门；跨快照恢复后条目须重新 store 登记（谓词引用不入值快照）。",
    ),
    "KNW_KEY_EXISTS": CodeInfo(
        title="knowledge.store 键已登记（登记与更正机器强制区分），或键非法（非空 str）。",
        fix="已登记条目的更新走 amend（附 reason 审计）；检查键为非空字符串。",
    ),
    "KNW_REASON_EMPTY": CodeInfo(
        title="knowledge.amend / amend_fact / retract 理由（reason）为空，或键/fact_id 未登记。",
        fix="更正/墓碑必须附非空理由（审计链完整性要求）；操作仅适用于已登记条目/已登记事实。",
    ),
    "KNW_VOCAB_UNREGISTERED": CodeInfo(
        title="knowledge.add_fact 引用未注册词表项（世界/关系类型/主语词/对象词）——KB 治理门（allowlist 机器强制）。",
        fix="先经 register_world / register_relation / register_word 注册对应词表项，再 add_fact。",
    ),
    "KNW_VOCAB_EXISTS": CodeInfo(
        title="knowledge.register_word / register_relation / register_world 重复注册（词表单一权威源）。",
        fix="词表项已注册则查询其记录（word/relation/world）；更正归调用方治理流程，KB 值面只有登记。",
    ),
    "KNW_VOCAB_MALFORMED": CodeInfo(
        title="knowledge 词表/事实方法参数形态非法（非 str / 非 bool / 非 list / 非 dict / 空串）。",
        fix="按方法签名提供正确形态：词表名非空 str、is_set/transitive/multi_valued 为 bool、members 为 list、entries 为 dict、size_rank 为 int。",
    ),
    "KNW_FACT_DUPLICATE": CodeInfo(
        title="knowledge.add_fact 同 (world,s,r,o) 已有 active 事实——去重机器强制。",
        fix="事实已存在则查询其记录（get_fact/lookup_pair）；更正在事实面走 amend_fact（附 reason），废止走 retract（附 reason）。",
    ),
    "KNW_FACT_NOT_FOUND": CodeInfo(
        title="knowledge 事实面操作引用未知 fact_id（get_fact/source/history_fact/expand/compare/retract/amend_fact）。",
        fix="fact_id 须为 add_fact 返回值（或经 facts 枚举确认在日志中）；未知 id 经 get_fact 返回 null 预检。",
    ),
    "KNW_FACT_RETRACTED": CodeInfo(
        title="对已 retract（墓碑）事实再 retract / amend_fact——事实已废止。",
        fix="墓碑事实只读（get_fact/facts/history_fact 仍可查全史）；需恢复语义 = 登记新事实（append-only 纪律：不复活的版本是新事实）。",
    ),
    "KNW_KB_ARTIFACT_MALFORMED": CodeInfo(
        title="world_model.load_kb / save_kb 的 KB artifact 结构非法（非合法 JSON / 缺封套字段 / facts-vocab 记录形态错 / seq 非负 int 违约）。",
        fix="经 world_model.save_kb 重新导出合规 artifact（封套 {schema_version, content_hash, facts, vocab, seq}；facts 记录含 id/world/s/r/o/source/status/events；vocab 含 words/relations/worlds 三面）。",
    ),
    "KNW_KB_SCHEMA_VERSION": CodeInfo(
        title="world_model.load_kb 遇到未知 schema_version（本版本仅支持 1；无自动迁移）。",
        fix="以支持该版本的引擎版本加载，或由导出方按当前 schema_version 重新导出 artifact。",
    ),
    "KNW_KB_HASH_MISMATCH": CodeInfo(
        title="world_model.load_kb 的 content_hash 验证失败——artifact 数据损坏或被篡改（内容寻址完整性门）。",
        fix="重新经 world_model.save_kb 导出（取回 content_hash 作钉扎基准）；跨传输场景以 hash 比对检出损坏后重传。",
    ),
    # ==================== 窄模型工件 (NAR_) ====================
    "NAR_ENTITY_UNREGISTERED": CodeInfo(
        title="narrow_model.score/topk 的 s/o 引用未注册实体（冻结工件词表固定，无静默默认）。",
        fix="仅用工件 entities() 已注册实体作 s/o；候选空间见 model.entities()。",
    ),
    "NAR_RELATION_UNREGISTERED": CodeInfo(
        title="narrow_model.score/topk 的 r 引用未注册关系（冻结工件词表固定，无静默默认）。",
        fix="仅用工件 relations() 已注册关系作 r；关系空间见 model.relations()。",
    ),
    "NAR_TOPK_INVALID": CodeInfo(
        title="narrow_model.topk 的 k 非正整数（k ≥ 1 整数；k 超候选数 = 返回全部候选，非错误）。",
        fix="传正整数 k；k 超候选数时返回全部候选（截断语义，非违约）。",
    ),
    # ==================== 层级记忆基底 (MEM_) ====================
    "MEM_KEY_EXISTS": CodeInfo(
        title="memory.encode 键已存在或键非法（非空 str）。",
        fix="重复键须先 prune 或 promote/demote 到其它层再 encode；键须为非空字符串。",
    ),
    "MEM_KEY_NOT_FOUND": CodeInfo(
        title="memory 操作（promote/content_hash 等）引用未登记键。",
        fix="确认键已 encode 登记；跨层操作前用 tier() 确认条目位置。",
    ),
    "MEM_TIER_FULL": CodeInfo(
        title="memory 层容量已满，拒绝写入。",
        fix="先 prune（遗忘）或 demote（降级）腾出空间；或 set_capacity 扩大容量。",
    ),
    "MEM_TIER_UNKNOWN": CodeInfo(
        title="memory 操作引用了非法层名（非 working_set/session/knowledge/long_term）。",
        fix="层名须为固定四值之一：working_set / session / knowledge / long_term。",
    ),
    # ==================== 配置 (CFG_) ====================
    "CFG_CONFIG_NOT_FOUND": CodeInfo(
        title="配置加载指定的配置文件不存在（ai.load_config / ai.load_project_config）。",
        fix="确认路径正确（相对路径锚定 project_root），或创建 api_config.json；load_project_config 对缺失文件为 no-op。",
    ),
    "CFG_CONFIG_INVALID_JSON": CodeInfo(
        title="配置文件不是合法的 JSON。",
        fix="检查 JSON 语法（引号、逗号、括号配对），可用 JSON 校验工具排查。",
    ),
    "CFG_CONFIG_NOT_OBJECT": CodeInfo(
        title="配置文件顶层不是 JSON 对象（dict）。",
        fix="配置必须是对象，如 {\"default_model\": {...}}。",
    ),
    "CFG_CONFIG_MISSING_DEFAULT": CodeInfo(
        title="配置缺少 default_model 字段。",
        fix="添加 default_model 字段（对象形态或命名模型引用字符串）。",
    ),
    "CFG_CONFIG_MODEL_NOT_OBJECT": CodeInfo(
        title="模型条目不是 JSON 对象（dict）。",
        fix="每个模型条目必须是对象，含 base_url/api_key/model 字段。",
    ),
    "CFG_CONFIG_MISSING_FIELD": CodeInfo(
        title="模型条目缺少必要字段（base_url/api_key/model）。",
        fix="补全缺失字段；三个字段均为必填。",
    ),
    "CFG_CONFIG_INVALID_FIELD_TYPE": CodeInfo(
        title="配置字段类型错误（如 base_url 不是字符串、timeout 不是数字）。",
        fix="按字段类型要求修正：base_url/api_key/model 为 str，timeout 为 number，reasoning 为 bool。",
    ),
    "CFG_CONFIG_UNKNOWN_MODEL_REF": CodeInfo(
        title="default_model 引用的命名模型在 named_models 中不存在。",
        fix="确认 default_model 字符串与 named_models 的键名一致（区分大小写）。",
    ),
    "CFG_CONFIG_UNKNOWN_PROVIDER": CodeInfo(
        title="模型引用的 provider 在 providers 中不存在。",
        fix="确认 model 的 provider 字段与 providers 的键名一致（区分大小写）。",
    ),
    "CFG_CONFIG_ENV_VAR_MISSING": CodeInfo(
        title="配置中 {env:VAR} 引用的环境变量未设置。",
        fix="设置对应环境变量，或移除该 {env:VAR} 引用改为直接写值。",
    ),
    "CFG_CONFIG_UNKNOWN_FIELD": CodeInfo(
        title="api_config model 条目含未知字段（拼写错误/废弃字段）。",
        fix="按报错消息列出的允许字段修正；未知字段不再静默丢弃（配置面可审计性纪律）。",
    ),
    "CFG_CONFIG_INVALID_BUDGET": CodeInfo(
        title="api_config.json budget 节形态错误（阈值非正数 / on_exceed 非 warn|fail）。",
        fix="budget 节为可选：{max_tokens, max_calls, max_wall_s 均为正数; on_exceed 为 \"warn\"(默认) 或 \"fail\"}；按报错消息修正或移除该节。",
    ),
    "RUN_LLM_EMPTY_CONTENT": CodeInfo(
        title="LLM 返回空内容（仅有思考内容、无最终答案）。",
        fix="思考抑制对模型无效或模型行为形态异常——显式声明 reasoning 模式（api_config model 条目 reasoning: true）或使用非思考模型端点；该错误不再静默以思考内容替代答案（可审计性纪律）。",
    ),
    "LLM_ASSEMBLY_UNKNOWN_KEY": CodeInfo(
        title="llm 可调用类装配 dict 含契约外字段（疑似拼写错误/废弃字段）。",
        fix="按装配契约修正字段名（user_prompt[必需] / output_hint / expected_type / model / prompt_slots）；未知字段不再静默忽略（可见性纪律——警告级，不阻断调用）。",
    ),
}


def lookup(code: str) -> CodeInfo | None:
    """按诊断码查询用户友好条目；未登记返回 None（调用方决定回退展示）。"""
    return CODE_CATALOG.get(code)
