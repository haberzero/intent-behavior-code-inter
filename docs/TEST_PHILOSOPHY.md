# IBCI 测试哲学

> **核心信念**：测试应验证"IBCI 作为一门语言的语义不变量"，而非"解释器的实现细节"。

本文档阐述 IBCI 测试体系的长期战略、设计原则与最佳实践。

---

## §1 为什么需要测试哲学

### 1.1 IBCI 的独特挑战

IBCI 不是传统编程语言，它面临独特的测试挑战：

1. **混合确定性与不确定性**
   - 确定性代码（变量、控制流、类型）+ 不确定性 LLM 推理
   - 测试必须验证 MOCK 协议正确性，而非 LLM 实际输出

2. **意图驱动范式**
   - 通过 `@` 注释动态增强上下文
   - 测试需要验证意图传播、优先级、跨帧行为

3. **AI 容错控制流**
   - `llmexcept` / `retry` 机制处理 LLM 输出异常
   - 测试必须覆盖错误恢复路径与循环不变量

4. **快照语义**
   - `snapshot` 实现无状态可重入行为
   - 测试需验证深克隆、隔离性、调用现场捕获

5. **解释器 vs 语言分离**
   - 解释器是 **实现细节**（tree-walker / CPS / JIT 任意切换）
   - 测试应聚焦 **语言语义**（对外可观察行为）

### 1.2 传统测试方法的局限

**传统单元测试思维**：
- 为每个函数写测试
- 为每个类写测试
- 覆盖每个代码分支

**在 IBCI 中的问题**：
- ❌ 解释器内部结构会变化（VM 重构 / CPS 改造）
- ❌ 测试与实现紧耦合（访问 `node_pool` / `side_table`）
- ❌ 测试数量爆炸（1,259 个测试验证 30K 行代码）
- ❌ 维护成本高（内部重构破坏大量测试）

---

## §2 IBCI 测试的分层模型

### 2.1 四层测试金字塔

```
                    ┌────────────────┐
                    │   Examples     │  4-6 个完整示例程序
                    │   (文档化)      │  计算器/聊天代理/数据流水线
                    └────────────────┘
                  ┌──────────────────────┐
                  │    Compliance        │  公开 API 黑盒契约
                  │    (50-80 tests)     │  并发/隔离/内存模型
                  └──────────────────────┘
              ┌──────────────────────────────┐
              │       Contracts              │  核心语义不变量
              │    (300-400 tests)           │  类型/执行/作用域/Intent/LLM
              └──────────────────────────────┘
          ┌────────────────────────────────────────┐
          │           Regression                   │  历史 Bug 最小复现
          │         (按 issue 索引)                 │  不可被 contract 覆盖的边界条件
          └────────────────────────────────────────┘
```

### 2.2 各层职责与范围

#### Contracts 层（核心，70% 测试工作）

**目的**：验证语言设计文档中的核心不变量

**范围**：
- 类型系统不变量（Optional 空安全 / 泛型协变 / cast 合法性）
- 执行模型公理（CPS 无递归 / Signal 传播 / 帧栈隔离）
- 作用域语义（Cell 共享 / lambda 捕获 / snapshot 克隆）
- Intent 系统（优先级 / 跨帧传播 / retry 还原）
- llmexcept 保证（错误历史 / 深度限制 / 循环不变量）
- LLM 集成契约（MOCK 协议 / dispatch / DDG 顺序）

**特征**：
- 每个测试验证 **一个** 语义不变量
- 使用 **最小 IBCI 代码**（5-15 行）
- **不访问内部实现**（不依赖 node_pool / interpreter 内部）
- 参数化测试覆盖多种情况

**示例**：
```python
# tests/contracts/test_type_invariants.py

class TestOptionalNullSafety:
    """验证 Optional[T] 的空安全保证"""

    def test_optional_none_access_raises(self):
        """INV-OPT-1: 访问 None 的 Optional 必须抛出运行时错误"""
        code = """
        Optional[int] x = None
        int y = x.get()  # 必须失败
        """
        with pytest.raises(RuntimeError, match="None"):
            run_ibci(code)

    @pytest.mark.parametrize("type_,value", [
        ("int", "42"),
        ("str", '"hello"'),
        ("list[int]", "[1,2,3]"),
    ])
    def test_optional_preserves_wrapped_type(self, type_, value):
        """INV-OPT-2: Optional[T] 包装后类型不变"""
        code = f"""
        Optional[{type_}] x = Some({value})
        {type_} y = x.get()
        print(y)
        """
        # 验证不抛类型错误即可
        run_ibci(code)
```

