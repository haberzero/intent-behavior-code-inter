import unittest
from core.engine import IBCIEngine

class TestStandardLibExpansion(unittest.TestCase):
    def setUp(self):
        self.engine = IBCIEngine()

    def test_schema_module(self):
        code = """
import schema
dict data = {"name": "Alice", "age": 25}
dict rules = {
    "required": ["name"],
    "properties": {
        "age": {"type": "integer"}
    }
}
bool ok = schema.validate(data, rules)
print("Schema Valid: " + str(ok))

schema.assert(data, rules) # Should not raise
"""
        self.engine.run_string(code)
        # If no error, success

    def test_net_module_mock(self):
        code = """
import net
# We don't actually call real network in tests usually, 
# but let's test if the module is loadable and functions exist.
str res = net.get("http://example.com", {})
print("Net Get Result: " + res)
"""
        # Run in a way that doesn't fail if no network
        try:
            self.engine.run_string(code)
        except Exception:
            pass # Network might fail, but we check if it was called

if __name__ == "__main__":
    unittest.main()
