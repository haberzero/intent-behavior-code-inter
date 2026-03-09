from typing import Any, Optional, Dict, List, Callable, Union
from core.domain import symbols
from core.domain import types as uts

class TypeBridge:
    """
    Bridge between foundation.types (UTS) and compiler.semantic symbols.
    This ensures the compiler only depends on metadata descriptors, not runtime objects.
    """
    @staticmethod
    def import_all_from_registry(registry: Any, external_resolver: Optional[Callable[[str], Optional[symbols.StaticType]]] = None) -> Dict[str, symbols.StaticType]:
        """
        [IES 2.0 ARCH] 统一的语义网关：从元数据注册表中批量导入所有顶层符号（类型和全局函数）。
        """
        if not registry or not hasattr(registry, "_metadata_registry"):
            return {}
            
        metadata_reg = registry._metadata_registry
        cache = {}
        results = {}
        
        for name, desc in metadata_reg.all_descriptors.items():
            # 仅导入顶层符号（不带点号的）
            if "." in name:
                continue
                
            sm_type = TypeBridge.uts_to_semantic_type(desc, cache, external_resolver)
            results[name] = sm_type
            
        return results

    @staticmethod
    def uts_to_semantic_type(
        descriptor: uts.TypeDescriptor, 
        cache: Optional[Dict[int, symbols.StaticType]] = None,
        external_resolver: Optional[Callable[[str], Optional[symbols.StaticType]]] = None
    ) -> symbols.StaticType:
        """
        将 UTS 描述符转换为编译器语义类型。
        
        Args:
            descriptor: UTS 元数据描述符
            cache: 递归转换缓存（处理循环引用）
            external_resolver: 外部模块解析器，用于处理跨模块继承 (parent_module)
        """
        if cache is None:
            cache = {}
            
        desc_id = id(descriptor)
        if desc_id in cache:
            return cache[desc_id]

        # 原子类型直接返回
        if descriptor is uts.INT_DESCRIPTOR: return symbols.STATIC_INT
        if descriptor is uts.STR_DESCRIPTOR: return symbols.STATIC_STR
        if descriptor is uts.FLOAT_DESCRIPTOR: return symbols.STATIC_FLOAT
        if descriptor is uts.BOOL_DESCRIPTOR: return symbols.STATIC_BOOL
        if descriptor is uts.VOID_DESCRIPTOR: return symbols.STATIC_VOID
        if descriptor is uts.ANY_DESCRIPTOR or descriptor is uts.VAR_DESCRIPTOR: return symbols.STATIC_ANY
        
        if isinstance(descriptor, uts.ListMetadata):
            lt = symbols.ListType(TypeBridge.uts_to_semantic_type(descriptor.element_type, cache, external_resolver))
            cache[desc_id] = lt
            return lt
        
        if isinstance(descriptor, uts.FunctionMetadata):
            ft = symbols.FunctionType(
                param_types=[TypeBridge.uts_to_semantic_type(p, cache, external_resolver) for p in descriptor.param_types],
                return_type=TypeBridge.uts_to_semantic_type(descriptor.return_type, cache, external_resolver) if descriptor.return_type else symbols.STATIC_VOID
            )
            cache[desc_id] = ft
            return ft
            
        if isinstance(descriptor, uts.ModuleMetadata):
            st = symbols.SymbolTable()
            mt = symbols.ModuleType(descriptor.name, st)
            cache[desc_id] = mt # 先入缓存，防止循环引用
            
            for name, exp_desc in descriptor.members.items():
                stype = TypeBridge.uts_to_semantic_type(exp_desc, cache, external_resolver)
                if isinstance(exp_desc, uts.FunctionMetadata):
                    st.define(symbols.FunctionSymbol(name=name, kind=symbols.SymbolKind.FUNCTION, type_signature=stype))
                elif isinstance(exp_desc, uts.ClassMetadata):
                    st.define(symbols.TypeSymbol(name=name, kind=symbols.SymbolKind.CLASS, static_type=stype))
                else:
                    st.define(symbols.VariableSymbol(name=name, kind=symbols.SymbolKind.VARIABLE, var_type=stype))
            
            return mt

        if isinstance(descriptor, uts.ClassMetadata):
            # 1. 尝试解析父类
            parent_type = None
            if descriptor.parent_name:
                # 如果指定了父模块，则通过解析器查找
                if descriptor.parent_module and external_resolver:
                    ext_mod = external_resolver(descriptor.parent_module)
                    if isinstance(ext_mod, symbols.ModuleType):
                        parent_sym = ext_mod.resolve_member(descriptor.parent_name)
                        if parent_sym and isinstance(parent_sym.type_info, symbols.ClassType):
                            parent_type = parent_sym.type_info
                
                # 如果没找到（或没指定模块），则在当前“转换链”中尝试（简单情况）
                if not parent_type:
                    # 这是一个启发式：如果父类在同一个模块中且已经转换过
                    for cached_t in cache.values():
                        if isinstance(cached_t, symbols.ClassType) and cached_t.name == descriptor.parent_name:
                            parent_type = cached_t
                            break
            
            # [IES 2.0 FIX] ClassType 构造函数现在接收 descriptor 而非 cls_scope
            cls_type = symbols.ClassType(descriptor.name, parent_type, descriptor=descriptor)
            cache[desc_id] = cls_type # 先入缓存，防止循环引用
            
            # 注意：不再需要手动填充 cls_scope，因为 ClassType 会代理给 descriptor.resolve_member
            
            return cls_type
            
        return symbols.STATIC_ANY
