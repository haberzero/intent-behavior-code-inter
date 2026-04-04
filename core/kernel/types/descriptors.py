from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Any, Dict, List, Union, Protocol, runtime_checkable, TYPE_CHECKING, Callable
import copy

# [Axiom Layer Integration]
if TYPE_CHECKING:
    from core.kernel.axioms.protocols import (
        TypeAxiom, CallCapability, IterCapability, SubscriptCapability,
        OperatorCapability, ParserCapability, WritableTrait
    )
    from .registry import MetadataRegistry
    from core.kernel.symbols import Symbol

@dataclass
class TypeDescriptor:
    """
    UTS (Unified Type System) 基础描述符。
    作为 [Axiom Container]，它不再包含硬编码逻辑，而是代理到底层的公理系统。
    """
    name: str = ""
    module_path: Optional[str] = None
    is_nullable: bool = True
    is_user_defined: bool = True # [CHANGE] 默认设为 True，仅内核类手动设为 False
    kind: str = field(init=False)
    # 成员字典：名称 -> 符号 (不再是 TypeDescriptor)
    # 这样我们可以同时追踪成员的类型和定义源
    members: Dict[str, 'Symbol'] = field(default_factory=dict)
    
    # 运行时绑定的注册表上下文
    _registry: Optional['MetadataRegistry'] = field(default=None, init=False, repr=False)
    
    # 公理绑定
    _axiom: Optional['TypeAxiom'] = field(default=None, init=False, repr=False)

    def walk_references_raw(self, callback: Callable[['TypeDescriptor'], 'TypeDescriptor']) -> None:
        """
         深度遍历描述符持有的类型引用。
        与 walk_references 的区别在于，它不包含 members 遍历，
        专门用于 clone 过程中处理子类特有的字段（如 element_type）。
        """
        pass

    def walk_references(self, callback: Callable[['TypeDescriptor'], 'TypeDescriptor']) -> None:
        """
         深度遍历描述符持有的类型引用（包含成员符号）。
        """
        if self.members:
            for sym in self.members.values():
                sym.walk_references(callback)
        self.walk_references_raw(callback)

    def get_references(self) -> Dict[str, Any]:
        """
         获取所有内部持有的类型引用。
        用于序列化和结构分析，消除 isinstance 检查。
        """
        return {}

    def clone(self, memo: Optional[Dict[int, Any]] = None) -> 'TypeDescriptor':
        """
        [IES 2.0 Isolation] 深度克隆描述符，确保引擎实例间的物理隔离。
        使用 memo 字典防止循环引用导致的无限递归。
        """
        if memo is None: memo = {}
        if id(self) in memo:
            return memo[id(self)]
            
        # 1. 基础浅拷贝处理标量字段
        new_desc = copy.copy(self)
        memo[id(self)] = new_desc
        
        # 2. 重置运行时绑定状态
        new_desc._registry = None
        new_desc._axiom = None
        
        # 3. 递归克隆成员符号
        if self.members:
            # 注意：此处必须使用 dict comprehension 确保 Symbol.clone 也能使用同一个 memo
            new_desc.members = {name: sym.clone(memo) for name, sym in self.members.items()}
            
        # 4.  多态处理子类持有的结构化类型引用
        # 注意：此处必须使用一个新的 callback，它只对“尚未被克隆”的原生引用调用 clone
        def clone_ref(d: 'TypeDescriptor') -> 'TypeDescriptor':
            if id(d) in memo:
                return memo[id(d)]
            return d.clone(memo)

        new_desc.walk_references_raw(clone_ref)
            
        return new_desc

    def __post_init__(self):
        self.kind = self.__class__.__name__

    def __eq__(self, other: Any) -> bool:
        if type(self) is not type(other):
            return False
        # 基于名称与引用进行一致性判定，消除子类中的冗余 isinstance
        return self.name == other.name and self.get_references() == other.get_references()

    def unwrap(self) -> 'TypeDescriptor':
        return self

    def get_signature(self) -> Optional[tuple[List['TypeDescriptor'], Optional['TypeDescriptor']]]:
        """ 获取函数签名 (参数列表, 返回类型)。多态实现，消除 isinstance。"""
        return None

    def get_base_axiom_name(self) -> str:
        """ 获取该描述符对应的基础公理名称"""
        return self.name

    # --- Capability Accessors (Delegated to Axiom) ---
    
    def get_call_trait(self) -> Optional['CallCapability']:
        return self._axiom.get_call_capability() if self._axiom else None

    def _resolve_type_ref(self, res: Optional[Union['TypeDescriptor', str]]) -> Optional['TypeDescriptor']:
        """[Helper] 将公理返回的类型引用（可能是字符串名称）转换为当前实例的描述符对象"""
        if res is None: return None
        if isinstance(res, str):
            resolved = self._registry.resolve(res) if self._registry else None
            return resolved
        return res

    def resolve_return(self, args: List['TypeDescriptor']) -> Optional['TypeDescriptor']:
        if self._axiom:
            trait = self._axiom.get_call_capability()
            if trait:
                return self._resolve_type_ref(trait.resolve_return(args))
        return None

    def get_element_type(self) -> Optional['TypeDescriptor']:
        if self._axiom:
            trait = self._axiom.get_iter_capability()
            if trait:
                return self._resolve_type_ref(trait.get_element_type())
        return None

    def get_key_type(self) -> Optional['TypeDescriptor']:
        """获取键类型（针对字典类型）"""
        return None

    def get_value_type(self) -> Optional['TypeDescriptor']:
        """获取值类型（针对字典类型）"""
        return None

    def get_receiver_type(self) -> Optional['TypeDescriptor']:
        """获取接收者类型（针对绑定方法）"""
        return None

    def get_function_type(self) -> Optional['TypeDescriptor']:
        """获取内部函数类型（针对绑定方法）"""
        return None

    def resolve_item(self, key: 'TypeDescriptor') -> Optional['TypeDescriptor']:
        """解析下标访问结果（委托给公理）"""
        if self._axiom:
            trait = self._axiom.get_subscript_capability()
            if trait:
                return self._resolve_type_ref(trait.resolve_item(key))
        return None

    def resolve_specialization(self, args: List['TypeDescriptor']) -> 'TypeDescriptor':
        """ 产生特化类型（委托给公理）"""
        if self._axiom and self._registry:
            return self._axiom.resolve_specialization(self._registry, args)
        return self

    def rehydrate_fields(self, data: Dict[str, Any], hydrator: Any) -> None:
        """ 重水化：根据扁平化数据恢复对象字段"""
        pass

    def get_operator_result(self, op: str, other: Optional['TypeDescriptor'] = None) -> Optional['TypeDescriptor']:
        """运算符决议 (Delegated to Axiom)"""
        if other:
            other = other.unwrap()
        
        if self._axiom:
            op_cap = self._axiom.get_operator_capability()
            if op_cap:
                return self._resolve_type_ref(op_cap.resolve_operation(op, other))
        return None

    def get_iter_trait(self) -> Optional['IterCapability']:
        return self._axiom.get_iter_capability() if self._axiom else None

    def get_subscript_trait(self) -> Optional['SubscriptCapability']:
        return self._axiom.get_subscript_capability() if self._axiom else None

    def get_parser_trait(self) -> Optional['ParserCapability']:
        """获取解析能力（委托给公理）"""
        if self._axiom:
            return self._axiom.get_parser_capability()
        return None

    def get_writable_trait(self) -> Optional['WritableTrait']:
        """获取写能力（用于分析阶段更新元数据）"""
        if self._axiom:
            return self._axiom.get_writable_trait()
        # 使用能力探测替代 isinstance 检查
        if hasattr(self, 'update_signature'):
            return self
        return None

    def is_dynamic(self) -> bool:
        """
        判断是否为动态/Any类型。
        完全委托给公理系统判断。如果未绑定公理，默认视为非动态（安全回退）。
        """
        if self._axiom:
            return self._axiom.is_dynamic()
        return self.name in ("Any", "var")

    def is_class(self) -> bool:
        """是否为类类型。"""
        if self._axiom:
            return self._axiom.is_class()
        # 默认通过 kind 判定，消除 isinstance
        return self.kind == "ClassMetadata"

    def is_module(self) -> bool:
        """是否为模块类型。"""
        if self._axiom:
            return self._axiom.is_module()
        # 默认通过 kind 判定，消除 isinstance
        return self.kind == "ModuleMetadata"

    def is_behavior(self) -> bool:
        """是否为行为描述类型。"""
        return self.name == "behavior"

    def is_assignable_to(self, other: 'TypeDescriptor') -> bool:
        """
        类型兼容性校验 (Axiom-Driven)
        """
        if other is None:
            return False

        s = self.unwrap()
        o = other.unwrap()

        if s is o: return True

        if o.is_dynamic():
            return True
        if s.is_dynamic():
            return o.is_dynamic()

        if s._axiom and s._axiom.is_compatible(o):
            return True
        if o._axiom and o._axiom.is_compatible(s):
            return True

        return s._is_structurally_compatible(o)

    def get_diff_hint(self, other: 'TypeDescriptor') -> str:
        """
        [UTS Diagnostic] 生成类型不匹配的友好提示。
        """
        s = self.unwrap()
        o = other.unwrap()
        
        # 1. 极简匹配 (基础名不匹配)
        if s.name != o.name:
            # [IES 2.1 Axiom-Driven] 优先尝试公理提供的诊断提示，消除硬编码字符串比对
            if s._axiom:
                axiom_hint = s._axiom.get_diff_hint(o)
                if axiom_hint: return axiom_hint
            
            if s.is_dynamic() or s.name in ("Any", "var"):
                return f"Expected '{o.name}', but got dynamic type '{s.name}'. Use explicit cast (e.g. '({o.name}) expr') to convert it."
            
            return f"Expected '{o.name}', but got '{s.name}'."

        # 2. 泛型参数匹配 (如果子类支持)
        if hasattr(s, 'element_type') and hasattr(o, 'element_type'):
            if s.element_type and o.element_type and not s.element_type.is_assignable_to(o.element_type):
                return f"Element type mismatch: {s.element_type.get_diff_hint(o.element_type)}"
        
        if hasattr(s, 'key_type') and hasattr(o, 'key_type'):
            if s.key_type and o.key_type and not s.key_type.is_assignable_to(o.key_type):
                return f"Key type mismatch: {s.key_type.get_diff_hint(o.key_type)}"
        
        if hasattr(s, 'value_type') and hasattr(o, 'value_type'):
            if s.value_type and o.value_type and not s.value_type.is_assignable_to(o.value_type):
                return f"Value type mismatch: {s.value_type.get_diff_hint(o.value_type)}"

        # 3. 函数签名匹配 (通过 Capability 访问签名，消除 isinstance)
        s_sig = s.get_signature()
        o_sig = o.get_signature()
        if s_sig and o_sig:
            s_params, s_ret = s_sig
            o_params, o_ret = o_sig
            if len(s_params) != len(o_params):
                return f"Parameter count mismatch: expected {len(o_params)}, but got {len(s_params)}"
            for i, (p1, p2) in enumerate(zip(s_params, o_params)):
                if not p1.is_assignable_to(p2):
                    return f"Parameter {i+1} mismatch: {p1.get_diff_hint(p2)}"
            if s_ret and o_ret and not s_ret.is_assignable_to(o_ret):
                return f"Return type mismatch: {s_ret.get_diff_hint(o_ret)}"

        return f"Type '{s.name}' is not compatible with '{o.name}'."

    # TODO: 疑问：是否存在问题？结构化兼容逻辑是不是有点宽松？
    def _is_structurally_compatible(self, other: 'TypeDescriptor') -> bool:
        """ 子类可重写的结构化兼容性逻辑，消除硬编码比对"""
        if type(self) is not type(other):
            return False
        return self.name == other.name and self.get_references() == other.get_references()

    def resolve_member(self, name: str) -> Optional['Symbol']:
        """
        解析已存在的成员符号。
        [Architecture Policy] 此处不再负责动态创建符号，以保持底层纯净。
        """
        if name in self.members:
            return self.members[name]
            
        return None

    def __str__(self):
        if self.module_path:
            return f"{self.module_path}.{self.name}"
        return self.name

