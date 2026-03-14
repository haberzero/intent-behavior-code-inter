# core/__init__.py
# 空的 __init__.py 以支持物理隔离，防止顶层包加载强制引入编译器依赖。
# 用户应通过 from core.engine import IBCIEngine 或 from core.compiler.scheduler import Scheduler 显式导入。
