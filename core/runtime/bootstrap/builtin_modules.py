# -*- coding: utf-8 -*-
"""
宿主侧构造期内置契约注册。

职责：内核原生 5（ai/ihost/meta/idbg/isys/iruntime）+ net + file 的 TypeDef 字面量 +
Engine 构造期注册——这些契约面含构造期 lifecycle / LLM 通道 / 引擎内部服务 / 内核值类型
导出，bind 机制无对应表达面，维持宿主侧字面量（契约单一权威源）。

**工具 4（math/json/time/schema）契约已迁移**：契约单一权威源 = IBCI bind 声明契约源
（``contracts/<module>.ibci``），经 ``kernel_contracts.load_tool_contracts`` 于构造期
处理（自举方向：内核以自身语言表达工具契约）；本文件不再承载其字面量。

用户侧扩展唯一边 = 宿主绑定 bind（不保留 Python 侧 _spec.py 磁盘发现通道）。

说明：
- 字面量原由一次性生成脚本经旧 discovery 路径产出（结构等价，防手写漂移）；该脚本
  重构后已删除（用后即删，决策沉入 WORKLOG/架构文档）。
- file（逻辑名 ``fs``）的 spec 自 core/engine.py 挪入（保留 mutating/param_descriptors/
  exported_types 语义字段）；world_model（KB 磁盘面）同 file 为内核模块（无物理包，
  实现 core.runtime.modules.world_model_impl.WorldModelLib）。
- net 显式 provenance=USER_DEFINED（非 KERNEL_NATIVE，host_interface 覆盖保护不适用）；
  内核原生 7 + file + world_model = KERNEL_NATIVE；全部内置模块 visibility=IMPORT_GATED
  （须显式 import 才可用）。

"""
import contextlib
import importlib
import sys
from typing import Any, Dict

from core.base.enums import Provenance, Visibility
from core.base.path import IbPath
from core.kernel.spec import (
    TypeDef,
    TypeKind,
    MemberSpec,
    MethodMemberSpec,
    ParamDescriptor,
    TypeRef,
)
from core.runtime.path import InstallPaths


# 内核原生模块（logical_name -> 物理包名）；KERNEL_NATIVE provenance + HostInterface 覆盖保护。
KERNEL_NATIVE_MODULES: Dict[str, str] = {
    "ai": "ibci_ai",
    "ihost": "ibci_ihost",
    "meta": "ibci_meta",
    "selfref": "ibci_selfref",
    "idbg": "ibci_idbg",
    "isys": "ibci_isys",
    "iruntime": "ibci_iruntime",
}

# 宿主侧构造期注册的全部内置模块（内核原生 7 + net）；file 无物理包（实现为
# core.runtime.modules.fs_impl.FileLib）。工具 4（math/json/time/schema）经契约源
# 自举注册（kernel_contracts.load_tool_contracts），不在此表。
BUILTIN_MODULES: Dict[str, str] = dict(KERNEL_NATIVE_MODULES)
BUILTIN_MODULES.update({
    "net": "ibci_net",
})


