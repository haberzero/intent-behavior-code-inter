from core.engine import IBCIEngine
import os

engine = IBCIEngine()
code = """
str source = get_self_source()
print("My Source Code:")
print("----------------")
print(source)
print("----------------")
"""

with open("test_meta.ibci", "w", encoding="utf-8") as f:
    f.write(code)

try:
    engine.run("test_meta.ibci")
finally:
    if os.path.exists("test_meta.ibci"):
        os.remove("test_meta.ibci")
