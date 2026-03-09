from core.engine import IBCIEngine
import os
import json

engine = IBCIEngine()

# 1. Test Source Meta API
print("\n--- Test 1: get_source ---")
code1 = """
import host
str s = host.get_source()
print("Source length: " + len(s).to_str())
if len(s) > 0:
    print("Source meta-api works!")
"""
engine.run_string(code1)

# 2. Test Save/Load State
print("\n--- Test 2: save_state & load_state ---")
code2 = """
import host
int secret = 42
host.save_state("state_42.json")
print("Saved secret=42")
"""
engine.run_string(code2)

# Check if file exists
if os.path.exists("state_42.json"):
    print("state_42.json exists.")
    with open("state_42.json", "r") as f:
        data = json.load(f)
        # print(json.dumps(data, indent=2))
else:
    print("Error: state_42.json NOT found.")

code3 = """
import host
host.load_state("state_42.json")
# print("Loaded state. Checking secret...")
# Due to how load_state works (replacing context), 
# variables in the current execution flow might not be immediately updated 
# if they were already resolved. 
# But let's see if we can get it back.
"""
# engine.run_string(code3)

# 3. Test host.run with Isolation & Recovery
print("\n--- Test 3: host.run with isolation & recovery ---")
with open("sub_fail.ibci", "w") as f:
    f.write("print('Sub running...')\nint x = 'fail' # Type error\n")

code4 = """
import host
int marker = 100
print("Marker before run: 100")
try:
    host.run("sub_fail.ibci")
except Exception as e:
    print("Caught sub-run failure as expected.")

print("Checking if marker is still 100...")
if marker == 100:
    print("Recovery successful!")
"""
engine.run_string(code4)

# Cleanup
for f in ["state_42.json", "sub_fail.ibci"]:
    if os.path.exists(f):
        os.remove(f)