#### Compliance 层（公开 API，20% 测试工作）

**目的**：验证跨实现的公开 API 契约

**范围**：
- 并发 LLM 调用（多线程安全）
- 执行隔离（多 Interpreter 互不干扰）
- 内存模型（快照不变性 / Cell 共享）

**特征**：
- 黑盒测试，只使用 `IBCIEngine` / `host.*` 公开 API
- **禁止** import `core/runtime/...` 内部模块
- 适合作为语言规范的可执行定义

#### Regression 层（历史 Bug，5% 测试工作）

**目的**：防止已修复的 Bug 再次出现

**范围**：
- 无法被 contract 测试覆盖的边界条件
- 历史上导致崩溃/数据损坏的特定输入

**特征**：
- 按 GitHub issue 编号索引
- 每个测试包含最小复现代码
- Docstring 注明修复时间与相关 PR

**示例**：
```python
# tests/regression/test_known_issues.py

def test_issue_42_intent_leak_in_retry(self):
    """Issue #42: retry 后意图栈未正确还原

    修复：NS-2c (2026-05-11)
    验证：retry 前后 intent_context 状态一致
    """
    code = """
    import ai
    ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
    @ "initial"
    llmexcept {
        @ "temporary"
        str x = @~ MOCK:INVALID ~
    } retry {
        str x = @~ MOCK:TRUE retry ~
    }
    """
    # 验证不抛异常即可（原 Bug 会因意图泄漏崩溃）
    run_ibci(code)
```

#### Examples 层（文档化，5% 测试工作）

**目的**：提供完整示例程序，兼具测试与教程价值

**范围**：
- 简单计算器（基础语法）
- 聊天代理（LLM 集成）
- 数据流水线（高阶函数 / snapshot）
- 并发任务（多 Interpreter）

**特征**：
- 每个示例 50-100 行 IBCI 代码
- 自包含，可直接运行
- Docstring 解释设计意图

---

## §3 测试编写指南

### 3.1 黄金法则

1. **最小化原则**：每个测试验证一个语义不变量
2. **黑盒优先**：避免访问内部实现（node_pool / interpreter 内部）
3. **参数化复用**：10 个相似测试 → 1 个 `@pytest.mark.parametrize` 测试
4. **代码简洁**：IBCI 测试代码 ≤ 15 行
5. **自解释性**：测试方法名清晰描述验证内容

### 3.2 命名规范

**文件命名**：
- `test_<concept>.py`（concept 是语言概念，如 `type_invariants` / `scope_semantics`）
- **禁止**：里程碑代号（`test_ns2b_*.py` / `test_pt21_*.py`）

**测试类命名**：
- `Test<Concept><Aspect>`（如 `TestOptionalNullSafety` / `TestIntentPropagation`）
- **禁止**：代号前缀（`TestNS2bXxx` / `TestPT21Xxx`）

**测试方法命名**：
- 描述 **行为** 而非编号：`test_optional_none_access_raises`
- **禁止**：`test_ns2b_feature_1` / `test_pt21_case_a`

**不变量编号**（可选）：
- 在 docstring 中引用：`"""INV-OPT-1: 访问 None 的 Optional 必须抛出运行时错误"""`
- 对应设计文档中的公理编号

### 3.3 参数化测试模式

**反模式**（冗余）：
```python
def test_optional_int():
    code = 'Optional[int] x = Some(42)'
    run_ibci(code)

def test_optional_str():
    code = 'Optional[str] x = Some("hi")'
    run_ibci(code)

def test_optional_list():
    code = 'Optional[list[int]] x = Some([1,2])'
    run_ibci(code)
```

**正确模式**（精简）：
```python
@pytest.mark.parametrize("type_,value", [
    ("int", "42"),
    ("str", '"hi"'),
    ("list[int]", "[1,2]"),
])
def test_optional_type_preservation(type_, value):
    code = f'Optional[{type_}] x = Some({value})\nprint(x.get())'
    run_ibci(code)
```

### 3.4 使用 fixtures/ 样本库

