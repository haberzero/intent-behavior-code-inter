# Comment Inventory: Runtime Engine Area (Inv 2)

> **Scope**: `core/engine.py` (actual location; task said `core/runtime/engine.py` but file
> resides at `core/engine.py` — the `IBCIEngine` class), `core/runtime/host/`,
> `core/runtime/module_system/`, `core/runtime/path/`, `core/runtime/rt_scheduler.py`,
> `core/runtime/bootstrap/`, `core/runtime/interfaces.py`, `core/runtime/shared/`.
>
> **Path note**: `core/runtime/engine.py` does NOT exist. The Engine class
> (`IBCIEngine`) lives in `core/engine.py:63`. All engine findings reference `core/engine.py`.
>
> **READ-ONLY inventory**. No code modified. Categories: TC / ADR / PT / DATE / DOC / CODE / DOCREF / ERR.
> ERR = KEEP+normalize. "锚点"(path anchor) and "Layer N/Phase N/STAGE N"(algorithm stages) are
> functional — NOT flagged.

## Summary by Primary Category

| Category | Count |
|----------|-------|
| TC       | 2     |
| ADR      | 56    |
| PT       | 4     |
| DATE     | 13    |
| DOC      | 1     |
| CODE     | 15    |
| DOCREF   | 0     |
| ERR      | 2     |
| **Total**| **93**|

## Inventory

### core/engine.py

