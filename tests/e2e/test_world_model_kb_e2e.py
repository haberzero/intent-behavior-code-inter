"""
tests/e2e/test_world_model_kb_e2e.py

knowledge 世界模型 KB 面 E2E 契约（用户面全链路：注册词表 → 登记事实 →
7 查找 → 矛盾/传递 → 展开/对比 → 墓碑/版本化）：

- **R-B 验收面对照**（试用方规格）：B2 索引/查找（8 索引 + 7 查找全确定性
  零 LLM）/ B3 对比（1/2/3/5 层确定性）/ B4 按需确定性展开（逐字节一致，
  不预存展开态）/ 双写根治（词关系 = by_subject 派生，无独立存储面）；
- **用户面形态**：全 IBCI 代码（import json 用于字节对比——dict == 为
  恒等语义（既有语言边界），展开态字节对比经 JSON 序列化 str ==）；
- 确定性：全路径零 LLM（纯内存操作），同脚本两次运行输出一致。

注：本文件属 e2e 层（全量门覆盖；不在单任务默认 smoke 子集）。
"""

from tests.conftest import run_ibci


def _mini_world_kb_code(tail: str) -> str:
    """微型世界模型 KB 脚本头（用户面：2 世界 / 3 关系 / 4 词 / 5 事实）+ tail。"""
    return (
        "import json\n"
        "kb = knowledge()\n"
        # 治理词表（KB 元规则）
        'kb.register_world("modern", "现代物理世界", 3)\n'
        'kb.register_world("quantum", "量子世界", 4)\n'
        'kb.register_relation("composed_of", "组成关系", False, False)\n'
        'kb.register_relation("depends_on", "依赖关系", True, False)\n'
        'kb.register_relation("excites", "激发关系", False, True)\n'
        # 词（atom 含跨世界词形——跨尺度自指面）
        'kb.register_word("atom", "原子", False, [], '
        '{"modern": {"form": "atom", "self_ref": "self"}, '
        '"quantum": {"form": "quark", "self_ref": "self"}})\n'
        'kb.register_word("proton", "质子", False, [], {})\n'
        'kb.register_word("electron", "电子", False, [], {})\n'
        'kb.register_word("nucleus", "原子核", False, [], {})\n'
        # 事实日志（append-only；fact_id = seq 确定性）
        'f1 = kb.add_fact("modern", "atom", "composed_of", "proton", "v30", "active")\n'
        'f2 = kb.add_fact("modern", "atom", "composed_of", "electron", "v30", "active")\n'
        'f3 = kb.add_fact("modern", "nucleus", "depends_on", "proton", "v30", "active")\n'
        'f4 = kb.add_fact("modern", "atom", "depends_on", "nucleus", "v30", "active")\n'
        'f5 = kb.add_fact("quantum", "atom", "composed_of", "proton", "v30", "active")\n'
        + tail
    )


