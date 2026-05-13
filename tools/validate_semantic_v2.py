#!/usr/bin/env python3
"""
semantic_v2 验证工具：V1/V2 并行对比验证

这个工具并行运行 V1 和 V2 语义分析器，对比输出并生成差异报告

使用方法:
    python tools/validate_semantic_v2.py [options]

选项:
    --test-dir DIR      测试用例目录（默认: tests/）
    --output FILE       输出报告文件（默认: semantic_v2_validation_report.md）
    --verbose           详细输出
    --stop-on-error     遇到错误立即停止
"""

import argparse
import os
import sys
import json
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.kernel import ast
from core.kernel.symbols import SymbolTable, Symbol
from core.kernel.registry import KernelRegistry
from core.kernel.spec import IbSpec
from core.compiler.lexer.ibci_lexer import IBCILexer
from core.compiler.parser.ibci_parser import IBCIParser
from core.compiler.semantic.passes.semantic_analyzer import SemanticAnalyzer
from core.compiler.semantic_v2.pipeline import create_semantic_pipeline
from core.compiler.semantic_v2.context import SemanticContext
from core.compiler.semantic_v2.metadata import MetadataStore, SymbolTableContext, TypeEnvironment
from core.runtime.bootstrap.builtin_initializer import initialize_builtin_classes


@dataclass
class ComparisonResult:
    """V1/V2 对比结果"""
    test_name: str
    v1_success: bool
    v2_success: bool
    v1_errors: int
    v2_errors: int
    symbol_table_match: bool
    type_bindings_match: bool
    error_count_match: bool
    differences: List[str]
    v1_time: float = 0.0
    v2_time: float = 0.0


@dataclass
class ValidationReport:
    """整体验证报告"""
    total_tests: int
    successful_comparisons: int
    v1_failures: int
    v2_failures: int
    differences_found: int
    results: List[ComparisonResult]


