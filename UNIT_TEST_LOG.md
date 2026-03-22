# IBC-Inter 单元测试工作日志

> 本文件记录 IBC-Inter 项目单元测试工作的详细进展，用于后续对齐和回归参考。
>
> **生成日期**：2026-03-22
> **版本**：V1.0

---

## 一、项目状态总结

### 1.1 架构层级

| 层级 | 目录 | 职责 |
|------|------|------|
| **base** | `core/base/` | 原子概念：位置信息、严重级别、调试基础设施 |
| **kernel** | `core/kernel/` | 核心语言概念：AST、符号、类型描述符、公理、异常 |
| **compiler** | `core/compiler/` | 编译：词法分析、语法分析、语义分析、序列化 |
| **runtime** | `core/runtime/` | 解释执行：解释器、宿主服务、插件执行 |
| **extension** | `core/extension/` | 插件SDK：接口定义、能力注入 |

### 1.2 已完成工作（根据文档）

根据 NEXT_STEPS_PLAN.md：
- ✅ Phase 0-6 全部完成
- ✅ IES 2.2 架构确立
- ✅ 所有核心功能已实现

### 1.3 当前状态

- **单元测试**：❌ 不存在
- **测试框架**：unittest（标准库）
- **测试目录**：需要创建

---

## 二、单元测试计划

### 2.1 测试分层策略

遵循 AI_WORKFLOW.md 的要求：
- **策略一**：从 lexer → parser → semantic → serialization（编译器流程）
- **策略二**：从 base → kernel → runtime（运行时流程）
- **最终目标**：从 base 到 engine，从 lexer 到解释运行的全流程

### 2.2 测试目录结构

```
tests/
├── base/                           # base 层测试
│   ├── __init__.py
│   ├── test_source_atomic.py       # Location, Severity 测试
│   ├── test_enums.py               # 枚举测试
│   ├── test_interfaces.py          # 接口测试
│   ├── test_debugger.py            # CoreDebugger 测试
│   └── test_host_interface.py      # HostInterface 测试
├── kernel/                         # kernel 层测试
│   ├── __init__.py
│   ├── test_axioms/                # 公理体系测试
│   │   ├── __init__.py
│   │   ├── test_primitives.py      # 基础公理测试
│   │   └── test_registry.py        # 公理注册表测试
│   ├── test_types/                # 类型系统测试
│   │   ├── __init__.py
│   │   ├── test_descriptors.py     # TypeDescriptor 测试
│   │   ├── test_registry.py        # MetadataRegistry 测试
│   │   └── test_axiom_hydrator.py  # 公理注入测试
│   ├── test_symbols.py             # 符号系统测试
│   ├── test_issue.py               # 诊断系统测试
│   ├── test_ast.py                 # AST 节点测试
│   └── test_factory.py             # 工厂测试
├── compiler/                       # compiler 层测试
│   ├── __init__.py
│   ├── conftest.py                 # pytest 配置（可选）
│   ├── base.py                     # BaseCompilerTest 基类
│   ├── lexer/                      # 词法分析测试
│   │   ├── __init__.py
│   │   ├── test_lexer.py
│   │   ├── test_str_stream.py
│   │   ├── test_core_scanner.py
│   │   ├── test_indent_processor.py
│   │   └── test_llm_scanner.py
│   ├── parser/                     # 语法分析测试
│   │   ├── __init__.py
│   │   ├── test_parser.py
│   │   ├── test_expression.py
│   │   ├── test_statement.py
│   │   ├── test_declaration.py
│   │   └── test_type_def.py
│   ├── semantic/                   # 语义分析测试
│   │   ├── __init__.py
│   │   ├── test_semantic_analyzer.py
│   │   ├── test_expression_analyzer.py
│   │   ├── test_scope_manager.py
│   │   ├── test_collector.py
│   │   └── test_resolver.py
│   └── serialization/              # 序列化测试
│       ├── __init__.py
│       └── test_serializer.py
├── runtime/                        # runtime 层测试
│   ├── __init__.py
│   ├── test_objects/               # 对象测试
│   │   ├── __init__.py
│   │   ├── test_kernel_objects.py
│   │   └── test_builtins.py
│   ├── interpreter/               # 解释器测试
│   │   ├── __init__.py
│   │   ├── test_interpreter.py
│   │   ├── test_expr_handler.py
│   │   └── test_stmt_handler.py
│   └── test_bootstrap.py           # 引导测试
├── integration/                    # 集成测试
│   ├── __init__.py
│   └── test_end_to_end.py
└── fixtures/                       # 测试固件
    └── compiler/                   # 编译器测试固件
        ├── standard/              # 标准测试用例
        └── edge_cases/            # 边界测试用例
```

### 2.3 测试执行顺序

#### 第一阶段：base 层（最底层）

1. `test_source_atomic.py` - Location, Severity
2. `test_enums.py` - PrivilegeLevel, RegistrationState
3. `test_interfaces.py` - Protocol 接口验证
4. `test_debugger.py` - CoreDebugger 调试功能
5. `test_host_interface.py` - HostModuleRegistry, HostInterface

#### 第二阶段：kernel 层（公理和类型系统）

**axioms 子层**：
1. `test_primitives.py` - IntAxiom, StrAxiom, ListAxiom 等基础公理
2. `test_registry.py` - AxiomRegistry 公理注册

**types 子层**：
1. `test_descriptors.py` - TypeDescriptor, LazyDescriptor, FunctionMetadata 等
2. `test_registry.py` - MetadataRegistry 两阶段注册
3. `test_axiom_hydrator.py` - 公理注入机制

