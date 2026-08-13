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
            # list[T] / dict[K,V] / tuple[T]：经 factory 重建特化 spec——
            # 特化工厂按泛型实参重建 spec（硬编码基础 TypeDef 会丢失实参）。
            TypeKind.LIST.value: lambda: (
                factory.create_list(
                    allowed_element_type_names=data.get("allowed_element_type_names"),
                    allowed_element_type_modules=data.get("allowed_element_type_modules"),
                )
                if data.get("allowed_element_type_names")
                else factory.create_list(
                    element_type_name=data.get("element_type_name", "any"),
                    element_type_module=data.get("element_type_module"),
                )
            ),
            TypeKind.DICT.value: lambda: factory.create_dict(
                key_type_name=data.get("key_type_name", "any"),
                key_type_module=data.get("key_type_module"),
                value_type_name=data.get("value_type_name", "any"),
                value_type_module=data.get("value_type_module"),
            ),
            TypeKind.TUPLE.value: lambda: (
                factory.create_tuple(
                    positional_element_type_names=data.get("positional_type_names"),
                    positional_element_type_modules=data.get("positional_type_modules"),
                )
                if data.get("positional_type_names")
                else factory.create_tuple(
                    element_type_name=data.get("element_type_name", "any"),
                    element_type_module=data.get("element_type_module"),
                )
            ),
            TypeKind.FUNCTION.value: lambda: TypeDef(
                name=name or "callable",
                provenance=Provenance.KERNEL_NATIVE,
                visibility=Visibility.PRELUDE_VISIBLE,
            ),
            TypeKind.CALLABLE_SIG.value: lambda: TypeDef(
                name="fn",
                provenance=Provenance.KERNEL_NATIVE,
                visibility=Visibility.PRELUDE_VISIBLE,
                return_type=TypeRef.of(data.get("return_type_name", "auto")),
                param_types=[TypeRef.of(p) for p in data.get("param_type_names", [])],
            ),
            TypeKind.CLASS.value: lambda: factory.create_class(
                name, parent_name=data.get("parent_name")
            ),
            TypeKind.TYPE_PARAM.value: lambda: factory.create_type_param(name),
            TypeKind.BOUND_METHOD.value: lambda: TypeDef(
                name="bound_method",
                provenance=Provenance.KERNEL_NATIVE,
                visibility=Visibility.PRELUDE_VISIBLE,
            ),
            TypeKind.MODULE.value: lambda: TypeDef(
                name=name,
                provenance=Provenance.KERNEL_NATIVE,
                visibility=Visibility.PRELUDE_VISIBLE,
            ),
            # Callable-instance specs ("fn_callable[T]" / "behavior[T]") — reconstruct
            # the proper variant so that get_base_name() routes to the matching
            # axiom ("fn_callable" / "behavior").  The axiom selection key is the
            # axiom name embedded in the serialized data, falling back to the
            # spec's own name prefix.
            TypeKind.CALLABLE_INSTANCE.value: lambda: (
                factory.create_behavior(value_type_name=data.get("value_type_name", "auto"))
                if (data.get("axiom_name") or name).startswith("behavior")
                else factory.create_fn_callable(value_type_name=data.get("value_type_name", "auto"))
            ),
            TypeKind.OPTIONAL.value: lambda: factory.create_optional(
                wrapped_type_name=data.get("wrapped_type_name", "any"),
                wrapped_type_module=data.get("wrapped_type_module"),
            ),
            TypeKind.THREAD.value: lambda: factory.create_thread(
                value_type_name=data.get("value_type_name", "any"),
                value_type_module=data.get("value_type_module"),
            ),
            TypeKind.THREAD_RESULT.value: lambda: factory.create_thread_result(
                value_type_name=data.get("value_type_name", "any"),
                value_type_module=data.get("value_type_module"),
            ),
            TypeKind.CHANNEL.value: lambda: factory.create_chan(
                value_type_name=data.get("value_type_name", "any"),
                value_type_module=data.get("value_type_module"),
            ),
            TypeKind.SLOT.value: lambda: factory.create_slot(
                value_type_name=data.get("value_type_name", "any"),
                value_type_module=data.get("value_type_module"),
            ),
            TypeKind.GENERATOR.value: lambda: factory.create_generator(
                value_type_name=data.get("value_type_name", "any"),
                value_type_module=data.get("value_type_module"),
            ),
        }

        if name in PRIMITIVE_TYPES and kind == TypeKind.PRIMITIVE.value:
            spec = self.registry.resolve(name) or factory.create_primitive(name)
        else:
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
            param_uids = data.get("param_types_uids", [])
            spec.param_types = [
                TypeRef.of(s.name, s.module_path) for uid in param_uids
                if (s := self.hydrate(uid)) is not None
            ]
            ret = self.hydrate(data.get("return_type_uid"))
            spec.return_type = TypeRef.of(ret.name, ret.module_path) if ret else TypeRef.of("void")
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
        elif spec.kind == TypeKind.CLASS.value:
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
            # 用户类泛型特化实参（Box[int]）+ 原始基类名：重建供 from_spec
            # 结构化构造（round-trip 保真）。
            if data.get("type_args"):
                spec.type_args = [self._parse_arg_ref(a) for a in data["type_args"]]
            if data.get("base_name"):
                spec.base_name = data["base_name"]
        elif spec.kind == TypeKind.MODULE.value:
            spec.exported_types = list(data.get("exported_types", []))

        return spec
