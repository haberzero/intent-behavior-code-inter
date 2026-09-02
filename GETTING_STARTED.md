# IBC-Inter 入门指南

> 从零开始学习 IBC-Inter 的完整教程。按顺序阅读，每章 5-10 分钟。
>
> **定位**：新用户入门入口（教程旅程起点）。文档体系导航与治理见 `docs/README.md`；
> 语言边界见 `docs/KNOWN_LIMITS.md`；语法速查见 `docs/SYNTAX_REFERENCE.md`。

## 教程

0. [环境准备](docs/guide/00_environment.md) — 安装 Python 环境（≥3.10）与运行依赖
1. [配置 LLM 提供者](docs/guide/01_setup.md) — 配置 API key、模型路由和连接验证
2. [第一个 @~ 调用](docs/guide/02_first_call.md) — 行为表达式基础、变量插值和类型约束
3. [处理 LLM 调用失败](docs/guide/03_handling_errors.md) — llmexcept、retry 和异常体系
4. [用意图控制 LLM 行为](docs/guide/04_intents.md) — @/@+/@-/@! 实战与意图栈管理
5. [定义和使用 LLM 可调用类](docs/guide/05_llm_callable.md) — __llm_call__ 协议与提示词工程
6. [构建多步骤 LLM 工作流](docs/guide/06_multistep.md) — file 模块 + fn + for @~ 串联调用
7. [MOCK 测试与调试](docs/guide/07_testing.md) — 不连 API 也能测试，idbg 调试

---

## 语法参考

如果你已经熟悉基础用法，需要查阅语法细节：

- [完整语法参考](docs/SYNTAX_REFERENCE.md) — 类型、变量、控制流、行为表达式等全部语法章节的完整规范
- [已知限制](docs/KNOWN_LIMITS.md) — 当前版本的语言边界和使用约束

---

## 架构与设计

如果你想理解"为什么这样设计"：

- [架构原则](docs/ARCHITECTURE.md) — 层级架构、依赖规则、公理体系
- [子系统设计](docs/SUBSYSTEM_DESIGN.md) — 意图系统、文件容器、插件系统等内部设计

---

## 运行示例

*注意：现阶段不推荐使用思考模型接入 IBC-Inter。思考模型在当前版本提示词约束下容易陷入思考循环。请使用非思考模式。*

```bash
python main.py run your_script.ibci
```