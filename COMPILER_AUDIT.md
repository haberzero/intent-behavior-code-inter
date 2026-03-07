# Compiler Semantic Audit & Technical Debt Report - 2026-03-07

## 1. Executive Summary
This report documents the architectural compromises and technical risks introduced during the transition to a standardized fixture-based testing suite. While the current 18 tests pass, several "deep-seated" issues in the compiler's semantic and structural logic have been identified that may impact future extensibility and the "everything is an object" design philosophy.

## 2. Identified Technical Debt & Risks

### 2.1. Identity Fragility (node_uid Coupling)
- **Problem**: The `SymbolTable.define` method currently relies on `node_uid` to allow re-definitions during multi-pass scanning.
- **Location**: `core/compiler/semantic/symbols.py:L11-17`
- **Risk**: High. This couples a logical "Symbol" to a physical "AST Node" identity.
- **Future Impact**: Any future AST transformations, desugaring, or macro systems that generate new nodes for the same logical symbol will break this check. It prevents the compiler from being truly "dynamic" in its code generation phase.

### 2.2. Scope Isolation via "Blacklist" Scanning
- **Problem**: `LocalSymbolCollector` (Pass 2.5) uses an explicit list of nodes (`FunctionDef`, `ClassDef`) to block recursive scanning into nested scopes.
- **Location**: `core/compiler/semantic/collector.py:L142-146`
- **Risk**: Medium (Maintenance). It's a "blacklist" approach.
- **Architecture Violation**: Violates the pure Visitor pattern. The top-level collector must "know" the internal scope-handling behavior of every node. Adding new scope-bearing nodes (e.g., `Namespace`) requires manual updates to this collector.

### 2.3. Stateful Parser (Intent Pre-consumption)
- **Problem**: The parser now consumes "pending intents" before parsing specific declaration nodes to avoid conflicts with nested blocks.
- **Location**: `core/compiler/parser/components/declaration.py:L82`
- **Risk**: Medium. Makes the parser increasingly stateful.
- **Future Impact**: Complex nesting of intents or decorators might lead to "intent stealing" where an intent is captured by the wrong subsequent node.

### 2.4. Design Philosophy Mismatch ("Everything is an Object")
- **Issue**: The `SymbolTable` and `Scope` are currently implemented as simple dictionary wrappers rather than first-class IBCI objects.
- **Philosophical Gap**: In a true "everything is an object" system, the Scope itself should be an object that can be reflected upon and manipulated by IBCI code at compile-time or runtime.

### 2.5. Type Erasure & Shadow Implementation
- **Issue**: Several Visitor methods (e.g., `Compare`, `ListExpr`) were implemented as "stubs" returning `STATIC_ANY` or `STATIC_BOOL` to pass smoke tests.
- **Location**: `core/compiler/semantic/semantic_analyzer.py`
- **Risk**: High (False Security). Tests pass, but real semantic constraints (e.g., operator overloading, list element homogeneity) are not yet enforced.
- **Future Impact**: `none` is mapped directly to `STATIC_VOID`, potentially losing the "Object" nature of `None` (e.g., if we want `None.to_str()` to work later).

## 3. Fixture System Flaws (Current State)
- **Over-coupling**: `core_syntax.ibci` is too monolithic. A failure in basic variable parsing cascades into inheritance and control flow tests.
- **Lack of Pre-validation**: Fixtures are used as the "Source of Truth" without being validated against a "Golden Parser" first, making them prone to syntax drift (e.g., Python-style `except` syntax).

## 4. Proposed Remediation Path
1. **Decouple Identity**: Move from `node_uid` to logical path-based symbol identification (e.g., `pkg.module.Class.method`).
2. **Objectify Scopes**: Refactor `SymbolTable` to be a first-class IBCI Object.
3. **Granular Fixtures**: Split the monolithic suite into responsibility-focused files while maintaining a "Smoke Test" master file.
4. **Strict Type Analysis**: Replace `STATIC_ANY` stubs with full operator and type compatibility logic.
