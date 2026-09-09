# P6 内核自举：内核契约 bind 化 —— Phase 0 实证裁定与设计

> 定位：VISION-6 内核工程化 P6（bind 表达内核契约，自举台阶 ④ 之后方向）的 Phase 0
> 交付——**实证裁定 bind 化的具体范围** + **设计确认**（对照 9 项 VM 设计不变量
> `docs/architecture/04_vm_interpreter.md` §11 + 工作模式定论九条）+ **分阶段批次
> 计划**。Phase 0 结论：bind 化范围 = 工具 4（math/json/time/schema）契约 + net
> 契约源（实现绑定保留 per-engine 实例）；kernel 5 + fs 维持宿主侧。
>
> 历史输入：F5 评估（2026-08-18，WORKLOG F5 决策记录）曾把"内置契约再表达为 bind
> 声明"整体列为远期 pending（"bind 为运行时用户侧机制，与内核构造期需求时序矛盾"）。
> 本设计对该裁定做**精化而非推翻**（user-principles：原则与机制分开评估——F5 的
> 时序矛盾裁定对 kernel 5+fs 仍然成立，对工具 5 的纯声明面不成立）。

---

## 一、实证基础（本 session 调查事实，逐项有代码/测试证据）

### 1.1 内核契约面现状（`core/runtime/bootstrap/builtin_modules.py`，850 行）

构造期一次性注册全部 11 个内置模块（`register_builtin_modules`，engine.py:146-147
于 `__init__` 执行）：

| 模块 | provenance | 实现形态 | 生命周期/通道语义 | exported_types |
|------|-----------|---------|------------------|----------------|
| ai | KERNEL_NATIVE | ibci_ai 包工厂实例 | **LLM 通道（不变量 #4：全部 LLM 调用经 KernelRegistry.get_llm_executor）** + capability 槽（provider 注册，F4 bind-based provider 为用户扩展注入通道）+ journal/budget 接线 | — |
| ihost | KERNEL_NATIVE | ibci_ihost 包工厂实例 | **引擎内部服务**：run_file/run_code 经 IInterpreterFactory spawn 隔离子引擎（父上下文/继承快照） | — |
| meta | KERNEL_NATIVE | ibci_meta 包工厂实例 | 子引擎 compile-only（编译门） | — |
| idbg / isys / iruntime | KERNEL_NATIVE | ibci_* 包工厂实例 | 内核内省/调试/系统服务（registry 绑定） | — |
| fs | KERNEL_NATIVE | core.runtime.modules.fs_impl.FileLib（无物理包） | 沙箱策略（PathContext/权限系统） | **file_handle/audio/image/video（内核值类型）** |
| math / json / time / schema | USER_DEFINED | ibci_* 包工厂实例（MathLib 等类，**无状态**） | **纯 callable 面，无 setup 钩子**（`_setup_implementation` 经 hasattr 跳过） | 无 |
| net | USER_DEFINED | ibci_net 包工厂实例（NetLib，**有状态**：`_timeout`/`_default_headers`，set_timeout/set_default_headers/set_auth 为跨调用持久配置） | per-engine 可变状态（多引擎隔离：子引擎 net 状态独立） | 无 |

**关键事实**：
- 工具 5 无 setup/lifecycle 钩子（grep 实证：五个 core.py 零 `def setup`）——契约面
  = 纯声明（成员名 + 签名 + 类型），无构造期行为。
- 工具 5 无 exported_types（仅 fs 有）——契约面无内核值类型。
- 工具 5 实现 = 类实例方法（工厂 `create_implementation()` per-engine 构造）；
  `ibci_modules` 包不暴露模块级函数（F3 探针 A1 同结论：bind 模块成员路径需模块级
  函数）。
- 内置模块 spec 字面量（TypeDef）= **实现签名的手写重复知识**（每成员 param_types /
  return_type 与实现 Python 签名双写，人工维护）。

### 1.2 bind 机制（`docs/architecture/01_native_host_binding.md`）的表达力与边界

