# -*- coding: utf-8 -*-
"""
tests/runtime/test_selfref_module.py
=====================================

selfref 模块（自指性体系架构 Phase C 地基）判别测试。

SR-1 自描述（真内省，非硬编码字符串）/ SR-2 显式生成器（模板注册 + 确定性组装）/
SR-3 宪法（不变量集）。验证：
- describe 从系统实际结构组装（modules = 真实内核模块集 / constitution / templates）
- 模板注册 + render 确定性组装（受控替换 + fail-fast）
- 完整管线：register → render → meta.compile（架构产出合法 ibci，e49 教训的架构解）
"""
import pytest

from core.engine import IBCIEngine
from core.runtime.bootstrap.builtin_modules import KERNEL_NATIVE_MODULES
from ibci_modules.ibci_selfref.core import SelfRefPlugin, _CONSTITUTION
from tests.conftest import REPO_ROOT


def _run(ibci_code: str) -> str:
    """经 IBCI 引擎运行代码，收集 stdout。"""
    import os
    path = os.path.join(".tmp_verify", f"selfref_{id(ibci_code) % 100000}.ibci")
    os.makedirs(".tmp_verify", exist_ok=True)
    with open(path, "w") as f:
        f.write(ibci_code)
    out = []
    engine = IBCIEngine(root_dir=REPO_ROOT)
    engine.run(path, silent=False, output_callback=lambda t: out.append(t))
    os.unlink(path)
    return "\n".join(out)


class TestSelfRefPlugin:
    """插件层（Python 直调）——SR-1/SR-2/SR-3 语义。"""

    def test_describe_assembles_real_structure(self):
        """SR-1：describe 从实际结构组装（modules = 真实内核模块集，非硬编码字符串）。"""
        p = SelfRefPlugin()
        d = p.describe()
        # modules 是真实内核原生模块集（含 selfref 自身——自指性：系统描述自己）
        assert d["modules"] == list(KERNEL_NATIVE_MODULES.keys())
        assert "selfref" in d["modules"]
        assert d["constitution"] == list(_CONSTITUTION)
        assert d["templates"] == []  # 初始无模板

    def test_constitution_is_structured_nonempty(self):
        """SR-3：宪法 = 结构化不变量集（非空，非硬编码自描述字符串）。"""
        p = SelfRefPlugin()
        cons = p.constitution()
        assert len(cons) >= 3
        assert all(isinstance(c, str) and c for c in cons)
        # 宪法含"自修改须经验证门"的元规则（递归性："我如何被修改"）
        assert any("verify" in c for c in cons)

    def test_register_template_roundtrip(self):
        """SR-2：模板注册 → templates 内省（真内省，非硬编码）。"""
        p = SelfRefPlugin()
        assert p.templates() == []
        p.register_template("greet", "return 'hi {who}'")
        p.register_template("classify", "func classify(str x) -> str:\n    if {cond}:\n        return 'a'\n    return 'h'\n")
        assert p.templates() == ["greet", "classify"]
        d = p.describe()
        assert d["templates"] == ["greet", "classify"]  # describe 反映注册

    def test_render_deterministic_assembly(self):
        """SR-2：render = 确定性组装（受控占位替换，零 LLM）。"""
        p = SelfRefPlugin()
        p.register_template("greet", "return 'hi {who}'")
        assert p.render("greet", {"who": "world"}) == "return 'hi world'"

    def test_render_multi_placeholder(self):
        """SR-2：多占位独立替换。"""
        p = SelfRefPlugin()
        p.register_template("f", "{a}+{b}+{a}")
        assert p.render("f", {"a": "1", "b": "2"}) == "1+2+1"


class TestSelfRefFailFast:
    """fail-fast 纪律（非静默/非 tricky）。"""

    def test_render_unregistered_template(self):
        p = SelfRefPlugin()
        with pytest.raises(RuntimeError):
            p.render("nope", {})

    def test_render_missing_placeholder(self):
        p = SelfRefPlugin()
        p.register_template("f", "{a}+{b}")
        with pytest.raises(RuntimeError):
            p.render("f", {"a": "1"})  # 缺 b

    def test_register_template_empty_name(self):
        p = SelfRefPlugin()
        with pytest.raises(RuntimeError):
            p.register_template("", "x")

    def test_register_template_empty_body(self):
        p = SelfRefPlugin()
        with pytest.raises(RuntimeError):
            p.register_template("f", "")


class TestSelfRefE2E:
    """IBCI 内端到端——完整自指性管线（register → render → meta.compile）。"""

    def test_e2e_assemble_and_compile(self):
        """架构确定性组装合法 ibci + meta.compile 验证（e49 教训的架构解）。"""
        out = _run('''import selfref
import meta
selfref.register_template("classify", """func classify(str x) -> str:
    if {cond}:
        return 'assert'
    return 'hedge'
""")
str code = selfref.render("classify", {"cond": "x.find('证实') >= 0"})
dict art = meta.compile(code)
print("compiles=" + str(art["ok"]))
print("n_funcs=" + str(art["n_funcs"]))
''')
        assert "compiles=True" in out
        assert "n_funcs=1" in out

    def test_e2e_describe(self):
        """IBCI 内 describe 真内省（modules 含 selfref 自身——自指性）。"""
        out = _run('''import selfref
dict d = selfref.describe()
list mods = d["modules"]
print("n_modules=" + str(mods.len()))
list cons = d["constitution"]
print("n_const=" + str(cons.len()))
''')
        assert f"n_modules={len(KERNEL_NATIVE_MODULES)}" in out
        assert "n_const=3" in out
