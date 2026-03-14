import unittest
from tests.base import BaseIBCTest
from core.domain import ast

class TestCompilerLogic(BaseIBCTest):
    """
    全方位的编译器逻辑验证测试。
    覆盖表达式解析、声明处理、作用域、类型检查和错误报告。
    """

    def setUp(self):
        super().setUp()
        self.registry = self.engine.registry.get_metadata_registry()
        # 统一获取当前实例中的描述符
        self.INT = self.registry.resolve("int")
        self.STR = self.registry.resolve("str")
        self.FLOAT = self.registry.resolve("float")
        self.BOOL = self.registry.resolve("bool")
        self.ANY = self.registry.resolve("Any")
        self.VOID = self.registry.resolve("void")

    def test_arithmetic_inference(self):
        """验证算术表达式的类型推导"""
        code = 'var a = 1 + 2.0\nvar b = "hello" + " world"\n'
        self.compile_code(code)
        
        result = self.get_last_result()
        module = result.module_ast
        
        # 1. 1 + 2.0 -> float
        a_assign = module.body[0]
        a_val_type = result.node_to_type[a_assign.value]
        self.assertIs(a_val_type, self.FLOAT)
        
        # 2. "hello" + " world" -> str
        b_assign = module.body[1]
        b_val_type = result.node_to_type[b_assign.value]
        self.assertIs(b_val_type, self.STR)

    def test_function_scoping(self):
        """验证函数作用域和符号解析"""
        code = '''
        var x = 10
        func test(int y):
            int x = 20
            var z = x + y
        '''
        self.compile_code(code)
        
        result = self.get_last_result()
        module = result.module_ast
        
        # 获取函数内部的赋值语句 var z = x + y
        func_def = [s for s in module.body if isinstance(s, ast.IbFunctionDef)][0]
        z_assign = func_def.body[1]
        
        # 验证 z_assign.value (x + y) 中的 x 解析为局部变量 (x=20)
        bin_op = z_assign.value
        x_name_node = bin_op.left
        
        sym = result.node_to_symbol[x_name_node]
        self.assertEqual(sym.name, "x")
        # 确认不是全局那个 x (全局 x 的定义节点是 module.body[0])
        self.assertNotEqual(sym.def_node, module.body[0]) 
        # 局部变量的定义节点应该是 int x = 20 那个语句
        self.assertIs(sym.def_node, func_def.body[0])

    def test_type_mismatch_error(self):
        """验证类型不匹配错误报告 (SEM_003)"""
        code = 'int x = "not an int"'
        from core.domain.issue import CompilerError
        with self.assertRaises(CompilerError) as cm:
            with self.silent_mode():
                self.compile_code(code)
        
        self.assertTrue(any(d.code == "SEM_003" for d in cm.exception.diagnostics))

    def test_member_access_inference(self):
        """验证内置类型的成员访问（如 list.len()）"""
        code = '''
        list[int] l = [1, 2]
        var n = l.len()
        '''
        self.compile_code(code)
        result = self.get_last_result()
        
        # 验证 n 的类型为 int
        n_assign = result.module_ast.body[1]
        n_type = result.node_to_type[n_assign.value]
        self.assertIs(n_type, self.INT)

    def test_oop_inference(self):
        """验证类定义和成员访问"""
        code = '''
        class Point:
            int x
            int y
            func dist() -> int:
                return self.x + self.y
        
        Point p = Point()
        var d = p.dist()
        '''
        self.compile_code(code)
        result = self.get_last_result()
        
        # 验证 d 的类型为 int
        d_assign = result.module_ast.body[2]
        d_type = result.node_to_type[d_assign.value]
        self.assertIs(d_type, self.INT)

    def test_dynamic_type_flexibility(self):
        """验证 Any/var 类型的动态灵活性"""
        code = '''
        Any x = 10
        x = "now i am string"
        Any y = [1, 2, 3]
        '''
        self.compile_code(code)
        result = self.get_last_result()
        
        # 验证 x 的类型是 Any
        x_def = result.module_ast.body[0]
        self.assertIs(result.node_to_type[x_def.targets[0]], self.ANY)
        
        # 验证 y 的显式定义类型是 Any
        y_def = result.module_ast.body[2]
        self.assertIs(result.node_to_type[y_def.targets[0]], self.ANY)

    def test_filtered_expression_inference(self):
        """验证带过滤条件的表达式推导 (FilteredExpr)"""
        code = '''
        func is_ready() -> bool:
            return True
        
        while True if is_ready():
            int a = 1
        '''
        self.compile_code(code)
        result = self.get_last_result()
        
        # 找到 While 节点
        while_stmt = [s for s in result.module_ast.body if isinstance(s, ast.IbWhile)][0]
        # While.test 应该是 FilteredExpr
        filter_expr = while_stmt.test
        self.assertIsInstance(filter_expr, ast.IbFilteredExpr)
        
        # 验证 FilteredExpr 的推导类型应为内部 expr (True) 的类型，即 bool
        res_type = result.node_to_type[filter_expr]
        self.assertIs(res_type, self.BOOL)

    def test_argument_count_mismatch_error(self):
        """验证参数数量不匹配错误 (SEM_005)"""
        code = '''
        func add(int a, int b) -> int:
            return a + b
        var res = add(1)
        '''
        from core.domain.issue import CompilerError
        with self.assertRaises(CompilerError) as cm:
            with self.silent_mode():
                self.compile_code(code)
        self.assertTrue(any(d.code == "SEM_005" for d in cm.exception.diagnostics))

    def test_duplicate_definition_error(self):
        """验证重复定义错误 (SEM_002)"""
        code = '''
        int x = 1
        int x = 2
        '''
        from core.domain.issue import CompilerError
        with self.assertRaises(CompilerError) as cm:
            with self.silent_mode():
                self.compile_code(code)
        self.assertTrue(any(d.code == "SEM_002" for d in cm.exception.diagnostics))

    def test_global_statement_validation(self):
        """验证 global 声明的合法性 (SEM_004)"""
        # 顶层不允许使用 global
        code = '''
        global x
        '''
        from core.domain.issue import CompilerError
        with self.assertRaises(CompilerError) as cm:
            with self.silent_mode():
                self.compile_code(code)
        # 如果解析失败可能是 PAR_001，如果是语义失败可能是 SEM_004
        self.assertTrue(any(d.code in ("SEM_004", "PAR_001") for d in cm.exception.diagnostics))

    def test_generic_dict_inference(self):
        """验证多参数泛型 (dict[str, int]) 的推导"""
        code = 'dict[str, int] scores = {"alice": 100}'
        self.compile_code(code)
        result = self.get_last_result()
        
        scores_assign = result.module_ast.body[0]
        scores_type = result.node_to_type[scores_assign.targets[0]]
        self.assertTrue(scores_type.name.startswith("dict"))
        self.assertIs(scores_type.key_type, self.STR)
        self.assertIs(scores_type.value_type, self.INT)

    def test_unknown_member_error(self):
        """验证未知成员访问错误 (SEM_001)"""
        code = '''
        var x = 10
        var y = x.unknown_field
        '''
        from core.domain.issue import CompilerError
        with self.assertRaises(CompilerError) as cm:
            with self.silent_mode():
                self.compile_code(code)
        self.assertTrue(any(d.code == "SEM_001" for d in cm.exception.diagnostics))

    def test_module_member_access(self):
        """验证模块级成员访问 (lib.val)"""
        # 模拟一个外部已编译的模块 lib
        from core.domain.types.descriptors import ModuleMetadata
        from core.domain.symbols import SymbolTable, VariableSymbol, SymbolKind
        
        lib_scope = SymbolTable()
        lib_scope.define(VariableSymbol(name="val", kind=SymbolKind.VARIABLE, descriptor=self.INT))
        
        lib_meta = ModuleMetadata(name="lib")
        # 手动注入成员
        for name, sym in lib_scope.symbols.items():
            lib_meta.members[name] = sym
        
        # 将 lib 注入到当前编译器的 host_interface 中
        self.engine.host_interface.register_module("lib", None, metadata=lib_meta)
        
        code = '''
        import lib
        var x = lib.val
        '''
        self.compile_code(code)
        result = self.get_last_result()
        
        x_assign = result.module_ast.body[1]
        x_type = result.node_to_type[x_assign.value]
        self.assertIs(x_type, self.INT)

    def test_nested_generic_inference(self):
        """验证极端嵌套泛型 (list[dict[str, list[int]]]) 的推导"""
        code = 'list[dict[str, list[int]]] data = []'
        self.compile_code(code)
        result = self.get_last_result()
        
        data_type = result.node_to_type[result.module_ast.body[0].targets[0]]
        self.assertTrue(data_type.name.startswith("list"))
        dict_type = data_type.element_type
        self.assertTrue(dict_type.name.startswith("dict"))
        inner_list_type = dict_type.value_type
        self.assertTrue(inner_list_type.name.startswith("list"))
        self.assertIs(inner_list_type.element_type, self.INT)

    def test_nested_compound_logic(self):
        """验证多重语法糖嵌套下的语义稳定性 (千层饼测试)"""
        # 验证 while-if 嵌套
        code = '''
        func check() -> bool:
            return True
        while True if check():
            while check() if True:
                int x = 1
        '''
        self.compile_code(code)
        result = self.get_last_result()
        self.assertIsNotNone(result)

if __name__ == '__main__':
    unittest.main()
