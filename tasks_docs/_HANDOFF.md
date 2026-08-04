# 临时交接文档（下一 session 完成交接后删除）

> 本文件为**临时交接**，记录当前工作状态、已完成、下一步、关键约束与待决项。下一 session 据此继续后，经确认删除本文件。
> 状态：**线程对象模型方向修正实施中**——任务 A（Optional 配套）、任务 B（统一泛型模型）**已完成并 commit**；任务 C（线程对象模型）**已调研、未写代码**；任务 D-F 待开工。分支 `unsafe-vibe-dev`。
> ⚠️ **重要**：下一 session 必须先完整阅读本文件（尤其 §三 自主运行配置 与 §四 当前工作状态），再启动自主运行。workflow 全过程坚持 AGENTS.md 中"自主工作循环"（含"只记录，不断决"、上报阈值、破坏性重构授权、禁止 push 硬原则）。

---

## 一、当前工作状态

- **主线**：线程对象模型方向修正（`tasks_docs/THREAD_DESIGN_REVISION.md`，唯一决策依据）。任务 A-F 按依赖驱动顺序实施。
- **任务 A 已完成**：Optional 配套完整实现。
- **任务 B 已完成**：统一泛型模型（GenericTypeRegistry 单一权威源 + thread[T] 首个消费者）。
- **任务 C（进行中）**：线程对象模型（thread[T] + 构造函数 + 句柄方法 + 生命周期状态机）。**已做完调研，尚未写任何实现代码**（详见 §四）。
- **分支**：`unsafe-vibe-dev`（唯一活动分支）。
- **测试基线**：以实跑为准。当前全量 `python -m pytest tests/` = **1443 passed / 4 skipped**（任务 A、B 落地后）。
- **工作区**：git 干净（仅 `.opencode/opencode.json`、`.opencode/tui.json` 未跟踪，属 opencode 配置，非项目代码）。

## 二、已完成（本会话，已 commit，未 push）

**方向修正决策（commit 8275124 + 4f2a456）**：
- `tasks_docs/THREAD_DESIGN_REVISION.md`：async/thread 领域分离、删 spawn/join/cancel/task、`thread[T]` 泛型、`thread_result[T]` 容器、err 类型统一、挂起取消、统一泛型模型、Optional 配套、疏漏 1-6 裁决、F-1~F-8 碎片化、VP-1~VP-6 违规点、任务 A-F 清单。用户已授权实现。

**任务 A — Optional 配套完整实现（commit b7b3e77）**：
- 新增运行时 `IbOptional` 值类（`core/runtime/objects/primitives/optional.py`，`@register_ib_type("Optional")`）：is_some/unwrap/or_else + 值协议（to_bool/cast_to/__to_prompt__/to_native/receive __eq__/__ne__）。
- `ScopeImpl._wrap_optional` 单一绑定入口（define/assign/assign_by_uid 三处接入，覆盖定义/重赋值/函数参数/LLMFuture 解析回写），幂等。
- `_assignability.py`：Optional 基础（wrapped=any）→ Optional[T] 可赋值（复制场景）。
- `OptionalAxiom` 补值协议方法表面；序列化（serialize + deserialize optional 分支）。
- 测试：`tests/runtime/test_optional_runtime.py`（17 用例）。

**任务 B — 统一泛型模型（commit d814568）**：
- 新增 `core/kernel/spec/generic.py`：`GenericTypeDeclaration` + `GenericTypeRegistry`（按 name+kind 索引），每类型声明生命周期四操作 `build`（创建）/`to_typeref`（序列化）/`restore`（还原）。内置 list/dict/tuple/Optional/fn_callable/behavior/thread。
- `SpecRegistry` 持有 `self.generic_types`；`resolve_specialization` 统一走注册表创建/解析。
- **删除历史遗留路径**（用户明确要求"不保留历史包袱，最终删除"）：删除 `_assignability.resolve_specialization` 的遗留兜底分支 + Optional/List/Dict/Tuple Axiom 的 `resolve_specialization_by_names` 方法。
- `thread[T]` 首个消费者：`THREAD_SPEC`（kind=TASK，`_axiom_name="thread"`）、`ThreadAxiom`（start/join/cancel/is_done 方法表面）、`SpecFactory.create_thread`、`_members.py` thread 特化（`thread[T].join()`→T）、serializer/rehydrator thread 值类型持久化。
- 测试：`tests/kernel/test_generic_model.py`（16 用例）。

**通用体系（前会话）**：`design-philosophy` skill + `skills/README.md` + `AGENTS.md` 注册（已 commit，见 d865d1a）。

---