class TestKBLookupE2E:
    def test_seven_lookups_user_surface(self):
        """7 查找用户面（试用方 §3.3）：lookup_pair / exists / all_in_world /
        by_source / by_subject / contradicts / transitive。"""
        code = _mini_world_kb_code(
            # 1. lookup_pair：atom 经 composed_of 指向什么（modern 内 2 条）
            "print(len(kb.lookup_pair(\"atom\", \"composed_of\")))\n"
            # 2. exists：事实存在（去重）
            "print(kb.exists(\"modern\", \"atom\", \"composed_of\", \"proton\"))\n"
            "print(kb.exists(\"modern\", \"atom\", \"composed_of\", \"neutron\"))\n"
            # 3. all_in_world
            "print(len(kb.all_in_world(\"modern\")))\n"
            "print(len(kb.all_in_world(\"quantum\")))\n"
            # 4. by_source（审计）
            "print(len(kb.by_source(\"v30\")))\n"
            # 7. by_subject（词关系的派生替代——根治双写）
            "print(len(kb.by_subject(\"atom\")))\n"
            # 5. contradicts：composed_of 非 multi_valued，atom 已有 o → 新 o 矛盾
            "print(kb.contradicts(\"atom\", \"composed_of\", \"neutron\"))\n"
            # excites 为 multi_valued → 恒非矛盾
            "print(kb.contradicts(\"atom\", \"excites\", \"proton\"))\n"
            # 6. transitive：atom -depends_on-> nucleus -depends_on-> proton
            "print(kb.transitive(\"atom\", \"depends_on\"))\n"
        )
        out = run_ibci(code)
        # 注意：by_pair/by_subject 按试用方规格 §3.2 为 **world 无关** 索引
        # （键 = (s,r) / s）——lookup 结果跨世界聚合，world 维经 all_in_world /
        # by_triple（exists）表达
        assert out[0] == "3"        # lookup_pair (atom,composed_of)：f1/f2/f5
        assert out[1] == "True"     # exists 命中（by_triple 含 world 维）
        assert out[2] == "False"    # exists 未命中
        assert out[3] == "4"        # all_in_world modern（world 维视图）
        assert out[4] == "1"        # all_in_world quantum
        assert out[5] == "5"        # by_source v30（全 5 事实同来源）
        assert out[6] == "4"        # by_subject atom：f1/f2/f4/f5
        assert out[7] == "True"     # contradicts 非 multi_valued
        assert out[8] == "False"    # contradicts multi_valued 恒非矛盾
        trans = out[9]
        # 传递闭包：直接 nucleus（via []）+ 经 nucleus 到 proton（via [nucleus]）
        assert "nucleus" in trans and "proton" in trans
        assert '"via": []' in trans
        assert "nucleus" in trans

    def test_governance_gate_user_surface(self):
        """治理门用户面：未注册词表项 add_fact fail-fast（try/except 可捕获，
        诊断码可辨）。"""
        code = (
            "import json\n"
            "kb = knowledge()\n"
            'kb.register_world("modern", "现代物理世界", 3)\n'
            'kb.register_relation("composed_of", "组成关系", False, False)\n'
            'kb.register_word("atom", "原子", False, [], {})\n'
            'try:\n'
            '    kb.add_fact("modern", "atom", "composed_of", "quark")\n'
            "    print('no-error-wrong')\n"
            "except Exception as e:\n"
            "    print(e.message)\n"
            "print('parent-alive')\n"
        )
        out = run_ibci(code)
        assert "no-error-wrong" not in out
        assert "KNW_VOCAB_UNREGISTERED" in "\n".join(out)
        assert out[-1] == "parent-alive"


class TestKBExpandCompareE2E:
    def test_expand_deterministic_byte_identical(self):
        """R-B B4 验收：expand 按需确定性展开——多次调用逐字节一致（经 JSON
        序列化 str == 对比；dict == 恒等语义为既有语言边界）。"""
        code = _mini_world_kb_code(
            "e1 = kb.expand(f1)\n"
            "e2 = kb.expand(f1)\n"
            "print(json.stringify(e1) == json.stringify(e2))\n"
            # 展开全字段（词记录 + 跨世界词形 + 关系语义 + 世界上下文）
            'print(e1["subject"]["gloss"])\n'
            'print(e1["subject_form"]["form"])\n'
            'print(e1["relation"]["semantics"])\n'
            'print(e1["world_ctx"]["size_rank"])\n'
            # quantum 世界的同词跨尺度词形（atom → quark 呈现）
            "e5 = kb.expand(f5)\n"
            'print(e5["subject_form"]["form"])\n'
        )
        out = run_ibci(code)
        assert out[0] == "True"   # 逐字节一致
        assert out[1] == "原子"
        assert out[2] == "atom"   # modern 词形
        assert out[3] == "组成关系"
        assert out[4] == "3"      # modern size_rank
        assert out[5] == "quark"  # quantum 跨尺度词形（跨尺度自指面）

    def test_compare_four_layers(self):
        """对比 4 层（1/2/3/5）用户面：exact / contradiction / scale /
        same_word 各判别（层 4 语义相似归向量面，不在此面）。"""
        code = _mini_world_kb_code(
            # f1 vs f2：同 (s,r) 不同 o（composed_of 非 multi_valued）→ 矛盾；同 world
            "c = kb.compare(f1, f2)\n"
            'print(c["exact"])\n'
            'print(c["contradiction"])\n'
            'print(c["scale"])\n'
            'print(c["same_word"])\n'
            # f1 vs f5：同 (s,r,o) 不同 world → scale cross，exact false
            "c2 = kb.compare(f1, f5)\n"
            'print(c2["scale"])\n'
            'print(c2["exact"])\n'
            # 词同一性
            'print(kb.same_word("atom", "atom"))\n'
            'print(kb.same_word("quark", "quark"))\n'
        )
        out = run_ibci(code)
        assert out[0:4] == ["False", "True", "same", "True"]
        assert out[4:6] == ["cross", "False"]
        assert out[6] == "True"    # atom 已注册
        assert out[7] == "False"   # quark 未注册（跨世界词形 ≠ 注册词）


