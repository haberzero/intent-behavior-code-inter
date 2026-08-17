# WORKLOG — 关键裁定与长期约束

> 本文件只保留**仍有长期约束力的关键用户裁定**与**防止未来误解的重大方向裁定**；
> 历史完成记录与过程细节由 git 承载（`git log` 追溯）。
> 治理规则见 `tasks_docs/GOVERNANCE.md`。
>
> **书写要求**：新增/修改裁定必须按本文尾部「书写模式」模板与格式书写，保持一致。

## 一、长期约束裁定（已固化于 AGENTS.md/HANDOFF 的，此处不重复）

以下裁定已在 `AGENTS.md` 与 `tasks_docs/HANDOFF.md` §1.2 固化，WORKLOG 不复制：
禁 push / 破坏性重构授权 / 大范围破坏性重构分支政策（含 2026-08-11"零风险直接合并"
细则）/ 自主推进偏好与上报阈值 / 工作日志纪律 / 碎片化判断基准 / "不删也不修"两档 /
subagent 仅 general agent / 决策纪律 / goal 配置习惯。

## 二、主线与方向裁定（保留追溯价值）

| 裁定 | 内容 |
|------|------|
| 架构健康性最高准则（2026-08-16） | 内核/架构体系健康性与宏观长远利益为最高准则；全量重跑与试用是对智能体的约束而非负担；理论问题清理完毕后进入下一主线。协议化重构主线（阶段 A-D）由此裁定。 |
| 文档体系正规化（2026-08-16） | 技术文档系统化重构（跟随代码事实 + 章节/讲解顺序/模块化/层次归属重整）；任务控制文档清理与八股化（GOVERNANCE 治理章程 + PENDING_TASKS 正式清单）；KNOWN_LIMITS 真实性查验与体系化；根目录清洁。**完成登记**：5 并行审计（43 文件）→ 五批修复（红线/漂移/结构）→ 全量 3006/1 零回归；LANGUAGE_DESIGN_EVOLUTION 恢复保留（审计复核：正文 1-344 为有价值规划内容，降格为演进评估参考、删除红线附录与自治豁免定位、重新登记 README 目录树与单点真理表）；协议化体系归属架构文档 03 §4.0（唯一权威）；docs/ 零日期戳/零任务编号/零断链（Phase 5 扫描实证）。 |
| 优先级原则（2026-08-08） | 架构缺陷 ≥ 强相关依赖顺序 > 小而快的独立任务 > 非紧急功能演进。"无事实用户，历史兼容不是考虑项"。 |
| 类型体系方向 v2（2026-08-13） | 类型地基根治**不拉回原始架构意图**（原始文档 §8.1 纯函数 substitute 是擦除式方向，照搬会回归已实现的运行时类型身份特性）；当前物化特化类路线（reified，C#/Kotlin 同族）正确，修的是物化路线内的实现缺陷（字符串接口扁平化/双真相/覆盖缺口）。历史文档不是权威——以架构远景+长远收益裁决。 |
| 真实试用定义（2026-08-12） | 试用 = 完整语法全面试用 + 各层面交叉/正交/多层次/多文件压力试用（略带挑刺/恶意试探边界）；**只记录不修复**（优先确定性记录可溯源）；技术手册为主要信息来源；所有试用必须加死循环保护（OS 级硬超时）。 |
| 批判性试用原则（2026-08-14） | 批判性试用应充分利用既有试用地基；以前的试用体系也要经历重跑；试用发现先记录、不查内核成因、不直接修改（非内核修改任务时）。唯一底线：不为规避缺陷改套件（缺陷触发用例保留）。 |
| 显式配置方向（2026-08-12） | LLM 配置显式优于隐式：`setup()` 去自动加载，新增 `ai.load_project_config()`（命名用户拍板）；fail-fast 保留且失败点更清晰。 |
| 用户类泛型升主线（2026-08-12） | PT-FEAT-3（`class Box[T]:`）升主线完整落地；其"泛型类必须特化使用"等守卫为语言约束（KNOWN_LIMITS §十四 #1）。 |
| LLM 主线轮替（2026-08-15/16） | 2026-08-15：PT-FEAT-14 暂缓，主线 = LLM 全能力真实压力试用；2026-08-16：主线 = 协议化内核大重构（压力试用顺延）；理论清理后按用户意愿恢复试用扩展。 |
| 能力判定协议化口径（2026-08-16） | `__from_prompt__` 能力判定与获取口径不一致时——历史不是权威；"记录不整改"理由不成立，须整改收敛（get_from_prompt_cap 单一查询入口；结构性用户方法由 VTableParsingStrategy 职责分离，不合并）。 |

