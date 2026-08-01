# AGENTS.md

> AI agent 进入本仓库后的**开工前必读**。本文件只放指针与硬规则，不复制其它文档内容（单点真理）。

## 项目定位

IBC-Inter 是实验性意图驱动混合编程语言（Python-style 确定性代码 + LLM 非确定性推理融合）。处于实验性示例阶段，详见 `README.md`。

## 开工前必读（按顺序）

1. `tasks_docs/NEXT_STEPS.md` "⛔ 工作模式定论"--禁止 compat shim / 胶水实现 / tricky 实现，质量优先于速度
2. `docs/README.md` §三 "文档治理纪律"--单点真理、数字纪律、跨文件一致性
3. `docs/WRITING_GUIDE.md`--技术文档书写准则，修改/新增 `docs/` 下技术文档前必读
4. `docs/KNOWN_LIMITS.md`--语言级限制，改公理层或语义错误集前必查
5. `docs/architecture/02_metadata_ast.md`--新增 AST 字段或侧表前必查
6. `skills/doc-governance.md`--执行文档治理/检查/体系建设前必读，按 Phase 0-8 流程操作
7. `skills/code-workflow.md`--执行代码任务（实现/修复/重构）前必读，按 Phase 0-5 流程操作，遵守工作模式定论
8. `skills/code-review.md`--执行缺陷复核/分类决策/实施后核验前必读，按 Phase 0-5 流程操作，遵守验证与分组纪律
9. `skills/code-quality.md`--执行代码子系统健康/清洁诊断（体检/残留扫描/历史痕迹排查）与质量红线判定前必读，按"健康诊断十查"与分类速查操作（`code-health` 已并入）
10. `skills/code-odor.md`--执行工作过程自查/异味特征扫描前必读，命中兼容/兜底/快速实现等字样时按自我质询协议审问
11. `skills/self-grill.md`--交付前对计划/设计/已完成工作自我质询，仅将无法自主决断项反馈用户

## 测试

```bash
python -m pytest tests/
```

- 这是**唯一命令**。`pytest.ini` 已配 `-q --tb=short --strict-markers`，无需附加 flag。
- 开新分支前必复跑，把 pass/fail 计数写进 PR 描述。
- 当前基线以实跑为准，不冻结数字（见 `tasks_docs/NEXT_STEPS.md` 顶部锚点）。

## 编码与平台注意

- **文档多为 CRLF**，部分历史文件含非 UTF-8 字节；Edit 工具多行匹配可能失败，改用单行锚点或 PowerShell。
- **Windows 路径大小写不敏感**；`tests/conftest.py` 强制 basetemp 为 `.tmp_pytest/`（跨盘 relpath 兼容）。
- **临时目录导入**需 `importlib.invalidate_caches()`，否则 `FileFinder` 缓存陈旧导致 `import_module` 失败（见 `ibci_sdk/check.py` `_load_module`）。
- 文档引用代码路径时以 `docs/README.md` §四"代码路径约定"为准（多个模块已重构为包）。

## 不要做的事

- 不复制其它文档内容到本文件（单点真理；本文件只放指针）。
- 不在文档中冻结测试通过数字（以实跑为准）。
- 不同时主推多个 P0 阶段（见 `tasks_docs/NEXT_STEPS.md` "工作规则"）。
- 不写 compat shim / 胶水 / tricky 实现（见 `tasks_docs/NEXT_STEPS.md` "⛔ 工作模式定论"）。
- 不在代码注释中使用任务代号/ADR 编号/PT 编号/文档章节指针/历史叙述--注释只注明功能设计与已知问题（详见 `docs/README.md` §三.6）。
- 重大架构决策直接写入 `docs/architecture/` 对应章节，不再使用独立 ADR 文件。
- 不在未读 `tasks_docs/NEXT_STEPS.md` 的情况下开始 media Phase 4（当前 GATED）。
- 执行文档治理前必读 `skills/doc-governance.md`，按 Phase 0-8 流程操作——禁止凭经验直接修改，必须先审计、做任务规划、交叉核验。
- 执行代码任务前必读 `skills/code-workflow.md`，按 Phase 0-5 流程操作——禁止未理解代码上下文前动手修改，必须对照工作模式定论检验方案。
