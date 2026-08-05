from typing import Any, List, Dict, Optional, Callable, TYPE_CHECKING
from core.runtime.objects.ib_type_mapping import get_ib_implementation
from core.runtime.objects.kernel.base import unbox
from ..objects.kernel import IbClass, IbNativeFunction, IbNone, IbObject, IbValue, IbLLMUncertain
from ..objects.primitives import IbInteger, IbFloat, IbString, IbList, IbTuple, IbDict, IbBehavior, IbBool
from ..objects.file_handle import IbFileHandle
from ..objects.media_types import audio_from_file, image_from_file, video_from_file
from ..objects.intent import IbIntent  # 确保 @register_ib_type("Intent") 在公理自动化绑定前已执行
from ..objects.thread import IbThread  # 确保 @register_ib_type("thread") 在公理自动化绑定前已执行（循环导入修复：thread 不再经 primitives 反向再导出）
from ..objects.thread_result import IbThreadResult  # 确保 @register_ib_type("thread_result") 在公理自动化绑定前已执行（同上）
from ..objects.intent_stack import IbIntentStack
from ..objects.intent_context import IbIntentContext
from core.kernel.registry import KernelRegistry
from core.base.enums import RegistrationState
from core.kernel.issue import InterpreterError
from core.kernel.spec import (
    IbSpec,
    TypeDef,
    MethodMemberSpec,
    INT_SPEC,
    STR_SPEC,
    FLOAT_SPEC,
    BOOL_SPEC,
    VOID_SPEC,
    ANY_SPEC,
)
from core.kernel.factory import create_default_registry
from core.kernel.intent_logic import IntentMode, IntentRole
from core.runtime.frame import get_current_frame
from ..bootstrapper import Bootstrapper

def _reg_native(ib_class: IbClass, name: str, py_func: Callable, unbox: bool = True):
    """统一注册原生方法的辅助函数"""
    ib_class.register_method(name, IbNativeFunction(py_func, unbox_args=unbox, is_method=True, name=f"{ib_class.name}.{name}", ib_class=ib_class))

def _auto_bind_operators(ib_cls: IbClass, py_impl_cls: Any):
    """ 基于公理声明自动化绑定二元运算符"""
    spec_reg = ib_cls.registry.get_metadata_registry() if ib_cls.registry else None
    axiom = spec_reg.get_axiom(ib_cls.spec) if (spec_reg and ib_cls.spec) else None
    if not axiom: return
    
    operators = axiom.get_operators()
    for op_symbol, magic_name in operators.items():
        if hasattr(py_impl_cls, magic_name):
            # 获取 Python 原生实现 (如 IbInteger.__add__)
            py_method = getattr(py_impl_cls, magic_name)
            # 绑定为原生方法，运算符通常处理 IbObject 所以 unbox=False
            # 注意：一元运算符 (如 __neg__) 也是同样的逻辑
            _reg_native(ib_cls, magic_name, py_method, unbox=False)

