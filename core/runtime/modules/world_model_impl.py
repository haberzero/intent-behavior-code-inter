"""
core/runtime/modules/world_model_impl.py

Kernel-native IBCI ``world_model`` 模块实现：世界模型的**工件磁盘面**——
KB（``knowledge`` 值的 KB 面——facts 事实日志 + vocab 治理词表）+ 推理时窄
模型（``narrow_model`` 值 = 冻结 KG 嵌入工件）两类 artifact 的加载/保存。

- 提供 IBCI 脚本可见的自由函数：``load_kb(path)`` / ``save_kb(kb, path)``
  （KB artifact）+ ``bind_artifact(path)`` / ``save_artifact(model, path)``
  （窄模型 artifact）。
- 磁盘形态 = **内容寻址 artifact**（单 JSON 文件）——JSON 是传输格式，
  运行时模型 = 加载后水化的活值（非文件本体）：
  - KB：``{schema_version, content_hash, facts[], vocab{...}, seq}`` →
    活 ``knowledge`` 值；
  - 窄模型：``{schema_version, content_hash, model_name, architecture, dim,
    entities[], entity_embeddings{}, relations[], relation_embeddings{}}``
    → 活 ``narrow_model`` 值（纯推理零训练，TransE 向量空间模型）。
- ``content_hash`` = canonical 载荷的 sha256 全摘要：**内容即身份**（同内容
  不同排版 = 同 hash；加载时重算比对 = 完整性验证）。
- 所有 FS I/O 经 ``ExecutionContext.resolve_path()`` + ``PermissionManager``
  沙箱校验（同 ``fs`` 模块纪律）。

⚠️ 命名约定：实现文件 ``world_model_impl.py``（不与 IBCI 模块名完全同名）——
沿既有命名纪律（``fs_impl.py`` 先例）。
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Tuple, Union

from core.base.diagnostics.codes import (
    KNW_KB_ARTIFACT_MALFORMED,
    KNW_KB_HASH_MISMATCH,
    KNW_KB_SCHEMA_VERSION,
    NAR_ARTIFACT_MALFORMED,
    NAR_HASH_MISMATCH,
    NAR_SCHEMA_VERSION,
)
from core.base.path import IbPath
from core.kernel.issue import InterpreterError
from core.runtime.objects.file_handle import IbFileHandle
from core.runtime.objects.primitives.knowledge import IbKnowledge
from core.runtime.objects.primitives.narrow_model import IbNarrowModel


#: artifact 格式版本（共享契约；未知版本加载 fail-fast，无自动迁移）。
KB_SCHEMA_VERSION = 1

#: artifact 封套必需键（结构门）。
_KB_ARTIFACT_KEYS = ("schema_version", "content_hash", "facts", "vocab", "seq")

#: 事实记录必需字段（结构门）。
_KB_FACT_KEYS = ("id", "world", "s", "r", "o", "source", "status", "events")

#: 词表三面（结构门）。
_KB_VOCAB_SECTIONS = ("words", "relations", "worlds")


def kb_canonical_payload(
    facts: Dict[str, Dict[str, Any]],
    vocab: Dict[str, Dict[str, Any]],
    seq: int,
) -> str:
    """artifact canonical 载荷（内容身份的单一规范形态）。

    ``{"facts", "seq", "vocab"}`` 经 ``sort_keys`` + 紧凑分隔 + UTF-8 字面序列化
    ——dict 键排序、list 序保持（facts 按 seq 序传入 = 确定性）。同内容不同
    文件排版（缩进/键序）映射到同一 canonical 文本。
    """
    payload = {"facts": facts, "seq": seq, "vocab": vocab}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def kb_content_hash(
    facts: Dict[str, Dict[str, Any]],
    vocab: Dict[str, Dict[str, Any]],
    seq: int,
) -> str:
    """content_hash = canonical 载荷的 sha256 全摘要（64-hex，内容即身份）。"""
    return hashlib.sha256(
        kb_canonical_payload(facts, vocab, seq).encode("utf-8")
    ).hexdigest()


def _kb_facts_list(facts: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """facts 记录按 seq 序展开为 list（artifact 传输面形态）。"""
    return [facts[k] for k in sorted(facts, key=lambda x: int(x))]


#: 窄模型 artifact 格式版本（共享契约；未知版本加载 fail-fast，无自动迁移）。
MODEL_SCHEMA_VERSION = 1

#: 窄模型 artifact 封套必需键（结构门）。
_MODEL_ARTIFACT_KEYS = (
    "schema_version", "content_hash", "model_name", "architecture",
    "dim", "entities", "entity_embeddings", "relations", "relation_embeddings",
)

#: 当前支持的模型架构（推理面按此分派；未知架构 = 结构门 fail-fast）。
_MODEL_SUPPORTED_ARCHITECTURES = ("transe",)


def _is_vector(v: Any, dim: int) -> bool:
    """向量形态验证：list/tuple，长度 = dim，元素全为 int/float（非 bool）。"""
    if not isinstance(v, (list, tuple)) or len(v) != dim:
        return False
    for x in v:
        if isinstance(x, bool) or not isinstance(x, (int, float)):
            return False
    return True


def model_canonical_payload(
    model_name: str,
    architecture: str,
    dim: int,
    entities: List[str],
    entity_embeddings: Dict[str, List[float]],
    relations: List[str],
    relation_embeddings: Dict[str, List[float]],
) -> str:
    """窄模型 artifact canonical 载荷（内容身份的单一规范形态）。

    ``{model_name, architecture, dim, entities, entity_embeddings, relations,
    relation_embeddings}`` 经 ``sort_keys`` + 紧凑分隔 + UTF-8 字面序列化
    ——dict 键排序、list 序保持（entities/relations 固定序 = 确定性）。同内容
    不同文件排版（缩进/键序）映射到同一 canonical 文本。
    """
    payload = {
        "model_name": model_name,
        "architecture": architecture,
        "dim": dim,
        "entities": entities,
        "entity_embeddings": entity_embeddings,
        "relations": relations,
        "relation_embeddings": relation_embeddings,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def model_content_hash(
    model_name: str,
    architecture: str,
    dim: int,
    entities: List[str],
    entity_embeddings: Dict[str, List[float]],
    relations: List[str],
    relation_embeddings: Dict[str, List[float]],
) -> str:
    """content_hash = canonical 载荷的 sha256 全摘要（64-hex，内容即身份）。"""
    return hashlib.sha256(
        model_canonical_payload(
            model_name, architecture, dim, entities,
            entity_embeddings, relations, relation_embeddings,
        ).encode("utf-8")
    ).hexdigest()


class WorldModelLib:
    """``world_model`` 模块的核心实现（kernel-native）。

    不持有 ``capabilities`` 之外的持久状态；磁盘 artifact 是 KB 面的
    内容寻址形态（加载水化为活 KB 值——KB 的可变性归值面，文件只读）。
    """

    def setup(self, capabilities):
        """插件式注入入口（kernel-native 注册时调用）。"""
        self.capabilities = capabilities
        self.permission_manager = capabilities.service_context.permission_manager
        self.registry = capabilities.service_context.registry

    # ------------------------------------------------------------------ #
    # 路径解析（同 fs 纪律：resolve_path 统一入口 + PermissionManager 沙箱）
    # ------------------------------------------------------------------ #

    def _resolve_native_path(
        self, path: Union[str, IbPath, IbFileHandle], operation: str
    ) -> str:
        """统一路径解析 + 沙箱校验，返回原生绝对路径（同 ``fs`` 模块
        ``_resolve_path`` 纪律——越权/不存在错误原样穿透，不吞不降）。"""
        if isinstance(path, IbPath):
            native = path.to_native()
        elif isinstance(path, IbFileHandle):
            native = path.backing.path.to_native()
        else:
            ib_path = self.capabilities.execution_context.resolve_path(path)
            native = ib_path.to_native()
        self.permission_manager.validate_path(native, operation)
        return native

    # ------------------------------------------------------------------ #
    # 结构门（加载/保存共用的 artifact 载荷验证——fail-fast 不静默）
    # ------------------------------------------------------------------ #

    @staticmethod
    def _validate_kb_payload(facts, vocab, seq) -> None:
        """KB 载荷结构验证（违例 = KNW_KB_ARTIFACT_MALFORMED）。

        facts：dict[str, dict]，记录含必填字段且 str 形态、events = list；
        vocab：三面 dict，words 记录含 lexeme/gloss/is_set/entries、relations
        记录含 type/semantics/transitive/multi_valued、worlds 记录含
        name/description/size_rank。
        """
        if not isinstance(facts, dict):
            raise InterpreterError(
                "world_model: artifact facts 节须为 dict（fact_id → 事实记录）。",
                error_code=KNW_KB_ARTIFACT_MALFORMED,
            )
        for fid, rec in facts.items():
            if not isinstance(fid, str) or not isinstance(rec, dict):
                raise InterpreterError(
                    f"world_model: artifact 事实记录 '{fid}' 形态非法"
                    "（fact_id 须 str，记录须 dict）。",
                    error_code=KNW_KB_ARTIFACT_MALFORMED,
                )
            for key in _KB_FACT_KEYS:
                if key not in rec:
                    raise InterpreterError(
                        f"world_model: artifact 事实记录 '{fid}' 缺字段 '{key}'。",
                        error_code=KNW_KB_ARTIFACT_MALFORMED,
                    )
            for key in ("id", "world", "s", "r", "o", "source", "status"):
                if not isinstance(rec[key], str):
                    raise InterpreterError(
                        f"world_model: artifact 事实记录 '{fid}' 字段 '{key}' 须为 str。",
                        error_code=KNW_KB_ARTIFACT_MALFORMED,
                    )
            if not isinstance(rec["events"], list):
                raise InterpreterError(
                    f"world_model: artifact 事实记录 '{fid}' 字段 'events' 须为 list。",
                    error_code=KNW_KB_ARTIFACT_MALFORMED,
                )
        if not isinstance(vocab, dict):
            raise InterpreterError(
                "world_model: artifact vocab 节须为 dict。",
                error_code=KNW_KB_ARTIFACT_MALFORMED,
            )
        for section in _KB_VOCAB_SECTIONS:
            if not isinstance(vocab.get(section), dict):
                raise InterpreterError(
                    f"world_model: artifact vocab 节缺 '{section}' 面（须 dict）。",
                    error_code=KNW_KB_ARTIFACT_MALFORMED,
                )
        for lexeme, rec in vocab["words"].items():
            for key in ("lexeme", "gloss", "is_set", "members", "entries"):
                if key not in rec:
                    raise InterpreterError(
                        f"world_model: artifact 词 '{lexeme}' 记录缺字段 '{key}'。",
                        error_code=KNW_KB_ARTIFACT_MALFORMED,
                    )
        for rtype, rec in vocab["relations"].items():
            for key in ("type", "semantics", "transitive", "multi_valued"):
                if key not in rec:
                    raise InterpreterError(
                        f"world_model: artifact 关系类型 '{rtype}' 记录缺字段 '{key}'。",
                        error_code=KNW_KB_ARTIFACT_MALFORMED,
                    )
        for wname, rec in vocab["worlds"].items():
            for key in ("name", "description", "size_rank"):
                if key not in rec:
                    raise InterpreterError(
                        f"world_model: artifact 世界 '{wname}' 记录缺字段 '{key}'。",
                        error_code=KNW_KB_ARTIFACT_MALFORMED,
                    )
        if not isinstance(seq, int) or isinstance(seq, bool) or seq < 0:
            raise InterpreterError(
                "world_model: artifact seq 须为非负 int。",
                error_code=KNW_KB_ARTIFACT_MALFORMED,
            )

    @staticmethod
    def _validate_model_payload(
        model_name, architecture, dim, entities, entity_embeddings,
        relations, relation_embeddings,
    ) -> None:
        """窄模型载荷结构验证（违例 = NAR_ARTIFACT_MALFORMED）。

        model_name/architecture = str；dim = 正 int；entities/relations =
        str list（候选/关系空间，固定序）；entity_embeddings/relation_
        embeddings = dict（键 == 对应空间集合，值 = dim 维数值向量）。
        """
        if not isinstance(model_name, str) or not model_name:
            raise InterpreterError(
                "world_model: artifact model_name 须为非空 str。",
                error_code=NAR_ARTIFACT_MALFORMED,
            )
        if not isinstance(architecture, str) \
                or architecture not in _MODEL_SUPPORTED_ARCHITECTURES:
            raise InterpreterError(
                f"world_model: artifact architecture {architecture!r} 不受支持"
                f"（当前仅 {list(_MODEL_SUPPORTED_ARCHITECTURES)}）。",
                error_code=NAR_ARTIFACT_MALFORMED,
            )
        if not isinstance(dim, int) or isinstance(dim, bool) or dim < 1:
            raise InterpreterError(
                "world_model: artifact dim 须为正 int。",
                error_code=NAR_ARTIFACT_MALFORMED,
            )
        for label, names, embeddings in (
            ("entities", entities, entity_embeddings),
            ("relations", relations, relation_embeddings),
        ):
            if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
                raise InterpreterError(
                    f"world_model: artifact {label} 须为 str list。",
                    error_code=NAR_ARTIFACT_MALFORMED,
                )
            if not isinstance(embeddings, dict):
                raise InterpreterError(
                    f"world_model: artifact {label}_embeddings 须为 dict。",
                    error_code=NAR_ARTIFACT_MALFORMED,
                )
            if set(embeddings) != set(names):
                raise InterpreterError(
                    f"world_model: artifact {label}_embeddings 键集须与 {label} "
                    "一致（名-嵌入键匹配）。",
                    error_code=NAR_ARTIFACT_MALFORMED,
                )
            for name in names:
                if not _is_vector(embeddings[name], dim):
                    raise InterpreterError(
                        f"world_model: artifact {label} '{name}' 嵌入须为 dim={dim} "
                        "数值向量。",
                        error_code=NAR_ARTIFACT_MALFORMED,
                    )

    # ------------------------------------------------------------------ #
    # 磁盘面（load/save——内容寻址 artifact）
    # ------------------------------------------------------------------ #

    def load_kb(self, path: str) -> IbKnowledge:
        """加载 KB artifact → 三级验证门 → 水化为**活 KB 值**（B1 验收：
        加载后可查询 + 可增量 add_fact，无需重编译）。

        验证门（fail-fast，逐级）：① 结构门（合法 JSON + 封套键齐备 +
        facts/vocab 记录形态）→ ``KNW_KB_ARTIFACT_MALFORMED``；② 版本门
        （schema_version 未知）→ ``KNW_KB_SCHEMA_VERSION``（无自动迁移）；
        ③ 完整性门（canonical 重算 hash ≠ content_hash——篡改/损坏）→
        ``KNW_KB_HASH_MISMATCH``。文件不存在/沙箱拒绝 = 复用 fs 面诊断
        （原样穿透）。
        """
        native_path = self._resolve_native_path(path, operation="read")
        with open(native_path, "r", encoding="utf-8") as f:
            text = f.read()
        # ① 结构门
        try:
            artifact = json.loads(text)
        except (json.JSONDecodeError, ValueError) as e:
            raise InterpreterError(
                f"world_model.load_kb: artifact 非合法 JSON（{e}）。",
                error_code=KNW_KB_ARTIFACT_MALFORMED,
            ) from e
        if not isinstance(artifact, dict):
            raise InterpreterError(
                "world_model.load_kb: artifact 顶层须为对象（dict）。",
                error_code=KNW_KB_ARTIFACT_MALFORMED,
            )
        for key in _KB_ARTIFACT_KEYS:
            if key not in artifact:
                raise InterpreterError(
                    f"world_model.load_kb: artifact 缺封套字段 '{key}'。",
                    error_code=KNW_KB_ARTIFACT_MALFORMED,
                )
        facts = artifact["facts"]
        vocab = artifact["vocab"]
        seq = artifact["seq"]
        if not isinstance(facts, list):
            raise InterpreterError(
                "world_model.load_kb: artifact facts 节须为 list（seq 序记录）。",
                error_code=KNW_KB_ARTIFACT_MALFORMED,
            )
        facts_map: Dict[str, Dict[str, Any]] = {}
        for rec in facts:
            if not isinstance(rec, dict) or "id" not in rec:
                raise InterpreterError(
                    "world_model.load_kb: artifact facts 记录须为含 'id' 的对象。",
                    error_code=KNW_KB_ARTIFACT_MALFORMED,
                )
            facts_map[rec["id"]] = rec
        self._validate_kb_payload(facts_map, vocab, seq)
        # ② 版本门
        version = artifact["schema_version"]
        if version != KB_SCHEMA_VERSION:
            raise InterpreterError(
                f"world_model.load_kb: 未知 schema_version {version!r}"
                f"（本版本仅支持 {KB_SCHEMA_VERSION}；无自动迁移）。",
                error_code=KNW_KB_SCHEMA_VERSION,
            )
        # ③ 完整性门（内容寻址：canonical 重算比对）
        expected = kb_content_hash(facts_map, vocab, seq)
        if expected != artifact["content_hash"]:
            raise InterpreterError(
                "world_model.load_kb: content_hash 验证失败"
                f"（期望 {expected}，artifact 载 {artifact['content_hash']}）"
                "——数据损坏或被篡改。",
                error_code=KNW_KB_HASH_MISMATCH,
            )
        # 水化：活 KB 值（entries 面空——artifact 只辖 KB 面；索引经构造
        # 入口从事实日志确定性重建，派生面纪律）
        cls = self.registry.get_class("knowledge")
        return IbKnowledge(
            cls,
            payload={"entries": {}, "seq": seq, "facts": facts_map, "vocab": vocab},
        )

    def save_kb(self, kb: Dict[str, Any], path: str) -> str:
        """序列化 KB 面为 artifact 写盘，返回 ``content_hash``（钉扎/审计面：
        调用方可经 hash 比对验证落盘内容）。

        ``kb`` 参数经调用边界拆箱到达 = 值快照（``to_native`` 三面 dict）；
        保存只取 KB 面三键（facts/vocab/seq）——entries 面不入 artifact
        （其持久化通道 = ihost.save_state 全状态面，两通道各辖其面）。
        文件布局 = 传输（pretty JSON）；身份 = canonical（紧凑规范形态）。
        """
        if not isinstance(kb, dict):
            raise InterpreterError(
                "world_model.save_kb: 第一参须为 knowledge 值。",
                error_code=KNW_KB_ARTIFACT_MALFORMED,
            )
        for key in ("facts", "vocab", "seq"):
            if key not in kb:
                raise InterpreterError(
                    f"world_model.save_kb: knowledge 快照缺 KB 面节 '{key}'。",
                    error_code=KNW_KB_ARTIFACT_MALFORMED,
                )
        facts = kb["facts"]
        vocab = kb["vocab"]
        seq = kb["seq"]
        self._validate_kb_payload(facts, vocab, seq)
        content_hash = kb_content_hash(facts, vocab, seq)
        artifact = {
            "schema_version": KB_SCHEMA_VERSION,
            "content_hash": content_hash,
            "facts": _kb_facts_list(facts),
            "vocab": vocab,
            "seq": seq,
        }
        text = json.dumps(artifact, ensure_ascii=False, indent=2)
        native_path = self._resolve_native_path(path, operation="write")
        with open(native_path, "w", encoding="utf-8") as f:
            f.write(text)
        return content_hash

    # ------------------------------------------------------------------ #
    # 窄模型工件面（bind/save——内容寻址 artifact；纯推理零训练）
    # ------------------------------------------------------------------ #

    def bind_artifact(self, path: str) -> IbNarrowModel:
        """加载窄模型 artifact → 三级验证门 → 水化为**活 narrow_model 值**
        （bind 已训练窄模型工件，推理时 score/topk，纯推理零训练）。

        验证门（fail-fast，逐级，同 load_kb 纪律）：① 结构门（合法 JSON +
        封套键齐备 + 向量维度/名-嵌入键一致 + 架构受支持）→
        ``NAR_ARTIFACT_MALFORMED``；② 版本门（schema_version 未知）→
        ``NAR_SCHEMA_VERSION``（无自动迁移）；③ 完整性门（canonical 重算
        hash ≠ content_hash——篡改/损坏）→ ``NAR_HASH_MISMATCH``。文件
        不存在/沙箱拒绝 = 复用 fs 面诊断（原样穿透）。
        """
        native_path = self._resolve_native_path(path, operation="read")
        with open(native_path, "r", encoding="utf-8") as f:
            text = f.read()
        # ① 结构门（合法 JSON + 顶层对象 + 封套键）
        try:
            artifact = json.loads(text)
        except (json.JSONDecodeError, ValueError) as e:
            raise InterpreterError(
                f"world_model.bind_artifact: artifact 非合法 JSON（{e}）。",
                error_code=NAR_ARTIFACT_MALFORMED,
            ) from e
        if not isinstance(artifact, dict):
            raise InterpreterError(
                "world_model.bind_artifact: artifact 顶层须为对象（dict）。",
                error_code=NAR_ARTIFACT_MALFORMED,
            )
        for key in _MODEL_ARTIFACT_KEYS:
            if key not in artifact:
                raise InterpreterError(
                    f"world_model.bind_artifact: artifact 缺封套字段 '{key}'。",
                    error_code=NAR_ARTIFACT_MALFORMED,
                )
        model_name = artifact["model_name"]
        architecture = artifact["architecture"]
        dim = artifact["dim"]
        entities = artifact["entities"]
        entity_embeddings = artifact["entity_embeddings"]
        relations = artifact["relations"]
        relation_embeddings = artifact["relation_embeddings"]
        self._validate_model_payload(
            model_name, architecture, dim, entities, entity_embeddings,
            relations, relation_embeddings,
        )
        # ② 版本门
        version = artifact["schema_version"]
        if version != MODEL_SCHEMA_VERSION:
            raise InterpreterError(
                f"world_model.bind_artifact: 未知 schema_version {version!r}"
                f"（本版本仅支持 {MODEL_SCHEMA_VERSION}；无自动迁移）。",
                error_code=NAR_SCHEMA_VERSION,
            )
        # ③ 完整性门（内容寻址：canonical 重算比对）
        expected = model_content_hash(
            model_name, architecture, dim, entities,
            entity_embeddings, relations, relation_embeddings,
        )
        if expected != artifact["content_hash"]:
            raise InterpreterError(
                "world_model.bind_artifact: content_hash 验证失败"
                f"（期望 {expected}，artifact 载 {artifact['content_hash']}）"
                "——数据损坏或被篡改。",
                error_code=NAR_HASH_MISMATCH,
            )
        # 水化：活 narrow_model 值（冻结工件——纯推理零训练）
        cls = self.registry.get_class("narrow_model")
        return IbNarrowModel(
            cls,
            payload={
                "model_name": model_name,
                "architecture": architecture,
                "dim": dim,
                "entities": entities,
                "entity_embeddings": entity_embeddings,
                "relations": relations,
                "relation_embeddings": relation_embeddings,
                "schema_version": MODEL_SCHEMA_VERSION,
                "content_hash": expected,
            },
        )

    def save_artifact(self, model: Dict[str, Any], path: str) -> str:
        """序列化窄模型工件为 artifact 写盘，返回 ``content_hash``（钉扎/
        审计面：调用方可经 hash 比对验证落盘内容）。

        ``model`` 参数经调用边界拆箱到达 = 值快照（``to_native`` 全字段 dict）；
        保存取工件全键（model_name/architecture/dim/entities/entity_embeddings/
        relations/relation_embeddings）。文件布局 = 传输（pretty JSON）；身份
        = canonical（紧凑规范形态）。
        """
        if not isinstance(model, dict):
            raise InterpreterError(
                "world_model.save_artifact: 第一参须为 narrow_model 值。",
                error_code=NAR_ARTIFACT_MALFORMED,
            )
        for key in (
            "model_name", "architecture", "dim", "entities",
            "entity_embeddings", "relations", "relation_embeddings",
        ):
            if key not in model:
                raise InterpreterError(
                    f"world_model.save_artifact: narrow_model 快照缺工件节 '{key}'。",
                    error_code=NAR_ARTIFACT_MALFORMED,
                )
        model_name = model["model_name"]
        architecture = model["architecture"]
        dim = model["dim"]
        entities = model["entities"]
        entity_embeddings = model["entity_embeddings"]
        relations = model["relations"]
        relation_embeddings = model["relation_embeddings"]
        self._validate_model_payload(
            model_name, architecture, dim, entities, entity_embeddings,
            relations, relation_embeddings,
        )
        content_hash = model_content_hash(
            model_name, architecture, dim, entities,
            entity_embeddings, relations, relation_embeddings,
        )
        artifact = {
            "schema_version": MODEL_SCHEMA_VERSION,
            "content_hash": content_hash,
            "model_name": model_name,
            "architecture": architecture,
            "dim": dim,
            "entities": entities,
            "entity_embeddings": entity_embeddings,
            "relations": relations,
            "relation_embeddings": relation_embeddings,
        }
        text = json.dumps(artifact, ensure_ascii=False, indent=2)
        native_path = self._resolve_native_path(path, operation="write")
        with open(native_path, "w", encoding="utf-8") as f:
            f.write(text)
        return content_hash