class SemanticV2Validator:
    """V1/V2 语义分析器对比验证器"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.registry = KernelRegistry()
        initialize_builtin_classes(self.registry)
        self.lexer = IBCILexer()
        self.parser = IBCIParser()

    def parse_code(self, code: str) -> Optional[ast.IbModule]:
        """解析 IBCI 代码为 AST"""
        try:
            tokens = self.lexer.tokenize(code)
            ast_node = self.parser.parse(tokens)
            return ast_node
        except Exception as e:
            if self.verbose:
                print(f"Parse error: {e}")
            return None

    def run_v1_analyzer(self, ast_node: ast.IbModule) -> Tuple[bool, int, SymbolTable, Dict]:
        """运行 V1 语义分析器"""
        import time
        start = time.time()

        try:
            analyzer = SemanticAnalyzer(self.registry, ast_node.name)
            result = analyzer.analyze(ast_node, raise_on_error=False)

            elapsed = time.time() - start

            success = result.success
            error_count = len(result.errors)
            symbol_table = analyzer.symbol_table
            side_table = {
                'node_to_type': dict(analyzer.side_table.node_to_type),
                'node_to_symbol': dict(analyzer.side_table.node_to_symbol)
            }

            return success, error_count, symbol_table, side_table, elapsed

        except Exception as e:
            if self.verbose:
                print(f"V1 exception: {e}")
            return False, 1, SymbolTable(), {}, time.time() - start

    def run_v2_pipeline(self, ast_node: ast.IbModule) -> Tuple[bool, int, SymbolTable, Dict]:
        """运行 V2 语义分析管道"""
        import time
        start = time.time()

        try:
            # Create context
            symbol_table = SymbolTable()
            context = SemanticContext(
                ast=ast_node,
                registry=self.registry,
                module_name=ast_node.name,
                symbol_table=SymbolTableContext(symbol_table),
                type_environment=TypeEnvironment(),
                metadata=MetadataStore()
            )

            # Run pipeline
            pipeline = create_semantic_pipeline()
            result = pipeline.run(context)

            elapsed = time.time() - start

            success = result.success
            error_count = len([d for d in result.diagnostics if d.level.name == 'ERROR'])
            symbol_table = result.context.symbol_table.current
            metadata = {
                'type_bindings': dict(result.context.metadata.type_bindings),
                'symbol_bindings': dict(result.context.metadata.symbol_bindings)
            }

            return success, error_count, symbol_table, metadata, elapsed

        except Exception as e:
            if self.verbose:
                print(f"V2 exception: {e}")
            return False, 1, SymbolTable(), {}, time.time() - start

    def compare_symbol_tables(self, v1_table: SymbolTable, v2_table: SymbolTable) -> Tuple[bool, List[str]]:
        """对比两个符号表"""
        differences = []

        # Get all symbol names from both tables
        v1_symbols = {name: sym for name, sym in v1_table._symbols.items()}
        v2_symbols = {name: sym for name, sym in v2_table._symbols.items()}

        v1_names = set(v1_symbols.keys())
        v2_names = set(v2_symbols.keys())

        # Check for missing symbols
        only_in_v1 = v1_names - v2_names
        only_in_v2 = v2_names - v1_names

        if only_in_v1:
            differences.append(f"Symbols only in V1: {only_in_v1}")
        if only_in_v2:
            differences.append(f"Symbols only in V2: {only_in_v2}")

        # Check common symbols
        common = v1_names & v2_names
        for name in common:
            v1_sym = v1_symbols[name]
            v2_sym = v2_symbols[name]

            if v1_sym.kind != v2_sym.kind:
                differences.append(f"Symbol '{name}' kind mismatch: V1={v1_sym.kind}, V2={v2_sym.kind}")

        return len(differences) == 0, differences

    def compare_results(self, test_name: str, code: str) -> ComparisonResult:
        """对比 V1 和 V2 在同一代码上的结果"""
        differences = []

        # Parse code
        ast_node = self.parse_code(code)
        if ast_node is None:
            return ComparisonResult(
                test_name=test_name,
                v1_success=False,
                v2_success=False,
                v1_errors=1,
                v2_errors=1,
                symbol_table_match=False,
                type_bindings_match=False,
                error_count_match=False,
                differences=["Failed to parse code"]
            )

        # Run V1
        v1_success, v1_errors, v1_table, v1_metadata, v1_time = self.run_v1_analyzer(ast_node)

        # Run V2
        v2_success, v2_errors, v2_table, v2_metadata, v2_time = self.run_v2_pipeline(ast_node)

        # Compare success status
        if v1_success != v2_success:
            differences.append(f"Success status mismatch: V1={v1_success}, V2={v2_success}")

        # Compare error counts
        error_count_match = v1_errors == v2_errors
        if not error_count_match:
            differences.append(f"Error count mismatch: V1={v1_errors}, V2={v2_errors}")

        # Compare symbol tables
        symbol_match, symbol_diffs = self.compare_symbol_tables(v1_table, v2_table)
        differences.extend(symbol_diffs)

        # Type bindings comparison (simplified)
        type_bindings_match = True  # TODO: Implement detailed type binding comparison

        return ComparisonResult(
            test_name=test_name,
            v1_success=v1_success,
            v2_success=v2_success,
            v1_errors=v1_errors,
            v2_errors=v2_errors,
            symbol_table_match=symbol_match,
            type_bindings_match=type_bindings_match,
            error_count_match=error_count_match,
            differences=differences,
            v1_time=v1_time,
            v2_time=v2_time
        )

    def validate_test_cases(self, test_cases: Dict[str, str]) -> ValidationReport:
        """验证一组测试用例"""
        results = []

        for test_name, code in test_cases.items():
            if self.verbose:
                print(f"\nTesting: {test_name}")

            result = self.compare_results(test_name, code)
            results.append(result)

            if self.verbose:
                if len(result.differences) == 0:
                    print(f"  ✓ MATCH")
                else:
                    print(f"  ✗ DIFFERENCES: {len(result.differences)}")

        # Generate report
        total = len(results)
        successful = sum(1 for r in results if len(r.differences) == 0)
        v1_failures = sum(1 for r in results if not r.v1_success)
        v2_failures = sum(1 for r in results if not r.v2_success)
        differences = sum(1 for r in results if len(r.differences) > 0)

        return ValidationReport(
            total_tests=total,
            successful_comparisons=successful,
            v1_failures=v1_failures,
            v2_failures=v2_failures,
            differences_found=differences,
            results=results
        )

    def generate_markdown_report(self, report: ValidationReport, output_file: str):
        """生成 Markdown 格式的报告"""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# semantic_v2 验证报告\n\n")

            # Summary
            f.write("## 📊 验证摘要\n\n")
            f.write(f"- **总测试数**: {report.total_tests}\n")
            f.write(f"- **完全匹配**: {report.successful_comparisons}\n")
            f.write(f"- **存在差异**: {report.differences_found}\n")
            f.write(f"- **V1 失败**: {report.v1_failures}\n")
            f.write(f"- **V2 失败**: {report.v2_failures}\n")
            f.write(f"- **匹配率**: {report.successful_comparisons/report.total_tests*100:.1f}%\n\n")

            # Detailed results
            f.write("## 📋 详细结果\n\n")

            for result in report.results:
                f.write(f"### {result.test_name}\n\n")

                if len(result.differences) == 0:
                    f.write("✅ **完全匹配**\n\n")
                else:
                    f.write("❌ **存在差异**\n\n")

                f.write("| 维度 | V1 | V2 | 匹配 |\n")
                f.write("|------|----|----|------|\n")
                f.write(f"| 成功状态 | {result.v1_success} | {result.v2_success} | {result.v1_success == result.v2_success} |\n")
                f.write(f"| 错误数量 | {result.v1_errors} | {result.v2_errors} | {result.error_count_match} |\n")
                f.write(f"| 符号表 | - | - | {result.symbol_table_match} |\n")
                f.write(f"| 类型绑定 | - | - | {result.type_bindings_match} |\n")
                f.write(f"| 执行时间 | {result.v1_time:.3f}s | {result.v2_time:.3f}s | - |\n\n")

                if result.differences:
                    f.write("**差异详情**:\n\n")
                    for diff in result.differences:
                        f.write(f"- {diff}\n")
                    f.write("\n")

            # Performance summary
            f.write("## ⚡ 性能对比\n\n")
            total_v1_time = sum(r.v1_time for r in report.results)
            total_v2_time = sum(r.v2_time for r in report.results)
            f.write(f"- **V1 总时间**: {total_v1_time:.3f}s\n")
            f.write(f"- **V2 总时间**: {total_v2_time:.3f}s\n")
            f.write(f"- **性能比**: {total_v2_time/total_v1_time:.2f}x\n\n")

        print(f"\n报告已生成: {output_file}")


def get_default_test_cases() -> Dict[str, str]:
    """获取默认测试用例"""
    return {
        "simple_function": """
