from .core import SelfRefPlugin


def create_implementation() -> SelfRefPlugin:
    return SelfRefPlugin()
