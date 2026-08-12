# _code_ai_autoset — F9 配置副作用显式化设计记录

> 2026-08-12 编制。F9（`import ai` 配置副作用）用户裁定方向：**改为显式配置**——提供
> `ai.autoset`（或等价命名）类方法，明确说明操作后果，用户在主函数/入口显式调用。
> 本文档 = 现状分析 + 方案设计 + 待用户拍板项。**只设计，未改代码。**

## 一、现状（2026-08-12 代码级）

- **触发时点**：`AIPlugin.setup()`（**引擎启动**时，STAGE 4 插件加载钩子）自动加载
  `project_root/api_config.json`（存在则）→ `apply_config` → 非 mock 时 `set_config` → 急切
  `_init_client()`。实测：**即使脚本不 `import ai`，引擎 run 也会加载并校验配置**——副作用
  绑定到引擎启动，比"import ai"更宽。
- **副作用链**（`ibci_modules/ibci_ai/core.py`）：
  - `setup`(:92-118)：自动加载 api_config.json；
  - `apply_config`(:202)：`defaults.mock:false` → `set_config(base_url, key, model)`；
  - `set_config`(:152-164)：立即 `_init_client()`；
  - `_init_client`(:120-150)：未装 openai → `RuntimeError`；凭据缺失 → `InterpreterError`。
- **失败场景**：项目根有真实 api_config.json + 未装 openai → **启动即 RuntimeError**（即使脚本
  只 mock/从不调 LLM）；配置校验失败/空凭据 → 启动即 CFG_ 诊断。
- **合法态**：无 api_config.json → 静默跳过；`defaults.mock:true` → `set_mock_mode`（不 init client）。

## 二、用户裁定（2026-08-12）

**改为显式配置**：提供 `ai.autoset` 类方法，明确说明其操作后果和为什么要操作；用户在主函数或
入口文件里手动调用。引擎启动不再自动加载。

## 三、设计（方案草案）

### 3.1 语义
`ai.autoset()` = 加载 `project_root/api_config.json` + 应用（含 `set_config`/`_init_client`）：
- `api_config.json` 不存在 → **no-op 合法态**（用户无配置）。
- 存在 → 加载 + 校验 + 应用（非 mock 时初始化客户端）。配置错误/未装 openai → 在**显式调用点**
  立即 fail-fast（带 CFG_ 诊断），失败时点从"引擎启动（用户不可见）"移到"用户可见调用点"。
- **幂等**：重复调用覆盖式应用，无累积副作用。
- 未 autoset 即调 LLM → 现有 "LLM 运行配置缺失" fail-fast（`_call_llm` :258）。

### 3.2 变更清单（实施时）
| 文件 | 变更 |
|------|------|
| `ibci_modules/ibci_ai/core.py` | `setup` 去掉自动加载段；新增 `autoset`（或定名）方法（复用 apply_config + PathValidator canonicalize + ec/project_root fail-fast） |
| `ibci_modules/ibci_ai/_spec.py` | vtable 注册 `autoset`（文档化契约） |
| `ibci_modules/ibci_ai/__init__.py` | 导出（如需要） |
| 示例（examples/ 6 篇） | 入口加 `ai.autoset()`（真实 LLM 路径） |
| 试用 harness / 用例 | `_LLM_TRIAL_*` 真实 LLM 用例入口加 `ai.autoset()` |
| 测试 | 去"自动加载"依赖；`set_mock_mode()` 前缀路径不受影响（显式 mock 不经 autoset）；新增 autoset 契约测试（加载/幂等/无配置 no-op/fail-fast/路径规范化） |
| 文档 | `docs/guide/01_setup.md`、`docs/syntax/11_modules.md` §11.3、README 本地 LLM 快速开始、KNOWN_LIMITS（若涉及）——配置加载改显式 |

### 3.3 保留既有安全契约（PT-DEBT-21 U4/U6/U7 归位）
- `PathValidator.canonicalize_for_security` 路径规范化（符号链接解析）——移入 autoset；
- `ec is None` / `project_root` 缺失 → 注入异常 fail-fast——移入 autoset；
- `api_config.json` 不存在 → 合法态静默跳过——autoset no-op。

### 3.4 命名（待用户拍板）
| 候选 | 说明 |
|------|------|
| `ai.autoset` | 用户提议名。保留则文档须清楚说明"显式加载项目配置的一等入口"（非自动探测） |
| `ai.load_project_config` | 更贴合语义（加载项目配置），与既有 `ai.load_config(path)` 对齐 |
| `ai.configure` | 通用配置入口，略含糊 |

## 四、影响评估

- **方向**：从"隐式自动加载（副作用绑定引擎启动）"改为"显式调用加载"——符合"显式优于隐式"
  + 副作用可控；fail-fast 保留且失败点更清晰。**可推翻 C1"引擎自动加载"设计**（IBCI 自身设计
  缺陷可推翻范畴，用户倾向明确）。
- **破坏性**：中等（对外行为变化：自动加载消失）。C1 落地形态同步调整（"原生一等入口"仍成立，
  只是显式）。示例/测试/文档全仓更新。
- **风险**：真实 LLM 用户忘记 autoset → 调 LLM 时报"运行配置缺失"（显式错误，可接受，优于隐式副作用）。
- **不与用户类泛型主线混做**；建议作为独立小任务，可先做设计（本文档）待命名确认后实施。

## 五、待用户拍板
1. 方法命名（3.4 候选）。
2. 是否本轮实施（或等用户类泛型主线后的独立窗口）。
