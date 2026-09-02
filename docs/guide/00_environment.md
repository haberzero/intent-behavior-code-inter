# 00 · 安装运行环境

> 本文是 IBCI 入门教程的第零章。面向首次接触 IBCI 的开发者。覆盖 Python 运行环境创建、项目依赖安装与环境验证。

## 你将会学到

- 用标准库 `venv` 创建独立的 Python 环境
- 用 pip 安装项目依赖
- 验证环境可用
- 理解运行时 / 测试依赖的分组结构

## 前置要求

Python ≥3.10（版本下界见 `pyproject.toml` 的 `requires-python`；开发基线建议 3.12），并确保 `python3` 命令可用：

```bash
python3 --version
```

## 第一步：创建环境

在项目根目录创建虚拟环境 `.venv`，并以**可编辑模式**安装本项目及开发依赖：

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

可编辑模式使源码改动即时生效，无需重复安装；`.venv/` 已列入 `.gitignore`。依赖规格的单点真理在 `pyproject.toml`（运行时依赖 `openai`，开发分组含 `pytest`）。

## 第二步：激活环境

```bash
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

激活后，后续所有 `python` 与 `pytest` 命令都在此环境下运行。脚本与非交互 shell 可免激活，直接以绝对路径调用（如 `.venv/bin/python -m pytest tests/`）。

## 第三步：验证环境

```bash
python --version          # ≥3.10
python -c "import core; import ibci_modules"
python -m pytest tests/   # 全量测试套件
```

`python -c "import core; import ibci_modules"` 无输出即表示包可正常导入；`python --version` 会打印版本号，pytest 会打印测试结果。测试套件的通过数量以实跑为准。

## 依赖分组

项目依赖的单点真理在 `pyproject.toml`，本文不复述完整清单：

| 分组 | 安装命令 | 内容 |
|------|----------|------|
| 运行时 | `pip install -e .` | LLM 客户端（`openai`） |
| 测试 | `pip install -e ".[test]"` | 运行时 + `pytest` |
| 开发 | `pip install -e ".[dev]"` | 测试 + 开发工具 |

日常开发与测试统一使用 `dev` 分组（即第一步安装的形态）。

## 更新环境

`pyproject.toml` 的依赖声明变化后，重新安装同步环境：

```bash
.venv/bin/pip install -e ".[dev]"
```

## 你现在能做什么

环境已就绪，下一步配置 LLM 提供者，让行为表达式调用真正工作起来。

**下一步**：[01 · 配置 LLM 提供者][]——填写 API 密钥并验证模型连接。

[01 · 配置 LLM 提供者]: ./01_setup.md
