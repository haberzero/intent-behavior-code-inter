# NEXT_STEPS — 当前最紧要项

> 本文档**只**记录当前周期内最紧要、可立即开工的下一步。
> 阻塞 / 等前置项见 `docs/PENDING_TASKS.md`；历史归档见 `docs/COMPLETED.md`。
> 已知语言级限制见 `docs/KNOWN_LIMITS.md`。
>
> **最后更新**：2026-07-13（**ADR-019 立项**：路径与插件模型重设计——proj_root/plugin_path 分离 + 隔离反转 + 多阶段启动。经 5-agent 交叉验证 + 多轮研讨确认"路径统一"实为模型重设计。取代 ADR-018 的 D1/D5/CWD 上界。原 PT-ARCH-19/20 机械清理并入 ADR-019 阶段 D。D1''/C1 已完成部分需回退/改造。）

---

## ⛔ 工作模式定论（强制，凌驾于本文件一切任务之上）

经 2026-06-25 三轮架构审计，项目负责人确认以下工作模式为**不可违反的强制原则**：

> **扎实推进，禁止任何形式的快速实现 / 兼容层 / 胶水实现 / tricky 实现。**

具体含义：

1. **禁止 compat shim / 兼容层**：不写"过渡性包装"。新设计就是真设计，旧代码要么真合并、要么真删除，不存在"包一层先跑通"。
2. **禁止胶水实现**：不在两个不统一的子系统之间塞字符串拼接 / 魔法哨兵 / 隐式约定来强行粘合（典型反例：`HostService.save_state` 的 `.assets/` 字符串拼接 + `"__EXTERNAL_FILE_REF__"` 哨兵）。
3. **禁止 tricky 实现**：不靠 `replace(os.sep, '.')` 这类隐式字符串变换承载语义；不靠"凑巧相等"（如 `type(val) is X` 严格身份判定覆盖子类）；不靠书写顺序的便利掩盖数据依赖。
4. **禁止过程式硬编码分发**：同一决策只通过协议驱动（`receive()` / vtable）完成，不在运行流程里写 `if 能力标志位` 分支（详见 ADR-016 第 3 条）。
5. **质量优先于速度**：任何"先出成果再还债"的提议都被本原则否决。检测到的技术债必须先清，再推进依赖它的特性。**潜伏 bug 不允许过渡/简易修复**——必须在依赖它的架构完善后统一修复。

本原则的执行机制见下文"P0 阶段序列"——media 特性被显式 gate 在前置架构完成之后。

---

## 当前测试基线（每次开新分支前必须复跑确认）

```bash
python -m pytest tests/ -q --tb=no --no-header
```

**2026-07-13 实测结果**：`1135 passed, 7 skipped`（0 failures/errors，win32 / PowerShell，junitxml 捕获）

> **基线说明**：ADR-019 阶段 A/B/C/D 全部完成 + 4-subagent 交叉验证修复（B1 相对 entry canonicalize、B2 execute 守卫、Gate A1 resolver 迁移）。已知限制与覆盖缺口见 ADR-019 "交叉验证发现"段。
> ⚠️ **基线锚点警示**：当前为**未提交 WIP**。从干净 `git checkout HEAD` 复跑将得到旧基线。
> ✅ 7 个 skipped：2 设计限制 + 3 层级元测试 + 1 win32 symlink + 1（无新增预期删除）。

---

## P0 阶段序列（media Phase 4 的前置 gate）

> **核心约束**：在以下阶段全部完成前，**不得**开始 media Phase 4 的实现工作（ADR-014/016 明确 gate）。
> 同一时刻只主推一个阶段；每个阶段完成后把摘要追加到 `docs/COMPLETED.md` 并从本文件移除。

### ✅ 阶段 0（已完成）：三轮架构审计 + 治理决策固化

> 详见 `docs/COMPLETED.md` 2026-06-25 三轮条目。
> 产出：ADR-013（修订）/014（修订）/015/016；潜伏 bug 处置决策；路径碎片化 Fragmentation Map；协议驱动分发框架。

---

### 🔴 [重设计] PT-ARCH-21：路径与插件模型重设计（ADR-019，最高优先级）