_SPEC_AI = TypeDef(name="ai", kind="module", provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.IMPORT_GATED, members={
        "set_config": MethodMemberSpec(name="set_config", kind="method", type_ref=TypeRef.of("void"), param_types=[
                TypeRef.of("str"),
                TypeRef.of("str"),
                TypeRef.of("str")
            ], return_type=TypeRef.of("void"), param_descriptors=[
                ParamDescriptor(name="url", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
                ParamDescriptor(name="key", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
                ParamDescriptor(name="model", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
                ParamDescriptor(name="timeout", kind="KEYWORD_ONLY", type_ref=TypeRef.of("any"), has_default=True, default_value=None),
                ParamDescriptor(name="retry", kind="KEYWORD_ONLY", type_ref=TypeRef.of("any"), has_default=True, default_value=None),
                ParamDescriptor(name="max_tokens", kind="KEYWORD_ONLY", type_ref=TypeRef.of("any"), has_default=True, default_value=None),
                ParamDescriptor(name="temperature", kind="KEYWORD_ONLY", type_ref=TypeRef.of("any"), has_default=True, default_value=None),
                ParamDescriptor(name="top_p", kind="KEYWORD_ONLY", type_ref=TypeRef.of("any"), has_default=True, default_value=None),
                ParamDescriptor(name="top_k", kind="KEYWORD_ONLY", type_ref=TypeRef.of("any"), has_default=True, default_value=None),
                ParamDescriptor(name="seed", kind="KEYWORD_ONLY", type_ref=TypeRef.of("any"), has_default=True, default_value=None),
                ParamDescriptor(name="extra_body", kind="KEYWORD_ONLY", type_ref=TypeRef.of("any"), has_default=True, default_value=None)
            ]),
        "load_config": MethodMemberSpec(name="load_config", kind="method", type_ref=TypeRef.of("void"), param_types=[
                TypeRef.of("str")
            ], return_type=TypeRef.of("void"), param_descriptors=[
                ParamDescriptor(name="path", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str"))
            ]),
        "load_project_config": MethodMemberSpec(name="load_project_config", kind="method", type_ref=TypeRef.of("void"), return_type=TypeRef.of("void")),
        "apply_config": MethodMemberSpec(name="apply_config", kind="method", type_ref=TypeRef.of("void"), param_types=[
                TypeRef.of("dict")
            ], return_type=TypeRef.of("void"), param_descriptors=[
                ParamDescriptor(name="config", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("dict"))
            ]),
        "set_mock_mode": MethodMemberSpec(name="set_mock_mode", kind="method", type_ref=TypeRef.of("void"), param_types=[
                TypeRef.of("bool")
            ], return_type=TypeRef.of("void"), param_descriptors=[
                ParamDescriptor(name="enable", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("bool"), has_default=True, default_value=True)
            ]),
        "register_model": MethodMemberSpec(name="register_model", kind="method", type_ref=TypeRef.of("void"), param_types=[
                TypeRef.of("str"),
                TypeRef.of("str"),
                TypeRef.of("str"),
                TypeRef.of("str")
            ], return_type=TypeRef.of("void"), param_descriptors=[
                ParamDescriptor(name="name", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
                ParamDescriptor(name="url", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
                ParamDescriptor(name="key", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
                ParamDescriptor(name="model", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
                ParamDescriptor(name="timeout", kind="KEYWORD_ONLY", type_ref=TypeRef.of("any"), has_default=True, default_value=None),
                ParamDescriptor(name="max_tokens", kind="KEYWORD_ONLY", type_ref=TypeRef.of("any"), has_default=True, default_value=None),
                ParamDescriptor(name="temperature", kind="KEYWORD_ONLY", type_ref=TypeRef.of("any"), has_default=True, default_value=None),
                ParamDescriptor(name="top_p", kind="KEYWORD_ONLY", type_ref=TypeRef.of("any"), has_default=True, default_value=None),
                ParamDescriptor(name="top_k", kind="KEYWORD_ONLY", type_ref=TypeRef.of("any"), has_default=True, default_value=None),
                ParamDescriptor(name="seed", kind="KEYWORD_ONLY", type_ref=TypeRef.of("any"), has_default=True, default_value=None),
                ParamDescriptor(name="extra_body", kind="KEYWORD_ONLY", type_ref=TypeRef.of("any"), has_default=True, default_value=None)
            ]),
        "has_api_key": MethodMemberSpec(name="has_api_key", kind="method", type_ref=TypeRef.of("bool"), return_type=TypeRef.of("bool")),
        "probe_model": MethodMemberSpec(name="probe_model", kind="method", type_ref=TypeRef.of("str"), return_type=TypeRef.of("str")),
        "set_retry": MethodMemberSpec(name="set_retry", kind="method", type_ref=TypeRef.of("void"), param_types=[
                TypeRef.of("int")
            ], return_type=TypeRef.of("void"), param_descriptors=[
                ParamDescriptor(name="count", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("int"))
            ]),
        "get_retry": MethodMemberSpec(name="get_retry", kind="method", type_ref=TypeRef.of("int"), return_type=TypeRef.of("int")),
        "is_auto_intent_injection_enabled": MethodMemberSpec(name="is_auto_intent_injection_enabled", kind="method", type_ref=TypeRef.of("bool"), return_type=TypeRef.of("bool")),
        "set_timeout": MethodMemberSpec(name="set_timeout", kind="method", type_ref=TypeRef.of("void"), param_types=[
                TypeRef.of("float")
            ], return_type=TypeRef.of("void"), param_descriptors=[
                ParamDescriptor(name="seconds", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("float"))
            ]),
        "set_return_type_prompt": MethodMemberSpec(name="set_return_type_prompt", kind="method", type_ref=TypeRef.of("void"), param_types=[
                TypeRef.of("str"),
                TypeRef.of("str")
            ], return_type=TypeRef.of("void"), param_descriptors=[
                ParamDescriptor(name="type_name", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
                ParamDescriptor(name="prompt", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str"))
            ]),
        "get_return_type_prompt": MethodMemberSpec(name="get_return_type_prompt", kind="method", type_ref=TypeRef.of("str"), param_types=[
                TypeRef.of("str")
            ], return_type=TypeRef.of("str"), param_descriptors=[
                ParamDescriptor(name="type_name", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str"))
            ]),
        "get_current_call_info": MethodMemberSpec(name="get_current_call_info", kind="method", type_ref=TypeRef.of("dict"), return_type=TypeRef.of("dict")),
        "run_batch": MethodMemberSpec(name="run_batch", kind="method", type_ref=TypeRef.of("list"), param_types=[
                TypeRef.of("any"),
                TypeRef.of("list")
            ], return_type=TypeRef.of("list"), param_descriptors=[
                ParamDescriptor(name="behavior", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("any")),
                ParamDescriptor(name="items", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("list"))
            ]),
        "set_global_intent": MethodMemberSpec(name="set_global_intent", kind="method", type_ref=TypeRef.of("void"), param_types=[
                TypeRef.of("str")
            ], return_type=TypeRef.of("void"), param_descriptors=[
                ParamDescriptor(name="intent", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str"))
            ]),
        "clear_global_intents": MethodMemberSpec(name="clear_global_intents", kind="method", type_ref=TypeRef.of("void"), return_type=TypeRef.of("void")),
        "remove_global_intent": MethodMemberSpec(name="remove_global_intent", kind="method", type_ref=TypeRef.of("void"), param_types=[
                TypeRef.of("str")
            ], return_type=TypeRef.of("void"), param_descriptors=[
                ParamDescriptor(name="intent", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str"))
            ]),
        "mask": MethodMemberSpec(name="mask", kind="method", type_ref=TypeRef.of("void"), param_types=[
                TypeRef.of("str")
            ], return_type=TypeRef.of("void"), param_descriptors=[
                ParamDescriptor(name="tag_pattern", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str"))
            ]),
        "get_global_intents": MethodMemberSpec(name="get_global_intents", kind="method", type_ref=TypeRef.of("list"), return_type=TypeRef.of("list")),
        "get_current_intent_stack": MethodMemberSpec(name="get_current_intent_stack", kind="method", type_ref=TypeRef.of("list"), return_type=TypeRef.of("list")),
        "stream_call": MethodMemberSpec(name="stream_call", kind="method", type_ref=TypeRef.of("any"), param_types=[
                TypeRef.of("any")
            ], return_type=TypeRef.of("any"), param_descriptors=[
                ParamDescriptor(name="target", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("any"))
            ]),
        "stream_channel": MethodMemberSpec(name="stream_channel", kind="method", type_ref=TypeRef.of("chan"), param_types=[
                TypeRef.of("any")
            ], return_type=TypeRef.of("chan"), param_descriptors=[
                ParamDescriptor(name="target", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("any"))
            ]),
        "set_provider": MethodMemberSpec(name="set_provider", kind="method", type_ref=TypeRef.of("void"), param_types=[
                TypeRef.of("any")
            ], return_type=TypeRef.of("void"), param_descriptors=[
                ParamDescriptor(name="provider", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("any"))
            ]),
        # embedding 服务面（词嵌入一等能力；配置单源 = api_config kind: "embedding"）
        "embed": MethodMemberSpec(name="embed", kind="method", type_ref=TypeRef.of("any"), param_types=[
                TypeRef.of("any")
            ], return_type=TypeRef.of("any"), param_descriptors=[
                ParamDescriptor(name="texts", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("any")),
                ParamDescriptor(name="model", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("any"), has_default=True, default_value=None),
                ParamDescriptor(name="dimensions", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("any"), has_default=True, default_value=None),
                ParamDescriptor(name="side", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("any"), has_default=True, default_value="doc"),
                ParamDescriptor(name="instruct", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("any"), has_default=True, default_value=None)
            ]),
        "set_embedding_config": MethodMemberSpec(name="set_embedding_config", kind="method", type_ref=TypeRef.of("void"), param_types=[
                TypeRef.of("str"),
                TypeRef.of("str"),
                TypeRef.of("str")
            ], return_type=TypeRef.of("void"), param_descriptors=[
                ParamDescriptor(name="url", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
                ParamDescriptor(name="key", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
                ParamDescriptor(name="model", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str"))
            ]),
        "register_embedding_model": MethodMemberSpec(name="register_embedding_model", kind="method", type_ref=TypeRef.of("void"), param_types=[
                TypeRef.of("str"),
                TypeRef.of("str"),
                TypeRef.of("str"),
                TypeRef.of("str")
            ], return_type=TypeRef.of("void"), param_descriptors=[
                ParamDescriptor(name="name", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
                ParamDescriptor(name="url", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
                ParamDescriptor(name="key", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
                ParamDescriptor(name="model", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str"))
            ]),
        "set_embedding_model": MethodMemberSpec(name="set_embedding_model", kind="method", type_ref=TypeRef.of("void"), param_types=[
                TypeRef.of("str")
            ], return_type=TypeRef.of("void"), param_descriptors=[
                ParamDescriptor(name="name", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str"))
            ]),
        "set_embedding_mock": MethodMemberSpec(name="set_embedding_mock", kind="method", type_ref=TypeRef.of("void"), return_type=TypeRef.of("void"), param_descriptors=[
            ParamDescriptor(name="enable", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("bool"), has_default=True, default_value=True),
            ParamDescriptor(name="dim", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("int"), has_default=True, default_value=128),
            ParamDescriptor(name="seed", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("int"), has_default=True, default_value=0)
        ]),
        "retrieve": MethodMemberSpec(name="retrieve", kind="method", type_ref=TypeRef.of("list"), param_types=[
                TypeRef.of("vector"),
                TypeRef.of("list"),
                TypeRef.of("int")
            ], return_type=TypeRef.of("list"), param_descriptors=[
                ParamDescriptor(name="query", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("vector")),
                ParamDescriptor(name="corpus", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("list")),
                ParamDescriptor(name="k", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("int"))
            ], unbox_args=False),
        "recall": MethodMemberSpec(name="recall", kind="method", type_ref=TypeRef.of("list"), param_types=[
                TypeRef.of("str"),
                TypeRef.of("list"),
            ], return_type=TypeRef.of("list"), param_descriptors=[
                ParamDescriptor(name="query", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
                ParamDescriptor(name="corpus", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("list")),
                ParamDescriptor(name="k", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("int")),
                ParamDescriptor(name="instruct", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("any"), has_default=True, default_value=""),
                ParamDescriptor(name="dimensions", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("any"), has_default=True, default_value=None)
            ], unbox_args=False),
        "recall_stats": MethodMemberSpec(name="recall_stats", kind="method", type_ref=TypeRef.of("dict"), return_type=TypeRef.of("dict")),
        "get_embedding_call_info": MethodMemberSpec(name="get_embedding_call_info", kind="method", type_ref=TypeRef.of("dict"), return_type=TypeRef.of("dict")),
        "probe_embedding": MethodMemberSpec(name="probe_embedding", kind="method", type_ref=TypeRef.of("str"), return_type=TypeRef.of("str")),
    })


_SPEC_IHOST = TypeDef(name="ihost", kind="module", provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.IMPORT_GATED, members={
        "save_state": MethodMemberSpec(name="save_state", kind="method", type_ref=TypeRef.of("void"), param_types=[
                TypeRef.of("str")
            ], return_type=TypeRef.of("void"), param_descriptors=[
                ParamDescriptor(name="path", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str"))
            ]),
        "load_state": MethodMemberSpec(name="load_state", kind="method", type_ref=TypeRef.of("void"), param_types=[
                TypeRef.of("str")
            ], return_type=TypeRef.of("void"), param_descriptors=[
                ParamDescriptor(name="path", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str"))
            ]),
        "run_isolated": MethodMemberSpec(name="run_isolated", kind="method", type_ref=TypeRef.of("dict"), param_types=[
                TypeRef.of("str"),
                TypeRef.of("dict")
            ], return_type=TypeRef.of("dict"), param_descriptors=[
                ParamDescriptor(name="path", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
                ParamDescriptor(name="policy", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("dict"))
            ]),
        "spawn_isolated": MethodMemberSpec(name="spawn_isolated", kind="method", type_ref=TypeRef.of("str"), param_types=[
                TypeRef.of("str"),
                TypeRef.of("dict")
            ], return_type=TypeRef.of("str"), param_descriptors=[
                ParamDescriptor(name="path", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
                ParamDescriptor(name="policy", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("dict"))
            ]),
        "collect": MethodMemberSpec(name="collect", kind="method", type_ref=TypeRef.of("dict"), param_types=[
                TypeRef.of("str")
            ], return_type=TypeRef.of("dict"), param_descriptors=[
                ParamDescriptor(name="handle", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str"))
            ]),
        "run_file": MethodMemberSpec(name="run_file", kind="method", type_ref=TypeRef.of("run_result"), param_types=[
                TypeRef.of("str"),
                TypeRef.of("dict")
            ], return_type=TypeRef.of("run_result"), param_descriptors=[
                ParamDescriptor(name="path", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
                ParamDescriptor(name="policy", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("dict"))
            ]),
        "run_code": MethodMemberSpec(name="run_code", kind="method", type_ref=TypeRef.of("run_result"), param_types=[
                TypeRef.of("str"),
                TypeRef.of("dict")
            ], return_type=TypeRef.of("run_result"), param_descriptors=[
                ParamDescriptor(name="code", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
                ParamDescriptor(name="policy", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("dict"))
            ]),
        "get_source": MethodMemberSpec(name="get_source", kind="method", type_ref=TypeRef.of("str"), return_type=TypeRef.of("str")),
        "getenv": MethodMemberSpec(name="getenv", kind="method", type_ref=TypeRef.of("str"), param_types=[
                TypeRef.of("str")
            ], return_type=TypeRef.of("str"), param_descriptors=[
                ParamDescriptor(name="key", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str"))
            ]),
    })


_SPEC_META = TypeDef(name="meta", kind="module", provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.IMPORT_GATED, members={
        # 编译门原语：代码字符串进程内 compile-only 静态校验（不执行）+ 返回编译产物
        # 值（行为作值 TYPE-1）。失败抛 CompilerError（ibci 源定位：合成 entry 标记
        # + line/column），成功返回摘要 dict。
        "compile": MethodMemberSpec(name="compile", kind="method", type_ref=TypeRef.of("dict"), param_types=[
                TypeRef.of("str")
            ], return_type=TypeRef.of("dict"), param_descriptors=[
                ParamDescriptor(name="code", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str"))
            ]),
        # quote/eval 数据/命令二元：quote = 表达式源串经编译门验证冻结为 quoted
        # 值（数据形态；自包含性由构造成立，fresh scope 门）；eval = 执行 quoted
        # 值取回表达式**值**（命令形态；值通道非 stdout；fail-fast）。入参类型
        # quoted 静态强制（str 直调 = 编译期类型错）。
        "quote": MethodMemberSpec(name="quote", kind="method", type_ref=TypeRef.of("quoted"), param_types=[
                TypeRef.of("str")
            ], return_type=TypeRef.of("quoted"), param_descriptors=[
                ParamDescriptor(name="source", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str"))
            ]),
        "eval": MethodMemberSpec(name="eval", kind="method", type_ref=TypeRef.of("any"), param_types=[
                TypeRef.of("quoted")
            ], return_type=TypeRef.of("any"), param_descriptors=[
                ParamDescriptor(name="expr", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("quoted"))
            ]),
    })

_SPEC_WORLD_MODEL = TypeDef(
    name="world_model",
    kind=TypeKind.MODULE.value,
    provenance=Provenance.KERNEL_NATIVE,
    visibility=Visibility.IMPORT_GATED,
    members={
        # KB 磁盘面（内容寻址 artifact）：load_kb = 三级验证门（结构/版本/
        # 完整性 hash）后水化为活 KB 值（加载后可查询 + 可增量 add_fact）；
        # save_kb = KB 面序列化写盘，返回 content_hash（钉扎/审计）。
        "load_kb": MethodMemberSpec(
            name="load_kb", kind="method", type_ref=TypeRef.of("knowledge"),
            param_types=[TypeRef.of("str")], return_type=TypeRef.of("knowledge"),
            param_descriptors=[
                ParamDescriptor(name="path", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
            ],
        ),
        "save_kb": MethodMemberSpec(
            name="save_kb", kind="method", type_ref=TypeRef.of("str"),
            param_types=[TypeRef.of("knowledge"), TypeRef.of("str")],
            return_type=TypeRef.of("str"),
            param_descriptors=[
                ParamDescriptor(name="kb", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("knowledge")),
                ParamDescriptor(name="path", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
            ],
        ),
        # 窄模型工件面（内容寻址 artifact；纯推理零训练）：bind_artifact =
        # 三级验证门（结构/版本/完整性 hash）后水化为活 narrow_model 值
        # （推理时 score/topk）；save_artifact = 工件序列化写盘，返回
        # content_hash（钉扎/审计）。
        "bind_artifact": MethodMemberSpec(
            name="bind_artifact", kind="method", type_ref=TypeRef.of("narrow_model"),
            param_types=[TypeRef.of("str")], return_type=TypeRef.of("narrow_model"),
            param_descriptors=[
                ParamDescriptor(name="path", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
            ],
        ),
        "save_artifact": MethodMemberSpec(
            name="save_artifact", kind="method", type_ref=TypeRef.of("str"),
            param_types=[TypeRef.of("narrow_model"), TypeRef.of("str")],
            return_type=TypeRef.of("str"),
            param_descriptors=[
                ParamDescriptor(name="model", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("narrow_model")),
                ParamDescriptor(name="path", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
            ],
        ),
    },
)

_SPEC_SELFREF = TypeDef(name="selfref", kind="module", provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.IMPORT_GATED, members={
        # 自指性体系架构（Phase C）确定性原语——零 LLM（SR-5 结构性保证）。
        # SR-1 自描述：从系统实际结构组装结构化自描述值（非硬编码字符串）。
        "describe": MethodMemberSpec(name="describe", kind="method", type_ref=TypeRef.of("dict"), return_type=TypeRef.of("dict")),
        # SR-3 宪法：系统不变量集（自修改元规则）。
        "constitution": MethodMemberSpec(name="constitution", kind="method", type_ref=TypeRef.of("list"), return_type=TypeRef.of("list")),
        # SR-2 显式生成器：行为模板注册（name + 含 {placeholder} 的代码模板体）。
        "register_template": MethodMemberSpec(name="register_template", kind="method", type_ref=TypeRef.of("void"), param_types=[
                TypeRef.of("str"),
                TypeRef.of("str"),
            ], return_type=TypeRef.of("void"), param_descriptors=[
                ParamDescriptor(name="name", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
                ParamDescriptor(name="body", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str"))
            ]),
        # SR-2：已注册模板名列表。
        "templates": MethodMemberSpec(name="templates", kind="method", type_ref=TypeRef.of("list"), return_type=TypeRef.of("list")),
        # SR-2 确定性组装：模板 + 语义参数 → 合法 ibci 源串。
        "render": MethodMemberSpec(name="render", kind="method", type_ref=TypeRef.of("str"), param_types=[
                TypeRef.of("str"),
                TypeRef.of("dict"),
            ], return_type=TypeRef.of("str"), param_descriptors=[
                ParamDescriptor(name="name", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
                ParamDescriptor(name="params", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("dict"))
            ]),
        # SR-3 验证门：编译 + 执行 + 结果（三关，非仅编译）→ {ok, gate, detail}。
        "verify": MethodMemberSpec(name="verify", kind="method", type_ref=TypeRef.of("dict"), param_types=[
                TypeRef.of("str"),
                TypeRef.of("str"),
                TypeRef.of("str"),
            ], return_type=TypeRef.of("dict"), param_descriptors=[
                ParamDescriptor(name="code", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
                ParamDescriptor(name="test_call", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
                ParamDescriptor(name="expected", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str"))
            ]),
    })

_SPEC_IDBG = TypeDef(name="idbg", kind="module", provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.IMPORT_GATED, members={
        "vars": MethodMemberSpec(name="vars", kind="method", type_ref=TypeRef.of("dict"), return_type=TypeRef.of("dict")),
        "print_vars": MethodMemberSpec(name="print_vars", kind="method", type_ref=TypeRef.of("void"), return_type=TypeRef.of("void")),
        "current_llm": MethodMemberSpec(name="current_llm", kind="method", type_ref=TypeRef.of("dict"), return_type=TypeRef.of("dict")),
        "show_target_prompt": MethodMemberSpec(name="show_target_prompt", kind="method", type_ref=TypeRef.of("void"), return_type=TypeRef.of("void")),
        "show_target_result": MethodMemberSpec(name="show_target_result", kind="method", type_ref=TypeRef.of("void"), return_type=TypeRef.of("void")),
        "show_all": MethodMemberSpec(name="show_all", kind="method", type_ref=TypeRef.of("void"), return_type=TypeRef.of("void")),
        "current_result": MethodMemberSpec(name="current_result", kind="method", type_ref=TypeRef.of("dict"), return_type=TypeRef.of("dict")),
        "retry_stack": MethodMemberSpec(name="retry_stack", kind="method", type_ref=TypeRef.of("list"), return_type=TypeRef.of("list")),
        "show_retry_stack": MethodMemberSpec(name="show_retry_stack", kind="method", type_ref=TypeRef.of("void"), return_type=TypeRef.of("void")),
        "protection_map": MethodMemberSpec(name="protection_map", kind="method", type_ref=TypeRef.of("dict"), return_type=TypeRef.of("dict")),
        "show_protection_map": MethodMemberSpec(name="show_protection_map", kind="method", type_ref=TypeRef.of("void"), return_type=TypeRef.of("void")),
        "intents": MethodMemberSpec(name="intents", kind="method", type_ref=TypeRef.of("list"), return_type=TypeRef.of("list")),
        "show_environment": MethodMemberSpec(name="show_environment", kind="method", type_ref=TypeRef.of("void"), return_type=TypeRef.of("void")),
        "show_intents": MethodMemberSpec(name="show_intents", kind="method", type_ref=TypeRef.of("void"), return_type=TypeRef.of("void")),
        "runtime": MethodMemberSpec(name="runtime", kind="method", type_ref=TypeRef.of("dict"), return_type=TypeRef.of("dict")),
        "show_runtime": MethodMemberSpec(name="show_runtime", kind="method", type_ref=TypeRef.of("void"), return_type=TypeRef.of("void")),
        "fields": MethodMemberSpec(name="fields", kind="method", type_ref=TypeRef.of("dict"), param_types=[
                TypeRef.of("any")
            ], return_type=TypeRef.of("dict"), param_descriptors=[
                ParamDescriptor(name="obj", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("any"))
            ]),
    })


_SPEC_ISYS = TypeDef(name="isys", kind="module", provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.IMPORT_GATED, members={
        "entry_path": MethodMemberSpec(name="entry_path", kind="method", type_ref=TypeRef.of("str"), return_type=TypeRef.of("str")),
        "entry_dir": MethodMemberSpec(name="entry_dir", kind="method", type_ref=TypeRef.of("str"), return_type=TypeRef.of("str")),
        "project_root": MethodMemberSpec(name="project_root", kind="method", type_ref=TypeRef.of("str"), return_type=TypeRef.of("str")),
        "is_sandboxed": MethodMemberSpec(name="is_sandboxed", kind="method", type_ref=TypeRef.of("bool"), return_type=TypeRef.of("bool")),
        "request_external_access": MethodMemberSpec(name="request_external_access", kind="method", type_ref=TypeRef.of("void"), return_type=TypeRef.of("void")),
    })


_SPEC_IRUNTIME = TypeDef(name="iruntime", kind="module", provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.IMPORT_GATED, members={
        "snapshot": MethodMemberSpec(name="snapshot", kind="method", type_ref=TypeRef.of("dict"), return_type=TypeRef.of("dict")),
        "subscribe": MethodMemberSpec(name="subscribe", kind="method", type_ref=TypeRef.of("subscriber"), return_type=TypeRef.of("subscriber")),
        "configure": MethodMemberSpec(name="configure", kind="method", type_ref=TypeRef.of("dict"), param_types=[
                TypeRef.of("any")
            ], return_type=TypeRef.of("dict"), param_descriptors=[
                ParamDescriptor(name="kwargs", kind="VAR_KEYWORD", type_ref=TypeRef.of("any"))
            ]),
        "get_config": MethodMemberSpec(name="get_config", kind="method", type_ref=TypeRef.of("dict"), return_type=TypeRef.of("dict")),
    })


_SPEC_NET = TypeDef(name="net", kind="module", provenance=Provenance.USER_DEFINED, visibility=Visibility.IMPORT_GATED, members={
        "set_timeout": MethodMemberSpec(name="set_timeout", kind="method", type_ref=TypeRef.of("void"), param_types=[
                TypeRef.of("float")
            ], return_type=TypeRef.of("void"), param_descriptors=[
                ParamDescriptor(name="seconds", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("float"))
            ]),
        "set_default_headers": MethodMemberSpec(name="set_default_headers", kind="method", type_ref=TypeRef.of("void"), param_types=[
                TypeRef.of("dict")
            ], return_type=TypeRef.of("void"), param_descriptors=[
                ParamDescriptor(name="headers", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("dict"))
            ]),
        "set_bearer_token": MethodMemberSpec(name="set_bearer_token", kind="method", type_ref=TypeRef.of("void"), param_types=[
                TypeRef.of("str")
            ], return_type=TypeRef.of("void"), param_descriptors=[
                ParamDescriptor(name="token", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str"))
            ]),
        "set_basic_auth": MethodMemberSpec(name="set_basic_auth", kind="method", type_ref=TypeRef.of("void"), param_types=[
                TypeRef.of("str"),
                TypeRef.of("str")
            ], return_type=TypeRef.of("void"), param_descriptors=[
                ParamDescriptor(name="username", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
                ParamDescriptor(name="password", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str"))
            ]),
        "clear_auth": MethodMemberSpec(name="clear_auth", kind="method", type_ref=TypeRef.of("void"), return_type=TypeRef.of("void")),
        "get": MethodMemberSpec(name="get", kind="method", type_ref=TypeRef.of("str"), param_types=[
                TypeRef.of("str"),
                TypeRef.of("dict")
            ], return_type=TypeRef.of("str"), param_descriptors=[
                ParamDescriptor(name="url", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
                ParamDescriptor(name="headers", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("dict"), has_default=True, default_value=None)
            ]),
        "get_json": MethodMemberSpec(name="get_json", kind="method", type_ref=TypeRef.of("dict"), param_types=[
                TypeRef.of("str"),
                TypeRef.of("dict")
            ], return_type=TypeRef.of("dict"), param_descriptors=[
                ParamDescriptor(name="url", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
                ParamDescriptor(name="headers", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("dict"), has_default=True, default_value=None)
            ]),
        "post": MethodMemberSpec(name="post", kind="method", type_ref=TypeRef.of("str"), param_types=[
                TypeRef.of("str"),
                TypeRef.of("dict"),
                TypeRef.of("dict")
            ], return_type=TypeRef.of("str"), param_descriptors=[
                ParamDescriptor(name="url", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
                ParamDescriptor(name="body", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("dict")),
                ParamDescriptor(name="headers", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("dict"), has_default=True, default_value=None)
            ]),
        "post_json": MethodMemberSpec(name="post_json", kind="method", type_ref=TypeRef.of("dict"), param_types=[
                TypeRef.of("str"),
                TypeRef.of("dict"),
                TypeRef.of("dict")
            ], return_type=TypeRef.of("dict"), param_descriptors=[
                ParamDescriptor(name="url", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
                ParamDescriptor(name="body", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("dict")),
                ParamDescriptor(name="headers", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("dict"), has_default=True, default_value=None)
            ]),
        "post_form": MethodMemberSpec(name="post_form", kind="method", type_ref=TypeRef.of("str"), param_types=[
                TypeRef.of("str"),
                TypeRef.of("dict"),
                TypeRef.of("dict")
            ], return_type=TypeRef.of("str"), param_descriptors=[
                ParamDescriptor(name="url", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
                ParamDescriptor(name="data", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("dict")),
                ParamDescriptor(name="headers", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("dict"), has_default=True, default_value=None)
            ]),
        "put": MethodMemberSpec(name="put", kind="method", type_ref=TypeRef.of("str"), param_types=[
                TypeRef.of("str"),
                TypeRef.of("dict"),
                TypeRef.of("dict")
            ], return_type=TypeRef.of("str"), param_descriptors=[
                ParamDescriptor(name="url", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
                ParamDescriptor(name="body", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("dict")),
                ParamDescriptor(name="headers", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("dict"), has_default=True, default_value=None)
            ]),
        "delete": MethodMemberSpec(name="delete", kind="method", type_ref=TypeRef.of("str"), param_types=[
                TypeRef.of("str"),
                TypeRef.of("dict")
            ], return_type=TypeRef.of("str"), param_descriptors=[
                ParamDescriptor(name="url", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
                ParamDescriptor(name="headers", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("dict"), has_default=True, default_value=None)
            ]),
        "head": MethodMemberSpec(name="head", kind="method", type_ref=TypeRef.of("dict"), param_types=[
                TypeRef.of("str"),
                TypeRef.of("dict")
            ], return_type=TypeRef.of("dict"), param_descriptors=[
                ParamDescriptor(name="url", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
                ParamDescriptor(name="headers", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("dict"), has_default=True, default_value=None)
            ]),
        "get_status_code": MethodMemberSpec(name="get_status_code", kind="method", type_ref=TypeRef.of("int"), param_types=[
                TypeRef.of("str")
            ], return_type=TypeRef.of("int"), param_descriptors=[
                ParamDescriptor(name="url", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str"))
            ]),
    })


_SPEC_PLUGINS = TypeDef(name="plugins", kind="module", provenance=Provenance.KERNEL_NATIVE,
                          visibility=Visibility.IMPORT_GATED, members={
    "load": MethodMemberSpec(name="load", kind="method", type_ref=TypeRef.of("int"),
        param_types=[TypeRef.of("str")], return_type=TypeRef.of("int"),
        param_descriptors=[
            ParamDescriptor(name="path", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
        ]),
    "call": MethodMemberSpec(name="call", kind="method", type_ref=TypeRef.of("any"),
        param_types=[TypeRef.of("str"), TypeRef.of("any")], return_type=TypeRef.of("any"),
        param_descriptors=[
            ParamDescriptor(name="name", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
            ParamDescriptor(name="args", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("any")),
        ]),
})

_SPEC_COMPUTE = TypeDef(name="compute_engine", kind="module", provenance=Provenance.KERNEL_NATIVE,
                        visibility=Visibility.IMPORT_GATED, members={
    "register_engine": MethodMemberSpec(name="register_engine", kind="method", type_ref=TypeRef.of("void"),
        param_types=[TypeRef.of("str"), TypeRef.of("any")], return_type=TypeRef.of("void"),
        param_descriptors=[
            ParamDescriptor(name="name", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
            ParamDescriptor(name="engine", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("any")),
        ]),
    "run": MethodMemberSpec(name="run", kind="method", type_ref=TypeRef.of("any"),
        param_types=[TypeRef.of("str"), TypeRef.of("any"), TypeRef.of("any")],
        return_type=TypeRef.of("any"),
        param_descriptors=[
            ParamDescriptor(name="op", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
            ParamDescriptor(name="operands", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("any")),
            ParamDescriptor(name="engine", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("any"),
                            has_default=True, default_value=None),
        ]),
})

BUILTIN_MODULE_SPECS: Dict[str, TypeDef] = {
    "ai": _SPEC_AI,
    "ihost": _SPEC_IHOST,
    "meta": _SPEC_META,
    "selfref": _SPEC_SELFREF,
    "idbg": _SPEC_IDBG,
    "isys": _SPEC_ISYS,
    "iruntime": _SPEC_IRUNTIME,
    "net": _SPEC_NET,
    "world_model": _SPEC_WORLD_MODEL,
    "compute_engine": _SPEC_COMPUTE,
    "plugins": _SPEC_PLUGINS,
}


@contextlib.contextmanager
def modules_path_guard():
    """install 模块目录（ibci_modules 包的父目录）的 sys.path 守卫（退出即还原）。

    内核原生 / net 的工厂加载（_load_implementation）与工具契约自举
    （kernel_contracts）共用本单一守卫；导入目标字符串由调用方按自身语义提供
    （包名 vs 契约源声明的完整模块路径）。
    """
    modules_dir = InstallPaths.modules_dir().to_native()
    parent_dir = IbPath.from_native(modules_dir).parent
    if parent_dir is None:
        raise RuntimeError(f"Cannot determine parent of modules_dir: {modules_dir}")
    parent_native = parent_dir.to_native()
    added = False
    if parent_native not in sys.path:
        sys.path.insert(0, parent_native)
        added = True
    try:
        yield
    finally:
        if added and parent_native in sys.path:
            sys.path.remove(parent_native)


def _load_implementation(package_name: str) -> Any:
    """加载内置模块的实现包并调用 create_implementation() 工厂。"""
    with modules_path_guard():
        mod = importlib.import_module(f"ibci_modules.{package_name}")
    factory = getattr(mod, "create_implementation", None)
    if factory is None:
        raise RuntimeError(f"Builtin package {package_name} has no create_implementation")
    return factory()


def register_builtin_modules(host_interface: "HostInterface") -> None:
    """在 HostInterface 中预注册宿主侧构造期内置模块（构造期；内核原生 + net）。

    KERNEL_NATIVE provenance 的模块经 register_module 内建机制自动 reserve
    （HostInterface.register_module：is_kernel_native_meta 时加入 _kernel_native_names），
    file/world_model 同此；net 为 USER_DEFINED provenance，不参与覆盖保护。
    工具 4（math/json/time/schema）经契约源自举注册（kernel_contracts.load_tool_contracts）。
    """
    from core.kernel.host_interface import HostInterface

    for logical_name, package_name in BUILTIN_MODULES.items():
        spec = BUILTIN_MODULE_SPECS[logical_name]
        implementation = _load_implementation(package_name)
        host_interface.register_module(
            logical_name,
            implementation,
            metadata=spec,
            discovery_name=package_name,
        )

    # file：实现为内核模块（无物理包），spec 移动自 engine.py（保留语义字段）。
    from core.runtime.modules.fs_impl import FileLib
    host_interface.register_module(
        "fs",
        FileLib(),
        metadata=BUILTIN_MODULE_SPECS["fs"],
    )

    # world_model：KB 磁盘面（内容寻址 artifact），实现为内核模块（无物理包）。
    from core.runtime.modules.world_model_impl import WorldModelLib
    host_interface.register_module(
        "world_model",
        WorldModelLib(),
        metadata=BUILTIN_MODULE_SPECS["world_model"],
    )

    # compute：计算编排网关（R5-2——引擎注册/调度/Tensor 缓冲交换；numpy 引擎
    # 参考实现；内核不做 SIMD）。
    from core.runtime.modules.compute_impl import ComputeLib
    host_interface.register_module(
        "compute_engine",
        ComputeLib(),
        metadata=BUILTIN_MODULE_SPECS["compute_engine"],
    )

    # plugins：Rust 插件网关（R6 ④层——外部 Rust 插件加载/调用，内核 GIL-free）
    from core.runtime.modules.plugins_impl import PluginsLib
    host_interface.register_module(
        "plugins",
        PluginsLib(),
        metadata=BUILTIN_MODULE_SPECS["plugins"],
    )


def _spec_file() -> TypeDef:
    return TypeDef(
        name="fs",
        kind=TypeKind.MODULE.value,
        provenance=Provenance.KERNEL_NATIVE,
        visibility=Visibility.IMPORT_GATED,
        # `import fs` also gates the disk-backed types into scope.
        exported_types=["file_handle", "audio", "image", "video"],
        members={
            "open": MethodMemberSpec(
                name="open", kind="method", type_ref=TypeRef.of("file_handle"),
                param_types=[TypeRef.of("str")], return_type=TypeRef.of("file_handle"),
            ),
            "read": MethodMemberSpec(
                name="read", kind="method", type_ref=TypeRef.of("str"),
                param_types=[TypeRef.of("any")], return_type=TypeRef.of("str"),
            ),
            "read_bytes": MethodMemberSpec(
                name="read_bytes", kind="method", type_ref=TypeRef.generic("list", TypeRef.of("int")),
                param_types=[TypeRef.of("any")], return_type=TypeRef.generic("list", TypeRef.of("int")),
            ),
            "write": MethodMemberSpec(
                name="write", kind="method", type_ref=TypeRef.of("file_handle"), mutating=True,
                param_types=[TypeRef.of("any"), TypeRef.of("any"), TypeRef.of("str")],
                return_type=TypeRef.of("file_handle"),
                param_descriptors=[
                    ParamDescriptor(name="target", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("any")),
                    ParamDescriptor(name="data", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("any")),
                    ParamDescriptor(name="overwrite_flag", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str"), has_default=True, default_value="new"),
                ],
            ),
            "exists": MethodMemberSpec(
                name="exists", kind="method", type_ref=TypeRef.of("bool"),
                param_types=[TypeRef.of("str")], return_type=TypeRef.of("bool"),
            ),
            "remove": MethodMemberSpec(
                name="remove", kind="method", type_ref=TypeRef.of("void"), mutating=True,
                param_types=[TypeRef.of("any")], return_type=TypeRef.of("void"),
            ),
        },
    )


BUILTIN_MODULE_SPECS["fs"] = _spec_file()


__all__ = [
    "KERNEL_NATIVE_MODULES",
    "BUILTIN_MODULES",
    "BUILTIN_MODULE_SPECS",
    "modules_path_guard",
    "register_builtin_modules",
]
