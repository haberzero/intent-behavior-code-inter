# 机器更换交接文档（HANDOFF_MACHINE_CHANGE）

> **用途**：开发将更换机器。本文是**自包含**的完整交接——新机器上 clone 本仓库 + 按下述
> 步骤重建环境 + 按任务清单续作，**不遗漏任何内容或信息**。
> **日期**：2026-09-09 ｜ **分支**：`unsafe-vibe-dev`（已 push origin，见 §6）
> **安全**：本文**不含任何密钥**（api_config.json 的 api_key 需你另行重新提供，见 §4.2）。

---

## 0. 一句话现状

IBC-Inter（实验性意图驱动混合编程语言）当前处于 **Round5 自指性体系架构**主线：
LLM 作低阈值基础细胞 + 确定性架构（显式生成器/自描述/自修改安全/验证/观测/成本）。
已完成 P7 进程隔离 + Round4 基础智能（memory/ai.recall/meta.compile 行为值）+
Phase C 的 C1（selfref 地基）+ C2（selfref.verify 三关门）；下一步 C3（自修改 + 回滚）。

---

## 1. 项目身份与战略方向

- **仓库**：`git@github.com:haberzero/intent-behavior-code-inter.git`
- **定位**：实验性 IBCI 语言（Python-style 确定性代码 + LLM 非确定性推理融合）。
- **战略主线**（round5 自指性转向，试用方 2026-09-09 需求单驱动）：
  - **横切原则**：可靠性与自指性来自**确定性代码/架构**，非 LLM 智力。
  - LLM = 低阈值基础细胞（仅语义选择/分类/草稿/先验；**不产结构/不写 ibci/不做判定**）。
  - 架构 = 确定性计算机（结构 + 记忆 + **显式代码生成器** + 验证 + 观测 + 成本）。
- **权威需求源**（外部，不在本仓库）：
  - `/home/dsh/proj/ibci-trial/docs/ibci_round5_selfref_requirements.md`（SR-1..5）
  - `/home/dsh/proj/ibci-trial/docs/ibci_round4_vision_requirements.md`（MEM/REC/SELF/OBS/COST/TYPE）
  - **注意**：ibci-trial 是独立工作区；换机器后需一并迁移/重建（见 §7）。

---

## 2. 如何获取代码

```bash
git clone git@github.com:haberzero/intent-behavior-code-inter.git
cd intent-behavior-code-inter
git checkout unsafe-vibe-dev   # 开发主线（本交接的全部工作已 push 到此分支）
```
- `main` 永不触碰（冻结）。
- 工作/里程碑分支 = `unsafe-vibe-dev`（`free-explore` 已删除，内容已并入）。

---

## 3. 环境重建（gitignored，换机器会丢失——须重建）

### 3.1 Python 虚拟环境（.venv）
```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```
- 需要 Python 3.12.x（旧机 = 3.12.3）。
- 唯一测试命令：`.venv/bin/python -m pytest tests/`（pytest.ini 已配 `-q --tb=short --strict-markers`）。
- `tests/conftest.py` 强制 pytest basetemp = `.tmp_pytest/`（仓库不变量）。

