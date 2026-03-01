import argparse
import os
import sys
import json
import importlib.util
from typing import Dict, Any

# 确保项目根目录在路径中
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.engine import IBCIEngine

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
    run_parser.add_argument("--no-sniff", action="store_true", help="Disable auto-sniffing plugins/ folder")
    run_parser.add_argument("--core-debug", help="Enable core debugging. Pass a JSON string (e.g. '{\\"INTERPRETER\\": \\"DATA\\"}') or a file path.")

    # Check command
    check_parser = subparsers.add_parser("check", help="Static check an IBCI project")
    check_parser.add_argument("file", help="Path to the .ibci entry file")
    check_parser.add_argument("--root", help="Project root directory", default=None)
    check_parser.add_argument("--plugin", action="append", help="Path to external Python plugin (.py)")
    check_parser.add_argument("--no-sniff", action="store_true", help="Disable auto-sniffing plugins/ folder")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # 确定项目根目录 (root_dir)
    # 逻辑：如果显式指定了 --root，则使用它；
    # 否则，默认将目标 .ibci 文件所在的目录作为根目录。
    root_dir = args.root
    if not root_dir and hasattr(args, 'file'):
        root_dir = os.path.dirname(os.path.abspath(args.file))

    # 初始化引擎，决定是否自动嗅探
    auto_sniff = not args.no_sniff
    
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
