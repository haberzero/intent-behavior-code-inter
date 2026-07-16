"""
tests/e2e/test_e2e_engine_lifecycle.py
=======================================

IBCIEngine 生命周期 e2e 测试（PT-TEST-4 area 2）。

验证核心生命周期契约：
1. 新引擎未封印、无解释器
2. ``compile_string`` 不封印注册表（编译无副作用于 seal 状态）
3. ``execute`` 封印注册表（单次执行后不可复用）
4. 封印后再次 ``execute`` 抛 ``PermissionError``（NEXT_STEPS 指定的核心契约）
5. ``compile_string`` → ``execute`` 分步流程可独立工作并产出输出
6. 典型用户路径 ``run_string`` 单次运行后封印引擎

设计约束：每个 Engine 实例只能执行一次（封印后需新建实例），因此每个测试创建独立引擎。
不依赖 LLM（无 ``@~`` 调用），故无需 MOCK 配置。
"""
import os

import pytest

from core.engine import IBCIEngine
from core.kernel.path import PathValidator
from tests.conftest import TESTS_ROOT

# 简单非 LLM 代码：无需 MOCK 即可运行
_SIMPLE_CODE = 'str x = "hello"\nprint(x)\n'


def _new_engine():
    return IBCIEngine(root_dir=TESTS_ROOT, auto_sniff=False)


class TestEngineLifecycle:
    """IBCIEngine 的封印/重入/分步执行契约。"""

    def test_fresh_engine_not_sealed_and_no_interpreter(self):
        """新引擎：注册表未封印，解释器尚未创建（惰性初始化）。"""
        eng = _new_engine()
        assert eng.registry.is_sealed is False
        assert eng.interpreter is None

    def test_compile_does_not_seal_registry(self):
        """compile_string 仅编译，不产生封印副作用。"""
        eng = _new_engine()
        eng.compile_string(_SIMPLE_CODE, silent=True)
        assert eng.registry.is_sealed is False

    def test_execute_seals_registry(self):
        """execute 执行产物后封印注册表（单次执行语义）。"""
        eng = _new_engine()
        artifact = eng.compile_string(_SIMPLE_CODE, silent=True)
        eng.execute(artifact, output_callback=lambda t: None)
        assert eng.registry.is_sealed is True

    def test_sealed_registry_reexecute_raises_permission_error(self):
        """封印后再次 execute 必须抛 PermissionError（核心安全契约）。

        这是 NEXT_STEPS 明确指定的契约：防止在已封印注册表上复用引擎。
        """
        eng = _new_engine()
        artifact = eng.compile_string(_SIMPLE_CODE, silent=True)
        eng.execute(artifact, output_callback=lambda t: None)
        assert eng.registry.is_sealed is True
        with pytest.raises(PermissionError):
            eng.execute(artifact, output_callback=lambda t: None)

    def test_compile_then_execute_produces_output(self):
        """compile_string 返回可执行产物；execute 独立消费它并产出输出。"""
        eng = _new_engine()
        artifact = eng.compile_string(_SIMPLE_CODE, silent=True)
        assert artifact is not None
        lines = []
        eng.execute(artifact, output_callback=lambda t: lines.append(str(t)))
        assert "hello" in lines

    def test_run_string_seals_engine_after_single_run(self):
        """典型用户路径 run_string 单次运行后封印引擎。"""
        eng = _new_engine()
        eng.run_string(_SIMPLE_CODE, silent=True)
        assert eng.registry.is_sealed is True

    def test_engine_instances_are_isolated(self):
        """两个独立引擎实例互不干扰：A 封印不影响 B 独立执行。"""
        eng_a = _new_engine()
        eng_b = _new_engine()
        eng_a.run_string('str a = "A"\nprint(a)\n', silent=True)
        assert eng_a.registry.is_sealed is True
        # A 已封印，B 仍可独立完成完整的 compile→execute 生命周期
        lines_b = []
        eng_b.run_string('str b = "B"\nprint(b)\n', silent=True, output_callback=lambda t: lines_b.append(str(t)))
        assert "B" in lines_b
        assert eng_b.registry.is_sealed is True


