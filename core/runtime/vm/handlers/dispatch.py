"""
core.runtime.vm.handlers.dispatch — node_type → handler 查询表。

"""
from core.runtime.vm.handlers.leaf import (
    vm_handle_IbConstant,
    vm_handle_IbName,
    vm_handle_IbBinOp,
    vm_handle_IbUnaryOp,
    vm_handle_IbAwaitExpr,
    vm_handle_IbYieldExpr,
    vm_handle_IbYieldFromExpr,
    vm_handle_IbBoolOp,
    vm_handle_IbIfExp,
    vm_handle_IbCompare,
    vm_handle_IbCall,
    vm_handle_IbAttribute,
    vm_handle_IbSubscript,
    vm_handle_IbTuple,
    vm_handle_IbListExpr,
    vm_handle_IbDict,
    vm_handle_IbSlice,
    vm_handle_IbCastExpr,
    vm_handle_IbFilteredExpr,
)
from core.runtime.vm.handlers.control_flow import (
    vm_handle_IbPass,
    vm_handle_IbExprStmt,
    vm_handle_IbIf,
    vm_handle_IbWhile,
    vm_handle_IbReturn,
    vm_handle_IbBreak,
    vm_handle_IbContinue,
    vm_handle_IbRaise,
    vm_handle_IbSwitch,
    vm_handle_IbFor,
    vm_handle_IbTry,
)
from core.runtime.vm.handlers.assignment import (
    vm_handle_IbAssign,
    vm_handle_IbAugAssign,
    vm_handle_IbGlobalStmt,
    vm_handle_IbNonlocalStmt,
)
from core.runtime.vm.handlers.declarations import (
    vm_handle_IbModule,
    vm_handle_IbFunctionDef,
    vm_handle_IbLLMFunctionDef,
    vm_handle_IbClassDef,
    vm_handle_IbImport,
    vm_handle_IbImportFrom,
)
from core.runtime.vm.handlers.llm_behavior import (
    vm_handle_IbBehaviorExpr,
    vm_handle_IbLambdaExpr,
    vm_handle_IbIntentAnnotation,
    vm_handle_IbIntentStackOperation,
    vm_handle_IbRetry,
)
from core.runtime.vm.handlers.comm import (
    vm_handle_IbChannelExpr,
    vm_handle_IbSlotExpr,
)


# ---------------------------------------------------------------------------
# 注册表
# ---------------------------------------------------------------------------

def build_dispatch_table() -> dict:
    """返回 node_type → generator-handler 的查询表。"""
    return {
        # 表达式
        "IbConstant": vm_handle_IbConstant,
        "IbName": vm_handle_IbName,
        "IbBinOp": vm_handle_IbBinOp,
        "IbUnaryOp": vm_handle_IbUnaryOp,
        "IbAwaitExpr": vm_handle_IbAwaitExpr,
        "IbYieldExpr": vm_handle_IbYieldExpr,
        "IbYieldFromExpr": vm_handle_IbYieldFromExpr,
        "IbBoolOp": vm_handle_IbBoolOp,
        "IbIfExp": vm_handle_IbIfExp,
        "IbCompare": vm_handle_IbCompare,
        "IbCall": vm_handle_IbCall,
        "IbAttribute": vm_handle_IbAttribute,
        "IbSubscript": vm_handle_IbSubscript,
        "IbTuple": vm_handle_IbTuple,
        "IbListExpr": vm_handle_IbListExpr,
        # 表达式求值 handler
        "IbDict": vm_handle_IbDict,
        "IbSlice": vm_handle_IbSlice,
        "IbCastExpr": vm_handle_IbCastExpr,
        "IbFilteredExpr": vm_handle_IbFilteredExpr,
        # 语句
        "IbModule": vm_handle_IbModule,
        "IbPass": vm_handle_IbPass,
        "IbExprStmt": vm_handle_IbExprStmt,
        "IbIf": vm_handle_IbIf,
        "IbWhile": vm_handle_IbWhile,
        "IbReturn": vm_handle_IbReturn,
        "IbBreak": vm_handle_IbBreak,
        "IbContinue": vm_handle_IbContinue,
        "IbAssign": vm_handle_IbAssign,
        # 语句 handler 扩展
        "IbAugAssign": vm_handle_IbAugAssign,
        "IbGlobalStmt": vm_handle_IbGlobalStmt,
        "IbNonlocalStmt": vm_handle_IbNonlocalStmt,
        "IbRaise": vm_handle_IbRaise,
        "IbImport": vm_handle_IbImport,
        "IbImportFrom": vm_handle_IbImportFrom,
        "IbSwitch": vm_handle_IbSwitch,
        "IbFunctionDef": vm_handle_IbFunctionDef,
        "IbLLMFunctionDef": vm_handle_IbLLMFunctionDef,
        "IbClassDef": vm_handle_IbClassDef,
        "IbIntentAnnotation": vm_handle_IbIntentAnnotation,
        "IbIntentStackOperation": vm_handle_IbIntentStackOperation,
        # 剩余节点 handler
        "IbBehaviorExpr": vm_handle_IbBehaviorExpr,
        "IbLambdaExpr": vm_handle_IbLambdaExpr,
        "IbFor": vm_handle_IbFor,
        "IbTry": vm_handle_IbTry,
        "IbRetry": vm_handle_IbRetry,
        # 并发/通信
        "IbChannelExpr": vm_handle_IbChannelExpr,
        "IbSlotExpr": vm_handle_IbSlotExpr,
    }