@dataclass
class LazyDescriptor(TypeDescriptor):
    """
    延迟加载描述符。
    用于解决模块加载时的循环依赖。
    """
    target_name: str = ""
    target_module: Optional[str] = None
    _resolved: Optional[TypeDescriptor] = None

    def __init__(self, name: str, module_path: Optional[str] = None):
        super().__init__(name=name, module_path=module_path)
        self.target_name = name
        self.target_module = module_path

    def walk_references_raw(self, callback: Callable[['TypeDescriptor'], 'TypeDescriptor']) -> None:
        """ 延迟加载描述符也需要参与多态遍历"""
        if self._resolved:
            self._resolved = callback(self._resolved)

    def unwrap(self) -> TypeDescriptor:
        if self._resolved:
            return self._resolved
            
        # 如果没有关联注册表，无法解包 (这在单引擎场景下不应该发生)
        if not self._registry:
            return self
            
        self._resolved = self._registry.resolve(self.target_name, self.target_module)
        if not self._resolved:
            # 仍然没找到，返回自身占位
            return self
            
        return self._resolved

    def resolve_member(self, name: str) -> Optional['Symbol']:
        return self.unwrap().resolve_member(name)

    def get_call_trait(self) -> Optional['CallCapability']:
        return self.unwrap().get_call_trait()

    def get_iter_trait(self) -> Optional['IterCapability']:
        return self.unwrap().get_iter_trait()

    def get_subscript_trait(self) -> Optional['SubscriptCapability']:
        return self.unwrap().get_subscript_trait()

    def get_parser_trait(self) -> Optional['ParserCapability']:
        return self.unwrap().get_parser_trait()

    def is_assignable_to(self, other: 'TypeDescriptor') -> bool:
        if other is None:
            return False
        resolved_self = self._resolved
        if resolved_self:
            return resolved_self.is_assignable_to(other)
        if not self._registry:
            o = other.unwrap()
            return self.name == o.name and type(self) is type(o)
        return self.unwrap().is_assignable_to(other)

    def resolve_return(self, args: List['TypeDescriptor']) -> Optional['TypeDescriptor']:
        return self.unwrap().resolve_return(args)

    def get_element_type(self) -> Optional['TypeDescriptor']:
        return self.unwrap().get_element_type()

    def resolve_item(self, key: 'TypeDescriptor') -> Optional['TypeDescriptor']:
        return self.unwrap().resolve_item(key)

    def get_references(self) -> Dict[str, Any]:
        """ 延迟加载描述符返回已解析描述符的引用"""
        if self._resolved:
            return {"_resolved": self._resolved}
        return {}