class TestEngineRootDirContract:
    """IBCIEngine 的 project_root 契约（ADR-019 §2：引擎级默认 + 延迟确立）。

    ADR-019：root_dir 可选；未提供时 project_root 在 run/compile 时确立为 entry_dir。
    root-dependent 初始化（Scheduler/plugin 发现）延迟到 _ensure_root_initialized。
    D2 保留：root 经 canonicalize_for_security 规范化（解 symlink）。
    """

    def test_construct_without_root_dir_succeeds_root_deferred(self):
        """无 root_dir 构造成功（引擎级默认）；root_dir 延迟（构造期为 None）。"""
        eng = IBCIEngine(auto_sniff=False)
        assert eng.root_dir is None  # 延迟，未确立
        assert eng._explicit_root is None

    def test_explicit_root_canonicalized_at_construction(self, tmp_path):
        """显式 root_dir 在构造期即 canonicalize（_explicit_root 立即可用）。"""
        eng = IBCIEngine(root_dir=str(tmp_path), auto_sniff=False)
        expected = PathValidator.canonicalize_for_security(str(tmp_path)).to_native()
        assert eng._explicit_root == expected

    def test_run_defaults_project_root_to_entry_dir(self, tmp_path):
        """无显式 root + run(entry_file) → project_root 默认 = entry_dir（canonicalize）。"""
        entry = tmp_path / "main.ibci"
        entry.write_text('str x = "hi"\nprint(x)\n', encoding="utf-8")
        eng = IBCIEngine(auto_sniff=False)  # 无 root
        eng.run(str(entry), silent=True)
        # project_root 应 = entry 所在目录（canonicalize）
        assert eng.root_dir == PathValidator.canonicalize_for_security(str(tmp_path)).to_native()

    def test_explicit_root_overrides_entry_dir_default(self, tmp_path):
        """显式 root 优先于 entry_dir 默认：run 后 project_root 仍 = 显式 root。"""
        explicit_root = tmp_path / "myroot"
        explicit_root.mkdir()
        entry = explicit_root / "main.ibci"  # entry 必须在 root 内（沙箱可及）
        entry.write_text('str x = "hi"\nprint(x)\n', encoding="utf-8")
        eng = IBCIEngine(root_dir=str(explicit_root), auto_sniff=False)
        eng.run(str(entry), silent=True)
        assert eng.root_dir == PathValidator.canonicalize_for_security(str(explicit_root)).to_native()

    def test_run_string_without_explicit_root_raises(self, tmp_path):
        """run_string 无真实 entry_file；无显式 root 时必须报错（无可默认的 entry_dir）。"""
        eng = IBCIEngine(auto_sniff=False)  # 无 root
        with pytest.raises(Exception):  # InterpreterError
            eng.run_string('str x = "hi"\n', silent=True)

    def test_run_string_with_explicit_root_succeeds(self):
        """run_string 有显式 root 时正常（_new_engine 提供 root）。"""
        eng = _new_engine()
        eng.run_string('str x = "hi"\nprint(x)\n', silent=True)
        assert eng.root_dir is not None

    def test_root_dir_resolves_symlinks(self, tmp_path):
        """显式 root_dir 含符号链接时解析到真实路径（D2：symlink 基准统一）。"""
        import os
        target = tmp_path / "real_project"
        target.mkdir()
        link = tmp_path / "link_project"
        try:
            os.symlink(str(target), str(link))
        except (OSError, NotImplementedError):
            pytest.skip("无法创建符号链接（权限不足）")
        eng = IBCIEngine(root_dir=str(link), auto_sniff=False)
        assert eng._explicit_root == os.path.realpath(str(target))

    def test_cwd_saved_at_construction(self):
        """ADR-019 §2 A4：CWD 在构造期单独保存（无上界校验）。"""
        import os
        eng = IBCIEngine(auto_sniff=False)
        assert eng._cwd == os.getcwd()

    def test_run_relative_entry_canonicalizes_to_absolute(self, tmp_path, monkeypatch):
        """B1 修复：相对 entry_file 经 canonicalize_for_security → 绝对 entry_dir（§6.1 锚点健全）。

        旧 bug：run() 仅 resolve_dot_segments（词法），相对 entry 产出相对 entry_dir，
        破坏运行时路径解析。
        """
        entry = tmp_path / "main.ibci"
        entry.write_text('str x = "hi"\nprint(x)\n', encoding="utf-8")
        monkeypatch.chdir(str(tmp_path))  # chdir 后用相对路径调用
        eng = IBCIEngine(auto_sniff=False)
        eng.run("main.ibci", silent=True)
        # entry_dir 必须是绝对的（canonicalize 后），非相对 "main.ibci" 的父目录 "."
        assert os.path.isabs(eng._path_ctx.entry_dir.to_native())

    def test_execute_without_prior_compile_raises(self, tmp_path):
        """B2 修复：execute() 未经 run/compile 触发 root 初始化 → 明确 InterpreterError（非 AttributeError）。"""
        from core.kernel.issue import InterpreterError
        eng = IBCIEngine(root_dir=str(tmp_path), auto_sniff=False)
        with pytest.raises(InterpreterError):
            eng.execute(None)