**核心组件**：
1. `test_symbols.py` - 符号表、Symbol、SymbolTable
2. `test_issue.py` - Diagnostic, 错误类
3. `test_ast.py` - AST 节点结构
4. `test_factory.py` - create_default_registry()

#### 第三阶段：compiler 层（词法→语法→语义→序列化）

**lexer 子层**：
1. `test_str_stream.py` - 字符串流处理
2. `test_core_scanner.py` - 核心 Token 扫描
3. `test_indent_processor.py` - 缩进处理
4. `test_llm_scanner.py` - LLM 块扫描
5. `test_lexer.py` - Lexer 集成测试

**parser 子层**：
1. `test_type_def.py` - 类型注解解析
2. `test_expression.py` - 表达式解析（Pratt Parser）
3. `test_statement.py` - 语句解析
4. `test_declaration.py` - 声明解析（func, class, llm）
5. `test_parser.py` - Parser 集成测试

**semantic 子层**：
1. `test_collector.py` - 符号收集（Pass 1）
2. `test_resolver.py` - 类型决议（Pass 2）
3. `test_scope_manager.py` - 作用域管理
4. `test_expression_analyzer.py` - 表达式类型推导
5. `test_semantic_analyzer.py` - 语义分析集成

**serialization 子层**：
1. `test_serializer.py` - FlatSerializer 扁平化序列化

#### 第四阶段：runtime 层（解释执行）

**objects 子层**：
1. `test_kernel_objects.py` - IbObject, IbClass, IbFunction 等核心对象
2. `test_builtins.py` - IbInteger, IbString, IbList 等内置对象

**interpreter 子层**：
1. `test_expr_handler.py` - 表达式处理
2. `test_stmt_handler.py` - 语句处理
3. `test_interpreter.py` - Interpreter 集成测试

**bootstrap 子层**：
1. `test_bootstrap.py` - Bootstrapper, builtin_initializer

#### 第五阶段：集成测试

1. `test_end_to_end.py` - 从 lexer 到解释运行的全流程测试

---

## 三、关键测试用例设计

### 3.1 base 层关键测试

#### test_source_atomic.py
```python
class TestLocation:
    def test_creation(self):
        loc = Location(file_path="test.ibci", line=10, column=5)
        assert loc.file_path == "test.ibci"
        assert loc.line == 10
        assert loc.column == 5

    def test_equality(self):
        loc1 = Location(line=1, column=1)
        loc2 = Location(line=1, column=1)
        assert loc1 == loc2
```

#### test_debugger.py
```python
class TestCoreDebugger:
    def test_debug_level_configuration(self):
        debugger = CoreDebugger()
        debugger.configure({"LEXER": "BASIC", "PARSER": "DETAIL"})
        assert debugger.get_level(CoreModule.LEXER) == DebugLevel.BASIC

    def test_trace_output(self):
        outputs = []
        debugger = CoreDebugger(output_callback=outputs.append)
        debugger.trace(CoreModule.GENERAL, "test message")
        assert "test message" in outputs[0]
```

### 3.2 kernel 层关键测试

#### test_descriptors.py
```python
class TestTypeDescriptor:
    def test_primitive_descriptor_creation(self):
        desc = TypeDescriptor(name="int", is_nullable=False)
        assert desc.name == "int"
        assert desc.is_nullable == False

    def test_clone_isolation(self):
        original = TypeDescriptor(name="test")
        cloned = original.clone()
        assert cloned is not original
        assert cloned == original
```

#### test_primitives.py
```python
class TestIntAxiom:
    def test_resolve_operation(self):
        int_axiom = IntAxiom()
        result = int_axiom.resolve_operation("+", INT_DESCRIPTOR)
        assert result is not None

    def test_can_convert_from(self):
        int_axiom = IntAxiom()
        assert int_axiom.can_convert_from("str")
        assert int_axiom.can_convert_from("int")
```

### 3.3 compiler lexer 层关键测试

#### test_lexer.py
```python
class TestLexerBasic:
    def test_simple_tokens(self):
        lexer = Lexer()
        tokens = lexer.tokenize("var x = 42")
        assert tokens[0].type == TokenType.VAR
        assert tokens[1].type == TokenType.IDENTIFIER
        assert tokens[2].type == TokenType.ASSIGN
        assert tokens[3].type == TokenType.NUMBER

    def test_behavior_marker(self):
        lexer = Lexer()
        tokens = lexer.tokenize("x = @~ hello ~")
        behavior_idx = find_token_type(tokens, TokenType.BEHAVIOR_MARKER)
        assert behavior_idx is not None
```

### 3.4 compiler parser 层关键测试

#### test_expression.py
```python
class TestExpressionParser:
    def test_binary_operation(self):
        parser = Parser()
        ast = parser.parse_expression("1 + 2 * 3")
        assert isinstance(ast, IbBinOp)
        assert ast.op == "+"

    def test_call_expression(self):
        parser = Parser()
        ast = parser.parse_expression("foo(a, b)")
        assert isinstance(ast, IbCall)
        assert len(ast.args) == 2
```

### 3.5 runtime interpreter 层关键测试

#### test_stmt_handler.py
```python
class TestStmtHandler:
    def test_variable_assignment(self):
        # 测试变量赋值
        pass

    def test_if_statement(self):
        # 测试 if 语句
        pass

    def test_function_call(self):
        # 测试函数调用
        pass
```

---

## 四、测试实施记录

### 4.1 第一阶段：base 层测试

| 日期 | 测试文件 | 状态 | 说明 |
|------|----------|------|------|
| 2026-03-22 | - | 待开始 | |

---

*本文件将持续更新，记录每个阶段的测试进展。*