## 三、重大方向决策记录（防止未来误解）

- **协议化重构（2026-08-16，exp/protocol-kernel → unsafe-vibe-dev 直接合并）**：
  协议注册表（ProtocolDef/Registry）为能力判定单一权威；普通函数与 LLM 函数全链路
  统一；retroactive implementation（impl 可携带方法体）。合并前 116 例真实 LLM 复跑
  分类与基线逐例一致，用户授权直接合并。设计要点固化于架构文档与交接记录。
- **阶段 A-D（2026-08-16，本 session）**：OOP 侧协议化（receive dunder 注册表化）、
  双轨收敛（self 形态统一/特化身份结构化/成员单一权威/auto-init 声明化/预评估诊断）、
  判定链双协议化（协议条目判定声明数据驱动 satisfies）、KNOWN_LIMITS 26 节终判。
  设计决策 D1-D7/B1-D1/B2-D1~D4 记录于临时设计文档（已随临时文档清理，git 承载）。
- **文档体系重构（2026-08-16，本任务）**：见 `tasks_docs/GOVERNANCE.md` 治理章程与
  `docs/` 重构记录（git）。
- **LLM 调用层插件化 / 供应商无关中间层（2026-08-17，exp/llm-providerization →
  unsafe-vibe-dev 手动 cherry-pick）**：内核只产出结构化 `LLMCallRequest` 委托给可
  插拔 `LLMProvider`；系统提示词组装（推荐模板）、思考抑制/探测、api_config.json
  书写格式全部下沉为可自定义 provider/ConfigSourceAdapter。移除旧 `ILLMProvider`
  标量协议死代码。设计要点固化于 `docs/architecture/01_principles.md` §3.7 与
  提交记录。验证：全量 pytest 3027 pass + T09 真实 LLM 8/8 PASS。
- **Provider 层分离（近期主线）+ IBCI 原生宿主绑定（远期愿景）· 两段式（2026-08-17，规划交接阶段）**：
  近期聚焦 LLM provider 层分离彻底完成（当前 Python 源码分发，近期不开放语言级自定义 API，
  需自定义的用户改内核 provider 文件 `ibci_modules/ibci_ai/provider_impl.py`）；远期才推进
  "抛弃 Python `_spec.py` 插件思路、用户 IBCI 层原生绑定 Python 内容"（宿主导入 + 类型/协议/impl
  绑定 + 插件体系重构 + 内核自举 + 缓存/JIT）。总路线图见 `tasks_docs/ROADMAP_NATIVE_BINDING.md`
  （近期 R0-R2 / 远期 F0-F5 / 关键裁决点）。触发背景：深度调研确认 `box()` 已能包装任意
  Python 对象/可调用，但 `import X` 与 `impl` 目前受 `_spec.py`/本模块用户类限制；近期先做对
  provider 解耦、为远期留位。
- **近期主线 R0-R2 完成（2026-08-17，exp/provider-decouple-r1 → unsafe-vibe-dev 零风险直接合并）**：
  近期分发形态确立 = 自定义 LLM 底层 = 修改/替换 `ibci_modules/ibci_ai/provider_impl.py`
  （`RecommendedProvider`，纯 provider，kernel-free 可整文件替换；宿主 `core.py` 仅 IBCI 胶水，
  内外结构 `AIPlugin(RecommendedProvider, IbStatefulPlugin)`）；MOCK 哨兵下沉
  `core/base/llm_protocol.llm_call`（单一权威源，kernel 消费者改从 base 导入）；kernel-free
  `config_normalize.py` 收拢默认常量与 to_llm_config 归一；provider 失败契约统一 RuntimeError
  （唯一行为差异：`_init_client` 配置缺失错误类 InterpreterError→RuntimeError，已记录）。
  接口位收敛口径：`LLMCallRequest.thinking_mode` 保持"契约字段存在、推荐实现不读"，推为远期
  F4 供应商字段映射位；`ConfigSourceAdapter` 不加注册入口（推荐默认适配器整文件替换路径）；
  不新增语言级注册 API。设计要点固化于 `docs/howto/modify_llm_provider.md` +
  `docs/architecture/01_principles.md` §3.7 + 路线图 §五。验证：全量 pytest 3027 pass +
  独立复核放行（probe 启发式 P1 修复 + 字节级二次验证）。远期 F0-F5 接口位已留、无返工债务。
