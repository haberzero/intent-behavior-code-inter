import os
import subprocess
import sys

def run_ibci(file_path):
    print(f"Running: {file_path}")
    try:
        # Use subprocess to run main.py
        result = subprocess.run(
            [sys.executable, "main.py", "run", file_path],
            capture_output=True,
            text=True,
            timeout=30 # Avoid infinite loops
        )
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)

def main():
    test_dirs = ["examples", "test_target_proj"]
    all_files = []
    for d in test_dirs:
        for root, _, files in os.walk(d):
            for f in files:
                if f.endswith(".ibci"):
                    all_files.append(os.path.join(root, f))
    
    # Files already tested (skip them to save time, but run others)
    already_tested = {
        "examples/01_quick_start/01_hello_ai.ibci",
        "examples/01_quick_start/02_control_flow.ibci",
        "examples/01_quick_start/03_stdlib_usage.ibci",
        "examples/02_advanced_ai/01_intent_roles.ibci",
        "examples/02_advanced_ai/02_structured_data.ibci",
        "examples/03_engineering/01_error_handling.ibci",
        "examples/03_engineering/03_config_and_mock.ibci",
        "examples/03_engineering/isolation_demo/parent.ibci",
        "examples/03_engineering/plugins_demo/main.ibci",
    }
    
    # Normalize paths for comparison
    already_tested = {os.path.normpath(p) for p in already_tested}
    
    failures = []
    passed_count = 0
    skipped_count = 0
    
    for f in all_files:
        norm_f = os.path.normpath(f)
        if norm_f in already_tested:
            skipped_count += 1
            continue
            
        success, output = run_ibci(f)
        if success:
            passed_count += 1
        else:
            failures.append((f, output))
            
    print(f"\nSummary: {passed_count} passed, {len(failures)} failed, {skipped_count} skipped.")
    
    if failures:
        print("\nFailures:")
        for f, output in failures:
            print(f"\n--- FAILURE: {f} ---")
            print(output)
            print("-" * 20)

if __name__ == "__main__":
    main()