> **2026-07-13 决策**：经 5-agent 交叉验证 + 多轮研讨，确认"路径统一"实为更深的**模型重设计**。立 [ADR-019](decisions/ADR-019-path-and-plugin-model-redesign.md) 为正本。
> **ADR-019 取代** ADR-018 的 D1（root 必填→引擎级默认）、D5（标志→合成 entry）、CWD 上界不变量（撤回）、D4 PathContext 穿透（→五概念模型）。
> **原 PT-ARCH-19/20 的机械清理项**（P0-C~J 散点 os.path 消除）**并入本重设计的实现序列**——因相关组件本身要重构，先清理再重构=浪费。
> **设计要点**：① proj_root/plugin_path 分离；② project_root 引擎级默认（=显式 OR entry_dir）；③ run_string 合成 entry `<proj_root>/__string_exec__.ibci`；④ plugin 优先级 builtin > global_plugin > plugin_paths > 嗅探 > 全局(预留)；⑤ 隔离反转（子必须在父 proj_root 内）；⑥ plugin 只读特权；⑦ CWD 仅保存不校验；⑧ ibci.json 配置（不与 api_config 合并）。

**本轮已完成（保留）**：
- ✅ P0-A：SnapshotLayout BUG 修复（无关重设计，保留）。
- ✅ P0-B：3 新能力测试（canonicalize / SnapshotLayout 保留；derive_isolated 待随隔离反转改）。
- ✅ D2：project_root 经 canonicalize_for_security 规范化（保留，ADR-019 §2 沿用）。

**本轮已完成但需回退/改造**：
- ⚠️ D1''（root 必填）→ 回退为**可选**（引擎级默认 entry_dir，ADR-019 §2）。`TestEngineRootDirContract` 改契约。
- ⚠️ C1/方案 B（run_string entry_dir=project_root）→ 方向保留，entry_file 改**合成 `__string_exec__.ibci`**（ADR-019 §2）。

**ADR-019 实现序列（分阶段、每步配测试）**：

**阶段 A：路径模型核心** ✅（2026-07-13 完成，1110 passed / 0 fail）
1. **A1** ✅：root_dir 改可选；project_root 延迟到 run/compile 确立（= 显式 OR entry_dir，`_establish_project_root`）。
2. **A2** ✅：Scheduler/PermissionManager 构造延迟到 run()（`_ensure_root_initialized`，幂等）。
3. **A3** ✅：run_string 合成 entry `<project_root>/__string_exec__.ibci`（entry_dir=project_root，非 tempdir）。
4. **A4** ✅：CWD 单独保存（`engine._cwd`，构造期），无上界校验。
5. **A5** ✅：project_root/entry 规范化统一走 canonicalize_for_security（D2 延伸到 check/entry）。

**阶段 B：插件系统分离** ✅（2026-07-13 完成，1132 passed / 0 fail）
6. **B1** ✅：`core/kernel/config.py` IbciConfig 加载 ibci.json（plugin_paths / global_plugin 字段；位置 = project_root 下，不与 api_config 合并）。
7. **B2** ✅：plugin 发现优先级实现（builtin > global_plugin > plugin_paths > 嗅探 > 全局[预留]）——`_resolve_plugin_search_paths`。
8. **B3** ✅：ProjectDetector 改兜底嗅探（仅 plugin_paths 未配置时触发）。
9. **B4** ✅：plugin_path 只读特权——resolver 允许越界（写入仍由 proj_root 沙箱约束，loader 级特权读）。
10. **B5** ✅：全局 ibci.json / 全局 config **预留接口，不实现**（resolver 留注释位）。

**阶段 C：隔离语义修订** ✅（2026-07-13 完成，1133 passed / 0 fail）
11. **C1** ✅：`_validate_and_derive_isolated`——子 entry 必须在父 project_root 内（canonicalize + is_within 校验，违反报错）。隔离调用前确保父 root 已延迟初始化。
12. **C2** ✅：子引擎经 `inherited_plugin_paths` 继承父 plugin search_paths（resolver 附加为兜底来源，去重保序）。
13. **C3** ✅：删除过期测试 `test_run_isolated_absolute_path_still_works`（旧"子可越父 root"语义），替换为 `test_run_isolated_child_outside_parent_root_now_rejected`（守护反转）。`derive_isolated` docstring 订正（派生与策略分离）。

**阶段 D：机械清理** ✅（2026-07-13 完成，1133 passed / 0 fail）— 门槛关键项已清
14. **D1** ✅：scheduler.py:127 `os.path.abspath`→`canonicalize_for_security`；:97 `os.path.join`→`IbPath /`。compiler 层零散点 `os.path.abspath`（门槛 A = 0）。
15. **D2** ✅：移除 scheduler/resolver/permissions 的 **3 处 root 冗余 canonicalize**（信任 engine 传入），字段 `_root_ib`/`_root_path`→`_project_root`（仅 IbPath 包装）。**保留** 9 处文件路径 canonicalize（is_within 前防 symlink 逃逸，安全必需）。
16. **D3** ✅：死 import 清理——permissions/execution_context/module_manager/interpreter/meta 的 `import os` + scheduler/permissions 死 `IbPath` + module_manager 死 `root_dir` 字段（含调用方 interpreter.py:243）。
17. **D4（部分，待交叉检验定夺）**：`ibci_file/core.py`（用户可见）+ `project_detector.py`/`module_system`（多为合法 FS 查询边界）——非门槛阻塞，留待 subagent 评估是否本轮必修。