| file:line | CAT | current_snippet | proposed_cleaning |
|-----------|-----|-----------------|-------------------|
| core/engine.py:18 | TC | `PENDING_TASKS_VM.md Step 11` — "多 Interpreter 并发（Layer 2，PENDING_TASKS_VM.md Step 11）由 DynamicHost 负责调度" | Delete "PENDING_TASKS_VM.md Step 11" pointer; keep "多 Interpreter 并发由 DynamicHost（HostService）负责调度，而非 Engine". Layer 2 is functional (KEEP). |
| core/engine.py:71 | ADR | `Per ADR-019 §2` — "引擎级默认--未提供时 project_root 在 run()/compile() 时确立为 entry_file 所在目录" + `（D2）` on L73 | Delete "Per ADR-019 §2：" and "（D2）"; keep design explanation about default project_root derivation. Secondary: DOC §2, CODE D2. |
| core/engine.py:74 | ADR | `ADR-019 §3` — "plugin 发现优先级见 ADR-019 §3" | Delete "ADR-019 §3"; keep "plugin 发现优先级见 _resolve_plugin_search_paths". Secondary: DOC §3. |
| core/engine.py:77 | ADR | `ADR-019 多阶段启动` — "__init__ 仅做 root-independent 设置；root-dependent 设置延迟到 _ensure_root_initialized" | Delete "ADR-019" label; keep "多阶段启动：__init__ 仅做 root-independent 设置…". |
| core/engine.py:89 | ADR | `ADR-019 §2 CWD` — "单独保存（无上界校验）；子脚本可获取。使用待权限系统" | Delete "ADR-019 §2"; keep "CWD：单独保存（无上界校验）…". Secondary: DOC §2. |
| core/engine.py:108 | ADR | `ADR-019 §1` — "内核原生模块目录：恒在，单独存储，不配置不隔离" | Delete "ADR-019 §1"; keep "内核原生模块目录：恒在，单独存储…". Secondary: DOC §1. |
| core/engine.py:115 | ADR | `ADR-020 G2` — "kernel-native 模块元数据对编译器可见" | Delete "ADR-020 G2"; keep design explanation. Secondary: CODE G2. |
| core/engine.py:117 | ADR | `ADR-020 G2` — "预注册 ai/ihost/idbg/isys 为 kernel-native 模块" | Delete "ADR-020 G2"; keep "预注册 ai/ihost/idbg/isys 为 kernel-native 模块". Secondary: CODE G2. |
| core/engine.py:121 | ADR | `ADR-020 G6…ibci_file 插件消亡` — "注册 file 为 kernel-native 模块（ibci_file 插件消亡）" | Delete "ADR-020 G6：" and "（ibci_file 插件消亡）"; keep "注册 file 为 kernel-native 模块". Secondary: CODE G6, DATE (消亡). |
| core/engine.py:128 | ADR | `ADR-020 G6` — "import file also gates the disk-backed types into scope" | Delete "ADR-020 G6:"; keep "import file also gates the disk-backed types into scope". Secondary: CODE G6. |
| core/engine.py:198 | ADR | `ADR-019 §6 C2/G1` — "继承的父 plugin search_paths（隔离子引擎透传）" | Delete "ADR-019 §6 C2/G1："; keep "继承的父 plugin search_paths（隔离子引擎透传）". Secondary: DOC §6, CODE C2/G1. |
| core/engine.py:210 | ADR | `ADR-019 多阶段启动` — "project_root 确立 + root-dependent 延迟初始化" | Delete "ADR-019"; keep "多阶段启动：project_root 确立 + root-dependent 延迟初始化". |
| core/engine.py:214 | ADR | `ADR-019 §2` — "确立 project_root：= 显式 OR entry_dir" | Delete "ADR-019 §2"; keep "确立 project_root：= 显式 OR entry_dir". Secondary: DOC §2. |
| core/engine.py:225 | ADR | `ADR-019 §2` — error message "须在构造期显式提供 root_dir" | Delete "（ADR-019 §2）" from error message; keep functional text. Secondary: DOC §2. |
| core/engine.py:231 | CODE | `A5 与 D2 同源` — "project_root = entry_dir（canonicalize：解 symlink，A5 与 D2 同源）" | Delete "A5 与 D2" labels; keep "canonicalize：解 symlink". Note: comment claims symlink resolution but see code-smell finding (entry_file NOT canonicalized before parent extraction). |
| core/engine.py:235 | ADR | `ADR-019 多阶段启动` — "root-dependent 延迟初始化：plugin 发现路径 + Scheduler" | Delete "ADR-019"; keep "多阶段启动：root-dependent 延迟初始化…". |
| core/engine.py:238 | ADR | `ADR-019 §3` — "plugin 发现优先级见 _resolve_plugin_search_paths" | Delete "（ADR-019 §3）"; keep functional pointer to method. Secondary: DOC §3. |
| core/engine.py:254 | ADR | `ADR-019 §3` — "plugin 发现优先级（高 -> 低，先命中者胜）" docstring | Delete "ADR-019 §3"; keep "plugin 发现优先级（高 -> 低…）". Secondary: DOC §3. |
| core/engine.py:263 | CODE | `G1 修复` — "继承的 global_plugin 单独透传，并入优先级 2…保持 global_plugin 不被普通优先级覆盖" | Delete "G1 修复：" label; keep "继承的 global_plugin 单独透传…". Secondary: DATE (修复). |
| core/engine.py:264 | ADR | `ADR-019 §3` — "保持 ADR-019 §3 global_plugin 不被普通优先级覆盖 在隔离子引擎中也成立" | Delete "ADR-019 §3"; keep "global_plugin 不被普通优先级覆盖". Secondary: DOC §3. |
| core/engine.py:267 | ADR | `ADR-019 §5` — "plugin_path 只读特权：可在 project_root 之外" | Delete "ADR-019 §5："; keep "plugin_path 只读特权：可在 project_root 之外". Secondary: DOC §5. |
| core/engine.py:274 | CODE | `G1` — "global_plugin = 自身 + 继承（去重保序，保持在优先级 2）" | Delete "G1：" label; keep "global_plugin = 自身 + 继承（去重保序…）". |
| core/engine.py:321 | CODE | `D4…方案 B` — "entry_dir 从 PathContext（D4 锚点容器）读取--方案 B 保证其始终有意义" | Delete "D4" and "方案 B" labels; keep "entry_dir 从 PathContext（锚点容器）读取--保证其始终有意义". |
| core/engine.py:390 | ADR | `ADR-020 G2` — "在 registry hooks 全部注入后，给 kernel-native 模块 late-hydrate 窗口" | Delete "ADR-020 G2："; keep "在 registry hooks 全部注入后…late-hydrate 窗口". Secondary: CODE G2. |
| core/engine.py:403 | ADR | `ADR-019 §3` — "plugin 发现走统一解析的 search_paths" | Delete "ADR-019 §3："; keep "plugin 发现走统一解析的 search_paths". Secondary: DOC §3. |
| core/engine.py:427 | ADR | `ADR-019` — "可能在 run() 前调用（如 main.py load_external_plugins）" | Delete "ADR-019：" prefix; keep "可能在 run() 前调用（如 main.py load_external_plugins）". |
| core/engine.py:451 | ADR | `ADR-020 G2` — "传入已有的 host_interface，保留构造期预注册的 kernel-native 模块" | Delete "ADR-020 G2："; keep functional explanation. Secondary: CODE G2. |
| core/engine.py:460 | ADR | `ADR-019 §2 / A3` — "run_string 无真实 entry_file -> 合成 entry" | Delete "ADR-019 §2 / A3："; keep "run_string 无真实 entry_file -> 合成 entry". Secondary: DOC §2, CODE A3. |
| core/engine.py:467 | ADR | `ADR-019 A3` — "合成 entry：anchor 语义，非源码文件" | Delete "（ADR-019 A3）"; keep "合成 entry：anchor 语义，非源码文件". Secondary: CODE A3. |
| core/engine.py:508 | ADR | `ADR-019 多阶段启动` — "先确立 project_root + root-dependent 初始化" | Delete "ADR-019"; keep "多阶段启动：先确立 project_root + root-dependent 初始化". |
| core/engine.py:511 | CODE | `A5…修复 B1…§6.1` — "entry 锚点：经 canonicalize_for_security 规范化（A5…）。修复 B1--原仅 resolve_dot_segments（词法），对相对 entry 会产出相对 entry_dir，破坏 §6.1 运行时路径解析" | Delete "A5"、"B1"、"§6.1" labels; rewrite to present tense: "entry 锚点：经 canonicalize_for_security 规范化（解 symlink、绝对化相对路径）。原仅 resolve_dot_segments 对相对 entry 产出相对 entry_dir，破坏运行时路径解析". Secondary: DATE (修复/原). |
| core/engine.py:557 | ADR | `ADR-019 多阶段启动` — "确立 project_root（= 显式 OR entry_dir）+ root-dependent 初始化" | Delete "ADR-019"; keep "多阶段启动：确立 project_root…". |
| core/engine.py:560 | ADR | `ADR-019` — "确立 project_root + root-dependent 初始化（幂等）" | Delete "ADR-019："; keep "确立 project_root + root-dependent 初始化（幂等）". |
| core/engine.py:566 | CODE | `A5` — "entry_file 直接用作编译输入（源码位置）；A5：canonicalize（解 symlink、绝对化）" | Delete "A5：" label; keep "canonicalize（解 symlink、绝对化）". |
| core/engine.py:596 | ADR | `ADR-019` — "execute() 依赖 root-dependent 初始化" | Delete "ADR-019：" prefix; keep "execute() 依赖 root-dependent 初始化". |
| core/engine.py:598 | CODE | `修复 B2：原为 AttributeError` — "直接 execute() 未经编译 -> 明确报错（修复 B2：原为 AttributeError）" | Delete "B2" label and "原为 AttributeError" historical detail; rewrite: "直接 execute() 未经编译 -> 明确报错". Secondary: DATE (修复/原为). |
| core/engine.py:603 | ADR | `ADR-019 多阶段启动` — error message "root-dependent 设置延迟到首次编译/运行" | Delete "（ADR-019 多阶段启动…）" from error message; keep functional text. |
| core/engine.py:609 | CODE | `[P2-D]` — "包装为 ImmutableArtifact，防止解释器修改 artifact" | Delete "[P2-D]" label; keep "包装为 ImmutableArtifact，防止解释器修改 artifact". |
| core/engine.py:644 | ADR | `ADR-019 多阶段启动` — "确立 project_root + root-dependent 初始化" (check docstring) | Delete "ADR-019"; keep "多阶段启动：确立 project_root + root-dependent 初始化". |
| core/engine.py:645 | CODE | `A5` — "entry 规范化统一走 canonicalize_for_security（与 run/compile 同源，解 symlink）" | Delete "A5：" label; keep "entry 规范化统一走 canonicalize_for_security". |
| core/engine.py:647 | ADR | `ADR-019` — "确立 project_root + root-dependent 初始化" | Delete "ADR-019："; keep "确立 project_root + root-dependent 初始化". |
| core/engine.py:683 | ADR | `ADR-019 §5` — "隔离反转：解析子 entry + 校验其在父 project_root 内" | Delete "ADR-019 §5"; keep "隔离反转：解析子 entry + 校验其在父 project_root 内". Secondary: DOC §5. |
| core/engine.py:688 | ADR | `ADR-019 §5 open` — "未来：policy 可放开特定外部 zone" | Delete "ADR-019 §5 open"; keep "未来：policy 可放开特定外部 zone". Secondary: DOC §5. |
| core/engine.py:700 | ADR | `ADR-019 §5` — error message "现阶段子脚本不得超出父 proj_root" | Delete "（ADR-019 §5…）" from error message; keep functional text. Secondary: DOC §5. |
| core/engine.py:712 | ADR | `ADR-019 §5` — "子 host 沙箱派生 + 隔离反转校验" | Delete "ADR-019 §5："; keep "子 host 沙箱派生 + 隔离反转校验". Secondary: DOC §5. |
| core/engine.py:715 | ADR | `ADR-019 §6 C2` — "实例化全新的 Engine（继承父 plugin search_paths）" | Delete "ADR-019 §6 C2"; keep "实例化全新的 Engine（继承父 plugin search_paths）". Secondary: DOC §6, CODE C2. |
| core/engine.py:721 | ADR | `ADR-019 §6` — inline "继承父 plugin" | Delete "ADR-019 §6：" from inline comment; keep "继承父 plugin". Secondary: DOC §6. |
| core/engine.py:722 | CODE | `G1` — inline "global_plugin 单独透传保持优先级" | Delete "G1：" label; keep "global_plugin 单独透传保持优先级". |
| core/engine.py:739 | ADR | `ADR-019 §5` — "派生 + 隔离反转校验" | Delete "ADR-019 §5："; keep "派生 + 隔离反转校验". Secondary: DOC §5. |
| core/engine.py:746 | ADR | `ADR-019 §6` — inline "继承父 plugin" | Delete "ADR-019 §6：" from inline comment; keep "继承父 plugin". Secondary: DOC §6. |
| core/engine.py:747 | CODE | `G1` — inline "global_plugin 单独透传保持优先级" | Delete "G1：" label; keep "global_plugin 单独透传保持优先级". |

