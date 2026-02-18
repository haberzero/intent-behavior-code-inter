# IBC-Inter Type System Refactoring Specification

## 1. Overview

This document outlines the plan to refactor the IBC-Inter type system to support strict type checking, generics, and a robust symbol table, as recommended by the third-party audit. The goal is to move from a string-based or ad-hoc type checking mechanism to a formal Type Object system.

## 2. Problem Statement

Current implementation fails to handle:
1.  Container types like `list` and `dict` in variable declarations.
2.  Generic type instantiation like `List[int]` or `Dict[str, int]`.
3.  Strict type compatibility checks (currently relies on string matching or incomplete logic).
4.  Distinction between a Type Definition (e.g., `List`) and a Type Instance (e.g., `List[int]`).

## 3. Proposed Changes

### 3.1 Type System (`utils/semantic/types.py`)

We will introduce a clear distinction between **Primitive Types**, **Generic Definitions**, and **Instantiated Types**.

- **`Type` (Base Class)**
  - `PrimitiveType`: `int`, `float`, `str`, `bool`
  - `VoidType`: `void`
  - `AnyType`: `Any`, `var`
  - **`GenericDefinitionType`**: Represents the raw generic type (e.g., `List`, `Dict`).
    - Attributes: `name`, `type_params_count` (e.g., List takes 1, Dict takes 2).
  - **`ListType`**: Represents an instantiated List (e.g., `List[int]`).
    - Attributes: `element_type` (Type).
  - **`DictType`**: Represents an instantiated Dict (e.g., `Dict[str, int]`).
    - Attributes: `key_type` (Type), `value_type` (Type).
  - `FunctionType`: `(args...) -> return_type`

### 3.2 Symbol Table (`utils/semantic/symbol_table.py`)

The symbol table must be pre-populated with all built-in types, including container types.

- **Register Built-ins**:
  - `int`, `float`, `str`, `bool` -> `PrimitiveType`
  - `list` -> `GenericDefinitionType('list', 1)` (Supporting `list` keyword)
  - `List` -> `GenericDefinitionType('List', 1)` (Supporting `List` keyword for typing)
  - `dict` -> `GenericDefinitionType('dict', 2)`
  - `Dict` -> `GenericDefinitionType('Dict', 2)`
  - `Any` -> `AnyType`
  - `void` -> `VoidType`

### 3.3 Semantic Analyzer (`utils/semantic/analyzer.py`)

We will implement a robust `TypeResolver` within the analyzer.

- **`_resolve_type_node(node)`**:
  - **Input**: AST Node (`Name`, `Subscript`).
  - **Output**: A `Type` object.
  - **Logic**:
    1.  If `Name`: Look up symbol.
        - If symbol is `PrimitiveType` -> Return it.
        - If symbol is `GenericDefinitionType` -> Return it (allowed in some contexts, or treated as `List[Any]` if used as raw type? Strict mode might require instantiation).
          - *Decision*: Bare `list` means `List[Any]`.
    2.  If `Subscript` (e.g., `List[int]`):
        - Resolve `value` (e.g., `List`) -> Must be `GenericDefinitionType`.
        - Resolve `slice` (e.g., `int`) -> Must be `Type`.
        - Instantiate: Create `ListType(element_type)` or `DictType(key, value)`.
        - Validate param count.

- **`visit_Assign`**:
  - Strict type checking using `_is_type_compatible`.
  - Ensure variable declaration updates symbol table with correct `Type` object.

- **`visit_BinOp`**:
  - Strict type rules (e.g., `int + int = int`).

## 4. Migration Strategy

1.  **Phase 1**: Update `types.py` with new classes.
2.  **Phase 2**: Update `symbol_table.py` to register new types.
3.  **Phase 3**: Update `analyzer.py` logic.
4.  **Phase 4**: Add comprehensive tests.

## 5. Risk Mitigation

- **Backward Compatibility**: We will support both `list` and `List` for now.
- **Incremental Testing**: We will add tests for each phase.
- **Verification Script**: A script will be provided to verify the type system consistency.
