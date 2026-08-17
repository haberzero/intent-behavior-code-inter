# F3 — 插件体系重构（废弃 Python _spec.py 思路，设计定稿 + 进度）

> 临时任务控制文档（governance：F3 完成后删除，决策沉入 docs/）。主线：
> ROADMAP_NATIVE_BINDING.md §三【远期愿景】F3。本文件由研读报告（subagent 4f5a1e99）
> + 2026-08-17 session 自主定稿更新。**当前分支 `exp/plugin-refactor-f3`**
> （自 unsafe-vibe-dev @3ce67993 起）。

## 〇、F3 目标与验证门

- **F3 目标**：废弃「Python 侧手写 `_spec.py` 暴露库给 IBCI」的思路；既有 `_spec.py`
  插件按新宿主绑定统一 / 内核原生隔离；**不保留双通道**（用户侧扩展唯一边 = 宿主绑定 bind）。
- **验证门**：全量 pytest 零回归；无 `_spec.py` 残留路径；用户侧扩展仅经 bind。
- **最终删除面**：10 个 `_spec.py` + `core/extension/auto_discovery.py`
  + `core/runtime/module_system/discovery.py` + loader 磁盘扫描环 2 + 插件搜索路径配置面
  + `main.py --plugin`/`load_external_plugins` + SDK gen_spec/check 的 _spec 相关面
  + `__ibcext_axiom__` 死协议 + 相关测试/examples/trials/docs。

## 一、F3 总体方案（本 session 定稿）

**内置模块全部内联 TypeDef spec，集中到 `core/runtime/bootstrap/kernel_native_modules.py`。**

- 覆盖全部 10 个内置模块：内核原生 5（ai/ihost/idbg/isys/iruntime）+ 工具 5
  （math/json/time/net/schema）+ file（spec 从 engine.py:155-198 挪出，修复 engine 膨胀）。
- `_load_spec`（读 _spec.py + ModuleDiscoveryService）删除；每模块 spec = TypeDef 字面量，
  预注册于 Engine 构造期（同 file 先例）。
- **工具插件实现不改**：现为类实例（MathLib/JSONLib/TimeLib/SchemaLib/NetLib +
  create_implementation），loader 环 1 `_validate_and_bind` 走
  `context.interop.metadata.resolve` + `getattr(implementation, name)`，类实例持有全部成员，
  **无需改模块级函数**（探针 A1 印证：仅 bind 模块成员路径需模块级函数，loader 路径不需要）。
- **F3-0（bind 默认参数语法）已重新裁决：跳过**。研读报告曾建议给 bind 补默认参数
  （net 的 headers 默认 None 需要）；但 IBCI 用户函数本身支持默认参数
  （`IbArg.default`，parser declaration.py:484-534 解析 `= 默认值`），故工具库默认值
  放 **.ibci 包装层**（bind = 裸原生契约无默认值；wrapper = IBCI 侧人体工学补默认），
  bind 语法零改动。bind 调用点经包装函数显式传全部实参，编译期签名检查天然满足。
- **裁决点 3（内置工具库归宿）收敛为第三态**：研读 (a) 彻底删 / (b) IBCI 标准库
  （.ibci 源码库 + bind 包装）；本 session 收敛为 **「内联 spec 的内置模块」**——
  保 `import math` 全兼容（44 个测试文件隐式走插件路径，零迁移），契约从 Python _spec.py
  移入内核 TypeDef 字面量。bind-based IBCI 标准库（研读 (b) 的真正形态）推迟到 F5
  内核自举时再评估（届时内置契约可再表达为 bind 声明）。

## 二、关键约束（下个 session 必须遵守）

- `tests/runtime/test_kernel_native_modules.py:42-43` 断言 `math`/`time` **不是**
  KERNEL_NATIVE → 工具 5 模块内联 spec **不得标 KERNEL_NATIVE provenance**
  （用 TypeDef 默认 provenance + `Visibility.IMPORT_GATED`，同 discovery 现状）。
  内核原生 5 + file 保持 KERNEL_NATIVE + IMPORT_GATED。