class TestPluginSearchPathResolution:
    """ADR-019 §3 plugin 发现优先级：builtin > global_plugin > plugin_paths > 嗅探 > 全局(预留)。"""

    @staticmethod
    def _resolve(project_root, auto_sniff=True):
        eng = IBCIEngine(root_dir=project_root, auto_sniff=auto_sniff)
        return eng._resolve_plugin_search_paths(project_root), eng._builtin_path

    def test_builtin_always_first_and_highest(self, tmp_path):
        """builtin 恒在且最高优先级（search_paths[0]）。"""
        paths, builtin = self._resolve(str(tmp_path))
        assert paths[0] == builtin

    def test_no_config_with_sniff_includes_project_plugin_dirs(self, tmp_path):
        """无 ibci.json + auto_sniff：嗅探 project_root 下的 plugins/ibci_modules。"""
        (tmp_path / "plugins").mkdir()
        (tmp_path / "ibci_modules").mkdir()
        paths, builtin = self._resolve(str(tmp_path))
        # builtin + 两个嗅探目录
        assert any("plugins" in p for p in paths)
        assert any("ibci_modules" in p for p in paths)

    def test_no_config_no_sniff_flag_only_builtin(self, tmp_path):
        """无 ibci.json + auto_sniff=False：仅 builtin（不嗅探）。"""
        (tmp_path / "plugins").mkdir()
        paths, builtin = self._resolve(str(tmp_path), auto_sniff=False)
        assert paths == [builtin]

    def test_explicit_plugin_paths_disables_sniff(self, tmp_path):
        """ibci.json 配置 plugin_paths 后，嗅探不触发（explicit > implicit）。"""
        (tmp_path / "plugins").mkdir()  # 嗅探本会命中它
        ext = tmp_path / "explicit_only"
        ext.mkdir()
        (tmp_path / "ibci.json").write_text(
            json.dumps({"plugin_paths": ["explicit_only"]}), encoding="utf-8"
        )
        paths, builtin = self._resolve(str(tmp_path))
        assert any("explicit_only" in p for p in paths)
        # 嗅探的 plugins/ 不应出现（被显式配置抑制）
        assert not any(p.endswith("plugins") and "explicit_only" not in p for p in paths)

    def test_global_plugin_precedence_over_plugin_paths(self, tmp_path):
        """global_plugin 排在 plugin_paths 之前（更高优先级）。"""
        gp = tmp_path / "glob"
        gp.mkdir()
        pp = tmp_path / "proj"
        pp.mkdir()
        (tmp_path / "ibci.json").write_text(
            json.dumps({"global_plugin": ["glob"], "plugin_paths": ["proj"]}), encoding="utf-8"
        )
        paths, builtin = self._resolve(str(tmp_path))
        gp_idx = next(i for i, p in enumerate(paths) if "glob" in p)
        pp_idx = next(i for i, p in enumerate(paths) if p.endswith("proj"))
        assert gp_idx < pp_idx  # global_plugin 在 plugin_paths 前

    def test_builtin_highest_over_all(self, tmp_path):
        """builtin 排在 global_plugin 与 plugin_paths 之前。"""
        gp = tmp_path / "glob"
        gp.mkdir()
        pp = tmp_path / "proj"
        pp.mkdir()
        (tmp_path / "ibci.json").write_text(
            json.dumps({"global_plugin": ["glob"], "plugin_paths": ["proj"]}), encoding="utf-8"
        )
        paths, builtin = self._resolve(str(tmp_path))
        assert paths[0] == builtin

    def test_dedup_preserves_order(self, tmp_path):
        """重复路径去重，保序。"""
        (tmp_path / "ibci.json").write_text(
            json.dumps({"global_plugin": ["x"], "plugin_paths": ["x"]}), encoding="utf-8"
        )
        (tmp_path / "x").mkdir()
        paths, builtin = self._resolve(str(tmp_path))
        # "x" 只出现一次
        x_count = sum(1 for p in paths if p.endswith("x"))
        assert x_count == 1

    def test_plugin_path_outside_project_root_allowed(self, tmp_path, tmp_path_factory):
        """ADR-019 §5 B4：plugin_path 可在 project_root 之外（特权只读越界）——resolver 不拒绝。"""
        import os
        # 独立临时目录（project_root 之外）
        external = tmp_path_factory.mktemp("external_plugins") / "ext"
        external.mkdir()
        (tmp_path / "ibci.json").write_text(
            json.dumps({"plugin_paths": [str(external)]}), encoding="utf-8"
        )
        paths, builtin = self._resolve(str(tmp_path))
        # 外部路径被纳入（特权越界读取；写入仍由 proj_root 沙箱约束——见 PermissionManager）
        assert os.path.realpath(str(external)) in paths

    def test_inherited_parent_plugins_appended(self, tmp_path):
        """ADR-019 §6 C2：子引擎继承父 plugin search_paths（附加于自身之后，兜底来源）。"""
        parent_extra = tmp_path / "parent_plugins"
        parent_extra.mkdir()
        child_root = tmp_path / "child_area"
        child_root.mkdir()
        # 子引擎直接接收 inherited_plugin_paths（模拟隔离透传）
        child = IBCIEngine(root_dir=str(child_root), auto_sniff=False,
                           inherited_plugin_paths=[str(parent_extra)])
        resolved = child._resolve_plugin_search_paths(str(child_root))
        # 父的 parent_extra 应出现在子的 search_paths（继承，兜底来源）
        assert os.path.realpath(str(parent_extra)) in resolved


