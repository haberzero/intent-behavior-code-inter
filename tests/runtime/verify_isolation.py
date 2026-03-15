import sys
import os
import json

# Add current directory to path
sys.path.append(os.getcwd())

# 模拟预编译的产物
dummy_artifact = {
    "version": "2.0",
    "entry_module": "main",
    "pools": {
        "nodes": {
            "node_1": {"_type": "IbModule", "body": ["node_2"]},
            "node_2": {"_type": "IbConstant", "value": 42}
        },
        "symbols": {},
        "scopes": {},
        "types": {
            "type_int": {"name": "int", "kind": "TypeDescriptor"}
        },
        "assets": {}
    },
    "modules": {
        "main": {
            "root_node_uid": "node_1",
            "side_tables": {
                "node_to_type": {"node_2": "type_int"}
            }
        }
    }
}

def verify_isolation(silent=False):
    if not silent: print("Checking physical isolation of Interpreter...")
    
    # 1. 确保核心编译器模块未加载
    forbidden = ["core.compiler.lexer", "core.compiler.parser", "core.compiler.semantic"]
    for m in forbidden:
        if m in sys.modules:
            print(f"PRE-CHECK FAILED: {m} is already in sys.modules!")
            return False

    # 2. 仅导入运行时必要的模块
    from core.runtime.interpreter.interpreter import Interpreter
    from core.runtime.loader.artifact_loader import ArtifactLoader
    from core.foundation.registry import Registry
    from core.runtime.bootstrap.builtin_initializer import initialize_builtin_classes
    
    # 使用简单的运行时诊断器代替 Compiler 下的实现
    class SimpleIssueTracker:
        def report(self, severity, code, message, location=None, hint=None):
            if not silent: print(f"[{severity}] {code}: {message}")
        def has_errors(self): return False
    
    # 3. 运行解释器
    registry = Registry()
    initialize_builtin_classes(registry)
    
    issue_tracker = SimpleIssueTracker()
    
    # [Plan A] 解释器会内部创建 Loader 并加载 artifact
    if not silent: print("Running interpreter with dummy artifact...")
    interpreter = Interpreter(issue_tracker, registry=registry, artifact=dummy_artifact)
    
    result = interpreter.interpret("node_1")
    if not silent: print(f"Result: {result.to_native()}")
    
    # 4. 再次核查
    failed = False
    for m in forbidden:
        if m in sys.modules:
            print(f"FAILED: {m} was imported during runtime!")
            failed = True
            
    if failed:
        print("\nInvestigating why core.compiler was imported...")
        # Check core.domain.ast since it's used by interpreter
        import core.domain.ast as ast
        print(f"core.domain.ast file: {ast.__file__}")
        
        # Check core.runtime.interpreter.interpreter
        import core.runtime.interpreter.interpreter as itp
        print(f"core.runtime.interpreter.interpreter file: {itp.__file__}")
        return False
            
    if not silent: print("SUCCESS: Interpreter is physically isolated from Compiler.")
    return True

if __name__ == "__main__":
    silent = "--silent" in sys.argv
    if verify_isolation(silent=silent):
        sys.exit(0)
    else:
        sys.exit(1)
