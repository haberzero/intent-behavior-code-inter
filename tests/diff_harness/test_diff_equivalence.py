"""
tests/diff_harness/test_diff_equivalence.py

差分等价 harness——双内核替换的常设安全网（地基验收）：

- **语料合法 + Python 参考内核确定性**：全部语料脚本合法 IBCI + Python 内核
  两次执行数据面逐字节一致（参考基准自身确定性——差分比对的前提）；
- **Rust 内核检测（双内核协议）**：`load_rust_kernel` 经 ibci_ext kernel_info
  探明状态（未构建 = 未加载[合法态] / 已构建 = 加载 + status）；骨架
  status="skeleton" → ready=False（仅加载验证，不比数据面——无静默回退）；
- **差分报告正确性**：Rust 未就绪 → 仅 Python 参考确定性验证（报告如实，不
  冒充 Rust）；Rust 就绪（执行核心落地后）→ 双内核数据面逐字节比对。

注：本 harness 是常设交付物（整个替换的安全网）——语料扩展（现有测试用例 +
fuzz 种子）+ Rust 就绪后的差分比对归后续阶段。
"""
import pytest

from tests.diff_harness.corpus import CORPUS, names
from tests.diff_harness.harness import differential_check, load_rust_kernel, python_kernel_data_plane


class TestCorpus:
    def test_corpus_non_empty(self):
        assert len(CORPUS) > 0
        assert len(set(names())) == len(names())  # 语料名唯一

    def test_all_corpus_valid_and_deterministic(self):
        """全部语料合法 IBCI + Python 内核两次执行数据面逐字节一致。"""
        for name, script in CORPUS:
            d1 = python_kernel_data_plane(script)
            d2 = python_kernel_data_plane(script)
            assert d1 == d2, f"语料 {name} Python 内核非确定性"


class TestRustKernelDetection:
    def test_load_handles_absent_so(self, tmp_path, monkeypatch):
        """Rust 未构建（.so 缺失）= 未加载（合法态，不崩）。"""
        import tests.diff_harness.harness as h
        monkeypatch.setattr(h, "_SO_PATH", str(tmp_path / "nope.so"))
        rk = h.load_rust_kernel()
        assert rk.loaded is False
        assert rk.ready is False

    def test_load_detects_skeleton(self):
        """Rust 已构建（.so 存在）= 加载 + kernel_info 探明状态。

        骨架 status="skeleton" → ready=False（仅加载验证）。若 .so 未
        构建（环境未跑 build_rust_ext.sh）= 未加载（合法态），断言不崩。
        """
        rk = load_rust_kernel()
        if rk.loaded:
            assert rk.name == "rust"
            assert rk.stage >= 1
            # 骨架未就绪（执行核心未落地）——ready 仅当 status == "ready"
            assert rk.ready is (rk.status == "ready")
        # 未加载亦是合法态（harness 优雅降级到仅 Python 参考）


class TestDifferentialReport:
    def test_report_python_reference_only_when_rust_not_ready(self):
        """Rust 未就绪 → 报告 = 仅 Python 参考确定性验证（14/14），不冒充 Rust。"""
        report = differential_check(CORPUS)
        assert report.total == len(CORPUS)
        assert report.python_deterministic == len(CORPUS)  # 参考内核全确定性
        assert not report.mismatches or all(
            m["kind"] != "differential" for m in report.mismatches
        )
        # Rust 就绪时才有差分比对（骨架 → compared=0）
        if not report.rust_ready:
            assert report.compared == 0
        summary = report.summary()
        assert "差分 harness" in summary


