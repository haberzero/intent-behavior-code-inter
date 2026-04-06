from enum import Enum, auto

class PrivilegeLevel(Enum):
    KERNEL = auto()
    EXTENSION = auto()
    UNAUTHORIZED = auto()

class RegistrationState(Enum):
    STAGE_1_BOOTSTRAP = 1
    STAGE_2_CORE_TYPES = 2
    STAGE_3_PLUGIN_METADATA = 3
    STAGE_4_PLUGIN_IMPL = 4
    STAGE_5_HYDRATION = 5
    STAGE_6_PRE_EVAL = 6
    STAGE_7_READY = 7
