# Comment Cleanup Inventory — core/base & core/kernel

- **Scope**: `core/base/**/*.py` and `core/kernel/**/*.py` (path/, spec/, axioms/, symbols, config, interfaces, host_interface, issue, registry).
- **Mode**: READ-ONLY analysis. No code or comment was modified.
- **Method**: Grep for ADR-\d, PT-[A-Z]/PT-4., NEXT_STEPS/PENDING_TASKS/tasks_docs/, dates/锚点/legacy/历史, §, docs/... paths, SEM/DEP/INV/SC/LT/CF/OM codes, codenames (G/D/H/P/C/B/A/M/R + digit, NS-x, 方案AB, CF-1, P0), .md / IBCI_SPEC / FROM_ZERO doc refs, smell-hint keywords (占位/simplified/disabled/workaround/TODO). 3-8 lines of context read around each match to classify.
- **Note**: "锚点" (path anchor) and "Layer N / Phase N" (algorithm stages, e.g. `_inference.py` Layers 1-5) are functional and NOT flagged. Error-code constant *assignments* (e.g. `SEM_UNDEFINED_SYMBOL = "SEM_001"`) are CODE, not comments, and are excluded; only comment/docstring lines are inventoried.

## Category legend
- **TC** task-control doc refs (NEXT_STEPS/PENDING_TASKS/tasks_docs/) -> delete pointer, keep function
- **ADR** ADR-NNN codes -> delete "Per ADR-x："/"（ADR-x）" prefix/suffix, keep design explanation
- **PT** PT-xxx / PT-ARCH-xxx task IDs -> delete "PT-xxx：" prefix, keep function
- **DATE** dates / "历史" / "legacy" / "旧 bug" / "修复见PR" / "合并自" / "Source:" -> rewrite present-tense or delete historical line
- **DOC** § section pointers (§6.1/§9.2/§E) -> delete section number, keep function
- **CODE** task/design codenames (G1-G6/D1-D6/H1-H3/NS-x/P0-P7/C2-C11/B1/B2/A3/A5/R1/P4b/方案A-B/M1-M6/CF-1) -> delete codename label, keep function
- **DOCREF** tech-doc path pointers (docs/.../IBCI_SPEC/IBCI_TYPE_SYSTEM_..._ARCHITECTURE.md) -> delete pointer line/clause
- **ERR** SEM_xxx/DEP_xxx/PAR_xxx/INV-x/SC-x/LT-x/CF-x/OM-x -> KEEP (flag for later normalization)

Composite labels (e.g. `ADR+CODE+DATE`) indicate a single comment carrying multiple issues; all listed cleanings apply.

## Inventory