# --- 具体描述符实现 ---

@dataclass
class ListMetadata(TypeDescriptor):
    """列表类型元数据"""
    element_type: Optional[TypeDescriptor] = None

    def walk_references_raw(self, callback: Callable[['TypeDescriptor'], 'TypeDescriptor']) -> None:
        if self.element_type:
            self.element_type = callback(self.element_type)

    def get_references(self) -> Dict[str, Any]:
        return {"element_type": self.element_type}

    def get_base_axiom_name(self) -> str:
        return "list"

    def get_iter_trait(self) -> Optional['IterCapability']:
        return self

    def get_element_type(self) -> Optional[TypeDescriptor]:
        return self.element_type

    def rehydrate_fields(self, data: Dict[str, Any], hydrator: Any) -> None:
        self.element_type = hydrator.hydrate(data.get("element_type_uid"))

    def __post_init__(self):
        super().__post_init__()
        self.name = f"list[{self.element_type.name}]" if self.element_type else "list"

    def get_subscript_trait(self) -> Optional['SubscriptCapability']:
        return self

    def resolve_item(self, key: TypeDescriptor) -> Optional[TypeDescriptor]:
        res = super().resolve_item(key)
        return res

    def is_assignable_to(self, other: TypeDescriptor) -> bool:
        if super().is_assignable_to(other): return True
        o = other.unwrap()

        o_iter = o.get_iter_trait()
        if o_iter:
            o_elem = o_iter.get_element_type()
            if o is LIST_DESCRIPTOR or self.element_type is ANY_DESCRIPTOR or o_elem is ANY_DESCRIPTOR:
                return True
            if o_elem is None:
                return self.element_type is None
            if self.element_type is None:
                return False
            return self.element_type.is_assignable_to(o_elem)
        return False

