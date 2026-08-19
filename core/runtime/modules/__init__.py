"""
core/runtime/modules/
===================

本目录存放 IBCI **内核原生模块**的 Python 实现。

这些模块在 IBCI 语言中以 `import <name>` 形式暴露给用户，但在 Python 层它们
不是通过 ``ibci_modules/`` 插件机制发现的，而是通过 ``core/engine.py`` 构造期
直接注册到 ``HostInterface``（``Provenance.KERNEL_NATIVE + Visibility.IMPORT_GATED``）。

命名风险警示
------------
- 本目录下的 Python 文件名**不要**与 IBCI 模块名完全同名，以避免 Python import
  shadowing 与概念混淆。
- 例如：IBCI 模块名为 ``fs``，实现文件必须**不是** ``fs.py``，因此当前使用
  ``fs_impl.py``（沿原 ``file_impl.py`` 约定迁移）。
- 如需新增内核原生模块，请在 ``core/engine.py`` 中注册，并选择一个不与 Python
  标准库/内建冲突的实现文件名。
"""