- **远期主线 F0 完成（2026-08-17，exp/native-binding-f0 → unsafe-vibe-dev 零风险直接合并）**：
  Native Binding 地基验证——实证 `box` 裸 Python 模块 + 手动 vtable 绑定成员 + receive 调用
  可行（内核 API）；设计底稿 `docs/architecture/01_native_host_binding.md`。**裁决点 1（宿主
  绑定语法形态）定稿 = `import python "pkg" as lib`**（复用既有 import 形态 + `python` 伪模块
  + 字符串模块名），理由：统一设计语言（import 已承载"引入外部内容"）/ 机制同构（复用
  parser→scheduler→VM→module_manager 管线）/ 语义区分（python 伪模块标识宿主空间）/
  无外部用户（全新语法零迁移成本，风险可控自主决策）。裁决点 2（宿主导入类型 = 一等类型，
  复用 Provenance.EXTERNAL_MODULE）、3（成员绑定 = 显式声明式、非自动穿透）定方向。
- **远期主线 F1 完成（2026-08-17，exp/native-binding-f1 → unsafe-vibe-dev 零风险直接合并）**：
  宿主导入一等语法 `import python "pkg" as lib: bind ...` + 用户类持有 native。全链路实现
  （AST IbHostImport/IbHostBinding + bind 关键字 + parser 宿主 import/bind 块 + 依赖扫描跳过
  + scheduler 合成宿主模块 spec/注入 lib 符号 + 语义符号绑定 + module_manager import_host_module
  + vm_handle_IbHostImport）。**显式声明式绑定**：成员访问强制经 vtable/whitelist 门控，契约外
  fail-fast；bind 签名编译期类型检查；用户 IBCI 类 `any` 字段持 native。**单一权威源提取**：
  `_annotation_utils.annotation_to_typeref`（AST→TypeRef，自 symbol_collection_pass）与
  `proxy.create_proxy`（unbox→调→box，自 loader._validate_and_bind）供插件/宿主共用，消除双真相。
  验证：e2e（sqrt=4.0/pi/pow=1024.0/用户类=5.0/磁盘文件 rehydrate/跨模块=7.0/无 asname=4.0）；
  负样本（未声明成员 fail-fast、绑定缺失成员报错、编译期类型检查 SEM_TYPE_MISMATCH）；全量
  pytest 3041 passed / 1 skipped（新增 tests/runtime/test_host_binding.py 10 项）。
  **F1 独立复核（subagent a8fc712b）**：核心红线（禁双通道/兜底/历史包袱）干净，无阻塞性放行
  障碍。修复中 severity #1（import python 误伤真实模块——加 peek(1)==STRING 守卫）+ 低 severity
  #3/#4/#5/#7/#8/#9/#10（strip 死代码删、descriptor type_ref 同步、序列化缺节点 fail-fast、
  _spec.py 硬编码消息、重复 bind SEM_REDEFINITION、param _loc、类型检查 pass visit_IbHostImport）。
  设计取舍记录：#2（未声明成员编译期静默降级 any，与既有 import 一致，F2 再评估）、#6（宿主
  import 不传 registry_id，裸模块进程级单例低风险）。
- **远期主线 F2 完成（2026-08-17，exp/native-binding-f2 → unsafe-vibe-dev 零风险直接合并，65414738）**：
  协议/impl 扩展到宿主类型——bind class 宿主类型绑定 + impl 目标限制解除。**语法定稿**：
  `bind class Name: <嵌套 bind 成员>` 块形式 + `bind class Name -> any` 简写；成员表 =
  宿主声明 + impl 补充并集；impl provenance 放行 EXTERNAL_MODULE、拒绝 KERNEL_NATIVE。
  **编译期**：scheduler `_inject_host_class` 注册一等类型 EXTERNAL_MODULE CLASS（模块限定）+
  合成 owned_scope（宿主类无 AST 作用域，impl 注入需要）；协议满足 = 编译期静态 spec 判定
  （bind 声明 + impl 补充并集），零运行期改动。**运行期**：HostClassBinding(IbClass) 恒走
  instantiate（裸 Python 类构造）+ per-instance vtable（bind 方法 = create_proxy 绑定方法）+
  whitelist（bind 属性）；impl 方法经 IbNativeObject._dispatch_getattr 类方法回落 →
  IbBoundMethod（注入 receiver）；bind 方法返回 py_class 实例时重包装保持一等类型。
  **F2 独立复核（subagent b228d4fd）整改闭环**：B1（回落加 isinstance(HostClassBinding) 门控——
  实证为误诊，pre-F2 父提交 j.toString 经 Object 公理路径同样泄露；gate 保留为机制隔离）；
  M1（bind vs impl 同名编译期未拦截——宿主类合成 owned_scope 为空表，冲突检查只查符号表；
  修复：visit_IbImplDef 冲突判定改以权威成员面 spec.members 为准 SEM_REDEFINITION +
  bind 块内重复绑定同样 fail-fast，新增 3 回归测试）；M2（instantiate 内联拆箱 →
  base.unbox_for_native_call 单一权威含可调用透传，proxy/host_class 共用）；
  L1（UID 内联拼接 → uid.py helper）、L2（STAGE5/VM import 重复+错误类型漂移 →
  module_manager.import_host_py_module 单一入口）、L3（getattr 能力探测 →
  isinstance(IbNativeObject) 协议化判别）、L4（属性实例属性类级误拒已修，queue.Queue 回归）、
  L5（POSITIONAL_OR_KEYWORD 散落记录为已知限制，随 F3 统一绑定面收敛）。
  验证：全量 pytest 3053 passed / 1 skipped 零回归。测试
  `tests/runtime/test_host_binding.py`（F1 10 + F2 18）。
