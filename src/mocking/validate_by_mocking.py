
import os
import json
import shutil
import argparse
import subprocess
import tqdm
import xml.etree.ElementTree as ET
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed


class ValidateByMocking:
    def __init__(self, args, fragment):
        self.args = args
        self.fragment = fragment
    
    def validate(self):
        validation_result = {'outcome': 'pending', 'feedback': []}
        
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
                                        
                    # If any test fails, update validation result and break
                    if test_outcome == 'failed':
                        validation_result['outcome'] = 'failed'
                        validation_result['feedback'].append({test: test_feedback})
                        # Cancel remaining futures
                        for f in future_to_test:
                            f.cancel()
                        break
                    elif test_outcome == 'success':
                        validation_result['outcome'] = 'success'
                
                except Exception as exc:
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
            test_feedback = e.stderr

        assert os.path.exists(full_test_report_path)
        with open(full_test_report_path, 'r') as f:
            tree = ET.parse(f)
            root = tree.getroot()
            for testcase in root.findall('.//testcase'):
                if testcase.get('name') == 'test_mocking':
                    if testcase.find('failure') is not None:
                        test_outcome = 'failed'
                        test_feedback = testcase.find('failure').text
                    elif testcase.find('error') is not None:
                        test_outcome = 'failed'
                        test_feedback = testcase.find('error').text
                    break
        
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