### core/runtime/host/host_interface.py

| file:line | CAT | current_snippet | proposed_cleaning |
|-----------|-----|-----------------|-------------------|
| core/runtime/host/host_interface.py:1 | DATE | `向后兼容垫片 - 实际定义已移至 core/kernel/host_interface.py` + L3 "移至 kernel 层以消除 compiler -> runtime 层级反转" | Rewrite to present tense: "HostInterface 定义位于 core/kernel/host_interface.py；本模块 re-export 以维持 import 路径". Delete "向后兼容垫片" historical framing. Note: file IS a re-export shim (see code-smell review). |

### core/runtime/host/service.py

| file:line | CAT | current_snippet | proposed_cleaning |
|-----------|-----|-----------------|-------------------|
| core/runtime/host/service.py:79 | PT | `属 PT-ARCH-13` — "assets 的 __EXTERNAL_FILE_REF__ 哨兵是序列化格式约定，属 PT-ARCH-13" | Delete "属 PT-ARCH-13（…）" pointer clause; keep "哨兵是序列化格式约定". |
| core/runtime/host/service.py:83 | PT | `PT-ARCH-26：` — "在序列化之前扫描活跃变量，若存在磁盘型容器则直接拒绝" | Delete "PT-ARCH-26：" prefix; keep "在序列化之前扫描活跃变量，若存在磁盘型容器则直接拒绝". |
| core/runtime/host/service.py:226 | TC | `PENDING_TASKS.md §10.2` — "返回执行结果（当前简化为布尔值；多返回值改进见 PENDING_TASKS.md §10.2）" | Delete "见 PENDING_TASKS.md §10.2" pointer; keep "返回执行结果（当前简化为布尔值；多返回值改进待实现）". Secondary: DOC §10.2. |
| core/runtime/host/service.py:254 | DOC | `§6.1 契约` — "委托规范解析器 PathResolver（entry_dir 单锚点，§6.1 契约）" | Delete "§6.1" section number; keep "委托规范解析器 PathResolver（entry_dir 单锚点契约）". |
| core/runtime/host/service.py:257 | DATE | `历史实现统一走 os.path.abspath` — "历史实现统一走 os.path.abspath，相对 cwd 解析，与 file.read 语义不一致，导致 README §5 与 examples/… 仅在 cwd 恰好为入口目录时才能跑通" | Rewrite to present tense or delete historical paragraph. Keep current-behavior explanation: "使用 PathResolver（entry_dir 锚点）解析，与 file.read 的相对入口目录语义一致". Delete "历史实现…" narrative. Secondary: DOCREF (README §5, examples path). |