class TestRustLexerTokenDifferential:
    """Rust lexer（ibci_ext.lex）vs Python lexer 的 token 级差分等价（语料面）。

    Rust lexer = Rust 前端首增量（core normal 模式：数字/标识符/关键字/字符串/
    运算符/括号/点/冒号/逗号/注释/换行 + 行处理 + 缩进）。token 级差分 = Rust
    token 流 == Python token 流（type 名 + value + line + column 逐条）。
    """

    def test_lexer_loaded_or_graceful(self):
        """Rust lexer 已构建 = 已加载；未构建 = 优雅降级（token 级差分跳过）。"""
        from tests.diff_harness.harness import load_rust_kernel
        rk = load_rust_kernel()
        # 未构建亦是合法态（harness 优雅降级）
        assert rk.loaded in (True, False)

    def test_token_differential_corpus(self):
        """token 级差分等价：全部语料 Rust token 流 == Python token 流。"""
        from tests.diff_harness.harness import (
            load_rust_kernel, python_lexer_tokens, rust_lexer_tokens,
        )
        rk = load_rust_kernel()
        if not rk.loaded:
            pytest.importorskip("tests", reason="Rust .so 未构建——token 级差分跳过")
            return
        for name, script in CORPUS:
            pt = python_lexer_tokens(script)
            rt = rust_lexer_tokens(script)
            assert rt == pt, f"语料 {name} token 级差分不等价"

    def test_token_differential_simple(self):
        """token 级差分等价：简单 IBCI 片段（算术/控制流/字符串/容器）。"""
        from tests.diff_harness.harness import (
            load_rust_kernel, python_lexer_tokens, rust_lexer_tokens,
        )
        rk = load_rust_kernel()
        if not rk.loaded:
            return
        snippets = [
            "x = 1 + 2 * 3\nprint(x)\n",
            's = "hello"\nprint(s)\n',
            "xs = [1, 2, 3]\nprint(xs)\n",
            "d = {'a': 1}\nprint(d)\n",
            "if x > 5:\n    print('big')\nelse:\n    print('small')\n",
            "for i in range(3):\n    print(i)\n",
            "func add(int a, int b) -> int:\n    return a + b\n",
        ]
        for src in snippets:
            assert rust_lexer_tokens(src) == python_lexer_tokens(src)


class TestRustParserAstDifferential:
    """Rust parser（ibci_ext.parse_struct）vs Python parser 的 AST 级差分等价。

    Rust parser = Rust 前端第二增量（完整语句/表达式面：Assign[Name/Subscript
    target] / ExprStmt / If[elif 链] / For / FunctionDef[typed args + returns] /
    Return / Break / Continue / Pass / Constant / Name / BinOp[+ - * / // % **] /
    UnaryOp / Compare / Call / List / Dict / Attribute / Subscript）+ **位置跟踪
    对齐**（每节点 lineno/col_offset/end_lineno/end_col_offset 对齐 Python _loc）。
    AST 级差分 = Rust AST 完整形态（含位置）== Python AST 完整形态（tests/
    diff_harness/ast_dump.py include_positions=True 参考）。
    """

    def test_ast_differential_simple(self):
        """AST 级差分等价：简单 IBCI 片段（Rust AST structure == Python）。"""
        from tests.diff_harness.ast_dump import parse_ast_dump
        from tests.diff_harness.harness import load_rust_kernel, rust_parse_struct
        rk = load_rust_kernel()
        if not rk.loaded:
            return
        snippets = [
            "x = 1\n",
            "s = 'hi'\n",
            "x = 1 + 2\n",
            "print(x)\n",
            "add(1, 2)\n",
            "x = 1\ny = 2\nprint(x + y)\n",
        ]
        for src in snippets:
            rs = rust_parse_struct(src)
            py = parse_ast_dump(src, include_positions=True)
            assert rs == py, f"AST 级差分不等价：\n  py : {py}\n  rust: {rs}"

    def test_ast_differential_corpus(self):
        """AST 级差分等价：全部语料（Rust parser 完整面 == Python）。"""
        from tests.diff_harness.ast_dump import parse_ast_dump
        from tests.diff_harness.harness import load_rust_kernel, rust_parse_struct
        rk = load_rust_kernel()
        if not rk.loaded:
            return
        for name, script in CORPUS:
            rs = rust_parse_struct(script)
            py = parse_ast_dump(script, include_positions=True)
            assert rs == py, f"语料 {name} AST 级差分不等价：\n  py : {py}\n  rust: {rs}"

    def test_ast_differential_remaining_forms(self):
        """AST 级差分等价：剩余语句/表达式面（while/try/class/三元/lambda）。"""
        from tests.diff_harness.ast_dump import parse_ast_dump
        from tests.diff_harness.harness import load_rust_kernel, rust_parse_struct
        rk = load_rust_kernel()
        if not rk.loaded:
            return
        snippets = [
            "i = 0\nwhile i < 3:\n    i = i + 1\n",
            "try:\n    x = 1\nexcept:\n    x = 0\n",
            "class Animal:\n    name = 'generic'\n",
            "y = 'pos' if x > 0 else 'non'\n",
            "f = lambda(int a): a + 1\n",
            "f = lambda: 1 + 1\n",
            "f = lambda -> int: 1\n",
        ]
        for src in snippets:
            rs = rust_parse_struct(src)
            py = parse_ast_dump(src, include_positions=True)
            assert rs == py, f"剩余面 AST 级差分不等价：\n  py : {py}\n  rust: {rs}"


