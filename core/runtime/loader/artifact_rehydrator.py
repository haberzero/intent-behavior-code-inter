from typing import Dict, Any, Optional, List
from core.kernel.spec.registry import SpecRegistry
from core.kernel.spec import (
    IbSpec,
    TypeDef,
)
from core.kernel.spec.specs import TypeDef
from core.kernel.spec.base import TypeKind
from core.kernel.spec.type_ref import TypeRef
from core.base.enums import RegistrationState, Provenance, StorageModel, Visibility

# 统一原语类型列表，确保水化阶段一致性
PRIMITIVE_TYPES = [
    "int", "str", "float", "bool", "void", "any", "auto", "fn", "callable",
    "list", "dict", "behavior", "Optional", "None", "llm_uncertain"
]

# S4 声明驱动：payload 字段名 → 序列化字段名映射（与 serializer._PAYLOAD_FIELD_NAMES
# 同步）。positional_element_types 的序列化键为 positional_type_names。
_PAYLOAD_FIELD_NAMES = {
    "positional_element_types": "positional_type",
}


def _base_name_from_name(name: str) -> str:
    """从特化 spec 名提取基类名（"fn_callable[int]" → "fn_callable"）。"""
    if "[" in name:
        return name.split("[", 1)[0]
    return name


def _is_placeholder_ref(value: str) -> bool:
    """是否为占位类型名（any/auto）：裸基类/缺字段时序列化写 any，还原时跳过。"""
    return value in ("any", "auto", "")