### core/runtime/module_system/discovery.py

| file:line | CAT | current_snippet | proposed_cleaning |
|-----------|-----|-----------------|-------------------|
| core/runtime/module_system/discovery.py:32 | ADR | `ADR-019` — "仅做分隔符规范化；调用方保证路径为绝对路径（ADR-019）" | Delete "（ADR-019）"; keep "仅做分隔符规范化；调用方保证路径为绝对路径". |
| core/runtime/module_system/discovery.py:44 | ADR | `ADR-020 G2` — "用于保留构造期预注册的 kernel-native 模块" | Delete "（ADR-020 G2）"; keep "用于保留构造期预注册的 kernel-native 模块". Secondary: CODE G2. |
| core/runtime/module_system/discovery.py:79 | ADR | `ADR-020 G2` — "已预注册的 kernel-native 模块不再从磁盘重复加载" | Delete "ADR-020 G2："; keep "已预注册的 kernel-native 模块不再从磁盘重复加载". Secondary: CODE G2. |
| core/runtime/module_system/discovery.py:156 | DATE | `向前兼容…旧插件` — "缺省值为 method_module，以确保向前兼容（所有未声明 kind 的旧插件均被视为 method_module）" | Rewrite to present tense: "缺省值为 method_module；未声明 kind 的插件被视为 method_module". Delete "向前兼容" and "旧" historical framing. |

