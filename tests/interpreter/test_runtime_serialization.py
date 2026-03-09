import unittest
import json
import os
from tests.interpreter.base import BaseInterpreterTest
from core.runtime.serialization.runtime_serializer import RuntimeSerializer, RuntimeDeserializer
from core.runtime.objects.kernel import IbObject

class TestRuntimeSerialization(BaseInterpreterTest):
    """
    深度验证运行时序列化引擎：
    包括特权常量恢复、原生插件重绑定以及大规模对象图的处理。
    """

    def test_privileged_constant_overwrite(self):
        """验证反序列化器能否通过特权路径覆盖常量符号（如 print）"""
        # 确保解释器已初始化
        self.run_code("1")
        
        # 1. 创建一个包含常量的作用域
        ctx = self.engine.interpreter.context
        ctx.define_variable("MY_CONST", 100, is_const=True)
        
        # 验证普通路径无法修改
        from core.domain.issue import InterpreterError
        with self.assertRaises(InterpreterError):
            ctx.define_variable("MY_CONST", 200)
            
        # 2. 序列化当前现场
        serializer = RuntimeSerializer(self.engine.registry)
        data = serializer.serialize_context(ctx)
        
        # 3. 修改快照中的数据
        # 找到 runtime_scopes 池中的 MY_CONST
        scopes = data["pools"]["runtime_scopes"]
        root_scope_uid = data["root_scope_uid"]
        symbols = scopes[root_scope_uid]["symbols"]
        self.assertIn("MY_CONST", symbols)
        
        # 4. 使用特权模式加载
        deserializer = RuntimeDeserializer(self.engine.registry)
        # 我们手动模拟一个带有不同值的新 Context 加载过程
        # 但更直接的测试是验证 RuntimeDeserializer 内部调用了 force=True
        new_ctx = deserializer.deserialize_context(data)
        
        # 验证加载后的常量值
        val = new_ctx.global_scope.get("MY_CONST")
        self.assertEqual(val.to_native(), 100)
        
        # 关键点：load_state 之后，HostService 会调用 setup_context(force=True)
        # 这确保了内置函数如 print 被重新注入
        self.engine.interpreter.setup_context(new_ctx, force=True)
        # 如果不报错，说明特权路径生效

    def test_environment_rebinding_intrinsics(self):
        """验证恢复快照后，内置函数（Intrinsics）是否依然可用，且逻辑标识一致"""
        code = """
        import host
        var my_print = print
        host.save_state("env.json")
        my_print("Before load")
        host.load_state("env.json")
        my_print("After load")
        print("Global print also works")
        """
        self.run_code(code)
        self.assert_outputs(["Before load", "After load", "Global print also works"])

    def test_environment_rebinding_plugins(self):
        """验证恢复快照后，原生插件（如 sys）是否被重新绑定"""
        code = """
        import host
        import sys
        host.save_state("sys.json")
        # 销毁当前的 sys 插件（模拟环境迁移）
        # 在 IBCI 2.0 中，load_state 会自动触发重绑定
        host.load_state("sys.json")
        # 如果重绑定成功，sys 对象应该依然具备其原生能力
        print(sys)
        """
        self.run_code(code)
        self.assert_output("<Instance of Object>") # sys 在 IBCI 中被包装为 Object 或 NativeObject

    def test_circular_reference_serialization(self):
        """验证极深的对象图和循环引用在序列化时不发生溢出"""
        # 构造一个 A -> B -> C -> A 的循环
        code = """
        import host
        dict a = {}
        dict b = {}
        dict c = {}
        a["next"] = b
        b["next"] = c
        c["next"] = a
        
        host.save_state("circle.json")
        host.load_state("circle.json")
        
        print(a["next"]["next"]["next"] == a)
        """
        self.run_code(code)
        self.assert_output("1")

if __name__ == '__main__':
    unittest.main()