@dataclass
class DictMetadata(TypeDescriptor):
    """字典类型元数据"""
    key_type: Optional[TypeDescriptor] = None
    value_type: Optional[TypeDescriptor] = None

    def walk_references_raw(self, callback: Callable[['TypeDescriptor'], 'TypeDescriptor']) -> None:
        if self.key_type: self.key_type = callback(self.key_type)
        if self.value_type: self.value_type = callback(self.value_type)

    def get_references(self) -> Dict[str, Any]:
        return {"key_type": self.key_type, "value_type": self.value_type}

    def get_base_axiom_name(self) -> str:
        return "dict"

    def get_key_type(self) -> Optional[TypeDescriptor]:
        return self.key_type

    def get_value_type(self) -> Optional[TypeDescriptor]:
        return self.value_type

    def get_subscript_trait(self) -> Optional['SubscriptCapability']:
        return self

    def rehydrate_fields(self, data: Dict[str, Any], hydrator: Any) -> None:
        self.key_type = hydrator.hydrate(data.get("key_type_uid"))
        self.value_type = hydrator.hydrate(data.get("value_type_uid"))

    def __post_init__(self):
        super().__post_init__()
        if self.key_type and self.value_type:
            self.name = f"dict[{self.key_type.name}, {self.value_type.name}]"
        else:
            self.name = "dict"

    def resolve_item(self, key: TypeDescriptor) -> Optional[TypeDescriptor]:
        res = super().resolve_item(key)
        return res

    def is_assignable_to(self, other: TypeDescriptor) -> bool:
        if super().is_assignable_to(other): return True
        o = other.unwrap()

        o_key = o.get_key_type()
        o_val = o.get_value_type()

        if o_key is ANY_DESCRIPTOR and o_val is ANY_DESCRIPTOR:
            return True

        if o is DICT_DESCRIPTOR:
            if o_key is None and o_val is None:
                return True
            k_comp = True
            if self.key_type and o_key:
                k_comp = self.key_type.is_assignable_to(o_key)
            v_comp = True
            if self.value_type and o_val:
                v_comp = self.value_type.is_assignable_to(o_val)
            return k_comp and v_comp
        return False

