# Phase 2 Test Deletion Strategy
> Created: 2026-05-13
> Purpose: Guide systematic deletion of 1000+ redundant tests (Phase 2.3)

## Executive Summary

**Current state**: 1,326 total tests (1,235 legacy + 91 new contracts)
**Target state**: 300-400 tests
**Deletion needed**: ~950 tests (-72%)

## Deletion Categories

### Category A: FULL DELETION (Implementation Detail Tests)

These test **internal mechanisms** rather than **semantic guarantees**. They MUST be deleted entirely:

#### A1: Micro-Syntax Tests (DELETE ALL ~150 tests)
**Location**: `tests/e2e/test_e2e_core_syntax.py` (128 tests)
**Pattern**: Individual tests for literals, operators, basic assignments
**Examples**:
- `test_int_variable` / `test_str_variable` / `test_float_variable`
- `test_addition` / `test_subtraction` / `test_multiplication`
- `test_bool_variable_true` / `test_bool_variable_false`

**Why delete**: These are covered by contract tests (type invariants). Testing `3 + 4 = 7` doesn't validate semantic contracts.

**Replacement**: Already covered by `tests/contracts/test_type_invariants.py`

#### A2: White-Box VM Tests (DELETE ALL ~122 tests)
**Location**: `tests/runtime/test_vm_executor.py` (122 tests)
**Pattern**: Tests accessing `node_pool`, `find_node_uid`, interpreter internals
**Examples**:
- Tests using `find_node_uid(engine, "IbBinOp")`
- Tests directly calling `VMExecutor` handlers
- Tests validating handler dispatch tables

**Why delete**: These couple to implementation. VM refactoring breaks these tests even when semantics unchanged.

**Replacement**: Already covered by `tests/contracts/test_execution_model.py` (CPS/signals/frames)

#### A3: Axiom/Spec Layer Unit Tests (DELETE ALL ~243 tests)
**Location**: `tests/kernel/` (243 tests total)
- `test_typeref.py` (102 tests)
- `test_spec_layer.py` (81 tests)
- `test_axioms.py` (34 tests)
- `test_symbols.py` (26 tests)

**Pattern**: Low-level type system implementation testing
**Examples**:
- `test_typeref_int_construction`
- `test_spec_registry_resolve`
- `test_axiom_parent_chain`

**Why delete**: These test kernel implementation details. Type system contracts are validated by compiler + contract tests.

**Replacement**: Type contracts in `tests/contracts/test_type_invariants.py`

#### A4: Higher-Order Function Axiom Tests (DELETE ~50 of 112)
**Location**: `tests/e2e/test_e2e_higher_order.py`
**Pattern**: Tests checking axiom hierarchy, spec existence, capability presence
**Examples**:
- `test_fn_callable_spec_exists`
- `test_callable_axiom_not_dynamic`
- `test_behavior_parent_is_fn_callable`
- `test_fn_callable_has_call_capability`

**Why delete**: These are kernel/axiom white-box tests disguised as e2e tests.

**Keep**: Only functional closure/snapshot semantic tests (~62 tests)

### Category B: PARAMETRIZE & REDUCE (Similar Tests)

These have legitimate semantic value but can be consolidated via `@pytest.mark.parametrize`:

#### B1: Control Flow Tests (REDUCE 18 → 6)
**Location**: `tests/e2e/test_e2e_control_flow.py` (18 tests)
**Current**: Separate tests for each if/while/for/break/continue variant
**Target**: Parametrized tests covering all cases

**Example transformation**:
```python
# BEFORE (3 separate tests)
def test_if_true_branch():
    assert run_ibci('if True: print("yes")') == ["yes"]

def test_if_false_branch():
    assert run_ibci('if False: print("no")') == []

def test_if_else():
    assert run_ibci('if False: print("a") else: print("b")') == ["b"]

# AFTER (1 parametrized test)
@pytest.mark.parametrize("code,expected", [
    ('if True: print("yes")', ["yes"]),
    ('if False: print("no")', []),
    ('if False: print("a") else: print("b")', ["b"]),
])
def test_if_statement(code, expected):
    assert run_ibci(code) == expected
```

#### B2: Plugin Implementation Tests (REDUCE 98 → 30)
**Location**: `tests/runtime/test_plugin_implementations.py` (98 tests)
**Current**: Exhaustive testing of math.sqrt/json.dumps/time.sleep etc
**Target**: Smoke tests for each plugin (3-5 tests per plugin)

**Why reduce**: Plugins use Python stdlib. We don't need to validate Python's math.sqrt implementation.

### Category C: KEEP & MIGRATE (High-Value E2E)

These validate real semantic guarantees and should be kept/enhanced:

#### C1: LLM Integration (~30 tests) ✓ KEEP
**Locations**:
- `tests/e2e/test_e2e_llm_basic.py` (16 tests)
- `tests/e2e/test_e2e_llm_pipeline.py` (7 tests)
- `tests/compliance/test_concurrent_llm.py` (9 tests)

**Why keep**: Test LLM-specific semantics not covered by contracts (MOCK protocol edge cases, concurrent LLM execution)

#### C2: Intent System (~26 tests) ✓ KEEP
**Location**: `tests/e2e/test_e2e_intent.py` (26 tests)

**Why keep**: Complement contract tests with complex intent interaction scenarios

#### C3: llmexcept Edge Cases (~23 tests) ✓ KEEP
**Location**: `tests/e2e/test_e2e_llmexcept.py` (23 tests)