### core/runtime/module_system/loader.py

| file:line | CAT | current_snippet | proposed_cleaning |
|-----------|-----|-----------------|-------------------|
| core/runtime/module_system/loader.py:37 | ADR | `ADR-019` — "仅做分隔符规范化；调用方保证路径为绝对路径（ADR-019）" | Delete "（ADR-019）"; keep "仅做分隔符规范化；调用方保证路径为绝对路径". |
| core/runtime/module_system/loader.py:207 | ADR | `ADR-020 G2` — "kernel-native 模块已在构造期预注册，不再从磁盘加载覆盖" | Delete "ADR-020 G2："; keep "kernel-native 模块已在构造期预注册，不再从磁盘加载覆盖". Secondary: CODE G2. |
| core/runtime/module_system/loader.py:240 | DATE | `兼容直接导出的类或函数` — "兼容直接导出的类或函数（如有必要可扩展）" | Rewrite: "支持直接导出的类或函数（如有必要可扩展）". Delete "兼容" (implies legacy pattern). |

### core/runtime/path/__init__.py

| file:line | CAT | current_snippet | proposed_cleaning |
|-----------|-----|-----------------|-------------------|
| core/runtime/path/__init__.py:4 | ADR | `Per ADR-017` — "纯路径原语与 IBCI 路径模型已下沉至 base/path 与 kernel/path" | Delete "Per ADR-017：" and rewrite "已下沉至" to present: "纯路径原语与 IBCI 路径模型位于 base/path 与 kernel/path". Secondary: DATE (已下沉). |
| core/runtime/path/__init__.py:10 | ADR | `命名（ADR-020 §E）` — "原 BuiltinPaths -> InstallPaths（builtin 一词五义消除）" | Delete "ADR-020 §E" and "原 BuiltinPaths ->" rename history; keep "InstallPaths：精确表达安装根路径语义". Secondary: DOC §E, DATE (原). |

### core/runtime/path/install.py

| file:line | CAT | current_snippet | proposed_cleaning |
|-----------|-----|-----------------|-------------------|
| core/runtime/path/install.py:4 | ADR | `Per ADR-015 D3` — "本服务是 IBCI 安装根的唯一计算点" | Delete "Per ADR-015 D3："; keep "本服务是 IBCI 安装根的唯一计算点". Secondary: CODE D3. |
| core/runtime/path/install.py:5 | DATE | `历史上 4 处独立用 __file__ 遍历（3 种不同公式）` — "导致碎片化" | Delete historical narrative; keep current-behavior: "所有需要内置模块路径的站点都应委托本服务". |
| core/runtime/path/install.py:13 | ADR | `命名（ADR-020 §E）` — "原 BuiltinPaths（builtin 一词五义之一）-> InstallPaths" | Delete "ADR-020 §E" and "原 BuiltinPaths ->" rename history; keep "InstallPaths：精确表达安装根路径语义". Secondary: DOC §E, DATE (原). |

### core/runtime/rt_scheduler.py