@dataclass
class FunctionMetadata(TypeDescriptor):
    """函数/方法签名元数据"""
    param_types: List[TypeDescriptor] = field(default_factory=list)
    return_type: Optional[TypeDescriptor] = None

    def walk_references_raw(self, callback: Callable[['TypeDescriptor'], 'TypeDescriptor']) -> None:
        self.param_types = [callback(p) for p in self.param_types]
        if self.return_type: self.return_type = callback(self.return_type)

    def get_references(self) -> Dict[str, Any]:
        return {"param_types": self.param_types, "return_type": self.return_type}

    def get_base_axiom_name(self) -> str:
        return "callable"

    def get_signature(self) -> Optional[tuple[List['TypeDescriptor'], Optional['TypeDescriptor']]]:
        return self.param_types, self.return_type

    def rehydrate_fields(self, data: Dict[str, Any], hydrator: Any) -> None:
        param_uids = data.get("param_types_uids", [])
        self.param_types = [hydrator.hydrate(p_uid) for p_uid in param_uids if p_uid]
        self.return_type = hydrator.hydrate(data.get("return_type_uid"))

    def __post_init__(self):
        super().__post_init__()
        if not self.name or self.name == "TypeDescriptor":
            self.name = "callable"

    # --- Trait Implementations ---

    def update_signature(self, param_types: List['TypeDescriptor'], return_type: Optional['TypeDescriptor']) -> None:
        """[IES 2.1 WritableTrait] 安全更新函数签名"""
        self.param_types = param_types
        self.return_type = return_type

    def get_call_trait(self) -> Optional['CallCapability']:
        return self

    def resolve_return(self, args: List['TypeDescriptor']) -> Optional['TypeDescriptor']:
        # FunctionMetadata 是具体的签名描述，不应该被动态公理拦截
        # 静态推导：检查参数匹配
        if len(args) != len(self.param_types):
            return None
        for i, (expected, actual) in enumerate(zip(self.param_types, args)):
            if not actual.is_assignable_to(expected):
                return None
        return self.return_type

    def is_assignable_to(self, other: TypeDescriptor) -> bool:
        if super().is_assignable_to(other):
            return True
        o = other.unwrap()
        if o is CALLABLE_DESCRIPTOR:
            return True
            
        # 使用能力探测 (get_signature) 代替 isinstance 检查
        o_sig = o.get_signature()
        if o_sig:
            o_params, o_ret = o_sig
            if self.return_type and o_ret:
                if not self.return_type.is_assignable_to(o_ret):
                    return False
            if len(self.param_types) != len(o_params):
                return False
            for p1, p2 in zip(self.param_types, o_params):
                # 参数逆变 (Contravariance)
                if not p2.is_assignable_to(p1): 
                    return False
            return True
        return False

