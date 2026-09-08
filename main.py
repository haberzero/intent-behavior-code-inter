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


def _read_source_line(file_path, line):
    """读单行源码（result trailer snippet 用；读取失败 = None，尽力而为）。"""
    try:
        with open(file_path, encoding="utf-8") as f:
            for i, text in enumerate(f, start=1):
                if i == line:
                    return text.rstrip("\n")
                if i > line:
                    break
    except (OSError, UnicodeDecodeError):
        pass
    return None


def _source_dict(location):
    """诊断位置 → trailer source 对象（location 为 None = None）。"""
    if location is None:
        return None
    source = {
        # file_path 为 Location 专属字段（Locatable 契约只保证 line/column；
        # 非 Location 位置面 = 无文件，显式 None 而非静默）
        "file": getattr(location, "file_path", None),
        "line": location.line,
        "column": location.column,
    }
    if source["file"] and source["line"]:
        snippet = _read_source_line(source["file"], source["line"])
        if snippet is not None:
            source["snippet"] = snippet
    return source


def _extract_compile_error(e):
    """编译错误 → trailer exception（首个诊断 = 根因面；复用诊断对象，无新渲染）。"""
    diags = e.diagnostics or []
    if not diags:
        return {"code": None, "message": str(e), "source": None}
    d = diags[0]
    return {
        "code": d.code,
        "message": d.message,
        "source": _source_dict(getattr(d, "location", None)),
    }


def _extract_runtime_error(e):
    """运行期错误 → trailer exception（复用异常对象字段，无新渲染）。"""
    return {
        "code": getattr(e, "error_code", None),
        "message": getattr(e, "message", None) or str(e),
        "source": _source_dict(getattr(e, "location", None)),
    }


