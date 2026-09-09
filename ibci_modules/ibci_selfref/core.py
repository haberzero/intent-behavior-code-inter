"""
ibci_modules/ibci_selfref/core.py

IBCI Self-Ref 核心级自指性插件实现（Phase C 地基）。

selfref 是 IBCI 核心级插件（Core-Level Plugin）：承载**自指性体系架构**的确定性
原语——系统自省自身结构（SR-1）+ 行为模板注册/确定性组装（SR-2）+ 宪法不变量
（SR-3 地基）。**零 LLM**（SR-5 结构性保证）：组装/内省/判定全确定性（D1 铁律）；
LLM 仅在*调用方*提供低阈值语义参数（params），经 render 进入确定性组装。

与 meta/idbg 同族（core-level plugin），但**持有系统级状态**（宪法 + 模板注册表）——
每引擎一实例（create_implementation 工厂）。

C1（本轮）范围：SR-1 自描述 + SR-2 模板注册/组装 + SR-3 宪法结构。
verify（三关门）/ modify（自修改 + 回滚）归 C2/C3（需 ihost 集成）。
"""
import re
from core.extension.ibcext import IbPlugin, ExtensionCapabilities
from typing import Any, Dict, List, Optional


# 宪法不变量（SR-3 地基）：系统可被修改的边界（元规则）。结构化（非硬编码自描述
# 字符串），是 describe 递归性"我如何被修改"的落点。初版最小集（设计 Q2）；C3 扩展。
_CONSTITUTION: List[str] = [
    "self-modification must pass the verify three-gate (compile + execute + result check)",
    "modification target must be a registered template",
    "constitution itself is protected (not modifiable via selfref.modify)",
]

# 显式占位符语法（设计 Q4）：模板体中的 {name} 位。受控替换，fail-fast（未定义
# 占位/未注册模板 → 报错，非静默）。非 tricky 字符串魔法——仅替换声明的占位。
_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


class SelfRefPlugin(IbPlugin):
    """Self-Ref 自指性插件（自描述 + 模板注册/组装 + 宪法）。"""

    def __init__(self):
        super().__init__()
        self._capabilities: Optional[ExtensionCapabilities] = None
        # 行为模板注册表（SR-2）：name -> 代码模板体（含 {placeholder} 位）
        self._templates: Dict[str, str] = {}

    @property
    def plugin_id(self) -> str:
        return "ibc:selfref"

    def setup(self, capabilities: ExtensionCapabilities) -> None:
        super().setup(capabilities)
        self._capabilities = capabilities

    # ------------------------------------------------------------------
    # SR-1 自描述（真内省，非硬编码字符串）
    # ------------------------------------------------------------------

    def describe(self) -> Dict[str, Any]:
        """真内省：从系统**实际结构**组装结构化自描述值（SR-1）。

        返回 dict：
        - modules: list[str]（已注册内核原生模块——经 registry 内省，非字符串）
        - constitution: list[str]（系统不变量集——自修改边界，递归含"我如何被修改"）
        - templates: list[str]（已注册行为模板名——经模板注册表内省）

        与 e50 硬编码 self_desc 的区别：describe 每次查询实时内省实际结构（模块集/
        不变量/模板），非一次性硬编码字符串。memory 是调用方一等值（经 mem.snapshot()
        组合），selfref 不隐式持有（保持自包含）。
        """
        from core.runtime.bootstrap.builtin_modules import KERNEL_NATIVE_MODULES
        return {
            "modules": list(KERNEL_NATIVE_MODULES.keys()),
            "constitution": list(_CONSTITUTION),
            "templates": list(self._templates.keys()),
        }

    # ------------------------------------------------------------------
    # SR-3 宪法（不变量集）
    # ------------------------------------------------------------------

    def constitution(self) -> List[str]:
        """系统宪法（不变量集）：自修改的元规则（结构化，非硬编码自描述）。"""
        return list(_CONSTITUTION)

    # ------------------------------------------------------------------
    # SR-2 显式生成器（模板注册 + 确定性组装）
    # ------------------------------------------------------------------

    def register_template(self, name: str, body: str) -> None:
        """注册行为模板（SR-2）：name + 代码模板体（含 {placeholder} 参数位）。

        模板由**架构作者**编写（合法 ibci 骨架）；参数是**值**（非代码），render
        填充后仍合法 ibci——LLM 永不直接产码（e49 教训的架构解）。
        """
        if not isinstance(name, str) or not name:
            raise RuntimeError("selfref.register_template name 须为非空 str")
        if not isinstance(body, str) or not body:
            raise RuntimeError("selfref.register_template body 须为非空 str")
        self._templates[name] = body

    def templates(self) -> List[str]:
        """已注册行为模板名列表（供 describe 内省 / 复用）。"""
        return list(self._templates.keys())

    def render(self, name: str, params: Dict[str, Any]) -> str:
        """确定性组装（SR-2）：模板 + 语义参数 → 合法 ibci 源串。

        - name 须已注册（fail-fast）
        - params = {placeholder: value}；每个模板占位 {p} 须有对应参数（fail-fast）
        - 纯确定性字符串组装（零 LLM）；参数值 str 化后填充
        """
        if name not in self._templates:
            raise RuntimeError(f"selfref.render 模板 '{name}' 未注册")
        body = self._templates[name]
        params = params if isinstance(params, dict) else {}
        for ph in _PLACEHOLDER_RE.findall(body):
            if ph not in params:
                raise RuntimeError(f"selfref.render 模板 '{name}' 占位 '{ph}' 缺参数")
        # 受控替换：仅替换声明占位，值 str 化
        def _sub(m: "re.Match") -> str:
            return str(params[m.group(1)])
        return _PLACEHOLDER_RE.sub(_sub, body)


def create_implementation() -> SelfRefPlugin:
    """工厂函数：创建 SelfRefPlugin 实例（每引擎一实例，状态隔离）。"""
    return SelfRefPlugin()