@dataclass
class ClassMetadata(TypeDescriptor):
    """类元数据描述"""
    parent_name: Optional[str] = None
    parent_module: Optional[str] = None

    def get_base_axiom_name(self) -> str:
        return "Type"
    
    # --- Trait Implementations ---

    def get_call_trait(self) -> Optional['CallCapability']:
        """类是可调用的（用于实例化）"""
        return self

    def resolve_return(self, args: List['TypeDescriptor']) -> Optional['TypeDescriptor']:
        # 类实例化返回其实例类型（即自身）
        return self

    def get_references(self) -> Dict[str, Any]:
        """ 补全类元数据的引用获取，支持结构化比对"""
        refs = super().get_references()
        parent = self.resolve_parent()
        if parent:
            refs["parent"] = parent
        return refs

    def resolve_parent(self) -> Optional[TypeDescriptor]:
        if not self.parent_name: return None
        if not self._registry: return None
        return self._registry.resolve(self.parent_name, self.parent_module)

    def is_assignable_to(self, other: TypeDescriptor) -> bool:
        if super().is_assignable_to(other): return True
        parent = self.resolve_parent()
        return parent.is_assignable_to(other) if parent else False

    def resolve_member(self, name: str) -> Optional['Symbol']:
        if name in self.members:
            return self.members[name]
        parent = self.resolve_parent()
        if parent:
            return parent.resolve_member(name)
        return None

    def rehydrate_fields(self, data: Dict[str, Any], hydrator: Any) -> None:
        self.parent_name = data.get("parent_name")
        self.parent_module = data.get("parent_module")
        # 成员表重水化在 Serializer 中已转换为 UID 映射，但运行时通常动态填充
        # 这里保留占位
        pass

@dataclass
class BoundMethodMetadata(TypeDescriptor):
    """绑定方法类型元数据 (合成类型)"""
    receiver_type: Optional[TypeDescriptor] = field(default=None)
    function_type: Optional[TypeDescriptor] = field(default=None)

    def walk_references_raw(self, callback: Callable[['TypeDescriptor'], 'TypeDescriptor']) -> None:
        if self.receiver_type: self.receiver_type = callback(self.receiver_type)
        if self.function_type: self.function_type = callback(self.function_type)

    def get_references(self) -> Dict[str, Any]:
        return {"receiver_type": self.receiver_type, "function_type": self.function_type}

    def get_base_axiom_name(self) -> str:
        return "bound_method"

    def get_receiver_type(self) -> Optional[TypeDescriptor]:
        return self.receiver_type

    def get_function_type(self) -> Optional[TypeDescriptor]:
        return self.function_type

    def get_signature(self) -> Optional[tuple[List['TypeDescriptor'], Optional['TypeDescriptor']]]:
        return self.param_types, self.return_type

    @property
    def param_types(self) -> List[TypeDescriptor]:
        """ 代理函数签名的参数列表，并移除第一个 self 参数"""
        sig = self.function_type.get_signature() if self.function_type else None
        if sig:
            params, _ = sig
            # 如果是类方法，第一个参数通常是 self，在绑定后应被移除
            if len(params) > 0:
                return params[1:]
            return params
        return []

    @property
    def return_type(self) -> Optional[TypeDescriptor]:
        """代理函数签名的返回类型"""
        sig = self.function_type.get_signature() if self.function_type else None
        if sig:
            _, ret = sig
            return ret
        return None

    # --- Trait Implementations ---

    def get_call_trait(self) -> Optional['CallCapability']:
        return self

    def resolve_return(self, args: List['TypeDescriptor']) -> Optional['TypeDescriptor']:
        if self.function_type:
            # 1. 尝试直接决议 (适用于内置方法，它们在公理中通常不显式声明 self)
            res = self.function_type.resolve_return(args)
            if res: return res
            
            # 2. 如果失败，尝试注入 receiver 后决议 (适用于用户定义的类方法，它们在推导中显式包含了 self 参数)
            if self.receiver_type:
                full_args = [self.receiver_type] + args
                return self.function_type.resolve_return(full_args)
        return None

    def __post_init__(self):
        super().__post_init__()
        # 统一绑定方法的名称标识，通过结构化校验实现强类型
        self.name = "bound_method"

    def is_assignable_to(self, other: TypeDescriptor) -> bool:
        if super().is_assignable_to(other):
            return True
        o = other.unwrap()
        if o is CALLABLE_DESCRIPTOR:
            return True
            
        # 使用能力探测代替 isinstance 检查
        o_receiver = o.get_receiver_type()
        o_func = o.get_function_type()
        
        if o_receiver:
            if not self.receiver_type:
                return False
            if not self.receiver_type.is_assignable_to(o_receiver):
                return False
            if self.function_type and o_func:
                return self.function_type.is_assignable_to(o_func)
            return True
        return False

