# NEXT_STEPS - 当前最紧要项

> 本文档**只**记录当前周期内最紧要、可立即开工的下一步。
> 阻塞 / 等前置项见 `tasks_docs/PENDING_TASKS.md`；历史归档见 `tasks_docs/COMPLETED.md`。
> 已知语言级限制见 `docs/KNOWN_LIMITS.md`。
>
> **最后更新**：2026-07-21（文档卫生清理：删除全部 ADR，设计知识已迁入技术文档；任务控制文档精简）

---

## ⛔ 工作模式定论（强制，凌驾于本文件一切任务之上）

> **扎实推进，禁止任何形式的快速实现 / 兼容层 / 胶水实现 / tricky 实现。**

1. **禁止 compat shim / 兼容层**：不写"过渡性包装"。新设计就是真设计，旧代码要么真合并、要么真删除。
2. **禁止胶水实现**：不在两个不统一的子系统之间塞字符串拼接 / 魔法哨兵 / 隐式约定来强行粘合。
3. **禁止 tricky 实现**：不靠隐式字符串变换承载语义；不靠"凑巧相等"；不靠书写顺序掩盖数据依赖。
4. **禁止过程式硬编码分发**：同一决策只通过协议驱动（`receive()` / vtable）完成，不在运行流程里写 `if 能力标志位` 分支。
5. **质量优先于速度**：技术债必须先清，再推进依赖它的特性。潜伏 bug 不允许过渡修复。

---

## 当前测试基线

```bash
python -m pytest tests/
```

**2026-07-21 实测结果**：`1176 passed, 7 skipped`（0 failures/errors，win32 / PowerShell）

> 当前基线以实跑为准，不冻结数字。

---

## ⛔ GATED：media Phase 4 - MediaAxiom + IbMedia 全模态容器

> **状态**：所有前置（路径统一、内核原生化、磁盘型存储体系）已全部完成。media Phase 4 **可被提升为 P0**，但需项目负责人明确开工指令。

解锁后的工作：
1. **`MediaAxiom` + 协议驱动的响应解析**：解析多模态响应为 media 对象（协议驱动，非 `if/else`）。
2. **`IbMedia` 全模态组合容器**：modality->payload 映射 + 固定访问器（`.text/.audio/.image/.video`）。
3. **MOCK 模式扩展**：`MOCK:MEDIA:` 合成响应（暂缓，届时再议）。

**Phase 4 关联延迟项**（从 ADR-008/010/013 提取，详见 `PENDING_TASKS.md` §九）：
- 多模态模型注册字段（`modalities`/`endpoint`/`audio_config` 存储）
- 非聊天端点推理绕过（endpoint-based reasoning bypass）
- 磁盘型响应解析协议（`from_response` / bypass register）

---

## P1 后续任务

以下任务不影响 media Phase 4 的开工决策：

1. **PT-ARCH-22**：全项目文件命名清理（暂缓，独立窗口执行）。
2. **PT-ARCH-28**：`file` 模块统一写入 API + 函数动态/命名参数支持（临时 `write_new` 已就位）。
3. **PT-ARCH-29**：命名历史包袱全方位代码卫生清理（代码层零残留，历史文档标注待做）。
4. **PT-ARCH-30**：内置 `file` 模块命名风险清理（长期需重命名，如 `fs`）。

详见 `tasks_docs/PENDING_TASKS.md`。

---

## 工作规则

- **每次开新分支前**，先复跑 `python -m pytest tests/`，把当前 pass/fail 计数写在 PR 描述里。
- **同一时刻只主推一个 P0 阶段**。
- **工作模式定论优先**：任何与"⛔ 工作模式定论"冲突的提议一律以定论为准。
- 任何改动公理层公约或语义错误集的任务，需在分支早期跑全量 pytest 评估破坏面。
- 每个阶段完成后，把摘要追加到 `tasks_docs/COMPLETED.md`，并把对应条目从本文件移除。
- **本文件不冻结具体测试通过数字**。
- 重大架构决策记录在技术文档中（`docs/ARCHITECTURE.md`、`docs/architecture/02_metadata_ast.md`、`docs/architecture/01_principles.md`），不再使用独立 ADR 文件。