- **远期主线 F3 定稿 + F3-1 完成（2026-08-18，exp/plugin-refactor-f3）**：
  **F3 目标** = 废弃 Python 侧 `_spec.py` 磁盘发现/加载通道、不保留双通道，用户侧扩展
  唯一边 = 宿主绑定 bind。**F3 定稿决策**：内置模块全部内联 TypeDef 字面量集中
  `core/runtime/bootstrap/builtin_modules.py`（`BUILTIN_MODULE_SPECS`，内核原生 5 +
  工具 5 + file，file 自 engine.py 挪入），Engine 构造期一次注册全部含实现；工具插件
  实现不改（探针 A1：类实例路径可行，仅 bind 模块成员路径需模块级函数）；
  F3-0（bind 默认参数语法）**裁定跳过**——默认值放 .ibci 包装层（IBCI 用户函数本支持
  默认参数），bind 语法零改动；工具库归宿收敛为第三态「内联 spec 的内置模块」
  （保 `import math` 全兼容，bind-based IBCI 标准库推迟 F5 内核自举评估）。
  **F3-1 落地决策**：文件/函数重命名（`kernel_native_modules.py` → `builtin_modules.py`、
  `register_kernel_native_modules` → `register_builtin_modules`——职责从"内核原生 5"扩展
  为"全部内置模块"，命名同步，design-philosophy §八）；loader 环 2 跳过构造期已注册
  实现模块（消除"环 1 绑定 + 环 2 再建实例重绑"双绑定，即 F3-2 删除环 2 的终点语义
  提前落地）；去除冗余显式 `reserve_kernel_native_name`（`register_module` 对 KERNEL_NATIVE
  provenance 元数据已内建自动 reserve，机制同构）；测试迁移（`test_kernel_native_modules.py`
  → `test_builtin_modules.py` 含结构契约断言；`test_idbg.py` 改断言内联 spec；
  SDK `test_check_plugin.py` 迁移至 F3 语义——ibci_modules 安装包不再算用户插件目录）。
  验证：结构等价探针（9 模块字面量 vs 旧 discovery 路径逐字段比对等价，_spec.py 删除前
  运行）+ 全量 pytest 3056 passed / 1 skipped 零回归。设计要点固化于
  `tasks_docs/_f3_plugin_refactor.md`（F3 完成后沉入 docs/architecture）。
  遗留：discovery/auto_discovery/main.py --plugin/SDK _spec 面删除 = F3-2；测试/
  examples/trials/docs 迁移 = F3-3。
