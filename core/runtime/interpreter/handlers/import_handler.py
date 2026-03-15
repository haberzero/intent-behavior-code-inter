from typing import Any, Mapping, List, Optional
from .base_handler import BaseHandler
from core.runtime.objects.kernel import IbObject

class ImportHandler(BaseHandler):
    """
    导入节点处理分片。
    """
    def visit_IbImport(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        for alias_uid in node_data.get("names", []):
            alias_data = self.get_node_data(alias_uid)
            if alias_data:
                name = alias_data.get("name")
                asname = alias_data.get("asname")
                mod_inst = self.service_context.module_manager.import_module(name, self.execution_context)
                
                # 绑定到当前作用域：优先使用别名，否则使用原始模块名
                target_name = asname if asname else name
                
                # [FIX] 必须获取符号 UID 并绑定，否则 visit_IbName 无法通过 UID 查找到该模块
                sym_uid = self.get_side_table("node_to_symbol", alias_uid)
                self.runtime_context.define_variable(target_name, mod_inst, is_const=True, uid=sym_uid)
        return self.registry.get_none()

    def visit_IbImportFrom(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
        names = []
        for alias_uid in node_data.get("names", []):
            alias_data = self.get_node_data(alias_uid)
            if alias_data:
                names.append((alias_data.get("name"), alias_data.get("asname")))
        self.service_context.module_manager.import_from(node_data.get("module"), names, self.execution_context)
        return self.registry.get_none()
