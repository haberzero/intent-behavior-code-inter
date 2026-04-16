import argparse
import os
import sys
import json
import importlib.util
from typing import Dict, Any, Optional

# 确保项目根目录在路径中
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.engine import IBCIEngine
from core.project_detector import ProjectDetector
from core.kernel.issue import CompilerError
from core.compiler.diagnostics.formatter import DiagnosticFormatter
from core.compiler.lexer.lexer import Lexer
from core.runtime.objects.kernel import CoreModule, DebugLevel

def load_external_plugins(engine: IBCIEngine, plugin_paths: list):
    """从本地 Python 文件动态加载插件"""
    for path in plugin_paths:
        if not os.path.exists(path):
            print(f"Warning: Plugin path not found: {path}")
            continue
            
        try:
            # 自动提取模块名（文件名）
            module_name = os.path.splitext(os.path.basename(path))[0]
            
            # 动态加载 Python 模块
            spec = importlib.util.spec_from_file_location(module_name, path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            
            # 注册到引擎
            engine.register_native_module(module_name, mod)
            print(f"Loaded plugin: {module_name} from {path}")
        except Exception as e:
            print(f"Failed to load plugin {path}: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description="IBC-Inter CLI")
    parser.add_argument('--max-inst', type=int, default=100000000, help='Max instructions (default: 100000000)')
    subparsers = parser.add_subparsers(dest="command")
    
    # Run command
    run_parser = subparsers.add_parser("run", help="Compile and run an IBCI file")
    run_parser.add_argument("file", help="Path to the .ibci entry file")
    run_parser.add_argument("--root", help="Project root directory", default=None)
    run_parser.add_argument("--auto", action="append", help="Set variable (key=value)")
    run_parser.add_argument("--plugin", action="append", help="Path to external Python plugin (.py)")
    run_parser.add_argument("--no-sniff", action="store_true", help="Disable auto-sniffing plugins/ folder")
    run_parser.add_argument("--core-debug", help="Core debugger config (JSON string or file path)", default=None)
    run_parser.add_argument('--max-inst', type=int, default=100000000, help='Max instructions (default: 100000000)')

    # Check command
    check_parser = subparsers.add_parser("check", help="Static check an IBCI project")
    check_parser.add_argument("file", help="Path to the .ibci entry file")
    check_parser.add_argument("--root", help="Project root directory", default=None)
    check_parser.add_argument("--plugin", action="append", help="Path to external Python plugin (.py)")
    check_parser.add_argument("--no-sniff", action="store_true", help="Disable auto-sniffing plugins/ folder")

    # Compile command
    compile_parser = subparsers.add_parser("compile", help="Compile only (no interpret)")
    compile_parser.add_argument("file", help="Path to the .ibci entry file")
    compile_parser.add_argument("--root", help="Project root directory", default=None)
    compile_parser.add_argument("--output", "-o", help="Output file for compiled artifact", default=None)
    compile_parser.add_argument("--format", choices=["json", "pretty"], default="json", help="Output format")

    # Lex command
    lex_parser = subparsers.add_parser("lex", help="Lexer output only (tokens)")
    lex_parser.add_argument("file", help="Path to the .ibci entry file")
    lex_parser.add_argument("--root", help="Project root directory", default=None)

    # Parse command
    parse_parser = subparsers.add_parser("parse", help="Parser output only (AST)")
    parse_parser.add_argument("file", help="Path to the .ibci entry file")
    parse_parser.add_argument("--root", help="Project root directory", default=None)
    parse_parser.add_argument("--format", choices=["json", "pretty"], default="json", help="Output format")

    # Semantic command
    semantic_parser = subparsers.add_parser("semantic", help="Semantic analysis output only")
    semantic_parser.add_argument("file", help="Path to the .ibci entry file")
    semantic_parser.add_argument("--root", help="Project root directory", default=None)
    semantic_parser.add_argument("--format", choices=["json", "pretty"], default="json", help="Output format")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # 确定项目根目录 (root_dir)
    # 逻辑：
    # 1. 如果显式指定了 --root，则使用它
    # 2. 否则，自动检测项目根目录（向上查找 plugins/ 或 ibci_modules/）
    # 3. 如果未检测到，则使用入口文件所在目录
    root_dir = args.root
    if not root_dir and hasattr(args, 'file'):
        detected_root = ProjectDetector.detect_project_root(args.file)
        if detected_root:
            root_dir = detected_root
            if hasattr(args, 'verbose') and args.verbose:
                print(f"[Auto-detect] {ProjectDetector.describe_detection(args.file)}")
        else:
            root_dir = os.path.dirname(os.path.abspath(args.file))
            if hasattr(args, 'verbose') and args.verbose:
                print(f"[Auto-detect] No project root detected, using entry directory: {root_dir}")

    # 初始化引擎，决定是否自动嗅探
    auto_sniff = not getattr(args, 'no_sniff', False)
    
    # 处理内核调试配置
    core_debug_config = None
    if hasattr(args, 'core_debug') and args.core_debug:
        if os.path.exists(args.core_debug):
            try:
                with open(args.core_debug, 'r', encoding='utf-8') as f:
                    core_debug_config = json.load(f)
            except Exception as e:
                print(f"Warning: Failed to load core debug config file: {e}")
        else:
            try:
                core_debug_config = json.loads(args.core_debug)
            except Exception as e:
                print(f"Warning: Failed to parse core debug JSON string: {e}")

    engine = IBCIEngine(root_dir=root_dir, auto_sniff=auto_sniff, core_debug_config=core_debug_config)

    # 1. 加载插件
    if getattr(args, 'plugin', None):
        load_external_plugins(engine, args.plugin)

    if args.command == "run":
        # 加载命令行变量
        cli_variables = {}
        if getattr(args, 'auto', None):
            for auto_var in args.auto:
                if "=" in auto_var:
                    k, v = auto_var.split("=", 1)
                    cli_variables[k] = v

        # 运行引擎
        success = engine.run(args.file, variables=cli_variables)
        sys.exit(0 if success else 1)

    elif args.command == "check":
        success = engine.check(args.file)
        sys.exit(0 if success else 1)

    elif args.command == "compile":
        success = engine.compile(args.file)
        if success:
            from core.compiler.serialization.serializer import FlatSerializer
            serializer = FlatSerializer()
            artifact_dict = serializer.serialize_artifact(success)
            output = json.dumps(artifact_dict, indent=2, ensure_ascii=False)
            if getattr(args, 'output', None):
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(output)
                print(f"Compiled artifact saved to: {args.output}")
            else:
                print(output)
            sys.exit(0)
        sys.exit(1)

    elif args.command == "lex":
        from core.compiler.lexer.lexer import Lexer
        with open(args.file, 'r', encoding='utf-8') as f:
            content = f.read()
        lexer = Lexer(content, engine.issue_tracker, debugger=engine.debugger)
        tokens = lexer.tokenize()
        for tok in tokens:
            print(tok)
        sys.exit(0)

    elif args.command == "parse":
        artifact = engine.compile(args.file)
        if artifact:
            # 获取入口模块名（对应用户提供的文件）
            entry_module = artifact.entry_module
            if entry_module in artifact.modules:
                mod_result = artifact.modules[entry_module]
                ast_node = mod_result.module_ast
                ast_dict = {
                    "type": type(ast_node).__name__,
                    "repr": repr(ast_node)
                }
                if hasattr(ast_node, '__dict__'):
                    ast_dict["fields"] = {k: repr(v) for k, v in ast_node.__dict__.items() if not k.startswith('_')}
                output = json.dumps(ast_dict, indent=2, ensure_ascii=False)
                print(output)
            sys.exit(0)
        sys.exit(1)

    elif args.command == "inspect":
        artifact = engine.compile(args.file)
        if artifact:
            entry_module = artifact.entry_module
            if entry_module in artifact.modules:
                mod_result = artifact.modules[entry_module]
                sym_table = mod_result.symbol_table
                result = {
                    "module": module_name,
                    "symbols": {}
                }
                if sym_table:
                    for name, sym in sym_table.symbols.items():
                        result["symbols"][name] = {
                            "kind": str(sym.kind),
                            "type": str(sym.spec) if sym.spec else "None"
                        }
                output = json.dumps(result, indent=2, ensure_ascii=False)
                print(output)
            sys.exit(0)
        sys.exit(1)

if __name__ == "__main__":
    main()