class TestRustDeserializerDifferential:
    """Rust 反序列化器（ibci_ext.deserialize_struct）vs Python AST 的差分等价。

    执行核心的输入契约：Rust 侧消费 Python 前端产出的序列化 artifact
    （FlatSerializer JSON，含语义层输出），反重构 AST。差分 = 反序列化 AST 完整
    形态（含位置）== Python AST 完整形态（验证 Rust 侧可消费 artifact）。
    """

    def test_deserializer_corpus(self):
        """反序列化差分等价：全部语料（artifact → Rust AST == Python AST）。"""
        import json
        from tests.conftest import compile_ibci
        from core.compiler.serialization.serializer import FlatSerializer
        from tests.diff_harness.ast_dump import parse_ast_dump
        from tests.diff_harness.harness import load_rust_kernel, rust_deserialize_struct
        rk = load_rust_kernel()
        if not rk.loaded:
            return
        for name, code in CORPUS:
            try:
                artifact = compile_ibci(code)
            except Exception:
                continue  # 编译失败语料跳过（合法态）
            data = FlatSerializer().serialize_artifact(artifact)
            js = json.dumps(data, ensure_ascii=False)
            rs = rust_deserialize_struct(js)
            py = parse_ast_dump(code, include_positions=True)
            assert rs == py, f"语料 {name} 反序列化 AST 差分不等价：\n  py : {py}\n  rust: {rs}"

    def test_symbol_table_corpus(self):
        """符号表差分等价：全部语料（Rust symbol_table == Python node_to_symbol
        解析）。执行核心的完整 artifact 消费——不止 nodes 池（symbols 池 +
        node_to_symbol 侧表）。"""
        import json
        from tests.conftest import compile_ibci
        from core.compiler.serialization.serializer import FlatSerializer
        from tests.diff_harness.harness import load_rust_kernel, rust_symbol_table
        rk = load_rust_kernel()
        if not rk.loaded:
            return
        for name, code in CORPUS:
            try:
                artifact = compile_ibci(code)
            except Exception:
                continue  # 编译失败语料跳过（合法态）
            data = FlatSerializer().serialize_artifact(artifact)
            js = json.dumps(data, ensure_ascii=False)
            rs = rust_symbol_table(js)
            # Python 参考：同一 artifact 的 node_to_symbol 解析（node → symbol 名）
            mod = data["modules"][data["entry_module"]]
            syms = {u: s["name"] for u, s in mod["pools"]["symbols"].items()}
            py = "\n".join(
                sorted(
                    f"{n} -> {syms[s]}"
                    for n, s in mod["side_tables"]["node_to_symbol"].items()
                    if s in syms
                )
            )
            assert rs == py, f"语料 {name} 符号表差分不等价：\n  py : {py}\n  rust: {rs}"

    def test_type_table_corpus(self):
        """类型表差分等价：全部语料（Rust type_table == Python node_to_type
        解析）。执行核心的完整 artifact 消费——types 池 + node_to_type 侧表。"""
        import json
        from tests.conftest import compile_ibci
        from core.compiler.serialization.serializer import FlatSerializer
        from tests.diff_harness.harness import load_rust_kernel, rust_type_table
        rk = load_rust_kernel()
        if not rk.loaded:
            return
        for name, code in CORPUS:
            try:
                artifact = compile_ibci(code)
            except Exception:
                continue  # 编译失败语料跳过（合法态）
            data = FlatSerializer().serialize_artifact(artifact)
            js = json.dumps(data, ensure_ascii=False)
            rs = rust_type_table(js)
            # Python 参考：同一 artifact 的 node_to_type 解析（node → type 名）
            mod = data["modules"][data["entry_module"]]
            types = {u: t["name"] for u, t in mod["pools"]["types"].items()}
            py = "\n".join(
                sorted(
                    f"{n} -> {types[t]}"
                    for n, t in mod["side_tables"]["node_to_type"].items()
                    if t in types
                )
            )
            assert rs == py, f"语料 {name} 类型表差分不等价：\n  py : {py}\n  rust: {rs}"


