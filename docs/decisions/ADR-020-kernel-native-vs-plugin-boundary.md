# ADR-020: 内核原生 vs 插件边界重划 + FileHandle 磁盘型基类

## Status
**Accepted (设计阶段，2026-07-13)**。实现归属 PT-ARCH-23（含 G1.5/G2/G4-G6）。本 ADR 固化经 8-subagent 交叉验证收敛的设计决策。落地顺序与部分命名（见 Open）待后续研讨。

> **修订（2026-07-17，ADR-021）**：本 ADR G2 的 kernel-native 标记写法原表述为 "`is_user_defined=False` → 恒可解析/不可覆盖"，经 flag 碎片化审计证实与 prelude 过滤器冲突（见 [ADR-021](ADR-021-typed-provenance-visibility-storage-axes.md) §F1）。**修正为：`provenance=KERNEL_NATIVE + visibility=IMPORT_GATED`**——来源与可见性两轴正交落地，本 ADR §A 的原则不变。

## Date
2026-07-13

## Context
ADR-019（路径与插件模型）落地后，交叉分析暴露一个被掩盖的分裂：第一方"插件"实际混了两种本质不同的东西——
- **纯工具**（math/json/time/net/schema）：纯值计算，不碰内核/路径。**真插件**。
- **内核桥**（ai/file/ihost/idbg/isys）：内核能力的脚本化投射，深度内核耦合，却穿"插件"外衣。

负责人决策方向：**内核耦合的东西应是内核原生，不该伪装成插件**；其中 **file 因与未来容器类变量（ADR-016 磁盘型）高度重叠，应内核化为某种核心类，多媒体作为其扩展**。

经 8 个 subagent 从代码现实/分层/存储模型/语言设计/架构原则/迁移/安全多角度交叉分析（结论高度收敛），形成本 ADR。

## Decision

### A. 语法：内核原生模块 = import-gated（非免 import）

**采用 Option 2（始终可 import 的内建模块）**，非 Option 1（免 import 全局）。

**关键拆分（两轴正交）**：
- **kernel-native 管可用性**：恒可解析（绝不"模块未找到"）、不可被用户插件覆盖、内部特权。
- **import 管可见性**：名字是否进入本文件作用域。
- 二者不冲突。"内核原生但 import-gated" 自洽。

**命名 prelude 规则（Rust 式，curated 小集合）**：
- **免 import（prelude）**：仅能力中性原语——`print`/`len`/`range` + 不可缺类型（int/str/list/dict/...）+ `@~` 语法。
- **import-gated**：授能力的命名空间——ai/file/ihost/idbg/isys（各授一独立能力）。判定准则：凡"授一个 sandbox/审计须看见的能力"的命名空间 → 必须 import；凡"移除则破坏可用性基线"的原语 → 免 import。

**理由（多 subagent 收敛）**：
- 安全：`ihost.save_state` by design 绕沙箱（service.py:56-57）；`isys.request_external_access` 全局关沙箱（permissions.py:19-24）。对这几个，**import 是唯一闸门**。免 import = 把"关/绕沙箱"按钮默塞给所有脚本（含不可信 LLM 生成代码）。
- 原则：显式优于隐式 **强制** import-gating；禁止过程式硬编码分发（⛔#4）禁止"部分模块免 import"的判定列表。
- 迁移：Option 2 = 0 脚本/示例/测试/文档破坏；Option 1 ≈ 13 脚本+25 测试串+30 文档站点+编译器/运行时新机制。
- `@~…~` 本就不需 `import ai`（SPEC.md:137，是语法非模块）——免 import 的代码生成便利基本不存在。

### B. FileHandle = 磁盘型基类（内核原生类型），media 为其子类

复用 IBC-Inter **既有的内置类型三角色模式**（str/int/audio 都这么干）：

| 角色 | 职责 | 层 | 注 |
|---|---|---|---|
| **类型契约 axiom** | 身份、方法签名、磁盘协议声明（**零 I/O**） | `core/kernel/axioms/primitives/` | 编译器可见；不 import open/os |
| **值类 value** | 持 `IbPath`+backing、实现磁盘协议（惰性物化） | `core/runtime/objects/` | `@register_ib_type` |
| **原生方法绑定** | 把 open()/read() 绑到 IbClass | `core/runtime/bootstrap/` | `_reg_native`（既有模式） |

