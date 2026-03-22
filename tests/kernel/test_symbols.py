import unittest
from core.kernel.symbols import (
    SymbolKind,
    Symbol,
    TypeSymbol,
    FunctionSymbol,
    VariableSymbol,
    IntentSymbol,
    SymbolTable,
)


class TestSymbolKind(unittest.TestCase):
    """测试 SymbolKind 枚举"""

    def test_symbol_kind_values(self):
        """验证所有符号种类"""
        self.assertEqual(SymbolKind.VARIABLE.value, 1)
        self.assertEqual(SymbolKind.FUNCTION.value, 2)
        self.assertEqual(SymbolKind.LLM_FUNCTION.value, 3)
        self.assertEqual(SymbolKind.CLASS.value, 4)
        self.assertEqual(SymbolKind.INTENT.value, 5)
        self.assertEqual(SymbolKind.MODULE.value, 6)

    def test_symbol_kind_count(self):
        """验证符号种类数量"""
        self.assertEqual(len(list(SymbolKind)), 6)


class TestSymbol(unittest.TestCase):
    """测试 Symbol 基类"""

    def test_symbol_creation(self):
        """测试创建符号"""
        sym = Symbol(name="test_var", kind=SymbolKind.VARIABLE)
        self.assertEqual(sym.name, "test_var")
        self.assertEqual(sym.kind, SymbolKind.VARIABLE)
        self.assertIsNone(sym.uid)
        self.assertIsNone(sym.descriptor)

    def test_symbol_is_type_property(self):
        """测试 is_type 属性"""
        sym = Symbol(name="TestClass", kind=SymbolKind.CLASS)
        self.assertTrue(sym.is_type)

        var_sym = Symbol(name="test_var", kind=SymbolKind.VARIABLE)
        self.assertFalse(var_sym.is_type)

    def test_symbol_is_function_property(self):
        """测试 is_function 属性"""
        func_sym = Symbol(name="test_func", kind=SymbolKind.FUNCTION)
        llm_sym = Symbol(name="test_llm", kind=SymbolKind.LLM_FUNCTION)

        self.assertTrue(func_sym.is_function)
        self.assertTrue(llm_sym.is_function)

        var_sym = Symbol(name="test_var", kind=SymbolKind.VARIABLE)
        self.assertFalse(var_sym.is_function)

    def test_symbol_is_variable_property(self):
        """测试 is_variable 属性"""
        var_sym = Symbol(name="test_var", kind=SymbolKind.VARIABLE)
        self.assertTrue(var_sym.is_variable)

        func_sym = Symbol(name="test_func", kind=SymbolKind.FUNCTION)
        self.assertFalse(func_sym.is_variable)

    def test_symbol_clone(self):
        """测试符号克隆"""
        sym = Symbol(name="test", kind=SymbolKind.VARIABLE)
        cloned = sym.clone()

        self.assertIsNot(sym, cloned)
        self.assertEqual(sym.name, cloned.name)
        self.assertEqual(sym.kind, cloned.kind)

    def test_get_content_hash(self):
        """测试内容哈希生成"""
        sym = Symbol(name="test", kind=SymbolKind.VARIABLE)
        hash1 = sym.get_content_hash()

        self.assertIsInstance(hash1, str)
        self.assertEqual(len(hash1), 16)

        hash2 = sym.get_content_hash()
        self.assertEqual(hash1, hash2)


class TestTypeSymbol(unittest.TestCase):
    """测试 TypeSymbol"""

    def test_type_symbol_creation(self):
        """测试创建类型符号"""
        sym = TypeSymbol(name="MyClass", kind=SymbolKind.CLASS)
        self.assertEqual(sym.name, "MyClass")
        self.assertEqual(sym.kind, SymbolKind.CLASS)


class TestFunctionSymbol(unittest.TestCase):
    """测试 FunctionSymbol"""

    def test_function_symbol_creation(self):
        """测试创建函数符号"""
        sym = FunctionSymbol(name="my_func", kind=SymbolKind.FUNCTION)
        self.assertEqual(sym.name, "my_func")
        self.assertEqual(sym.kind, SymbolKind.FUNCTION)

    def test_function_symbol_properties_without_descriptor(self):
        """测试无描述符时的属性"""
        sym = FunctionSymbol(name="my_func", kind=SymbolKind.FUNCTION)
        self.assertIsNone(sym.return_type)
        self.assertEqual(sym.param_types, [])


class TestVariableSymbol(unittest.TestCase):
    """测试 VariableSymbol"""

    def test_variable_symbol_creation(self):
        """测试创建变量符号"""
        sym = VariableSymbol(name="count", kind=SymbolKind.VARIABLE)
        self.assertEqual(sym.name, "count")
        self.assertFalse(sym.is_const)
        self.assertFalse(sym.is_global)

    def test_variable_symbol_const(self):
        """测试常量变量符号"""
        sym = VariableSymbol(name="PI", kind=SymbolKind.VARIABLE, is_const=True)
        self.assertTrue(sym.is_const)

    def test_variable_symbol_global(self):
        """测试全局变量符号"""
        sym = VariableSymbol(name="global_var", kind=SymbolKind.VARIABLE, is_global=True)
        self.assertTrue(sym.is_global)


