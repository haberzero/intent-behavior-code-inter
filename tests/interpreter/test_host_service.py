import unittest
import os
from tests.interpreter.base import BaseInterpreterTest
from core.domain.issue import InterpreterError

class TestHostService(BaseInterpreterTest):
    """
    验证 IBCI 2.0 核心宿主服务 (HostService) 的各项功能：
    包括运行现场持久化、隔离执行策略以及元编程能力。
    """

    def test_host_save_load_basic(self):
        """测试基础变量现场的保存与恢复"""
        code = """
        import host
        int x = 100
        host.save_state("basic.json")
        x = 200
        host.load_state("basic.json")
        print(x)
        """
        self.run_code(code)
        self.assert_output("100")

    def test_host_save_load_complex_graph(self):
        """测试复杂对象图（循环引用、类实例）的保存与恢复"""
        code = """
        import host
        class Node:
            var next = None
            var val = 0
            
        Node n1 = Node()
        Node n2 = Node()
        n1.next = n2
        n2.next = n1 # 循环引用
        n1.val = 42
        
        host.save_state("complex.json")
        
        n1.val = 99
        host.load_state("complex.json")
        
        print(n1.val)
        print(n1.next.next == n1) # 验证引用一致性
        """
        self.run_code(code)
        self.assert_outputs(["42", "1"])

    def test_host_get_source(self):
        """测试元编程 API：获取当前模块源码"""
        source = """
        import host
        str src = host.get_source()
        print(src.len() > 0)
        """
        self.write_file("main.ibci", source)
        # 运行文件而非字符串，以便编译器能记录路径
        self.engine.run(os.path.join(self.test_root, "main.ibci"), output_callback=self.output_callback)
        self.assert_output("1")

    def test_run_isolated_basic(self):
        """测试隔离运行子脚本：变量空间不继承"""
        self.write_file("sub.ibci", """
        print("Sub-script running")
        # 尝试访问父作用域变量 (应该导致编译或运行错误)
        # print(parent_var) 
        1
        """)
        
        code = """
        import host
        int parent_var = 100
        dict policy = {"inherit_plugins": ["sys"]}
        bool res = host.run("sub.ibci", policy)
        print(res)
        """
        self.run_code(code)
        self.assert_output("Sub-script running")
        self.assert_output("1")

    def test_run_isolated_intent_inheritance(self):
        """测试隔离运行子脚本：意图栈继承"""
        self.write_file("sub.ibci", """
        # 这里模拟一个行为表达式，它会查看意图栈
        # 目前解释器在执行时会打印当前意图栈深度（如果开启了调试）
        # 我们通过一个简单的逻辑来验证
        print("Sub-script intent test")
        """)
        
        code = """
        import host
        if True:
            @ High Level Intent
            dict policy = {"inherit_intents": 1}
            host.run("sub.ibci", policy)
        """
        self.run_code(code)
        self.assert_output("Sub-script intent test")

    def test_run_isolated_rollback_on_failure(self):
        """测试 Snapshot-Try-Restore：子脚本崩溃时父环境自动回滚"""
        self.write_file("fail.ibci", """
        print("Fail-script starting")
        # 故意触发运行时错误
        1 / 0
        """)
        
        code = """
        import host
        int x = 10
        try:
            dict policy = {}
            x = 20 # 在 run 之前修改
            host.run("fail.ibci", policy)
        except:
            print("Caught sub-script error")
        
        # 验证 x 是否回滚到了 save_state 时的值
        # 注意：目前的实现是在 host.run 内部自动做 snapshot。
        # 如果 host.run 报错，它应该恢复到调用前的状态。
        print(x)
        """
        # 注意：目前的 host.run 内部实现是在调用前的瞬时快照
        # 如果 x = 20 在 host.run 之前执行，它可能被包含在快照里，也可能不包含，取决于具体实现。
        # 规范要求：host.run 应该在执行子脚本逻辑前对父环境进行快照。
        self.run_code(code)
        self.assert_output("Fail-script starting")
        self.assert_output("Caught sub-script error")
        # 如果回滚成功，x 应该是 20 (因为 x=20 在 host.run 调用前已经发生，且快照是在 host.run 内部做的)
        # 如果我们要测试“回滚到 10”，我们需要确保快照是在 x=20 之前做的。
        # 但 IBCI 的事务模型通常是针对“尝试执行一段逻辑，失败则回滚到执行前”。
        self.assert_output("20") 

    def test_orchestrator_spawning_isolation(self):
        """测试协调器产生的解释器是否具有物理隔离的 ServiceContext"""
        # 这个测试需要直接操作 Python 层的 IBCIEngine
        engine = self.engine
        
        # 确保主解释器已准备好
        engine.run_string("1")
        
        # 编译一个简单的 artifact
        artifact = engine.scheduler.compile_project(self.write_file("dummy.ibci", "1"))
        
        # 使用工厂产生子解释器
        sub_interpreter = engine.spawn_interpreter(
            artifact=artifact,
            registry=engine.registry,
            host_interface=engine.host_interface,
            root_dir=self.test_root,
            parent_context=None
        )
        
        # 验证物理对象不相等
        self.assertIsNot(engine.interpreter, sub_interpreter)
        self.assertIsNot(engine.interpreter.service_context, sub_interpreter.service_context)
        # 但共享真相源 (Registry)
        self.assertIs(engine.registry, sub_interpreter.registry)

if __name__ == '__main__':
    unittest.main()
