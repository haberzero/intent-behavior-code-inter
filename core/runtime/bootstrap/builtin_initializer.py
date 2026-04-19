from typing import Any, List, Dict, Optional, Callable, TYPE_CHECKING
from core.runtime.objects.ib_type_mapping import get_ib_implementation
from ..objects.kernel import IbClass, IbNativeFunction, IbNone, IbObject, IbLLMUncertain
from ..objects.builtins import IbInteger, IbFloat, IbString, IbList, IbTuple, IbDict, IbBehavior, IbBool
from ..objects.intent import IbIntent  # 确保 @register_ib_type("Intent") 在公理自动化绑定前已执行
from core.kernel.registry import KernelRegistry
from core.base.enums import RegistrationState
from core.kernel.issue import InterpreterError
from core.kernel.spec import (
    IbSpec, FuncSpec, ClassSpec, MethodMemberSpec,
    INT_SPEC, STR_SPEC, FLOAT_SPEC, BOOL_SPEC, VOID_SPEC, ANY_SPEC
)
from core.runtime.support.converters import _cast_numeric_to_native, _cast_string_to_native
from core.kernel.factory import create_default_registry
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

def _cast_string_to(ib_str: 'IbString', target_class: Any) -> Any:
    """实现 Spec 中的自动类型转换策略 (Descriptor Identity 版)"""
    target_desc = target_class.spec if hasattr(target_class, 'spec') else None
    return _cast_string_to_native(ib_str.to_native(), target_desc)

def _cast_numeric_to(ib_num: 'IbObject', target_class: Any) -> Any:
    """数值类型到其他类型的转换 (Descriptor Identity 版)"""
    target_desc = target_class.spec if hasattr(target_class, 'spec') else None
    return _cast_numeric_to_native(ib_num.to_native(), target_desc)

