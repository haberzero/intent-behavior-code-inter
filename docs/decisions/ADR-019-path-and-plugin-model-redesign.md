# ADR-019: 路径与插件模型重设计 —— proj_root/plugin_path 分离 + 隔离语义修订

## Status
Accepted (2026-07-13)

**Supersedes**：ADR-018 D1（root 必填 → 引擎级默认 entry_dir）、ADR-018 D5（`_entry_is_tempfile` 标志 → 合成 entry）、ADR-018 的 `CWD ⊇ project_root` 不变量（撤回）。

## Date
2026-07-13

## Context
PT-ARCH-19/20 路径统一推进中（经 5-agent 交叉验证 + 多轮负责人研讨）发现更深的耦合，单纯的"散点 os.path 清理"无法解决：

1. **plugin 发现与 proj_root 绑定**：`ProjectDetector.get_plugin_paths(root)` 从 root 派生 search_paths，使 plugin_path 与沙箱边界耦合。
2. **隔离语义方向争议**：现状 `derive_isolated` 允许子脚本 entry 在父 proj_root 之外（有测试守护），与"沙箱应约束子脚本"的安全直觉冲突。
3. **run_string 无真实 entry**：tempfile 作为 entry_dir 无意义（方案 B 已部分处理，但 entry_file 仍是 tempfile）。
4. **CWD 上界不可行**：ADR-018 的 `CWD ⊇ project_root` 在跨盘启动等场景 UX 代价过高，负责人确认为设计失误。

负责人决策：重设计路径 + 插件模型，而非仅做行为不变的清理。

## Decision

### 1. 五个分离的路径概念

| 概念 | 定义 | 取值 | 时机 |
|------|------|------|------|
| **entry_file / entry_dir** | 入口脚本及其目录 | 真实文件；run_string 用合成路径 | run/compile 时 |
| **project_root**（沙箱边界） | 权限/写入集中点 | 显式 OR entry_dir（引擎级默认） | run/compile 时确立（延迟） |
| **plugin_paths**（特权只读） | 模块/插件发现路径 | 见 §3 优先级 | proj_root 确立后（多阶段） |
| **CWD** | OS 启动上下文 | 单独保存；子可取；**无上界校验** | 构造期 |
| **builtin** | 内置模块（ibci_ai 等） | 恒在，单独存储，不配置、不隔离 | 恒在 |

### 2. project_root（沙箱）

- **引擎级默认**：`project_root = 显式 OR entry_dir`。`IBCIEngine(root_dir=None)` 允许；在 `run()/compile()` 时确立（entry_file 此时才知）。
- **延迟确立**：project_root 延迟到 run() → Scheduler/PermissionManager 构造随之延迟（它们需 project_root 做沙箱）。plugin 发现亦延迟（因 ibci.json 位置依赖 project_root）。引擎单次执行（封印后不复用），故全部在唯一一次 run() 内线性完成。
- **run_string 合成 entry**：无真实 entry_file → 用合成路径 `<project_root>/__string_exec__.ibci`，使 `entry_dir = project_root`（语义自洽，非 tempdir）。
- **CWD 撤回上界**：不再校验 `CWD ⊇ project_root`。CWD 仅单独保存、子脚本可获取；其使用待权限系统设计。
- **ProjectDetector 改用途**：不再用于确立 project_root；仅作 plugin 兜底嗅探（见 §3）。

### 3. plugin_paths（与 project_root 分离）

**取值优先级**（高 → 低，高优先级不可被低优先级同名插件覆盖）：

1. **builtin**（恒在，最高优先级，不可覆盖）
2. **global_plugin**（`ibci.json` 的 `global_plugin` 字段；项目未定义则查全局 ibci.json——**全局查找本轮预留**）
3. **plugin_paths**（`ibci.json` 的 `plugin_paths` 字段，显式，可多个）
4. **嗅探 project_root**（ProjectDetector，仅当 `plugin_paths` **未配置**时触发——explicit > implicit）
5. **全局 config**（**本轮预留，不实现**）

**显式覆盖嗅探**：一旦 `ibci.json` 配置了 `plugin_paths`，ProjectDetector 嗅探不再触发（避免隐式插件混入显式配置）。

**global_plugin 语义**：用户 designated 的"随时可用"插件，**不被普通优先级覆盖**。若同名：builtin > global_plugin > plugin_paths。

**特权只读越界**：plugin_path 可在 project_root 之外（用户显式指定的共享插件库），但：
- 仅**只读**（ibci 脚本不可写入 plugin 所在位置——"不二次越界"即此意）。
- 写入权限集中于 project_root 机制。

### 4. 多阶段启动

```
① 确认 entry_file + project_root（显式 OR entry_dir）
② 定位 ibci.json（与 api_config.json 同目录，即 project_root 下）
③ 按 §3 优先级确定 plugin 处理（builtin + global_plugin + plugin_paths/嗅探）
④ 构造 Scheduler/Permission（需 project_root）+ plugin 发现
⑤ compile → execute
```

`__init__` 瘦身：仅 KernelRegistry + CWD 保存 + builtin 存储；其余延迟到 run() 的多阶段链。

### 5. 隔离语义（反转）

- **子 entry 必须在父 project_root 内**（违反 → 报错）。反转现状的"子可越父 root"。
- **子 project_root** = 显式（policy）OR 子 entry_dir。
- **子默认继承父全部 plugin + 嗅探自己的**（builtin 恒在；global_plugin 继承；plugin_paths 继承 + 子嗅探）。
- **未来**：policy 细粒度继承 + 外部 zone 配置文件（允许特定子脚本读/运行指定外部位置）。