class TestKBAuditE2E:
    def test_retract_and_amend_user_surface(self):
        """墓碑/版本化用户面：retract（图视图即时排除 + 日志全史保留）/
        amend_fact（o 切换 + 事件链可溯）/ history_fact / source。"""
        code = _mini_world_kb_code(
            "kb.retract(f1, \"实验推翻\")\n"
            # 图视图：f1 退出（lookup 少 1 条）；日志：全史保留
            "print(len(kb.lookup_pair(\"atom\", \"composed_of\")))\n"
            "print(kb.fact_len())\n"
            'print(kb.get_fact(f1)["status"])\n'
            # 事件链（add + retract 全史）
            "h = kb.history_fact(f1)\n"
            "print(len(h))\n"
            'print(h[1]["kind"])\n'
            # 版本化：f2 的 o 从 electron → nucleus（nucleus 已注册）
            "kb.amend_fact(f2, \"nucleus\", \"重新测量\")\n"
            "r = kb.get_fact(f2)\n"
            'print(r["o"])\n'
            'print(r["events"][1]["new_o"])\n'
            "print(kb.source(f2))\n"
            # 墓碑恢复语义 = 新事实（append-only：不复活旧版本）
            'f6 = kb.add_fact("modern", "atom", "composed_of", "proton", "v31")\n'
            'print(kb.get_fact(f6)["status"])\n'
        )
        out = run_ibci(code)
        assert out[0] == "2"        # f1 墓碑后 lookup 剩 f2 + f5（world 无关对索引）
        assert out[1] == "5"        # 日志全史（f1 仍在）
        assert out[2] == "retracted"
        assert out[3] == "2"        # 事件链：add + retract
        assert out[4] == "retract"
        assert out[5] == "nucleus"  # amend 后 o
        assert out[6] == "nucleus"  # 事件链 new_o 可溯
        assert out[7] == "v30"      # source 审计
        assert out[8] == "active"   # 新版本 = 新事实

    def test_amend_error_surfaces_user_surface(self):
        """审计面错误用户面：retract reason 空 / amend 新 o 未注册 fail-fast
        （try/except 可捕获 + 诊断码可辨）。"""
        code = _mini_world_kb_code(
            "try:\n"
            '    kb.retract(f1, "  ")\n'
            "    print('no-error-wrong')\n"
            "except Exception as e:\n"
            "    print(e.message)\n"
            "try:\n"
            '    kb.amend_fact(f1, "quark", "r")\n'
            "    print('no-error-wrong')\n"
            "except Exception as e:\n"
            "    print(e.message)\n"
            "print('parent-alive')\n"
        )
        out = run_ibci(code)
        joined = "\n".join(out)
        assert "no-error-wrong" not in out
        assert "KNW_REASON_EMPTY" in joined
        assert "KNW_VOCAB_UNREGISTERED" in joined
        assert out[-1] == "parent-alive"