**创建样本**：
```python
# tests/fixtures/llm_samples.py

BEHAVIOR_SAMPLES = {
    "simple_mock": """
        import ai
        ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
        str result = @~ MOCK:TRUE test ~
    """,

    "with_intent": """
        import ai
        ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
        @ "context info"
        str result = @~ generate response ~
    """,
}

@pytest.fixture
def llm_sample(request):
    return BEHAVIOR_SAMPLES[request.param]
```

**使用样本**：
```python
# tests/contracts/test_llm_integration.py

@pytest.mark.parametrize("llm_sample", ["simple_mock", "with_intent"], indirect=True)
def test_behavior_expression_executes(llm_sample):
    """LLM-1: behavior 表达式必须产生输出"""
    result = run_ibci(llm_sample)
    assert result  # 任何输出都是成功
```

### 3.5 避免的反模式

#### 反模式 1：测试实现细节
```python
# ❌ 错误：依赖内部数据结构
def test_vm_handler_dispatch():
    engine = make_engine("x = 42")
    node_uid = find_node_uid(engine, "IbAssignment")
    assert engine.interpreter.node_pool[node_uid].type == "IbAssignment"
```

```python
# ✅ 正确：测试可观察行为
def test_assignment_statement():
    code = "int x = 42\nprint(x)"
    assert run_ibci(code) == ["42"]
```

#### 反模式 2：微观测试
```python
# ❌ 错误：测试字面量
def test_int_constant():
    code = "print(42)"
    assert run_ibci(code) == ["42"]

def test_string_constant():
    code = 'print("hello")'
    assert run_ibci(code) == ["hello"]
```

```python
# ✅ 正确：测试类型系统不变量
@pytest.mark.parametrize("literal,expected_type", [
    ("42", "int"),
    ('"hello"', "str"),
    ("[1,2,3]", "list[int]"),
])
def test_literal_type_inference(literal, expected_type):
    code = f"auto x = {literal}\nprint(type(x))"
    assert expected_type in run_ibci(code)[0]
```

#### 反模式 3：重复样板
```python
# ❌ 错误：每个测试文件定义 helper
def run_and_capture(code):
    lines = []
    engine = IBCIEngine(...)
    engine.run_string(code, ...)
    return lines
```

```python
# ✅ 正确：使用 conftest.py 统一 API
from tests.conftest import run_ibci

def test_something():
    assert run_ibci(code) == expected
```

---

## §4 测试与文档的关系

### 4.1 测试即规范

IBCI 的测试体系应该是 **语言规范的可执行定义**：

- 设计文档（`IBCI_SYNTAX_REFERENCE.md` / `VM_AND_INTERPRETER_DESIGN.md`）定义 **公理**
- Contract 测试验证 **公理的实现**
- 两者必须保持同步

### 4.2 不变量编号系统

**建议**：在设计文档中为每个核心不变量分配唯一编号：

```markdown
## 类型系统不变量

- **INV-OPT-1**: 访问 None 的 Optional[T] 必须抛出运行时错误
- **INV-OPT-2**: Optional[T].get() 返回值类型为 T
- **INV-GEN-1**: list[T] 只接受类型 T 的元素
- **INV-CPS-1**: IBCI 递归深度不受 Python 递归限制
```

**在测试中引用**：
```python
def test_optional_none_access_raises(self):
    """INV-OPT-1: 访问 None 的 Optional 必须抛出运行时错误"""
    ...
```

### 4.3 文档更新流程

**规则**：
1. 新增语言特性 → 先更新设计文档 → 添加公理编号
2. 编写 contract 测试验证公理
3. 实现特性
4. 测试通过后更新 `docs/COMPLETED.md`

---

## §5 测试维护守则

### 5.1 新增测试时

1. **先查 `tests/COVERAGE_MAP.md`** 找对应文件
2. 找不到 → 先在 COVERAGE_MAP 添加条目 + 说明理由 → 再创建文件
3. 使用 `tests/conftest.py` 统一 helper，**禁止本地定义**
4. 遵守命名规范（无里程碑代号）
5. 每个测试验证 **一个** 语义不变量

### 5.2 修 Bug 添加回归测试时

1. 先尝试将 Bug 抽象为 **语义不变量违反**
2. 若能抽象 → 添加到 `contracts/` 相关测试类
3. 若无法抽象（特定输入组合） → 添加到 `regression/test_known_issues.py`
4. Docstring 注明 issue 编号 / 修复时间 / 相关 PR

