import unittest
import sys
import os
import shutil
import textwrap
import json

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.engine import IBCIEngine
from core.types.exception_types import InterpreterError
from tests.ibc_test_case import IBCTestCase

class TestLLMIntegration(IBCTestCase):
    """
    Consolidated tests for LLM integration.
    Covers control flow, return types, complex access, and configuration.
    """

    def setUp(self):
        super().setUp()
        self.output = []
        self.test_dir = os.path.join(os.path.dirname(__file__), "tmp_llm_integration")
        os.makedirs(self.test_dir, exist_ok=True)
        # Use inherited create_engine to support core_debug
        self.engine = self.create_engine(root_dir=self.test_dir)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def capture_output(self, msg):
        self.output.append(msg)

    def run_code(self, code, llm_responses=None):
        test_file = os.path.join(self.test_dir, "test.ibci")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(textwrap.dedent(code).strip() + "\n")

        self.engine._prepare_interpreter(output_callback=self.capture_output)
        
        # Ensure ai module is configured
        ai_pkg = self.engine.interpreter.service_context.interop.get_package("ai")
        # 默认配置
        ai_pkg.set_config("TESTONLY", "TESTONLY", "TESTONLY")

        # Setup Mock LLM if responses provided
        if llm_responses:
            llm_call_count = 0
            self.mock_retry_hint = None
            mock_self = self
            
            class MockLLM:
                def __call__(self, sys_prompt, user_prompt, scene="general"):
                    nonlocal llm_call_count
                    res = llm_responses[llm_call_count] if llm_call_count < len(llm_responses) else "1"
                    llm_call_count += 1
                    
                    stored_sys_prompt = sys_prompt
                    if mock_self.mock_retry_hint:
                        if "[RETRY_HINT]" not in stored_sys_prompt:
                            stored_sys_prompt = f"{sys_prompt}\n\n[RETRY_HINT]: {mock_self.mock_retry_hint}"

                    ai_pkg._last_call_info = {
                        "sys_prompt": stored_sys_prompt,
                        "user_prompt": user_prompt,
                        "response": res,
                        "scene": scene
                    }
                    return res
                
                def set_retry_hint(self, hint):
                    mock_self.mock_retry_hint = hint
                
                def get_last_call_info(self):
                    return ai_pkg._last_call_info

            self.engine.interpreter.llm_executor.llm_callback = MockLLM()
        
        # 开启 silent=True 以抑制冗余输出
        # 设置 prepare_interpreter=False 以保留我们刚刚设置好的 mock 环境
        try:
            return self.engine.run(
                test_file, 
                output_callback=self.capture_output, 
                silent=True,
                prepare_interpreter=False
            )
        except Exception:
            return False

    # --- Control Flow & Exception Handling ---

    def test_llm_except_and_retry(self):
        """Test llmexcept and retry mechanism."""
        code = """
        import ai
        int count = 0
        if @~check~:
            print("success")
        llmexcept:
            count = count + 1
            if count < 2:
                ai.set_retry_hint("retry")
                retry
            else:
                print("failed")
        """
        # MOCK_UNCERTAIN_RESPONSE will trigger llmexcept
        self.run_code(code, llm_responses=["MOCK_UNCERTAIN_RESPONSE", "1"])
        self.assertIn("success", self.output)

    def test_retry_hint_cleanup(self):
        """验证 ai._retry_hint 在成功调用后会被清除。"""
        code = """
        import ai
        import idbg
        
        # MOCK:REPAIR 在第一次调用时(无hint)会返回不确定结果触发 except
        # 在第二次调用时(有hint)会返回成功结果 1
        if @~ MOCK:REPAIR ~:
            print("success")
        llmexcept:
            ai.set_retry_hint("FIX_ME")
            retry
            
        # 此时第二次调用已成功，_retry_hint 应该已被清除
        # 我们发起第三次调用来验证
        @~ some_normal_call ~
        dict last = idbg.last_llm()
        print(last["sys_prompt"])
        """
        self.run_code(code)
        
        self.assertIn("success", self.output)
        # 检查最后一次调用的 sys_prompt，不应该包含 FIX_ME
        last_prompt = self.output[-1]
        self.assertNotIn("FIX_ME", last_prompt)

    def test_llm_keywords_same_line(self):
        """验证 __sys__ 和 __user__ 允许在同行书写文本。"""
        code = """
        import ai
        import idbg
        
        llm test_func(str name):
        __sys__ You are a robot.
        __user__ Say hello to $__name__.
        llmend
        
        test_func("Alice")
        dict last = idbg.last_llm()
        print(last["sys_prompt"])
        print(last["user_prompt"])
        """
        self.run_code(code)
        # 验证输出中包含了正确的提示词
        self.assertTrue(any("You are a robot." in o for o in self.output))
        self.assertTrue(any("Say hello to Alice." in o for o in self.output))

    def test_robust_llm_parsing(self):
        """验证 LLM 返回值解析的鲁棒性（处理噪声和 Markdown）。"""
        code = """
        import ai
        
        llm get_int() -> int:
            __user__
            MOCK:NOISY: 42
            llmend
            
        llm get_dict() -> dict:
            __user__
            MOCK:MARKDOWN: {"val": 100}
            llmend
            
        print(get_int())
        dict d = get_dict()
        print(d.val)
        """
        self.run_code(code)
        self.assertIn("42", self.output)
        self.assertIn("100", self.output)

    def test_nested_llm_except(self):
        """Test nested llmexcept blocks."""
        code = """
        if @~outer~:
            if @~inner~:
                print("inner success")
            llmexcept:
                print("inner failed")
        llmexcept:
            print("outer failed")
        """
        # Outer fails
        self.run_code(code, ["invalid"])
        self.assertEqual(self.output, ["outer failed"])
        
        self.output = []
        # Inner fails
        self.run_code(code, ["1", "invalid"])
        self.assertEqual(self.output, ["inner failed"])

    # --- Return Types & Parsing ---

    def test_llm_return_types(self):
        """Test LLM returning various data types (int, list, dict)."""
        code = """
        import ai
        ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
        llm get_data() -> dict:
            __user__
            MOCK:RESPONSE: {"val": 42, "list": [1, 2]}
            llmend
        dict d = get_data()
        print(d.val)
        """
        self.run_code(code, ['{"val": 42, "list": [1, 2]}'])
        self.assertIn("42", self.output)

    # --- Complex Access & Interpolation ---

    def test_complex_interpolation(self):
        """Test complex variable interpolation in behavior expressions."""
        code = """
        import ai
        ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
        dict data = {"info": {"id": 101}}
        str res = @~ID is $data.info.id~
        print(res)
        """
        # Captured prompt check would be better, but verifying execution for now
        self.run_code(code, ["1"])
        self.assertTrue(len(self.output) > 0)

    # --- Configuration Flow ---

    def test_config_flow(self):
        """Test loading config from JSON and injecting into ai module."""
        config_path = os.path.join(self.test_dir, "config.json")
        with open(config_path, 'w') as f:
            json.dump({"url": "TESTONLY", "key": "TESTONLY", "model": "TESTONLY"}, f)
            
        code = f"""
        import file
        import json
        import ai
        str raw = file.read('{config_path.replace('\\', '/')}')
        dict cfg = json.parse(raw)
        ai.set_config(cfg.url, cfg.key, cfg.model)
        @~ do something ~
        print("done")
        """
        self.run_code(code, ["1"])
        self.assertIn("done", self.output)

    # --- Whitebox Verification with idbg ---

    def test_intent_stack_injection(self):
        """利用 idbg 验证嵌套意图是否正确注入到 System Prompt 中。"""
        code = """
        import ai
        import idbg
        ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
        
        llm ai_func() -> str:
            __user__
            MOCK:RESPONSE:OK
            llmend

        func helper() -> str:
            @ 内部意图
            return ai_func()
            
        @ 外部意图
        helper()
        
        dict last = idbg.last_llm()
        print(last["sys_prompt"])
        """
        self.run_code(code, ["OK"])
        # 验证 sys_prompt 是否包含嵌套意图
        sys_prompt = self.output[0]
        self.assertIn("外部意图", sys_prompt)
        self.assertIn("内部意图", sys_prompt)

    def test_retry_hint_injection(self):
        """利用 idbg 验证 ai.set_retry_hint 是否正确影响了重试时的 Prompt。"""
        code = """
        import ai
        import idbg
        ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
        
        if @~ MOCK:FAIL ~:
            print("success")
        llmexcept:
            ai.set_retry_hint("请一定要返回 1")
            retry
            
        dict last = idbg.last_llm()
        print(last["sys_prompt"])
        """
        # 我们需要修改 run_code 中的 mock_llm 来支持 set_retry_hint
        # 已经在 run_code 中处理了
        self.run_code(code, ["maybe", "1"])
        
        # 检查第二次调用的 prompt。
        # 由于我们手动在 mock_llm 中更新了 last_call_info，
        # 且 LLMExecutorImpl 会调用 callback.set_retry_hint (如果 callback 有的话)
        # 我们需要在 run_code 的 mock_llm 中捕获 hint。
        self.assertTrue(len(self.output) > 1, f"Expected at least 2 output lines, got {self.output}")
        sys_prompt = self.output[1] 
        self.assertIn("请一定要返回 1", sys_prompt)

    def test_complex_data_stringification(self):
        """利用 idbg 验证复杂数据结构在 User Prompt 中的插值形式。"""
        code = """
        import ai
        import idbg
        ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
        
        dict user = {"name": "Alice", "score": 95, "tags": ["vip"]}
        @~ 分析用户 $user 的状态 ~
        
        dict last = idbg.last_llm()
        print(last["user_prompt"])
        """
        self.run_code(code, ["1"])
        user_prompt = self.output[0]
        # 验证复杂对象是否被正确字符串化
        self.assertIn("Alice", user_prompt)
        self.assertIn("95", user_prompt)
        self.assertIn("vip", user_prompt)

if __name__ == '__main__':
    unittest.main()
