from enum import Enum, auto

class RegistrationState(Enum):
    """IES 2.0 注册生命周期状态"""
    STAGE_1_BOOTSTRAP = 1         # 注册 Python 基础原生类
    STAGE_2_CORE_TYPES = 2        # 注入 IBCI 内置基础类契约 (Axioms)
    STAGE_3_PLUGIN_METADATA = 3   # 扫描并加载所有插件的 _spec.py
    STAGE_4_PLUGIN_IMPL = 4       # 加载插件实现并执行 setup()
    STAGE_5_HYDRATION = 5         # 执行用户产物重水合
    STAGE_6_READY = 6             # 解释器就绪，封印状态

class PrivilegeLevel(Enum):
    KERNEL = auto()    # 内核级：允许修改核心工厂、封印结构
    EXTENSION = auto() # 扩展级：允许注册普通类、注入元数据
    UNAUTHORIZED = auto()
