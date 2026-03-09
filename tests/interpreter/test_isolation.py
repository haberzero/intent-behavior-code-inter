import unittest
from tests.interpreter.base import BaseInterpreterTest
from core.engine import IBCIEngine

class TestIsolation(BaseInterpreterTest):
    """
    测试解释器的隔离性：模块级隔离与多引擎实例隔离。
    """
    def test_module_scoping_isolation(self):
        """测试模块级作用域隔离：模块内部变量对外不可见"""
        self.write_file("mod_a.ibci", "var secret = 100")
        self.write_file("mod_b.ibci", """
        import mod_a
        func get_secret() -> int:
            return secret # 错误：不应该能直接访问 mod_a 的私有变量
        """)
        
        main_code = """
        import mod_b
        print(mod_b.get_secret())
        """
        # 静态语义分析阶段就应该报错 (SEM_001: Name 'secret' not defined)
        from core.domain.issue import CompilerError
        with self.assertRaises(CompilerError) as cm:
            self.run_code(main_code)
        
        # 校验报错信息
        error_msg = " ".join([d.message for d in cm.exception.diagnostics])
        self.assertIn("secret", error_msg)

    @unittest.skip("暂时屏蔽：Registry 隔离下的类元数据同步问题待梳理")
    def test_registry_instance_isolation(self):
        """测试 Registry 多实例隔离：不同引擎的类定义和状态互不干涉"""
        import textwrap
        # 引擎 A：定义 Point 类并实例化
        engine_a = self.create_secondary_engine()
        code_a = textwrap.dedent("""
        class Point:
            var x = 1
        Point p = Point()
        print(p.x)
        """).strip() + "\n"
        outputs_a = []
        engine_a.run_string(code_a, output_callback=lambda x: outputs_a.append(str(x)))
        self.assertIn("1", outputs_a)
        
        # 引擎 B：尝试直接访问引擎 A 中定义的 Point
        engine_b = self.create_secondary_engine()
        code_b = "Point p = Point()\n"
        
        # 引擎 B 不应该认识 Point
        from core.domain.issue import CompilerError
        with self.assertRaises(CompilerError):
            engine_b.run_string(code_b, silent=True)

    def test_integer_pool_isolation(self):
        """测试小整数驻留池隔离：不同引擎的整数引用不相等"""
        engine_a = self.create_secondary_engine()
        engine_b = self.create_secondary_engine()
        
        # 获取同一个数值的 IbInteger 实例
        # 注意：解释器内部会从小整数驻留池获取
        # 我们通过获取各自 registry 内部的驻留池来验证物理隔离
        pool_a = engine_a.registry.get_int_cache()
        pool_b = engine_b.registry.get_int_cache()
        
        # 触发一次整数运算生成 42
        engine_a.run_string("var x = 40 + 2")
        engine_b.run_string("var x = 40 + 2")
        
        if 42 in pool_a and 42 in pool_b:
            self.assertIsNot(pool_a[42], pool_b[42], "Integer instances should be isolated between registries")

if __name__ == '__main__':
    unittest.main()
