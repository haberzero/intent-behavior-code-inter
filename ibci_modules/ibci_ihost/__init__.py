from .core import IHostPlugin


def create_implementation() -> IHostPlugin:
    return IHostPlugin()