| file:line | CATEGORY | current_snippet | proposed_cleaning |
|---|---|---|---|
| core/base/diagnostics/codes.py:1 | ERR | `# Lexical Errors (LEX_xxx)` | KEEP+normalize (functional error-code section header) |
| core/base/diagnostics/codes.py:9 | ERR | `# Syntax Errors (PAR_xxx)` | KEEP+normalize |
| core/base/diagnostics/codes.py:17 | ERR | `# Semantic Errors (SEM_xxx)` | KEEP+normalize |
| core/base/diagnostics/codes.py:24 | ERR | `# Dependency Errors (DEP_xxx)` | KEEP+normalize |
| core/base/diagnostics/codes.py:32 | ERR | `# Internal Errors (INT_xxx)` | KEEP+normalize |
| core/base/diagnostics/codes.py:35 | ERR | `# Runtime Errors (RUN_xxx)` | KEEP+normalize |
| core/base/diagnostics/codes.py:47 | ERR | `# Import / module resolution warnings (SEM_009)` | KEEP+normalize |
| core/base/diagnostics/codes.py:50 | ERR | `# llmexcept / snapshot isolation (SEM_05x)` | KEEP+normalize |
| core/base/enums.py:39 | ADR+DOC | `IMPORT_GATED = auto()  # Requires an explicit ``import`` (ADR-020 §A)` | delete "(ADR-020 §A)" |
| core/base/enums.py:44 | ADR | `"""Type-level backing model for IbSpec (ADR-016).` | delete "(ADR-016)" |
| core/base/enums.py:46 | CODE | `G1.5 only lands the field; dispatch logic is intentionally disabled until the G3 disk-backed storage stage.` | delete codename labels "G1.5"/"G3"; NOTE comment is stale (dispatch IS wired in runtime) — see smell report |
| core/base/enums.py:51 | PT | `DISK_BACKED = auto()  # FileHandle / media (gated by PT-ARCH-17/18)` | delete "gated by PT-ARCH-17/18" |
| core/base/path/__init__.py:4 | ADR | `Per ADR-017：纯值对象与纯词法操作，无 IBCI 语义、无 FS 访问。` | delete "Per ADR-017：" |
| core/base/path/relpath.py:4 | ADR+CODE+DATE | `Per ADR-015 D6：``safe_relpath`` 历史上位于 ``core/base/path_utils.py``（为绕开…workaround 文件）` | delete "Per ADR-015 D6：" prefix; delete/rewrite historical "历史上位于…workaround 文件" sentence |
| core/kernel/ast.py:469 | CODE | `# D2：表达式侧返回类型标注节点（IbName/IbSubscript 等）。` | delete "D2：" |
| core/kernel/ast.py:493 | CODE | `D3: supports ``fn[(param_types) -> return_type]`` syntax for HOF parameter…` | delete "D3: " |
| core/kernel/axioms/primitives/__init__.py:8 | DATE | `* Single inheritance from ``BaseAxiom``. The legacy multi-inheritance with…` | delete "legacy" |
| core/kernel/axioms/primitives/file_handle.py:33 | PT | `# PT-ARCH-24: path 是 field（纯内省，无 I/O）。` | delete "PT-ARCH-24: " |
| core/kernel/axioms/primitives/file_handle.py:37 | PT | `# PT-ARCH-25: file_handle 实例只读，无 write() 方法。` | delete "PT-ARCH-25: " |
| core/kernel/axioms/primitives/media.py:6 | ADR | `Per ADR-014/016: media 类型现在是磁盘型 ``file_handle`` 子类。` | delete "Per ADR-014/016: "; rewrite "现在是"->"是" |
| core/kernel/axioms/primitives/media.py:29 | ADR | `# media 类型是 file_handle 的磁盘型子类（ADR-014）。` | delete "（ADR-014）" |
| core/kernel/axioms/primitives/media.py:34 | PT | `# PT-ARCH-24: data 触发 I/O（base64 物化），保持 method；` | delete "PT-ARCH-24: " |
| core/kernel/axioms/primitives/media.py:64 | PT | `# PT-ARCH-25: 构造入口：audio.from_file(path)。` | delete "PT-ARCH-25: " |
| core/kernel/axioms/primitives/media.py:78 | PT | `# PT-ARCH-24: width/height 当前占位，未来可能读取图像头，保持 method。` | delete "PT-ARCH-24: "; NOTE placeholder logic — see smell report |
| core/kernel/axioms/primitives/media.py:81 | PT | `# PT-ARCH-25: 构造入口：image.from_file(path)。` | delete "PT-ARCH-25: " |
| core/kernel/axioms/primitives/media.py:95 | PT | `# PT-ARCH-25: 构造入口：video.from_file(path)。` | delete "PT-ARCH-25: " |
| core/kernel/axioms/primitives/sentinels.py:166 | TC+DOC | `- 用户自定义 UncertainResult；零参数 is_uncertain()；详见 PENDING_TASKS §十四。` | delete "详见 PENDING_TASKS §十四" pointer |
| core/kernel/axioms/primitives/sequences.py:77 | DATE+CODE | `# 历史过渡分支（`str + llm_uncertain` -> "str"）已收紧（NS-4）。` | delete "历史过渡分支" framing + "NS-4" codename; rewrite present tense |
| core/kernel/axioms/primitives/sequences.py:78 | ERR | `# 现在静态出现 `llm_uncertain` 操作数时按 SEM_003 处理，` | KEEP+normalize |
| core/kernel/config.py:2 | ADR+DOC | `IBCI 项目配置（ibci.json）加载 -- ADR-019 §6。` | delete "ADR-019 §6" |
| core/kernel/config.py:24 | ADR+DOC | `"""``ibci.json`` 项目配置加载器（ADR-019 §6）。"""` | delete "（ADR-019 §6）" |
| core/kernel/host_interface.py:43 | ADR+CODE | `self._kernel_native_names: Set[str] = set()  # ADR-020 G2：kernel-native 逻辑名集合` | delete "ADR-020 G2：" |
| core/kernel/host_interface.py:59 | ADR+CODE | `ADR-020 G2：若 name 已被标记为 kernel-native…` | delete "ADR-020 G2：" |
| core/kernel/interfaces.py:14 | CODE+DATE | `…此 Protocol 不包含 visit() 方法（已于 P2-P7 双轨消灭后删除）。` | delete "P2-P7" codename; rewrite "双轨消灭后删除"->"已删除" |
| core/kernel/path/__init__.py:4 | ADR | `Per ADR-017：锚点模型、沙箱、模块名映射、快照布局、FS 感知规范化。` | delete "Per ADR-017：" (keep functional 锚点) |
| core/kernel/path/__init__.py:6 | DATE | `消除历史上的 compiler->runtime 违规。` | delete "历史上的" (present tense) |
| core/kernel/path/context.py:4 | ADR+CODE+DATE | `Per ADR-015 D5：历史上 5 个独立 ``root_dir`` 字段并存…` | delete "Per ADR-015 D5：" + historical sentence |
| core/kernel/path/context.py:9 | DOC | `- ``entry_dir``：入口文件所在目录--**数据路径解析的锚**（§6.1 契约）。` | delete "§6.1 " (keep functional 锚) |
| core/kernel/path/context.py:66 | ADR | `派生子隔离执行上下文的路径锚点（纯路径策略，per ADR-017）。` | delete "（纯路径策略，per ADR-017）" |
| core/kernel/path/context.py:69 | ADR+DOC | `隔离策略校验（ADR-019 §5：子 entry 必须在父 project_root 内）在调用方` | delete "ADR-019 §5："; NOTE deferred validation — see smell report |
| core/kernel/path/context.py:74 | DATE | `历史：engine.request_isolated_run/request_spawn_isolated 内联计算…` | delete historical line |
| core/kernel/path/modulename.py:4 | ADR+CODE+DATE | `Per ADR-015 D4：历史上模块名与相对路径的互转靠散在两文件的字符串 ``replace``…` | delete "Per ADR-015 D4：" + historical sentence |
| core/kernel/path/resolver.py:4 | ADR+CODE+DOCREF+DOC | `Per ADR-015 D1：本解析器采用 **entry_dir 单锚点语义**，与 IBCI_SPEC §6.1 契约一致：` | delete "Per ADR-015 D1："、"IBCI_SPEC"、"§6.1" |
| core/kernel/path/resolver.py:11 | DATE+ADR | `历史\n----\n原实现采用 3 层语义…（ADR-015）将其重写为…` | delete entire historical "历史" block (lines 11-15) |
| core/kernel/path/resolver.py:36 | DOC | `--所有相对路径统一锚定 entry_dir（§6.1 契约）。` | delete "§6.1 " |
| core/kernel/path/resolver.py:58 | DOC | `统一路径解析入口（§6.1 契约的唯一实现）。` | delete "§6.1 " |
| core/kernel/path/snapshot.py:4 | ADR | `Per ADR-017：集中化"save_state 的资产外化到哪个目录、如何命名"的布局决策，` | delete "Per ADR-017：" |
| core/kernel/path/snapshot.py:5 | DATE | `历史上内联在 host/service.py（`save_path + ".assets"` 字符串拼接）。` | delete historical line |
| core/kernel/path/snapshot.py:16 | DATE | `历史上 host/service.save_state 内联 `abs_path + ".assets"` + …` | delete/rewrite historical line |
| core/kernel/path/validator.py:6 | ADR | `Per ADR-017：``canonicalize_for_security`` 是全仓**唯一**的 ``os.path.realpath`` 调用点…` | delete "Per ADR-017：" |
| core/kernel/path/validator.py:8 | DATE | `scheduler/resolver/permissions 三处历史各自调 realpath，现统一委托本方法。` | rewrite: "scheduler/resolver/permissions 统一委托本方法。" |
| core/kernel/path/validator.py:29 | CODE+DATE | `平台感知大小写（R1 修复）：大小写不敏感 FS（win32 等）需用 ``os.path.normcase``…` | delete "R1 修复"; rewrite "平台感知大小写：" |
| core/kernel/path/validator.py:183 | ADR | `**全仓唯一的 ``os.path.realpath`` 调用点**（per ADR-017）。` | delete "（per ADR-017）" |
| core/kernel/spec/base.py:186 | DATE | `…there are no legacy flat-string accessors.` | delete "legacy" |
| core/kernel/spec/registry/_assignability.py:98 | ERR | `call-site inference: ``int r = f()`` compiles without SEM_003.` | KEEP+normalize |
| core/kernel/spec/registry/_assignability.py:122 | CODE | `# G1: early-cache hit - 避免为已注册的特化类型分配临时 spec。` | delete "G1: " |
| core/kernel/spec/registry/_capabilities.py:26 | DATE | `# legacy per-capability Protocol classes into a single TypeAxiom` | delete "legacy" |
| core/kernel/spec/registry/_capabilities.py:77 | ERR | `Used by TypeCheckingPass.visit_IbCastExpr for compile-time SEM_091 warnings.` | KEEP+normalize |
| core/kernel/spec/registry/_inference.py:226 | CODE | `# P0-2: Check if user-defined class has operator method in its members` | delete "P0-2: " |
| core/kernel/spec/registry/_members.py:37 | CODE | `# G2/G3: For specialized generic containers, override the return type…` (block 37-49) | delete "G2/G3:"/"(was "any", G3)"/"G3:" labels; keep functional description; NOTE read-with-side-effect — see smell report |
| core/kernel/spec/registry/_members.py:56 | CODE | `# use element_type="any" intentionally - skip G3 specialization for them.` | delete "G3" |
| core/kernel/spec/registry/_members.py:67 | CODE | `# G3: dict[K,V].get(key) -> V  (same as pop)` | delete "G3: " |
| core/kernel/spec/registry/_members.py:71 | CODE | `# G3: dict[K,V].values() -> list[V]` | delete "G3: " |
| core/kernel/spec/registry/_members.py:83 | CODE | `# G3: dict[K,V].keys() -> list[K]` | delete "G3: " |
| core/kernel/spec/registry/_members.py:93 | CODE | `# G2: specialize write-method parameter types for list[T].` | delete "G2: " |
| core/kernel/spec/specs.py:89 | ADR | `# Per ADR-012: 作为普通类名注册（非关键字）。` | delete "Per ADR-012: " |
| core/kernel/spec/specs.py:90 | ADR | `# Per ADR-014/016: 继承 file_handle，使用磁盘型存储模型。` | delete "Per ADR-014/016: " |
| core/kernel/spec/specs.py:93 | PT | `# PT-ARCH-25: audio/image/video 与 file_handle 同为 import-gated，需 import file。` | delete "PT-ARCH-25: " |
| core/kernel/spec/specs.py:112 | ADR | `# Per ADR-020: file_handle 为 kernel-native 类型，import-gated；Per ADR-016: 磁盘型存储模型。` | delete "Per ADR-020: "/"Per ADR-016: " |
| core/kernel/spec/type_ref.py:9 | DOCREF+DOC | `设计原则（来自 IBCI_TYPE_SYSTEM_FROM_ZERO_ARCHITECTURE.md §1.1）：` | delete doc path pointer + "§1.1" |

## Row count by category

Total inventoried comment locations: **70**

Category occurrences (composite rows counted in each constituent category, so the sum exceeds 70):

| CATEGORY | occurrences |
|---|---|
| ADR | 23 |
| CODE | 20 |
| ERR | 11 |
| DATE | 15 |
| DOC | 10 |
| PT | 9 |
| DOCREF | 2 |
| TC | 1 |

Files with the densest comment debt: `core/kernel/path/*` (resolver/context/modulename/snapshot/validator — historical "ADR-015/017 统一化" framing), `core/kernel/spec/registry/_members.py` (G2/G3 codename labels), `core/kernel/axioms/primitives/media.py` & `file_handle.py` (PT-ARCH-24/25 labels), `core/base/diagnostics/codes.py` (ERR section headers — all KEEP).