- loader 环 1 `_validate_and_bind`（loader.py:51-144）消费 `spec_member.param_descriptors`：
  `param_meta = [(d.name, d.kind, ("value", d.default_value) if d.has_default else None)]`、
  `has_declared_varkw = any(d.kind == "VAR_KEYWORD")`、具名参数契约 + varkw 契约。
  → 内联 TypeDef 必须**结构等价**于 discovery `_build_spec_from_dict`
  （discovery.py:160-243）产出，尤其：
  - `ai.set_mock_mode`：`ParamDescriptor(name="enable", kind="POSITIONAL_OR_KEYWORD",
    type_ref=TypeRef.of("bool"), has_default=True, default_value=True)`
  - `iruntime.configure`：`ParamDescriptor(name="kwargs", kind="VAR_KEYWORD",
    type_ref=TypeRef.of("any"))`（无 default）
  - `math` variables：pi/e/inf = `MemberSpec(name, kind="field", type_ref=TypeRef.of("float"))`
  - `json.__to_prompt__`：是 **functions 成员**（method），须保留为 MethodMemberSpec
  - `net` 的 get/get_json/post/post_json/post_form/put/delete/head：headers 参数
    `has_default=True, default_value=None`
- 类型字符串直译 `TypeRef.of(ptype)`（str/dict/void/bool/subscriber/list/int/float/any/
  behavior/chan 等均为已注册类型名，file 先例同法）。

## 三、已完成探针（本 session）

- **A1**：`import python "ibci_modules.ibci_math.core" as m: bind sqrt(x: float) -> float`
  → 报 `Host binding: ... has no member 'sqrt' declared in bind`。结论：
  (a) `ibci_modules.ibci_math.core` **可导入**（`python -` 时 cwd 在 sys.path，仓内成立）；
  (b) 类实例实现无模块级 `sqrt` → bind 模块成员路径失败 → 印证 loader 路径（类实例）
  是工具插件内联 spec 的正确载体，无需改实现。
- **IBCI 用户函数默认参数**：已确认支持（`IbArg.default` + declaration.py 解析），
  支撑 F3-0 跳过裁决。

## 四、建议实施顺序（定稿）

1. **F3-1 内联 spec 化（当前）**：
   a. 写生成脚本：对 10 个 _spec.py，用 discovery 旧路径产出 TypeDef，再序列化为等价的
      TypeDef 字面量 Python 代码（保结构等价，防手写漂移）。
   b. 集中写入 `kernel_native_modules.py`（如 `BUILTIN_MODULE_SPECS: Dict[str, TypeDef]`，
      含 file，file 从 engine.py 挪出）；改 `register_kernel_native_modules` 直用字面量。
   c. 删除 10 个 `_spec.py`；`_load_spec`/discovery import 移除。
   d. 验证：结构等价探针（内联 spec vs 旧 discovery 输出逐字段比对）+ 
      `tests/runtime/test_kernel_native_modules.py` + 全量 pytest 零回归。
2. **F3-2 拆发现/加载通道**：删 `core/extension/auto_discovery.py`、
   `core/runtime/module_system/discovery.py`、loader 磁盘扫描环 2（用户插件 _spec.py 发现）、
   插件搜索路径配置面（IbciConfig plugin_paths/global_plugin、ProjectDetector 嗅探、
   继承透传）、`main.py --plugin`/`load_external_plugins`、SDK gen_spec/check 的 _spec 面、
   `__ibcext_axiom__` 死协议。`load_and_register_all` 收敛为仅内置模块注册。
3. **F3-3 测试/examples/trials/docs 迁移**：122 直接测试 + 44 隐式走插件加载的文件按
   新语义改（test_plugin_discovery、test_isolation_plugin_inheritance、
   test_kernel_diagnostics、SDK 测试、examples/plugins_demo、isolation_demo、trials/T01、
   docs/subsystems/04_plugin_system.md、KNOWN_LIMITS §十九、write_user_plugin.md 等）。
4. **F3-4 残留扫描 + 全量 pytest**：`_spec.py`/`__ibcext_vtable__`/discovery 引用清零。

## 五、与主线衔接