### 5.3 删除/修改测试时

**严禁**：
- 因"测试碍事"而删除断言
- 删除测试但不验证语义被其他测试承接

**允许**：
- 重构测试（改用参数化 / 合并重复测试）
- 删除实现细节测试（如 `node_pool` 访问）
- 已落地功能的"反例测试"改为"正例测试"

**流程**：
1. 在 PR 描述中逐条说明被删测试的语义
2. 指出哪个 contract 测试承接了该语义
3. Code Review 确认无遗漏

### 5.4 CI 门禁

**强制检查**：
1. `tests/meta/test_no_duplicate_helpers.py` 必须通过（无 helper 重复）
2. 测试总数不得低于基线（当前 300-400 个）
3. 覆盖率不降低（核心路径 ≥ 85%）
4. 所有测试通过（`pytest tests/ -v`）

---

## §6 质量标准

### 6.1 优秀测试的特征

- ✅ **自解释**：方法名 + docstring 清晰描述验证内容
- ✅ **最小化**：IBCI 代码 ≤ 15 行
- ✅ **黑盒**：不访问内部实现
- ✅ **独立**：不依赖其他测试的执行顺序
- ✅ **快速**：单个测试 < 100ms

### 6.2 劣质测试的特征

- ❌ **白盒**：访问 `node_pool` / `side_table` / `interpreter` 内部
- ❌ **冗长**：IBCI 代码 > 30 行
- ❌ **脆弱**：内部重构破坏测试
- ❌ **重复**：多个测试验证同一语义
- ❌ **慢**：单个测试 > 1s

### 6.3 代码审查清单

**提交测试 PR 前，自查**：

- [ ] 测试方法名描述行为（无编号 / 无代号前缀）
- [ ] IBCI 代码 ≤ 15 行
- [ ] 不访问 `interpreter` / `node_pool` / `side_table`
- [ ] 使用 `conftest.py` 统一 API（无本地 helper）
- [ ] Docstring 注明验证的不变量
- [ ] 可能的话使用参数化测试
- [ ] 已更新 `tests/COVERAGE_MAP.md`（如新增文件）

---

## §7 成功案例

### 7.1 Optional 空安全测试（示范）

**设计文档公理**（`IBCI_SYNTAX_REFERENCE.md`）：
```
INV-OPT-1: 访问 None 的 Optional[T] 必须抛出运行时错误
INV-OPT-2: Optional[T].get() 返回值类型为 T
INV-OPT-3: Optional[T].has_value() 为 true 时 get() 安全
```

**Contract 测试**（`tests/contracts/test_type_invariants.py`）：
```python
class TestOptionalNullSafety:
    """验证 Optional[T] 的空安全保证"""

    def test_optional_none_access_raises(self):
        """INV-OPT-1"""
        code = "Optional[int] x = None\nint y = x.get()"
        with pytest.raises(RuntimeError, match="None"):
            run_ibci(code)

    @pytest.mark.parametrize("type_,value", [
        ("int", "42"),
        ("str", '"hi"'),
        ("list[int]", "[1,2]"),
    ])
    def test_optional_get_preserves_type(self, type_, value):
        """INV-OPT-2"""
        code = f"Optional[{type_}] x = Some({value})\n{type_} y = x.get()"
        run_ibci(code)  # 不抛类型错误即可

    def test_optional_has_value_guards_access(self):
        """INV-OPT-3"""
        code = """
        Optional[int] x = Some(42)
        if x.has_value():
            print(x.get())
        """
        assert run_ibci(code) == ["42"]
```

**特点**：
- 3 个公理 → 3 个测试方法
- 参数化测试覆盖多种类型
- 代码简洁（5-10 行 IBCI）
- 黑盒（不访问内部）

### 7.2 CPS 无递归公理测试

**设计文档公理**（`VM_AND_INTERPRETER_DESIGN.md`）：
```
INV-CPS-1: IBCI 递归深度不受 Python 递归限制（通过 CPS 实现无栈递归）
```

