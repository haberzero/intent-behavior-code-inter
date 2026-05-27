# NEXT_STEPS — 当前最紧要项

> 本文档**只**记录当前周期内最紧要、可立即开工的下一步。
> 阻塞 / 等前置项见 `docs/PENDING_TASKS.md`；历史归档见 `docs/COMPLETED.md`。
> 已知语言级限制见 `docs/KNOWN_LIMITS.md`。
>
> **最后更新**：2026-05-27（Phase 2 完成；下一步 = Phase 3 多模态内置类型）

---

## 当前测试基线（每次开新分支前必须复跑确认）

```bash
python -m pytest tests/ -q --tb=no --no-header
```

**2026-05-27 实测结果**：`832 passed, 2 skipped`（Phase 2 `__payload_prompt__` 协议完成，全部通过）。

---

## 当前最紧要：Phase 3 — `audio` / `image` / `video` 内置类型

**前置条件**：
- ✅ Phase 1 命名模型路由
- ✅ Phase 2 `__payload_prompt__` 协议 + 多模态 payload 构建

**目标**：实现 IBCI 语言级的多模态数据类型，使用户可以：
```ibci
audio recording = file.read_audio("interview.wav")
str transcript = @WHISPER~ 识别 $recording 里的内容 ~
```

**具体待做**：
1. 新增 `AudioAxiom` / `ImageAxiom` / `VideoAxiom` 公理（`core/kernel/axioms/primitives.py`）
   - 每个公理实现 `has_payload_prompt_cap = True` + `__payload_prompt__` 返回对应结构化 content block
2. 新增 `IbAudio` / `IbImage` / `IbVideo` 运行时对象类（`core/runtime/objects/builtins.py`）
3. 新增 `MediaStorage` 存储后端（`core/runtime/objects/media_storage.py`）
4. 注册新类型到内核（通过 axiom 驱动，`builtin_initializer.py`）
5. 决策：作为类型关键字还是普通类名（设计文档建议作为关键字，与 `str`/`int` 同级）
6. 测试：单元测试 + e2e 测试（含 MOCK 模式下的多模态行为表达式）

**关键设计决策待定**：
- 媒体数据存储策略（内存 vs 磁盘卸载 — Phase 5 课题，Phase 3 先实现内存方案）
- Lexer/Parser 是否需要改动（如果作为关键字则需要）
- 媒体文件 I/O API 的形态（内置函数 vs 模块方法）

**预估工作量**：3-5 天

---

## P1 候选：PT-SEM-1 Semantic Pipeline 生产就绪化

**前置条件**：Semantic 4-Phase pipeline 已稳定运行 ✅；nonlocal 完成后闭包语义全链路验证通过 ✅

**具体待做**：
1. **错误信息优化**：当前 `SEM_xxx` 错误码附带的消息偏技术化，需转化为用户友好表述
2. **诊断工具**：为符号表、类型绑定、行为依赖图提供可视化导出（JSON/dot 格式）
3. **性能基准**：建立编译时间基准测试（针对 100+ 行脚本）
4. **CI/CD 集成**：语义分析测试套件纳入 CI 流水线自动运行

**预估工作量**: 15-20 小时

> 注：本项由 PENDING_TASKS PT-SEM-1 提升。如有更紧迫需求出现，可替换。

---

### 确认为设计决策（不修复）

| 测试 ID | 原因 | 处理 |
|---------|------|------|
| **INV-LAMBDA-3** | IBCI 无 walrus (`:=`) / lambda 体赋值语法 | 保持 SKIP，标注为"设计限制" |
| **INV-SCOPE-1** | SEM_002 禁止 if-block 内重声明同名变量 | 保持 SKIP，标注为"设计限制" |

---

## P3 候选（远景；详见 PENDING_TASKS）

- `isinstance()` 运行时类型检查语法与 VM handler
- 二层 IR 路线（结构 IR + 执行 IR）
- 公理 + 元数据 LLVM 化
- 用户级泛型 (`class Box[T]:`)
- `ProtocolMethodRegistry` 完整统一解决方案

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
