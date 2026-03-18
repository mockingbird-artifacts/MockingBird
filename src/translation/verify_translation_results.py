import os
import argparse
import json
import tqdm
from src.translation.test_validation import test_validation
from src.translation.compositional_translation_validation import update_labels


def main(args):
    args.schemas_dir = f'data/schemas{args.suffix}/{args.model_name}/{args.temperature}/{args.project_name}'

    tests_require_revalidation = []

    for schema_fname in os.listdir(args.schemas_dir):

        if 'package-info' in schema_fname or 'module-info' in schema_fname:
            continue

        if f'{args.project_name}.src.test' not in schema_fname:
            continue

        schema_path = f'{args.schemas_dir}/{schema_fname}'
        
        schema = {}
        with open(schema_path, 'r') as f:
            schema = json.load(f)

        for class_ in schema['classes']:

            extended_classes = schema['classes'][class_]['extends']

            for method_ in schema['classes'][class_]['methods']:
                
                if schema['classes'][class_]['methods'][method_]['is_overload']:
                    continue

                if '@Test' not in [x.split('(')[0] for x in schema['classes'][class_]['methods'][method_]['annotations']]:
                    continue
                if '@Ignore' in [x.split('(')[0] for x in schema['classes'][class_]['methods'][method_]['annotations']]:
                    continue
                if '@Disabled' in [x.split('(')[0] for x in schema['classes'][class_]['methods'][method_]['annotations']]:
                    continue

                tests_require_revalidation.append({'schema_name': schema_fname.replace('.json', ''), 'class_name': class_, 'fragment_name': method_, 'fragment_type': 'method', 'is_test_method': True})

            for extended_class in extended_classes:
                extended_class_schema_fname = ''
                for potential_extended_class_schema_fname in os.listdir(args.schemas_dir):
                    potential_extended_class_schema_path = f'{args.schemas_dir}/{potential_extended_class_schema_fname}'
                    potential_extended_class_schema = {}
                    with open(potential_extended_class_schema_path, 'r') as f:
                        potential_extended_class_schema = json.load(f)
                    
                    potential_extended_class_name = None
                    for potential_extended_class in potential_extended_class_schema['classes']:
                        if potential_extended_class.split(':')[1] == extended_class:
                            potential_extended_class_name = potential_extended_class
                            break
                    
                    if potential_extended_class_name is None:
                        continue

                    for method_ in potential_extended_class_schema['classes'][potential_extended_class_name]['methods']:
                        if potential_extended_class_schema['classes'][potential_extended_class_name]['methods'][method_]['is_overload']:
                            continue

                        if '@Test' not in [x.split('(')[0] for x in potential_extended_class_schema['classes'][potential_extended_class_name]['methods'][method_]['annotations']]:
                            continue
                        if '@Ignore' in [x.split('(')[0] for x in potential_extended_class_schema['classes'][potential_extended_class_name]['methods'][method_]['annotations']]:
                            continue
                        if '@Disabled' in [x.split('(')[0] for x in potential_extended_class_schema['classes'][potential_extended_class_name]['methods'][method_]['annotations']]:
                            continue

                        tests_require_revalidation.append({'schema_name': schema_fname.replace('.json', ''), 'class_name': class_, 'fragment_name': method_, 'fragment_type': 'method', 'is_test_method': True})

    test_execution_details = test_validation(args, tests_require_revalidation, recompose_fragments=False)
    for test in test_execution_details:
        for covered_method in test_execution_details[test]['covered_methods']:
            covered_method_file = covered_method['schema_name']
            covered_method_class = covered_method['class_name']
            covered_method_name = covered_method['fragment_name']

            update_labels(args=args, fragment={'schema_name': covered_method_file, 'class_name': covered_method_class, 'fragment_name': covered_method_name, 'fragment_type': 'method'}, translation=[], translation_status=[], syntactic_validation=[], field_exercise=[], graal_validation=[], mocking_validation=[], test_execution={test: test_execution_details[test]}, elapsed_time=0, update_test_execution=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Verify translation results')
    parser.add_argument('--model_name', type=str, dest='model_name', help='model name to use for translation')
    parser.add_argument('--project_name', type=str, dest='project_name', help='project name to translate')
    parser.add_argument('--temperature', type=float, dest='temperature', help='temperature for generation')
    parser.add_argument('--suffix', type=str, dest='suffix', help='suffix for the translated files')
    args = parser.parse_args()
    main(args)
