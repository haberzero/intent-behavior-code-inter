# F1 — 宿主导入一等语法 + 用户类持有 native（设计文档）

> 临时任务控制文档（governance：完成后删除，决策沉入 docs/architecture/01_native_host_binding.md）。
> 主线：ROADMAP_NATIVE_BINDING.md §三【远期愿景】F1。

## 〇、F1 目标与验证门

- **F1 目标**：宿主导入一等语法（`import python "pkg" as lib`）+ 用户 IBCI 类/`any`
  字段持 `IbNativeObject`，显式绑定到 IBCI 声明方法（非自动穿透）。
- **验证门**：e2e（`.ibci` 绑定宿主 callable 并调用成功）；全量 pytest 零回归。

## 状态（2026-08-17 实现完成）

- **已实现**：语法 + 全链路（AST/lexer/parser/依赖扫描/scheduler/语义/运行时/VM）。
  共享函数提取（_annotation_utils.annotation_to_typeref、proxy.create_proxy）消除双真相。
- **已验证**：e2e（sqrt=4.0/pi/pow=1024.0/用户类持 native=5.0/磁盘文件 rehydrate）；
  负样本（未声明成员 fail-fast、绑定缺失成员报错、编译期类型检查 SEM_TYPE_MISMATCH）；
  全量 pytest 3037 passed / 1 skipped（新增 tests/runtime/test_host_binding.py 6 项）。
- **文档**：docs/architecture/01_native_host_binding.md §五 + docs/syntax/11_modules.md §11.10。
- **待办**：独立复核放行 → 合入 unsafe-vibe-dev（零风险：纯新增语法/机制，不触碰既有
  import 语义；全量 pytest 绿；测试+文档齐全）。
- **后续**：F2（协议/impl 扩展到宿主类型）基于 F1 稳定后新分支推进。

## 一、语法设计（裁决点 1 落地，定稿：bind 块方案）

### 1.1 宿主绑定 import

```ibci
import python "math" as m:
    bind sqrt(x: float) -> float
    bind pow(x: float, y: float) -> float
    bind pi -> float
```

- `python` = 伪模块关键字（标记宿主空间导入；非保留字，无 token 冲突）
- `"math"` = 字符串模块名（任意 Python 模块/包）
- `as m` = 绑定名（模块级变量，IbNativeObject）
- `:` + `bind` 块 = 显式绑定声明（IBCI 方法签名 → 运行时 proxy vtable）
  - `bind name(params) -> ret`：函数/方法成员（签名声明，编译期类型检查可用）
  - `bind name -> type`：属性/常量成员（白名单）

**为何 bind 块而非 from-import 简化**：
- 满足"显式绑定到 IBCI 声明方法"——bind 声明方法签名，编译期可做成员类型检查
  （调用 `m.sqrt(16.0)` 校验实参类型）。
- from-import 简化（`from python "math" import sqrt`）丢失签名信息，成员类型退化为
  any/动态——不符合"绑定到声明方法"的类型安全意图。
- bind 块与 `protocol`/`impl` 方法签名形态一致（统一设计语言）。

### 1.2 设计理由（对照 design-philosophy）

- 统一设计语言：`import` 承载"引入外部内容"；`bind` 承载"声明绑定"（与 `protocol`/
  `impl` 的方法签名形态一致）。
- 显式声明式（非自动穿透）：成员访问强制经声明绑定集（vtable/白名单门控，
  fail-fast）。
- 机制同构：绑定块签名 → 编译期构建宿主模块 spec（MethodMemberSpec/MemberSpec）
  → 运行时复用 loader proxy（unbox→调→box + param_meta）→ vtable。

## 二、实现落点（已实证）

| 环节 | 文件 | 改动 |
|---|---|---|
| Parser | `core/compiler/parser/components/import_def.py` | `parse_import` 识别 `python` 伪模块 + 字符串模块名 + bind 块 |
| Parser | `core/compiler/parser/parser.py:188` | import 语句入口分发（bind 块解析） |
| AST | `core/kernel/ast.py` | 扩展 `IbImport`（或新节点）承载宿主绑定：python 伪模块 + 绑定声明列表 |
| 编译期 | `core/compiler/scheduler.py` | 宿主 import 符号注入（MODULE 符号 + 绑定成员符号） |
| 运行时 | `core/runtime/interpreter/module_manager.py` | `import_module` 的 `python` 分支：裸 Python import → 构建 vtable |
| 运行时 | `core/runtime/vm/handlers/declarations.py` | `vm_handle_IbImport` 支持宿主绑定执行 |
| 绑定机制 | `core/runtime/module_system/loader.py` proxy | 复用为宿主绑定 vtable 构造 |

## 三、设计细节

### 3.1 AST 承载

宿主绑定信息是"程序源码结构"（AST 固有属性）：`python` 伪模块 + 模块名 + 绑定声明
（方法签名 / 属性）。类型级属性（宿主类型身份、成员 spec）归 IbSpec
（provenance=EXTERNAL_MODULE）。对齐 02_metadata_ast 边界。

### 3.2 运行时绑定

`import_module` 的 `python` 分支：
1. `importlib.import_module("pkg")` 取裸 Python 模块
2. 按绑定声明构建 vtable：`bind name(params)->ret` → proxy（unbox→调→box）+
   param_meta（复用 loader create_proxy 逻辑）；`bind name->type` → 白名单
3. `create_native_object(pkg, Object, vtable, whitelist)` → IbNativeObject
4. `create_module(name, native_obj)` 或直接作为模块级变量

### 3.3 用户类持有

`any` 字段/局部变量持 IbNativeObject（KNOWN_LIMITS 已支持）；用户 IBCI 类方法内
`lib.member(...)` 经 IbNativeObject.receive → vtable 调用。

## 四、安全模型

- 成员访问强制经 vtable/白名单门控（IbNativeObject.receive 现有强制）；契约外成员
  fail-fast（AttributeError）。
- Registry 隔离保留（registry_id 校验）。
- bind 块声明的签名与实现校验：绑定方法须存在于 Python 对象（绑定期校验，对齐
  loader._validate_and_bind）。

## 五、e2e 验证计划

```ibci
import python "math" as m:
    bind sqrt(x: float) -> float

func main():
    float r = m.sqrt(16.0)
    print((str)r)   # 4.0
```

- e2e 断言输出 `4.0`。
- 负样本：未声明的成员访问报错（fail-fast）。
- 全量 pytest 零回归。

## 六、待定/风险

- parser 对 `:` + bind 块的语法支持（import 语句后的块）。
- scheduler 符号注入（MODULE 符号 + 绑定成员符号）与现有 import 机制的一致性。
- 绑定块签名 → spec 的映射（方法签名 → MethodMemberSpec）。
