"""
tests/fixtures/llm_samples.py
==============================

LLM-related IBCI code samples: behavior expressions, llmexcept, intent, retry.
"""

import pytest

# AI configuration prefix (used in most LLM samples)
AI_SETUP = 'import ai\nai.set_config("TESTONLY", "TESTONLY", "TESTONLY")\n'


# ============================================================================
# Behavior Expression Samples
# ============================================================================

BEHAVIOR_SAMPLES = {
    "simple_mock_true": AI_SETUP + """
str result = @~ MOCK:TRUE is sky blue ~
print(result)
""",

    "simple_mock_false": AI_SETUP + """
str result = @~ MOCK:FALSE is it raining ~
print(result)
""",

    "behavior_with_variable": AI_SETUP + """
str topic = "weather"
str result = @~ MOCK:TRUE tell me about {topic} ~
print(result)
""",

    "behavior_type_cast": AI_SETUP + """
int answer = @~ MOCK:42 what is the answer ~
print(answer)
""",

    "llm_function_basic": AI_SETUP + """
func llm str summarize(str text):
    return @~ MOCK:summary summarize: {text} ~

str result = summarize("long text here")
print(result)
""",
}


# ============================================================================
# Intent System Samples
# ============================================================================

INTENT_SAMPLES = {
    "simple_intent": AI_SETUP + """
@ "context information"
str result = @~ MOCK:TRUE generate with context ~
print(result)
""",

    "intent_override": AI_SETUP + """
@ "base context"
@! "override context"
str result = @~ MOCK:TRUE generate ~
print(result)
""",

    "intent_append": AI_SETUP + """
@ "first part"
@+ "second part"
str result = @~ MOCK:TRUE generate ~
print(result)
""",

    "intent_scope_isolation": AI_SETUP + """
@ "global context"

func void inner():
    @ "local context"
    str x = @~ MOCK:local inside function ~
    print(x)

inner()
str y = @~ MOCK:global outside function ~
print(y)
""",

    "intent_in_retry": AI_SETUP + """
@ "initial context"
llmexcept {
    @ "temporary context"
    str x = @~ MOCK:INVALID ~
} retry {
    str x = @~ MOCK:TRUE fallback ~
}
print(x)
""",
}


# ============================================================================
# llmexcept / retry Samples
# ============================================================================

LLMEXCEPT_SAMPLES = {
    "basic_llmexcept": AI_SETUP + """
llmexcept {
    str x = @~ MOCK:INVALID ~
    print("in try block")
} retry {
    str x = @~ MOCK:TRUE fallback ~
    print("in retry block")
}
print(x)
""",

    "nested_llmexcept": AI_SETUP + """
llmexcept {
    llmexcept {
        str x = @~ MOCK:INVALID ~
    } retry {
        str x = @~ MOCK:INVALID again ~
    }
} retry {
    str x = @~ MOCK:TRUE final ~
}
print(x)
""",

    "llmexcept_in_loop": AI_SETUP + """
for int i in range(3):
    llmexcept {
        int x = @~ MOCK:INVALID ~
    } retry {
        int x = i
    }
    print(x)
""",

    "conditional_retry": AI_SETUP + """
bool should_fail = True
llmexcept {
    if should_fail:
        int x = @~ MOCK:INVALID ~
    else:
        int x = @~ MOCK:42 ~
} retry {
    int x = 0
}
print(x)
""",
}


# ============================================================================
# Snapshot Protocol Samples
# ============================================================================

SNAPSHOT_SAMPLES = {
    "user_object_snapshot": AI_SETUP + """
class Counter:
    int value

    func void __snapshot__(intent ctx):
        ctx.smear("Counter value: " + str(self.value))

Counter c = Counter(42)
llmexcept {
    str x = @~ MOCK:INVALID ~
} retry {
    str x = @~ MOCK:TRUE with counter ~
}
print(x)
""",
}


# ============================================================================
# Pytest Fixtures
# ============================================================================

@pytest.fixture
def behavior_sample(request):
    """Fixture to access BEHAVIOR_SAMPLES by key"""
    return BEHAVIOR_SAMPLES[request.param]


@pytest.fixture
def intent_sample(request):
    """Fixture to access INTENT_SAMPLES by key"""
    return INTENT_SAMPLES[request.param]


@pytest.fixture
def llmexcept_sample(request):
    """Fixture to access LLMEXCEPT_SAMPLES by key"""
    return LLMEXCEPT_SAMPLES[request.param]


@pytest.fixture
def snapshot_sample(request):
    """Fixture to access SNAPSHOT_SAMPLES by key"""
    return SNAPSHOT_SAMPLES[request.param]