**可表达**：
- `import python "pkg" as name: bind member(params) -> ret` / `bind attr -> type` /
  `bind class Name: ...` —— 成员契约（签名 + IBCI 类型）显式声明；
- 编译期：`parse_host_import`（import_def.py:37）→ `_inject_host_import`
  （scheduler.py:654）合成 ModuleMetadata（= TypeDef 别名，provenance=
  EXTERNAL_MODULE，**visibility 缺省 IMPORT_GATED**（base.py:146）——门控语义与内置
  一致）注入符号表（本模块内类型检查）；宿主 import 跳过 IBCI 依赖图；
- 运行期（用户侧）：STAGE 5 预注册 `_hydrate_host_classes` + VM
  `vm_handle_IbHostImport` → `module_manager.import_host_module`（importlib + 按 bind
  构建 vtable/whitelist + create_native_object + create_module）。
- provenance 消费点实证：USER_DEFINED 与 EXTERNAL_MODULE 在编译器侧行为等价
  （`_declaration_visitors.py:93` impl 目标两者并列放行；依赖扫描对 external 模块统一
  跳过；覆盖保护仅 KERNEL_NATIVE 触发——工具 5 现为 USER_DEFINED 本就不受保护）。

**不可表达**：
- 构造期 lifecycle（setup/teardown/capability 槽/registry 通道接线）——bind 是
  声明 + 运行期 importlib 机制，无构造期钩子面；
- 内核值类型（带 vtable 语义的一等类型，如 file_handle）——`bind class` 绑定的是
  裸 Python 类（EXTERNAL_MODULE），非内核值类型注册通道；
- 引擎内部服务（spawn/子引擎/沙箱策略）——实现须绑定 Engine 实例/registry，非
  importlib 裸模块成员。

### 1.3 引擎启动时序（core/engine.py）

```
__init__（构造期，root-independent）
  ├─ KernelRegistry + 原语类（int/str/float/bool/void/any + 核心值类）
  ├─ CapabilityRegistry
  ├─ HostInterface（external_registry = 共享 metadata registry）
  ├─ register_builtin_modules        ← 内置模块 spec + 实现注册（当前：字面量 + 工厂）
  └─ （延迟）Scheduler / module_loader
run/compile → _ensure_root_initialized（Scheduler 确立）
执行准备 → _load_plugins（STAGE 4→5）
  └─ module_loader.load_and_register_all
     └─ 遍历 metadata registry 全部模块：有实现者严格契约绑定
        （_validate_and_bind → vtable/whitelist → interop.bind_native_contract）
        + setup 注入（无 setup 者跳过）
运行期 import math → module_manager.import_module
  └─ InterOp.get_package（HostInterface 实现）+ get_native_contract（绑定期产物）
```

**关键事实**：
- 编译器可见性 = 共享 metadata registry（构造期注册即可见，先于一切用户编译）；
- 运行期绑定 = STAGE 4→5 的**单一 loader 循环**，对"registry 中有 spec + HostInterface
  中有实现"的任意模块自动严格绑定（loader 文档明确实现来源 = 构造期内置 / host 绑定 /
  测试手动注册）；
- `_validate_and_bind`（loader.py:34）**完全泛型**：对任意实现对象按 spec 声明成员
  getattr + callable + 签名校验（禁止隐式反射，成员缺声明即错）——类实例与模块对象
  同适用；
- registry 隔离守卫（`_BOUND_IMPLEMENTATIONS`）：同一实现对象**不可**绑定两个引擎
  （多引擎进程：ihost 子引擎与父引擎同进程）——实现对象必须 per-engine 身份。

### 1.4 机制同构（built-in 通道 vs bind 通道）

