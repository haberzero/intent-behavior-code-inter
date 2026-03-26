
import sys
import os
import subprocess
from pathlib import Path

# Add project root to sys.path
project_root = Path(r"c:\myself\proj\intent-behavior-code-inter")

def run_example_via_main(example_rel_path):
    example_path = project_root / example_rel_path
    print(f"\n>>> Running Example (CLI): {example_rel_path}")
    
    # Use main.py run command
    # Only use --config for files that don't load it themselves
    cmd = [
        sys.executable, 
        "main.py", 
        "run", 
        str(example_path)
    ]
    
    if "cli_config.ibci" in example_rel_path:
        cmd += ["--config", "api_config.json"]
    
    # Determine if we should use Real LLM or Mock
    # We keep flow control syntax and complex integration as Real calls
    real_llm_examples = {
        "intent_driven_loop.ibci",
        "llm_error_handling.ibci",
        "intent_stacking.ibci",
        "story_teller.ibci",
        "complex_workflow.ibci",
        "integration.ibci",
        "doc_analyzer.ibci",
        "04_mock_advanced.ibci"
    }
    
    use_mock = True
    for real_name in real_llm_examples:
        if real_name in example_rel_path:
            use_mock = False
            break
            
    try:
        # Set IBC_TEST_MODE based on our gray-scale policy
        env = os.environ.copy()
        env["IBC_TEST_MODE"] = "1" if use_mock else "0"
        
        mode_str = "MOCK" if use_mock else "REAL LLM"
        print(f"Mode: {mode_str}")
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            cwd=str(project_root),
            env=env,
            encoding='utf-8',
            errors='replace'
        )
        
        if result.returncode == 0:
            print("--- Execution Output ---")
            print(result.stdout.strip())
            print("--- SUCCESS ---")
            return True, ""
        else:
            print(f"--- Execution FAILED (Exit Code: {result.returncode}) ---")
            print("STDOUT:")
            print(result.stdout.strip())
            print("STDERR:")
            print(result.stderr.strip())
            return False, result.stderr
            
    except Exception as e:
        print(f"--- ERROR: {type(e).__name__} ---")
        return False, str(e)

def main():
    # Discover all .ibci files in test_target_proj
    test_target_dir = project_root / "test_target_proj"
    examples_to_test = []
    
    # Priority order or just all
    for p in test_target_dir.rglob("*.ibci"):
        rel_path = p.relative_to(project_root)
        # Skip some files if necessary (e.g. interactive ones)
        if "interactive_debug.ibci" in str(rel_path): continue
        if "debug_demo.ibci" in str(rel_path): continue
        examples_to_test.append(str(rel_path))
    
    # Sort for deterministic output
    examples_to_test.sort()
    
    results = []
    for example_rel_path in examples_to_test:
        success, error = run_example_via_main(example_rel_path)
        results.append((example_rel_path, success, error))
        
    print("\n" + "="*50)
    print("IBC-INTER CLI MVP TEST SUMMARY")
    print("="*50)
    
    all_passed = True
    for path, success, error in results:
        status = "PASSED" if success else "FAILED"
        print(f"[{status}] {path}")
        if not success:
            all_passed = False
            
    if not all_passed:
        sys.exit(1)

if __name__ == "__main__":
    main()