# ibci.json 测试需要 json
import json  # noqa: E402


class TestEnginePathContextContract:
    """IBCIEngine 的 PathContext 锚点契约（PT-ARCH-20 D4 + 方案 B）。

    方案 B 核心：entry_dir 必须始终是有意义的用户目录。
    - ``run(entry_file)``：entry_dir = entry_file.parent（§6.1 数据路径契约）
    - ``run_string``/``compile_string``：entry_dir = project_root（tempfile 无意义）
    这样 ``_resolve_isolated_path`` 永远读 entry_dir，无需标志位（符合工作模式定论第 4 条）。
    """

    def test_run_sets_entry_dir_to_entry_parent(self, tmp_path):
        """run(entry_file) 后，PathContext.entry_dir = 入口文件所在目录。"""
        entry = tmp_path / "main.ibci"
        entry.write_text('str x = "hi"\nprint(x)\n', encoding="utf-8")
        eng = IBCIEngine(root_dir=str(tmp_path), auto_sniff=False)
        eng.run(str(entry), silent=True)
        import os
        expected_entry_dir = PathValidator.canonicalize_for_security(str(tmp_path)).to_native()
        assert eng._path_ctx.entry_dir.to_native() == expected_entry_dir

    def test_run_string_sets_entry_dir_to_project_root(self):
        """【方案 B 核心】run_string 后，entry_dir = project_root，而非 tempdir。

        历史 BUG：run_string 经 tempfile，entry_dir 退化为系统 temp 目录（对用户无意义），
        致 ihost.run_isolated 的相对子脚本路径解析失败。
        """
        eng = _new_engine()
        eng.run_string('str x = "hi"\nprint(x)\n', silent=True)
        # entry_dir 必须是 project_root（= TESTS_ROOT 经 canonicalize），而非 tempdir
        assert eng._path_ctx.entry_dir.to_native() == eng.root_dir

    def test_compile_string_sets_entry_dir_to_project_root(self):
        """compile_string（不执行）同样把 entry_dir 锚到 project_root。"""
        eng = _new_engine()
        eng.compile_string('str x = "hi"\n', silent=True)
        assert eng._path_ctx.entry_dir.to_native() == eng.root_dir

    def test_run_string_entry_dir_not_in_system_temp(self):
        """run_string 的 entry_dir 绝不能落在系统 temp 目录（方案 B 反向断言）。"""
        import tempfile, os
        eng = _new_engine()
        eng.run_string('str x = "hi"\n', silent=True)
        entry_dir = eng._path_ctx.entry_dir.to_native()
        sys_temp = os.path.realpath(tempfile.gettempdir())
        assert not entry_dir.startswith(sys_temp), \
            f"entry_dir 不应是系统 temp：{entry_dir} (sys_temp={sys_temp})"

    def test_run_string_uses_synthetic_entry_file(self):
        """ADR-019 A3：run_string 的 entry_file = 合成 <proj_root>/__string_exec__.ibci（非 tempdir）。"""
        eng = _new_engine()
        eng.run_string('str x = "hi"\nprint(x)\n', silent=True)
        assert eng._entry_file is not None
        assert eng._entry_file.replace("\\", "/").endswith("__string_exec__.ibci")
        # 合成 entry 的 dir = project_root
        assert eng._path_ctx.entry_dir.to_native() == eng.root_dir

    def test_path_ctx_project_root_always_engine_root(self, tmp_path):
        """无论 run 还是 run_string，PathContext.project_root 始终 = engine.root_dir。"""
        entry = tmp_path / "main.ibci"
        entry.write_text('str x = "hi"\nprint(x)\n', encoding="utf-8")
        eng = IBCIEngine(root_dir=str(tmp_path), auto_sniff=False)
        eng.run(str(entry), silent=True)
        assert eng._path_ctx.project_root.to_native() == eng.root_dir