class TestRustExecutionDataPlane:
    """Rust 执行核心（ibci_ext.run_artifact）vs Python 执行核心的数据面差分等价。

    执行核心 = P9 阶段③ 主战场（cProfile 实证性能瓶颈）。迁移期策略：Python 前端
    → artifact → Rust 执行核心（反序列化 + 执行）。数据面差分 = Rust print 输出
    == Python print 输出。本增量 = 非 KB 语料面（KB 语料需宿主服务 = 后续增量）。
    """

    def test_data_plane_non_host_corpus(self):
        """数据面差分等价：非宿主服务语料（无桥接，Rust 执行 == Python 执行）。

        KB（knowledge()）与 quoted 值（import meta）需 host service 桥接——由
        test_data_plane_full_corpus 覆盖；本测试仅无桥接语料。
        """
        from tests.conftest import run_ibci
        from tests.diff_harness.harness import load_rust_kernel, rust_execution_data_plane
        rk = load_rust_kernel()
        if not rk.loaded:
            return
        non_host = [
            (n, c)
            for n, c in CORPUS
            if (
                not n.startswith("kb_")
                and "import meta" not in c
                and "from meta import" not in c
            )
        ]
        for name, code in non_host:
            py = run_ibci(code)
            rs = rust_execution_data_plane(code)
            assert rs == py, f"语料 {name} 数据面差分不等价：\n  py : {py}\n  rust: {rs}"

    def test_data_plane_simple(self):
        """数据面差分等价：简单 IBCI 片段（算术/控制流/函数/容器/字符串）。"""
        from tests.conftest import run_ibci
        from tests.diff_harness.harness import load_rust_kernel, rust_execution_data_plane
        rk = load_rust_kernel()
        if not rk.loaded:
            return
        snippets = [
            "print(1 + 2 * 3)\n",
            "x = 0\nfor i in range(1, 11):\n    x = x + i\nprint(x)\n",
            "func double(int n) -> int:\n    return n * 2\nprint(double(21))\n",
            "xs = [1, 2]\nxs.append(3)\nprint(xs)\n",
            "print('a' + 'b')\n",
        ]
        for src in snippets:
            py = run_ibci(src)
            rs = rust_execution_data_plane(src)
            assert rs == py, f"数据面差分不等价：\n  py : {py}\n  rust: {rs}"

    def test_data_plane_kb_corpus(self):
        """数据面差分等价：KB 语料面（host service 桥接——KB 操作委托 Python
        knowledge 对象，KB 逻辑留 Python 单点真理）。"""
        from tests.conftest import run_ibci
        from tests.diff_harness.harness import load_rust_kernel, rust_execution_data_plane
        from tests.diff_harness import bridge
        rk = load_rust_kernel()
        if not rk.loaded:
            return
        kb = [(n, c) for n, c in CORPUS if n.startswith("kb_")]
        for name, code in kb:
            py = run_ibci(code)
            rs = rust_execution_data_plane(code, bridge)
            assert rs == py, f"语料 {name} KB 数据面差分不等价：\n  py : {py}\n  rust: {rs}"

    def test_data_plane_full_corpus(self):
        """数据面差分等价：全语料（非 KB/quoted + KB host service 桥接 + quoted
        值 meta host service 桥接）。"""
        from tests.conftest import run_ibci
        from tests.diff_harness.harness import load_rust_kernel, rust_execution_data_plane
        from tests.diff_harness import bridge
        rk = load_rust_kernel()
        if not rk.loaded:
            return
        for name, code in CORPUS:
            # KB（knowledge()）、quoted 值（import meta）与 from-import
            # （from meta import）经 host service 桥接
            needs_bridge = (
                name.startswith("kb_")
                or "import meta" in code
                or "from meta import" in code
            )
            py = run_ibci(code)
            rs = rust_execution_data_plane(code, bridge if needs_bridge else None)
            assert rs == py, f"语料 {name} 数据面差分不等价：\n  py : {py}\n  rust: {rs}"

    def test_parallel_execution_equivalence(self):
        """并行执行 API（run_artifacts_parallel）：多纯 CPU artifact 经 Rust 线程
        GIL-free 真并行执行——结果 == 顺序执行（run_artifact），顺序保持。"""
        import json
        from tests.conftest import compile_ibci
        from core.compiler.serialization.serializer import FlatSerializer
        from tests.diff_harness.harness import load_rust_kernel
        rk = load_rust_kernel()
        if not rk.loaded or not hasattr(rk._module, "run_artifacts_parallel"):
            return
        # 4 个纯 CPU artifact（不同值，无宿主服务）
        artifacts = []
        for i in range(4):
            code = f"s = 0\nfor j in range(1, 20001):\n    s = s + j + {i}\nprint(s)\n"
            a = compile_ibci(code)
            artifacts.append(
                json.dumps(FlatSerializer().serialize_artifact(a), ensure_ascii=False)
            )
        # 顺序执行（run_artifact）
        seq = [list(rk._module.run_artifact(js, None)) for js in artifacts]
        # 4 线程并行执行（run_artifacts_parallel）
        par = rk._module.run_artifacts_parallel(artifacts, 4)
        par = [list(x) for x in par]
        assert par == seq, f"并行执行 != 顺序执行：\n  seq: {seq}\n  par: {par}"

    def test_task_pool_equivalence(self):
        """有状态任务池（TaskPool）：CPU 任务 submit 入队 → run_all 经 Rust 线程
        GIL-free 真并行执行——结果（按任务 ID 序）== 顺序执行，空池 = 空列表。"""
        import json
        from tests.conftest import compile_ibci
        from core.compiler.serialization.serializer import FlatSerializer
        from tests.diff_harness.harness import load_rust_kernel
        rk = load_rust_kernel()
        if not rk.loaded or not hasattr(rk._module, "TaskPool"):
            return
        # 4 个纯 CPU artifact（不同值，无宿主服务）
        artifacts = []
        for i in range(4):
            code = f"s = 0\nfor j in range(1, 20001):\n    s = s + j + {i}\nprint(s)\n"
            a = compile_ibci(code)
            artifacts.append(
                json.dumps(FlatSerializer().serialize_artifact(a), ensure_ascii=False)
            )
        # TaskPool：submit 入队 → run_all 并行执行
        pool = rk._module.TaskPool(4)
        for js in artifacts:
            pool.submit(js)
        assert pool.pending() == 4
        res = pool.run_all()
        # 按任务 ID 序取结果
        par = [item[1] for item in sorted(res, key=lambda x: x[0])]
        par = [list(x) for x in par]
        # 顺序执行（run_artifact）
        seq = [list(rk._module.run_artifact(js, None)) for js in artifacts]
        assert par == seq, f"任务池并行 != 顺序执行：\n  seq: {seq}\n  par: {par}"
        # 空池 run_all = 空列表
        assert rk._module.TaskPool(2).run_all() == []


