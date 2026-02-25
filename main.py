import argparse
import os
import sys
import json

# 确保项目根目录在路径中
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.engine import IBCIEngine

def main():
    parser = argparse.ArgumentParser(description="IBC-Inter 语言执行器")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # Run 命令
    run_parser = subparsers.add_parser("run", help="运行 IBCI 项目")
    run_parser.add_argument("file", help="入口 .ibci 文件路径")
    run_parser.add_argument("--config", help="API 配置文件路径 (json)", default="test_target_proj/api_config.json")
    run_parser.add_argument("--root", help="工程根目录 (默认为当前目录)", default=None)

    # Check 命令
    check_parser = subparsers.add_parser("check", help="静态检查 IBCI 项目")
    check_parser.add_argument("file", help="入口 .ibci 文件路径")
    check_parser.add_argument("--root", help="工程根目录", default=None)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    engine = IBCIEngine(root_dir=args.root)

    if args.command == "run":
        variables = {}
        if args.config and os.path.exists(args.config):
            try:
                with open(args.config, 'r', encoding='utf-8') as f:
                    api_config = json.load(f)
                    default_model = api_config.get('default_model', {})
                    variables = {
                        "url": default_model.get('base_url'),
                        "key": default_model.get('api_key'),
                        "model": default_model.get('model')
                    }
            except Exception as e:
                print(f"Warning: Failed to load config: {e}")

        success = engine.run(args.file, variables=variables)
        sys.exit(0 if success else 1)

    elif args.command == "check":
        success = engine.check(args.file)
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
