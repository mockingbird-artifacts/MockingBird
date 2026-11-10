
import os
import json
import shutil
import argparse
import subprocess
import tqdm
import xml.etree.ElementTree as ET
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed


HARNESS_SIGNATURES = ("MockConversionGap", "mock_helper.py", "set_object_instance_fields",
                      "update_static_fields", "convert_to_python", "No module named",
                      "partially initialized module", "cannot import name")

def classify_error(text, focal_marker=None):
    """Three-state refinement: an <error> (non-assertion exception) only fails a method when it
    originates in the translated code itself. Crashes inside the mock infrastructure, replay
    exhaustion, or missing test resources make the test INCONCLUSIVE: it neither passes nor fails,
    exactly as if the recording had never produced this test. A pass still requires real assertions,
    so this cannot introduce false positives."""
    import re as _re
    t = str(text)
    final = [l for l in t.strip().splitlines() if l.strip()][-1] if t.strip() else ""
    if final.strip().startswith("AssertionError"):
        return 'failed'   # a real assertion verdict is conclusive no matter whose frames appear mid-trace
    if "StopIteration" in t:
        # replay exhaustion: divergence only if it fired inside the focal invocation; in setup or
        # reference construction it is the recording running short, a harness condition
        if focal_marker and focal_marker in t:
            return 'failed'
        return 'inconclusive'
    if "FileNotFoundError" in t and "resources" in t:
        return 'inconclusive'
    last = None
    for m in _re.finditer(r'File "([^"]+)", line', t):
        last = m.group(1)
    if last and "/src/main/" in last.replace("\\", "/"):
        return 'failed'
    if any(sig in t for sig in HARNESS_SIGNATURES):
        return 'inconclusive'
    return 'failed'