- **F3-2 完成（2026-08-18，exp/plugin-refactor-f3）**：磁盘插件发现/加载双通道彻底铲除。
  **删除面**：`core/runtime/module_system/discovery.py` + `core/extension/auto_discovery.py`
  （ModuleDiscoveryService/AutoDiscoveryService）；loader 环 2（磁盘扫描 + create_implementation
  实例化 + 二次绑定），`load_and_register_all` 收敛为仅对已注册实现做环 1 契约绑定；
  插件搜索路径配置面（`IbciConfig` plugin_paths/global_plugin 整模块 `core/kernel/config.py`
  删除、`ProjectDetector.get_plugin_paths` 嗅探、`inherited_plugin_paths`/
  `inherited_global_plugin` 继承透传）；main.py `--plugin`/`--no-sniff`/`load_external_plugins`；
  `engine.register_native_module` API（唯一消费者即 main.py）；SDK `ibci_sdk/` 整包
  （gen_spec/check 为写/查 _spec.py 插件工具，F3 后无场景）；`__ibcext_axiom__` 死协议
  （engine 公理加载面）；`core/extension/spec_builder.py`（SpecBuilder/ClassSpecBuilder
  零消费者死代码）；幽灵诊断码 `KDIAG_POLICY_MODULE_NO_EXPORT`（唯一发射点为 loader 环 2，
  从 codes.py/catalog/docs 一并删除）。**Engine 签名简化**为 `IBCIEngine(root_dir=...)`
  单一参数（auto_sniff/inherited_* 移除；41 处测试机械迁移）。**隔离超时测试稳定化**：
  `test_timeout_raises_when_child_exceeds_deadline` 由"启动耗时 > 1ms"脆弱墙钟假设改为
  子任务先 sleep 再返回——F3 移除插件发现使子引擎启动更快使原假设偶发失效，追踪根因
  修正而非 flaky 搪塞。验证：全量 pytest 零回归；幽灵码清除经 test_diagnostic_catalog
  CAT-7 佐证。遗留：examples/trials/docs 迁移 = F3-3；_spec 主题残留扫描 = F3-4。
- **F3-3 + F3-4 完成，F3 全部落地（2026-08-18，exp/plugin-refactor-f3）**：
  **F3-3（examples/trials/docs 迁移，subagent 1ba1f995 执行 + 本 session 复核）**：
  删除 `examples/plugins_demo/`、`isolation_demo/sub_project/plugins/`、
  `trials/T01_llm_full/plugins/`（演示/试用已删除的用户插件 `_spec.py` 系统）；
  `trials/cases/D2-21-plugin.ibci` 改写为宿主绑定演示（`import python "math" as m:
  bind sqrt/pow`，经 main.py 实跑通过）；`docs/howto/write_user_plugin.md` 删除 →
  新建 `docs/howto/extend_with_host_binding.md`（用户扩展 howto 换宿主绑定语义）；
  `docs/subsystems/04_plugin_system.md` 重写为"内置模块系统与宿主绑定"；01_principles/
  06_path_system（删插件发现优先级章节）/07_kernel_native_modules/11_modules
  （§11.9 改宿主绑定指针）/KNOWN_LIMITS §十九/README 等 20+ 文档更新到 F3 事实。
  **F3-4（残留扫描 + 全量验证）**：`_spec.py` 物理文件清零；discovery/auto_sniff/
  plugin_paths/ibci_sdk/SpecBuilder 等功能性引用全零；剩余 `_spec.py` 均为历史说明
  注释（顺手清除 ibci_ai/core.py 与 builtin_modules.py docstring 过时引用）。全量
  pytest 2946 passed / 1 skipped 零回归。**F3 完整度**：三阶段放行门全过，达分支合并
  细则"零风险直接合并 unsafe-vibe-dev"标准（全量 pytest 零回归 + F3-1 结构探针 +
  F3-2/F3-3 独立 subagent 复核 + F3-4 残留扫描，无对外契约/架构级风险）——仍禁
  push，合并须用户授权。


---

## 附、书写模式（本文档专用模板，书写必须参照）

> 本节是本文档书写的**唯一权威模板**（模板归属 = 文档自身；`GOVERNANCE.md`
> §三 仅做索引）。新增/修改裁定一律按下列模板与规则书写。

### 1. 文档结构

```
# WORKLOG — 关键裁定与长期约束
定位段（只保留仍有长期约束力的裁定；历史由 git 承载）
一、长期约束裁定（已固化于 AGENTS.md/HANDOFF 的，此处只列指针不复制）
二、主线与方向裁定（表格）
三、重大方向决策记录（防止未来误解）
```

### 2. 裁定表格模板（§二）

```markdown
| 裁定标题（时间 YYYY-MM-DD） | 关键裁定/决策 + 变化前后摘要（实现+测试+文档）|
```

规则：
- 只保留**仍有长期约束力**的用户裁定与**防止未来误解**的重大方向裁定；
- 例行完成记录由 commit 消息承载，**不写入** WORKLOG；
- 内容一句话说清裁定本身与适用边界，不写过程叙述；
- 已固化于 `AGENTS.md` / `HANDOFF.md` 的裁定，在 §一 列指针、不复制正文（单点真理）。

### 3. 重大方向决策记录格式（§三）

```markdown
- **<决策名>（时间 YYYY-MM-DD，<分支/来源>）**：决策内容 + 设计要点落点（
  架构文档 / 交接记录 / git）。
```

规则：每条一至三段；设计要点**不在此展开**，标注其固化的权威位置（指针）。
