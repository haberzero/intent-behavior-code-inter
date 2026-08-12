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


class Provenance(Enum):
    """Where a symbol/spec originates from.

    Replaces the overloaded ``is_user_defined`` bool and the flat
    ``metadata["is_intrinsic"]`` / ``metadata["is_external_module"]`` keys.
    """

    KERNEL_NATIVE = auto()      # Core language: int/str/list/print + kernel-bridged modules
    AXIOM_PROVIDED = auto()     # Provided by an axiom vtable (e.g. late-hydrated methods)
    USER_DEFINED = auto()       # User code / user-defined classes and functions
    EXTERNAL_MODULE = auto()    # Introduced via ``import`` from an external plugin/module

    def compatible_with(self, other: "Provenance") -> bool:
        """System origins can coexist; user-defined names must stay unique."""
        return self is not Provenance.USER_DEFINED and other is not Provenance.USER_DEFINED


class Visibility(Enum):
    """Whether a symbol is visible without an explicit import."""

    PRELUDE_VISIBLE = auto()    # Automatically visible (e.g. print, len, primitive types)
    IMPORT_GATED = auto()       # Requires an explicit ``import``
    SCOPE_PRIVATE = auto()      # Not exported from its defining scope


class StorageModel(Enum):
    """Type-level backing model for IbSpec.

    Only lands the field; dispatch logic is intentionally disabled
    until the disk-backed storage stage.
    """

    MEMORY_BACKED = auto()      # Default for all current types
    DISK_BACKED = auto()        # FileHandle / media