**FS-操作悖论的解**：axiom 只声明 `read()->str` 签名（零 I/O）；bootstrap 在运行时绑做真实 open() 的原生函数。axiom 永不 import open/os（同 IbString/IbInteger/IbAudio 现状）。

**media = FileHandle 子类**（非 modality 标签）：ADR-016 §3 强制（协议驱动分发，禁 flag if/else）。`IbAudio/IbImage/IbVideo(IbFileHandle)` 各 override payload 方法。`IbMedia`（未来容器）= **聚合**多 FileHandle，非子类。

**存储模型契合**：FileHandle 是 ADR-016 一直隐含未命名的磁盘型基类（"它是一个 handle"）。一个类型、两种 backing：
- `FileBacking(path, sandboxed)`：可沙箱内或特权只读越界（复用 `allow_external`）。
- `GeneratedBacking(path)`：恒在 project_root 内（溢出目录派生）。

**路径校验**：FileHandle 创建时统一经 `resolve_path` + `canonicalize_for_security`；特权挂在 backing 属性（非另造子类型）。

**ibci_file 插件消亡**：其功能迁入 axiom(kernel)+值类(runtime)+bootstrap 绑定。FS 操作（open/os）落 **runtime 值类的原生方法**（runtime 层合法，ADR-017 §4：FS 查询不入 kernel axiom 但可在 runtime），**不进用户插件目录**——既满足"内核一部分"，又不违反分层。

**揪出的既有违规**：`core/kernel/axioms/primitives/media.py:72-73` 在 kernel axiom 内做 base64（kernel 伸手字节物化，违反 §3.2）——P0-3 重写时移到磁盘协议（运行时惰性物化）。

**命名（已确认 2026-07-13）**：
| 名字类型 | 决定 | 理由 |
|---|---|---|
| Python axiom 文件 | `core/kernel/axioms/primitives/file_handle.py` | 避免 `file.py` 影子化 Python 内建（Py2 `file`），core 层危险 |
| Python 值类文件 | `core/runtime/objects/file_handle.py` | 同上；与 `media_types.py` 同级 |
| IBCI 模块名（`import file`）| **保留 `file`** | IBCI 语言层符号（非 Python 模块），自然，类比 Python `os` |
| IBCI 类型名 | `file_handle`（B 阶段终定） | 容器类型 |

**形态（镜像 Python 的 open()+文件对象模型）**：
```
import file                            # 内核原生模块（free 函数）
file_handle fh = file.open("a.txt")    # open() 创建 FileHandle（持 IbPath，已沙箱校验）
str content = fh.read()                # FileHandle 方法（axiom 声明 + runtime 实现）
```
`file` 模块（free 函数 open/read/write）+ `file_handle` 容器类型（持 IbPath + backing，方法 read/write/close）——容器类与路径体系**直接合一**（FileHandle 本体即 IbPath 引用）。

**澄清："runtime 值类"非"运行时注册"，非折中（2026-07-13 研讨确认）**：
- **"runtime"指代码物理所在目录**（`core/runtime/`），**非注册时机**。类型契约（axiom）、值类实现、bootstrap 绑定**三者全部在 bootstrap（引擎 init，早于任何编译）就位**——与 `str`/`int`/`audio` 现状完全一致（`IbString` 在 `runtime/objects/builtins/strings.py`，但 `str.len()` 编译期类型检查照常工作）。
- **编译期检查靠 axiom 签名**（kernel 层，bootstrap 注册，编译器可见），不依赖值类实现。值类（runtime）只是实现归宿，绑定时点也是 bootstrap。
- **分置（类型在 kernel / I/O 实现在 runtime）是分层原则对所有内置类型的强制要求**（ADR-017 §3.2：kernel 必须 I/O-free），非 file 特例、非折中。file 仍是内核原生（非用户插件）、编译期检查完整、路径绑定保留——三者无让步。

### C. bootstrap 升级（针对性，非重设计）

bootstrap 能吸收内核原生模块，需三处升级：
1. **内核原生注册 API**：桥接 axiom-spec 与 _spec.py vtable（见 D）。
2. **懒查找契约**：注册时只捕获 `kernel_registry`，钩子（llm_executor/host_service/stack_inspector）延迟到调用时取（ihost/idbg 现状）——绕开"钩子在 STAGE_7、seal_classes 之后才注入"的时序死锁。
3. **late-hydrate 生命周期钩子**：在 `_prepare_interpreter` 附近，给有状态内核原生模块（ai）setup/hydrate 窗口。

