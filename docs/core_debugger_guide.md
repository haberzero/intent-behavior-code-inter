# IBC-Inter 内核调试器 (Core Debugger) 指南

内核调试器是一个专为 IBC-Inter 解释器内部逻辑、编译器流转以及 LLM 交互细节设计的内省工具。它采用非破坏性设计，允许开发者在不修改核心代码的情况下，精准观测系统运行状态。

---

## 1. 核心概念

### 1.1 模块划分 (CoreModule)

调试器将系统划分为以下模块，可独立配置：
- `LEXER`: 词法分析过程、Token 流生成。
- `PARSER`: 语法分析过程、AST 节点生成。
- `SEMANTIC`: 静态语义检查、符号表注册。
    - `DETAIL`: 追踪作用域进入/退出、类型解析、符号查找。
    - `DATA`: 输出函数签名、类结构快照。
- `INTERPRETER`: 运行时节点访问、变量读写、控制流跳转。
- `LLM`: Prompt 评估、意图注入、模型交互原文。
    - `DETAIL`: 追踪 Prompt 插值过程、自动类型转换逻辑、决策映射详情。
- `SCHEDULER`: 多文件编译调度、依赖扫描。
    - `DETAIL`: 追踪依赖扫描阶段、增量编译判定（缓存命入）、拓扑排序过程。
    - `DATA`: 输出完整的编译优先级列表。
- `GENERAL`: 引擎初始化与全局状态。

### 1.2 调试级别 (DebugLevel)

- `NONE` (0): 禁用。
- `BASIC` (1): 核心步骤（如“Tokenization complete”）。
- `DETAIL` (2): 细粒度操作。
    - 编译器：节点访问、作用域流转、依赖解析详情。
    - 运行时：Prompt 合成过程、类型转换中间状态、决策映射逻辑。
- `DATA` (3): 完整数据快照。
    - 输出 AST 结构、Prompt 原文、符号表完整数据、编译拓扑顺序等。

---

## 2. 使用方法

### 2.1 命令行方式 (main.py)

通过 `--core-debug` 参数传入 JSON 配置字符串或配置文件路径：

```bash
# 示例：观测 LLM 交互细节
python main.py run app.ibci --core-debug '{"LLM": "DATA"}'

# 示例：全面观测解释器和语义分析
python main.py run app.ibci --core-debug '{"INTERPRETER": "DETAIL", "SEMANTIC": "BASIC"}'
```

### 2.2 环境变量方式

通过设置 `IBC_CORE_DEBUG` 环境变量进行全局或持久化配置：

```bash
export IBC_CORE_DEBUG='{"LEXER": "BASIC", "INTERPRETER": "DATA"}'
python main.py run app.ibci
```

---

## 3. 单元测试集成

IBC-Inter 的测试套件原生支持内核调试。

### 3.1 动态调试测试

你可以通过 `IBC_CORE_DEBUG` 环境变量为任何现有的单元测试开启调试输出：

```bash
# 调试特定测试中的语义分析逻辑
export IBC_CORE_DEBUG='SEMANTIC:DETAIL'
python -m unittest tests.compiler.test_semantic
```

### 3.2 静态调试配置

对于基于 `BaseCompilerTest` 的测试，可以通过引擎实例手动配置调试器：

```python
def test_complex_logic(self):
    # 启用调度器详细追踪
    self.engine.debugger.configure({"SCHEDULER": "DETAIL"})
    artifact = self.engine.compile("app.ibci")
```

---

## 4. 性能影响

- 在 `DebugLevel.NONE` 时，追踪点仅涉及简单的布尔判断，对运行速度的影响可以忽略不计。
- 在 `DebugLevel.DATA` 级别下，由于涉及大量的数据序列化和终端输出，性能会有明显下降，建议仅在调试特定问题时开启。