## 三、自主运行配置（下一 session 必须完整读取并据此配置 goal）

### 3.1 授权原则（用户已明确授权，可直接执行）

**用户已授权无人值守自主运行**，以下原则是授权的完整内容，下一 session 必须全文纳入 goal objective：

1. **自主推进偏好（最高优先）**：总体偏向**无人值守**，允许模型**较大限度自我裁定与自我质询分析**并**尽可能推进**。**只有经过最大限度反思、质询、分析后仍确实无法彻底自主决定的内容，才造成阻塞**。凡能自主决断的，一律自主决断并**详尽记录决策依据**（工作日志）。上报阈值从"最小化上报"统一为"**尽可能自主推进**"——不是"遇到困难就上报"，而是"先穷尽自主手段，确实无法决定才上报"。
2. **决策纪律**：凡需用户拍板的决断项，可**大胆且相对激进地选择方案**，不必保守。最底线 = ①架构设计原则 ②代码质量原则 ③非妥协/非 tricky/非临时兼容层原则 ④大方向主线任务原则。在此底线内自主推进，不因需拍板而停滞。
3. **交付纪律**：全程本地 git commit；**禁止 push 到 GitHub（硬原则）**——除非用户明确指示允许 push，否则一律禁止 `git push` 到任何远程仓库。push 不因"已授权自主运行"而默许，必须等用户显式授权。
4. **破坏性重构授权（硬原则）**：当判断符合一般工程经验、普适性、合理架构选择与设计，且经分析确实优于现有体系及已有代码时，**哪怕该设计已被文档记录，也允许进行破坏性重构**。用户**不禁止修改已有代码**；已有代码的优先级**低于**架构正确性与设计统一一致。此授权覆盖"超出已授权范围的破坏性变更"项，默认自主推进，仅需详尽记录决策依据与工作内容即推进。
5. **大范围破坏性重构的分支政策（硬原则）**：对**无法确认边界、无法判断危害程度**的破坏性重构，**100% 授权在其独立分支**（不污染 `main` 与 `unsafe-vibe-dev`，不污染任何计算机环境与用户目录），允许任意程度破坏性实验与重构。**仅当独立隔离分支也无法经自主实验确定工作路线时**才将任务配置为阻塞。**独立分支禁止直接合并到 `unsafe-vibe-dev` 或 `main`**；确认完整技术路线后，允许单独手动更新 `unsafe-vibe-dev` 代码。**永远不允许触碰主干分支（`main`）的代码。**
6. **工作流（每任务强制）**：code-workflow Phase 0-5（先读 NEXT_STEPS/PENDING_TASKS 再读代码证据再对照硬约束设计，实现守卫生纪律，全量验证，收尾同步）；方案对照工作模式定论五条 + code-quality 红线 + fail-fast/封装纪律；设计后 self-grill 自我质询 + design-philosophy 设计哲学对照；code-odor 工作过程自查；批量后 code-review 残留扫描；每批跑全量 `python -m pytest tests/` 零回归才算完成。
7. **工作模式定论**：禁 compat shim/胶水/tricky/过程式硬编码/双通道/双写真相；质量优先于速度；原则优先于行为维持；可推翻 IBCI 自身设计缺陷（文档化也可推翻，按更普适方案重建，通常不询问用户）。
8. **文档治理**：设计/决策先写**任务控制文档 `tasks_docs/`**，**不写进技术手册 `docs/`**（用户明确要求）；落地后按治理择机写入。`docs/` 只面向人类，禁智能体元信息。
9. **工作日志记录（强制）**：所有自主决策、质询分析、方案取舍、变化前后（实现+测试+文档）必须**详尽记录**在 `tasks_docs/` 任务控制文档（如 `WORKLOG` 或各任务文档的决策记录段落）。**"只记录，不断决"**——能自主决定的就记录决定并推进，不断等用户；只有确实无法决定的才在记录中标记为待决并上报。

### 3.2 goal objective 模板（可直接复制使用）

> 注意：任务 A、B 已完成。下一 session 从 **任务 C** 开始，goal 主任务应写明"任务 C 起"。模板已按此更新。