| file:line | CAT | current_snippet | proposed_cleaning |
|-----------|-----|-----------------|-------------------|
| core/runtime/rt_scheduler.py:9 | DATE | `已通过接口化解除物理循环依赖` — "顶层导入核心实现类，已通过接口化解除物理循环依赖" | Rewrite to present tense: "顶层导入核心实现类，通过接口化解除物理循环依赖". Delete "已" perfective aspect. |
| core/runtime/rt_scheduler.py:41 | ADR | `ADR-019 §5` — "isolation 参数保留以维持协议兼容，但当前实现不再在调度器内分支处理隔离…通过新建 Engine 实例完成（ADR-019 §5）" | Delete "ADR-019 §5" and "协议兼容" historical framing; keep "isolation 参数保留但当前实现不再在调度器内分支处理隔离；隔离执行由 Engine.request_isolated_run 通过新建 Engine 实例完成". Secondary: DOC §5, DATE (兼容). |
| core/runtime/rt_scheduler.py:199 | DATE | `从 Engine 迁移而来` — "配置工厂的 IoC 注册表。从 Engine 迁移而来。" | Delete "从 Engine 迁移而来。" historical migration note; keep "配置工厂的 IoC 注册表。". |
| core/runtime/rt_scheduler.py:200 | CODE | `P5：旧 Handler 类…已删除` — "P5：旧 Handler 类（StmtHandler/ExprHandler/ImportHandler）已删除；VMExecutor CPS dispatch table 是唯一的 AST->执行映射，无需注册" | Delete "P5：旧 Handler 类…已删除；" (historical dead reference); keep "VMExecutor CPS dispatch table 是唯一的 AST->执行映射，无需注册". Secondary: DATE (旧/已删除). |

### core/runtime/bootstrap/kernel_native_modules.py

| file:line | CAT | current_snippet | proposed_cleaning |
|-----------|-----|-----------------|-------------------|
| core/runtime/bootstrap/kernel_native_modules.py:2 | ADR | `ADR-020 G2` — module docstring "内核原生模块预注册（ADR-020 G2）" | Delete "（ADR-020 G2）"; keep "内核原生模块预注册". Secondary: CODE G2. |

### core/runtime/bootstrap/primitive_initializer.py

| file:line | CAT | current_snippet | proposed_cleaning |
|-----------|-----|-----------------|-------------------|
| core/runtime/bootstrap/primitive_initializer.py:64 | ADR | `命名（ADR-020 §E）` — "原 initialize_builtin_classes（builtin 一词五义之一）-> initialize_primitive_classes" | Delete "ADR-020 §E" and "原 initialize_builtin_classes ->" rename history; keep "initialize_primitive_classes：精确表达语言原语类初始化语义". Secondary: DOC §E, DATE (原). |
| core/runtime/bootstrap/primitive_initializer.py:92 | DATE | `已下沉到各实现类的 @register_ib_type 装饰器中` — "基础类型与实现类的映射已下沉到各实现类的 @register_ib_type 装饰器中" | Rewrite to present: "基础类型与实现类的映射位于各实现类的 @register_ib_type 装饰器中". Delete "已下沉到" perfective. |
| core/runtime/bootstrap/primitive_initializer.py:97 | ADR | `ADR-020 §D` — "公理名清单统一从 AxiomRegistry 派生（ADR-020 §D：无硬编码特例/回退列表）" | Delete "（ADR-020 §D：…）"; keep "公理名清单统一从 AxiomRegistry 派生，无硬编码特例/回退列表". Secondary: DOC §D. |
| core/runtime/bootstrap/primitive_initializer.py:146 | DATE | `保持兼容性` — "获取引用以便后续绑定（保持兼容性）" | Delete "（保持兼容性）"; keep "获取引用以便后续绑定". |
| core/runtime/bootstrap/primitive_initializer.py:259 | DATE | `不再借用 none_class` — "llm_uncertain 有独立的公理类（不再借用 none_class）" | Rewrite to present: "llm_uncertain 有独立的公理类". Delete "（不再借用 none_class）" historical detail. |
| core/runtime/bootstrap/primitive_initializer.py:557 | DATE | `旧帧实现` — "防御性回退：旧帧实现没有新方法时仍能清空持久栈" | Rewrite: "回退：帧实现缺少 clear_inherited_intents 时直接操作 _intent_ctx". Delete "旧" and "防御性" framing. Note: code smell — accessing private _intent_ctx (see review). |
| core/runtime/bootstrap/primitive_initializer.py:611 | ADR | `Per ADR-012` — "作为普通类名注册，通过 axiom -> primitive_initializer 标准路径" | Delete "Per ADR-012:"; keep "作为普通类名注册，通过 axiom -> primitive_initializer 标准路径". |
| core/runtime/bootstrap/primitive_initializer.py:612 | ADR | `Per ADR-014/016` — "media 类型现在是 file_handle 的磁盘型子类" | Delete "Per ADR-014/016:"; keep "media 类型是 file_handle 的磁盘型子类". Secondary: DATE (现在). |
| core/runtime/bootstrap/primitive_initializer.py:643 | PT | `PT-ARCH-25:` — "media 静态构造入口 audio.from_file / image.from_file / video.from_file" | Delete "PT-ARCH-25:" prefix; keep "media 静态构造入口 audio.from_file / image.from_file / video.from_file". |
| core/runtime/bootstrap/primitive_initializer.py:655 | ADR | `Per ADR-020` — "file_handle 为 kernel-native 类型，import-gated" | Delete "Per ADR-020:"; keep "file_handle 为 kernel-native 类型，import-gated". |
| core/runtime/bootstrap/primitive_initializer.py:656 | ADR | `Per ADR-016` — "声明 storage_model = DISK_BACKED，由 deep_clone / RuntimeSerializer 自动走磁盘协议族" | Delete "Per ADR-016:"; keep "声明 storage_model = DISK_BACKED…". |
| core/runtime/bootstrap/primitive_initializer.py:661 | PT | `PT-ARCH-25:` — "file_handle 实例只读，无 write() 方法" | Delete "PT-ARCH-25:" prefix; keep "file_handle 实例只读，无 write() 方法". |
| core/runtime/bootstrap/primitive_initializer.py:677 | DATE | `清理遗留 Legacy 术语与残留注释` — "清理遗留 Legacy 术语与残留注释" (stale, no corresponding code) | Delete entirely — stale comment with no corresponding code action. |

