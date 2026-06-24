import argparse
import json
import tqdm
import os
import time
import datetime
import shutil

from get_reverse_traversal import get_reverse_traversal
from src.mocking.validate_by_mocking import ValidateByMocking


def get_processed_fragments(fragment_traversal, args):
    """
    Extract all processed fragments
    """
    processed_fragments = []
    for fragment in fragment_traversal:
        schema_data = {}
        with open(f'{args.schemas_dir}/{fragment["schema_name"]}.json', 'r') as f:
            schema_data = json.load(f)

        if schema_data['classes'][fragment['class_name']][f'{fragment["fragment_type"]}s'][fragment['fragment_name']]['translation_status'] in ['attempted', 'out_of_context']:
            processed_fragments.append(fragment)
    
    return processed_fragments


def update_labels(args, fragment, translation, translation_status, syntactic_validation, field_exercise, mocking_validation, elapsed_time, update_test_execution=False, fixed_by_simple_reprompt=False, fixed_by_advanced_reprompt=False):
    """
    Update the labels of the fragment in the schema file
    """
    schema_data = {}
    with open(f'{args.schemas_dir}/{fragment["schema_name"]}.json', 'r') as f:
        schema_data = json.load(f)
    
    if update_test_execution:
        pass
    else:
        schema_data['classes'][fragment['class_name']][f'{fragment["fragment_type"]}s'][fragment['fragment_name']]['translation'] = translation
        schema_data['classes'][fragment['class_name']][f'{fragment["fragment_type"]}s'][fragment['fragment_name']]['translation_status'] = translation_status
        schema_data['classes'][fragment['class_name']][f'{fragment["fragment_type"]}s'][fragment['fragment_name']]['syntactic_validation'] = syntactic_validation
        schema_data['classes'][fragment['class_name']][f'{fragment["fragment_type"]}s'][fragment['fragment_name']]['field_exercise'] = field_exercise 
        schema_data['classes'][fragment['class_name']][f'{fragment["fragment_type"]}s'][fragment['fragment_name']]['mocking_validation'] = mocking_validation
        schema_data['classes'][fragment['class_name']][f'{fragment["fragment_type"]}s'][fragment['fragment_name']]['elapsed_time'] = elapsed_time
        schema_data['classes'][fragment['class_name']][f'{fragment["fragment_type"]}s'][fragment['fragment_name']]['model_name'] = args.model_name
        schema_data['classes'][fragment['class_name']][f'{fragment["fragment_type"]}s'][fragment['fragment_name']]['generation_timestamp'] = datetime.datetime.now().isoformat()

    if fixed_by_simple_reprompt:
        schema_data['classes'][fragment['class_name']][f'{fragment["fragment_type"]}s'][fragment['fragment_name']]['fixed_by_simple_reprompt'] = True
    if fixed_by_advanced_reprompt:
        schema_data['classes'][fragment['class_name']][f'{fragment["fragment_type"]}s'][fragment['fragment_name']]['fixed_by_advanced_reprompt'] = True

    with open(f'{args.schemas_dir}/{fragment["schema_name"]}.json', 'w') as f:
        json.dump(schema_data, f, indent=4)
        f.flush()
        os.fsync(f.fileno())


def get_processed_translation(args, fragment):
    """
    Get processed translation in a previous run
    """
    schema_data = {}
    with open(f'{args.schemas_dir}/{fragment["schema_name"]}.json', 'r') as f:
        schema_data = json.load(f)
    
    return schema_data['classes'][fragment['class_name']][f'{fragment["fragment_type"]}s'][fragment['fragment_name']]['translation']


def get_higher_order_tests(test_fragment, args, executable_eligible_tests):
    other_higher_order_tests = []
    for test in executable_eligible_tests:
        if test['schema_name'] == test_fragment['schema_name'] and test['class_name'] == test_fragment['class_name']:
            if '_decomposed' not in test['fragment_name']:
                continue
            if '_decomposed' not in test_fragment['fragment_name']:
                continue
            if test['fragment_name'] == test_fragment['fragment_name']:
                continue

            test_fragment_base_name = test_fragment['fragment_name'].split(':')[1]
            test_base_name = test['fragment_name'].split(':')[1]

            test_fragment_base_name_first = '_'.join(test_fragment_base_name.split('_')[:-2])
            test_fragment_base_name_second = test_fragment_base_name.split('_')[-2]

            test_base_name_first = '_'.join(test_base_name.split('_')[:-2])
            test_base_name_second = test_base_name.split('_')[-2]

            if test_fragment_base_name_first != test_base_name_first:
                continue

            if int(test_base_name_second.replace('test', '')) > int(test_fragment_base_name_second.replace('test', '')):
                other_higher_order_tests.append(test)

    return other_higher_order_tests