**零破坏迁移路径**（关键发现）：loader 已有短路（loader.py:156-168）处理"预注册实现"。**bootstrap 预注册 5 模块进 HostInterface → 发现机制 no-op → loader 经短路拾取**——零文件移动、零测试破坏。

### D. 注册协议：双路径保留（粒度正交），立决策规则

**两路径都保留**——粒度正交，非冗余：
- **axiom-spec**：你**持有并调用方法**的**类型**（`str.len()`、`fh.read()`）。
- **_spec.py vtable**：你**import 并调用自由函数**的**模块**（`ai.complete()`）。

单点真理 = **每粒度一条路径**，非"所有东西一条路径"。强行合并违反"公理为唯一真源"。

**决策规则**：
- FileHandle（值类型，持方法）→ **axiom-spec**，bootstrap seal 注册（因此必然 kernel-native）。
- ai/ihost/idbg/isys（import 的能力模块）→ **_spec.py vtable 保留**，只把"文件系统发现"换"bootstrap 直接注册"。

**真正的债**：axiom 路径的**硬编码回退列表**（builtin_initializer.py:98）应从 `AxiomRegistry.get_all_names()` 派生，无硬编码特例。

### E. "builtin" 概念：作为独立名词删除（一词五义 = 单点真理违规）

精确化：
| 新术语 | 指 |
|---|---|
| **language primitive** | int/str/print/len（是语言本身） |
| **kernel-native module** | ai/file/ihost/idbg/isys（随内核发行、恒在、不可覆盖） |
| **plugin** | 用户/第三方（plugin_paths/global_plugin/嗅探） |
| **first-party** | 统称 = primitive + kernel-native |

替换：`BuiltinPaths`→`InstallPaths`；`builtin_initializer.py`→`primitive_initializer.py`；`is_builtin`→`is_intrinsic`；ADR-019 §1 "builtin 恒在"→"kernel-native 恒在"。

### 迁移策略
顺序化干净切口（ADR-019 的 A/B/C/D 先例）；**禁** feature-flag、**禁** 新旧命名空间共存（皆 compat shim，违 ⛔#1）。每阶段完整测试重写。

## 与其它 ADR 关系
- **协同**：ADR-016（存储模型——FileHandle 是其磁盘型基类的落地）、ADR-014（media 磁盘型 handle——改为 FileHandle 子类）。
- **承接**：ADR-019（路径机制——FileHandle 持 IbPath，创建经 resolve_path 沙箱）。
- **不冲突**：ADR-017（分层——FileHandle 复用既有 axiom/kernel + value/runtime + binding/bootstrap 三角色）。

## Open / 待研讨（未定，不阻塞文档）

1. ~~`file.py` 命名隐患~~ → **已确认（见 B 命名表）**：Python 文件用 `file_handle.py`，IBCI 模块名保留 `file`。
2. ~~ai/ihost/idbg/isys reclassification 时机~~ → **已确认（负责人 2026-07-13）**：**所有核心模块内核迁移同步执行，同一里程碑内完成**（PT-ARCH-23，见 PENDING_TASKS）。不分子批。
3. ~~落地顺序~~ → **已认可**：E→A→C→D→B（按里程碑内依赖自主微调）。
4. **FileHandle 具体 API**：**延后**到真正实现容器类/文件类时细化（`file` 模块 free 函数 + `file_handle` 方法清单 + resolve_path 接合点 + 媒体子类 override）。
5. ~~`file` 是否部分免 import~~ → **已确认**：**file 相关模块全 import-gated**（保 manifest 清晰；file 授沙箱相关能力，按 A 的 prelude 规则必须 import）。
6. **全项目命名清理（PT-ARCH-22）**：暂缓，已排期入 PENDING_TASKS，待 PT-ARCH-23 后或独立窗口执行。

## 里程碑归属（已确认）
本 ADR 的实现归属 **PT-ARCH-23**（与 P0-2/P0-3 强耦合，协同设计为一个里程碑）。依赖序与任务分配见 `PENDING_TASKS §PT-ARCH-23`。

## Consequences
- "核心层插件"这个自相矛盾的中间态消除：内核耦合=内核原生，工具=插件。
- 路径集中管理范围清晰：内核内部一致性（file/isys 皆内核）。
- 插件系统回归"可选纯工具"本义；用户插件受信不管路径（ADR-019 结论成立）。
- 影响面：bootstrap 改造、ibci_file 消亡、media 改 FileHandle 子类、术语全仓替换——大重构，分阶段。