class TestIntentSymbol(unittest.TestCase):
    """测试 IntentSymbol"""

    def test_intent_symbol_creation(self):
        """测试创建意图符号"""
        sym = IntentSymbol(name="my_intent", kind=SymbolKind.INTENT, content="test content")
        self.assertEqual(sym.content, "test content")
        self.assertFalse(sym.is_exclusive)


class TestSymbolTable(unittest.TestCase):
    """测试 SymbolTable"""

    def setUp(self):
        """每个测试前创建新的符号表"""
        self.table = SymbolTable(name="global")

    def test_symbol_table_creation(self):
        """测试符号表创建"""
        self.assertIsNone(self.table.parent)
        self.assertEqual(self.table.name, "global")
        self.assertEqual(self.table.depth, 0)
        self.assertEqual(len(self.table.symbols), 0)

    def test_define_symbol(self):
        """测试定义符号"""
        sym = VariableSymbol(name="x", kind=SymbolKind.VARIABLE)
        self.table.define(sym)

        self.assertEqual(len(self.table.symbols), 1)
        self.assertIs(self.table.symbols["x"], sym)

    def test_define_symbol_with_uid(self):
        """测试定义符号时分配 UID"""
        sym = VariableSymbol(name="x", kind=SymbolKind.VARIABLE)
        self.table.define(sym)

        self.assertIsNotNone(sym.uid)
        self.assertIn("global", sym.uid)
        self.assertIn("x", sym.uid)

    def test_resolve_existing_symbol(self):
        """测试解析已存在的符号"""
        sym = VariableSymbol(name="x", kind=SymbolKind.VARIABLE)
        self.table.define(sym)

        resolved = self.table.resolve("x")
        self.assertIs(resolved, sym)

    def test_resolve_nonexistent_symbol(self):
        """测试解析不存在的符号"""
        resolved = self.table.resolve("nonexistent")
        self.assertIsNone(resolved)

    def test_resolve_in_parent_scope(self):
        """测试在父作用域解析符号"""
        parent = SymbolTable(name="parent")
        child = SymbolTable(parent=parent, name="child")

        sym = VariableSymbol(name="x", kind=SymbolKind.VARIABLE)
        parent.define(sym)

        resolved = child.resolve("x")
        self.assertIs(resolved, sym)

    def test_get_global_scope(self):
        """测试获取全局作用域"""
        parent = SymbolTable(name="parent")
        child = SymbolTable(parent=parent, name="child")
        grandchild = SymbolTable(parent=child, name="grandchild")

        global_scope = grandchild.get_global_scope()
        self.assertIs(global_scope, parent)

    def test_nested_scope_depth(self):
        """测试嵌套作用域深度"""
        parent = SymbolTable(name="parent")
        child = SymbolTable(parent=parent, name="child")

        self.assertEqual(parent.depth, 0)
        self.assertEqual(child.depth, 1)

    def test_define_duplicate_symbol_raises(self):
        """测试重复定义符号抛出异常"""
        sym1 = VariableSymbol(name="x", kind=SymbolKind.VARIABLE)
        sym2 = VariableSymbol(name="x", kind=SymbolKind.VARIABLE)

        self.table.define(sym1)
        with self.assertRaises(ValueError):
            self.table.define(sym2)

    def test_define_builtin_symbol_allows_overwrite(self):
        """测试内置符号允许覆盖"""
        sym1 = VariableSymbol(name="x", kind=SymbolKind.VARIABLE)
        sym1.metadata["is_builtin"] = True

        sym2 = VariableSymbol(name="x", kind=SymbolKind.VARIABLE)
        sym2.metadata["is_builtin"] = True

        self.table.define(sym1)
        self.table.define(sym2, allow_overwrite=True)

        self.assertIs(self.table.symbols["x"], sym2)

    def test_add_global_ref(self):
        """测试添加全局引用"""
        self.table.add_global_ref("global_var")
        self.assertIn("global_var", self.table.global_refs)


class TestSymbolTableNested(unittest.TestCase):
    """测试嵌套符号表"""

    def test_nested_scope_defines(self):
        """测试嵌套作用域定义"""
        global_table = SymbolTable(name="global")
        func_table = SymbolTable(parent=global_table, name="my_func")

        global_var = VariableSymbol(name="global_var", kind=SymbolKind.VARIABLE)
        func_var = VariableSymbol(name="func_var", kind=SymbolKind.VARIABLE)

        global_table.define(global_var)
        func_table.define(func_var)

        self.assertEqual(len(global_table.symbols), 1)
        self.assertEqual(len(func_table.symbols), 1)

        self.assertIs(global_table.resolve("global_var"), global_var)
        self.assertIs(func_table.resolve("func_var"), func_var)
        self.assertIs(func_table.resolve("global_var"), global_var)

    def test_scope_uid_generation(self):
        """测试作用域 UID 生成"""
        global_table = SymbolTable(name="global")
        func_table = SymbolTable(parent=global_table, name="my_func")

        self.assertEqual(global_table.uid, "scope_global")
        self.assertTrue(func_table.uid.startswith("scope_global/"))


if __name__ == "__main__":
    unittest.main()