### 3.2 api_config.json（LLM/embedding 配置 + 密钥——gitignored）
仓库根创建 `api_config.json`，结构如下（**`api_key` 需你从 SiliconFlow 重新取得填入**）：
```json
{
  "defaults": { "timeout": 60.0, "retry": 3, "auto_intent_injection": true, "mock": false },
  "providers": { "siliconflow": { "base_url": "https://api.siliconflow.cn/v1", "api_key": "<你的 SiliconFlow key>" } },
  "models": {
    "default": {
      "provider": "siliconflow", "model": "Qwen/Qwen3.6-35B-A3B", "reasoning": false, "timeout": 180.0,
      "extra_body": { "enable_thinking": false, "chat_template_kwargs": { "enable_thinking": false } }
    },
    "qwen35": {
      "provider": "siliconflow", "model": "Qwen/Qwen3.6-35B-A3B", "reasoning": false, "timeout": 180.0,
      "extra_body": { "enable_thinking": false, "chat_template_kwargs": { "enable_thinking": false } }
    },
    "emb-qwen": { "provider": "siliconflow", "model": "Qwen/Qwen3-Embedding-0.6B", "kind": "embedding", "timeout": 60 }
  },
  "default_model": "default"
}
```
- 端点 = SiliconFlow `https://api.siliconflow.cn/v1`（可自由使用）。
- chat = `Qwen/Qwen3.6-35B-A3B`（思考模型；双字段抑制 `enable_thinking=false` = 非思考基线形态）。
- embedding = `Qwen/Qwen3-Embedding-0.6B`（~1024 维，MRL 32–1024）。
- **密钥来源**：SiliconFlow 控制台。**切勿**把 key 写进任何提交/文档（本文刻意不含 key）。

### 3.3 AGENTS.local.md（机器事实——gitignored）
按 `AGENTS.md` 指引重建：记录本机解释器路径 + venv 激活 + LLM 端点/密钥通道。
（旧机内容可参考本文 §3.1/§3.2 + `AGENTS.md`；机器无关规范见 `trials/_toolkit/LLM_SERVICE.md`。）

### 3.4 环境验证
```bash
.venv/bin/python trials/_toolkit/probe.py          # 端点/鉴权/模型校验（需 api_config 就位）
.venv/bin/python -m pytest tests/ -p no:warnings   # 全量（基线见 §5）
```

---

## 4. 完整任务清单（核心——不遗漏）

### 4.1 已完成（里程碑，git 承载细节）
| 阶段 | 内容 | 状态 |
|------|------|------|
| **P7 进程级隔离** | ihost 子环境 threading→subprocess；LLM 继承跨进程（IBCI_LLM_STATE_FILE）；变量导出协议；资源限制（RLIMIT）；判别测试 9 例 | ✅ |
| **Round4 B MEM** | `memory` 一等值类型：encode/retrieve/promote/demote/tier/tier_size/tier_keys/set_capacity/content_hash/verify/consolidate/prune/keys/len/export | ✅ |
| **Round4 B REC** | `ai.embed(side,instruct,dimensions)`（query/doc 不对称 + MRL）；`ai.recall(query,corpus,k,instruct,dimensions)` 低层向量原语（doc 内容缓存）；`ai.recall_stats`（COST 遥测）；`mem.search`（文本召回）+ `mem.corpus`（语料收集） | ✅ |
| **Round4 B 序列化** | memory 完整序列化/水化（save_state/load_state，含 events 审计链） | ✅ |
| **Round4 B OBS** | `memory.snapshot()`（活体快照） | ✅ |
| **TYPE-1 行为作值** | `meta.compile(code)` 返回编译产物摘要 dict（{ok,n_modules,entry_module,n_top_stmts,n_funcs,func_names,n_classes,class_names}） | ✅ |
| **round5 整合** | 吸收试用者 f5a6e356(REC-6)/af5c9c6e(TYPE-1) + `ai.recall` 设计调和（单一权威/机制同构） | ✅ |
| **Phase C C1** | `selfref` 模块地基：SR-1 `describe()`（真内省）+ SR-3 `constitution()` + SR-2 `register_template`/`templates`/`render` | ✅ |
| **Phase C C2** | `selfref.verify(code,test_call,expected)` 三关门（编译+执行+结果，非仅编译）+ 15 判别测试 | ✅ |

### 4.2 进行中 / 下一步（Phase C 剩余 + Phase D）
**Phase C（自指性架构一等化，最高优先）**：
- ✅ C1：SR-1 自描述原语
- ✅ C2：SR-2 生成器（模板/组装）+ SR-3 verify 三关门
- **🔄 C3（下一项）**：SR-3 自修改安全——`selfref.modify(name, params, test_call, expected)`
  （render → verify 三关 → 采纳/拒绝，确定性 + 审计 append-only + 回滚经 memory 快照）
  + 不变量保护（constitution 自身不可被 modify 修改）
