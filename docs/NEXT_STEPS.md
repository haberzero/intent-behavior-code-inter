# NEXT_STEPS — 当前最紧要项

> 本文档**只**记录当前周期内最紧要、可立即开工的下一步。
> 阻塞 / 等前置项见 `docs/PENDING_TASKS.md`；历史归档见 `docs/COMPLETED.md`。
> 已知语言级限制见 `docs/KNOWN_LIMITS.md`。
>
> **最后更新**：2026-05-28（调整优先级：多模态 Phase 3 为 P0，协程搁置）

---

## 当前测试基线（每次开新分支前必须复跑确认）

```bash
python -m pytest tests/ -q --tb=no --no-header
```

**2026-05-28 实测结果**：`838 passed, 2 skipped`（super() 修复 + Phase 2 多模态 payload 均通过）。

---

## P0（当前最紧要）：Phase 3 — `audio` / `image` / `video` 内置类型

**前置条件**：
- ✅ Phase 1 命名模型路由（已实现，代码核验：`ibci_modules/ibci_ai/core.py` `target_model` + `register_model`）
- ✅ Phase 2 `__payload_prompt__` 协议 + 多模态 payload 构建（已实现，代码核验：`llm_executor.py:137` `_obj_to_payload` + `_evaluate_segments_cps` 多模态路径）

**目标**：实现 IBCI 语言级的多模态数据类型，使用户可以：
```ibci
audio recording = file.read_audio("interview.wav")
str transcript = @WHISPER~ 识别 $recording 里的内容 ~
```

**具体待做**：
1. 新增 `AudioAxiom` / `ImageAxiom` / `VideoAxiom` 公理（`core/kernel/axioms/primitives.py`）
   - 每个公理实现 `has_payload_prompt_cap = True` + `__payload_prompt__` 返回对应结构化 content block
2. 新增 `IbAudio` / `IbImage` / `IbVideo` 运行时对象类（`core/runtime/objects/`）
3. 新增 `MediaStorage` 存储后端（`core/runtime/objects/media_storage.py`）
4. 注册新类型到内核（通过 axiom 驱动，`builtin_initializer.py`）
5. 决策：作为类型关键字还是普通类名（设计文档建议关键字，与 `str`/`int` 同级）
6. 测试：单元测试 + e2e 测试（含 MOCK 模式下的多模态行为表达式）

**关键设计决策待定**（需项目负责人决断）：
- 媒体数据存储策略（Phase 3 先实现纯内存方案）
- Lexer/Parser 是否需要改动（如果作为关键字则需要加入 KEYWORDS 表）
- 媒体文件 I/O API 的形态（`file.read_audio` vs `audio.from_file`）
- `media` 容器的属性访问模型（固定属性 vs 动态字典）
- `from_response` 协议的接入点（Phase 4 预留 vs Phase 4 再改）
- 多模态变量的 `__snapshot__` / `__restore__` 实现策略

**设计文档**：`docs/MULTIMODAL_BEHAVIOR_DESIGN.md` §七 Phase 3

**预估工作量**：3-5 天

---

## P1 候选：多模态 Phase 4 — `media` 全模态容器 + 响应解析

**前置条件**：Phase 3 完成

**具体待做**：
1. 新增 `MediaAxiom`（`has_multimodal_response_cap = True`）
2. 新增 `IbMedia` 运行时类（`.text` / `.audio` / `.image` 属性）
3. 新增 `MultimodalParsingStrategy`
4. `_call_llm_multimodal` 新路径（返回完整 API response 对象）
5. 评估 D6 决策（是否需要 `_call_llm_raw`）

**设计文档**：`docs/MULTIMODAL_BEHAVIOR_DESIGN.md` §七 Phase 4

---

## P2 候选：PT-SEM-1 Semantic Pipeline 生产就绪化

**前置条件**：Semantic 4-Phase pipeline 已稳定运行 ✅

