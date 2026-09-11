"""差分语料契约（数据面执行——差分机制退场后的权威断言面）。

差分 harness 数据面执行差分（Rust vs Python 参考）退场后，语料探针的
期望输出冻结为本契约（行为层可观察断言面——契约权威化：输出 = 契约，
不再经 Python 参考逐条对拍）。前端层差分（lexer/parser/UID/符号表）保留。
"""

import pytest

from tests.behavior.helpers import run


# 差分语料契约：探针名 → (源码, 期望输出[冻结自 Python 参考——同 Rust 数据面])
_CORPUS_CONTRACTS = {
    "arithmetic_basic": (
        'print(1 + 2 * 3)\nprint(10 / 4)\nprint(7 % 3)\n',
        ['7', '2', '1'],
    ),
    "arithmetic_loop": (
        'total = 0\nfor i in range(1, 11):\n    total = total + i\nprint(total)\n',
        ['55'],
    ),
    "arithmetic_neg": (
        'print(-5 + 3)\nprint(2 ** 3)\n',
        ['-2', '8'],
    ),
    "aug_assign": (
        'x = 0\nx += 1\nx += 2\nprint(x)\ny = 10\ny -= 3\nprint(y)\n',
        ['3', '7'],
    ),
    "chained_cmp": (
        'a = 1\nb = 2\nc = 3\nprint(a < b < c)\nprint(1 < 2 < 3)\n',
        ['True', 'True'],
    ),
    "closure_capture": (
        'func make(int k) -> int:\n    a = k * 2\n    func get() -> int:\n        return a\n    return get()\nprint(make(21))\n',
        ['42'],
    ),
    "closure_top_global": (
        'a = 100\nfunc get_a() -> int:\n    return a\nprint(get_a())\n',
        ['100'],
    ),
    "control_for_break": (
        'for i in range(10):\n    if i == 3:\n        break\n    print(i)\n',
        ['0', '1', '2'],
    ),
    "control_if": (
        "x = 7\nif x > 5:\n    print('big')\nelif x > 0:\n    print('small')\nelse:\n    print('neg')\n",
        ['big'],
    ),
    "control_nested": (
        'for i in range(3):\n    for j in range(2):\n        print(i * 10 + j)\n',
        ['0', '1', '10', '11', '20', '21'],
    ),
    "control_while": (
        'i = 0\ns = 0\nwhile i < 5:\n    s = s + i\n    i = i + 1\nprint(s)\n',
        ['10'],
    ),
    "dict_methods": (
        "d = {'a': 1, 'b': 2}\nprint(d.get('a'))\nprint(d.get('z', 0))\nprint(d.keys())\n",
        ['1', '0', '[a, b]'],
    ),
    "dict_ops": (
        "d = {'a': 1, 'b': 2}\nd['c'] = 3\nprint(d['a'])\nprint(d)\n",
        ['1', '{"a": 1, "b": 2, "c": 3}'],
    ),
    "expr_bool": (
        'print(True and False)\nprint(True or False)\nprint(not True)\n',
        ['False', 'True', 'False'],
    ),
    "expr_ternary": (
        "x = 7\ny = 'big' if x > 5 else 'small'\nprint(y)\n",
        ['big'],
    ),
    "from_import": (
        'from meta import quote\nq = quote("1 + 2")\nprint(q.source)\n',
        ['1 + 2'],
    ),
    "function_basic": (
        'func add(int a, int b) -> int:\n    return a + b\nprint(add(2, 3))\nprint(add(add(1, 2), 4))\n',
        ['5', '7'],
    ),
    "function_nested": (
        'func outer(int n) -> int:\n    func inner(int m) -> int:\n        return m + 1\n    return inner(n)\nprint(outer(41))\n',
        ['42'],
    ),
    "function_recursion": (
        'func fact(int n) -> int:\n    if n <= 1:\n        return 1\n    return n * fact(n - 1)\nprint(fact(5))\n',
        ['120'],
    ),
    "kb_contradicts": (
        'kb = knowledge()\nkb.register_world("modern", "现代物理世界", 3)\nkb.register_relation("composed_of", "组成关系", False, False)\nkb.register_word("atom", "原子", False, [], {})\nkb.register_word("proton", "质子", False, [], {})\nkb.register_word("electron", "电子", False, [], {})\nkb.add_fact("modern", "atom", "composed_of", "proton", "v30", "active")\nprint(kb.contradicts(\'atom\', \'composed_of\', \'electron\'))\n',
        ['True'],
    ),
    "kb_fact_lookup": (
        'kb = knowledge()\nkb.register_world("modern", "现代物理世界", 3)\nkb.register_relation("composed_of", "组成关系", False, False)\nkb.register_word("atom", "原子", False, [], {})\nkb.register_word("proton", "质子", False, [], {})\nkb.add_fact("modern", "atom", "composed_of", "proton", "v30", "active")\nprint(kb.exists(\'modern\', \'atom\', \'composed_of\', \'proton\'))\nprint(kb.lookup_pair(\'atom\', \'composed_of\'))\n',
        ['True', '[{"id": 1, "world": modern, "s": atom, "r": composed_of, "o": proton, "source": v30, "status": active, "events": [{"seq": 1, "kind": add, "reason": , "new_o": None}]}]'],
    ),
    "kb_world_vocab": (
        'kb = knowledge()\nkb.register_world("modern", "现代物理世界", 3)\nkb.register_relation("composed_of", "组成关系", False, False)\nkb.register_word("atom", "原子", False, [], {})\nkb.register_word("proton", "质子", False, [], {})\nprint(kb.worlds())\nprint(kb.words())\n',
        ['[modern]', '[atom, proton]'],
    ),
    "list_methods": (
        'xs = [1, 2, 3]\nxs.append(4)\nprint(xs.index(3))\nxs.pop()\nprint(xs)\n',
        ['2', '[1, 2, 3]'],
    ),
    "list_more": (
        'a = [1, 2]\nb = [3, 4]\nprint(a + b)\nprint(a[0] * 2)\n',
        ['[1, 2, 3, 4]', '2'],
    ),
    "list_ops": (
        'xs = [1, 2, 3]\nxs.append(4)\nprint(xs)\nprint(xs[1])\nprint(len(xs))\n',
        ['[1, 2, 3, 4]', '2', '4'],
    ),
    "list_slice": (
        'xs = [1, 2, 3, 4, 5]\nprint(xs[1:3])\nprint(xs[:2])\n',
        ['[2, 3]', '[1, 2]'],
    ),
    "nested_container": (
        "data = {'xs': [1, 2], 'ys': [3, 4]}\nprint(data['xs'][1])\nprint(data['ys'][0] + 10)\n",
        ['2', '13'],
    ),
    "quoted_eval_expr": (
        'import meta\nx = meta.eval(meta.quote("3 * 4"))\nprint(x + 1)\n',
        ['13'],
    ),
    "quoted_eval_value": (
        'import meta\nprint(meta.eval(meta.quote("1 + 2")))\n',
        ['3'],
    ),
    "quoted_source": (
        'import meta\nq = meta.quote("21 * 2")\nprint(q.source)\n',
        ['21 * 2'],
    ),
    "str_methods": (
        "s = 'a,b,c'\nprint(s.split(','))\nprint(s.find('b'))\n",
        ['[a, b, c]', '2'],
    ),
    "string_methods": (
        "s = '  hello  '\nprint(s.strip())\nprint(s.upper())\nprint(s.lower())\n",
        ['hello', '  HELLO  ', '  hello  '],
    ),
    "string_ops": (
        "s = 'hello'\nprint(s + ' world')\nprint(len(s))\n",
        ['hello world', '5'],
    ),
    "tuple_basic": (
        't = (1, 2, 3)\nprint(t[0])\nprint(len(t))\n',
        ['1', '3'],
    ),
}


@pytest.mark.parametrize("name", sorted(_CORPUS_CONTRACTS))
def test_corpus_contract(name):
    """差分语料探针 = 冻结输出契约（Rust 数据面执行——权威断言面）。"""
    code, expected = _CORPUS_CONTRACTS[name]
    assert run(code) == expected, f"语料契约 {name} 输出偏离"