**机械门槛校验（实测通过）**：
```bash
rg -n 'os\.path\.(abspath|getcwd)\(' core/compiler/ core/base/   # 0（实测）
rg -n 'from core\.runtime' core/compiler/ core/base/             # 0（实测）
rg -n 'canonicalize_for_security' core/compiler/scheduler.py core/compiler/parser/resolver/resolver.py core/runtime/interpreter/permissions.py  # 仅余文件路径 canonicalize（安全必需），root 冗余已清
rg -n '^import os' core/runtime/interpreter/permissions.py core/runtime/interpreter/execution_context.py core/runtime/interpreter/module_manager.py core/runtime/interpreter/interpreter.py core/runtime/interpreter/intrinsics/meta.py  # 0（实测）
```

**关键交接点**：ADR-019 是正本；逐文件:行清单演进到 `PENDING_TASKS.md §九`（重写为 ADR-019 任务）。

---

### [历史] PT-ARCH-19 + PT-ARCH-20（路径统一，已被 ADR-019 吸收）

> 原最高优先级，2026-07-13 经多轮研讨确认实为模型重设计，**整体并入 ADR-019 / PT-ARCH-21**。其已完成的部分（P0-A/B、D2）保留；机械清理项（P0-C~J）转入 ADR-019 阶段 D。详见 ADR-019 Supersedes 明细。隔离侧（概念 4/5 健康部分）ADR-019 沿用。

---

### P0-2（后置）：变量存储模型基础设施（ADR-016）

> 确立 memory-backed / disk-backed 类型级区分 + 协议驱动分发框架。详见 `docs/PENDING_TASKS.md §九 PT-ARCH-17`。

**待做**：
1. 在 axiom/spec 体系引入 `storage_model` 类型级属性（取值 memory-backed / disk-backed）。
2. 确立**磁盘型协议族**（与 `__prompt__` 平行）的具体方法名与签名（设计期决定）；内存型继续走既有 `__prompt__` 族，语义不变。
3. 改造 `deep_clone.py`：按存储模型分发——磁盘型对象拷贝路径引用（浅、廉价），不再"深拷贝字节"。**此处一并完成 `deep_clone.py:89` 的 `type(val) is` → `isinstance` 修复**（ADR-007 未竟部分）。
4. 改造序列化器：增加磁盘型分支——序列化路径引用，不再"序列化字节"。**此处一并补 `BaseFlatSerializer` 的 `bytes` / 路径处理能力**。
5. 改造响应解析分发（ADR-013 修订版）：`AxiomParsingStrategy` 通过 `receive()` 委托给目标类型的协议方法，不写 `if/else`。
6. 全程**协议驱动**——executor/strategy/deep_clone/序列化器存储模型无关。

**验证策略**：内存型路径字节级不变（全量 pytest 0 failure）；新增"磁盘型分发不命中内存型协议"守护测试。
**预估工作量**：~2-3 天

---

### P0-3：media 重建为磁盘型 + 潜伏 bug 统一修复（ADR-014）

> 整体淘汰 `MediaStorage`；潜伏 bug 在此随模型切换统一消解。详见 `docs/PENDING_TASKS.md §九 PT-ARCH-18`。

**待做**：
1. 新建 `MediaBacking` 抽象 + `FileBacking` / `GeneratedBacking`（均持 `IbPath`，无 MemoryBacking）。
2. 重写 `IbAudio`/`IbImage`/`IbVideo` 为磁盘型 handle（替换 `media_types.py`）。
3. 删除 `media_storage.py`（字节持有者，整体淘汰）；替换其单测为 handle 契约测试。
4. 改 `axioms/primitives/media.py`：`__payload_prompt__` 从 backing 惰性物化字节。
5. 改 `ibci_file.read_*`：返回 `FileBacking(resolved_path)`，**不立即读字节**（零拷贝）。
6. **潜伏 bug 随之统一修复**：PT-ARCH-12（`deep_clone` 静默跳过 media）+ PT-ARCH-13（序列化器丢字节）在 P0-2 的存储模型分发落地后，因 media 不再持有进程内字节而**自然消解**——按项目负责人指令，不允许先行过渡修复。

