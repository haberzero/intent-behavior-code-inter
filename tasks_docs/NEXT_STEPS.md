# NEXT_STEPS — 当前最紧要项

> 本文件**只**记录当前最紧要、可立即开工的下一步与强制工作约束；长期规划见
> `tasks_docs/PENDING_TASKS.md`。本文件不承载历史完成记录（git 承载）；任务控制
> 治理见 `tasks_docs/GOVERNANCE.md`。
>
> **书写要求**：更新本文档必须按尾部「书写模式」模板与格式书写，保持一致。

---

## ⛔ 工作模式定论（强制，凌驾于本文件一切任务之上）

> **扎实推进，禁止任何形式的快速实现 / 兼容层 / 胶水实现 / tricky 实现。**

1. 禁止 compat shim / 兼容层：新设计就是真设计，旧代码要么真合并、要么真删除。
2. 禁止胶水实现：不在两个不统一的子系统之间塞字符串拼接 / 魔法哨兵 / 隐式约定。
3. 禁止 tricky 实现：不靠隐式字符串变换承载语义；不靠"凑巧相等"；不靠书写顺序掩盖数据依赖。
4. 禁止过程式硬编码分发：同一决策只通过协议驱动（`receive()` / vtable），不写 `if 能力标志位`。
5. 质量优先于速度：技术债必须先清；潜伏 bug 不允许过渡修复。
6. 原则优先于行为维持：既有行为违反一般工程/架构原则时，以原则为准，不以"保持已有行为"为主。
7. 可推翻 IBCI 自身设计缺陷：即使设计思路已在文档记录，也可按更普适、实践更合理的方案重建。
8. 破坏性重构授权：符合一般工程经验且经分析优于现有体系时默认已授权自主推进，详记决策。
9. 大范围破坏性重构分支政策：无法确认边界/危害程度的重构 100% 授权在独立分支实验；
   独立分支禁止直接合并到 unsafe-vibe-dev 或 main；永远不触碰 main。

---

## 🔴 当前状态

**主线：远期原生宿主绑定（F0-F5）**——`ROADMAP_NATIVE_BINDING.md` §三【远期愿景】。
**F0（地基验证）+ F1（宿主导入一等语法 + 用户类持有 native）+ F2（协议/impl 扩展到
宿主类型）已完成**：宿主导入 `import python "pkg" as lib: bind ...` 全链路实现（AST/
lexer/parser/依赖扫描/scheduler/语义/运行时/VM），显式声明式绑定（非自动穿透）+
编译期类型检查 + 用户类持 native；bind class 宿主类型绑定（一等类型 EXTERNAL_MODULE
CLASS + per-instance vtable + impl 补充/协议满足）。F2 独立复核整改闭环已合并
（65414738），全量 pytest 3053 passed / 1 skipped。设计底稿
`docs/architecture/01_native_host_binding.md` §五 + 语法文档
`docs/syntax/11_modules.md` §11.10。**F3（插件体系重构）已完成**：废弃 Python 侧
`_spec.py` 磁盘发现/加载通道，用户侧扩展唯一边 = 宿主绑定 `bind`。F3-1：10 个
`_spec.py` 删除，内置 11 模块（内核原生 5 + 工具 5 + file）TypeDef 字面量集中
`core/runtime/bootstrap/builtin_modules.py`（BUILTIN_MODULE_SPECS，file 自 engine 挪入）
构造期一次注册全部含实现；结构等价探针 + 契约测试 + loader 环 2 去双绑定。F3-2：磁盘
插件发现/加载双通道彻底铲除（discovery/auto_discovery/loader 环 2/插件搜索路径配置面/
main.py --plugin/ibci_sdk/__ibcext_axiom__ 死协议/spec_builder 死代码/幽灵码），Engine
签名简化 `IBCIEngine(root_dir=...)`。F3-3：examples/trials/docs 全迁移（清 plugins_demo/
isolation plugins/T01 plugins，write_user_plugin → extend_with_host_binding，docs 改 F3
事实）。F3-4：残留扫描 `_spec.py`/`__ibcext_vtable__`/discovery 引用清零（功能面零残留，
仅历史注释）。三阶段全量 pytest 零回归。F3-0 bind 默认参数已裁决跳过（默认值放 .ibci
包装层）。**F4（Provider 自定义经宿主绑定统一）已完成**：用户经
`import python "<mod>" as lib: bind provider` 声明实现 `LLMProvider` 契约的自定义
provider，`ai.set_provider(lib.provider)` 注册为激活 `llm_provider`（HIGH 优先级覆盖
内置默认 RecommendedProvider）；R 期"改 provider_impl.py"临时形态拆除（provider_impl.py
降为内置默认实现）；`docs/howto/modify_llm_provider.md` 改写为宿主绑定通道；用户
2026-08-18 授权推翻 R0-R2"不新增语言级注册 API"裁定。全量 pytest 2956 passed /
1 skipped 零回归 + 自定义 provider e2e。分支 `exp/provider-bind-f4`。**下一步 = F5
（架构统一/文档收敛 + 内核自举 + 缓存/JIT 规划）**。