def initialize_builtin_classes(registry: KernelRegistry) -> Any:
    """
    初始化 IBCI 核心内置类及其 UTS 契约。
    支持多引擎实例隔离。
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
    # 基础类型与实现类的映射已下沉到各实现类的 @register_ib_type 装饰器中
    # 自动创建类并注册
    # 注意：我们必须保证顺序，或者允许多次查找
    # 依赖于 pritmives.py 中的注册顺序 (int before bool)
    
    core_axioms = []
    axiom_registry = metadata_registry.get_axiom_registry()
    if axiom_registry:
        core_axioms = axiom_registry.get_all_names()
    else:
        # Fallback (Safety net) - 仅在极端的 UTS 注册表未对齐时使用
        core_axioms = ["int", "str", "float", "bool", "list", "dict", "None", "behavior", "deferred", "callable", "bound_method", "auto", "any", "void", "llm_call_result"]
    
    # 自动创建类并注册
    ib_classes = {}
    
    # 确保 enum 在 core_axioms 中
    if "enum" not in core_axioms:
        core_axioms = core_axioms + ["enum"]
    
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

    # 获取引用以便后续绑定 (保持兼容性)
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
    from core.runtime.objects.kernel import IbClass, IbNativeFunction
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
        self_native = self_value.to_native() if self_value and hasattr(self_value, 'to_native') else self_value
        
        # 获取 other 的值（可能是另一个 Mood 实例或枚举字面量）
        if hasattr(other, 'fields') and "_value" in other.fields:
            other_value = other.fields.get("_value")
            other_native = other_value.to_native() if hasattr(other_value, 'to_native') else other_value
        elif hasattr(other, 'to_native'):
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

    # ------------------------------

    # 4. 注册 None 单例 (Per-registry)
    registry.register_none(IbNone(none_class), token)
    _reg_native(none_class, '__to_prompt__', lambda self: "None")
    _reg_native(none_class, 'to_bool', lambda self: 0)

    # 5. 注册 LLM 不确定结果单例 (IbLLMUncertain)
    registry.register_llm_uncertain(IbLLMUncertain(none_class), token)

    # 4. 注册特殊逻辑 (Axiom 无法完全自动化的部分)
    _reg_native(integer_class, '__to_prompt__', lambda self: str(self.to_native()))
    
    # int(x) 构造函数/转换逻辑
    def _int_call(self, *args):
        if not args: return self.registry.box(0)
        return args[0].receive('cast_to', [self])
    _reg_native(integer_class, '__call__', _int_call, unbox=False)
    
    # Float
    _reg_native(float_class, '__to_prompt__', lambda self: str(self.to_native()))

    # float(x) 构造函数/转换逻辑
    def _float_call(self, *args):
        if not args: return self.registry.box(0.0)
        return args[0].receive('cast_to', [self])
    _reg_native(float_class, '__call__', _float_call, unbox=False)

    # String
    _reg_native(string_class, '__to_prompt__', lambda self: self.to_native())
    _reg_native(string_class, '__getitem__', lambda self, key: self.__getitem__(key), unbox=False)

    # range(start, stop, step) 构造函数
    def _range_impl(reg, *args):
        native_args = [a.to_native() for a in args]
        return reg.box(list(range(*native_args)))
    
    _reg_native(bootstrapper.get_class("Object"), "range", _range_impl, unbox=False)
    
    # str(x) 构造函数/转换逻辑
    def _str_call(self, *args):
        if not args: return self.registry.box("")
        return args[0].receive('__to_prompt__', [])
    _reg_native(string_class, '__call__', _str_call, unbox=False)

    _reg_native(list_class, '__to_prompt__', lambda self: "[" + ", ".join(e.receive('__to_prompt__', []).to_native() for e in self.elements) + "]")
    _reg_native(list_class, 'to_list', lambda self: self.elements)
    _reg_native(list_class, 'len', lambda self: self.len())

    # Tuple
    tuple_class = ib_classes.get("tuple")
    if tuple_class:
        _reg_native(tuple_class, '__to_prompt__', lambda self: "(" + ", ".join(e.receive('__to_prompt__', []).to_native() for e in self.elements) + ")")
        _reg_native(tuple_class, 'to_list', lambda self: list(self.elements))
        _reg_native(tuple_class, 'len', lambda self: self.len())

    # Dict
    _reg_native(dict_class, '__to_prompt__', lambda self: "{" + ", ".join(f'"{k}": {v.receive("__to_prompt__", []).to_native()}' for k, v in self.fields.items()) + "}")
    _reg_native(dict_class, 'len', lambda self: self.len())
    
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
    from core.runtime.objects.intent_stack import IbIntentStack

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

    registry.register_builtin_instance("IntentStack", IbIntentStack(intent_stack_class))

    # 5.6 注册 intent_context 内置类（OOP MVP — is_class=True）
    # 允许 IBCI 用户代码显式创建和操作意图上下文对象：
    #   intent_context ctx = intent_context()
    #   ctx.push("用中文回复")
    #   ctx.fork() → 新的 intent_context 实例（拷贝）
    intent_context_class = ib_classes.get("intent_context")
    if intent_context_class:
        from core.runtime.objects.intent_context import IbIntentContext
        from core.runtime.objects.intent import IbIntent
        from core.kernel.intent_logic import IntentMode, IntentRole

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
            content_str = content_obj.to_native() if hasattr(content_obj, 'to_native') else str(content_obj)
            tag_str = None
            if len(args) >= 2:
                tag_obj = args[1]
                tag_str = tag_obj.to_native() if hasattr(tag_obj, 'to_native') else None
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

        _reg_native(intent_context_class, '__init__', _ic_init, unbox=False)
        _reg_native(intent_context_class, 'push', _ic_push, unbox=False)
        _reg_native(intent_context_class, 'pop', _ic_pop, unbox=False)
        _reg_native(intent_context_class, 'fork', _ic_fork, unbox=False)
        _reg_native(intent_context_class, 'resolve', _ic_resolve, unbox=False)
        _reg_native(intent_context_class, 'merge', _ic_merge, unbox=False)
        _reg_native(intent_context_class, 'clear', _ic_clear, unbox=False)

    # 6. 封印注册表结构 (Active Defense)
    registry.seal_structure(token)

    # 跃迁到 STAGE_3_PLUGIN_METADATA
    registry.set_state_level(RegistrationState.STAGE_3_PLUGIN_METADATA.value, token)
    
    # 清理遗留 Legacy 术语与残留注释
    return token
