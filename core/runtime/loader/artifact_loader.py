from typing import Dict, Any, Mapping, Optional
from core.base.enums import Provenance
from .artifact_rehydrator import ArtifactRehydrator
from core.kernel.registry import KernelRegistry

from core.runtime.exceptions import RegistryIsolationError

class LoadedArtifact:
    """已加载并水化的产物容器"""
    def __init__(self, 
                 node_pool: Dict[str, Mapping[str, Any]], 
                 symbol_pool: Dict[str, Mapping[str, Any]], 
                 scope_pool: Dict[str, Mapping[str, Any]], 
                 type_pool: Dict[str, Mapping[str, Any]], 
                 asset_pool: Dict[str, str],
                 entry_module: str,
                 artifact_rehydrator: ArtifactRehydrator,
                 artifact_dict: Dict[str, Any],
                 class_to_node: Dict[Any, Any]):
        self.node_pool = node_pool
        self.symbol_pool = symbol_pool
        self.scope_pool = scope_pool
        self.type_pool = type_pool
        self.asset_pool = asset_pool
        self.entry_module = entry_module
        self.artifact_rehydrator = artifact_rehydrator
        self.artifact_dict = artifact_dict
        self.class_to_node = class_to_node

class ArtifactLoader:
    """
    产物加载器：负责解析原始产物字典并执行类型重水化。
    [Plan A] 严格数据契约：仅接受 Dict 格式的产物数据，实现运行时与编译器的物理隔离。
    """
    def __init__(self, registry: KernelRegistry):
        self.registry = registry

    def _is_concrete_arg(self, name: str) -> bool:
        """判断泛型实参是否为**具体类型**（非类型参数占位）。

        模板父引用 ``class Sub[T](Box[T])`` 的实参 T 是类型参数名，运行时无
        对应实体类；特化父引用 ``Sub[int]`` 的实参 int 是具体类型。判据：
        实参名可被 metadata registry 解析（具体类型）即 concrete；解析失败
        视为类型参数占位。
        """
        spec_reg = self.registry.get_metadata_registry()
        if spec_reg is not None:
            spec = spec_reg.resolve(name)
            if spec is not None and getattr(spec, "kind", None) != "type_param":
                return True
        return False

    def _hydrate_builtin_generic_classes(self, type_pool: Dict[str, Mapping[str, Any]]) -> None:
        """内置泛型特化类水化（缺陷二根治 + S3 句柄类覆盖，registry 封印前执行）。

        编译产物 type_pool 中出现的内置泛型特化 spec（``list[int]`` /
        ``dict[str,int]`` / ``tuple[int,str]`` / ``Optional[int]`` /
        ``thread[int]`` / ``chan[str]`` / ``slot[int]`` / ``generator[int]``
        / ``thread_result[int]``——全部值承载 kind 且 name 含 ``[``）预创建为
        运行时特化类，parent 指向基类。值创建点据此把值绑定特化类，使
        ``IbValue.type_ref`` 带实参（``type()`` 内省一致 + 运行时类型安全）。

        与用户类泛型特化类（hydrate_all → 下方预注册 CLASS 特化 spec）机制
        同构。幂等：特化类已注册则跳过；水化失败不影响加载（值回落基类）。
        """
        from core.kernel.spec.base import TypeKind

        hydrated_kinds = (
            TypeKind.LIST.value,
            TypeKind.TUPLE.value,
            TypeKind.DICT.value,
            TypeKind.OPTIONAL.value,
            TypeKind.THREAD.value,
            TypeKind.THREAD_RESULT.value,
            TypeKind.CHANNEL.value,
            TypeKind.SLOT.value,
            TypeKind.GENERATOR.value,
            TypeKind.CALLABLE_INSTANCE.value,
        )
        spec_reg = self.registry.get_metadata_registry()
        if spec_reg is None:
            return
        for data in type_pool.values():
            if not isinstance(data, Mapping):
                continue
            name = data.get("name", "")
            kind = data.get("kind", "")
            if "[" not in name or kind not in hydrated_kinds:
                continue
            if self.registry.get_class(name) is not None:
                continue
            spec = spec_reg.resolve(name)
            if spec is None:
                continue
            base_name = spec.get_base_name()
            if not base_name or self.registry.get_class(base_name) is None:
                continue
            try:
                self.registry.create_subclass(name, spec, base_name)
            except Exception:
                # 特化类水化失败（spec 未完全填充/父类缺失）保守跳过，值回落基类。
                continue

    def load(self, artifact_dict: Mapping[str, Any]) -> LoadedArtifact:
        """从扁平化字典中加载并执行类型重水化"""
        if not isinstance(artifact_dict, Mapping):
            raise TypeError(f"ArtifactLoader expects a mapping (dict or ImmutableArtifact), but got {type(artifact_dict).__name__}")
        
        pools = artifact_dict.get("pools", {})
        node_pool = pools.get("nodes", {})
        symbol_pool = pools.get("symbols", {})
        scope_pool = pools.get("scopes", {})
        type_pool = pools.get("types", {})
        asset_pool = pools.get("assets", {})
        
        entry_module = artifact_dict.get("entry_module") or artifact_dict.get("metadata", {}).get("entry_module", "main")

        # 执行重水化 (UTS 闭环)
        hydrator = ArtifactRehydrator(type_pool, self.registry.get_metadata_registry())
        user_classes = hydrator.hydrate_all(self.registry)

        # 内置泛型容器特化类水化（缺陷二根治）：编译产物中出现的内置泛型
        # 特化 spec（list[int] / dict[str,int] / tuple[int,str] / Optional[int]）
        # 预创建为运行时特化类——与用户类泛型特化类（hydrate_all 产出 CLASS
        # 特化 spec → 下方预注册）同构。registry 未封印（STAGE_5），值创建点
        # （vm 字面量/反序列化）据此把容器值绑定特化类，使 type_ref 带实参。
        self._hydrate_builtin_generic_classes(type_pool)

        # STAGE 5: 预水合用户类实体，并记录类名到节点 UID 的映射
        class_to_node = {}
        # 1. 扫描所有模块寻找类定义节点
        for module_name, module_data in artifact_dict.get("modules", {}).items():
            if not isinstance(module_data, dict): continue
            root_node_uid = module_data.get("root_node_uid")
            root_node = node_pool.get(root_node_uid)
            if not root_node: continue
            
            for stmt_uid in root_node.get("body", []):
                stmt_data = node_pool.get(stmt_uid)
                if stmt_data and stmt_data.get("_type") == "IbClassDef":
                    # 键 = (module_name, name) 元组：跨模块同名类不碰撞
                    # （geo.Box / graph.Box 各自对应自己的 AST 节点）。
                    class_to_node[(module_name, stmt_data.get("name"))] = (stmt_uid, module_name)

        # 2. 预注册用户定义的类 (支持继承依赖)
        remaining = [c for c in user_classes if c.provenance == Provenance.USER_DEFINED]
        last_count = -1
        
        while remaining and len(remaining) != last_count:
            last_count = len(remaining)
            still_remaining = []
            for cls_desc in remaining:
                # 父类名：parent_type 带**具体**泛型实参时用特化全名
                # （class Sub[T](Box[T]) 特化 Sub[int] → "Box[int]"），继承链
                # 对齐特化类；实参含类型参数占位（模板自身 Box[T] 的 T）或
                # 未注册类型则回退裸基类名。
                # [Module Identity] 父名 module 化：parent_type 缺 module 时以
                # 权威解析补全——内置泛型父（list[T] 等，module 恒 None）**不加**
                # 前缀；同模块用户父（编译期前向引用未解析）以 cls_desc.module_path
                # 补全 → 父名 = qualified_name（geo.Sub[int] 的父 = "geo.Box[int]"），
                # get_class 命中 qualified 键。
                p_ref = cls_desc.parent_type
                if p_ref is not None and p_ref.module is None:
                    parent_module = self.registry.resolve_class_module(
                        p_ref.head, cls_desc.module_path
                    )
                    if parent_module:
                        p_ref = p_ref.with_module(parent_module)
                if p_ref is not None and p_ref.args:
                    p_args = [a.canonical_name for a in p_ref.args]
                    if all(self._is_concrete_arg(a) for a in p_args):
                        parent_name = p_ref.qualified_name
                    else:
                        parent_name = p_ref.head
                else:
                    parent_name = (p_ref.head if p_ref is not None else None) or "Object"
                
                # 父类已存在（如预注册的 Enum 基类）：直接创建子类。
                # [S3 单类表] 无双表缺口——父类存在性检查统一走唯一权威类表。
                parent_class = self.registry.get_class(parent_name, module=cls_desc.module_path)
                if parent_class:
                    # 父类已存在，直接创建子类
                    if self.registry.get_class(cls_desc.name, module=cls_desc.module_path) is None:
                        # 类不存在才创建；已注册（如预注册的 Enum 基类/重复类）有意跳过
                        self.registry.create_subclass(
                            cls_desc.name,
                            cls_desc,
                            parent_name
                        )
                    # 其余 ValueError/PermissionError 是真实错误（封印/描述符失配），
                    # 不再被静默吞掉
                else:
                    try:
                        self.registry.create_subclass(
                            cls_desc.name, 
                            cls_desc, 
                            parent_name
                        )
                    except ValueError:
                        # 可能是父类尚未注册，等待下一轮
                        still_remaining.append(cls_desc)
                    except PermissionError:
                        # 注册表已封印，可能父类是内置类
                        still_remaining.append(cls_desc)
            remaining = still_remaining
            
        if remaining:
            # 继承链断裂属于致命错误 (Item 2.2 Audit)
            # 必须在加载阶段拦截，严禁进入运行时。
            missing = [f"{c.name} (extends {(c.parent_type.head if c.parent_type else None) or 'Object'})" for c in remaining]
            raise RegistryIsolationError(f"Linker Error: Broken inheritance chain for classes: {', '.join(missing)}. "
                                       f"Ensure all parent classes are defined and no circular inheritance exists.")

        return LoadedArtifact(
            node_pool=node_pool,
            symbol_pool=symbol_pool,
            scope_pool=scope_pool,
            type_pool=type_pool,
            asset_pool=asset_pool,
            entry_module=entry_module,
            artifact_rehydrator=hydrator,
            artifact_dict=artifact_dict,
            class_to_node=class_to_node
        )
