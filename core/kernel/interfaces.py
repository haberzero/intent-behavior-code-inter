from typing import Any, Protocol, Optional, List, Mapping, runtime_checkable

__all__ = ["IExecutionContext", "IModuleScope"]

@runtime_checkable
class IModuleScope(Protocol):
    """模块作用域协议：``IbModule.scope`` 的统一契约。

    模块 scope 有两种实现形态：
    - ``IbNativeObject``（objects/kernel）：原生模块桥接，成员经 ``receive`` 分发；
    - ``ScopeImpl``（runtime/interpreter）：IBC 模块作用域，成员经 ``get`` 查找。

    本协议声明两者的统一成员访问契约，使 ``IbModule.receive`` 无需按形态判别。
    """
    def get(self, name: str) -> Any:
        """按名字获取成员；不存在抛 ``KeyError``。"""
        ...
    def receive(self, message: str, args: List[Any]) -> Any:
        """消息分发（IbObject 协议）。"""
        ...

@runtime_checkable
class IExecutionContext(Protocol):
    """
    运行时执行上下文数据协议。
    作为 Interpreter 与底层组件（Kernel/Foundation）解耦的桥梁。
    它仅包含执行所需的只读数据池、栈内省能力以及辅助查询方法。

    此接口定义在 kernel 层，作为架构核心抽象。
    runtime 层实现具体类并实现此接口。
    求值入口为 VMExecutor.run()；此 Protocol 不包含 visit() 方法（已删除）。
    """
    @property
    def node_pool(self) -> Mapping[str, Any]: ...

    @property
    def symbol_pool(self) -> Mapping[str, Any]: ...

    @property
    def scope_pool(self) -> Mapping[str, Any]: ...

    @property
    def type_pool(self) -> Mapping[str, Any]: ...

    @property
    def asset_pool(self) -> Mapping[str, str]: ...

    @property
    def stack_inspector(self) -> Any: ...

    @property
    def registry(self) -> Any: ...

    @property
    def factory(self) -> Any: ...

    @property
    def runtime_context(self) -> Any: ...

    @property
    def module_manager(self) -> Any: ...

    @property
    def current_module_name(self) -> Optional[str]: ...

    @current_module_name.setter
    def current_module_name(self, value: Optional[str]) -> None: ...

    @property
    def strict_mode(self) -> bool: ...

    def get_node_data(self, node_uid: str) -> Mapping[str, Any]: ...

    def get_side_table(self, table_name: str, key: str) -> Any: ...

    def get_llmexcept_protection_map(self) -> Mapping[str, str]:
        """llmexcept 保护映射（被保护节点 UID -> handler UID）。

        内核拥有 node_pool 节点格式语义，对外只暴露结构化映射契约；
        消费方（idbg 等）不得直读 node_pool 原始节点结构。
        """
        ...

    def push_stack(self, name: str, location: Optional[Any] = None, is_user_function: bool = False, **kwargs) -> None: ...

    def pop_stack(self) -> None: ...

    def resolve_type_from_symbol(self, sym_uid: str) -> Optional[Any]: ...

    def extract_name_id(self, node_uid: str) -> Optional[str]: ...

    def resolve_value(self, val: Any) -> Any: ...

    def is_truthy(self, value: Any) -> bool: ...