# 阶段 C 试用工作计划（临时任务控制文档）

> **性质**：临时任务控制文档（`_` 前缀惯例）。记录阶段 C（VISION-3 真实 LLM 全面试用重启）
> 的试用项目更新补全计划、执行进度与结论。完成后收敛进 `trials/INDEX.md` + `NEXT_STEPS.md`
> 并删除（git 承载）。恶意边界测试起点清单见 `tasks_docs/_trial_edge_catalog.md`。

## 〇、结论先行：迁移面审计（2026-08-21）

**HANDOFF 中"既有 T01-T09 用例大量基于已删语法"的判断与实际不符**——P4c-2c 阶段已完成
trials 迁移（12 case + docs 全面同步）。本 session 全量扫描证实：

- 全 trials `.ibci` 仅 **2 个文件**命中旧语法字样（`llm func` / `__llmretry__`），且**正文已是
  新 `__llm_call__` 语法**，仅头部注释含旧语法迁移叙述。
- **8 个文件**的 `# doc:` 指针指向已重编删除的 `docs/syntax/09_llm.md`（现为
  `08_llm_callable.md`）。
- **已修复**（本 session，9 文件）：`# doc:` 指针 `09_llm.md → 08_llm_callable.md` +
  清理注释中的旧语法迁移叙述（CONTRACT_FORMAT §一：注释只保留功能说明 + `# doc:` 引用）。
- **追加发现（2026-08-21 修正）**：**4 个 stream 用例（T08 D5-01/D5-02/D5-08 + T01 D2-35）
  用已删的字符串形态 `stream_call(sys,user)` / `stream_channel(sys,user)`**——已迁移到新
  llm 可调用实例形态（与内核判别测试同形态）；`docs/syntax/11_modules.md:112` 陈旧指针
  `09_llm.md → 08_llm_callable.md` 一并修正。
- 全 trials 其余用例引用文档（01-15 章 / KNOWN_LIMITS / architecture / howto）均存在，
  章节级漂移留待阶段 C 结束统一文档复核时核对。

**迁移面结论**：旧语法依赖≈0（P4c 已迁移 + 本 session 补清 4 个 stream API 残留），
**阶段 C 主要工作量 = 新特性覆盖补全**（五大地基重构后新特性在既有 T01-T09 中覆盖不足）
+ 恶意边界测试。

## 〇.1 本 session 工具修复（HARNESS 处置）

- **进程内 mock 流式分块保真缺口已修复**：`provider_impl.py::RecommendedProvider.stream()`
  test_mode 分支丢弃 `MOCK:STREAM` 的 `chunks`（只回整块文本）→ stream_channel 逐块 recv
  报 `communication object is closed`。改为 `iter(chunks if chunks else [content])`（与
  HTTP mock 路径同构）。回归测试 +1（`tests/runtime/test_streaming.py`）。全量 pytest
  **3183 passed / 1 skipped 零回归**（+1）。

## 〇.2 本 session 真实缺陷修复（KERNEL_ISSUE-LLM-4）

- **llm-callable `expected_type`=裸用户类名不解析**：装配直接把裸名（"Resp"）传给解析器，
  VTableParsingStrategy `get_class` 因注册表键为 module 限定名（cases.<入口>.Resp）而 miss →
  `__from_prompt__` 不生效、退化返回 str（docs §8.5 宣称用户类经 __from_prompt__ 解析）。
  修复：装配时按 callable 类 module 限定裸 expected_type（对齐行为路径 node_to_type 限定
  语义），内置/容器/已限定名保持原样。回归测试 +2（test_llm_callable_unified.py），T08 D4-05
  真实 LLM 转 PASS。全量 pytest 3185 passed / 1 skipped 零回归（+2）。
- **T08 D4-01 转义用例 bug**（`\\"` → `\"`，P4c 迁移遗留）：修复后 list/dict 容器解析真实 LLM 转 PASS。

## 一、新套件规划（覆盖 HANDOFF_SESSION §6.1 九大评估面）