@dataclass
class ModuleMetadata(TypeDescriptor):
    """模块元数据描述"""
    required_capabilities: List[str] = field(default_factory=list)
    
    def get_base_axiom_name(self) -> str:
        return "module"

    def get_references(self) -> Dict[str, Any]:
        """ 模块元数据的引用获取"""
        refs = super().get_references()
        if hasattr(self, 'required_capabilities') and self.required_capabilities:
            refs["required_capabilities"] = self.required_capabilities
        return refs

    def rehydrate_fields(self, data: Dict[str, Any], hydrator: Any) -> None:
        self.required_capabilities = data.get("required_capabilities", [])

    def __post_init__(self):
        super().__post_init__()
        if not self.name or self.name == "TypeDescriptor":
            self.name = "module"

# 预定义常量描述符 (作为原型存在)
INT_DESCRIPTOR = TypeDescriptor(name="int", is_nullable=False, is_user_defined=False)
STR_DESCRIPTOR = TypeDescriptor(name="str", is_nullable=False, is_user_defined=False)
FLOAT_DESCRIPTOR = TypeDescriptor(name="float", is_nullable=False, is_user_defined=False)
BOOL_DESCRIPTOR = TypeDescriptor(name="bool", is_nullable=False, is_user_defined=False)
VOID_DESCRIPTOR = TypeDescriptor(name="void", is_nullable=False, is_user_defined=False)
ANY_DESCRIPTOR = TypeDescriptor(name="Any", is_nullable=True, is_user_defined=False)
VAR_DESCRIPTOR = TypeDescriptor(name="var", is_nullable=True, is_user_defined=False)
CALLABLE_DESCRIPTOR = TypeDescriptor(name="callable", is_nullable=True, is_user_defined=False)
EXCEPTION_DESCRIPTOR = TypeDescriptor(name="Exception", is_nullable=True, is_user_defined=False)

# Missing Descriptors
NONE_DESCRIPTOR = TypeDescriptor(name="None", is_nullable=True, is_user_defined=False)
BEHAVIOR_DESCRIPTOR = TypeDescriptor(name="behavior", is_nullable=True, is_user_defined=False)
BOUND_METHOD_DESCRIPTOR = BoundMethodMetadata(is_user_defined=False) # name will be "bound_method"

# 集合类型占位描述符 (用于基础元数据注册)
LIST_DESCRIPTOR = ListMetadata(name="list", is_nullable=True, is_user_defined=False)
DICT_DESCRIPTOR = DictMetadata(name="dict", is_nullable=True, is_user_defined=False)
MODULE_DESCRIPTOR = ModuleMetadata(name="module", is_nullable=False, is_user_defined=False)
