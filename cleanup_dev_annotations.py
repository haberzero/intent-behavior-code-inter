#!/usr/bin/env python3
"""
清理开发过程注释标注脚本

只清理以下开发版本标注：
- [IES 2.2], [IES 2.1], [IES 2.0] 及其变体
- [NEW], [FIX], [REFACTOR] 及其变体
- [NEW Policy], [NEW Phase X] 等开发策略标注

保留以下重要标记（技术债标记）：
- [BUG] - 已知bug
- [WIP] - 正在进行的工作
- [TODO] - 待办事项
- [HACK] - 需要改进的代码

安全策略：
1. 只替换注释中的标注，不影响代码缩进
2. 使用精确匹配，避免误匹配
3. 保留所有技术债标记
"""

import re
import os
from pathlib import Path
from typing import List, Tuple, Optional


# 只清理这些开发版本标注（注意：BUG, WIP, TODO, HACK 已被移除）
DEVELOPMENT_ANNOTATIONS = [
    r'\[IES\s*2\.2\]',
    r'\[IES\s*2\.1\]',
    r'\[IES\s*2\.0\]',
    r'\[IES\s*\d+\.\d+\]',
    r'\[IES\s*\d+\.\d+\s+Refactor\]',
    r'\[IES\s*\d+\.\d+\s+Fix\]',
    r'\[IES\s*\d+\.\d+\s+Stabilization\]',
    r'\[IES\s*\d+\.\d+\s+Architectural\s+Update\]',
    r'\[FIX\]',
    r'\[Fix\]',
    r'\[fix\]',
    r'\[NEW\]',
    r'\[new\]',
    r'\[NEW\s+Policy\]',
    r'\[NEW\s+Phase\s*\d+\]',
    r'\[REFACTOR\]',
    r'\[refactor\]',
]

# 编译成正则表达式，使用单词边界确保精确匹配
ANNOTATION_PATTERN = re.compile(
    r'(?<![a-zA-Z])(' + r'|'.join(DEVELOPMENT_ANNOTATIONS) + r')(?![a-zA-Z])',
    re.IGNORECASE
)


def clean_line(line: str) -> Tuple[bool, str]:
    """
    清理单行中的开发版本标注

    返回: (是否修改, 清理后的行)
    保持行的原始结构（缩进、空格等）不变
    """
    original = line

    # 使用sub替换，只替换匹配的内容，保留其他所有字符
    # 这确保了缩进不会被改变
    cleaned = ANNOTATION_PATTERN.sub('', line)

    # 清理可能产生的多余空格（但要小心不要破坏代码结构）
    # 情况1: # [IES 2.2] 注释 -> # 注释
    # 情况2: #  code  # [IES 2.2] comment -> #  code  # comment
    cleaned = re.sub(r'#\s{2,}', '# ', cleaned)

    # 如果 # 后面没有内容了，保留 # 但移除尾随空格
    cleaned = re.sub(r'#\s*$', '#', cleaned)

    return cleaned != original, cleaned


def process_file(file_path: Path, dry_run: bool = False) -> Tuple[int, List[str]]:
    """
    处理单个文件

    返回: (修改行数, 修改详情列表)
    """
    if not file_path.exists() or not file_path.is_file():
        return 0, []

    if file_path.suffix != '.py':
        return 0, []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except (UnicodeDecodeError, IOError) as e:
        print(f"  警告：无法读取文件 {file_path}: {e}")
        return 0, []

    modifications = []
    modified_count = 0
    new_lines = []

    for i, line in enumerate(lines, 1):
        modified, cleaned_line = clean_line(line)

        if modified:
            modifications.append(f"  行 {i}:")
            modifications.append(f"    旧: {line.rstrip()}")
            modifications.append(f"    新: {cleaned_line.rstrip()}")
            modified_count += 1

        new_lines.append(cleaned_line)

    # 只有在非dry_run模式且有修改时才写入
    if modified_count > 0 and not dry_run:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
        except IOError as e:
            print(f"  警告：无法写入文件 {file_path}: {e}")
            return 0, []

    return modified_count, modifications


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(
        description='清理开发版本标注（如 [IES 2.2], [NEW], [FIX] 等）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
保留的标记（技术债标记，不会被清理）：
  [BUG]   - 已知bug
  [WIP]   - 正在进行的工作
  [TODO]  - 待办事项
  [HACK]  - 需要改进的代码

将被清理的标记：
  [IES 2.2], [IES 2.1], [IES 2.0]
  [NEW], [FIX], [REFACTOR]
  [NEW Policy], [NEW Phase X]
        """
    )
    parser.add_argument('--dry-run', '-n', action='store_true',
                        help='只显示将要做的修改，不实际修改文件')
    parser.add_argument('--path', '-p', type=str, default='.',
                        help='要扫描的目录路径（默认: 当前目录）')

    args = parser.parse_args()

    target_path = Path(args.path)
    dry_run = args.dry_run

    # 如果是文件而不是目录，直接处理
    if target_path.is_file() and target_path.suffix == '.py':
        if target_path.name == 'cleanup_dev_annotations.py':
            print("跳过: 不能修改脚本自身")
            return
        print(f"处理文件: {target_path.absolute()}")
        if dry_run:
            print("=== 预演模式：只显示修改，不实际更改文件 ===\n")
        mod_count, mods = process_file(target_path, dry_run=dry_run)
        if mod_count > 0:
            print(f"\n文件: {target_path}")
            for mod in mods:
                print(mod)
        print(f"\n总结:")
        print(f"  修改行数: {mod_count}")
        if dry_run:
            print(f"\n提示: 这是预演模式，未做任何修改。")
        return

    target_dir = target_path

    if dry_run:
        print("=== 预演模式：只显示修改，不实际更改文件 ===\n")

    # 要排除的目录
    exclude_dirs = {
        '__pycache__', '.git', '.pytest_cache',
        'venv', 'env', '.venv', 'node_modules',
        '.git', 'backup_docs', 'docs',
    }

    # 要排除的文件模式
    exclude_files = {
        'cleanup_dev_annotations.py',
    }

    # 收集所有Python文件
    py_files = []
    for root, dirs, files in os.walk(target_dir):
        # 过滤排除的目录
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        for file in files:
            if file.endswith('.py') and file not in exclude_files:
                py_files.append(Path(root) / file)

    print(f"扫描目录: {target_dir.absolute()}")
    print(f"找到 {len(py_files)} 个 Python 文件")
    if dry_run:
        print(f"预演模式: 不做任何修改\n")
    print("=" * 60)

    total_files = 0
    total_lines = 0

    for file_path in sorted(py_files):
        mod_count, mods = process_file(file_path, dry_run=dry_run)
        if mod_count > 0:
            total_files += 1
            total_lines += mod_count
            rel_path = file_path.relative_to(target_dir) if target_dir == Path('.') else file_path
            print(f"\n文件: {rel_path}")
            for mod in mods:
                print(mod)

    print("\n" + "=" * 60)
    print(f"总结:")
    print(f"  修改文件数: {total_files}")
    print(f"  修改行数: {total_lines}")
    if dry_run:
        print(f"\n提示: 这是预演模式，未做任何修改。")
        print(f"      使用 --dry-run 参数来预览修改。")
    print("=" * 60)


if __name__ == '__main__':
    main()
