# IBC-Inter Architecture Design Guide

## 1. Introduction
This document outlines the architectural principles, patterns, and component interactions of the IBC-Inter compiler and runtime. It serves as a guide for understanding the system's design choices, particularly those made during the major refactoring phases.

## 2. Core Architecture

IBC-Inter follows a 3-layer data-driven architecture, ensuring total decoupling between logic and data.

### 2.1. Layer 1: Domain Model Layer (`core/domain/`)
The "Source of Truth". Contains 100% pure, read-only data structures.
- **AST**: Definitive structure of the IBCI language.
- **Symbols & StaticTypes**: The semantic backbone.
- **Artifact**: The serializable communication contract.

### 2.2. Layer 2: Production Layer (`core/compiler/`)
The "Factory". Transforms source code into data pools.
- **Side-Tabling**: Analysis results (symbol bindings, inferred types) are stored in mapping tables, keeping the AST immutable.
- **Flat Pooling (Black Magic)**: The `FlatSerializer` resolves complex memory object graphs into a flattened, UID-based JSON dictionary. This eliminates Python memory address dependencies and allows the interpreter to run in total isolation.

### 2.3. Layer 3: Execution Layer (`core/runtime/`)
The "Consumer". Executes the data pools produced by Layer 2.
- **Interpreter**: Directly walks the flattened data pool ("Pool-Walking"). It no longer needs to import compiler logic.
- **Intent Stack**: Manages hierarchical LLM intents (Global -> Block -> Call).

## 3. Interaction Patterns

### 3.1. Mediator Pattern (Parser)
The Parser coordinates complex parsing logic via `ParserContext`.
- **Problem**: `StatementComponent` needs to parse declarations, and `DeclarationComponent` needs to parse statements, creating a cycle.
- **Solution**: `ParserContext` acts as the Mediator.

### 3.2. Service Context (Runtime)
The runtime uses a manual Dependency Injection pattern via `ServiceContext`.
- **Purpose**: To manage the lifecycle of singleton services (`Interpreter`, `ModuleManager`, `Evaluator`, `LLMExecutor`) and resolve circular dependencies.

## 3. Subsystems

### 3.1. Type System Bridge
Bridging the gap between Static Analysis (Semantic) and Dynamic Execution (Runtime).
- **Semantic Type**: `UserDefinedType` (stores class name, scope, parent ref).
- **Runtime Object**: `ClassInstance` (stores fields, methods, interpreter ref).
- **The Bridge**: `ClassInstance` holds a `runtime_type` field pointing to its `UserDefinedType`.
- **Polymorphism**: `Interpreter.is_subclass_of` checks inheritance by traversing the `UserDefinedType.parent` chain. If runtime types are missing (dynamic execution), `ClassInstance` reconstructs the hierarchy on-the-fly.

### 3.2. Error Handling
- **Philosophy**: Catch early, report precisely.
- **Mechanism**:
  - Internal components raise `InterpreterError` (with `node` info).
  - `Interpreter.visit` (the main loop) wraps execution in a generic `try-except`.
  - Native Python exceptions (e.g., `ValueError`) are caught and wrapped into `InterpreterError`, attaching the current AST node to provide source location (line/col).
  - Errors are reported to `IssueTracker`.

### 3.3. Evaluator vs. Interpreter
- **Evaluator**: Pure expression evaluation (`1 + 1`, `a.b`). No side effects, no control flow.
- **Interpreter**: Statement execution, Control flow (`if`, `while`, `Call`), Side effects (`print`, `BehaviorExpr`).
- **Interaction**: The `Evaluator` delegates complex nodes (`Call`, `BehaviorExpr`) back to the `Interpreter` via `ServiceContext`.

## 4. Known Technical Debt

### 4.1. Scope Switching Hack
In `Interpreter.execute_module`, the `RuntimeContext`'s global scope is swapped by directly accessing the private member `_global_scope`.
**Plan**: Implement a `fork_with_scope()` method in `RuntimeContext`.

### 4.2. Incomplete Semantic Checks
`SemanticAnalyzer` validates class inheritance but lacks deep validation for class attribute access.
**Plan**: Implement attribute resolution in `visit_Attribute`.

## 5. Future Directions
- **Standard Library**: Implement `Prelude` with `math`, `io`, `json` modules.
- **Optimization**: Bytecode compilation (optional).