def initialize_primitive_classes(registry: KernelRegistry) -> Any:
    """
    初始化 IBCI 核心原语类（language primitives）及其 UTS 契约。
    支持多引擎实例隔离。

    ``initialize_primitive_classes``，精确表达"语言原语类初始化"语义。
    """
    if registry.is_initialized:
        return None # 已初始化
        
    # 确保处于 STAGE_1_BOOTSTRAP 状态
    registry.verify_level(RegistrationState.STAGE_1_BOOTSTRAP.value)
    
    # 1. 准备 UTS 元数据注册表 (隔离引擎实例)
    # [Active Defense] 贯彻“元数据先行”原则
    metadata_registry = create_default_registry()
    
    # 2. 引导核心类 (Type, Object, callable, IbModule, Intent)
    bootstrapper = Bootstrapper(registry)
    bootstrapper.initialize(metadata_registry)
    token = bootstrapper.token
    
    # 跃迁到 STAGE_2_CORE_TYPES
    registry.set_state_level(RegistrationState.STAGE_2_CORE_TYPES.value, token)
    
    # 注册元数据注册表到 Registry
    registry.register_metadata_registry(metadata_registry, token)

    # 3. 创建核心内置类 (Axiom-Driven Automation)
    # 遍历 AxiomRegistry 自动初始化所有注册的原子类型
    
    # 基础类型映射表 (用于绑定具体的 IbClass 实现)
    # 基础类型与实现类的映射位于各实现类的 @register_ib_type 装饰器中
    # 自动创建类并注册
    # 注意：我们必须保证顺序，或者允许多次查找
    # 依赖于 pritmives.py 中的注册顺序 (int before bool)
    
    # 公理名清单统一从 AxiomRegistry 派生，无硬编码特例/回退列表。
    # register_core_axioms 已在 create_default_registry() 中注册全部原语公理
    # （含 enum/None/Exception/audio/image/video/...），故 get_all_names() 已完备。
    axiom_registry = metadata_registry.get_axiom_registry()
    if axiom_registry is None:
        raise InterpreterError(
            "primitive_initializer: axiom registry unavailable — "
            "create_default_registry() must populate the axiom registry before bootstrap."
        )
    core_axioms = axiom_registry.get_all_names()
    
    # 自动创建类并注册
    ib_classes = {}
    
    for name in core_axioms:
        # 获取描述符 (Bootstrapper 初始化时已经注入了 MetadataRegistry)
        desc = metadata_registry.resolve(name)
        if not desc: continue
            
        # 创建类
        parent = "Object"
        axiom = metadata_registry.get_axiom(desc) if desc else None
        if axiom:
            # 从公理中自动提取继承关系，消除硬编码判定
            parent = axiom.get_parent_axiom_name() or "Object"
        
        ib_cls = registry.create_subclass(name, desc, parent_name=parent)
        ib_classes[name] = ib_cls
        
    # [Axiom-Driven Automation] 能力注入
    # 遍历公理中定义的所有方法，并从 IbObject 实现类中自动查找并绑定同名方法
    for name, ib_cls in ib_classes.items():
        desc = ib_cls.spec
        axiom = metadata_registry.get_axiom(desc) if desc else None
        if axiom:
            methods = axiom.get_method_specs()
            # 从全局类型注册表获取实现类，消除硬编码映射
            py_impl_cls = get_ib_implementation(name)
            if py_impl_cls:
                for method_name in methods:
                    if hasattr(py_impl_cls, method_name):
                        # 获取 Python 实现的方法
                        py_method = getattr(py_impl_cls, method_name)
                        # 绑定为原生方法
                        _reg_native(ib_cls, method_name, py_method, unbox=False)
                
                # 自动化运算符绑定
                _auto_bind_operators(ib_cls, py_impl_cls)

    # 获取引用以便后续绑定
    integer_class = ib_classes.get("int")
    float_class = ib_classes.get("float")
    string_class = ib_classes.get("str")
    list_class = ib_classes.get("list")
    dict_class = ib_classes.get("dict")
    slice_class = ib_classes.get("slice")
    none_class = ib_classes.get("None")
    bool_class = ib_classes.get("bool")
    
    # 特殊：module 类 (Bootstrapper 已经创建过一次)
    module_class = registry.create_subclass("module", metadata_registry.resolve("module"))
    
    # 在 runtime registry 中也创建 Enum 类（继承 Object）
    # 注意：Enum 的元数据描述符已在 factory.py 中通过 ENUM_DESCRIPTOR 正确注册
    object_class = ib_classes.get("Object")
    enum_class = IbClass(name="Enum", parent=object_class, registry=registry)
    
    # [Enum Hook] 为 Enum 类注册 __init__ 方法
    def enum_init_impl(receiver, *init_args):
        """Enum.__init__ 实现：设置 _value 字段"""
        if len(init_args) > 0:
            receiver.fields["_value"] = init_args[0]
        return registry.get_none()
    
    init_method = IbNativeFunction(
        enum_init_impl,
        unbox_args=False,
        is_method=True,
        ib_class=enum_class,
        name="__init__"
    )
    enum_class.register_method("__init__", init_method)
    
    # [Enum Hook] 为 Enum 类注册 __eq__ 方法
    def enum_eq_impl(receiver, *eq_args):
        """Enum.__eq__ 实现：比较 _value 字段"""
        if len(eq_args) < 1:
            return registry.box(False)
        other = eq_args[0]
        
        # 获取 receiver 的 _value
        self_value = receiver.fields.get("_value") if hasattr(receiver, 'fields') else None
        self_native = self_value.to_native() if self_value and isinstance(self_value, IbObject) else self_value
        
        # 获取 other 的值（可能是另一个 Mood 实例或枚举字面量）
        if hasattr(other, 'fields') and "_value" in other.fields:
            other_value = other.fields.get("_value")
            other_native = unbox(other_value)
        elif isinstance(other, IbObject):
            other_native = other.to_native()
        else:
            return registry.box(False)
        
        return registry.box(self_native == other_native)
    
    eq_method = IbNativeFunction(
        enum_eq_impl,
        unbox_args=False,
        is_method=True,
        ib_class=enum_class,
        name="__eq__"
    )
    enum_class.register_method("__eq__", eq_method)
    
    registry.register_class("Enum", enum_class, registry._kernel_token, metadata_registry.resolve("Enum"))
    
    # 4. 注册内置全局函数元数据 (供编译器发现)
    factory = metadata_registry.factory
    registry.register_function("print", factory.create_func(
        "print",
        param_type_names=["any"],
        return_type_name="void"
    ), token)

    registry.register_function("len", factory.create_func(
        "len",
        param_type_names=["any"],
        return_type_name="int"
    ), token)

    registry.register_function("range", factory.create_func(
        "range",
        param_type_names=["int"],
        return_type_name="list"
    ), token)

    registry.register_function("range", factory.create_func(
        "range",
        param_type_names=["int", "int"],
        return_type_name="list"
    ), token)

    registry.register_function("range", factory.create_func(
        "range",
        param_type_names=["int", "int", "int"],
        return_type_name="list"
    ), token)

    registry.register_function("get_self_source", factory.create_func(
        "get_self_source",
        param_type_names=[],
        return_type_name="str"
    ), token)

    registry.register_function("type", factory.create_func(
        "type",
        param_type_names=["any"],
        return_type_name="str"
    ), token)

    # ------------------------------

    # 4. 注册 None 单例 (Per-registry)
    registry.register_none(IbNone(none_class), token)
    _reg_native(none_class, '__to_prompt__', lambda self: "None")
    _reg_native(none_class, 'to_bool', lambda self: 0)

    # 5. 注册 LLM 不确定结果单例 (IbLLMUncertain)
    # llm_uncertain 有独立的公理类，
    # __to_prompt__ / to_bool / cast_to 通过公理方法自动绑定。
    llm_uncertain_class = ib_classes.get("llm_uncertain")
    if llm_uncertain_class:
        registry.register_llm_uncertain(IbLLMUncertain(llm_uncertain_class), token)
        _reg_native(llm_uncertain_class, '__to_prompt__', lambda self: "uncertain")
        _reg_native(llm_uncertain_class, 'to_bool', lambda self: 0)
        # 支持与 Uncertain 字面量（以及其他 llm_uncertain 值）进行 == / != 比较
        def _lu_eq(self, other):
            result = isinstance(other, IbLLMUncertain)
            return self.ib_class.registry.box(result)
        def _lu_ne(self, other):
            result = not isinstance(other, IbLLMUncertain)
            return self.ib_class.registry.box(result)
        _reg_native(llm_uncertain_class, '__eq__', _lu_eq, unbox=False)
        _reg_native(llm_uncertain_class, '__ne__', _lu_ne, unbox=False)
    else:
        raise InterpreterError(
            "llm_uncertain axiom is not registered. "
            "Ensure register_core_axioms() is called before primitive initialization."
        )

    # 4. 注册特殊逻辑 (Axiom 无法完全自动化的部分)
    _reg_native(integer_class, '__to_prompt__', lambda self: str(self.to_native()))
    
    # int(x) 构造函数/转换逻辑
    # 注意：receiver 可能是 int 类对象（IbClass），也可能是一个 IbInteger 实例（如 42()）。
    # 使用 self.ib_class.registry 保证两种情况均可访问注册表。
    def _int_call(self, *args):
        reg = self.ib_class.registry
        if not args: return reg.box(0)
        target = self if isinstance(self, IbClass) else self.ib_class
        return args[0].receive('cast_to', [target])
    _reg_native(integer_class, '__call__', _int_call, unbox=False)
    
    # Float
    _reg_native(float_class, '__to_prompt__', lambda self: str(self.to_native()))

    # float(x) 构造函数/转换逻辑
    def _float_call(self, *args):
        reg = self.ib_class.registry
        if not args: return reg.box(0.0)
        target = self if isinstance(self, IbClass) else self.ib_class
        return args[0].receive('cast_to', [target])
    _reg_native(float_class, '__call__', _float_call, unbox=False)

    # String
    _reg_native(string_class, '__to_prompt__', lambda self: self.to_native())
    _reg_native(string_class, 'to_bool', lambda self: len(self.value) > 0)
    _reg_native(string_class, '__getitem__', lambda self, key: self.__getitem__(key), unbox=False)

    # range(start, stop, step) 构造函数
    def _range_impl(reg, *args):
        native_args = [a.to_native() for a in args]
        return reg.box(list(range(*native_args)))
    
    _reg_native(bootstrapper.get_class("Object"), "range", _range_impl, unbox=False)
    
    # str(x) 构造函数/转换逻辑
    def _str_call(self, *args):
        reg = self.ib_class.registry
        if not args: return reg.box("")
        return args[0].receive('__to_prompt__', [])
    _reg_native(string_class, '__call__', _str_call, unbox=False)

    # str.__contains__: 用于 'in' 运算符（右侧为 str 时）
    def _str_contains(self, item):
        sub = item.to_native() if isinstance(item, IbObject) else str(item)
        return self.ib_class.registry.box(sub in self.value)
    _reg_native(string_class, '__contains__', _str_contains, unbox=False)

    _reg_native(list_class, '__to_prompt__', lambda self: "[" + ", ".join(e.receive('__to_prompt__', []).to_native() for e in self.elements) + "]")
    _reg_native(list_class, 'to_list', lambda self: self.elements)
    _reg_native(list_class, 'to_bool', lambda self: len(self.elements) > 0)
    _reg_native(list_class, 'len', lambda self: self.len())

    # list.__contains__: 用于 'in' 运算符（右侧为 list 时）
    def _list_contains(self, item):
        native = unbox(item)
        result = any(el.to_native() == native for el in self.elements)
        return self.ib_class.registry.box(result)
    _reg_native(list_class, '__contains__', _list_contains, unbox=False)

    # Exception: __init__ 存储 message 字段，使 Exception("msg") 可用
    exception_class = ib_classes.get("Exception")
    if exception_class:
        def _exception_init(receiver, *init_args):
            """Exception.__init__: 将首个参数存为 message 字段"""
            if init_args:
                msg_arg = init_args[0]
                receiver.fields["message"] = msg_arg if isinstance(msg_arg, IbObject) else registry.box(str(msg_arg))
            else:
                receiver.fields["message"] = registry.box("")
            return registry.get_none()
        _reg_native(exception_class, '__init__', _exception_init, unbox=False)

    # Tuple
    tuple_class = ib_classes.get("tuple")
    if tuple_class:
        _reg_native(tuple_class, '__to_prompt__', lambda self: "(" + ", ".join(e.receive('__to_prompt__', []).to_native() for e in self.elements) + ")")
        _reg_native(tuple_class, 'to_list', lambda self: list(self.elements))
        _reg_native(tuple_class, 'len', lambda self: self.len())

    # Dict
    _reg_native(dict_class, '__to_prompt__', lambda self: "{" + ", ".join(f'"{k}": {v.receive("__to_prompt__", []).to_native()}' for k, v in self.fields.items()) + "}")
    _reg_native(dict_class, 'to_bool', lambda self: len(self.fields) > 0)
    _reg_native(dict_class, 'len', lambda self: self.len())

    # dict.__contains__: 用于 'in' 运算符（右侧为 dict 时）
    def _dict_contains(self, key):
        k = unbox(key)
        return self.ib_class.registry.box(k in self.fields)
    _reg_native(dict_class, '__contains__', _dict_contains, unbox=False)
    
    # 5. 注册装箱逻辑
    registry.register_boxer(int, lambda reg, v, memo=None: IbInteger.from_native(v, reg.get_class("int")), token)
    registry.register_boxer(bool, lambda reg, v, memo=None: IbBool(v, reg.get_class("bool")), token)
    registry.register_boxer(float, lambda reg, v, memo=None: IbFloat(v, reg.get_class("float")), token)
    registry.register_boxer(str, lambda reg, v, memo=None: IbString(v, reg.get_class("str")), token)
    
    def _box_list(reg, val, memo):
        res = IbList([], reg.get_class("list"))
        memo[id(val)] = res
        res.elements = [reg.box(i, memo) for i in val]
        return res

    def _box_tuple(reg, val, memo):
        # 先创建占位符以处理循环引用
        boxed_elts = tuple(reg.box(i, memo) for i in val)
        res = IbTuple(boxed_elts, reg.get_class("tuple"))
        memo[id(val)] = res
        return res
        
    def _box_dict(reg, val, memo):
        res = IbDict({}, reg.get_class("dict"))
        memo[id(val)] = res
        res.fields = {k: reg.box(v, memo) for k, v in val.items()}
        return res
        
    registry.register_boxer(list, _box_list, token)
    registry.register_boxer(tuple, _box_tuple, token)
    registry.register_boxer(dict, _box_dict, token)

    # 5.5 注册 IntentStack 内置类（公理体系融入）

    intent_stack_class = bootstrapper.get_class("IntentStack")
    intent_stack_desc = metadata_registry.resolve("IntentStack")

    _reg_native(intent_stack_class, 'push', IbIntentStack.push, unbox=False)
    _reg_native(intent_stack_class, 'pop', IbIntentStack.pop, unbox=False)
    _reg_native(intent_stack_class, 'clear', IbIntentStack.clear, unbox=False)
    _reg_native(intent_stack_class, 'get_active', IbIntentStack.get_active, unbox=False)
    _reg_native(intent_stack_class, 'resolve', IbIntentStack.resolve, unbox=False)
    _reg_native(intent_stack_class, '__iter__', IbIntentStack.__iter__, unbox=False)
    _reg_native(intent_stack_class, '__len__', IbIntentStack.__len__, unbox=False)
    _reg_native(intent_stack_class, '__repr__', IbIntentStack.__repr__, unbox=False)

    registry.register_intrinsic_instance("IntentStack", IbIntentStack(intent_stack_class))

    # 5.6 注册 intent_context 内置类（OOP MVP — is_class=True）
    # 允许 IBCI 用户代码显式创建和操作意图上下文对象：
    #   intent_context ctx = intent_context()
    #   ctx.push("用中文回复")
    #   ctx.fork() → 新的 intent_context 实例（拷贝）
    intent_context_class = ib_classes.get("intent_context")
    if intent_context_class:

        def _ic_init(receiver, *args):
            """intent_context() 构造函数：创建空意图上下文。"""
            receiver.fields['_ctx'] = IbIntentContext()
            return registry.get_none()

        def _ic_push(receiver, *args):
            """ctx.push(content) 或 ctx.push(content, tag)：压入持久意图。"""
            ctx = receiver.fields.get('_ctx')
            if not ctx or not args:
                return registry.get_none()
            content_obj = args[0]
            content_str = content_obj.to_native() if isinstance(content_obj, IbObject) else str(content_obj)
            tag_str = None
            if len(args) >= 2:
                tag_obj = args[1]
                tag_str = tag_obj.to_native() if isinstance(tag_obj, IbObject) else None
            intent_cls = registry.get_class("Intent")
            intent = IbIntent(ib_class=intent_cls, content=content_str,
                              mode=IntentMode.APPEND, tag=tag_str, role=IntentRole.DYNAMIC)
            ctx.push(intent)
            return registry.get_none()

        def _ic_pop(receiver, *args):
            """ctx.pop()：弹出并返回栈顶意图内容。"""
            ctx = receiver.fields.get('_ctx')
            if ctx:
                intent = ctx.pop()
                if intent is not None and hasattr(intent, 'content'):
                    return registry.box(intent.content)
            return registry.get_none()

        def _ic_fork(receiver, *args):
            """ctx.fork()：返回新的 intent_context 实例（拷贝当前状态）。"""
            ctx = receiver.fields.get('_ctx')
            new_instance = IbObject(intent_context_class)
            new_instance.fields['_ctx'] = ctx.fork() if ctx else IbIntentContext()
            return new_instance

        def _ic_resolve(receiver, *args):
            """ctx.resolve()：返回当前意图上下文消解后的提示词字符串列表。"""
            ctx = receiver.fields.get('_ctx')
            if not ctx:
                return registry.box([])
            intents = ctx.get_active_intents()
            strings = [i.content for i in intents if hasattr(i, 'content') and i.content]
            return registry.box(strings)

        def _ic_merge(receiver, *args):
            """ctx.merge(other)：将另一个意图上下文的状态合并到 self。"""
            ctx = receiver.fields.get('_ctx')
            if not ctx or not args:
                return registry.get_none()
            other = args[0]
            other_ctx = other.fields.get('_ctx') if hasattr(other, 'fields') else None
            if other_ctx:
                ctx.merge(other_ctx)
            return registry.get_none()

        def _ic_clear(receiver, *args):
            """ctx.clear()：清空持久意图栈。"""
            ctx = receiver.fields.get('_ctx')
            if ctx:
                ctx.set_intent_top(None)
            return registry.get_none()

        def _ic_combine(receiver, *args):
            """ctx.combine(other)：将另一个 intent_context 的状态**叠加**到 self（加法式合并）。

            与 ``merge``（替换语义）的区别：``combine`` 保留 self 原有意图，把 ``other``
            的持久意图栈追加压入栈顶，smear_queue 追加，override 取 other 的。
            参见 :meth:`IbIntentContext.combine`。
            """
            ctx = receiver.fields.get('_ctx')
            if not ctx or not args:
                return registry.get_none()
            other = args[0]
            other_ctx = other.fields.get('_ctx') if hasattr(other, 'fields') else None
            if other_ctx is not None and hasattr(ctx, 'combine'):
                ctx.combine(other_ctx)
            return registry.get_none()

        def _ic_to_prompt(receiver, *args):
            """ctx.__to_prompt__()：渲染为 LLM 提示词友好文本（供 `$ctx` 段插值）。"""
            ctx = receiver.fields.get('_ctx')
            if ctx is None or not hasattr(ctx, 'to_prompt'):
                return registry.box("")
            return registry.box(ctx.to_prompt())

        _reg_native(intent_context_class, '__init__', _ic_init, unbox=False)
        _reg_native(intent_context_class, 'push', _ic_push, unbox=False)
        _reg_native(intent_context_class, 'pop', _ic_pop, unbox=False)
        _reg_native(intent_context_class, 'fork', _ic_fork, unbox=False)
        _reg_native(intent_context_class, 'resolve', _ic_resolve, unbox=False)
        _reg_native(intent_context_class, 'merge', _ic_merge, unbox=False)
        _reg_native(intent_context_class, 'combine', _ic_combine, unbox=False)
        _reg_native(intent_context_class, 'clear', _ic_clear, unbox=False)
        _reg_native(intent_context_class, '__to_prompt__', _ic_to_prompt, unbox=False)

        # --- 作用域控制方法（可在类上或实例上调用，均操作当前帧的意图上下文）---
        #
        # 设计说明：这三个方法不操作 receiver（实例字段 _ctx），
        # 而是直接操作当前执行帧的 _intent_ctx（当前作用域生效的意图上下文）。
        # 因此既可以写 intent_context.clear_inherited()，
        # 也可以写 ctx.clear_inherited()，效果完全相同。
        #
        # 使用场景：函数内部显式屏蔽/替换从调用者继承来的意图上下文：
        #
        #   func process():
        #       intent_context.clear_inherited()   # 清空从调用者继承的意图
        #       @+ "只以 JSON 格式回复"
        #       str r = @~ 处理数据 ~              # 只见本函数局部意图
        #
        #   func process_with_ctx(intent_context ctx):
        #       intent_context.use(ctx)            # 用传入的上下文替换当前作用域
        #       str r = @~ 处理数据 ~              # 只见 ctx 中的意图
        #
        # ContextVar 路径：通过 get_current_frame() 获取当前 RuntimeContextImpl，
        # 与 IbUserFunction.call() 使用相同的机制，安全且协程/线程隔离。

        def _ic_clear_inherited(receiver, *args):
            """
            intent_context.clear_inherited()
            清空当前函数作用域从调用者继承的持久意图栈。
            调用后，当前作用域的 @+ 意图（即 _intent_top 链表）被重置为空。
            函数内部的 @+ 操作从干净的起点开始，不受调用者意图干扰。

            复用 ``RuntimeContextImpl.clear_inherited_intents()``，
            同时重建活跃实例指针（共享 _ctx 引用），使 OOP 路径与语法路径保持同源。
            """
            frame = get_current_frame()
            if frame is not None and hasattr(frame, 'clear_inherited_intents'):
                frame.clear_inherited_intents()
            return registry.get_none()

        def _ic_use(receiver, *args):
            """
            intent_context.use(ctx)
            以给定的 intent_context 实例替换当前作用域的意图上下文。
            等效于：当前作用域的意图栈 = fork(ctx)（不是引用，是拷贝）。
            调用后，当前作用域所有 LLM 调用看到的意图完全来自 ctx 的内容。

            ``use_intent_context`` 会同步更新帧级活跃实例指针，
            使后续 ``@+``/``@-`` 与 OOP 操作落在同一底层 IbIntentContext 上。
            """
            frame = get_current_frame()
            if frame is None or not hasattr(frame, 'use_intent_context'):
                return registry.get_none()
            if not args:
                return registry.get_none()
            frame.use_intent_context(args[0])
            return registry.get_none()

        def _ic_get_current(receiver, *args):
            """
            intent_context.get_current()
            返回当前作用域正在生效的意图上下文的快照（fork 副本）。
            返回值是一个新的 intent_context 实例，可检查、可保存，不影响当前作用域。

            优先 fork 帧活跃实例指针 ``_active_intent_ibobj``——
            该指针的 ``_ctx`` 与帧的 ``_intent_ctx`` 共享引用，因此其 fork
            等价于 ``_intent_ctx.fork()``，但保留了"用户命名身份"的可观察性
            （调试器可由此追踪当前帧正在使用的策略对象身份）。
            """
            frame = get_current_frame()
            new_instance = IbObject(intent_context_class)
            if frame is not None and hasattr(frame, 'get_active_intent_ibobj'):
                active = frame.get_active_intent_ibobj()
                if active is not None and hasattr(active, 'fields'):
                    active_ctx = active.fields.get('_ctx')
                    if active_ctx is not None and hasattr(active_ctx, 'fork'):
                        new_instance.fields['_ctx'] = active_ctx.fork()
                        return new_instance
            if frame is not None and hasattr(frame, 'fork_intent_snapshot'):
                new_instance.fields['_ctx'] = frame.fork_intent_snapshot()
            else:
                new_instance.fields['_ctx'] = IbIntentContext()
            return new_instance

        _reg_native(intent_context_class, 'clear_inherited', _ic_clear_inherited, unbox=False)
        _reg_native(intent_context_class, 'use', _ic_use, unbox=False)
        _reg_native(intent_context_class, 'get_current', _ic_get_current, unbox=False)

    # 5b'. thread 类型构造函数注册
    #
    # thread 类方法（start/join/cancel/is_done）已由 ThreadAxiom → axiom-driven
    # auto-bind 自动绑定（从 get_ib_implementation("thread") = IbThread）。
    # 此处补充 __init__ 构造：接收 callable/args 关键字参数，创建 IbThread 实例。
    # 参数名 ``callable``（非关键字，避免与 ``fn``/``func`` 关键字碰撞）。
    _thread_class = ib_classes.get("thread")
    if _thread_class is not None:
        def _thread_init(receiver, *args):
            """thread(callable=..., args=...) 构造函数：创建线程并启动。

            线程状态直接写入 receiver 槽位（与 IbThread 方法读取的槽位一致），
            使 axiom 自动绑定的 start/join/cancel/is_done 在实例上直接工作。

            实参容器（args=[...]）按 IbList 元素直接取出（保持 IbObject 身份，
            不 to_native——否则 chan/slot 等值对象会退化为原生快照丢失身份）。
            """
            from core.runtime.coordinator import get_runtime_coordinator

            func_obj = args[0] if len(args) > 0 else registry.get_none()
            args_obj = args[1] if len(args) > 1 else registry.box([])
            if isinstance(args_obj, IbValue) and args_obj.ib_class.name == "list":
                arg_list = list(args_obj.elements)
            elif isinstance(args_obj, IbObject):
                native_args = args_obj.to_native()
                arg_list = list(native_args) if isinstance(native_args, (list, tuple)) else []
                for i, a in enumerate(arg_list):
                    if not isinstance(a, IbObject):
                        arg_list[i] = registry.box(a)
            else:
                arg_list = []
            execution_context = registry.get_execution_context()
            vm = execution_context.vm_executor if execution_context is not None else None
            coordinator = get_runtime_coordinator(vm) if vm is not None else None
            if coordinator is None:
                raise InterpreterError(
                    "thread: coordinator unavailable (no active execution context)"
                )
            # receiver 经 _create_blank 为真实 IbThread，直接写槽位；
            # 空槽位（_spawned=None/_state=idle）已由 IbThread.__init__ 初始化。
            receiver._coordinator = coordinator
            receiver._callable = func_obj
            receiver._args = arg_list
            receiver._ensure_started()
            return registry.get_none()

        _thread_init_meta = [
            ("callable", "POSITIONAL_OR_KEYWORD", None),
            ("args", "POSITIONAL_OR_KEYWORD", None),
        ]
        _reg_native(_thread_class, "__init__", _thread_init, unbox=False)
        _thread_class.lookup_method("__init__").param_meta = _thread_init_meta

    # 5b. 多模态类型方法注册 (audio / image / video)
    #
    # 作为普通类名注册，通过 axiom → primitive_initializer 标准路径。
    # media 类型是 file_handle 的磁盘型子类；
    # 所有 I/O 与 base64 编码下放到 runtime 层的 ``__path_payload_prompt__``。
    for _media_type_name in ("audio", "image", "video"):
        _media_class = registry.get_class(_media_type_name)
        if _media_class is not None:
            # 注意：必须用 SpecRegistry.get_axiom(spec)（内部经 spec.get_base_name() 取名），
            # 而非 AxiomRegistry.get_axiom(spec)（后者期望字符串名，传入 IbSpec 会返回 None）。
            _media_axiom = metadata_registry.get_axiom(
                metadata_registry.resolve(_media_type_name)
            ) if metadata_registry else None

            # 绑定循环变量为默认参数，避免 lambda 晚绑定闭包 bug
            _type_name = _media_type_name

            # __to_prompt__: 返回文本描述（供纯文本提示词路径使用）
            _reg_native(_media_class, '__to_prompt__',
                        lambda self, tn=_type_name: f"[{tn} handle: {self.backing.path}]" if self.backing else f"[empty {tn}]")

            # __payload_prompt__: 委托到公理的 __payload_prompt__，公理再下沉到
            # runtime 的 __path_payload_prompt__（零 I/O 在公理层）。
            if _media_axiom and hasattr(_media_axiom, '__payload_prompt__'):
                _axiom_ref = _media_axiom
                _reg_native(_media_class, '__payload_prompt__',
                            lambda self, ax=_axiom_ref: ax.__payload_prompt__(self), unbox=False)

            # __path_payload_prompt__: 实际构造 content block 的 runtime 协议方法。
            _py_impl_cls = get_ib_implementation(_type_name)
            if _py_impl_cls and hasattr(_py_impl_cls, '__path_payload_prompt__'):
                _pp_method = _py_impl_cls.__path_payload_prompt__
                _reg_native(_media_class, '__path_payload_prompt__', _pp_method, unbox=False)

            # media 静态构造入口 audio.from_file / image.from_file / video.from_file。
            # IBCI 调用 audio.from_file(path) 时 receiver 是 audio IbClass，因此 Python 函数
            # 第一个参数是 IbClass，第二个参数是原生 path 字符串（unbox=True）。
            if _type_name == "audio":
                _reg_native(_media_class, 'from_file', audio_from_file, unbox=True)
            elif _type_name == "image":
                _reg_native(_media_class, 'from_file', image_from_file, unbox=True)
            elif _type_name == "video":
                _reg_native(_media_class, 'from_file', video_from_file, unbox=True)

    # 5c. file_handle 类型方法注册
    #
    # file_handle 为 kernel-native 类型，import-gated。
    # 声明 storage_model = DISK_BACKED，由 deep_clone / RuntimeSerializer
    # 自动走磁盘协议族（__clone_ref__ / __to_descriptor__ / __from_descriptor__）。
    _file_handle_class = registry.get_class("file_handle")
    if _file_handle_class is not None:
        # 用户可见原生方法已由公理自动化绑定（path/read/read_bytes/close/cast_to）。
        # file_handle 实例只读，无 write() 方法。
        # 此处绑定磁盘协议族与 prompt 协议。
        _reg_native(_file_handle_class, '__materialize__', IbFileHandle.__materialize__, unbox=False)
        _reg_native(_file_handle_class, '__path_payload_prompt__', IbFileHandle.__path_payload_prompt__, unbox=False)
        _reg_native(_file_handle_class, '__clone_ref__', IbFileHandle.__clone_ref__, unbox=False)
        _reg_native(_file_handle_class, '__to_descriptor__', IbFileHandle.__to_descriptor__, unbox=False)
        _reg_native(_file_handle_class, '__from_descriptor__', IbFileHandle.__from_descriptor__, unbox=False)
        _reg_native(_file_handle_class, '__payload_prompt__',
                    lambda self: self.receive('__path_payload_prompt__', []), unbox=False)

    # 6. 封印注册表结构 (Active Defense)
    registry.seal_structure(token)

    # 跃迁到 STAGE_3_PLUGIN_METADATA
    registry.set_state_level(RegistrationState.STAGE_3_PLUGIN_METADATA.value, token)
    
    return token
