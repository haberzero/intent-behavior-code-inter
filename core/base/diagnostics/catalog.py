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
    "RUN_PERMISSION_ERROR": CodeInfo(
        title="运行时操作被权限策略拒绝。",
        fix="调整权限策略或避开被禁止的操作。",
    ),
    "RUN_LLMEXCEPT_SNAPSHOT_VIOLATION": CodeInfo(
        title="运行时违反了 llmexcept 快照隔离约束。",
        fix="避免在快照隔离区域内执行被禁止的写入/副作用。",
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
}


def lookup(code: str) -> CodeInfo | None:
    """按诊断码查询用户友好条目；未登记返回 None（调用方决定回退展示）。"""
    return CODE_CATALOG.get(code)
