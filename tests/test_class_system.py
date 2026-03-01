import unittest
import textwrap
from core.engine import IBCIEngine
from tests.ibc_test_case import IBCTestCase

class TestClassSystem(IBCTestCase):
    def setUp(self):
        super().setUp()
        # self.engine is already initialized by super().setUp()

    # --- Basic Tests ---

    def test_basic_class_definition_and_instantiation(self):
        code = textwrap.dedent("""
            class Person:
                str name = "Unknown"
                
                func __init__(self, str n):
                    self.name = n
                    
                func greet(self) -> str:
                    return "Hello, " + self.name
            
            var p = Person("Alice")
            if p.greet() != "Hello, Alice":
                raise "Error: greet() failed"
        """)
        success = self.engine.run_string(code)
        self.assertTrue(success)

    def test_class_scope_and_methods(self):
        code = textwrap.dedent("""
            class Counter:
                int count = 0
                
                func inc(self):
                    self.count = self.count + 1
                
                func get(self) -> int:
                    return self.count
                    
            var c = Counter()
            c.inc()
            c.inc()
            if c.get() != 2:
                raise "Error: count should be 2"
        """)
        success = self.engine.run_string(code)
        self.assertTrue(success)

    def test_class_aug_assign(self):
        code = textwrap.dedent("""
            class Counter:
                int count = 0
                
                func inc(self):
                    self.count += 1
                    
            var c = Counter()
            c.inc()
            c.inc()
            if c.count != 2:
                raise "Error: count should be 2"
        """)
        success = self.engine.run_string(code)
        self.assertTrue(success)

    # --- Advanced & Interaction Tests ---

    def test_recursion_in_class(self):
        code = textwrap.dedent("""
            class Math:
                func factorial(self, int n) -> int:
                    if n <= 1:
                        return 1
                    return n * self.factorial(n - 1)
            
            var m = Math()
            var res = m.factorial(5)
            if res != 120:
                raise "Error: factorial failed"
        """)
        success = self.engine.run_string(code)
        self.assertTrue(success)

    def test_object_interaction(self):
        code = textwrap.dedent("""
            class Data:
                int value = 0
                func set_val(self, int v):
                    self.value = v
            
            class Processor:
                func process(self, Data d):
                    d.set_val(d.value + 10)
            
            var d = Data()
            d.set_val(5)
            var p = Processor()
            p.process(d)
            
            if d.value != 15:
                raise "Error: object interaction failed"
        """)
        success = self.engine.run_string(code)
        self.assertTrue(success)

    def test_nested_attribute_access(self):
        code = textwrap.dedent("""
            class Config:
                int timeout = 30
            
            class Service:
                Config cfg
                
                func __init__(self, Config c):
                    self.cfg = c
            
            var c = Config()
            var s = Service(c)
            s.cfg.timeout = 60
            
            if c.timeout != 60:
                raise "Error: nested attribute assignment failed"
        """)
        success = self.engine.run_string(code)
        self.assertTrue(success)

    # --- LLM Interaction Tests ---

    def test_llm_method_with_self_injection(self):
        code = textwrap.dedent("""
            import ai
            ai.set_config("TESTONLY", "test", "test")
            
            class Translator:
                str target_lang = "French"
                
                llm translate(self, str text) -> str:
                __sys__
                __user__
                MOCK:RESPONSE:Translated to $__self.target_lang__: $__text__
                llmend
                
            var t = Translator()
            var res1 = t.translate("Hello")
            if res1 != "Translated to French: Hello":
                raise "Error: res1 failed"
            
            t.target_lang = "Spanish"
            var res2 = t.translate("Hello")
            if res2 != "Translated to Spanish: Hello":
                raise "Error: res2 failed"
        """)
        success = self.engine.run_string(code)
        self.assertTrue(success)

    def test_llm_except_in_class(self):
        code = textwrap.dedent("""
            import ai
            ai.set_config("TESTONLY", "test", "test")
            
            class SmartAgent:
                str mode = "normal"
                
                llm think(self) -> int:
                __sys__
                __user__
                MOCK:FAIL
                llmend
                
                func run(self) -> str:
                    try:
                        var res = self.think()
                        return "ok"
                    except:
                        self.mode = "recovery"
                        return "recovered"
            
            var a = SmartAgent()
            var res = a.run()
            if res != "recovered" or a.mode != "recovery":
                raise "Error: llm except recovery failed"
        """)
        success = self.engine.run_string(code)
        self.assertTrue(success)

    def test_intent_propagation_to_method(self):
        code = textwrap.dedent("""
            import ai
            ai.set_config("TESTONLY", "test", "test")
            
            class Logger:
                llm log(self, str msg) -> str:
                __sys__
                __user__
                MOCK:RESPONSE:OK
                llmend
            
            var l = Logger()
            @ "Analyze this log carefully"
            l.log("Hello")
        """)
        success = self.engine.run_string(code)
        self.assertTrue(success)
        
        # Verify intent was pushed
        ai_module = self.engine.interpreter.service_context.interop.get_package("ai")
        last_info = ai_module.get_last_call_info()
        self.assertIn("Analyze this log carefully", last_info["sys_prompt"])

    # --- Negative / Error Handling Tests ---

    def test_type_checking_negative(self):
        # Should fail semantic analysis
        code = textwrap.dedent("""
            class Person:
                str name = ""
            
            var p = Person()
            p.name = 123 # Type mismatch
        """)
        # We expect run_string to return False due to Compilation Error
        success = self.engine.run_string(code)
        self.assertFalse(success)

    def test_idbg_integration_with_classes(self):
        code = textwrap.dedent("""
            import idbg
            class User:
                str name = "Guest"
                int id = 0
                
            var u = User()
            u.name = "Alice"
            
            dict v = idbg.vars()
            var u_val = v["u"]["value"]
            
            # Check if fields are accessible
            dict f = idbg.fields(u_val)
            if f["name"] != "Alice" or f["id"] != 0:
                raise "Error: idbg.fields failed"
                
            # Direct attribute access from idbg.vars() result
            if u_val.name != "Alice":
                raise "Error: direct attribute access failed"
        """)
        success = self.engine.run_string(code)
        self.assertTrue(success)

if __name__ == "__main__":
    unittest.main()
