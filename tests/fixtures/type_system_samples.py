"""
tests/fixtures/type_system_samples.py
======================================

Type system-related IBCI code samples: Optional, generics, cast, tuple types.
"""

import pytest


# ============================================================================
# Optional Type Samples
# ============================================================================

OPTIONAL_SAMPLES = {
    "optional_some_int": """
Optional[int] x = Some(42)
print(x.get())
""",

    "optional_none_int": """
Optional[int] x = None
print(x.has_value())
""",

    "optional_some_str": """
Optional[str] x = Some("hello")
print(x.get())
""",

    "optional_some_list": """
Optional[list[int]] x = Some([1, 2, 3])
print(x.get())
""",

    "optional_has_value_guard": """
Optional[int] x = Some(42)
if x.has_value():
    print(x.get())
else:
    print("None")
""",
}


# ============================================================================
# Generic Type Samples
# ============================================================================

GENERIC_SAMPLES = {
    "list_int_basic": """
list[int] nums = [1, 2, 3]
print(nums)
""",

    "list_str_basic": """
list[str] words = ["hello", "world"]
print(words)
""",

    "dict_str_int": """
dict[str, int] scores = {"alice": 100, "bob": 95}
print(scores)
""",

    "nested_generic": """
list[list[int]] matrix = [[1, 2], [3, 4]]
print(matrix)
""",

    "generic_function": """
func list[int] double_list(list[int] items):
    list[int] result = []
    for int x in items:
        result.append(x * 2)
    return result

print(double_list([1, 2, 3]))
""",
}


# ============================================================================
# Cast Expression Samples
# ============================================================================

CAST_SAMPLES = {
    "int_to_str": """
int x = 42
str s = cast[str](x)
print(s)
""",

    "str_to_int": """
str s = "123"
int x = cast[int](s)
print(x)
""",

    "list_upcast": """
list[int] nums = [1, 2, 3]
auto generic_list = cast[list](nums)
print(generic_list)
""",
}


# ============================================================================
# Tuple Type Samples
# ============================================================================

TUPLE_SAMPLES = {
    "tuple_basic": """
tuple[int, str] pair = (42, "hello")
print(pair)
""",

    "tuple_positional_access": """
tuple[int, str, bool] triple = (42, "hello", True)
print(triple[0])
print(triple[1])
print(triple[2])
""",

    "tuple_unpack": """
tuple[int, str] pair = (42, "hello")
int x, str s = pair
print(x)
print(s)
""",

    "tuple_nested": """
tuple[int, tuple[str, bool]] nested = (42, ("hello", True))
print(nested)
""",
}


# ============================================================================
# Pytest Fixtures
# ============================================================================

@pytest.fixture
def optional_sample(request):
    """Fixture to access OPTIONAL_SAMPLES by key"""
    return OPTIONAL_SAMPLES[request.param]


@pytest.fixture
def generic_sample(request):
    """Fixture to access GENERIC_SAMPLES by key"""
    return GENERIC_SAMPLES[request.param]


@pytest.fixture
def cast_sample(request):
    """Fixture to access CAST_SAMPLES by key"""
    return CAST_SAMPLES[request.param]


@pytest.fixture
def tuple_sample(request):
    """Fixture to access TUPLE_SAMPLES by key"""
    return TUPLE_SAMPLES[request.param]