### 6. ibci.json

- **位置**：与 `api_config.json` 同目录（project_root 下）。
- **不与 api_config.json 合并**：后者可能含敏感信息（API key），保持隔离。
- **字段**：`plugin_paths`（数组）、`global_plugin`（数组）+ 未来非敏感项目配置。
- **缺失时**：plugin_paths 空 → 触发嗅探；global_plugin 空 → 查全局 ibci.json（预留）。

## Supersedes 明细

| 被取代项 | 原文位置 | 取代为 |
|---|---|---|
| ADR-018 D1（root 必填、退化 entry_dir） | ADR-018:35-38 | 引擎级默认 `project_root = 显式 OR entry_dir`（可选） |
| ADR-018 D5（`_entry_is_tempfile` 标志分发） | ADR-018:54-57 | 合成 entry `<project_root>/__string_exec__.ibci` |
| ADR-018 `CWD ⊇ project_root` 不变量 | ADR-018:27,35 | 撤回；CWD 仅保存不校验 |
| ADR-018 D4 PathContext 作"唯一锚点容器"穿透 scheduler/resolver/permissions | ADR-018:49-52 | 重构为 §1 五概念模型；PathContext 仍承载 entry_dir+project_root，但 plugin 独立 |

## Consequences

- **engine.__init__ 重构**：瘦身；project_root/plugin 发现/Scheduler/Permission 延迟至 run() 多阶段链。
- **隔离测试失效**（正常）：`test_run_isolated_absolute_path_still_works` 等"子越父 root"场景测试删除/重写。
- **已完成工作处置**：
  - P0-A（SnapshotLayout BUG）：保留，无关。
  - P0-B 测试：canonicalize_for_security / SnapshotLayout 保留；`derive_isolated` 测试需改（隔离反转）。
  - **D1''（root 必填）：回退为可选**；`TestEngineRootDirContract` 改为"默认 = entry_dir"契约。
  - C1/方案 B（run_string entry_dir=project_root）：**方向保留**，entry_file 改合成形态 `__string_exec__.ibci`。
- **解锁** P0-2（存储模型）干净落地。
- **PT-ARCH-19/20 机械清理项**（P0-C~J 散点 os.path 消除）：**并入 ADR-019 实现序列**（这些组件本身要重构，先清理再重构=浪费）。

## Open / Reserved（本轮不实现，设计位留好）

- 全局 ibci.json 查找（global_plugin 的全局源）。
- 全局 config 文件（plugin_paths 的全局兜底）。
- CWD 的实际使用（待权限系统）。
- 隔离的外部 zone 配置（未来 policy 细粒度）。
- plugin_path 的细粒度权限（本轮：只读特权；写入禁；其它待权限系统）。

## 交叉验证发现（2026-07-13，4-subagent 复核；已修或已记录）

**已修（本轮）：**
- ~~Gate A1 实为 1（resolver.py:77 残留 os.path.abspath）~~ → 已迁 IbPath，Gate A1 = 0。
- ~~B1：run()/compile() 对 entry 仅词法 resolve_dot_segments，相对 entry 产出相对 entry_dir~~ → 改 canonicalize_for_security（与 check/project_root 同源）。
- ~~B2：execute() 未经 compile 直调 → AttributeError~~ → 加 root-initialized 守卫，明确 InterpreterError。

**已知限制（记录，非本轮阻断）：**
- **R1（Windows 大小写）**：`PathValidator.is_within` 经字符串 `startswith`，在 win32（大小写不敏感 FS）上对异形大小写路径判定不健全。非 ADR-019 引入（既有），待权限系统统一处理。
- **G1（继承的 global_plugin 优先级扁平化）**：子引擎继承的是父的**已扁平化** search_paths（builtin+global_plugin+plugin_paths+sniff 合并），父的 global_plugin 在子中降至优先级 6（低于子自身 plugin_paths）。若需严格保持 global_plugin 优先级，需父单独传 global_plugin 集合。本轮接受扁平化（§6"继承全部 plugin"的字面达成）；严格优先级留后续。
- **R4（合成 entry 泄露到 isys.entry_path()）**：run_string 下 `isys.entry_path()` 返回 `<proj_root>/__string_exec__.ibci`（非真实文件）。用户可见但无害（与旧 tempfile 行为同属"不可复读"）。
- **R1'（_load_plugins 公理发现面扩大）**：新 `_load_plugins` 用全 search_paths（旧仅 root/plugins）做公理发现——这是**修复**（ibci_modules 下公理旧被忽略），但可能在同名公理场景暴露此前被掩盖的注册冲突。

**测试覆盖缺口（留后续，非阻断）：** plugin 发现仅 list 级测试，未 e2e 验证 `ibci.json` 配置路径的实际 `import` 解析（subagent 2 标 CRITICAL；builtin/sniff 路径由既有 test_plugin_implementations 覆盖，ibci.json 配置路径待补 e2e）。

**可延后机械项（subagent 3）：** project_detector/module_system/ibci_file 的 os.path 多为合法 FS 查询边界；resolver 残留 os.path.join（P0-H，cosmetic）。均下游 canonicalize 兜底，无功能/安全影响。

## 执行序列
见 `docs/NEXT_STEPS.md`（ADR-019 实现序列，分阶段、每步可测）。