```
【方向修正实施 · 无人值守】主任务：按 tasks_docs/THREAD_DESIGN_REVISION.md 实施线程对象模型方向修正（任务 A-F）。

一、主线任务（按序，依赖驱动）：
【任务 A（Optional 配套）、任务 B（统一泛型模型）已完成 2026-08-04，见 WORKLOG】
C) 线程对象模型（thread[T] 类型 + 构造函数 + 句柄方法 start/join/cancel/is_done + 生命周期状态机）→ D) err 类型统一（TaskCancelled/TaskFailed 映射 IBCI Exception 子类；cancel 返回 err；err 用户可见可继承）→ E) 线程相关清理（VP-1~VP-6 + F-1~F-8）→ F) 关键字精简（删 spawn/join/cancel/task 全链）+ 废除旧测试 + 新测试单独制作。
每完成一个任务用描述性 commit 提交（说明+验证计数），同步更新 NEXT_STEPS/PENDING_TASKS，然后自动接续下一任务。

二、自主推进偏好（最高优先）：总体偏向无人值守，允许较大限度自我裁定与自我质询分析并尽可能推进。只有经过最大限度反思/质询/分析后仍确实无法彻底自主决定的内容才造成阻塞。凡能自主决断的一律自主决断并详尽记录决策依据（工作日志）。上报阈值统一为"尽可能自主推进"——先穷尽自主手段，确实无法决定才上报。决策纪律：可大胆激进选方案，底线=架构原则/代码质量原则/非妥协/非tricky/非临时兼容层/大方向主线。不因需拍板而停滞。

三、交付纪律：本地 commit；禁止 push 到 GitHub（硬原则）——除非用户明确指示允许 push，否则一律禁止 git push 到任何远程仓库，push 不因"已授权自主运行"而默许，必须等用户显式授权。破坏性重构授权（硬原则）：当判断符合一般工程经验/普适性/合理架构设计且经分析确实优于现有体系及已有代码时，哪怕设计已被文档记录也允许破坏性重构；不禁止修改已有代码，已有代码优先级低于架构正确性与设计统一一致；此类破坏性变更默认已授权自主推进，仅需详尽记录决策依据与工作内容。大范围破坏性重构分支政策（硬原则）：对无法确认边界/危害程度的破坏性重构，100% 授权在其独立分支（不污染 main 与 unsafe-vibe-dev，不污染任何计算机环境与用户目录）进行任意程度破坏性实验与重构；仅当独立隔离分支也无法经自主实验确定工作路线时才将任务配置为阻塞；独立分支禁止直接合并到 unsafe-vibe-dev 或 main，确认完整技术路线后允许单独手动更新 unsafe-vibe-dev 代码；永远不允许触碰主干分支（main）的代码。工作日志：所有自主决策/质询分析/方案取舍/变化前后(实现+测试+文档)必须详尽记录在 tasks_docs/ 任务控制文档（WORKLOG 或各任务文档决策记录段落），"只记录，不断决"。

四、工作流：每任务 code-workflow Phase 0-5 + 质量门 + design-philosophy 设计哲学对照 + 全量 pytest 零回归（python -m pytest tests/）。

五、主任务阻塞/暂停时的支线（按优先级，主任务解阻立即回主线；全部主线任务被阻塞时自主推进，不因等待而停滞）：
1) 质量维护/代码健康：quality-maintenance Tier A/B + 健康诊断十查 + aimless-review 低密度审视，产出入 tasks_docs/AIMLESS_REVIEW.md；
2) PT-SMELL-1/2/3 代码质量审计（独立分支不混置主线文件）；
3) PT-SEM-1.1 错误用户友好化；PT-4.1 Enum 非 str 成员；
4) 测试体系重构（TEST_REFACTOR，tasks_docs/TEST_REFACTOR.md）。
每条支线仍须每批全量 pytest 零回归、commit+留痕（仅本地）、遇上报阈值项即停。

六、停止条件：先穷尽自主手段（反思/质询/分析/记录），仅当确实无法自主决定时（用户意图不明穷尽无解/公理层语义错误集确需用户裁决/与工作模式定论冲突/破坏性重构无法确认边界且独立隔离分支也无法经实验确定技术路线）才 update_goal(status="unmet", blocker=具体卡点+建议)。凡能自主决断的一律自主推进并记录工作日志。（破坏性重构默认已授权，见 §三.1；仅在独立分支也无法确定路线时才阻塞。）

七、非目标：media Phase 4、跨进程/CPU 并行、跨引擎通信、完整通用异步（async 函数/生成器）、线程无损挂起/恢复、用户级泛型类（PT-4.4）、Hindley-Milner 约束求解。
```

### 3.3 支线任务完整清单（主线卡住时允许执行）

| 优先级 | 支线 | 触发条件 | 说明 |
|--------|------|---------|------|
| 1 | 质量维护/代码健康 | 主线阻塞或阶段边界 | quality-maintenance Tier A/B + 健康诊断十查 + aimless-review，产出 `tasks_docs/AIMLESS_REVIEW.md` |
| 2 | PT-SMELL-1/2/3 | 主线全部停滞 | 代码质量审计（独立分支，不混置主线文件） |
| 3 | PT-SEM-1.1、PT-4.1 | 主线停滞 | 错误用户友好化；Enum 非 str 成员 |
| 4 | TEST_REFACTOR | 主线全部停滞 | 测试体系重构（用户已确认纳入支线） |