F3 是 F1/F2 收敛（插件体系统一到新绑定）；F4 用新绑定统一 provider 自定义
（逆 R 期改内核文件临时态）；F5 架构统一/文档收敛 + 内核自举（内置契约再表达为 bind
声明）+ 缓存/JIT + 隔离 + 反射。F3-1 完成后即在 unsafe-vibe-dev 同步 NEXT_STEPS/WORKLOG。

## 六、F3-1 落地记录（2026-08-18，exp/plugin-refactor-f3）

**完成态**：10 个 `_spec.py`（内核原生 5 + 工具 5）已删除；全部内置模块 TypeDef 字面量
集中 `core/runtime/bootstrap/builtin_modules.py`（`BUILTIN_MODULE_SPECS`，含 file 自
engine.py 挪入）；Engine 构造期一次注册全部 11 模块（含实现）。

**相对定稿方案的偏离（均自主决策，理由见下）**：
1. **文件/函数重命名**：`kernel_native_modules.py` → `builtin_modules.py`；
   `register_kernel_native_modules` → `register_builtin_modules`。理由：文件职责从
   "内核原生 5"扩展为"全部内置模块"，旧名不再反映真实内容（design-philosophy §八
   命名统一）。波及：engine.py + 测试 import（均已同步）。
2. **loader 环 2 跳过"构造期已注册实现"的模块**。理由：工具 5 构造期注册实现后，环 1
   已统一 validate/bind/setup；若环 2 仍按物理目录重复加载会创建第二个实现实例并重新
   绑定（双通道绑定）。新增 `interop.get_package(module_name) is not None → skip`——
   即 F3-2 删除环 2 后的终点语义，现在落地消除中间态双绑定。
3. **删除冗余显式 `reserve_kernel_native_name` 调用**。理由：`HostInterface.register_module`
   对 KERNEL_NATIVE provenance 元数据已内建自动 reserve（机制同构，不重复声明）。
4. **测试文件重命名**：`test_kernel_native_modules.py` → `test_builtin_modules.py`
   （覆盖范围已扩展为全部内置模块）；`tests/plugins/test_idbg.py` 由 import
   `ibci_modules.ibci_idbg._spec` 改为断言 `BUILTIN_MODULE_SPECS["idbg"]`（F3 语义：
   spec 只存在于内核字面量）。

**验证**：
- 结构等价探针（一次性，_spec.py 删除前运行）：9 个模块字面量 vs 旧 discovery 路径
  产出 TypeDef 逐字段比对等价（name/module_path/kind/provenance/visibility/
  storage_model/exported_types/members 全字段，含 param_descriptors 默认值）。
- `test_builtin_modules.py` 固化契约断言：ai.set_mock_mode 默认 True、
  iruntime.configure VAR_KEYWORD、json.__to_prompt__ 为 method、math 变量 field、
  net headers 默认 None、工具 5 = USER_DEFINED + IMPORT_GATED、file exported_types、
  register_builtin_modules 幂等。
- 冒烟：`import math/json/time/schema/file` 全链路（sqrt/pi/stringify/now/validate/exists）。
- 全量 pytest 零回归（实跑计数不冻结）。

**F3-1 遗留（排入 F3-2/F3-3）**：
- discovery.py / auto_discovery.py / loader 环 2 的 _spec.py 相关代码与文案（用户插件
  通道）——F3-2 一并删除。
- `load_and_register_all` 环 2 收敛为仅内置模块注册——F3-2 落地。
- 文档迁移（docs/subsystems/04_plugin_system.md、07_kernel_native_modules.md 注册描述、
  KNOWN_LIMITS §十九、write_user_plugin.md、示例/trials）——F3-3。

## 七、F3-2 落地记录（2026-08-18，exp/plugin-refactor-f3）

