"""
tests/fixtures/control_flow_samples.py
=======================================

Control flow-related IBCI code samples: if/for/while/switch/break/continue.
"""

import pytest


# ============================================================================
# Conditional Samples
# ============================================================================

CONDITIONAL_SAMPLES = {
    "if_true": """
if True:
    print("yes")
""",

    "if_else": """
bool condition = True
if condition:
    print("true branch")
else:
    print("false branch")
""",

    "if_elif_else": """
int x = 5
if x < 0:
    print("negative")
elif x == 0:
    print("zero")
else:
    print("positive")
""",
}


# ============================================================================
# Loop Samples
# ============================================================================

LOOP_SAMPLES = {
    "for_range": """
for int i in range(3):
    print(i)
""",

    "for_list": """
list[int] nums = [10, 20, 30]
for int x in nums:
    print(x)
""",

    "while_loop": """
int i = 0
while i < 3:
    print(i)
    i = i + 1
""",

    "for_with_break": """
for int i in range(10):
    if i == 3:
        break
    print(i)
""",

    "for_with_continue": """
for int i in range(5):
    if i == 2:
        continue
    print(i)
""",

    "nested_loops": """
for int i in range(2):
    for int j in range(2):
        print(i * 10 + j)
""",
}


# ============================================================================
# Switch Samples
# ============================================================================

SWITCH_SAMPLES = {
    "switch_basic": """
int x = 2
switch x:
    case 1:
        print("one")
    case 2:
        print("two")
    default:
        print("other")
""",

    "switch_with_string": """
str color = "red"
switch color:
    case "red":
        print("stop")
    case "green":
        print("go")
    default:
        print("unknown")
""",
}


# ============================================================================
# Function Control Flow Samples
# ============================================================================

FUNCTION_CONTROL_FLOW_SAMPLES = {
    "early_return": """
func int check(int x):
    if x < 0:
        return -1
    if x == 0:
        return 0
    return 1

print(check(5))
""",

    "return_in_loop": """
func int find_first_even(list[int] nums):
    for int x in nums:
        if x % 2 == 0:
            return x
    return -1

print(find_first_even([1, 3, 4, 5]))
""",
}


# ============================================================================
# Pytest Fixtures
# ============================================================================

@pytest.fixture
def conditional_sample(request):
    """Fixture to access CONDITIONAL_SAMPLES by key"""
    return CONDITIONAL_SAMPLES[request.param]


@pytest.fixture
def loop_sample(request):
    """Fixture to access LOOP_SAMPLES by key"""
    return LOOP_SAMPLES[request.param]


@pytest.fixture
def switch_sample(request):
    """Fixture to access SWITCH_SAMPLES by key"""
    return SWITCH_SAMPLES[request.param]


@pytest.fixture
def function_control_flow_sample(request):
    """Fixture to access FUNCTION_CONTROL_FLOW_SAMPLES by key"""
    return FUNCTION_CONTROL_FLOW_SAMPLES[request.param]
