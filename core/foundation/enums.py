from enum import Enum, auto

class PrivilegeLevel(Enum):
    KERNEL = auto()    # 内核级：允许修改核心工厂、封印结构
    EXTENSION = auto() # 扩展级：允许注册普通类、注入元数据
    UNAUTHORIZED = auto()