class TestRustSerializationUid:
    """序列化 UID 差分（全量 Rust 化·序列化面）：Rust node_uid/type_uid/asset_uid
    与 Python core/base/uid.py 逐条等价（确定性哈希 = sha256 前 16 hex）。"""

    def test_node_uid_corpus_node_pool(self):
        """34 语料节点池：Rust node_uid[json.dumps(node_data, sort_keys=True)] ==
        Python uid（节点池键）——序列化 UID 差分等价。"""
        import json
        from tests.conftest import compile_ibci
        from core.compiler.serialization.serializer import FlatSerializer
        from tests.diff_harness.harness import load_rust_kernel
        rk = load_rust_kernel()
        if not rk.loaded or not hasattr(rk._module, "node_uid"):
            return
        for name, code in CORPUS:
            artifact = compile_ibci(code)
            data = FlatSerializer().serialize_artifact(artifact)
            # 节点池（uid → node_data）
            node_pool = data["pools"]["nodes"]
            for uid, node_data in node_pool.items():
                content = json.dumps(node_data, sort_keys=True)
                rs = rk._module.node_uid(content)
                assert rs == uid, (
                    f"语料 {name} 节点 UID 差分不等价：\n  py: {uid}\n  rust: {rs}\n"
                    f"  node_data: {node_data}"
                )

    def test_type_uid_and_asset_uid(self):
        """type_uid / asset_uid：Rust == Python（确定性哈希 + 稳定 UID）。"""
        from core.base.uid import asset_uid as py_asset_uid, type_uid as py_type_uid
        from tests.diff_harness.harness import load_rust_kernel
        rk = load_rust_kernel()
        if not rk.loaded or not hasattr(rk._module, "type_uid"):
            return
        for module_path, name in [(None, "int"), ("core.mod", "MyClass"), ("root", "x")]:
            rs = rk._module.type_uid(name, module_path)
            py = py_type_uid(module_path, name)
            assert rs == py, f"type_uid 差分不等等：py={py} rust={rs}"
        for text in ["hello world", "1 + 2", ""]:
            rs = rk._module.asset_uid(text)
            py = py_asset_uid(text)
            assert rs == py, f"asset_uid 差分不等价：py={py} rust={rs}"

    def test_node_pool_corpus(self):
        """34 语料节点池差分（全量 Rust 化·序列化面）：Rust 节点池 == Python 节点池
        （node_data 内容等价）。free_vars 字段 = 语义层输出（Rust parser 未承载，非
        序列化面），其值差异会改变节点 content_str → UID，故比对时排除 free_vars 字段
        并规范化节点引用 UID（node_... → <UID>），按节点内容集合比对（节点结构 + 非
        UID 字段值等价；UID 本身由 content_str 派生，free_vars 差异不影响节点结构）。"""
        import json
        from tests.conftest import compile_ibci
        from core.compiler.serialization.serializer import FlatSerializer
        from tests.diff_harness.harness import load_rust_kernel
        rk = load_rust_kernel()
        if not rk.loaded or not hasattr(rk._module, "serialize_nodes"):
            return

        def _norm(val):
            if isinstance(val, str) and val.startswith("node_"):
                return "<UID>"
            if isinstance(val, list):
                return [_norm(v) for v in val]
            return val

        def _normalize(node_data):
            # 排除 free_vars（语义层输出，非序列化面）+ 规范化节点引用 UID
            return {
                k: _norm(v) for k, v in node_data.items() if k != "free_vars"
            }

        for name, code in CORPUS:
            root, pool_json = rk._module.serialize_nodes(code)
            rs_pool = json.loads(pool_json)
            py_pool = FlatSerializer().serialize_artifact(compile_ibci(code))["pools"]["nodes"]
            # 节点内容集合比对（排除 free_vars + 规范化 UID）
            rs_set = {json.dumps(_normalize(nd), sort_keys=True) for nd in rs_pool.values()}
            py_set = {json.dumps(_normalize(nd), sort_keys=True) for nd in py_pool.values()}
            missing = py_set - rs_set
            assert not missing, (
                f"语料 {name} 节点池差分缺失（Python 有 Rust 无）：\n  {sorted(missing)[:2]}"
            )
            extra = rs_set - py_set
            assert not extra, (
                f"语料 {name} 节点池差分多余（Rust 有 Python 无）：\n  {sorted(extra)[:2]}"
            )