| 环节 | built-in 通道（当前） | bind 通道（用户侧） | 同构点 |
|------|---------------------|-------------------|--------|
| 契约描述 | Python TypeDef 字面量 | IBCI bind 声明 | 皆显式成员 + 签名 |
| spec 合成 | 字面量直接注册 | `_inject_host_import` 从声明合成 | **可收敛为单一合成函数** |
| 实现来源 | 工厂 per-engine 实例 | importlib 模块（模块级成员） | 皆 per-engine 身份对象 |
| 绑定 | `_validate_and_bind`（STAGE 4→5） | 同（STAGE 4→5，registry 有 spec 即绑定） | **同一机制，零新运行期机制** |
| 运行期消费 | InterOp.get_package + get_native_contract | 同 | **同一机制** |
| provenance | KERNEL_NATIVE / USER_DEFINED | EXTERNAL_MODULE | 工具 5 行为等价（§1.2 实证） |

**结论**：bind 化 = 把工具 5 的**契约描述源**从 Python 字面量换为 IBCI bind 声明源，
bootstrap 期经既有通道（parser → spec 合成 → register_module）注册；运行期绑定与消费
机制**完全复用**（loader 循环自动覆盖）。

### 1.5 F5 时序矛盾的实证再裁定

F5（2026-08-18）："bind 为运行时用户侧机制，与内核构造期需求时序矛盾"。

- **对 kernel 5 + fs：成立**。其契约面含构造期 lifecycle（capability 槽/registry
  通道/沙箱策略）与引擎内部服务（spawn/compile-only）——bind 机制（声明 + 运行期
  importlib）无对应表达面；强行 bind 化 = 为构造期语义发明运行期机制（tricky，违反
  工作模式定论 #3）。
- **对工具 5：不成立**。其契约面 = 纯声明（成员 + 签名，§1.1 实证无 lifecycle、无
  exported_types）——bootstrap 期处理声明源（parser + 合成 + 注册）发生在构造期，
  无时序矛盾；运行期绑定经既有 STAGE 4→5 loader（§1.3 实证自动覆盖）。
- **裁定**：F5 结论对 kernel 5+fs 维持（保持 builtin_modules.py 字面量为单一权威源）；
  对工具 5 **精化**（单一权威源 = IBCI bind 声明契约源 + bootstrap 处理通道）。非推翻
  ——F5 的时序分析未区分"纯声明契约"与"含 lifecycle 契约"两类面。

---

## 二、裁定（bind 化范围）

| 模块 | 裁定 | 依据 |
|------|------|------|
| math / json / time / schema | **bind 化（完整通道）**：契约源 = IBCI bind 声明（单一权威源）；实现 = 模块级函数 + per-engine 身份命名空间；绑定 = 既有 `_validate_and_bind` | §1.1 纯声明面无 lifecycle；§1.4 机制同构零新运行期机制；**B2 实施期实证：4 工具契约零默认参数**（bind 无默认值语法无表达缺口） |
| net | **维持宿主侧**（builtin_modules.py 字面量，USER_DEFINED）——**B3 取消** | **B2 实施期实证精化**：net 8 个方法（get/get_json/post/post_json/post_form/put/delete/head）的 `headers` 参数带 `has_default=True, default_value=None`（字面量 descriptors）——bind 声明无默认值语法（F3-0 裁定"默认值放 .ibci 包装层"未推翻），契约源化将丢失 has_default 面 → `net.get(url)`（省略 headers）用户面调用语义回归。per-engine 可变状态（§1.1）同属本质差异。双重边界 → net 维持宿主侧字面量 |
| ai / ihost / meta / idbg / isys / iruntime / fs | **维持宿主侧**（builtin_modules.py 字面量） | §1.5 时序矛盾成立：lifecycle / 不变量 #4 LLM 通道 / 引擎内部服务 / 内核值类型导出——bind 机制无对应表达面 |

**单一权威源收敛**：工具 5 契约 = 5 份 IBCI 契约源文件（per-module）；kernel 5+fs
契约 = builtin_modules.py 字面量（不变）。两类契约两个权威源，各域单一——非双写真相
（每份契约知识只在一处维护；工具 5 的字面量真删除，不保留影子）。

---

## 三、设计（bootstrap 契约通道）

### 3.1 契约源文件

- 位置：`core/runtime/bootstrap/contracts/<module>.ibci`（kernel 源码域，与实现包
  `ibci_modules/` 分离——契约与实现分居是 F3 已确立的形态，本设计只改契约描述源）。