- **⏳ C4**：SR-5 LLM 阈值纪律（LLM 调用声明 role[semantic/content/prior] + 静态检查[结构/判定路径零 LLM]）
- **⏳ C5**：OBS 深化（自修改审计/召回决策审计面）

**Phase D（类型基底 + 行为值直接执行 + 收尾）**：
- **⏳ D1**：SR-4 行为值直接执行/组合（`meta.compile` 产物 `run(behavior_value)` 一等可执行；当前经 ihost.run_code 源串执行）
- **⏳ D2**：TYPE-2（谓词/函项约束泛型——与 VISION-4 类型理论加固整合）
- **⏳ D3**：SELF-5（自修改回滚一等化）+ COST-2（投机验证/确定性优先路由）

### 4.3 长期任务（状态单点真理 = `PENDING_TASKS.md`）
| 代码 | 内容 | 状态 |
|------|------|------|
| PT-DECIDE-2 | 供应商感知的模型思考禁用机制（后端强制思考场景的探测/降级语义） | 已解封，重估中 |
| PT-FEAT-17 | N3 弱模型输出漂移度量（logprobs 通道） | shelved（方向保留） |
| PT-FEAT-5 | 语义错误用户友好化 + 诊断 + CI/CD | 待推进 |
| PT-FEAT-6/12 | CompilationResult 精简 / AST UID 字段 | 远期（管线稳定 ≥1 月） |
| PT-DOC-4 | 文档示例验证闭环 | 待评估 |
| PT-TEST-2 | e2e 测试覆盖率提升 | 待推进 |
| PT-AUDIT-1/2/3 | 周期代码异味/复杂度/复核审计 | 周期支线 |
| VISION-4/5 | 类型理论加固 / 函数式地基 | user-gated（远期） |
| VISION-6 | 内核工程化（P1-P6 ✅，P7 ✅） | 主线完成 |
| PT-SEALED-1 | media Phase 4（多模态） | 彻底封存（短期不做） |

**远期不处理**：Hindley-Milner 约束求解 / Rust 内核重写 / 线程无损挂起恢复。

### 4.4 间隙期支线（主线阻塞/间隙时按优先级）
1. 质量维护/代码健康（quality-maintenance Tier A/B）
2. 文档对账/残留扫描
3. 恶意边界未测项（trials mock 层）
4. 周期审计（PT-AUDIT-1/3）

---

## 5. 测试基线（以实跑为准，不冻结）

- **末次全量**：`3992 passed / 1 skipped`（2026-09-09，含 15 个 selfref 判别测试）。
- 唯一命令：`.venv/bin/python -m pytest tests/`。
- selfref 专项：`tests/runtime/test_selfref_module.py`（15 例）。
- 每批交付纪律：全量零回归 + commit + 同步 NEXT_STEPS/WORKLOG/HANDOFF。

---

## 6. 分支与 push 状态

- **`unsafe-vibe-dev`**（开发主线）：已 push origin（截至本交接 = `fdfb1c81`）。
  - 最近 push：`11a893a7..123a341f`（13 提交，用户 2026-09-09 授权）。
  - 本交接后新增：`219145da`(C1 docs) + `fdfb1c81`(C2 verify)——**见 §9 push 指令**。
- **`main`**：冻结（0555d1d4，永不触碰）。
- **`free-explore`**：已删除（内容已 ff 并入 unsafe-vibe-dev）。

---

## 7. 协作状态（ibci-trial 试用方）

- ibci-trial 是**独立工作区**（`/home/dsh/proj/ibci-trial`），有自己的 git + 自主 agent。
  **换机器需一并迁移**（或在其新位置重建 clone + 其 .venv + 其 ibci-runtime 钉扎）。