def _build_result_json(*, exit_status, exception, journal, budget, replay):
    """组装 result trailer（v1 契约：单行 JSON）。"""
    return json.dumps({
        "v": 1,
        "exit_status": exit_status,
        "exception": exception,
        "journal": journal,
        "budget": budget,
        "replay": replay,
    }, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="IBC-Inter CLI")
    subparsers = parser.add_subparsers(dest="command")
    
    # Run command
    run_parser = subparsers.add_parser("run", help="Compile and run an IBCI file")
    run_parser.add_argument("file", help="Path to the .ibci entry file")
    run_parser.add_argument("--root", help="Project root directory", default=None)
    run_parser.add_argument("--auto", action="append", help="Set variable (key=value)")
    run_parser.add_argument("--no-journal", action="store_true",
                            help="Disable LLM call journal (default: on, llm_journal/<run-id>.jsonl)")
    run_parser.add_argument("--replay", metavar="JOURNAL",
                            help="Deterministic replay: serve LLM calls from a journal "
                                 "file in seq order (real provider not loaded; exhaustion "
                                 "fails fast). Implies journaling of the replay run.")
    run_parser.add_argument("--result-json", action="store_true",
                            help="Emit a machine-readable result trailer (single JSON line "
                                 "at the end of stdout: exit_status / exception / journal / "
                                 "budget / replay)")

    # Check command
    check_parser = subparsers.add_parser("check", help="Static check an IBCI project")
    check_parser.add_argument("file", help="Path to the .ibci entry file")
    check_parser.add_argument("--root", help="Project root directory", default=None)
    check_parser.add_argument("--format", choices=["pretty", "json"], default="pretty",
                              help="Output format: pretty (human-readable, default) or json (structured diagnostics export)")
    check_parser.add_argument("--output", "-o", help="Output file for json export (default: stdout)", default=None)

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
        # 输出通道行级 flush：ibci print = 行输出语义，长 run 可观测性为
        # 默认底线——非 TTY（管道/重定向）stdout 默认块缓冲，行缓冲化后
        # 每行 print 即时可见（TTY 本已行缓冲，重配置无副作用）。
        if hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(line_buffering=True)
            except (OSError, ValueError):
                pass

        # 加载命令行变量
        cli_variables = {}
        if getattr(args, 'auto', None):
            for auto_var in args.auto:
                if "=" in auto_var:
                    k, v = auto_var.split("=", 1)
                    cli_variables[k] = v

        # LLM 预算（api_config.json budget 节；无节 = 无预算，零侵入）。
        # budget 节自身形态错误 = fail-fast（用户显式写了预算且写错，不静默
        # 忽略）；文件级有效性归 ai 模块自身校验面（此处不重复验证）。
        budget_guard = None
        api_config_path = os.path.join(root_dir, "api_config.json")
        if os.path.isfile(api_config_path):
            from core.base.diagnostics.codes import CFG_CONFIG_INVALID_BUDGET
            from core.runtime.observability.budget import (
                BudgetConfigError, BudgetGuard, parse_budget_section,
            )
            try:
                with open(api_config_path, encoding="utf-8") as _f:
                    _cfg = json.load(_f)
                _spec = parse_budget_section(_cfg if isinstance(_cfg, dict) else {})
                if _spec is not None:
                    budget_guard = BudgetGuard(_spec)
            except BudgetConfigError as e:
                print(f"Error: [{CFG_CONFIG_INVALID_BUDGET}] {e}")
                sys.exit(1)
            except (OSError, ValueError):
                # 文件级损坏（JSON 非法等）= ai 模块配置加载自身的校验面，
                # 此处不重复报告（预算面只对自己的节负责）。
                pass

        # 确定性重放（--replay）：replay provider 经能力槽 SYSTEM 优先级替换
        # 真实 provider（真实 provider 不加载，无需 API key）；加载期校验
        # fail-fast（损坏/不合法 = 拒绝，不部分消费）。
        replay_journal_path = None
        replay_journal = None
        replay_arg = getattr(args, 'replay', None)
        if replay_arg:
            from core.runtime.capability_registry import CapabilityPriority, CapabilityRegistry
            from core.runtime.replay import ReplayJournal, ReplayLLMProvider, JournalFormatError
            try:
                replay_journal = ReplayJournal(replay_arg)
            except JournalFormatError as e:
                print(f"Error: {e}")
                sys.exit(1)
            engine.capability_registry.register(
                CapabilityRegistry.CAP_LLM_PROVIDER,
                ReplayLLMProvider(replay_journal),
                plugin_id="cli_replay",
                priority=CapabilityPriority.SYSTEM,
            )
            replay_journal_path = replay_arg
            print(f"replay: {replay_arg} ({replay_journal.total_calls} recorded calls)",
                  file=sys.stderr)

        # LLM journal（run 级调用审计，默认开；--no-journal 关闭）。路径在项目
        # 根下（与 --root 一致）；启动提示走 stderr（stdout 是数据面，审计提示
        # 不入数据面）。重放 run 仍写新 journal（审计链完整：replay_of 指向源）。
        journal_writer = None
        if not getattr(args, 'no_journal', False):
            from core.runtime.observability.llm_journal import LLMJournalWriter, make_run_id
            run_id = make_run_id()
            journal_rel = os.path.join("llm_journal", f"{run_id}.jsonl")
            journal_writer = LLMJournalWriter(
                os.path.join(root_dir, journal_rel),
                entry=os.path.basename(args.file),
                replay_of=replay_journal_path,
            )
            print(f"journal: {journal_rel}", file=sys.stderr)

        # 运行引擎（silent=True：CLI 为唯一渲染点，engine 层不重复打印）。
        # --result-json：stdout 末行机器可读结果 trailer（v1 契约：
        # exit_status / exception{code,message,source} / journal / budget /
        # replay）；数据面（print 输出）不受影响——验收机数据 = 末行之前，
        # 结果 = 末行解析（tail -n1）。
        result_json_flag = getattr(args, 'result_json', False)
        run_error = None
        try:
            try:
                engine.run(args.file, variables=cli_variables, silent=True,
                           journal_writer=journal_writer, budget_guard=budget_guard)
            finally:
                if journal_writer is not None:
                    journal_writer.close()
                    # 收尾面报告：写失败降级显形（审计可见性——journal 可能
                    # 不完整；run 本身不受影响，此处只把降级事实呈现给用户）
                    if journal_writer.write_failed:
                        print(
                            f"warning: journal write failures — "
                            f"{journal_writer.path} may be incomplete",
                            file=sys.stderr,
                        )
        except FileNotFoundError as e:
            print(f"Error: {e}")
            run_error = {"code": None, "message": str(e), "source": None}
        except CompilerError as e:
            # 编译错误：与其余 CLI 命令同形态（DiagnosticFormatter 渲染）
            print("\n--- Compilation Errors ---")
            print(DiagnosticFormatter.format_all(e.diagnostics, source_manager=engine.scheduler.source_manager))
            tracker = engine.scheduler.issue_tracker
            print(f"\nCompilation failed: {tracker.error_count} errors, {tracker.warning_count} warnings.")
            run_error = _extract_compile_error(e)
        except IBCBaseException as e:
            # 运行期错误：同编译错误形态（码 + 说明/修复 + --> file:line:col + 源行 + caret）
            print(_render_runtime_error(engine, e))
            run_error = _extract_runtime_error(e)

        if result_json_flag:
            print(_build_result_json(
                exit_status="error" if run_error else "ok",
                exception=run_error,
                journal=os.path.join("llm_journal", os.path.basename(journal_writer.path))
                        if journal_writer is not None else None,
                budget=budget_guard.snapshot() if budget_guard is not None else None,
                replay={"source": replay_journal_path,
                        "consumed": replay_journal.consumed_calls,
                        "total": replay_journal.total_calls}
                       if replay_journal_path else None,
            ))
        sys.exit(1 if run_error else 0)

    elif args.command == "check":
        if args.format == "json" or getattr(args, "output", None):
            # check export：静态检查诊断结构化导出（json）——复用 compile 面
            # （check 与 compile 同源 scheduler.compile_project），捕获诊断序列化。
            def _loc_dict(loc):
                if loc is None:
                    return None
                return {k: v for k, v in {
                    "file": getattr(loc, "file_path", None),
                    "line": getattr(loc, "line", None),
                    "column": getattr(loc, "column", None),
                    "end_line": getattr(loc, "end_line", None),
                    "end_column": getattr(loc, "end_column", None),
                }.items() if v is not None}

            def _diag_dict(d):
                return {
                    "severity": getattr(d.severity, "name", str(d.severity)),
                    "code": d.code,
                    "message": d.message,
                    "location": _loc_dict(d.location),
                    "hint": getattr(d, "hint", None),
                }

            try:
                engine.compile(args.file)
                result = {"success": True, "diagnostics": []}
                exit_code = 0
            except CompilerError as e:
                result = {"success": False,
                          "diagnostics": [_diag_dict(d) for d in e.diagnostics]}
                exit_code = 1
            output = json.dumps(result, indent=2, ensure_ascii=False)
            if getattr(args, "output", None):
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(output + "\n")
                print(f"Check diagnostics exported to: {args.output}")
            else:
                print(output)
            sys.exit(exit_code)
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