**验证策略**：MOCK 模式 e2e（`file.read_audio` → handle → `@~ $x ~`）端到端跑通；snapshot/serialize round-trip 守护测试（暴露过潜伏 bug）。
**预估工作量**：~2-3 天

---

## GATED：media Phase 4 — MediaAxiom + IbMedia 全模态容器（仅在 P0-1/2/3 全部完成后开工）

> **阻塞条件**：P0-1（路径统一）+ P0-2（存储模型架构）+ P0-3（media 重建）全部完成。
> 在此之前不得写任何 media 容器代码（ADR-014/016 明确阻塞）。

解锁后的工作（届时提升为本文件 P0）：
1. **`MediaAxiom` + 协议驱动的响应解析**：解析多模态响应为 media 对象（接入 P0-2 的协议驱动分发，**非 `if/else`**）。
2. **`IbMedia` 全模态组合容器**：modality→payload 映射 + 固定访问器（`.text/.audio/.image/.video`）语法糖，为未来元组解包留结构性扩展位。
3. **MOCK 模式扩展**：`MOCK:MEDIA:` 合成响应（用户确认了暂缓，届时再议）。

**明确剥离到独立后续**（不纳入主线，但结构上不堵死）：
- 元组解包 `(str t, audio a) = @~...~`（D5）——需 TypeCheckingPass 解包推断 + CPS 多返回值；`IbMedia` 的 modality 映射为此预留接入位。

---

## 确认为设计决策（不修复）

| 测试 ID | 原因 | 处理 |
|---------|------|------|
| **INV-LAMBDA-3** | IBCI 无 walrus (`:=`) / lambda 体赋值语法 | 保持 SKIP，标注为"设计限制" |
| **INV-SCOPE-1** | SEM_002 禁止 if-block 内重声明同名变量 | 保持 SKIP，标注为"设计限制" |

---

## 工作规则

- **每次开新分支前**，先复跑 `python -m pytest tests/ -q --tb=no --no-header`，把当前 pass/fail 计数写在 PR 描述里。
- **跨盘环境注意**：`conftest.py` 的 `pytest_configure` 已将 basetemp 设为 repo 下 `.tmp_pytest`，无需手动设置环境变量。
- **同一时刻只主推一个 P0 阶段**；其余项保留待选。
- **工作模式定论优先**：任何与"⛔ 工作模式定论"冲突的提议（含本文件历史里的"先跑通再还债"暗示）一律以定论为准。
- 任何改动公理层公约或语义错误集的任务，需在分支早期跑全量 pytest 评估破坏面。
- 每个阶段完成后，把摘要追加到 `docs/COMPLETED.md`，并把对应条目从本文件移除。
- **本文件不冻结具体测试通过数字**——任何"X 测试通过"的表述都必须附运行命令或日期锚点。

---

## 维护守则

1. **先复跑、后下结论**。任何关于"测试基线红线"的表述，必须以"附完整 pytest 输出 + 日期 + 分支 + 环境条件"的方式说服读者。
2. **不要相信"昨日完成"的总结**。`docs/COMPLETED.md` 的最新一两条锚点，必须能用一条具体 git 提交或一次具体 pytest 输出佐证。
3. **示例必须可零配置跑通**。任何"用户跟着 README 复制粘贴"的代码块，必须在 mock 模式下端到端跑通。
4. **已知 bug 与已修 bug 之间要勤更**。
5. **跨文件状态保持一致**。`README.md`、`docs/KNOWN_LIMITS.md`、`docs/IBCI_SYNTAX_REFERENCE.md`、`docs/METADATA_ARCHITECTURE.md` 之间对同一语法/限制/架构立场的描述必须用同一组事实。
6. **避免重复声明、单点真理**。一条已完成项写一次（在 `COMPLETED.md`），一条已知限制写一次（在 `KNOWN_LIMITS.md`），一条紧要项写一次（在 `NEXT_STEPS.md`），一条搁置项写一次（在 `PENDING_TASKS.md`）。
7. **新增 AST 字段或侧表前必须先在 `METADATA_ARCHITECTURE.md` 中查证**。
8. **重大架构决策必须写 ADR**。新增决策在 `docs/decisions/` 建对应 ADR 文件；被取代/修订的 ADR 必须在自身 Status 行标注（见 ADR-009 supersede、ADR-013/014 修订记录）。
9. **"Inter 层"命名已废弃**（ADR-016）。文档接触时改写为"变量存储模型"或具体协议族名。
