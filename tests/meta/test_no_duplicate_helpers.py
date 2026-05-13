"""
tests/meta/test_no_duplicate_helpers.py
========================================

CI enforcement: Prevent duplicate helper definitions in test files.

This meta-test ensures that all test files use the unified helpers from
tests/conftest.py instead of defining local copies.

Banned patterns:
- def make_engine(...)
- def run_and_capture(...)
- def run_capture(...)
- def run_code(...)
- def ai_setup(...)
- def ai_setup_code(...)
- def _ai_prefix(...)
- def make_vm(...)
- def find_node_uid(...)
- def find_node_uids(...)
- def native(...)
- def make_intent(...)
- def compile_code(...)

CI failure indicates a test file is defining local helpers.
Fix: Import from tests.conftest or use fixtures instead.
"""

import os
import re
from pathlib import Path


def find_test_files():
    """Find all test files in tests/ directory"""
    tests_dir = Path(__file__).parent.parent
    test_files = []

    for root, dirs, files in os.walk(tests_dir):
        # Skip meta directory (this file)
        if 'meta' in Path(root).parts:
            continue

        for file in files:
            if file.startswith('test_') and file.endswith('.py'):
                test_files.append(os.path.join(root, file))

    return test_files


# Banned helper names (must not be defined locally in test files)
BANNED_HELPERS = [
    'make_engine',
    'run_and_capture',
    'run_capture',
    'run_code',
    'ai_setup',
    'ai_setup_code',
    '_ai_prefix',
    'make_vm',
    'find_node_uid',
    'find_node_uids',
    'find_all_node_uids',
    'native',
    'make_intent',
    'compile_code',
]


def test_no_duplicate_helpers():
    """Ensure no test files define local helper functions"""
    violations = []

    for test_file in find_test_files():
        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check each banned helper
        for helper_name in BANNED_HELPERS:
            # Pattern: def <helper_name>(
            pattern = rf'^\s*def\s+{re.escape(helper_name)}\s*\('
            if re.search(pattern, content, re.MULTILINE):
                relative_path = os.path.relpath(test_file, Path(__file__).parent.parent.parent)
                violations.append((relative_path, helper_name))

    if violations:
        msg = "\n\nDuplicate helper definitions found:\n"
        for file_path, helper_name in violations:
            msg += f"  - {file_path}: def {helper_name}(...)\n"

        msg += "\nFix: Import from tests.conftest instead:\n"
        msg += "  from tests.conftest import run_ibci, make_vm, ...\n"
        msg += "\nOr use fixtures:\n"
        msg += "  def test_something(engine):  # engine fixture from conftest\n"

        assert False, msg


def test_conftest_exists():
    """Ensure tests/conftest.py exists"""
    conftest_path = Path(__file__).parent.parent / 'conftest.py'
    assert conftest_path.exists(), "tests/conftest.py must exist"


def test_conftest_provides_helpers():
    """Ensure tests/conftest.py provides required helpers"""
    conftest_path = Path(__file__).parent.parent / 'conftest.py'

    with open(conftest_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Required helpers/fixtures in conftest.py
    required = [
        'run_ibci',      # helper function
        'compile_ibci',  # helper function
        'make_vm',       # helper function
        'engine',        # fixture
        'AI_MOCK_PREFIX',  # constant
    ]

    missing = []
    for name in required:
        # Check for function def or fixture or constant assignment
        patterns = [
            rf'^\s*def\s+{re.escape(name)}\s*\(',
            rf'^\s*@pytest\.fixture.*\n\s*def\s+{re.escape(name)}\s*\(',
            rf'^\s*{re.escape(name)}\s*=',
        ]
        if not any(re.search(p, content, re.MULTILINE | re.DOTALL) for p in patterns):
            missing.append(name)

    if missing:
        msg = f"\ntests/conftest.py is missing required helpers: {', '.join(missing)}\n"
        msg += "These must be defined to prevent duplicate definitions in test files.\n"
        assert False, msg