**Why keep**: Complex nested llmexcept scenarios beyond contract guarantees

#### C4: Multi-Interpreter Isolation (~15 tests) ✓ KEEP
**Location**: `tests/e2e/test_e2e_multi_interpreter.py` (15 tests)

**Why keep**: Critical isolation guarantees for spawn_isolated/collect

#### C5: Closure/Snapshot Semantics (~62 tests) ✓ KEEP
**Location**: `tests/e2e/test_e2e_higher_order.py` (62 of 112 tests)

**Why keep**: Complex closure capture, snapshot deep-clone semantics

#### C6: Module System (~14 tests) ✓ KEEP
**Location**: `tests/e2e/test_e2e_modules.py` (14 tests)

**Why keep**: Import resolution, cyclic dependencies

#### C7: Class OOP (~25 tests) ✓ KEEP
**Location**: `tests/e2e/test_e2e_classes.py` (25 tests)

**Why keep**: Inheritance, method resolution, __init__

#### C8: Exception Handling (~13 tests) ✓ KEEP
**Location**: `tests/e2e/test_e2e_exceptions.py` (13 tests)

**Why keep**: Exception propagation, try/except semantics

#### C9: Compiler Type Checking (~140 tests) ✓ KEEP
**Location**: `tests/compiler/` (140 tests total)

**Why keep**: Compiler semantic analysis, type checking, error codes

#### C10: Runtime Subsystems (~100 tests) ✓ KEEP (selective)
**Locations**:
- `tests/runtime/test_intent_context.py` (37 tests) - Keep 15 high-value
- `tests/runtime/test_ib_cell.py` (18 tests) - Keep all (core semantic)
- `tests/runtime/test_vm_llm_pipeline.py` (26 tests) - Keep 10 high-value
- `tests/runtime/test_llmexcept.py` (7 tests) - Keep all
- `tests/runtime/test_ddg_analysis.py` (16 tests) - Keep 5 high-value
- Others: Keep selectively

#### C11: SDK Tools (~53 tests) ✓ KEEP ALL
**Location**: `tests/sdk/` (53 tests)

**Why keep**: Tooling tests (check plugin, gen_spec) are orthogonal to language semantics

#### C12: Compliance Tests (~32 tests) ✓ KEEP ALL
**Location**: `tests/compliance/` (32 tests)

**Why keep**: Cross-implementation contracts

## Deletion Execution Plan

### Phase 2.3 Step 1: Delete Full Categories (Week 4 Day 1-2)

Delete files entirely:
```bash
rm tests/e2e/test_e2e_core_syntax.py           # -128 tests
rm tests/runtime/test_vm_executor.py            # -122 tests
rm tests/kernel/test_typeref.py                # -102 tests
rm tests/kernel/test_spec_layer.py             # -81 tests
rm tests/kernel/test_axioms.py                 # -34 tests
rm tests/kernel/test_symbols.py                # -26 tests
```

**Total deleted**: 493 tests

### Phase 2.3 Step 2: Selective Deletion + Parametrization (Week 4 Day 3-4)

Edit files to remove white-box sections:
- `tests/e2e/test_e2e_higher_order.py`: Remove axiom tests (~50 tests) → Keep ~62
- `tests/e2e/test_e2e_control_flow.py`: Parametrize → Reduce 18 → 6
- `tests/runtime/test_plugin_implementations.py`: Reduce 98 → 30
- `tests/runtime/test_intent_context.py`: Remove implementation tests 37 → 15
- `tests/runtime/test_vm_llm_pipeline.py`: Remove handler tests 26 → 10
- `tests/runtime/test_ddg_analysis.py`: Keep high-value only 16 → 5

**Total reduction**: ~200 tests

### Phase 2.3 Step 3: Verify & Document (Week 4 Day 5)

- Run regression: `python -m pytest tests/ -v`
- Expected: ~400 tests pass (91 contracts + ~310 curated tests)
- Update `tests/COVERAGE_MAP.md`
- Update `docs/TESTS_REORGANIZATION_TASK.md` §11 with completion

## Final Test Distribution

```
Contracts:        91 tests  (semantic invariants)
E2E High-Value:  170 tests  (complex interactions)
Compiler:        140 tests  (type checking)
SDK:              53 tests  (tooling)
Compliance:       32 tests  (cross-impl)
Runtime:          ~40 tests (core subsystems)
─────────────────────────────
TOTAL:           ~426 tests (-66% from 1,259 baseline)
```

## Success Criteria

- ✅ All remaining tests are black-box (no node_pool access)
- ✅ No micro-syntax tests (literals, basic operators)
- ✅ No axiom/kernel unit tests
- ✅ All tests validate semantic contracts, not implementation
- ✅ Test suite runs in <60 seconds
- ✅ Coverage remains >85% on critical paths
- ✅ Documentation reflects new testing philosophy

## Risk Mitigation

1. **Git branches**: Each deletion step is a separate commit
2. **Baseline validation**: Run full regression before any deletion
3. **Incremental approach**: Delete Category A first, verify, then proceed
4. **Semantic coverage**: Cross-reference deleted tests with contract coverage
5. **Rollback plan**: Any semantic gap discovered → add to contracts before deleting

## References

- Phase 2 plan: `docs/TESTS_REORGANIZATION_TASK.md` §11
- Test philosophy: `docs/TEST_PHILOSOPHY.md`
- Contract tests: `tests/contracts/`
- Coverage map: `tests/COVERAGE_MAP.md`