### 3.4 上报阈值（仅"穷尽最大限度自主反思/质询/分析后仍无法决定"才停止/询问用户）

> 统一为"**尽可能自主推进**"：不是"遇到困难就上报"，而是"先穷尽自主手段，确实无法决定才上报"。凡能自主决断的一律自主决断并记录决策依据（工作日志）。

- 用户意图不明，且代码/文档/测试**穷尽证据后仍**无法给出确定答案
- 公理层或语义错误集变更——**倾向自主评估并推进**，仅在评估后确需用户裁决语义取舍时才上报
- 与工作模式定论冲突——先自主分析并给出推荐方案，确实无法自主裁决才上报
- 破坏性变更**默认已授权**（见 §三.1"破坏性重构授权"），**不构成上报项**；仅在**无法确认边界/危害程度**且**独立隔离分支也无法经自主实验确定技术路线**时，才将任务配置为阻塞并上报（见 §三.1"大范围破坏性重构的分支政策"）

---

## 四、当前工作状态（方向修正，最重要）

**完整决策**：`tasks_docs/THREAD_DESIGN_REVISION.md`（唯一决策依据）。

### 核心裁定
- **async 与 thread 彻底分离**：`IbTask` 不得满足 Waitable；await 只服务异步；线程走句柄方法。
- **关键字精简**：删 spawn/join/cancel/task，改用 `thread` 类型 + 句柄方法。
- **`thread[T]` 泛型标注必须**（非参数传递）；返回类型显式标注；`thread[void]` 支持。
- **`thread_result[T]` 泛型容器**：成功值/错误/状态，可继承可改写，禁止 any。
- **配套方法**（Rust 对齐）：`unwrap()→Optional[T]` / `unwrap_or(default)` / `is_error()` / `.value`(fail-fast) / `.error`。
- **err 类型统一**：接入既有 Exception 体系；TaskCancelled/TaskFailed 映射 IBCI 子类；`t.cancel()` 返回 err。
- **挂起机制取消**（未来也不做）。
- **统一泛型模型立即启动**：内置类型泛型化正式机制；`thread[T]` 首个消费者；不含用户级泛型类/约束求解。
- **Optional 配套**：运行时 `IbOptional` 已补齐（任务 A）。

### 疏漏裁决
- 疏漏 1：无用关键字直接删除。
- 疏漏 2：通信领域（chan/signal/slot）完善与统一化检查 = **下阶段任务，暂缓**。
- 疏漏 3：**大范围重构直接开始**，允许推翻/删除既有代码（含 PT-MT-1~8 的 spawn/join/cancel 相关实现与测试）。
- 疏漏 4：内省用明确方法（非裸属性）；线程对象/容器瞬态；**save_state 检测未完成线程则抛异常 fail**。
- 疏漏 6：废除相关旧测试，新机制测试单独制作。

### 任务进度（A-F）
- **A. Optional 配套完整实现 —— ✅ 已完成**（commit b7b3e77）
- **B. 统一泛型模型 —— ✅ 已完成**（commit d814568）
- **C. 线程对象模型（thread[T] + 构造函数 + 句柄方法 + 生命周期状态机）—— 🔄 调研中，未写代码**
- **D. err 类型统一 —— 待开工**
- **E. 线程相关清理（VP-1~VP-6 + F-1~F-8）—— 待开工**
- **F. 关键字精简（删 spawn/join/cancel/task）+ 废除旧测试 + 新测试 —— 待开工**

### 任务 C 调研结论（下一 session 据此继续，勿重复调研）

> 本会话已对任务 C 做过代码调研，以下为已确认事实，可作起点。**尚未写任何实现代码**。

