import argparse
import os
import sys
import json
from typing import Dict, Any, Optional

# 确保项目根目录在路径中
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.engine import IBCIEngine
from core.project_detector import ProjectDetector
from core.kernel.issue import CompilerError, IBCBaseException, Diagnostic
from core.base.diagnostics.codes import RUN_GENERIC_ERROR
from core.compiler.diagnostics.formatter import DiagnosticFormatter
from core.compiler.lexer.lexer import Lexer


def _render_runtime_error(engine: IBCIEngine, exc: IBCBaseException) -> str:
    """运行期错误的结构化渲染（与编译错误同形态，DiagnosticFormatter 单一权威源）。

    优先取 tracker 中最近一条同码诊断（VM 翻译点 / handler 主动上报已附
    location[真实文件路径 + 行列] 与 context_line）；无则回落异常对象自身
    （location 可能为 None，渲染器省略位置段）。
    """
    tracker = engine.scheduler.issue_tracker
    diag = None
    for d in reversed(tracker.diagnostics):
        if d.code == exc.error_code:
            diag = d
            break
    if diag is None:
        diag = Diagnostic(
            severity=exc.severity,
            code=exc.error_code or RUN_GENERIC_ERROR,
            message=exc.message,
            location=exc.location,
        )
    return DiagnosticFormatter.format(diag, source_manager=engine.scheduler.source_manager)


def main():
    parser = argparse.ArgumentParser(description="IBC-Inter CLI")
    subparsers = parser.add_subparsers(dest="command")
    
    # Run command
    run_parser = subparsers.add_parser("run", help="Compile and run an IBCI file")
    run_parser.add_argument("file", help="Path to the .ibci entry file")
    run_parser.add_argument("--root", help="Project root directory", default=None)
    run_parser.add_argument("--auto", action="append", help="Set variable (key=value)")

    # Check command
    check_parser = subparsers.add_parser("check", help="Static check an IBCI project")
    check_parser.add_argument("file", help="Path to the .ibci entry file")
    check_parser.add_argument("--root", help="Project root directory", default=None)

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
    semantic_parser = subparsers.add_parser("semantic", help="Semantic analysis output only (symbols + type bindings)")
    semantic_parser.add_argument("file", help="Path to the .ibci entry file")
    semantic_parser.add_argument("--root", help="Project root directory", default=None)
    semantic_parser.add_argument("--format", choices=["json", "dot"], default="json", help="Output format")
    semantic_parser.add_argument("--output", "-o", help="Output file (default: stdout)", default=None)

    # Inspect command
    inspect_parser = subparsers.add_parser("inspect", help="Export symbol table and type bindings (json/dot)")
    inspect_parser.add_argument("file", help="Path to the .ibci entry file")
    inspect_parser.add_argument("--root", help="Project root directory", default=None)
    inspect_parser.add_argument("--format", choices=["json", "dot"], default="json", help="Output format")
    inspect_parser.add_argument("--output", "-o", help="Output file (default: stdout)", default=None)

    # Bench command
    bench_parser = subparsers.add_parser("bench", help="Compile-time benchmark (warmup + N runs)")
    bench_parser.add_argument("file", help="Path to the .ibci entry file")
    bench_parser.add_argument("--root", help="Project root directory", default=None)
    bench_parser.add_argument("--runs", type=int, default=10, help="Number of timed runs (default: 10)")
    bench_parser.add_argument("--warmup", type=int, default=2, help="Warmup runs before timing (default: 2)")

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

    # 初始化引擎（无插件发现/嗅探开关）
    engine = IBCIEngine(root_dir=root_dir)

    if args.command == "run":
        # 加载命令行变量
        cli_variables = {}
        if getattr(args, 'auto', None):
            for auto_var in args.auto:
                if "=" in auto_var:
                    k, v = auto_var.split("=", 1)
                    cli_variables[k] = v

        # 运行引擎（silent=True：CLI 为唯一渲染点，engine 层不重复打印）
        try:
            engine.run(args.file, variables=cli_variables, silent=True)
        except FileNotFoundError as e:
            print(f"Error: {e}")
            sys.exit(1)
        except CompilerError as e:
            # 编译错误：与其余 CLI 命令同形态（DiagnosticFormatter 渲染）
            print("\n--- Compilation Errors ---")
            print(DiagnosticFormatter.format_all(e.diagnostics, source_manager=engine.scheduler.source_manager))
            tracker = engine.scheduler.issue_tracker
            print(f"\nCompilation failed: {tracker.error_count} errors, {tracker.warning_count} warnings.")
            sys.exit(1)
        except IBCBaseException as e:
            # 运行期错误：同编译错误形态（码 + 说明/修复 + --> file:line:col + 源行 + caret）
            print(_render_runtime_error(engine, e))
            sys.exit(1)
        sys.exit(0)

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
        lexer = Lexer(content, engine.issue_tracker)
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

    elif args.command in ("inspect", "semantic"):
        # 符号表 / 类型绑定诊断导出——json / dot
        from core.compiler.diagnostics.exporter import export_artifact
        try:
            artifact = engine.compile(args.file)
        except CompilerError as e:
            print(DiagnosticFormatter.format_all(
                e.diagnostics, source_manager=engine.scheduler.source_manager
            ))
            sys.exit(1)
        entry_module = artifact.entry_module
        if entry_module not in artifact.modules:
            print(f"Error: entry module '{entry_module}' not found in artifact")
            sys.exit(1)
        mod_result = artifact.modules[entry_module]
        output = export_artifact(mod_result, entry_module, fmt=args.format)
        if getattr(args, "output", None):
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"Exported to: {args.output}")
        else:
            print(output)
        sys.exit(0)

    elif args.command == "bench":
        # 编译时间基准：warmup + N 次计时，报告 min/avg/max。
        import statistics
        import time

        def _run_once() -> float:
            t0 = time.perf_counter()
            engine.compile(args.file)
            return time.perf_counter() - t0

        # warmup（引擎初始化/缓存预热不计入）；编译失败即报错退出
        for _ in range(max(0, args.warmup)):
            try:
                _run_once()
            except CompilerError as e:
                print(DiagnosticFormatter.format_all(
                    e.diagnostics, source_manager=engine.scheduler.source_manager
                ))
                sys.exit(1)

        samples = []
        for _ in range(max(1, args.runs)):
            try:
                samples.append(_run_once())
            except CompilerError as e:
                print(DiagnosticFormatter.format_all(
                    e.diagnostics, source_manager=engine.scheduler.source_manager
                ))
                sys.exit(1)

        ms = [s * 1000 for s in samples]
        print(f"bench: {args.file}")
        print(f"  runs: {len(ms)} (warmup {args.warmup})")
        print(f"  min:  {min(ms):.2f} ms")
        print(f"  avg:  {statistics.mean(ms):.2f} ms")
        print(f"  max:  {max(ms):.2f} ms")
        if len(ms) > 1:
            print(f"  stdev:{statistics.stdev(ms):.2f} ms")
        sys.exit(0)

if __name__ == "__main__":
    main()
