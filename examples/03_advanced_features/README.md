# 03 - 高级特性

本章节介绍 IBCI 的高级特性：动态宿主（隔离运行）。

> 用户插件系统（`plugins/` 目录 + `_spec.py`）已废弃。用户扩展 IBCI 的唯一通道是**宿主绑定**：在 `.ibci` 内用 `import python "..." as lib: bind ...` 声明宿主函数，见 `docs/architecture/01_native_host_binding.md` 与 `docs/syntax/11_modules.md`。

## 目录结构

```
03_advanced_features/
├── README.md              # 本文件
└── isolation_demo/       # 隔离机制演示
    ├── parent.ibci
    └── sub_project/      # 子项目（独立沙箱）
        └── child.ibci
```

## 核心概念

### 动态宿主

IBCI 支持**动态宿主**：一段 IBCI 代码可以主动开启一个新脚本的独立编译执行环境，且完全不干扰主环境。子环境的入口文件甚至不需要在主环境启动前存在——允许主环境动态生成子脚本后再切换运行。

```
parent.ibci
  └── 子项目/
      └── child.ibci
```

`child.ibci` 运行时是一个全新的独立 IBCI 实例（独立 Engine、默认不继承父环境变量）。

## 学习路径

### 隔离机制

```bash
python main.py run examples/03_advanced_features/isolation_demo/parent.ibci
```

> 隔离示例默认使用 MOCK 模式，可零配置运行。

## 下一步

- 回到 `examples/01_getting_started/01_hello_world.ibci` 复习基础语法
- 学习 `examples/02_basic_modules/` 掌握模块使用
- 完整语法参考见 `docs/SYNTAX_REFERENCE.md`