- **`thread` 类型已就绪**：`thread` 类已由 ThreadAxiom 在运行时创建（`registry.get_class("thread")` 存在）；`thread[T]` 类型解析经 GenericTypeRegistry 工作（任务 B 已验：`thread[int]` 解析成功、kind=TASK、`get_base_name()="thread"`、`value_type.head="int"`）。
- **`thread[T].join()` 返回类型特化已就绪**：`_members.py` 已加 thread 特化（`thread[T].join()`→T，`thread[void].join()`→void）。
- **既有内核机制可复用**：`core/runtime/coordinator.py` 的 `RuntimeCoordinator` + `SpawnedTask`（后台线程 + 任务本地执行上下文）。现有 `IbTask`（`core/runtime/objects/task.py`）是 spawn 句柄，**方向修正要求改造为 thread 对象 + 句柄方法**。
- **当前 spawn/join/cancel 是关键字**（TokenType.SPAWN/JOIN/CANCEL/TASK），走 `vm_handle_IbSpawnStmt/IbJoinStmt/IbCancelStmt`（`core/runtime/vm/handlers/comm.py`）。这些在任务 F 删除。
- **parser 构造函数模式参考**：chan/signal/slot 是关键字前缀（`chan_expr`/`signal_expr`/`slot_expr`，`core/compiler/parser/components/expression.py`），产 `IbChannelExpr/IbSignalExpr/IbSlotExpr`。**但 `thread` 不是关键字**，`thread(...)` 如何解析为构造函数需自主设计（参考 chan 模式，或作为类型调用构造）。
- **设计重点**：`thread[T] t = thread(fn=..., args=...)` 构造函数 + `t.join()/t.cancel()/t.start()/t.is_done()` 句柄方法 + 生命周期状态机。`join()` 返回 T（任务 B 已为此特化好返回类型）。`cancel()` 返回 err（任务 D 落地）。需从 comp_parser → semantic → VM dispatch → 运行时对象 全链设计。**设计决策按自主推进偏好记录于 WORKLOG，触及上报阈值项才上报。**

---

## 五、关键约束与原则（必须遵守）

- **交付纪律**：**禁止 push 到 GitHub（硬原则）**——除非用户明确指示允许 push，否则一律禁止 `git push` 到任何远程仓库，push 不因"已授权自主运行"而默许，必须等用户显式授权。
- **破坏性重构授权（硬原则）**：符合一般工程经验/普适性/合理架构设计且经分析确实优于现有体系及已有代码时，哪怕设计已被文档记录也允许破坏性重构；不禁止修改已有代码，已有代码优先级低于架构正确性与设计统一一致；默认已授权自主推进。
- **大范围破坏性重构分支政策（硬原则）**：无法确认边界/危害程度的破坏性重构，100% 授权在独立分支（不污染 main 与 unsafe-vibe-dev，不污染任何计算机环境与用户目录）任意实验；仅当独立隔离分支也无法确定技术路线时才阻塞；独立分支禁止直接合并到 unsafe-vibe-dev 或 main，确认技术路线后仅允许手动单独更新 unsafe-vibe-dev；永远不允许触碰主干分支（main）的代码。
- **设计哲学（用户工作习惯提炼，`design-philosophy` skill）**：系统级统一性——单一权威源（反碎片化）、设计语言统一、设计思路统一、机制同构、模块配合模式统一、系统一致性先于局部便利、宏观设计反思、概念命名与粒度统一。设计取舍时逐条对照。
- **决策纪律**：需用户拍板的决断项可大胆激进选方案；底线=架构原则/代码质量原则/非妥协/非 tricky/非临时兼容层/大方向主线。
- **工作模式定论**：禁 compat shim/胶水/tricky/过程式硬编码；质量优先；原则优先于行为维持；可推翻 IBCI 自身设计缺陷。
- **文档治理**：设计/决策先写任务控制文档（`tasks_docs/`），**不写进技术手册 `docs/`**（用户明确要求）；落地后按治理择机写入。
- **隔离运行的自我进化窗口**：跨引擎通信现阶段不做，保持文件/序列化机制，仅维护 + 同步演进。
- **不做跨进程/CPU 并行**（性能瓶颈在 IBCI 包装）。
- **工作流**：每任务走 code-workflow Phase 0-5 + 质量门 + design-philosophy 对照 + 全量 pytest 零回归。

## 六、待决项 / 待清理

- **待决**：任务 C-F 已授权未完成；任务 C 实施细节（thread 构造语法/容器成员/既有内核处置）已授权自主决策（见 THREAD_DESIGN_REVISION §八）。
- **待清理**：本 `_HANDOFF.md` 交接后删除；旧 spawn/join/cancel 相关代码与测试在任务 F 中删除。
- **非目标**：media Phase 4、跨进程/CPU 并行、跨引擎通信、完整通用异步（async 函数/生成器）、线程无损挂起/恢复、用户级泛型类、HM 约束求解。
- **未 commit**：无（任务 A、B 已全部 commit；`.opencode/opencode.json`、`.opencode/tui.json` 为 opencode 配置，未纳入版本控制）。

---

> 交接完成阶段：本文件由下一 session 交接后删除。下一 session 启动前必须完整读取 §三（自主运行配置）与 §四（当前工作状态）。