## 下一步候选（当前主干按序；支线仅在不打断主线时介入）

1. **[主线·远期，当前] F5 架构统一/文档收敛**——补齐原生绑定语法/协议/用户 IBCI 库
   文档；评估并落地档 A（缓存预编译）→ 档 B（真 JIT）；内核自举（内置契约再表达为
   bind 声明）；隔离/反射能力规划评估（ROADMAP_NATIVE_BINDING.md §三 F5）。
2. 支线：PT-DEBT-29/30/31、PT-DECIDE-2/3、PT-DEBT-4/5；
3. 支线：真实 LLM 压力试用扩展（VISION-3）；文档体系持续治理。

（最近完成与过程记录见 git log；长期裁定见 `tasks_docs/WORKLOG.md`。）

---

## 工作规则

- 同一时刻只主推一个 P0 阶段。
- 工作模式定论优先；改动公理层或语义错误集的任务需全量 pytest 评估破坏面。
- 重大架构决策直接写入 `docs/architecture/` 对应章节，不使用独立 ADR 文件。
- 测试基线以实跑为准，不冻结数字（唯一命令 `python -m pytest tests/`，见 AGENTS.md）。

---

## 附、书写模式（本文档专用模板，书写必须参照）

> 本节是本文档书写的**唯一权威模板**（模板归属 = 文档自身；`GOVERNANCE.md`
> §三 仅做索引）。更新本文档一律按下列结构与格式书写。

### 1. 文档结构

```
# NEXT_STEPS — 当前最紧要项
定位段（只记录当前最紧要、可立即开工的下一步与强制约束；不承载历史完成记录）
⛔ 工作模式定论（强制，凌驾于本文件一切任务之上；9 条硬约束）
🔴 当前状态（1 段：当前主线/任务 + 状态；无进行中主线时明确写出）
**下一步候选**（等待用户指示的候选项，按序编号）
工作规则（持续推进的硬规则）
（最近完成与过程记录由 git 承载，不在本文件登记）
```

### 2. 主线状态格式（有进行中主线时）

| 列 | 内容 |
|----|------|
| 阶段 | 阶段代号 + 一句话主题 |
| 状态 | 🔄 进行中 / ⏳ 待用户 / ❌ 阻塞（**不登记已完成阶段**——完成即从本文件移除） |
| 内容 | 本阶段正在做什么（2-4 项要点） |
| 验证 | 放行门（全量 pytest 实跑 + 复核，不冻结数字） |

### 3. 维护规则

- 主线变更时更新"当前状态"与"下一步候选"；**阶段完成即移除**（不保留完成登记）。
- **工作模式定论为最高约束**：修改其中条目属用户裁定级变更，须由用户拍板，不自主改写。
- 待用户确认项只在此标注；不建独立章节。
- 不出现日期戳、历史叙述、测试数字（基线以实跑为准）；引用其它任务控制文档用相对路径指针，不复制正文。