- 形态（每文件 = 单一 host import 声明，模块名 = 用户面 import 名）：

```ibci
# contracts/math.ibci —— 数学函数内核契约（bind 表达）
import python "ibci_modules.math" as math:
    bind sqrt(x: float) -> float
    bind pow(x: float, y: float) -> float
    ...
```

- 单一权威源：成员名/签名/类型只在此声明；实现包不得另维护签名文档（drift 由
  `_validate_and_bind` 构造/绑定期 fail-fast 拦截）。

### 3.2 bootstrap 阶段（engine.__init__，替代工具 5 的当前注册路径）

```
对每个契约源文件：
  1. tokenize + parse（既有 Parser，声明域文件——零执行语义，编译产物不需要）
  2. 提取 IbHostImport 节点 → 共享合成函数（§3.3）→ TypeDef spec
     （provenance=EXTERNAL_MODULE，visibility 缺省 IMPORT_GATED——与工具 5 现语义一致）
  3. 构造 per-engine 实现对象：
     - 工具 4：模块级函数命名空间（§3.4）
     - net：现有 create_implementation() 实例（不变）
  4. host_interface.register_module(name, impl, metadata=spec)
STAGE 4→5（既有 loader 循环，零改动）：
  _validate_and_bind（spec ↔ 实现严格校验 + vtable/whitelist）→ bind_native_contract
```

- **零新运行期机制**：步骤 1-2 为构造期声明处理（parser + 合成）；步骤 3-4 与既有
  注册同形；绑定/消费 = 既有 loader + InterOp 路径。
- **fail-fast**：契约源解析/合成失败 = 构造期异常（内核缺陷，引擎不得启动）；实现
  成员缺失 = STAGE 4→5 既有 `_validate_and_bind` 错误（同当前工具 5 的失败面）。
- **拒绝全 5 阶段管线编译契约源**（替代方案否决）：声明域文件经完整管线产出死
  artifact（不执行、无消费方）+ spec 合成副作用在符号表而非 registry（scheduler.py:654
  实证）——harvest 内部状态 = 穿透耦合；直接 parse + 共享合成 = 声明域的完整处理
  （无跳步），无死产物。

### 3.3 共享合成函数（机制同构重构）

- 从 `_inject_host_import`（scheduler.py:680-727）与 `_inject_host_class`
  （:737-830）提取**声明→spec 合成**为 kernel 层共享函数（如
  `core/kernel/spec/host_spec_synthesis.py`：`synthesize_host_module_spec(host_import)
  -> TypeDef` / `synthesize_host_class_specs(...)`）。
- 用户路径（scheduler）与 bootstrap 路径共用同一合成逻辑——单一权威源（设计哲学 §一）；
  用户路径行为不变（合成结果等价判别测试锁定，§六 B1）。
- 依赖方向核查：bootstrap（core.runtime）→ 合成函数（core.kernel）+ parser
  （core.compiler）——compiler↔runtime 既有交叉导入先例存在（engine 全域导入
  compiler）；实施期按 `docs/architecture/01_principles.md` §四 核查无环。

### 3.4 实现重打包（工具 4）

- `ibci_modules/ibci_<tool>` 包：类实例方法 → **模块级函数**（无状态四件：纯函数
  面，类包装 = 无语义的命名间接，删除）+ `create_namespace()` 工厂返回
  per-engine 身份容器（仅含声明成员属性——严格契约语义具象化：容器只有 spec 声明
  的成员，无隐式穿透）。
- 模块级函数为 Python 标准库形态（math/json 即此形态）——`import python "..." as m`
  的用户级语义与 bootstrap 语义**统一**（同一声明文本同一成员解析目标 = 模块属性）。
- **net 不重打包**（状态容器 = 实例，per-engine 身份已满足 registry 隔离守卫）。
- registry 隔离（§1.3 `_BOUND_IMPLEMENTATIONS`）：per-engine 容器/实例满足"同一
  实现对象不可绑两引擎"——sys.modules 模块单例**不可**直接作实现对象（多引擎进程
  第二引擎绑定即 RegistryIsolationError），容器为必要而非可选。