**Contract 测试**（`tests/contracts/test_execution_model.py`）：
```python
class TestCPSInvariants:
    """验证 CPS 调度循环的公理"""

    def test_deep_recursion_no_python_stack_overflow(self):
        """INV-CPS-1: IBCI 递归不受 Python 递归限制"""
        code = """
        func int fib(int n):
            if n <= 1:
                return n
            return fib(n-1) + fib(n-2)

        print(fib(500))  # Python 递归会溢出，IBCI 不会
        """
        result = run_ibci(code, timeout=10)
        assert result  # 任何输出都是成功（不崩溃）
```

**特点**：
- 验证架构设计的核心保证
- 不关心 VM handler 实现
- 失败即说明架构违背设计

---

## §8 常见问题

### Q1: 删除 80% 的测试安全吗？

**A**: 安全，因为：
1. 删除的是 **实现细节测试**（如 `node_pool` 访问），非语义测试
2. 保留的 contract 测试覆盖 **核心不变量**，更高价值
3. 分阶段删除（先创建新测试，验证覆盖率，再删旧测试）
4. Git tag 保护（随时可回滚）

### Q2: 如何确保覆盖率不降低？

**A**: 策略：
1. CI 强制覆盖率检查（核心路径 ≥ 85%）
2. Contract 测试聚焦关键路径（类型推断 / 执行模型 / Intent / llmexcept）
3. 覆盖率下降 → 分析遗漏路径 → 添加针对性测试
4. 质量 > 数量（300 个高质量测试 > 1,259 个琐碎测试）

### Q3: 如何处理遗留测试？

**A**: 三步走：
1. **Phase 2.1-2.2**：创建新 contracts/ 层，验证与旧测试等价
2. **Phase 2.3**：逐步删除旧测试（每批 50-100 个，Code Review）
3. **Phase 2.4**：删除空目录（`kernel/` / `runtime/` / `compiler/` / `e2e/`）

### Q4: 新特性如何添加测试？

**A**: 流程：
1. 设计阶段：在 `IBCI_SYNTAX_REFERENCE.md` 定义公理并分配编号（如 INV-XXX-N）
2. 实现前：编写 contract 测试（TDD 风格）
3. 实现特性直到测试通过
4. 更新 `docs/COMPLETED.md` 与 `tests/COVERAGE_MAP.md`

### Q5: Compliance 层 vs Contracts 层的区别？

**A**:
- **Contracts**：语义不变量，语言内部行为（可访问 `core/` 模块）
- **Compliance**：公开 API 契约，黑盒测试（只用 `IBCIEngine` / `host.*`）
- Compliance 适合跨实现验证（如未来有 Rust 实现，Compliance 必须通过）

---

## §9 参考资源

### 内部文档

- [`docs/TESTS_REORGANIZATION_TASK.md`](./TESTS_REORGANIZATION_TASK.md)：重构任务控制文档
- [`tests/README.md`](../tests/README.md)：测试目录维护守则
- [`tests/COVERAGE_MAP.md`](../tests/COVERAGE_MAP.md)：概念 → 测试入口映射
- [`docs/VM_AND_INTERPRETER_DESIGN.md`](./VM_AND_INTERPRETER_DESIGN.md)：执行模型公理
- [`docs/IBCI_SYNTAX_REFERENCE.md`](./IBCI_SYNTAX_REFERENCE.md)：IBCI 完整语法参考（旧条目"IBCI_SPEC.md"已重命名）

### 外部参考

- [Property-Based Testing](https://hypothesis.works/)：Hypothesis 库（Python）
- [Contract Testing](https://martinfowler.com/bliki/ContractTest.html)：Martin Fowler
- [Testing Pyramid](https://martinfowler.com/articles/practical-test-pyramid.html)：Mike Cohn

---

## §10 总结

IBCI 测试体系的核心原则：

1. **语义优先**：验证语言不变量，而非实现细节
2. **最小化**：每个测试验证一个公理
3. **黑盒**：避免白盒耦合
4. **文档化**：测试即规范
5. **可维护**：内部重构不破坏测试

**Phase 2 目标**：
- 测试代码从 15K 行削减到 ≤ 4K 行（**-74%**）
- 测试从 1,259 个精简到 300-400 个（**-68%**）
- 维护成本降低 **80%**
- 测试可读性提升 **10x**

**长期愿景**：
> IBCI 测试体系成为语言设计文档的**可执行规范**，验证核心不变量，而非追逐实现细节。

---

*文档版本：1.0（2026-05-13）*
*维护者：IBCI 核心团队*