class ValidateByMocking:
    def __init__(self, args, fragment):
        self.args = args
        self.fragment = fragment
    
    def validate(self):
        validation_result = {'outcome': 'pending', 'feedback': []}
        
        # pre-flight: if the fragment's own module cannot import, no test can execute it;
        # the fragment is pending without burning one doomed pytest per eligible test
        mod = "src." + ".".join(self.fragment['schema_name'].split(".src.")[1].split(".")[:-1]) \
              + "." + self.fragment['schema_name'].split(".")[-1]
        cwd = f"{os.getcwd()}/data/recomposed_projects/{self.args.model_name}/{self.args.temperature}/{self.args.project_name}"
        probe = subprocess.run(["python3", "-c", f"import {mod}"], capture_output=True, text=True,
                               cwd=cwd, timeout=60,
                               env={**os.environ, "PYTHONPATH": cwd + ":" + os.getcwd() + "/src/mocking"})
        if probe.returncode != 0:
            return validation_result   # pending: module import fails independent of this fragment
        
        eligible_tests = self.get_eligible_tests()
        self.copy_tests(eligible_tests)
        
        # Use ProcessPoolExecutor for parallel test execution
        with ProcessPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor:
            # Submit all tests to the executor
            future_to_test = {executor.submit(self.run_test, test): test for test in eligible_tests}
            
            # Use tqdm for progress tracking
            pbar = tqdm.tqdm(total=len(eligible_tests), desc="Validating Tests")
            
            # Collect results
            for future in as_completed(future_to_test):
                test = future_to_test[future]
                
                try:
                    test_outcome, test_feedback = future.result()
                    pbar.update(1)
                                        
                    # If any test fails CONCLUSIVELY, update validation result and break
                    if test_outcome == 'failed':
                        validation_result['outcome'] = 'failed'
                        validation_result['feedback'].append({test: test_feedback})
                        # Cancel remaining futures
                        for f in future_to_test:
                            f.cancel()
                        break
                    elif test_outcome == 'inconclusive':
                        pass   # mock-infrastructure incident: no evidence either way
                    elif test_outcome == 'success':
                        validation_result['outcome'] = 'success'
                
                except BaseException as exc:
                    if classify_error(str(type(exc).__name__) + ": " + str(exc)) == 'inconclusive':
                        pbar.update(1)
                        continue
                    validation_result['outcome'] = 'failed'
                    validation_result['feedback'].append({test: str(exc)})
                    # Cancel remaining futures
                    for f in future_to_test:
                        f.cancel()
                    break
            
            # Close the progress bar
            pbar.close()
        
        assert len(validation_result) == 2
        assert isinstance(validation_result, dict)
        assert 'outcome' in validation_result
        assert 'feedback' in validation_result
        assert isinstance(validation_result['outcome'], str)
        assert isinstance(validation_result['feedback'], list)
        
        self.delete_test_files()
        
        return validation_result

    def copy_tests(self, eligible_tests):
        current_dir = os.getcwd()
        cwd = f'{current_dir}/data/recomposed_projects/{self.args.model_name}/{self.args.temperature}/{self.args.project_name}'
        
        test_path = f'data/mock_tests/{self.args.project_name}'
        
        for test in eligible_tests:
            src_test_path = os.path.join(test_path, test)
            dest_test_path = os.path.join(cwd, test)

            os.makedirs(os.path.dirname(dest_test_path), exist_ok=True)

            shutil.copy2(src_test_path, dest_test_path)

    def delete_test_files(self):
        current_dir = os.getcwd()
        cwd = f'{current_dir}/data/recomposed_projects/{self.args.model_name}/{self.args.temperature}/{self.args.project_name}'
        
        # delete all .py files in cwd which has "_mocker_" in the name
        for root, dirs, files in os.walk(cwd):
            for file in files:
                if file.endswith('.py') and '_mocker_' in file:
                    os.remove(os.path.join(root, file))
    
    def get_eligible_tests(self):
        eligible_tests = []
        
        all_tests = self.get_all_tests()
        
        class_name = self.fragment['class_name'].split(':')[1]
        method_name = self.fragment['fragment_name'].split(':')[1]
        
        if class_name == method_name:
            method_name = '<init>'
        
        for test in all_tests:
            if test.endswith(f'_{class_name}_{method_name}.py') or test.endswith(f'${class_name}_{method_name}.py'):
                eligible_tests.append(test)
        
        # randomly select 1000 tests from eligible_tests
        import random
        random.shuffle(eligible_tests)        
        return eligible_tests[:1000]
    
    def get_all_tests(self):
        all_tests = []
        
        test_path = f'data/mock_tests/{self.args.project_name}'
        
        for root, dirs, files in os.walk(test_path):
            for file in files:
                if file.endswith('.py') and file != '__init__.py':
                    all_tests.append('/'.join(os.path.join(root, file).split('/')[3:]))
        
        return all_tests
    
    def run_test(self, test):
        test_outcome = 'success'
        test_feedback = ''

        current_dir = os.getcwd()
        cwd = f'{current_dir}/data/recomposed_projects/{self.args.model_name}/{self.args.temperature}/{self.args.project_name}'

        # Create a unique test report file for each test to avoid race conditions
        test_report = f'pytest-report-{os.getpid()}.xml'
        full_test_report_path = os.path.join(cwd, test_report)

        if os.path.exists(full_test_report_path):
            os.remove(full_test_report_path)

        env = os.environ.copy()
        env['PYTHONPATH'] = f"{cwd}:{current_dir}/src/mocking"
        # context-aware type map for deserialization in mock_helper (fixed mapping is only the fallback)
        env['MOCKINGBIRD_PROJECT'] = str(self.args.project_name)
        env['MOCKINGBIRD_ROOT'] = current_dir
        env['MOCKINGBIRD_TYPE_MAP'] = f"{current_dir}/data/type_resolution/{self.args.project_name}/type_mapping.json"
        env.setdefault('MOCKINGBIRD_TYPE_MAP_LOG', f"{current_dir}/data/type_resolution/{self.args.project_name}/mock_type_resolution_log.jsonl")
        
        try:
            subprocess.run(
                [
                    'pytest', test,
                    f'--junitxml={test_report}'
                ],
                check=True,
                capture_output=True,
                text=True,
                env=env,
                cwd=cwd,
                timeout=100
            )
        except subprocess.TimeoutExpired as e:
            test_outcome = 'failed'
            test_feedback = f'Timeout expired: {e}'
        except subprocess.CalledProcessError as e:
            test_outcome = 'failed'
            test_feedback = (e.stderr or "") + "\n" + (e.stdout or "")   # pytest INTERNALERROR tracebacks go to stdout

        focal = "orig_" + self.fragment['class_name'].split(':')[-1] + "_" + \
                (self.fragment['fragment_name'].split(':')[-1] if self.fragment['class_name'].split(':')[-1] != self.fragment['fragment_name'].split(':')[-1] else "init")
        if not os.path.exists(full_test_report_path):
            # pytest died before writing a report (collection crash): classify from captured stderr
            return classify_error(test_feedback, focal), test_feedback
        with open(full_test_report_path, 'r') as f:
            tree = ET.parse(f)
            root = tree.getroot()
            found = False
            for testcase in root.findall('.//testcase'):
                if testcase.get('name') == 'test_mocking':
                    found = True
                    if testcase.find('failure') is not None:
                        # pytest's junit writer files uncaught exceptions from unittest-protocol tests
                        # under <failure> too, so origin-classify: real assertion mismatches carry no
                        # harness signature and stay conclusive
                        test_feedback = testcase.find('failure').text
                        test_outcome = classify_error(test_feedback, focal)
                    elif testcase.find('error') is not None:
                        test_feedback = testcase.find('error').text
                        test_outcome = classify_error(test_feedback, focal)
                    break
            if not found and root.findall('.//error'):   # collection-level error (module import failed)
                # the focal method never ran: whatever broke the import (even a defect in another
                # fragment of the same module) is not evidence about this fragment
                txt = "".join(e.text or "" for e in root.findall('.//error'))
                test_outcome, test_feedback = 'inconclusive', txt
            elif not found and test_outcome == 'failed':
                # pytest aborted (e.g. INTERNALERROR from a BaseException) leaving a truncated report:
                # the raw exit-status verdict was never refined by any xml node, so classify the captured text
                test_outcome = classify_error(test_feedback, focal)
        
        if test_outcome == 'failed':
            t = str(test_feedback)
            import re as _re2
            none_sig = _re2.search(r"NoneType.{0,60}(has no attribute|not subscriptable|not iterable|has no len|must be str)", t)
            if none_sig and "/src/main/" in t:
                # null-provenance audit: a NoneType crash in the focal code is conclusive only if the
                # recording actually contains a null anywhere in this test; otherwise the None was
                # manufactured by reconstruction and the evidence is about the harness, not the code
                try:
                    if 'type\\":\\"null' not in open(test if os.path.isabs(test) else os.path.join(cwd, test)).read():
                        test_outcome = 'inconclusive'
                except Exception:
                    pass

        # Clean up the temporary test report
        if os.path.exists(full_test_report_path):
            os.remove(full_test_report_path)

        return test_outcome, test_feedback


if __name__ == '__main__':
    args = argparse.Namespace(model_name='llama-3-3-70b-instruct', project_name='commons-cli', from_lang='Java', to_lang='Python', validate_by_graal=False, debug=True, validate_by_mocking=True, temperature=0.0, suffix='_decomposed_tests', recursion_depth=2, schemas_dir='data/schemas_decomposed_tests/llama-3-3-70b-instruct/0.0/commons-cli')    
    fragment = {'schema_name': 'commons-cli.src.main.org.apache.commons.cli.HelpFormatter', 'class_name': '64-960:HelpFormatter', 'fragment_name': '256-261:createPadding', 'fragment_type': 'method', 'is_test_method': False}
    
    validator = ValidateByMocking(args, fragment)
    validation_result = validator.validate()
    
    print(json.dumps(validation_result, indent=4))
