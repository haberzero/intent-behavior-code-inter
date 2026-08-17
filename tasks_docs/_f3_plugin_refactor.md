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
