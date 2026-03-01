import unittest
import os
import sys
import shutil
import textwrap

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.engine import IBCIEngine
from core.scheduler import Scheduler
from core.compiler.lexer.lexer import Lexer
from core.compiler.parser.core.token_stream import TokenStream
from core.compiler.parser.scanners.import_scanner import ImportScanner
from core.compiler.parser.scanners.pre_scanner import PreScanner
from core.compiler.parser.symbol_table import ScopeManager, SymbolType
from core.support.diagnostics.issue_tracker import IssueTracker
from core.types.dependency_types import ImportType, CircularDependencyError
from core.types.diagnostic_types import CompilerError
from tests.ibc_test_case import IBCTestCase

class TestProjectSystem(IBCTestCase):
    """
    Consolidated tests for Project System, Module Loading, and Compilation Scheduling.
    Covers dependency scanning, pre-scanning, cross-module resolution, and plugin discovery.
    """

    def setUp(self):
        super().setUp()
        self.test_root = os.path.abspath("tmp_project_system_test")
        os.makedirs(self.test_root, exist_ok=True)
        self.test_data_dir = os.path.realpath(os.path.join(os.path.dirname(__file__), 'test_data'))
        # engine is already created by super().setUp()
        # Re-create engine with test_root if needed
        self.engine = self.create_engine(root_dir=self.test_root)

    def tearDown(self):
        if os.path.exists(self.test_root):
            shutil.rmtree(self.test_root)

    def _create_file(self, rel_path: str, content: str):
        full_path = os.path.join(self.test_root, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(textwrap.dedent(content).strip() + "\n")
        return full_path

    # --- Dependency & Pre-Scanning ---

    def test_import_scanning(self):
        """测试 ImportScanner 对各种导入语句的识别"""
        source = textwrap.dedent("""
            import os
            import sys, math
            from utils import helper
            from .pkg import mod
            from ..parent import base
            
            var x = 1
            import invalid # Should be ignored (not at top level)
        """).strip() + "\n"
        issue_tracker = IssueTracker()
        lexer = Lexer(source, issue_tracker)
        tokens = lexer.tokenize()
        scanner = ImportScanner(tokens, issue_tracker)
        imports = scanner.scan()
        
        self.assertEqual(len(imports), 6) # os, sys, math, utils, .pkg, ..parent
        self.assertEqual(imports[0].module_name, "os")
        self.assertEqual(imports[3].module_name, "utils")
        self.assertEqual(imports[3].import_type, ImportType.FROM_IMPORT)
        self.assertEqual(imports[4].module_name, ".pkg")
        
        # Verify error for invalid position
        self.assertTrue(issue_tracker.has_errors())

    def test_pre_scanning_registration(self):
        """测试 PreScanner 对函数和全局变量的预注册"""
        code = textwrap.dedent("""
            func my_func(int a):
                pass
            
            llm my_llm_func(str s):
                __sys__
                prompt
                __user__
                text $s
                llmend
                
            var x = 10
            list[int] numbers = []
            
            func outer():
                var inner_v = 1 # Should NOT be registered globally
        """).strip() + "\n"
        manager = ScopeManager()
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        stream = TokenStream(tokens, IssueTracker())
        pre_scanner = PreScanner(stream, manager)
        pre_scanner.scan()
        
        sym_func = manager.resolve("my_func")
        self.assertIsNotNone(sym_func)
        self.assertEqual(sym_func.type, SymbolType.FUNCTION)
        
        sym_llm = manager.resolve("my_llm_func")
        self.assertIsNotNone(sym_llm)
        self.assertEqual(sym_llm.type, SymbolType.FUNCTION)
        
        sym_x = manager.resolve("x")
        self.assertIsNotNone(sym_x)
        self.assertEqual(sym_x.type, SymbolType.VARIABLE)
        
        sym_numbers = manager.resolve("numbers")
        self.assertIsNotNone(sym_numbers)
        self.assertEqual(sym_numbers.type, SymbolType.VARIABLE)
        
        self.assertIsNone(manager.resolve("inner_v"))

    # --- Compilation & Scheduling ---

    def test_multi_file_compilation(self):
        """测试多文件项目的完整编译链路"""
        project_dir = os.path.join(self.test_data_dir, 'multi_file_project')
        entry_file = os.path.join(project_dir, 'main.ibci')
        
        scheduler = Scheduler(project_dir)
        ast_map = scheduler.compile_project(entry_file)
        
        self.assertIn(entry_file, ast_map)
        math_file = os.path.join(project_dir, 'utils', 'math.ibci')
        self.assertIn(math_file, ast_map)
        
        # Verify symbol resolution across files
        main_ast = ast_map[entry_file]
        math_sym = main_ast.scope.resolve('utils').exported_scope.resolve('math')
        self.assertIsNotNone(math_sym.exported_scope.resolve('add'))

    def test_circular_and_missing_files(self):
        """测试循环依赖和缺失文件处理"""
        # Circular
        circular_dir = os.path.join(self.test_data_dir, 'circular_project')
        scheduler = Scheduler(circular_dir)
        with self.assertRaises(CircularDependencyError):
            scheduler.compile_project(os.path.join(circular_dir, 'a.ibci'))
            
        # Missing
        scheduler = Scheduler(self.test_root)
        with self.assertRaises(CompilerError):
            scheduler.compile_project(os.path.join(self.test_root, 'ghost.ibci'))

    def test_relative_import_resolution(self):
        """测试相对导入路径解析"""
        project_dir = os.path.join(self.test_data_dir, 'relative_project')
        scheduler = Scheduler(project_dir)
        ast_map = scheduler.compile_project(os.path.join(project_dir, 'main.ibci'))
        
        calc_file = os.path.join(project_dir, 'pkg', 'subpkg', 'calc.ibci')
        calc_ast = ast_map[calc_file]
        self.assertEqual(calc_ast.scope.resolve('add').type.name, 'FUNCTION')

    def test_robust_import_propagation(self):
        """测试链式导入、别名和重导出的类型传播"""
        # Scenario: mod3 -> mod2 -> mod1.foo()
        self._create_file('mod1.ibci', """
            func foo() -> bool:
                return True
        """)
        self._create_file('mod2.ibci', "from mod1 import foo")
        self._create_file('mod3.ibci', """
            from mod2 import foo as f
            var res = f()
        """)
        
        scheduler = Scheduler(self.test_root)
        ast_map = scheduler.compile_project(os.path.join(self.test_root, 'mod3.ibci'))
        
        mod3_ast = ast_map[os.path.join(self.test_root, 'mod3.ibci')]
        res_sym = mod3_ast.scope.resolve('res')
        self.assertEqual(res_sym.type_info.name, 'bool')

    # --- Plugin & Module System ---

    def test_dynamic_plugin_discovery(self):
        """测试外部插件模块的动态发现与加载"""
        plugin_dir = os.path.join(self.test_root, "plugins", "hello")
        os.makedirs(plugin_dir, exist_ok=True)
        
        # spec.py
        with open(os.path.join(plugin_dir, "spec.py"), "w", encoding="utf-8") as f:
            f.write('from core.support.module_spec_builder import SpecBuilder\n'
                    'spec = SpecBuilder("hello").func("greet", params=["str"], returns="str").build()')
            
        # __init__.py
        with open(os.path.join(plugin_dir, "__init__.py"), "w", encoding="utf-8") as f:
            f.write('class Hello: \n    def greet(self, n): return f"Hi {n}"\n'
                    'implementation = Hello()')

        engine = IBCIEngine(root_dir=self.test_root)
        self.assertTrue(engine.host_interface.is_external_module("hello"))
        
        # Test calling plugin
        code = textwrap.dedent("""
            import hello
            str s = hello.greet('IBCI')
        """)
        test_file = self._create_file("test.ibci", code)
        
        success = engine.run(test_file)
        self.assertTrue(success, f"Compilation or execution failed: {engine.scheduler.issue_tracker.diagnostics}")
        self.assertEqual(engine.interpreter.context.get_variable("s"), "Hi IBCI")

    def test_builtin_priority(self):
        """测试内置模块优先于插件模块"""
        # Create a fake 'math' plugin
        plugin_dir = os.path.join(self.test_root, "plugins", "math")
        os.makedirs(plugin_dir, exist_ok=True)
        with open(os.path.join(plugin_dir, "spec.py"), "w", encoding="utf-8") as f:
            f.write('from core.support.module_spec_builder import SpecBuilder\n'
                    'spec = SpecBuilder("math").func("fake").build()')
            
        engine = IBCIEngine(root_dir=self.test_root)
        math_meta = engine.host_interface.get_module_type("math")
        self.assertTrue(math_meta.scope.resolve("sqrt")) # Built-in
        self.assertFalse(math_meta.scope.resolve("fake")) # Plugin should be ignored

if __name__ == '__main__':
    unittest.main()