| 套件 | 主题 | 覆盖评估面 | mock/LLM |
|------|------|-----------|----------|
| `T10_llm_callable` | llm 可调用类全面（直接调用/装配 dict/prompt_slots/expected_type/参数绑定/`__intent__` 三层改写/`__retry__` 高阶化/实例渲染/run_batch 逐项参数化） | llm 可调用类 + run_batch | mock 先行 + LLM 层 |
| `T11_stream_batch` | stream 流式（stream_call/stream_channel 逐块 recv/await 完整文本/流式错误）+ run_batch 批量（行为逐项绑参/批量并发/错误传播） | stream + run_batch | mock 先行 + LLM 层 |
| `T12_overlay_protocol` | 覆层机制（impl overlay 声明/with 作用域/跨根并发隔离/SEM_OVERLAY_UNUSED 告警/快照序列化影子条目）+ prompt 协议族五成员（to_prompt/from_prompt/outputhint/payload/validate + `__retry__` 调用级/`__intent__` 可选） | 覆层 + 协议族 | mock 先行 + LLM 层 |
| `T13_intent_ctx` | 意图一等值嵌入（行为/可调用值经 `__to_prompt__` 嵌入意图/`@-` 按值派生渲染/snapshot 意图冻结/lambda live）+ intent_context OOP 方法族（push/pop/fork/merge/combine/clear/use/get_current/缺参 fail-fast） | 意图一等值 + intent_context | mock 先行 + LLM 层 |
| `T14_fs_optional` | fs 模块（open/read/read_bytes/write/overwrite_flag/exists/remove/file_handle 只读/沙箱限制）+ Optional/容器解析（值模型/泛型特化/值语义） | fs + Optional/容器 | mock（无 LLM 依赖） |
| `T15_edge_malicious` | 恶意边界测试：`_trial_edge_catalog.md` 33 项起点清单逐条对抗性用例 + 自行扩展边界（可能存在缺陷/可能有问题/开发者没考虑到的场景） | 全评估面边界 | mock 先行 + LLM 层 |

> 既有 T01-T09 作为回归套件保留（阶段 C 末/阶段 C 中按需全量重跑对照新内核）。

## 二、执行顺序与节奏

1. **mock 层先行**（每套件）：建套件骨架 + 用例 → `run_one.py`/`run_batch.py --mock-only`
   验证契约 → 全 PASS 才算套件基础就绪（快速、确定）。
2. **真实 LLM 层**：`curl -s -m 5 http://127.0.0.1:1234/v1/models` 探测可用 → LLM 全量回归。
3. **恶意边界**（T15）与 1/2 并行穿插，按 `_trial_edge_catalog.md` 逐条设计对抗性用例。
4. **缺陷闭环**：发现 → INDEX 生命周期分类登记 → 根因修复（tests/ 补回归）→ 触发用例核销。
5. 每套件落地后更新 `trials/INDEX.md`；套件建成用 `run_batch.py` 批量回归。

## 三、执行纪律

- 用例头部断言（`# expect-class/out/exit/code/llm`）必填；无断言 = HARNESS。
- 注释只保留功能说明 + `# doc:` 引用；禁任务代号/历史叙述/时间戳。
- 每个用例 `--timeout` 必填（死循环保护）；mock 用例 `# expect-llm: false`。
- 只记录不修复优先（优先确定性记录可溯源）；不为规避缺陷改套件。
- mock 指令语言（`ibci_modules/ibci_ai/mock_scenario.py`）：`MOCK:INT/STR/FLOAT/BOOL/LIST/DICT`
  /`REPAIR[:fallback]`/`SEQ:[v1,v2,...] key`（FAIL→歧义哨兵）/`FAIL`/`TRUE`/`FALSE` +
  控制指令 `SLEEP:<ms>`/`ERROR:<code>`/`STREAM:<a|b|c>`。
- 套件骨架（CLASSIFICATION §五）：`DESIGN.md` + `cases/` + `api_config.json` +
  `harness/run_one.py`（软链 `_toolkit/run_one.py`）+ `logs/` + `REGISTER.md`。

## 四、进度记录

- [x] 迁移面审计 + 9 文件注释/指针修复 + 4 个 stream API 迁移 + docs 指针修正（2026-08-21）
- [x] T10_llm_callable（mock 层 9 PASS + 4 GUARD，BOUNDARY-LLM-4 登记）
- [x] T11_stream_batch（mock 层 5 PASS）+ 进程内 mock 流式分块缺口修复（回归 +1）
- [x] T12_overlay_protocol（mock 层 6 PASS + 3 GUARD）
- [x] T13_intent_ctx（mock 层 4 PASS + 1 GUARD，BOUNDARY-LLM-5 登记）
- [x] T14_fs_optional（mock 层 7 PASS + 2 GUARD，沙箱守卫确认无漏洞）
- [x] T15_edge_malicious（mock 层 16 例：9 PASS + 6 GUARD + 1 LIMIT，无内核缺陷）
- [ ] 真实 LLM 层全量回归（qwen3.6-35b-a3b）
- [ ] 压力维度扩展（>4k token / 多轮 / 批量并发 / 多模块交叉）
- [ ] 缺陷登记 + 根因修复 + 核销
- [ ] trials/INDEX.md 更新 + 阶段 C 末文档复核
