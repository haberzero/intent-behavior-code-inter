
import sys
import os

# 确保能找到 core 模块
sys.path.append(os.getcwd())

from core.compiler.lexer.lexer import Lexer
from core.compiler.parser.parser import Parser
from core.compiler.diagnostics.issue_tracker import IssueTracker
from core.compiler.common.diagnostics import DiagnosticReporter

# 简单的 DiagnosticReporter 模拟实现，绕过 Protocol 实例化问题
class SimpleReporter:
    def __init__(self, tracker):
        self.tracker = tracker
        
    def report(self, severity, code, message, location=None, hint=None):
        self.tracker.report(severity, code, message, location, hint)
    
    def error(self, message, location=None, code="COMPILER_ERROR", hint=None):
        self.tracker.error(message, location, code, hint)
        print(f"[ERROR] {message} at {location}")
        
    def warning(self, message, location=None, code="COMPILER_WARNING", hint=None):
        self.tracker.warning(message, location, code, hint)
        
    def hint(self, message, location=None, code="COMPILER_HINT"):
        self.tracker.hint(message, location, code)
        
    def panic(self, message, location=None, code="FATAL_ERROR"):
        self.tracker.panic(message, location, code)
        
    def check_errors(self):
        self.tracker.check_errors()
        
    def clear(self):
        self.tracker.clear()
        
    def has_errors(self) -> bool:
        return self.tracker.has_errors()
        
    def merge(self, other):
        pass

def debug_intent_parsing():
    import textwrap
    code = textwrap.dedent("""
    intent ! "Override Intent":
        pass
    """).strip()
    
    print(f"--- Debugging Code ---\n{code}\n----------------------")
    
    issue_tracker = IssueTracker()
    reporter = SimpleReporter(issue_tracker)
    
    # 1. Lexer Debug
    lexer = Lexer(code, reporter)
    # The method is named tokenize(), not scan_tokens()
    tokens = lexer.tokenize()
    
    print("\n--- Tokens ---")
    for t in tokens:
        print(f"{t.type.name:<15} {repr(t.value)}")
        
    # 2. Parser Debug
    parser = Parser(tokens, reporter)
    # Parser.parse() 会从模块级别开始解析
    # 我们只关心 intent 语句，但为了简单，让它解析整个 module
    module = parser.parse()
    
    print("\n--- AST ---")
    if module and module.body:
        stmt = module.body[0]
        print(f"Stmt Type: {type(stmt)}")
        if hasattr(stmt, 'intent'):
            print(f"Intent Mode: {repr(stmt.intent.mode)}")
            print(f"Intent Content: {repr(stmt.intent.content)}")
    else:
        print("Parse failed or empty body")

if __name__ == "__main__":
    debug_intent_parsing()