class ArtifactRehydrator:
    """
    类型重水化器：将序列化后的 type_pool 还原为运行时的 IbSpec 对象树。
    """
    _SUPPORTED_KINDS = {k.value for k in TypeKind}

    def __init__(self, type_pool: Dict[str, Any], registry: SpecRegistry):
        self.type_pool = type_pool
        self.registry = registry
        self.memo: Dict[str, IbSpec] = {}
        
        # 预注册原语基础描述符，防止重复创建
        self._init_primitives()

    def _init_primitives(self):
        """同步注册表中的原语描述符到 memo"""
        for name in PRIMITIVE_TYPES:
            desc = self.registry.resolve(name)
            if desc:
                # 寻找池中对应的内置类型（如果存在）并关联
                for uid, data in self.type_pool.items():
                    if data["name"] == name and not data.get("element_type_uid"):
                        self.memo[uid] = desc
                        break

    def hydrate_all(self, registry: Optional[Any] = None) -> List[TypeDef]:
        """
        水化池中所有类型。采用两阶段加载：先创建所有 Shell，再填充详细信息。
        返回所有被成功水化的 TypeDef。
        """
        if registry:
             registry.verify_level(RegistrationState.STAGE_5_HYDRATION.value)
            
        # Phase 1: Create all shells
        for uid in self.type_pool:
            self._create_shell(uid)
            
        # Phase 2: Fill all fields
        classes = []
        for uid in self.type_pool:
            spec = self._fill_descriptor(uid)
            if spec and spec.kind == TypeKind.CLASS.value:
                classes.append(spec)
        
        return classes

    def hydrate(self, uid: str) -> Optional[IbSpec]:
        """按需水化单个类型（支持递归调用）"""
        if not uid or uid not in self.type_pool:
            return None
        
        if uid in self.memo:
            return self.memo[uid]
            
        # 创建并填充
        spec = self._create_shell(uid)
        self._fill_descriptor(uid)
        return spec

    def _create_shell(self, uid: str) -> IbSpec:
        """创建 spec 外壳并存入缓存 (Phase 1)"""
        if uid in self.memo:
            return self.memo[uid]
            
        data = self.type_pool[uid]
        kind = self._resolve_kind(data, uid)
        name = data.get("name", "")
        provenance = Provenance[data.get("provenance", Provenance.KERNEL_NATIVE.name)]
        visibility = Visibility[data.get("visibility", Visibility.PRELUDE_VISIBLE.name)]
        storage_model = StorageModel[data.get("storage_model", StorageModel.MEMORY_BACKED.name)]

        factory = self.registry.factory

        # 映射驱动的 Shell 创建
        shell_creators = {
            # 泛型值承载 kind（LIST/DICT/TUPLE/OPTIONAL/THREAD/THREAD_RESULT/
            # CHANNEL/SLOT/GENERATOR/CALLABLE_INSTANCE）：经 GenericTypeDeclaration
            # 声明驱动还原（S4）——从序列化 payload_fields 读字符串，TypeRef.parse
            # 结构化重建后调 build。消除 per-kind 手工 factory 分支。
            # 非泛型 kind 保留既有 shell（FUNCTION/CALLABLE_SIG/CLASS/...）。
            TypeKind.FUNCTION.value: lambda: TypeDef(
                name=name or "callable",
                kind=TypeKind.FUNCTION.value,
                provenance=Provenance.KERNEL_NATIVE,
                visibility=Visibility.PRELUDE_VISIBLE,
                return_type=TypeRef.parse(data.get("return_type_name", "void")),
                param_types=[TypeRef.parse(p) for p in data.get("param_type_names", [])],
            ),
            TypeKind.CALLABLE_SIG.value: lambda: TypeDef(
                name="fn",
                kind=TypeKind.CALLABLE_SIG.value,
                provenance=Provenance.KERNEL_NATIVE,
                visibility=Visibility.PRELUDE_VISIBLE,
                return_type=TypeRef.parse(data.get("return_type_name", "auto")),
                param_types=[TypeRef.parse(p) for p in data.get("param_type_names", [])],
            ),
            TypeKind.CLASS.value: lambda: factory.create_class(
                name, module=data.get("module_path"), parent_name=data.get("parent_name")
            ),
            TypeKind.PROTOCOL.value: lambda: factory.create_protocol(
                name, module=data.get("module_path")
            ),
            TypeKind.TYPE_PARAM.value: lambda: factory.create_type_param(name),
            TypeKind.BOUND_METHOD.value: lambda: TypeDef(
                name="bound_method",
                kind=TypeKind.BOUND_METHOD.value,
                provenance=Provenance.KERNEL_NATIVE,
                visibility=Visibility.PRELUDE_VISIBLE,
                return_type=TypeRef.parse(data.get("return_type_name", "void")),
                param_types=[TypeRef.parse(p) for p in data.get("param_type_names", [])],
            ),
            TypeKind.MODULE.value: lambda: TypeDef(
                name=name,
                kind=TypeKind.MODULE.value,
                provenance=Provenance.KERNEL_NATIVE,
                visibility=Visibility.PRELUDE_VISIBLE,
            ),
        }

        if name in PRIMITIVE_TYPES and kind == TypeKind.PRIMITIVE.value:
            spec = self.registry.resolve(name) or factory.create_primitive(name)
        else:
            spec = self._generic_restore(kind, name, data, factory, shell_creators)
            if spec is None:
                creator = shell_creators.get(kind)
                if creator:
                    spec = creator()
                else:
                    spec = self.registry.resolve(name) or IbSpec(name=name)

        if spec:
            spec.provenance = provenance
            spec.visibility = visibility
            spec.storage_model = storage_model
            spec = self.registry.register(spec)
            
        self.memo[uid] = spec
        return spec

    def _resolve_kind(self, data: Dict[str, Any], uid: str) -> str:
        kind = data.get("kind", TypeKind.PRIMITIVE.value)
        if kind not in self._SUPPORTED_KINDS:
            raise ValueError(
                f"Artifact type '{uid}' has unsupported kind '{kind}'. "
                f"Supported kinds: {', '.join(sorted(self._SUPPORTED_KINDS))}."
            )
        return kind

    @staticmethod
    def _parse_arg_ref(text: str) -> TypeRef:
        """把泛型实参名解析为 TypeRef（支持嵌套："int" / "list[int]"）。

        serializer 用 ``TypeRef.canonical_name`` 持久化实参（如 "list[int]"）。
        统一委托 ``TypeRef.parse``（字符串→结构单一权威解析器，S1 收敛），
        不维护第二份切分实现。
        """
        return TypeRef.parse(text)

    def _generic_restore(self, kind: str, name: str, data: Dict[str, Any], factory, shell_creators: dict):
        """声明驱动泛型还原（S4）：经 GenericTypeDeclaration 重建泛型特化 spec。

        从序列化 payload_fields（``{field}_name``/``{field}_module``）读字符串，
        ``TypeRef.parse`` 结构化后按实参序调 ``build``。消除 per-kind 手工
        factory 分支（LIST/DICT/TUPLE/OPTIONAL/THREAD/THREAD_RESULT/CHANNEL/SLOT/
        GENERATOR/CALLABLE_INSTANCE）。非泛型 kind 返回 None（走 shell_creators）。
        """
        from core.kernel.spec.base import TypeKind

        if kind not in (
            TypeKind.LIST.value, TypeKind.DICT.value, TypeKind.TUPLE.value,
            TypeKind.OPTIONAL.value, TypeKind.THREAD.value, TypeKind.THREAD_RESULT.value,
            TypeKind.CHANNEL.value, TypeKind.SLOT.value, TypeKind.GENERATOR.value,
            TypeKind.CALLABLE_INSTANCE.value,
        ):
            return None
        generic_types = getattr(self.registry, "generic_types", None)
        if generic_types is None:
            return None
        # CALLABLE_INSTANCE 按 axiom_name 选 behavior/fn_callable 声明。
        base_name = data.get("axiom_name") or _base_name_from_name(name)
        decl = generic_types.get(base_name)
        if decl is None or not decl.payload_fields:
            return None
        arg_refs = []
        arg_modules = []
        for field in decl.payload_fields:
            name_key = _PAYLOAD_FIELD_NAMES.get(field, field)
            # 先试复数（列表字段 positional_type_names），再试单数
            list_val = data.get(f"{name_key}_names")
            if list_val is not None:
                for v, m in zip(list_val, data.get(f"{name_key}_modules") or [None] * len(list_val)):
                    if _is_placeholder_ref(v):
                        continue
                    arg_refs.append(TypeRef.parse(v, m))
                    arg_modules.append(m)
                continue
            val = data.get(f"{name_key}_name")
            if val is not None and not _is_placeholder_ref(val):
                mod = data.get(f"{name_key}_module")
                arg_refs.append(TypeRef.parse(val, mod))
                arg_modules.append(mod)
        # 至少一个实参可重建才调 build（tuple 单类型/裸基类等缺字段时按
        # 缺省建——由调用方回落裸 spec）；全缺返回 None 走 shell_creators 兜底。
        if not arg_refs:
            return None
        return decl.build(factory, arg_refs, arg_modules)

    def _fill_descriptor(self, uid: str) -> Optional[IbSpec]:
        """填充 spec 的详细字段 (Phase 2)"""
        spec = self.memo.get(uid)
        if not spec:
            return None
            
        data = self.type_pool[uid]
        
        if spec.kind == TypeKind.LIST.value:
            # shell 创建已经 factory.create_list(element_type_name=...) 结构化
            # （factory 内部 TypeRef.parse）；此处从序列化字符串字段精化，
            # 不再依赖 element_type_uid（死通道）与扁平 TypeRef.of。
            e_name = data.get("element_type_name")
            if e_name is not None:
                spec.element_type = TypeRef.parse(e_name, data.get("element_type_module"))
                spec.name = f"list[{spec.element_type.canonical_name}]" if spec.element_type.head != "any" else "list"
        elif spec.kind == TypeKind.DICT.value:
            k_name = data.get("key_type_name")
            v_name = data.get("value_type_name")
            if k_name is not None:
                spec.key_type = TypeRef.parse(k_name, data.get("key_type_module"))
            if v_name is not None:
                spec.value_type = TypeRef.parse(v_name, data.get("value_type_module"))
            spec.name = f"dict[{spec.key_type.canonical_name},{spec.value_type.canonical_name}]"
        elif spec.kind in (TypeKind.FUNCTION.value, TypeKind.CALLABLE_SIG.value):
            # 签名恢复经 canonical_name 字符串通道（嵌套保真，与 serializer 对称——
            # serializer 持久化 param_type_names/return_type_name）。旧的
            # param_types_uids/return_type_uid 引用通道对 FUNCTION 无产出
            # （get_references 基类默认空），此前回退 void 覆盖 shell 签名——
            # 运行期函数 spec 恒 void 返回，返回值类型在运行期不可得（类型身份
            # 架构断层：Optional 链式消费包装失效的直接根因）。
            spec.param_types = [
                TypeRef.parse(p) for p in data.get("param_type_names", [])
            ]
            ret_name = data.get("return_type_name")
            spec.return_type = TypeRef.parse(ret_name) if ret_name else TypeRef.of("void")
            if data.get("type_params"):
                spec.type_params = list(data["type_params"])
            if data.get("type_param_bounds"):
                spec.type_param_bounds = dict(data["type_param_bounds"])
        elif spec.kind == TypeKind.CALLABLE_INSTANCE.value:
            # Restore the value type for callable-instance specs (fn_callable[T] / behavior[T]).
            # ``capture_mode`` is intentionally NOT restored at the type level: it
            # belongs to the runtime value (IbFnCallable/IbBehavior) and to the AST
            # node (IbLambdaExpr), both of which are serialized through their own
            # channels.
            v_name = data.get("value_type_name")
            if v_name is not None:
                spec.value_type = TypeRef.parse(v_name, data.get("value_type_module"))
        elif spec.kind == TypeKind.OPTIONAL.value:
            w_name = data.get("wrapped_type_name")
            if w_name is not None:
                spec.wrapped_type = TypeRef.parse(w_name, data.get("wrapped_type_module"))
        elif spec.kind in (TypeKind.THREAD.value, TypeKind.GENERATOR.value):
            v_name = data.get("value_type_name")
            if v_name is not None:
                spec.value_type = TypeRef.parse(v_name, data.get("value_type_module"))
        elif spec.kind in (TypeKind.CLASS.value, TypeKind.PROTOCOL.value):
            p_name = data.get("parent_name")
            p_mod = data.get("parent_module")
            p_args = data.get("parent_args") or []
            if p_args:
                # 父类泛型实参（class Sub[T](Box[T]) → Box[T]；特化 Sub[int] →
                # Box[int]）：重建泛型 parent_type（TypeRef 递归 args 用别名）。
                # 实参名可含嵌套（"int" / "list[int]"），需解析为嵌套 TypeRef。
                spec.parent_type = TypeRef(
                    head=p_name or "Object",
                    args=tuple(self._parse_arg_ref(a) for a in p_args),
                    module=p_mod,
                )
            elif p_name:
                spec.parent_type = TypeRef.of(p_name, p_mod)
            else:
                spec.parent_type = None
            # 用户类泛型类型参数（class Box[T]）：重建供特化/检查。
            if data.get("type_params"):
                spec.type_params = list(data["type_params"])
            if data.get("implements"):
                spec.implements = list(data["implements"])
            if data.get("type_param_bounds"):
                spec.type_param_bounds = dict(data["type_param_bounds"])
            # 用户类泛型特化实参（Box[int]）+ 原始基类名：重建供 from_spec
            # 结构化构造（round-trip 保真）。
            if data.get("type_args"):
                spec.type_args = [self._parse_arg_ref(a) for a in data["type_args"]]
            if data.get("base_name"):
                spec.base_name = data["base_name"]
        elif spec.kind == TypeKind.MODULE.value:
            spec.exported_types = list(data.get("exported_types", []))

        return spec
