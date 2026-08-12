from typing import Optional, Dict, Any, List, TYPE_CHECKING

from core.kernel.spec import IbSpec

from .base import IbObject
from .functions import IbFunction

if TYPE_CHECKING:
    from core.runtime.interfaces import IExecutionContext


class IbUserFunction(IbFunction):
    """
    用户定义的 IBC 函数。
    """
    def __init__(self, node_uid: str, context: 'IExecutionContext', ib_class: Optional['IbClass'] = None, spec: Optional[IbSpec] = None, module_name: Optional[str] = None, owner_class: Optional['IbClass'] = None):
        super().__init__(ib_class or context.registry.get_class("callable"))
        self.node_uid = node_uid
        self.context = context
        self._spec = spec
        self.module_name = module_name or context.current_module_name
        # 定义该方法的 IbClass（方法归属类）。用于 super() 支持。
        # 对于顶层函数，此字段为 None（不在类内）。
        self.owner_class: Optional['IbClass'] = owner_class
        # nonlocal 闭包：{sym_uid: (name, IbCell)} — 由 vm_handle_IbFunctionDef 设置
        self.closure: Optional[Dict[str, Any]] = None
        # 惰性生成器（含 yield，D-08 自标记函数种类）。为 True 时 call() 返回
        # IbGenerator（不执行体），迭代驱动函数体、yield 点产出值。
        self.is_generator: bool = False

    @property
    def spec(self) -> Optional[IbSpec]:
        return self._spec if self._spec is not None else self.ib_class.spec

    def call(self, receiver: IbObject, args: List[IbObject]) -> IbObject:
        """执行用户定义的函数。

        **收敛**：本方法为宿主侧薄包装——委托 CPS 权威路径
        ``_vm_call_user_function`` + ``_drive_generator``（TaskScheduler 驱动
        ``_drive_loop_gen``），不再重复模块切换/意图 fork/作用域/闭包/self+super/
        实参绑定逻辑（消双写）。VM 主路径（leaf.py UserFunctionCall）与线程体
        （coordinator）本就经 CPS 执行本对象；本方法仅作 vtable receive('__call__')
        后备与宿主/反序列化同步调用。

        **生成器方法**：宿主同步路径对生成器方法返回 IbGenerator（不驱动函数体），
        与 VM 主路径 ``make_generator_driver`` 同构——否则经非 generator 模式的
        ``_drive_loop_gen`` 驱动体时 GeneratorYield 泄漏（用户类 ``__iter__`` 等
        协议方法经 receive 调用的崩溃根因，PT-DEBT-O1/I1）。
        """
        from core.runtime.vm.handlers._shared import _vm_call_user_function
        from core.runtime.coordinator import _drive_generator
        from core.runtime.shared.user_call import UserFunctionCall
        from core.runtime.objects.kernel.generator import IbGenerator

        vm = self.context.vm_executor
        if vm is None:
            raise RuntimeError(
                "IbUserFunction.call(): vm_executor not available on ExecutionContext. "
                "Ensure Interpreter.execute_module() has been called before invoking user functions."
            )

        if self.is_generator:
            driver = vm.make_generator_driver(
                UserFunctionCall(self, args, receiver)
            )
            gen_class = vm.registry.get_class("generator")
            if gen_class is None:
                raise RuntimeError("generator class not registered (bootstrap invariant violated)")
            return IbGenerator(gen_class, driver)

        gen = _vm_call_user_function(vm, self, receiver, args)
        return _drive_generator(vm, gen)

    def __repr__(self):
        node_data = self.context.get_node_data(self.node_uid)
        name = node_data.get("name", "unknown")
        return f"<Function '{name}'>"

class IbLLMFunction(IbFunction):
    """
    用户定义的 LLM 函数。

    公理化设计原则
    --------------
    IbLLMFunction 与 IbBehavior 同构：不再在构造时持有 llm_executor 引用。
    call() 通过 ib_class.registry.get_llm_executor().invoke_llm_function() 自主执行。
    """
    def __init__(self, node_uid: str, context: 'IExecutionContext', spec: Optional[IbSpec] = None, module_name: Optional[str] = None):
        super().__init__(context.registry.get_class("callable"))
        self.node_uid = node_uid
        self.context = context
        self._spec = spec
        self.module_name = module_name or context.current_module_name

    @property
    def spec(self) -> Optional[IbSpec]:
        return self._spec if self._spec is not None else self.ib_class.spec

    def call(self, receiver: IbObject, args: List[IbObject]) -> IbObject:
        """执行 LLM 函数。

        **收敛**：本方法为宿主侧薄包装——委托 CPS 权威路径
        ``_vm_invoke_llm_function`` + ``_drive_generator``（TaskScheduler 驱动
        ``_drive_loop_gen``），不再重复模块切换/意图 fork/作用域/实参绑定逻辑
        （消双写）。VM 主路径（leaf.py）本就经 CPS 执行本对象；本方法仅作
        vtable receive('__call__') 后备与宿主/反序列化同步调用。
        """
        from core.runtime.vm.handlers._shared import _vm_invoke_llm_function
        from core.runtime.coordinator import _drive_generator

        vm = self.context.vm_executor
        if vm is None:
            raise RuntimeError(
                "IbLLMFunction.call(): vm_executor not available on ExecutionContext. "
                "Ensure Interpreter.execute_module() has been called before invoking an LLM function."
            )

        gen = _vm_invoke_llm_function(vm, self, receiver, args)
        return _drive_generator(vm, gen)


    def __repr__(self):
        node_data = self.context.get_node_data(self.node_uid)
        name = node_data.get("name", "unknown")
        return f"<LLMFunction '{name}'>"
