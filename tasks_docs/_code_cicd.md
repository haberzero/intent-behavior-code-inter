# CI/CD 可靠化/实用化设计（PT-FEAT-5，阶段 B6）

> 临时任务控制文档。按用户 2026-08-20 裁定：B6 = **可靠化设计 + 本地配置**（不 push、不启用
> GitHub 侧），B6 完成标准 = 设计 + 配置就绪，远程启用待用户授权。设计落地后收敛进
> `PENDING_TASKS.md` PT-FEAT-5 条目，本临时文档按治理删除（git 承载）。

## 一、背景与问题

- 现状：`.github/workflows/ci.yml` 仅 `workflow_dispatch` 手动触发（2026-08-11 用户裁定停用
  自动触发）。原因为"GitHub 侧 CI 与本机 `python -m pytest tests/` 区别不大、必要性不足"。
- 目标：设计 CI/CD 的**可靠化与实用化**——让 CI 提供本机 pytest 之外的增量价值，才有重新
  启用的必要。
- 约束：禁 push（除非用户显式授权）；main 不触碰；工作模式定论（禁胶水/tricky/兼容层）。

## 二、CI 应提供的增量价值（可靠性四层）

本机单次 `pytest tests/` 已经覆盖 mock 层全部单元/契约/e2e。CI 若只重复这一步则无价值。
设计为**分层验证**，每层提供不同增量：

| 层 | 内容 | 增量价值 |
|----|------|----------|
| L1 单元/契约（fast） | `pytest tests/contracts tests/compiler tests/kernel -q` | 快速反馈，几分钟内定位回归 |
| L2 全量（full） | `pytest tests/ -q`（含 e2e/compliance/runtime/meta） | 与本地基线一致，跨平台矩阵发现环境差异 |
| L3 真实 LLM e2e（选做，需本地服务） | `trials/_toolkit/run_batch.py ... --mock-only` + 真实 LLM 批 | 验证五大地基重构后真实 LLM 路径（阶段 C VISION-3 前置） |
| L4 发布产物 | `python -m build` + 安装 smoke + 版本号 | 打包可用性、依赖声明完整性 |

**真实 LLM 层的定位**：本机 LLM 服务（qwen3.6-35b-a3b @ LM Studio）不在 GitHub 托管 runner
上。该层只能：
1. 在**本地/自托管 runner** 上跑（不 push 配置到 GitHub 时无意义）；
2. 或作为**手动触发的可选 job**（`workflow_dispatch` inputs），仅在开发者显式提供
   `api_config.json` 时执行；
3. 或在本地 CI 脚本（`scripts/ci_local.sh`）中跑，作为阶段 C 真实试用前的回归门。

## 三、跨平台矩阵

- 项目是纯 Python 3.10+/3.12，依赖仅 `openai>=1.0` + `pytest`（无 conda 特有依赖，
  `tests/conftest.py` 已处理 Windows 跨盘 basetemp）。矩阵可行且低成本：
  `ubuntu-latest` + `windows-latest`（macOS 可选）。
- 本机用 conda env `ibci` 运行；CI 用 `pip install -e ".[test]"` 即可等价（已实跑验证
  依赖面仅 openai+pytest）。

## 四、CI 可靠化要点（相对现有 40 行 ci.yml 的改进）

| 现有问题 | 改进 |
|----------|------|
| 只有 ubuntu + 全量跑 | 拆 L1/L2 两层 + 跨平台矩阵（ubuntu/windows） |
| 无缓存 | `actions/setup-python` + `pip cache` 缓存依赖，提速 |
| 无真实 LLM 层 | L3 手动触发 job（`workflow_dispatch` + inputs），本地可选 |
| 无发布验证 | L4 `python -m build` + 安装 smoke |
| 超时/看门狗 | 复用 `tests/conftest.py` 死锁看门狗（90s 超时硬退出） |
| 无产物可追溯 | 上传 pytest XML/HTML 报告 artifacts |

## 五、本地配置（本次交付）

- **`.github/workflows/ci.yml`（保持禁用，workflow_dispatch 仅手动）**：更新为分层设计模板，
  配置就绪；`on:` 仍为 `workflow_dispatch`（远程启用待授权时改回 push/PR 即可）。
- **`scripts/ci_local.sh`（新增，本地跑 CI 分层）**：本机复现 L1/L2（+可选 L3 mock），
  是"CI 可靠化"的本地落地——无需 push 即可获得 CI 分层价值，且不依赖 GitHub。

## 六、启用条件（待用户授权）

- 远程启用：用户显式授权后，将 `ci.yml` 的 `on:` 恢复为 `push`/`pull_request` 并 push。
- 真实 LLM 层：需自托管 runner 或手动触发 + 本地 `api_config.json`；默认不启用。
- 阶段 C 真实试用（VISION-3）重启后，L3 层作为回归门纳入。

## 七、验证

- 本地全量 `python -m pytest tests/` 零回归（本设计为纯配置/文档/脚本，不触 core）。
- `scripts/ci_local.sh` 本地实跑通过（L1/L2）。
