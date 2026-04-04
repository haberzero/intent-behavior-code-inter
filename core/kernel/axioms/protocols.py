from typing import Protocol, List, Optional, Any, TYPE_CHECKING, ForwardRef, Dict

if TYPE_CHECKING:
    from core.kernel.types.descriptors import TypeDescriptor, FunctionMetadata

# [Axiom Layer] 定义最底层的能力接口，切断对具体实现的依赖
# 使用 ForwardRef 或字符串引用 TypeDescriptor，避免运行时导入

class CallCapability(Protocol):
    """调用能力：描述一个类型如何被调用"""
    def resolve_return(self, args: List['TypeDescriptor']) -> Optional['TypeDescriptor']: ...

class IterCapability(Protocol):
    """迭代能力：描述一个类型如何被迭代"""
    def get_element_type(self) -> 'TypeDescriptor': ...

class SubscriptCapability(Protocol):
    """下标能力：描述一个类型如何被索引访问"""
    def resolve_item(self, key: 'TypeDescriptor') -> Optional['TypeDescriptor']: ...

class OperatorCapability(Protocol):
    """运算能力：描述一个类型如何参与二元运算"""
    def resolve_operation(self, op: str, other: Optional['TypeDescriptor']) -> Optional['TypeDescriptor']: ...

class ConverterCapability(Protocol):
    """转换能力：描述一个类型如何被强制转换"""
    def can_convert_from(self, source: 'TypeDescriptor') -> bool: ...

class ParserCapability(Protocol):
    """解析能力：描述一个类型如何从 LLM结果中解析出值"""
    def parse_value(self, raw_value: str) -> Any: ...

class WritableTrait(Protocol):
    """ 写能力：描述一个元数据对象如何被安全地更新（如分析阶段回填签名）"""
    def update_signature(self, param_types: List['TypeDescriptor'], return_type: Optional['TypeDescriptor']) -> None: ...

class TypeAxiom(Protocol):
    """
    [Axiom] 类型公理接口
    所有原子类型（如 int, str, Any）必须通过实现此接口来声明其行为。
    严禁在代码中通过 if name == "int" 来判断行为。
    """
    @property
    def name(self) -> str: ...
    
    def get_call_capability(self) -> Optional[CallCapability]: ...
    def get_iter_capability(self) -> Optional[IterCapability]: ...
    def get_subscript_capability(self) -> Optional[SubscriptCapability]: ...
    def get_operator_capability(self) -> Optional[OperatorCapability]: ...
    def get_converter_capability(self) -> Optional[ConverterCapability]: ...
    def get_parser_capability(self) -> Optional[ParserCapability]: ...
    def get_writable_trait(self) -> Optional[WritableTrait]: ...
    
    def get_methods(self) -> 'Dict[str, FunctionMetadata]':
        """获取该类型支持的内置方法签名 (Schema)"""
        ...
    
    def get_operators(self) -> Dict[str, str]:
        """ 获取支持的二元运算符及其对应的魔术方法名 (如 {"+": "__add__"})"""
        ...
    
    def is_dynamic(self) -> bool:
        """是否为动态类型 (Any/var/etc.)"""
        ...

    def is_compatible(self, other: 'TypeDescriptor') -> bool:
        """公理级兼容性判断（用于处理 Any/var 等特殊逻辑）"""
        ...

    def is_class(self) -> bool:
        """是否为类类型"""
        ...

    def is_module(self) -> bool:
        """是否为模块类型"""
        ...

    def get_parent_axiom_name(self) -> Optional[str]:
        """ 继承关系：返回父类公理名称 (如 bool -> int)"""
        ...

    def resolve_specialization(self, registry: Any, args: List['TypeDescriptor']) -> 'TypeDescriptor':
        """ 类型演算：根据泛型参数产生新的特化类型"""
        ...

    def get_diff_hint(self, other: 'TypeDescriptor') -> Optional[str]:
        """ 诊断增强：获取类型不匹配时的公理化提示"""
        ...

    def can_return_from_isolated(self) -> bool:
        """判断该类型的实例是否允许从隔离子环境返回"""
        ...
