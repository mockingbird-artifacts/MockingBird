import os
import subprocess
import tqdm
import xml.etree.ElementTree as ET
from calculate_coverage import calculate_method_coverage


def test_validation(args, eligible_tests, recompose_fragments=True):

    if recompose_fragments:
        os.system(f'python3 src/postprocessing/recompose.py --project_name={args.project_name} \
                                                            --model_name={args.model_name} \
                                                            --output_dir=data/recomposed_projects \
                                                            --temperature={args.temperature} \
                                                            --suffix={args.suffix}')

    test_execution_results = {}
    failed_tests = []
    for test in tqdm.tqdm(eligible_tests):
        print(f'Running test: {test["schema_name"]}.{test["class_name"]}.{test["fragment_name"]}', flush=True)

        test_path = '/'.join(test['schema_name'].split('.')[1:]) + '.py'
        test_class = test['class_name'].split(':')[1]
        test_method = test['fragment_name'].split(':')[1]

        if not test_method.startswith('test'):
            test_method = 'test' + test_method

        if '_decomposed' in test_method:
            actual_test_name = test_method[:test_method.index('_decomposed')].split('_')[0]
        else:
            actual_test_name = test_method

        actual_test_full_name = f'{test_path}::{test_class}::{actual_test_name}'

        if actual_test_full_name in failed_tests:
            continue

        test_execution_results.setdefault(f'{test_path}::{test_class}::{test_method}', {'test_outcome': 'exercised-success', 'feedback': '', 'covered_methods': []})

        current_dir = os.getcwd()
        cwd = f'{current_dir}/data/recomposed_projects/{args.model_name}/{args.temperature}/{args.project_name}'

        if os.path.exists(f'{cwd}/pytest-report.xml'):
            os.remove(f'{cwd}/pytest-report.xml')
        if os.path.exists(f'{cwd}/coverage.xml'):
            os.remove(f'{cwd}/coverage.xml')

        env = os.environ.copy()
        env['PYTHONPATH'] = cwd
        
        try:
            subprocess.run(
                [
                    'pytest', f'{test_path}::{test_class}::{test_method}',
                    '--cov=src.main',
                    '--cov=src.test',
                    '--cov-report=term-missing',
                    f'--cov-report=xml:coverage.xml',
                    f'--junitxml=pytest-report.xml'
                ],
                check=True,
                capture_output=True,
                text=True,
                env=env,
                cwd=cwd,
                timeout=100,
            )
        except subprocess.TimeoutExpired as e:            
            test_execution_results[f'{test_path}::{test_class}::{test_method}']['test_outcome'] = 'exercised-failed'
            test_execution_results[f'{test_path}::{test_class}::{test_method}']['feedback'] = 'test timed out'
            failed_tests.append(actual_test_full_name)
            continue
        except subprocess.CalledProcessError as e:
            test_execution_results[f'{test_path}::{test_class}::{test_method}']['test_outcome'] = 'exercised-failed'
            failed_tests.append(actual_test_full_name)
                    
        if not os.path.exists(f'{cwd}/coverage.xml'):
            test_execution_results[f'{test_path}::{test_class}::{test_method}']['test_outcome'] = 'exercised-failed'
            failed_tests.append(actual_test_full_name)
        else:
            covered_methods = calculate_method_coverage(args, cwd)
            test_execution_results[f'{test_path}::{test_class}::{test_method}']['covered_methods'] = covered_methods

        assert os.path.exists(f'{cwd}/pytest-report.xml')
        with open(f'{cwd}/pytest-report.xml', 'r') as f:
            tree = ET.parse(f)
            root = tree.getroot()
            for testcase in root.findall('.//testcase'):
                if testcase.get('name') == test_method:
                    if testcase.find('failure') is not None:
                        test_execution_results[f'{test_path}::{test_class}::{test_method}']['feedback'] = testcase.find('failure').text
                    elif testcase.find('error') is not None:
                        test_execution_results[f'{test_path}::{test_class}::{test_method}']['feedback'] = testcase.find('error').text
                    break
        
        if test_execution_results[f'{test_path}::{test_class}::{test_method}']['test_outcome'] == 'exercised-failed' and test_execution_results[f'{test_path}::{test_class}::{test_method}']['feedback'] == '':
            test_execution_results[f'{test_path}::{test_class}::{test_method}']['feedback'] = 'test did not execute properly'

    return test_execution_results