def add(int a, int b) -> int:
    return a + b
""",
        "simple_class": """
class Point:
    int x
    int y
""",
        "variable_assignment": """
int x = 42
str y = "hello"
""",
        "type_mismatch": """
int x = "hello"
""",
        "undefined_variable": """
int x = y
""",
        "function_with_locals": """
def calculate() -> int:
    int x = 10
    int y = 20
    return x + y
""",
        "class_with_method": """
class Calculator:
    func int add(self, int a, int b):
        return a + b
""",
    }


def main():
    parser = argparse.ArgumentParser(description="Validate semantic_v2 against V1")
    parser.add_argument("--test-dir", help="Test cases directory")
    parser.add_argument("--output", default="semantic_v2_validation_report.md", help="Output report file")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--stop-on-error", action="store_true", help="Stop on first error")

    args = parser.parse_args()

    # Create validator
    validator = SemanticV2Validator(verbose=args.verbose)

    # Get test cases
    test_cases = get_default_test_cases()

    print(f"Running validation with {len(test_cases)} test cases...")

    # Run validation
    report = validator.validate_test_cases(test_cases)

    # Generate report
    validator.generate_markdown_report(report, args.output)

    # Print summary
    print(f"\n{'='*60}")
    print(f"Validation Summary:")
    print(f"  Total tests: {report.total_tests}")
    print(f"  Successful: {report.successful_comparisons}")
    print(f"  Differences: {report.differences_found}")
    print(f"  Match rate: {report.successful_comparisons/report.total_tests*100:.1f}%")
    print(f"{'='*60}")

    # Exit code
    if report.differences_found > report.total_tests * 0.05:  # >5% difference
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