### 3.5 语义差异裁定（变化前后对账）

| 面 | 变化前 | 变化后 | 裁定 |
|----|--------|--------|------|
| 用户面 `import math; math.sqrt(4)` | 字面量 spec + 实例绑定 | 契约源 spec + 容器绑定 | **不变**（既有用户面测试全量锁定） |
| spec provenance | USER_DEFINED | EXTERNAL_MODULE | 行为等价（§1.2 消费点实证）；B2 判别测试锁定（用户模块覆盖 math 的语义前后一致） |
| spec 签名知识 | 字面量手写（与实现双写） | 契约源单写 + 严格绑定校验 | 单点真理改善（工作模式定论 #1/#2 正向） |
| net 状态 | per-engine 实例 | per-engine 实例（不变） | 不变 |
| 契约源编辑面 | Python 字面量 | IBCI 语法（语言自表达） | P6 目标面 |

---

## 四、9 项 VM 设计不变量对照（04_vm_interpreter.md §11）

| # | 不变量 | 对照 |
|---|--------|------|
| 1 | 统一执行入口 | ✅ 契约源不执行（声明域）；用户执行路径零改动 |
| 2 | 控制流数据化 | ✅ 不涉及 |
| 3 | 执行帧抽象 | ✅ 不涉及 |
| 4 | LLM 服务通道唯一 | ✅ 工具 5 无 LLM 成员；ai 通道不触碰 |
| 5 | 公理层无运行时依赖 | ⚠️ 实施期核查：合成函数落 core.kernel（bootstrap 调用），不得反向依赖 runtime |
| 6 | isinstance(IbXxx) 禁用 | ✅ 不涉及（绑定经协议/契约） |
| 7 | 快照隔离不变量 | ✅ 不涉及 |
| 8 | 阻塞即挂起 | ✅ 构造期处理（宿主线程，调度器外） |
| 9 | 调度器永不阻塞 | ✅ 不涉及 |

**确定性 UID 单一权威源**：bootstrap 不产出 artifact（§3.2 拒绝全管线）→ 无新节点
UID 产生 → 既有 UID 值零扰动。

## 五、工作模式定论对照

1. 禁 compat shim：✅ 工具 5 字面量**真删除**（单一权威源迁移，非新旧并存）。
2. 禁胶水：✅ 契约 = IBCI 声明源；绑定 = 既有严格机制（无字符串拼接/魔法哨兵）。
3. 禁 tricky：✅ 语义统一（同一声明文本用户级/bootstrap 级同一成员解析目标）；
   net 实例绑定 = 登记过的本质差异（per-engine 状态），非隐式约定。
4. 禁过程式硬编码分发：✅ 注册/绑定经既有协议通道（register_module / loader）。
5. 质量优先：✅ 消工具 5 签名双写（字面量手写重复 → 契约源单写 + fail-fast 校验）。
6-9. 原则优先/可推翻设计缺陷/破坏性重构授权/分支政策：本设计 = 破坏性重构
   （工具 5 契约源迁移 + 实现重打包），符合普适性（标准库模块级函数形态 + 单一
   权威源 + 机制同构），默认已授权；B2 若实跑破坏面超预期 → 独立隔离分支。

---

## 六、批次计划

> 每批 = 设计确认 → 实现 → 全量 pytest 零回归 → WORKLOG 落账 → 描述性中文本地
> commit（禁 push）；零风险确认（全量零回归 + 复核放行）后 ff unsafe-vibe-dev。

