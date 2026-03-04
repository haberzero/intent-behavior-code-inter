# IBC-Inter Architecture Design Guide

## 1. Introduction
This document outlines the architectural principles, patterns, and component interactions of the IBC-Inter compiler and runtime. It serves as a guide for understanding the system's design choices, particularly those made during the major refactoring phases.

## 2. Core Architecture

IBC-Inter follows a modular, component-based architecture with a clear separation between compilation (static analysis) and execution (runtime).

### 2.1. Dependency Injection (DI)
The system uses a manual Dependency Injection pattern via `ServiceContext`.
- **Purpose**: To manage the lifecycle of singleton services (`Interpreter`, `ModuleManager`, `Evaluator`, `LLMExecutor`) and resolve circular dependencies.
- **Key Component**: `core/runtime/interpreter/interfaces.py` (ServiceContext Protocol).
- **Implementation**: `core/runtime/interpreter/interpreter.py` (ServiceContextImpl).
- **Initialization**:
  1. Instantiate independent services (`RuntimeContext`, `Evaluator`).
  2. Instantiate dependent services with placeholders (`ModuleManager(interpreter=None)`).
  3. Construct `ServiceContext`.
  4. Perform Setter Injection to resolve cycles (e.g., `module_manager.set_interpreter(interpreter)`).

### 2.2. Compiler Architecture (Mediator Pattern)
The Parser uses the Mediator Pattern to coordinate complex parsing logic.
- **Problem**: `StatementComponent` needs to parse declarations, and `DeclarationComponent` needs to parse statements, creating a cycle.
- **Solution**: `ParserContext` acts as the Mediator.
- **Flow**:
  - Components (`ExpressionComponent`, `StatementComponent`, etc.) hold a reference to `ParserContext`.
  - Components access each other *only* through `ParserContext` (e.g., `self.context.statement_parser`).
  - `Parser` initializes all components and registers them with the context.

### 2.3. Runtime Architecture (Single Interpreter)
The runtime uses a "Single Interpreter, Multiple Scopes" model.
- **Old Model**: A new `Interpreter` instance was created for every imported module. Heavy and state-isolated.
- **New Model**: A single `Interpreter` instance is reused.
- **Mechanism**: `execute_module(module, scope=...)`. The interpreter temporarily switches its active `RuntimeContext` to the target module's scope, executes code, and then switches back.
- **Benefit**: Massive performance improvement and correct sharing of global state (intrinsics).

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
