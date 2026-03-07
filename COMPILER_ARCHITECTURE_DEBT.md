# IBCI Compiler Architecture & File Placement Debt Report - 2026-03-07
**Status**: Critical Audit (Pre-refactor Phase)
**Author**: Code Assistant

---

## 1. Issue: `serializer.py` (The Misplaced Backend)
### 1.1 Description
The file `serializer.py` is currently located in `core/compiler/semantic/`. However, its primary responsibility is the **serialization of the compilation results** (AST, SymbolTable, Types) into a flat, serializable format for storage or transmission.

### 1.2 Architectural Mismatch
- **Phase Violation**: Semantic Analysis is responsible for verifying correctness and enriching the AST with metadata. Serialization is an **Output/Backend** concern.
- **Dependency Paradox**: Because it is located inside the `semantic` folder, it creates a circular conceptual dependency where the "Analysis" folder is also responsible for "Exporting."
- **Coupling**: It must have intimate knowledge of every AST node (to serialize them) and every SymbolTable structure. Placing it deep within `semantic` hides this critical dependency from the rest of the compiler's top-level structure.

### 1.3 Current File Path
- `core/compiler/semantic/serializer.py`

---

## 2. Issue: `artifact.py` (The Orphaned Blueprint)
### 2.1 Description
The file `artifact.py` defines `CompilationArtifact`, which is the container for all `CompilationResult` objects in a multi-module project.

### 2.2 Architectural Mismatch
- **Structural Inconsistency**: It sits at the root of `core/compiler/`, while its child component `CompilationResult` sits inside `core/compiler/semantic/`. This breaks the "Parent-Child" directory hierarchy.
- **Responsibility Confusion**: As the "Blueprint" for the interpreter, it is the bridge between the compiler and the runtime. Its current location makes it look like a generic compiler utility rather than the **Final Product Definition**.

### 2.3 Current File Path
- `core/compiler/artifact.py`

---

## 3. Issue: `prelude.py` (Static Runtime vs. Semantic Analysis)
### 3.1 Description
The file `prelude.py` defines the built-in functions (`print`, `range`, etc.) and primitive types (`int`, `str`, `float`) that are injected into the global symbol table.

### 3.2 Architectural Mismatch
- **Language Standard Library Coupling**: It is currently treated as a component of the Semantic Analysis phase (`core/compiler/semantic/prelude.py`).
- **Conceptual Error**: Built-in symbols are a part of the **Language Specification / Runtime Environment**, not the "Analysis" logic itself. 
- **Future Risk**: If IBCI were to support different standard libraries or target different runtimes (e.g., a "light" version vs. a "full" version), the core semantic analyzer would have to be modified because the prelude is hardcoded inside its directory.

### 3.3 Current File Path
- `core/compiler/semantic/prelude.py`

---

## 4. Issue: `parser_types.py` (AST as Global Types)
### 4.1 Description
The entire AST (Abstract Syntax Tree) node definitions (e.g., `Assign`, `If`, `Expr`, `BinOp`) are located in `core/types/parser_types.py`.

### 4.2 Architectural Mismatch
- **Asset Ownership**: The AST is a **Compiler Internal Asset**. Placing it in `core/types/` makes it appear as a shared data structure for the entire system (including the foundation and infrastructure), which it is not.
- **Directory Bloat**: `core/types/` should ideally contain primitive, low-level types (like `TokenType` or `Severity`). Mixing high-level structural nodes (AST) with atomic types makes the `core/types` module too heavy and unfocused.
- **Boundary Violation**: It encourages the runtime or foundation to depend directly on compiler-specific structures, making it harder to swap out the parser or the AST representation in the future.

### 4.3 Current File Path
- `core/types/parser_types.py`

---

## 5. Issue: `IssueTracker` & Infrastructure Coupling
### 5.1 Description
The `IssueTracker` and `Issue` classes are used by the compiler to report syntax and semantic errors. They are defined in `core/foundation/interfaces.py` and implemented in foundation support.

### 5.2 Architectural Mismatch
- **Infrastructure Leak**: The compiler (a high-level logic module) is forced to import and understand interfaces from the `foundation` layer (a low-level infrastructure layer).
- **Inverted Dependencies**: Ideally, the compiler should define its own "Diagnostic" interface, and the system should provide an implementation. Currently, the compiler is "aware" of how the system tracks issues, which limits its ability to run in a standalone, lightweight environment without the full foundation.

### 5.3 Current Implementation Context
- Referenced in `core/compiler/semantic/semantic_analyzer.py` and `core/compiler/parser/core/context.py`.

---

## 7. Deep Analysis: `FlatSerializer` & Interpreter Decoupling
### 7.1 The Role of `FlatSerializer`
`FlatSerializer` is not just a storage utility; it is the **Standard Intermediate Representation (SIR)** of the IBCI compiler. 
- **Current State**: It transforms the class-based AST into a dictionary-based `node_pool` where each node is identified by a `_type` string (e.g., `"Assign"`) and a `uid`.
- **Misconception**: The interpreter currently walking the AST classes (`parser_types.py`) is a "legacy" behavior from the initial prototype phase. 
- **Target State**: The interpreter should be capable of running directly on the `node_pool` output of `FlatSerializer`. In this mode, the interpreter would never need to `import core.types.parser_types`, as it would operate on raw dictionaries and strings.

### 7.2 Decoupling Roadmap
1. **Refine SIR**: Ensure `FlatSerializer` outputs all necessary metadata (including the newly added `LLMExceptionalStmt` and `AnnotatedNode`) into the JSON-compatible pool.
2. **Interpreter Evolution**: Refactor `Interpreter.visit` to support a "Pool-Walking" mode.
    - Instead of `isinstance(node, ast.Assign)`, it would check `node_data["_type"] == "Assign"`.
    - This allows the interpreter to run on a compiled `.ibci_bin` file without the compiler's source code or AST definitions present.

## 8. Deep Analysis: `IssueTracker` Refactoring Route
### 8.1 The Core Problem
The current `IssueTracker` is a "Global Singleton" style service that mixes compiler diagnostics with runtime errors and infrastructure logging. This forces the compiler to be aware of the `foundation` layer.

### 8.2 Proposed Refactoring Roadmap
1. **Define `CompilerDiagnostic` Interface**:
    - Create `core/compiler/diagnostic.py`.
    - Define a lightweight `Diagnostic` structure and a `DiagnosticReporter` protocol.
    - This interface should only care about `Severity`, `Message`, `Code`, and `Location`.
2. **Implementation (The Adapter)**:
    - Create `core/compiler/support/diagnostic_adapter.py`.
    - This adapter implements `DiagnosticReporter` by internally delegating to the existing `foundation` `IssueTracker`.
    - **Benefit**: The compiler's core logic only sees the clean `DiagnosticReporter` interface, while the system still collects all errors in one place.
3. **Phased Migration**:
    - **Step 1**: Update `Lexer` and `Parser` to use the new interface.
    - **Step 2**: Update `SemanticAnalyzer`.
    - **Step 3**: Once the compiler is fully isolated, the `DiagnosticReporter` implementation can be swapped with a purely compiler-specific one for standalone tools (like a CLI linter).
