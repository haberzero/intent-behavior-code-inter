# IBC-Inter 单元测试指南 (Unit Testing Guide)

本指南旨在说明如何运行和编写 IBC-Inter 项目的单元测试。项目已完成编译器与解释器的彻底解耦，目前的测试重点在于验证编译器的扁平化池产出。

---

## 1. 测试框架概览

IBC-Inter 采用 Python 标准库 `unittest` 作为基础测试框架。

### 1.1 BaseCompilerTest 基类 (编译器测试)

针对**编译器**的测试（词法、语法、语义、序列化），必须继承自 `tests/compiler/base.py` 中的 `BaseCompilerTest`。它提供了以下核心功能：

- **自动化环境模拟**：在 `setUp` 中自动创建 `temp_test_root` 临时目录并切换工作目录，确保测试之间的文件系统隔离。
- **Fixture 支持**：提供 `copy_fixture_to_root()` 方法，方便将 `tests/fixtures/compiler/` 下的 `.ibci` 文件拷贝到测试环境。
- **编译断言**：
    - `assert_compile_success(rel_path)`：断言编译成功并返回 `CompilationArtifact`。
    - `assert_compile_fail(rel_path)`：断言编译应触发错误。
- **结果内省**：`get_main_result(artifact)` 用于从产物中提取主模块的 `CompilationResult`，以便进一步检查 `node_pool`、`symbol_table` 等侧表。

---

## 2. 运行测试

### 2.1 运行编译器完整测试 (推荐)

在项目根目录下运行：
```bash
python -m unittest discover tests/compiler
```

### 2.2 运行特定模块的测试
```bash
# 运行语义分析测试
python -m unittest tests.compiler.test_semantic

# 运行序列化与池化测试
python -m unittest tests.compiler.test_serialization
```

---

## 3. 在测试中使用内核调试器 (Core Debugger)

内核调试器允许你在测试运行期间观测编译器内部细节。

### 3.1 环境变量控制 (推荐方式)

通过设置 `IBC_CORE_DEBUG` 环境变量，可以为测试开启调试输出。

**示例：**
```bash
# 查看语义分析基础追踪和调度器详情
export IBC_CORE_DEBUG="SEMANTIC:BASIC,SCHEDULER:DETAIL"
python -m unittest tests.compiler.test_semantic

# Windows PowerShell:
$env:IBC_CORE_DEBUG="SEMANTIC:BASIC,SCHEDULER:DETAIL"
python -m unittest tests.compiler.test_semantic
```

---

## 4. 编写编译器测试的最佳实践

1.  **使用标准 Fixture**：尽量复用 `tests/fixtures/compiler/standard/` 下的 `.ibci` 文件，它们覆盖了核心语法。
2.  **验证侧表完整性**：在 `test_serialization.py` 中，通过 `res.to_dict()` 验证 UID 引用链是否完整，确保解释器能够“查表执行”。
3.  **关注 Symbol UID**：不再通过名称判断作用域，而是验证不同位置的同名变量是否被绑定到了不同的 `Symbol UID`（Shadowing 校验）。
4.  **测试错误提示**：编写 `assert_compile_fail` 测试时，确保编译器能准确捕获特定的语义错误（如循环继承、类型不匹配）。

---

## 5. 常见调试模块建议

| 调试场景 | 推荐配置 |
| :--- | :--- |
| **词法/语法报错** | `{"LEXER": "BASIC", "PARSER": "DETAIL"}` |
| **符号绑定/类型推导** | `{"SEMANTIC": "DETAIL"}` |
| **多文件依赖/导入** | `{"SCHEDULER": "DETAIL"}` |
