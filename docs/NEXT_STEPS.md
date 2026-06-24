# NEXT_STEPS — 当前最紧要项

> 本文档**只**记录当前周期内最紧要、可立即开工的下一步。
> 阻塞 / 等前置项见 `docs/PENDING_TASKS.md`；历史归档见 `docs/COMPLETED.md`。
> 已知语言级限制见 `docs/KNOWN_LIMITS.md`。
>
> **最后更新**：2026-06-24（全量分析体检 + P0/P1/P2 + 6 god module 拆分 + Phase 3 基础完成；基线 1011 passed）

---

## 当前测试基线（每次开新分支前必须复跑确认）

```bash
python -m pytest tests/ -q --tb=no --no-header
```

**2026-06-24 实测结果**：`1011 passed, 5 skipped`（0 failures，无环境变量 workaround）

> ✅ 基线可信。5 个 skipped：2 个设计限制（`INV-LAMBDA-3`/`INV-SCOPE-1`）+ 3 个层级元测试白名单（混合文件待拆分）。

---

## ✅ P0 / P1 / P2 已完成（2026-06-24）

> 详见 `docs/COMPLETED.md` 2026-06-24 条目和 `docs/worklogs/` 下的 4 份工作日志。
> 此处不再展开（遵守单点真理规则 #6）。

---

## P0（当前最紧要）：Phase 3 多模态 — 用户面 I/O API + e2e 测试

> **前置条件全部满足**：ADR-007~012 解除全部决策阻塞；snapshot 分发 `isinstance` 修复已完成；audio/image/video axiom + 运行时类 + 注册路径已完成。

**已完成部分**：
- ✅ `AudioAxiom`/`ImageAxiom`/`VideoAxiom`（`has_payload_prompt_cap`，`__payload_prompt__` 返回结构化 content block）
- ✅ `MediaStorage`（Phase 3 纯内存，ADR-007）
- ✅ `IbAudio`/`IbImage`/`IbVideo`（`@register_ib_type`，IbValue 子类）
- ✅ 完整注册路径 + `builtin_initializer` 方法绑定
- ✅ 36 个单元测试（公理能力 + payload prompt + 存储属性）

**待做**：
1. **`ibci_file` 插件扩展**：添加 `read_audio(path)` / `read_image(path)` / `read_video(path)` 函数
   - 文件：`ibci_modules/ibci_file/core.py` + `ibci_modules/ibci_file/_spec.py`
   - 每个 `read_*` 读取文件字节 → 构造 `MediaStorage` → 通过 `registry` 装箱为 `IbAudio`/`IbImage`/`IbVideo`
   - 需要访问 `registry` 以获取 `IbClass` 并构造对象（参考现有 `file.read` 的实现模式）
2. **e2e 集成测试**：MOCK 模式下的多模态行为表达式
   - 验证 `audio x = file.read_audio("test.wav")` 能编译并执行
   - 验证 `@~ 识别 $x ~` 能正确构建多模态 payload（通过 MOCK 拦截验证 content block 结构）
   - 验证 `__payload_prompt__` 被正确分发（而非 `__to_prompt__`）
3. **IBCI 语法级使用验证**：确保以下代码在 MOCK 模式下端到端工作：
   ```ibci
   import file
   import ai
   ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
   audio recording = file.read_audio("test.wav")
   str transcript = @~ MOCK:STR:transcript 识别 $recording ~
   print(transcript)
   ```

**设计文档**：`docs/MULTIMODAL_BEHAVIOR_DESIGN.md` §七 Phase 3 + ADR-007~012

**预估工作量**：3-5 天

---

## P1 候选：PT-TEST-4 覆盖缺口填补（4/5 区域待补）

> 已完成 1/5：`runtime/path/`（85 个测试 + 5 个 bug 修复）。

**待做**（按优先级排序）：
1. **`core/runtime/serialization/` round-trip 测试**（~6-8 个测试，中高复杂度）
   - `serialize → deserialize == identity` 属性测试
   - 零当前覆盖，回归风险高（影响 HostService save/load_state）
2. **`core/engine.py` 生命周期测试**（~4-6 个测试，中高复杂度）
   - 封印后重入抛 `PermissionError`、compile-then-execute、跨盘 isolated root
3. **`core/runtime/objects/kernel/` `__getitem__` 契约**（~6-7 个测试，中复杂度）
   - list/tuple/dict/str getitem 边界情况（负索引、缺键、type_ref 保持）
4. **`core/runtime/host/service.py` collect 委托**（~2-3 个测试，中复杂度）
   - 大部分路径已由 Engine 层 e2e 覆盖，仅 `HostService.collect` 无 orchestrator 委托分支未测

**预估工作量**：~3 天

---

## P1 候选：PT-ARCH-7 Phase 4-5（剩余 10 处静默吞异常）

> 已完成 Phase 1-3：7 处关键修复 + 4 处裸 except: 收窄。core/ 中零裸 except:。

**剩余 10 处** `except Exception: pass`（全部有注释说明意图，属低-中风险）：
- 6 处 fallback 链（`_prompt.py` × 3、`base.py` × 2、`_shared.py` × 1）—— 后续有默认行为，`pass` 是 fallback 触发
- 3 处文档化的有意跳过（`engine.py` collect 跳过不可转换值、`interpreter.py` 预评估允许失败、`_scheduler.py` `__del__` 析构）
- 1 处 `media.py` `_extract_media_storage` helper（新增代码）

**修复方式**：纯日志添加（`debugger.trace`），无行为变更。可增量提交。

**预估工作量**：~4 小时

---

## P2 候选：PT-ARCH-5 Group 3（CPS/non-CPS 薄提取）

> Group 1+2 已完成。Group 3 剩余 5 对 sync/CPS 方法。

**可做**：2 对薄 `invoke_*` 方法（各 7-18 行，委托到 `execute_*` + 相同后处理）→ 提取共享后处理 helper
**推迟**：3 对 `execute_*` 方法（各 ~100 行，body 90% 相同但 segment evaluator 不同）→ 需先统一 `_evaluate_segments`/`_evaluate_segments_cps`

**预估工作量**：薄提取 ~2h；完整统一 ~6h（推迟）

---

## P3 候选（远景；详见 PENDING_TASKS）

- 多模态 Phase 4：`media` 全模态容器 + 响应解析
- 多模态 Phase 5：磁盘卸载与生命周期管理
- `isinstance()` 运行时类型检查
- 二层 IR 路线
- 用户级泛型 (`class Box[T]:`)
- 协程层（搁置中，详见 `docs/COROUTINE_DESIGN_NOTES.md`）

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
- 同一时刻只主推一项 P0 任务（或一项 P1）；其余项保留待选。
- 任何改动公理层公约或语义错误集的任务，需在分支早期跑全量 pytest 评估破坏面。
- 每项完成后，把摘要追加到 `docs/COMPLETED.md`，并把对应条目从本文件移除。
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
8. **重大架构决策必须写 ADR**。新增决策在 `docs/decisions/` 建对应 ADR 文件。
