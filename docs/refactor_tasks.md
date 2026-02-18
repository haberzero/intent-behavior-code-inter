# Tasks for Type System Refactoring

- [ ] **Phase 1: Infrastructure (Types)**
  - [ ] Update `utils/semantic/types.py`: Add `GenericDefinitionType`.
  - [ ] Update `utils/semantic/types.py`: Ensure `ListType` and `DictType` are robust and have `__eq__` and `__str__`.

- [ ] **Phase 2: Infrastructure (Symbol Table)**
  - [ ] Update `utils/semantic/symbol_table.py`: Register `list`, `List`, `dict`, `Dict` as `GenericDefinitionType`.
  - [ ] Ensure `int`, `float`, `str`, `bool` are registered as `PrimitiveType`.

- [ ] **Phase 3: Semantic Logic (Analyzer)**
  - [ ] Update `utils/semantic/analyzer.py`: Implement `_resolve_type_node` to handle `GenericDefinitionType` and `Subscript` instantiation.
  - [ ] Update `utils/semantic/analyzer.py`: Handle bare `list` as `List[Any]`.
  - [ ] Update `utils/semantic/analyzer.py`: Improve `_is_type_compatible` for generics (covariant checking?). For now, invariant or simple compatibility.

- [ ] **Phase 4: Testing & Verification**
  - [ ] Create `tests/test_semantic_generics.py` covering:
    - `List[int]`, `Dict[str, int]`
    - Nested types `List[List[int]]`
    - Type mismatch `List[int] = ["a"]` (if array literal analysis is implemented)
    - Variable assignment type check.
  - [ ] Run existing tests to ensure no regression.
  - [ ] Create `tools/verify_types.py` to introspect symbol table and types.
