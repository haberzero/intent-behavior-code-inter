# 00 · 安装运行环境

> 本文是 IBCI 入门教程的第零章。面向首次接触 IBCI 的开发者。覆盖 Python 运行环境创建、项目依赖安装与环境验证。

## 你将会学到

- 用 conda 创建独立的 Python 环境
- 用 pip 安装项目依赖
- 验证环境可用
- 理解运行时 / 测试依赖的分组结构

## 前置要求

安装 [Miniconda](https://docs.anaconda.com/miniconda/) 或 Anaconda，并确保 `conda` 命令可用：

```bash
conda --version
```

## 第一步：创建环境

项目根目录下的 `environment.yml` 声明了完整的 conda 环境定义——Python 版本、pip、以及项目的可编辑安装（`-e ".[dev]"`）。运行：

```bash
conda env create -f environment.yml
```

命令会创建名为 `ibci` 的环境，并自动通过 pip 以**可编辑模式**安装本项目及其依赖。可编辑模式使源码改动即时生效，无需重复安装。

## 第二步：激活环境

```bash
conda activate ibci
```

激活后，后续所有 `python` 与 `pytest` 命令都应在此环境下运行。

## 第三步：验证环境

```bash
python --version          # 3.12.x
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

日常开发与测试统一使用 `dev` 分组（即 `environment.yml` 默认安装的形态）。

## 更新环境

`environment.yml` 或 `pyproject.toml` 的依赖声明变化后，重新同步环境：

```bash
conda env update -f environment.yml
```

## 你现在能做什么

环境已就绪，下一步配置 LLM 提供者，让行为表达式调用真正工作起来。

**下一步**：[01 · 配置 LLM 提供者][]——填写 API 密钥并验证模型连接。

[01 · 配置 LLM 提供者]: ./01_setup.md
