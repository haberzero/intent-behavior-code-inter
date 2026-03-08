# IBCI AST & Semantic Architecture Refactor Guide (Deep Audit)
**Version**: 2026-03-07-001
**Author**: Code Assistant
**Status**: Comprehensive Guidance (Awaiting Execution)

---

## 1. Introduction
This document provides an exhaustive, step-by-step technical blueprint for refactoring the IBC-Inter (Intent-Behavior Code Inter) compiler architecture. The goal is to move from a "Metadata-as-Property" (Attaching metadata to nodes) model to a "Metadata-as-Node/Context" (Wrapping or context-stacking metadata) model. This will eliminate redundant logic, reduce architectural fragility, and align with the "Everything is an Object" core philosophy.

---

## 2. Issue 1: `llmexcept` (Behavioral Fallback) - [COMPLETED]
### 2.1 Description
Previously, `llmexcept` logic was implemented as an optional `llm_fallback: List[Stmt]` attribute. This has been refactored into a dedicated wrapper node.

### 2.2 Refactored Implementation
- **Node**: `LLMExceptionalStmt(primary: Stmt, fallback: List[Stmt])` in [parser_types.py](file:///c:/myself/proj/intent-behavior-code-inter/core/types/parser_types.py).
- **Parser**: `statement.py` now produces `LLMExceptionalStmt` when `llmexcept:` is encountered.
- **Semantic**: `SemanticAnalyzer.visit_LLMExceptionalStmt` provides a unified entry point for fallback analysis.
- **Collector**: `SymbolCollector` and `LocalSymbolCollector` recursively scan both `primary` and `fallback` blocks.

---

## 3. Issue 2: `IntentInfo` (Intent Metadata) - [COMPLETED]
### 3.1 Description
Intent comments (e.g., `@~...~`) are currently parsed as `IntentInfo` and attached to nodes. The Parser uses a stateful "pending intent" system to inject these into the next parsed node.

### 3.2 Refactored Implementation
- **Nodes**: `AnnotatedStmt` and `AnnotatedExpr` in [parser_types.py](file:///c:/myself/proj/intent-behavior-code-inter/core/types/parser_types.py).
- **Parser**: `declaration.py` now wraps statements in `AnnotatedStmt` when a pending intent is present, instead of property injection.
- **Semantic**: `SemanticAnalyzer` and `Collector` visit `AnnotatedStmt/Expr`, allowing unified intent processing.
- **Impact**: Parser state is now safely consumed at the statement level, ensuring no "ghost intents" linger across blocks.

---

## 4. Issue 3: `scene_tag` (Control Flow Context) - [COMPLETED]
### 4.1 Description
Static `scene_tag` attributes on `Expr` nodes have been removed in favor of a dynamic semantic context stack.

### 4.2 Refactored Implementation
- **AST**: `Expr.scene_tag` removed from [parser_types.py](file:///c:/myself/proj/intent-behavior-code-inter/core/types/parser_types.py).
- **Context Stack**: `SemanticAnalyzer` maintains `self.scene_stack`.
- **Side-Table**: `SemanticAnalyzer.node_scenes` maps node UIDs to their analyzed scene context, preserving analysis results without polluting the AST.
- **Parser**: `_set_scene_recursive` removed from `component.py`.

---

## 5. Issue 4: `type_annotation` (Variable Type Metadata)
### 5.1 Description
Variable types are currently optional fields on `Assign` or `arg` nodes. This limits type annotations to specific "declaration" points.

### 5.2 Current Implementation Locations
- **File**: [parser_types.py](file:///c:/myself/proj/intent-behavior-code-inter/core/types/parser_types.py)
    - `Assign.type_annotation` (L150)
    - `arg.annotation` (L269)

### 3.3 Proposed Architectural Change
**Type-Annotated Expression Node (`TypeAnnotatedExpr`)**.
```python
@dataclass
class TypeAnnotatedExpr(Expr):
    target: Expr
    annotation: Expr # The type node
```

### 3.4 Implementation Checklist
1. [ ] **AST Modification**:
    - Add `TypeAnnotatedExpr` to `parser_types.py`.
    - Remove `type_annotation` from `Assign`.
2. [ ] **Parser Refactoring**:
    - Modify `variable_declaration` in `declaration.py`.
    - Return an `Assign` where the target is a `TypeAnnotatedExpr`.
3. [ ] **Semantic Analysis Refactoring**:
    - Implement `visit_TypeAnnotatedExpr`:
        - Resolve the `annotation` to a `StaticType`.
        - Visit the `target`.
        - Associate the type with the symbol in the current scope.

### 5.5 Impact Analysis
- **Risk**: Medium. Requires updating the `Assign` logic which is central to semantic analysis.
- **Benefit**: High. Enables C-style casts or inline annotations like `(x as int)`.

---

## 6. Issue 5: `filter_condition` (Intent Filtering)
### 6.1 Description
`filter_condition` is hardcoded into the `For` loop node for syntax like `for x in list if @~...~`.

### 6.2 Current Implementation Locations
- **File**: [parser_types.py](file:///c:/myself/proj/intent-behavior-code-inter/core/types/parser_types.py)
    - `For.filter_condition` (L167)

### 6.3 Proposed Architectural Change
**Filtered Expression Wrapper (`FilteredExpr`)**.
```python
@dataclass
class FilteredExpr(Expr):
    iterable: Expr
    condition: Expr
```

### 6.4 Implementation Checklist
1. [ ] **AST Modification**:
    - Add `FilteredExpr` to `parser_types.py`.
    - Remove `filter_condition` from `For`.
2. [ ] **Parser Refactoring**:
    - Update `for_statement` parsing. 
    - Wrap the `iter` expression in a `FilteredExpr` if an `if` intent is found.
3. [ ] **Semantic Analysis Refactoring**:
    - Implement `visit_FilteredExpr`.
    - Validate that the `iterable` is indeed iterable and the `condition` returns a boolean (or is a valid intent).

### 6.5 Impact Analysis
- **Risk**: Low. Localized change.
- **Benefit**: Medium. Allows filtering in other contexts (e.g., list comprehensions) for free.

---

## 7. Issue 6: Analysis Result Pollution (Side Tables)
### 7.1 Description
`symbol_uid` and `inferred_type` are stored directly on the AST nodes. This makes the AST "mutable" and "polluted" after semantic analysis.

### 7.2 Current Implementation Locations
- **File**: [parser_types.py](file:///c:/myself/proj/intent-behavior-code-inter/core/types/parser_types.py)
    - `ASTNode.symbol_uid` (L61)
    - `Expr.inferred_type` (L85)

### 7.3 Proposed Architectural Change
**Side-Table (Mapping) Storage**.
Remove these fields from the AST nodes. In `SemanticAnalyzer`, maintain:
- `self.node_to_symbol: Dict[str, str]` (Node UID -> Symbol UID)
- `self.node_to_type: Dict[str, StaticType]` (Node UID -> Type)

### 7.4 Implementation Checklist
1. [ ] **AST Modification**:
    - Remove `symbol_uid` and `inferred_type` from `ASTNode` and `Expr`.
2. [ ] **Semantic Analysis Refactoring**:
    - Add the two dictionaries to `SemanticAnalyzer`.
    - Update every `node.symbol_uid = ...` to `self.node_to_symbol[node.uid] = ...`.
    - Update every `node.inferred_type = ...` to `self.node_to_type[node.uid] = ...`.
3. [ ] **Serialization Update**:
    - Update `CompilationArtifact` to include these side tables so the interpreter can look up symbols/types by Node UID.

### 7.5 Impact Analysis
- **Risk**: Very High. Affects almost every line of the semantic analyzer and the bridge to the interpreter.
- **Benefit**: Extreme. Enables incremental compilation and keeps the AST as a pure, immutable representation of the source.

---

## 8. Summary of Breaking Changes
- **AST Topology**: Every tool relying on the AST structure (e.g., a formatter or linter) will need updates.
- **Serialization**: The binary format of `CompilationArtifact` will change.
- **Visitor Methods**: All `visit_*` methods must be reviewed for the new node types.

## 8. Issue 7: Global Diagnostic Coupling (`IssueTracker`) - [COMPLETED]
### 8.1 Description
The compiler currently depends on the `foundation` layer's `IssueTracker`. This creates an architectural leak where the compiler must know about system-level logging and issue management.

### 8.2 Refactored Implementation
- **Interface**: `DiagnosticReporter` protocol in [diagnostics.py](file:///c:/myself/proj/intent-behavior-code-inter/core/compiler/support/diagnostics.py).
- **Adapter**: `IssueTrackerAdapter` in [issue_adapter.py](file:///c:/myself/proj/intent-behavior-code-inter/core/compiler/support/issue_adapter.py) wraps the old `IssueTracker`.
- **Refactoring**: All compiler components (Lexer, Parser, Analyzer) now use the `DiagnosticReporter` interface.
- **Impact**: The compiler is now theoretically standalone and decoupled from the `foundation` layer's concrete error reporting logic.

---
## 9. Conclusion: The "Pool-Walking" Vision
The ultimate goal of this AST refactor is to prepare the system for **"Pool-Walking Execution"**. 
By converting metadata to structural nodes and using side-tables for analysis results, the `FlatSerializer` will produce a self-contained JSON pool. The future Interpreter will walk this pool using type strings, finally achieving 100% decoupling from the `parser_types.py` source code.
