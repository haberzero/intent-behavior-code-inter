
import os
import sys
from typing import Dict, Any

# Ensure project root is in sys.path
sys.path.append(os.getcwd())

from utils.scheduler import Scheduler
from utils.parser.parser import Parser
from utils.lexer.lexer import Lexer
from utils.semantic.semantic_analyzer import SemanticAnalyzer
from utils.diagnostics.issue_tracker import IssueTracker
from typedef.symbol_types import Symbol, SymbolType
from typedef.scope_types import ScopeNode

def print_scope(name: str, scope: ScopeNode):
    print(f"--- Scope Dump: {name} ---")
    if not scope:
        print("  <None>")
        return
    
    # Access internal symbols if possible, assuming ScopeNode has 'symbols' dict
    # Or use resolve for known names
    # Let's inspect __dict__ to find storage
    if hasattr(scope, 'symbols'):
        for sym_name, sym in scope.symbols.items():
            type_info_str = str(sym.type_info) if sym.type_info else "None"
            origin_str = f"Origin->{sym.origin_symbol.name}" if sym.origin_symbol else "NoOrigin"
            print(f"  Symbol: {sym_name:<15} | Type: {sym.type.name:<10} | TypeInfo: {type_info_str:<20} | {origin_str} | ID: {id(sym)}")
    else:
        print("  (Cannot iterate symbols, scope implementation hidden)")
    print("-------------------------")

def debug_compilation():
    root_dir = os.path.abspath("tests/test_data/robust_project")
    # Ensure files exist (created by previous test runs, assuming they persist)
    # If not, create them
    if not os.path.exists(root_dir):
        os.makedirs(root_dir)
        
    files = {
        "c.ibci": "var C_VAL = 42\n",
        "b.ibci": "import c\nfunc get_c_val() -> int:\n    return c.C_VAL\n",
        "a.ibci": "import b\nvar res = b.get_c_val()\n"
    }
    
    for fname, content in files.items():
        with open(os.path.join(root_dir, fname), 'w') as f:
            f.write(content)

    print("=== Starting Debug Compilation Sequence ===")
    
    # Shared Caches
    scope_cache = {}
    tracker = IssueTracker()
    
    # 1. Compile C
    print("\n[Step 1] Compiling C (Leaf)")
    c_path = os.path.join(root_dir, "c.ibci")
    with open(c_path, 'r') as f: c_src = f.read()
    
    c_lexer = Lexer(c_src, tracker)
    c_tokens = c_lexer.tokenize()
    c_parser = Parser(c_tokens, tracker, scope_cache, package_name="c")
    c_ast = c_parser.parse()
    
    print(f"Parsed C. Scope ID: {id(c_ast.scope)}")
    print_scope("C (Pre-Analysis)", c_ast.scope)
    
    c_analyzer = SemanticAnalyzer(tracker)
    c_analyzer.analyze(c_ast)
    
    print_scope("C (Post-Analysis)", c_ast.scope)
    scope_cache["c"] = c_ast.scope
    
    # Verify C_VAL has type
    c_val = c_ast.scope.resolve("C_VAL")
    if c_val.type_info and c_val.type_info.name == "int":
        print("SUCCESS: C_VAL is int")
    else:
        print(f"FAILURE: C_VAL is {c_val.type_info}")

    # 2. Compile B
    print("\n[Step 2] Compiling B (Depends on C)")
    b_path = os.path.join(root_dir, "b.ibci")
    with open(b_path, 'r') as f: b_src = f.read()
    
    b_lexer = Lexer(b_src, tracker)
    b_tokens = b_lexer.tokenize()
    b_parser = Parser(b_tokens, tracker, scope_cache, package_name="b")
    b_ast = b_parser.parse()
    
    print(f"Parsed B. Scope ID: {id(b_ast.scope)}")
    print_scope("B (Pre-Analysis)", b_ast.scope)
    
    # Check import c symbol in B
    c_sym_in_b = b_ast.scope.resolve("c")
    print(f"Symbol 'c' in B: {c_sym_in_b}")
    if c_sym_in_b.exported_scope:
        print(f"  Exported Scope ID: {id(c_sym_in_b.exported_scope)}")
        print(f"  Match C Scope? {id(c_sym_in_b.exported_scope) == id(c_ast.scope)}")
    
    b_analyzer = SemanticAnalyzer(tracker)
    b_analyzer.analyze(b_ast)
    
    print_scope("B (Post-Analysis)", b_ast.scope)
    scope_cache["b"] = b_ast.scope
    
    # Verify get_c_val
    get_c = b_ast.scope.resolve("get_c_val")
    if get_c.type_info and get_c.type_info.name == "function":
        print(f"SUCCESS: get_c_val is function. Return type: {get_c.type_info.return_type}")
    else:
        print(f"FAILURE: get_c_val is {get_c.type_info}")

    # 3. Compile A
    print("\n[Step 3] Compiling A (Depends on B)")
    a_path = os.path.join(root_dir, "a.ibci")
    with open(a_path, 'r') as f: a_src = f.read()
    
    a_lexer = Lexer(a_src, tracker)
    a_tokens = a_lexer.tokenize()
    a_parser = Parser(a_tokens, tracker, scope_cache, package_name="a")
    a_ast = a_parser.parse()
    
    print(f"Parsed A. Scope ID: {id(a_ast.scope)}")
    print_scope("A (Pre-Analysis)", a_ast.scope)
    
    a_analyzer = SemanticAnalyzer(tracker)
    a_analyzer.analyze(a_ast)
    
    print_scope("A (Post-Analysis)", a_ast.scope)
    
    # Verify res
    res = a_ast.scope.resolve("res")
    print(f"Symbol 'res' in A: {res}")
    if res.type_info and res.type_info.name == "int":
        print("SUCCESS: res is int")
    else:
        print(f"FAILURE: res is {res.type_info}")

if __name__ == "__main__":
    try:
        debug_compilation()
    except Exception as e:
        import traceback
        traceback.print_exc()