def validate(fragment, args, budget={}, feedback=None, recursion_depth=2):

    if recursion_depth == 0:
        return

    if fragment['is_test_method']:
        return

    if budget == {}:
        budget = {'mocking': 1}

    current_budget = 'mocking'
    start_time = time.time()

    while budget[current_budget] > 0:

        ############################ <MOCKING VALIDATION> ############################
        mocking_status = 'pending'
        if args.validate_by_mocking and 'src.main' in fragment['schema_name']:
            validate_by_mocking = ValidateByMocking(args, fragment)
            validation_result = validate_by_mocking.validate()
            
            if validation_result['outcome'] == 'success':
                mocking_status = 'success'
            elif validation_result['outcome'] == 'failed':
                mocking_status = validation_result

            if feedback != '' and validation_result['outcome'] == 'success':
                update_labels(args=args, fragment=fragment, translation=get_processed_translation(args, fragment), translation_status='attempted', syntactic_validation='parseable', field_exercise='pending', mocking_validation=mocking_status, elapsed_time=time.time() - start_time, fixed_by_simple_reprompt=True)
            else:
                update_labels(args=args, fragment=fragment, translation=get_processed_translation(args, fragment), translation_status='attempted', syntactic_validation='parseable', field_exercise='pending', mocking_validation=mocking_status, elapsed_time=time.time() - start_time)
            
            if validation_result['outcome'] == 'failed':
                print('=======================MOCKING VALIDATION FAILED=======================', flush=True)
                
                feedback = ''
                for test in validation_result['feedback'][0]:
                    feedback = validation_result['feedback'][0][test]
                
                budget[current_budget] -= 1

                if budget[current_budget] == 0:
                    pass
                else:
                    continue
            
        ############################ </MOCKING VALIDATION> ############################

        break


def clean_up(args):
    """
    # delete all __pycache__ directories recursively
    find . -name '__pycache__' -exec rm -rf {} +

    # delete all .pytest_cache directories recursively
    find . -name '.pytest_cache' -exec rm -rf {} +

    # delete all .coverage files recursively
    find . -name '.coverage' -exec rm -rf {} +

    # delete all pytest-report.xml files recursively
    find . -name 'pytest-report.xml' -exec rm -rf {} +
    """
    base = os.path.join(
        'data',
        'recomposed_projects',
        args.model_name,
        str(args.temperature),
        args.project_name
    )

    # Walk top-down so we can prune dirs as we go
    for root, dirs, files in os.walk(base, topdown=True):
        # Remove unwanted directories and prevent os.walk from recursing into them
        for d in list(dirs):
            if d in ('__pycache__', '.pytest_cache'):
                shutil.rmtree(os.path.join(root, d))
                dirs.remove(d)

        # Remove unwanted files
        for f in files:
            if f in ('.coverage', 'pytest-report.xml'):
                os.remove(os.path.join(root, f))
            

def main(args):

    # constant variables
    args.schemas_dir = f'data/schemas{args.suffix}/{args.model_name}/{args.temperature}/{args.project_name}'
    # extract the reverse-topological order of fragments based on call graph
    fragment_traversal = get_reverse_traversal(args)

    # extract all pending fragments which require translation
    processed_fragments = get_processed_fragments(fragment_traversal, args)
    
    for fragment in tqdm.tqdm(processed_fragments):

        validate(fragment, args, recursion_depth=args.recursion_depth)
        
        clean_up(args)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Translate fragments using LLM')
    parser.add_argument('--model_name', type=str, dest='model_name', help='model name to use for translation')
    parser.add_argument('--project_name', type=str, dest='project_name', help='project name to translate')
    parser.add_argument('--validate_by_mocking', action='store_true', help='validate translation by mocking')
    parser.add_argument('--temperature', type=float, dest='temperature', help='temperature for generation')
    parser.add_argument('--suffix', type=str, dest='suffix', help='suffix for the translated files')
    parser.add_argument('--recursion_depth', type=int, dest='recursion_depth', help='depth of recursion for translation')
    args = parser.parse_args()
    main(args)