### core/runtime/interfaces.py

| file:line | CAT | current_snippet | proposed_cleaning |
|-----------|-----|-----------------|-------------------|
| core/runtime/interfaces.py:53 | ERR | `公理 GC-2` — "公理 GC-2 根集合扫描入口" | KEEP+normalize. Note: GC not in standard ERR list (SEM/DEP/PAR/INV/SC/LT/CF/OM) but is a formal axiom reference. Consider normalizing to "Axiom GC-2" English form or keeping as-is. |
| core/runtime/interfaces.py:58 | CODE | `C12` — "C12 封装替代私有 _cell_map 探测" | Delete "C12" label; keep "封装替代私有 _cell_map 探测". Note: C12 outside stated C2-C11 range but is same codename series. |
| core/runtime/interfaces.py:64 | CODE | `C12` — "VM 特殊路径专用，C12" | Delete "，C12" label; keep "VM 特殊路径专用". Note: C12 outside stated C2-C11 range. |
| core/runtime/interfaces.py:256 | DATE | `历史的…已废弃` — "历史的 IntentNode 链表 / 已展平 list 路径已废弃" | Delete entirely (describes dead/废弃 path); or rewrite to present: "captured_intents 使用 IbIntentContext". |

### core/runtime/shared/signals.py

| file:line | CAT | current_snippet | proposed_cleaning |
|-----------|-----|-----------------|-------------------|
| core/runtime/shared/signals.py:22 | ERR | `公理 CF-1` — "控制流信号枚举（公理 CF-1）" | KEEP+normalize. CF-1 matches ERR pattern. Consider normalizing "公理 CF-1" to "Axiom CF-1". |
| core/runtime/shared/signals.py:52 | CODE | `C5` — "VM 顶层未消费信号的边界异常（C5）" | Delete "（C5）" label; keep "VM 顶层未消费信号的边界异常". |

### Files with zero findings

- `core/runtime/host/isolation_policy.py` — no markers (but see code-smell: type bug in `__post_init__`)
- `core/runtime/host/sync_manager.py` — no markers (but see code-smell: `_wait_for_sync` is no-op)
- `core/runtime/module_system/__init__.py` — empty file
- `core/runtime/shared/__init__.py` — empty file
- `core/runtime/shared/llm_result.py` — no markers
- `core/runtime/shared/op_constants.py` — no markers
