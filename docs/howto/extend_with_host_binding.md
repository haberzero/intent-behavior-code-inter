# 如何扩展 IBCI（宿主绑定 bind）

> 面向需要让 IBCI 代码调用 Python 能力的开发者。解决"把任意 Python 模块/类/函数
> 暴露给 IBCI 脚本"的具体问题。
> 前置知识：`docs/syntax/11_modules.md`（模块与 import）、Python 基础。

## 唯一扩展通道

用户扩展 IBCI 的**唯一通道**是宿主绑定：在 `.ibci` 文件内用
`import python "..." as lib: bind ...` 显式声明要绑定的宿主成员。不需要、也不存在
Python 侧的契约文件——绑定声明就是契约。

## 最小示例：绑定模块函数

```ibci
import python "math" as m:
    bind sqrt(x: float) -> float
    bind pi -> float

func main() -> auto:
    float r = m.sqrt(16.0)   # 4.0
    print((str)m.pi)         # 3.141592653589793
```

- `python` 伪模块标记"宿主空间导入"，字符串为任意 Python 模块/包名。
- `bind name(params) -> type`：方法成员（IBCI 签名声明，编译期类型检查）。
- `bind name -> type`：属性/常量成员。
- **显式声明式绑定（非自动穿透）**：只有 `bind` 声明的成员可访问；契约外成员
  fail-fast（运行时 AttributeError）。声明了宿主缺失的成员 → 绑定期报错。

## 绑定宿主类为一等类型

```ibci
import python "datetime" as dt:
    bind class datetime:
        bind year -> int
        bind replace(year: int) -> datetime

func main() -> auto:
    datetime d = dt.datetime(2026, 8, 17)
    datetime y = d.replace(year=2027)
    print((str)y.year)   # 2027
```

`bind class` 绑定的类型可作类型注解、构造、`impl` 目标与协议满足判定。
`impl` 只补充宿主没有的方法，不得与 bind 成员同名；同名冲突为编译期
`SEM_REDEFINITION`。详见 `docs/syntax/11_modules.md` §11.10。

## 约定与边界

- 宿主绑定声明遵守 import 位置约束：必须出现在文件顶部。
- 绑定名（含 `bind class` 类名）不可与内核原生模块（`ai`/`file`/`ihost`/`idbg`/`isys`/`iruntime`）重名。
- 宿主对象的成员访问强制经声明门控，无隐式反射；未声明成员一律 fail-fast。
- 宿主 Python 模块按 CPython 常规 `sys.modules` 机制加载：同一进程内同名模块
  共享一份模块对象（见 `docs/KNOWN_LIMITS.md` §十九的隔离边界说明）。

## 深入指引

- 宿主绑定架构设计：`docs/architecture/01_native_host_binding.md`
- 模块语法与 import 约束：`docs/syntax/11_modules.md`
- 内置模块系统内部设计：`docs/subsystems/04_plugin_system.md`
