"""差分 harness 语料（种子面）——代表 Rust 内核须与 Python 参考内核对齐的语义面。

每条 = (name, script)：script 为 IBCI 源码，经执行产出确定性数据面（print
输出）。语料覆盖核心语义面（算术/控制流/函数/容器/字符串/KB 世界模型）——
Rust 内核落地后，本 harness 验证双内核对全部语料数据面逐字节等价。

扩展方向（后续批次）：① 现有测试用例语料化（从 tests/ 提取脚本）；② fuzz 种子
（属性生成）。种子面 = 替换安全网的最低覆盖基线。
"""
from __future__ import annotations

from typing import List, Tuple

# 每条 (name, script)——script 经 run_ibci 执行产出数据面（print 行列表）
CORPUS: List[Tuple[str, str]] = [
    # ---- 算术 ----
    ("arithmetic_basic", "print(1 + 2 * 3)\nprint(10 / 4)\nprint(7 % 3)\n"),
    ("arithmetic_loop", "total = 0\nfor i in range(1, 11):\n    total = total + i\nprint(total)\n"),
    ("arithmetic_neg", "print(-5 + 3)\nprint(2 ** 3)\n"),
    # ---- 控制流 ----
    ("control_if", "x = 7\nif x > 5:\n    print('big')\nelif x > 0:\n    print('small')\nelse:\n    print('neg')\n"),
    ("control_for_break", "for i in range(10):\n    if i == 3:\n        break\n    print(i)\n"),
    ("control_nested", "for i in range(3):\n    for j in range(2):\n        print(i * 10 + j)\n"),
    # ---- 函数（IBCI 显式类型：参数 + 返回值注解；用返回值须定型）----
    ("function_basic",
     "func add(int a, int b) -> int:\n    return a + b\nprint(add(2, 3))\nprint(add(add(1, 2), 4))\n"),
    ("function_recursion",
     "func fact(int n) -> int:\n    if n <= 1:\n        return 1\n    return n * fact(n - 1)\nprint(fact(5))\n"),
    # ---- 容器 ----
    ("list_ops", "xs = [1, 2, 3]\nxs.append(4)\nprint(xs)\nprint(xs[1])\nprint(len(xs))\n"),
    ("dict_ops", "d = {'a': 1, 'b': 2}\nd['c'] = 3\nprint(d['a'])\nprint(d)\n"),
    # ---- 字符串 ----
    ("string_ops", "s = 'hello'\nprint(s + ' world')\nprint(len(s))\n"),
    ("string_methods", "s = '  hello  '\nprint(s.strip())\nprint(s.upper())\nprint(s.lower())\n"),
    # ---- 扩展控制流 / 表达式 ----
    ("control_while", "i = 0\ns = 0\nwhile i < 5:\n    s = s + i\n    i = i + 1\nprint(s)\n"),
    ("expr_ternary", "x = 7\ny = 'big' if x > 5 else 'small'\nprint(y)\n"),
    ("expr_bool", "print(True and False)\nprint(True or False)\nprint(not True)\n"),
    # ---- 函数扩展（嵌套）----
    ("function_nested",
     "func outer(int n) -> int:\n    func inner(int m) -> int:\n        return m + 1\n    return inner(n)\nprint(outer(41))\n"),
    ("closure_capture",
     "func make(int k) -> int:\n    a = k * 2\n    func get() -> int:\n        return a\n    return get()\nprint(make(21))\n"),
    ("closure_top_global", "a = 100\nfunc get_a() -> int:\n    return a\nprint(get_a())\n"),
    # ---- 容器扩展 ----
    ("list_more", "a = [1, 2]\nb = [3, 4]\nprint(a + b)\nprint(a[0] * 2)\n"),
    ("list_methods", "xs = [1, 2, 3]\nxs.append(4)\nprint(xs.index(3))\nxs.pop()\nprint(xs)\n"),
    ("dict_methods", "d = {'a': 1, 'b': 2}\nprint(d.get('a'))\nprint(d.get('z', 0))\nprint(d.keys())\n"),
    ("nested_container", "data = {'xs': [1, 2], 'ys': [3, 4]}\nprint(data['xs'][1])\nprint(data['ys'][0] + 10)\n"),
    # ---- 字符串方法扩展 ----
    ("str_methods", "s = 'a,b,c'\nprint(s.split(','))\nprint(s.find('b'))\n"),
    # ---- 链式比较 ----
    ("chained_cmp", "a = 1\nb = 2\nc = 3\nprint(a < b < c)\nprint(1 < 2 < 3)\n"),
    # ---- quoted 值（自指原语：meta.quote 冻结 / meta.eval 取值，host service 桥接）----
    ("quoted_source", 'import meta\nq = meta.quote("21 * 2")\nprint(q.source)\n'),
    ("quoted_eval_value", 'import meta\nprint(meta.eval(meta.quote("1 + 2")))\n'),
    ("quoted_eval_expr", 'import meta\nx = meta.eval(meta.quote("3 * 4"))\nprint(x + 1)\n'),
    # ---- KB 世界模型（主线核心面）----
    ("kb_world_vocab", (
        "kb = knowledge()\n"
        'kb.register_world("modern", "现代物理世界", 3)\n'
        'kb.register_relation("composed_of", "组成关系", False, False)\n'
        'kb.register_word("atom", "原子", False, [], {})\n'
        'kb.register_word("proton", "质子", False, [], {})\n'
        "print(kb.worlds())\n"
        "print(kb.words())\n"
    )),
    ("kb_fact_lookup", (
        "kb = knowledge()\n"
        'kb.register_world("modern", "现代物理世界", 3)\n'
        'kb.register_relation("composed_of", "组成关系", False, False)\n'
        'kb.register_word("atom", "原子", False, [], {})\n'
        'kb.register_word("proton", "质子", False, [], {})\n'
        'kb.add_fact("modern", "atom", "composed_of", "proton", "v30", "active")\n'
        "print(kb.exists('modern', 'atom', 'composed_of', 'proton'))\n"
        "print(kb.lookup_pair('atom', 'composed_of'))\n"
    )),
    ("kb_contradicts", (
        "kb = knowledge()\n"
        'kb.register_world("modern", "现代物理世界", 3)\n'
        'kb.register_relation("composed_of", "组成关系", False, False)\n'
        'kb.register_word("atom", "原子", False, [], {})\n'
        'kb.register_word("proton", "质子", False, [], {})\n'
        'kb.register_word("electron", "电子", False, [], {})\n'
        'kb.add_fact("modern", "atom", "composed_of", "proton", "v30", "active")\n'
        "print(kb.contradicts('atom', 'composed_of', 'electron'))\n"
    )),
]


def names() -> List[str]:
    return [name for name, _ in CORPUS]
