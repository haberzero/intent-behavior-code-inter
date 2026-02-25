import argparse
import os
import sys
import json
import importlib.util
from typing import Dict, Any

# 确保项目根目录在路径中
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.engine import IBCIEngine

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
            engine.register_plugin(module_name, mod)
            print(f"Loaded plugin: {module_name} from {path}")
        except Exception as e:
            print(f"Failed to load plugin {path}: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description="IBC-Inter (Intent-Behavior-Code Interaction) Interpreter")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run an IBCI file")
    run_parser.add_argument("file", help="Path to the .ibci entry file")
    run_parser.add_argument("--config", help="Path to API config JSON file", default="test_target_proj/api_config.json")
    run_parser.add_argument("--root", help="Project root directory (default: current dir)", default=None)
    run_parser.add_argument("--plugin", action="append", help="Path to external Python plugin (.py)")
    run_parser.add_argument("--var", action="append", help="Inject variables in key=value format")

    # Check command
    check_parser = subparsers.add_parser("check", help="Static check an IBCI project")
    check_parser.add_argument("file", help="Path to the .ibci entry file")
    check_parser.add_argument("--root", help="Project root directory", default=None)
    check_parser.add_argument("--plugin", action="append", help="Path to external Python plugin (.py)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    engine = IBCIEngine(root_dir=args.root)

    # 1. 加载插件
    if args.plugin:
        load_external_plugins(engine, args.plugin)

    if args.command == "run":
        # 2. 处理变量
        variables = {}
        
        # 从配置文件加载
        if args.config and os.path.exists(args.config):
            try:
                with open(args.config, 'r', encoding='utf-8') as f:
                    cfg_data = json.load(f)
                    # 兼容 test_target_proj 的格式
                    if "default_model" in cfg_data:
                        m = cfg_data["default_model"]
                        variables.update({
                            "url": m.get("base_url"),
                            "key": m.get("api_key"),
                            "model": m.get("model")
                        })
                    else:
                        variables.update(cfg_data)
            except Exception as e:
                print(f"Warning: Failed to load config: {e}")
        
        # 从命令行参数加载 (--var key=value)
        if args.var:
            for v in args.var:
                if "=" in v:
                    k, val = v.split("=", 1)
                    variables[k] = val

        # 3. 执行
        success = engine.run(args.file, variables=variables)
        sys.exit(0 if success else 1)

    elif args.command == "check":
        success = engine.check(args.file)
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