| 批 | 内容 | 风险 | 判别门 |
|----|------|------|--------|
| ~~B1~~ ✅ | 共享合成函数提取（`host_spec_synthesis.synthesize_host_members`，用户路径改调共享函数；行为等价锁定） | 低（纯重构） | 合成等价判别 7 例 + 既有宿主绑定 22 例 + 全量零回归 |
| ~~B2~~ ✅ | 契约源 4 件（math/json/time/schema）+ bootstrap 阶段（`kernel_contracts.load_tool_contracts`）+ 实现重打包（模块级函数；per-engine 命名空间由 bootstrap 经 spec 成员面构造——声明列表单一源 = 契约源，实现包不重复成员清单）+ 4 字面量真删除 + kernel_version 递增（P5 缓存失效） | 中（bootstrap/打包/spec 源三面；用户面契约由既有测试全量锁定） | 契约源↔字面量逐字段等价探针 + 用户面 e2e（import math/json/time/schema 全过）+ provenance 等价判别（用户模块覆盖语义一致）+ 契约漂移 fail-fast 判别（缺失成员/重复绑定/非声明体 → 构造期 InterpreterError）+ per-engine 隔离判别 + 全量零回归（3963/1） |
| ~~B3~~ **取消** | （原：net 契约源）——**实施期实证精化：net 维持宿主侧**（§二 裁定表注记：has_default 默认参数面超出 bind 表达力 + per-engine 状态双重边界） | — | 远期项登记：bind 默认值语法（推翻/精化 F3-0 裁定的语言级设计，独立立项） |
| B4 | 文档收敛（01_native_host_binding 增"内核契约自举"节；插件体系文档同步；KNOWN_LIMITS 边界注记）+ HANDOFF/NEXT_STEPS 同步 | 低 | doc 治理自检（单点真理/跨文件一致） |

**B2 实施期裁定记录（2026-09-09，free-explore）**：
1. **net B3 取消**（上表）——默认参数实证（8 方法 has_default=True）+ 状态本质差异。
2. **provenance 变更（工具 4：USER_DEFINED → EXTERNAL_MODULE）行为安全实证**：
   模块 spec 的 provenance 消费点仅两处——符号重定义兼容性（`compatible_with`：
   EXTERNAL 互兼可重定义，宽松于 USER_DEFINED 互斥，对用户 import 无影响）+ 诊断
   导出（只读投影）；import 解析经"metadata registry 可解析即跳过源文件"（与
   provenance 无关）；覆盖保护仅 KERNEL_NATIVE 触发（工具 4 前后皆不受保护）。
   e2e + shadowing 判别测试锁定。
3. **sys.path 守卫收敛为单一原语**（`modules_path_guard` contextmanager）：
   builtin 工厂加载与契约自举共用；导入目标字符串由调用方按语义提供（包名 vs
   契约源声明的完整模块路径）——消两处镜像的路径守卫逻辑。
4. **kernel_version 递增**（`ibci-2026.09.1-py312`）：工具模块 spec 派生机制/
   provenance 变更 = 内核变更，既有 P5 缓存须失效（kernel_version 的设计用途）。
5. **test_task_scheduler 全量负载下偶发 hang**（96% 处，单独运行 0.17s 通过；
   重跑全量 3963/1 绿）= HANDOFF 已知的框架层并发 flake 类，非 B2 引入（该测试
   不构造引擎），登记观察项。

**非目标**：kernel 5 + fs 契约 bind 化（§二裁定维持宿主侧）；VISION-4/5 类型层
（user-gated，不触碰）；P7 档 B 进程级隔离（后续里程碑）。

---

## 七、待实施期核查项（设计不阻塞，实施时实证）

1. 依赖方向：core.runtime.bootstrap → core.compiler.parser 导入无环（01_principles
   §四 依赖规则）。
2. Parser 独立调用面：契约源 tokenize+parse 的最小依赖集（Parser 构造参数：tokens +
   issue_tracker + host_interface——bootstrap 期皆可得；parser 对声明域文件是否触发
   依赖图副作用须实证 = 预期零副作用，声明域无 IBCI 依赖边）。
3. 工具 5 契约成员全集逐一对账（契约源成员 ↔ 实现面 ↔ 现字面量成员，三者一致）。
4. B2 用户模块覆盖（shadow）判别：EXTERNAL_MODULE spec 下用户模块名冲突行为与
   USER_DEFINED 现状一致。