- 关系：本仓库 = IBCI 上游；ibci-trial = 试用方（只读上游 + 提需求 + 本地实验）。
- **已交接**（2026-09-09）：
  - `TRIAL_ANNOUNCE_2026-09-09.md`（本仓库根，gitignored——换机器会丢，见 §8）
  - `/home/dsh/proj/ibci-trial/docs/UPSTREAM_ANNOUNCE_POINTER_2026-09-09.md`（试用方工作区）
  - 指引：试用方重新钉扎 ibci-runtime 到上游 tip + 回收其本地补丁（f5a6e356/af5c9c6e 已吸收）。
- 试用方当前进展：e40-e52 实验（自指性 PoC：e50 自描述 / e51 自修改 / e52 显式生成器）。
  其 round5 需求单（SR-1..5）= 本仓库 Phase C/D 的直接驱动。

---

## 8. 换机器会丢失的 gitignored 工件清单（重要）

以下**不在 git**（push 不覆盖）。区分两类：**须重建**（我的连续性依赖）vs **出站已交付**（试用方
自存，非我的丢失风险）：

| 文件 | 内容 | 性质 / 处置 |
|------|------|---------|
| `api_config.json` | LLM/embedding 配置 + 密钥 | **须重建**（§3.2；key 需重取） |
| `AGENTS.local.md` | 本机环境事实 | **须重建**（§3.3） |
| `.venv/` | Python 环境 | **须重建**（§3.1） |
| `TRIAL_ANNOUNCE_2026-09-08/09.md` | 试用方交接公告 | **出站（我→试用方）·已交付·非丢失风险**：公告指针已写入试用方工作区
  （`ibci-trial/docs/UPSTREAM_ANNOUNCE_POINTER_2026-09-09.md`），试用方会读入并记入其自身
  `AUTONOMOUS_LOG.md`（对方自存）；本仓库根的文件 gitignored，丢了不影响连续性（内容见 §7 +
  git 提交信息，可重写）。 |
| `.tmp_*` / `.tmp_pytest/` | 临时文件 | 无需 |

**手动迁移建议**：旧机器上把 `api_config.json` + `AGENTS.local.md` 拷到新机器（含密钥，注意
安全传输）；或直接在新机器按 §3 重建。

---

## 9. 本交接后的 push（用户已授权）

本交接文档 + C2 提交需 push 到 GitHub 以确保新机器 clone 即得全部工作。
（用户 2026-09-09 明确授权 push；push 后 unsafe-vibe-dev 含本交接文档。）

---

## 10. 工作纪律（新机器延续，权威源 = AGENTS.md）

- **禁 push 除非用户明确授权**（硬原则；本 §9 的 push 已获授权）。
- 破坏性重构授权（符合工程经验/普适性/合理架构且经分析确实优于现有体系时默认已授权）。
- 工作模式定论九条（禁 compat shim/胶水/tricky；协议驱动；质量优先；原则优先于行为维持）。
- 每任务：code-workflow Phase 0-5 + 全量零回归 + 文档同步 + WORKLOG 落账。
- 命名/路线/架构由开发智能体自主决定（用户 2026-09-09 授权），以长远收益节律为准。

---

## 11. 关键设计裁定（防新机器误解，详 = WORKLOG）

1. **selfref 模块名**（非 `self`）：IBCI 类方法首参即 `self`，模块名 `self` 会冲突。
2. **ai.recall 调和**：`ai.recall(query,corpus,...)` = 低层向量原语（吸收试用者版）；
   `mem.search` = 文本召回；记忆感知向量召回 = 调用方组合（`ai.recall(query, mem.corpus(scope), ...)`），
   非 memory 方法（embedding 服务归 ai 插件持有，memory 不持有引用）。
3. **selfref = core-level plugin**（同 meta/idbg 族，持系统级状态：宪法 + 模板注册表，每引擎一实例）。
4. **SR-5 结构性保证**：selfref 零 LLM（组装/内省/判定全确定性）；LLM 仅调用方提供低阈值 params。
5. **verify 三关门**：编译 + 执行 + 结果（非仅编译——e49 证明仅编译不足）。