**完成态**：磁盘插件发现/加载双通道完全铲除——`core/runtime/module_system/discovery.py`
与 `core/extension/auto_discovery.py` 删除；loader 环 2（磁盘扫描 + create_implementation
实例化 + 二次绑定）删除，`load_and_register_all` 收敛为仅对已注册实现做环 1 契约绑定；
`resolve_plugin_search_paths`/插件搜索路径配置面（`IbciConfig` plugin_paths/global_plugin、
`ProjectDetector.get_plugin_paths` 嗅探、继承透传 inherited_plugin_paths/
inherited_global_plugin）全部删除；main.py `--plugin`/`--no-sniff`/`load_external_plugins`
删除；`register_native_module` 引擎 API 删除（唯一消费者即 main.py）；SDK
`ibci_sdk/`（gen_spec/check）整包删除；`__ibcext_axiom__` 死协议（engine 公理加载面）
删除；`core/extension/spec_builder.py`（`SpecBuilder`/`ClassSpecBuilder`，为旧 _spec.py
书写的零消费者工具类）删除；幽灵诊断码 `KDIAG_POLICY_MODULE_NO_EXPORT`（唯一发射点为
loader 环 2）从其 codes.py/catalog/docs 删除。Engine 构造还原为 `IBCIEngine(root_dir=...)`
单一签名（无 auto_sniff/继承参数）。

**相对 F3-1 定稿方案 / 研读的偏离（均自主决策）**：
1. **`IBCIEngine` 签名简化为 `root_dir` 单一参数**——移除 auto_sniff/inherited_*
   三个参数。理由：插件搜索路径概念整体删除后参数无所承载；F3-2 终点语义。
   41 处测试 `auto_sniff=False` 机械迁移为无参构造。
2. **`ibci_sdk` 整包删除**——gen_spec/check 是"写/查 _spec.py 插件"工具，F3 后无用户
   插件撰写场景，死代码（质量红线）；其测试 test_check_plugin 上一轮已迁移 F3 语义，
   此次连 SDK 一并移除。
3. **`register_native_module` 引擎 API 删除**——唯一消费者 main.py `load_external_plugins`
   （同 F2 R 期遗留的动态注册面，F3-2 目标之一"load_and_register_all 收敛"延伸）。
4. **隔离超时测试稳定化**：`test_timeout_raises_when_child_exceeds_deadline` 由
   "启动耗时 > 1ms"脆弱墙钟假设改为子任务先 sleep 再返回（F3 移除插件发现后子引擎
   启动更快使原假设偶发失效）。追踪根因修正，非环境 flaky 搪塞。

**验证**：全量 pytest 零回归（实跑计数不冻结）；`KDIAG_POLICY_MODULE_NO_EXPORT` 幽灵码
清除经 test_diagnostic_catalog CAT-7 佐证；`spec_builder` 死代码清零经零消费者扫描。
冒烟：`import math/json/time/schema/file` 全链路正常（同 F3-1）。

## 八、F3-3 落地记录（2026-08-18，exp/plugin-refactor-f3）

**完成态**：examples/trials/docs 全部迁移到 F3 新语义（用户侧扩展唯一边 = 宿主绑定 bind）。

- **examples**：`03_advanced_features/plugins_demo/` 整目录删除（演示已删除的用户插件
  `_spec.py` 系统）；`isolation_demo/sub_project/plugins/` 删除（用户插件路已删，
  parent/child.ibci 隔离演示保留）；`03_advanced_features/README.md` 重写（移除插件
  系统/插件开发章节，目录树更新，指明用户扩展唯一通道 = 宿主绑定）。
- **trials/T01**：`plugins/`（calc/plugin_info 用户插件 _spec.py）删除；
  `cases/D2-21-plugin.ibci` 改写为宿主绑定演示（`import python "math" as m: bind
  sqrt/pow`，expect-out 改为 `sqrt=4.0 | pow=1024.0 | DONE`，经 main.py 实跑验证通过）；
  `REGISTER.md` D2-21 行与 `D1_MATRIX.md` D1-11-008 条目同步为新语义（历史 REV 行与
  缺陷证据段保留原状——它们是历史运行记录）。