**具体待做**：
1. **错误信息优化**：`SEM_xxx` 消息转化为用户友好表述
2. **诊断工具**：符号表/类型绑定/行为依赖图 JSON/dot 导出
3. **性能基准**：编译时间基准测试
4. **CI/CD 集成**

**预估工作量**: 15-20 小时

---

## ✅ 已完成（最近归档）

| 完成项 | 完成日期 | 验证方式 |
|--------|---------|---------|
| super() 编译期/运行时对齐修复 | 2026-05-28 | pytest 838 passed |
| Phase 2 `__payload_prompt__` 协议 + 多模态 payload | 2026-05-27 | 13 专项测试通过 |
| Phase 1 命名模型路由 | 2026-05-27 | 6 e2e 测试通过 |

---

### 确认为设计决策（不修复）

| 测试 ID | 原因 | 处理 |
|---------|------|------|
| **INV-LAMBDA-3** | IBCI 无 walrus (`:=`) / lambda 体赋值语法 | 保持 SKIP，标注为"设计限制" |
| **INV-SCOPE-1** | SEM_002 禁止 if-block 内重声明同名变量 | 保持 SKIP，标注为"设计限制" |

---

## P3 候选（远景；详见 PENDING_TASKS）

- 多模态 Phase 5 磁盘卸载与生命周期管理
- `isinstance()` 运行时类型检查
- 二层 IR 路线
- 用户级泛型 (`class Box[T]:`)
- 协程层（搁置中，详见 `docs/COROUTINE_DESIGN_NOTES.md`）

---

## 工作规则

- **每次开新分支前**，先复跑 `python -m pytest tests/ -q --tb=no --no-header`，把当前 pass/fail 计数写在 PR 描述里，不预设上一份文档里的数字。
- 同一时刻只主推一项 P0 任务（或一项 P1）；其余项保留待选。
- 任何改动公理层公约或语义错误集的任务，需在分支早期跑全量 pytest 评估破坏面。
- 每项完成后，把摘要追加到 `docs/COMPLETED.md`（极简时间线），并把对应条目从本文件移除。
- 出现新的紧要项时，按"先评估优先级、再决定是否替换 P0"原则操作。
- **本文件不冻结具体测试通过数字**——任何"X 测试通过"的表述都必须附运行命令或日期锚点。

---

## 维护守则

1. **先复跑、后下结论**。任何关于"测试基线红线"的表述，必须以"附完整 pytest 输出 + 日期 + 分支"的方式说服读者；否则视为待核查。
2. **不要相信"昨日完成"的总结**。`docs/COMPLETED.md` 的最新一两条锚点，必须能用一条具体 git 提交或一次具体 pytest 输出佐证。
3. **示例必须可零配置跑通**。任何"用户跟着 README 复制粘贴"的代码块，必须在 mock 模式下端到端跑通；改动后必须 `python main.py run <示例>` 至少一次。
4. **已知 bug 与已修 bug 之间要勤更**。每发现一个"文档说有但代码已修"的项目，立刻把文档同步更新；反向同理。
5. **跨文件状态保持一致**。`README.md`、`docs/KNOWN_LIMITS.md`、`docs/IBCI_SYNTAX_REFERENCE.md`、`docs/METADATA_ARCHITECTURE.md` 之间对同一语法/限制/架构立场的描述必须用同一组事实；如不一致，以代码与最近一次 pytest 输出为准。
6. **避免重复声明、单点真理**。一条已完成项写一次（在 `COMPLETED.md`），一条已知限制写一次（在 `KNOWN_LIMITS.md`），一条紧要项写一次（在 `NEXT_STEPS.md`）。出现"同一条目在多个文件中以不同状态出现"，立即合并。
7. **新增 AST 字段或侧表前必须先在 `METADATA_ARCHITECTURE.md` 中查证**：禁止"AST 字段 + 侧表"双写真相（同一份语义事实只能有一处可序列化位置）。
