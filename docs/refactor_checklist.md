# Checklist for Type System Refactoring

- [ ] `types.py` contains `GenericDefinitionType`.
- [ ] `symbol_table.py` registers `List`, `Dict`, `list`, `dict`.
- [ ] `analyzer.py` correctly resolves `List[int]` to `ListType(int)`.
- [ ] `analyzer.py` correctly resolves `Dict[str, int]` to `DictType(str, int)`.
- [ ] `analyzer.py` correctly resolves bare `list` to `ListType(Any)`.
- [ ] `test_semantic_generics.py` passes.
- [ ] `reproduce_issue.py` (modified to be valid) passes.
- [ ] Existing tests pass.