- **docs**：
  - `howto/write_user_plugin.md` **删除**，替换为新 howto `howto/extend_with_host_binding.md`
    （宿主绑定 bind 操作指南）。决策理由：旧主题（写 _spec.py 插件）整体不存在，且与
    重写后的 subsystems/04 不同层（howto=操作指南 vs subsystems=内部设计），不重复；
    文件名改写避免误导性文件名。引用方（modify_llm_provider.md ×2、docs/README.md
    目录树）已同步。
  - `subsystems/04_plugin_system.md` **重写**为"内置模块系统与宿主绑定"：内置 11 模块
    构造期注册（builtin_modules.py）+ 无插件搜索路径 + 宿主绑定为用户扩展唯一通道 +
    HostInterface 覆盖保护；_spec.py/plugin_paths/AutoDiscovery/用户插件描述全删
    （文件名保留，避免大范围断链，主题由标题与内容承载）。
  - `architecture/07_kernel_native_modules.md`：更新为"内置 11 模块（内核原生 5 +
    工具 5 + file）构造期一次注册 builtin_modules.py"；覆盖保护描述改为注册路径
    （register_module 内建 reserve + KDIAG_POLICY_MODULE_OVERRIDE）；保留两轴模型 /
    exported_types / 单一 setup / provenance 门控。
  - `architecture/01_principles.md` §七重写（模块系统与宿主绑定；删 §7.3 嗅探全节）、
    §九自动注册表（删 ModuleDiscoveryService/SpecBuilder 行）、附录关键文件索引
    （discovery.py 行 → builtin_modules.py 行）、HOST 双路暴露附录措辞。
  - `architecture/06_path_system.md`：五概念 → 四概念（删 plugin_paths）；§3 插件发现
    优先级整节改写为"模块加载（无插件搜索路径）"；§4 删继承插件路径条目。
  - `architecture/01_native_host_binding.md`：状态头更新为 F0-F3 已合入；§一/§2.3/§2.4
    的"当前 _spec.py"表述改为历史/已完成叙述；§3.4 标记 F3 已完成。
  - 定点修正：`03_type_system.md`（描述符来源 → builtin_modules.py param_descriptors）、
    `05_functions.md`（原生模块具名调用声明来源）、`09_observability.md` 与
    `15_diagnostics.md`（KDIAG_POLICY_MODULE_OVERRIDE 触发描述去"用户插件"）、
    `05_vm_specification.md` ISO-10（插件可见性隔离 → 模块可见性隔离）、
    `KNOWN_LIMITS` §十九（改题"模块可见性隔离与无状态约定"，内容覆盖内置模块 +
    宿主绑定 sys.modules 边界，删跨 project_root 用户插件条目）、
    `guide/00_environment.md`（删 ibci_sdk import 验证）、`ARCHITECTURE.md` 索引
    （06 四概念、07 标题）、`SUBSYSTEM_DESIGN.md` 04 行、`LANGUAGE_DESIGN_EVOLUTION.md`
    §3.8（_spec.py 现状描述 → TypeDef 字面量 + bind）、`syntax/11_modules.md`
    （§11.2 内置模块注册语义、§11.9 改为用户扩展=宿主绑定指针、§11.10 去
    "F1 成果/推翻 _spec.py"叙述、章题改"模块与宿主绑定"）。
  - 根 `README.md`：特性条"插件化扩展（自动嗅探）"→"宿主绑定扩展"；文档链接区
    "编写用户插件"→"宿主绑定扩展"。
- **保守保留**（有意不改）：`guide/01_setup.md` 项目标志列表中的 `plugins/`——
  `core/project_detector.py` 仍把 `plugins/` 列为 project_root 探测标志（代码事实，
  文档以代码为准）；`01_principles.md` §3.3/§3.7 等"插件"措辞——指内部扩展层
  （IbPlugin/IbStatefulPlugin 仍在 `core/extension/ibcext.py`），非已删用户插件通道；
  trials REGISTER.md/REVERIFY.md 历史运行记录行。
- **验证**：全量 pytest 零回归（实跑计数不冻结）；D2-21 改写后经 main.py 实跑通过。

**F3-2 遗留（排入 F3-3/F3-4）**：examples/plugins_demo、isolation_demo、trials/T01 等
含 _spec.py 的示例/trials 目录迁移或删除；docs/subsystems/04_plugin_system.md、
docs/howto/write_user_plugin.md、docs/architecture/07_kernel_native_modules.md 插件发现
描述、KNOWN_LIMITS §十九；`_spec.py`/`__ibcext_vtable__`/`discovery` 主题残留扫描
（F3-4）。
