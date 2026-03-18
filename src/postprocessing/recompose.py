import argparse
import json
import os

from src.utils.get_class_order import get_class_order


def main(args):

    total_fragments = 0
    total_unsuccessful = 0

    translation_dir = f'data/schemas{args.suffix}/{args.model_name}/{args.temperature}/{args.project_name}'

    for schema in os.listdir(translation_dir):

        if 'package-info' in schema or 'module-info' in schema:
            continue

        if f'{args.project_name}.src.main' not in schema and f'{args.project_name}.src.test' not in schema:
            continue

        data = {}
        with open(f'{translation_dir}/{schema}') as f:
            data = json.load(f)

        recomposed_file = '\n'.join(data['python_imports'])
        recomposed_file += '\n\n\n'

        class_order = get_class_order(data)
        
        class_initialize_methods = []
        for class_ in class_order:

            class_name = class_.split(':')[1]

            recomposed_file += data['classes'][class_]['python_class_declaration']

            if data['classes'][class_]['fields'] == {} and data['classes'][class_]['methods'] == {}:
                recomposed_file += '    pass\n\n'
                continue

            field_val = {}
            for field in data['classes'][class_]['fields']:
                translation = data['classes'][class_]['fields'][field]['translation']
                if translation == []:
                    translation = ('\n'.join(data['classes'][class_]['fields'][field]['partial_translation']).rstrip() + 'None # LLM could not translate this field').split('\n')
                translation = '\n'.join(translation).strip()
                field_name = translation[:translation.find(':')].strip()
                field_value = ''.join(translation.split('=')[1:]).strip()
                field_val[field_name] = {'value': field_value, 'key': field}
            
            field_dependencies = {}
            for field in field_val:
                field_dependencies.setdefault(field, [])
                for field_ in field_val:
                    if field == field_:
                        continue
                    if field_ in field_val[field]['value']:
                        field_dependencies[field].append(field_)

            cycles = []
            for field in field_dependencies:
                for field_ in field_dependencies[field]:
                    if field in field_dependencies[field_]:
                        if (field_, field) not in cycles:
                            cycles.append((field, field_))
            
            for cycle in cycles:
                field_dependencies[cycle[0]].remove(cycle[1])

            field_order = []
            while len(field_order) != len(field_val):
                for field in field_val:
                    if field in field_order:
                        continue
                    if all([x in field_order for x in field_dependencies[field]]):
                        field_order.append(field)

            assert len(field_order) == len(field_val)

            field_order = [field_val[x]['key'] for x in field_order]

            intialize_later_fields = []

            exempt_fields = []
            if args.fragment_name:
                for k in field_val:
                    if field_val[k]['key'] == args.fragment_name:
                        exempt_fields = [k]
                        break
                
                if len(exempt_fields) == 1:
                    exempt_fields = [field_val[x]['key'] for x in field_dependencies[exempt_fields[0]]]
                    exempt_fields.append(args.fragment_name)

            if args.fragment_name and 'run_static_init' in args.fragment_name and 'static_initializers' in data['classes'][class_]:
                for static_initializer in data['classes'][class_]['static_initializers']:
                    static_init_translation = data['classes'][class_]['static_initializers'][static_initializer]['translation']
                    for k in field_val:

                        field_name = ''.join(data['classes'][class_]['fields'][field_val[k]['key']]['translation']).split('=')[0].strip().split(':')[0].strip()

                        static_init_recomposed_translation = ''
                        static_init_translation = data['classes'][class_]['static_initializers'][static_initializer]['translation']
                        if static_init_translation == [] or data['classes'][class_]['static_initializers'][static_initializer]['field_exercise'] == 'failed' or (args.fragment_name and args.fragment_name != static_initializer):
                            static_init_recomposed_translation = '    def run_static_init():\n        pass # LLM could not translate this static initializer\n'
                        else:
                            static_init_recomposed_translation = '\n'.join(data['classes'][class_]['static_initializers'][static_initializer]['translation'])

                        if field_name in static_init_recomposed_translation:
                            exempt_fields.append(field_val[k]['key'])
            
            non_static_fields = []
            static_fields = []
            for field in field_order.copy():
                if 'static' in data['classes'][class_]['fields'][field]['modifiers']:
                    static_fields.append(field)
                    continue
                non_static_fields.append(field)

            for field in field_order:

                if args.fragment_name:
                    if field not in exempt_fields:
                        if data['classes'][class_]['fields'][field]['enum_constant']:
                            total_constructor_params = 1
                            for m in data['classes'][class_]['methods']:
                                if data['classes'][class_]['methods'][m]['is_constructor']:
                                    total_constructor_params = len(data['classes'][class_]['methods'][m]['parameters'])
                                    break
                            recomposed_file += ''.join(data['classes'][class_]['fields'][field]['partial_translation']).rstrip()
                            for i in range(total_constructor_params - 1):
                                recomposed_file += 'None, '
                            recomposed_file += 'None'
                        else:
                            if data['classes'][class_]['fields'][field]['translation_status'] == 'attempted' and data['classes'][class_]['fields'][field]['syntactic_validation'] == 'parseable' and data['classes'][class_]['fields'][field]['translation'] != [] \
                                and data['classes'][class_]['fields'][field]['generation_timestamp'] == 0 and data['classes'][class_]['fields'][field]['elapsed_time'] == 0:
                                recomposed_file += '\n'.join(data['classes'][class_]['fields'][field]['translation']).rstrip()
                            else:
                                recomposed_file += ''.join(data['classes'][class_]['fields'][field]['partial_translation']) + 'None'
                        recomposed_file += '\n'
                        total_fragments += 1
                        continue

                if data['classes'][class_]['fields'][field]['translation'] == [] or data['classes'][class_]['fields'][field]['field_exercise'] == 'failed':
                    if data['classes'][class_]['fields'][field]['enum_constant']:
                        total_constructor_params = 1
                        for m in data['classes'][class_]['methods']:
                            if data['classes'][class_]['methods'][m]['is_constructor']:
                                total_constructor_params = len(data['classes'][class_]['methods'][m]['parameters'])
                                break
                        recomposed_file += ''.join(data['classes'][class_]['fields'][field]['partial_translation']).rstrip()
                        for i in range(total_constructor_params - 1):
                            recomposed_file += 'None, '
                        recomposed_file += 'None'
                    else:
                        recomposed_file += '\n'.join([''] + data['classes'][class_]['fields'][field]['partial_translation']).rstrip() + 'None # LLM could not translate this field'
                    recomposed_file += '\n'
                    total_unsuccessful += 1
                    continue

                field_translation = ''
                for l in data['classes'][class_]['fields'][field]['translation']:
                    field_translation += l[:l.find('#')].replace('\\', '') if '#' in l else l.replace('\\', '')

                found = False

                static_methods = []
                for method in data['classes'][class_]['methods']:
                    if 'static' in data['classes'][class_]['methods'][method]['modifiers']:
                        if 'private' in data['classes'][class_]['methods'][method]['modifiers']:
                            static_methods.append(f'__{method.split(":")[1]}')
                        elif 'protected' in data['classes'][class_]['methods'][method]['modifiers']:
                            static_methods.append(f'_{method.split(":")[1]}')
                        else:
                            static_methods.append(method.split(":")[1])

                for method in static_methods:
                    field_translation = field_translation.replace(f'self.{method}', method)
                    if f'{method}(' in field_translation.split('=')[1].strip() or \
                        f'({method}' in field_translation.split('=')[1].strip() or \
                        f'{method})' in field_translation.split('=')[1].strip() or \
                        f'{method},' in field_translation.split('=')[1].strip() or \
                        f',{method}' in field_translation.split('=')[1].strip():

                        modified_class_name = class_.split(':')[1]
                        intialize_later_fields.append((field, field_translation.split('=')[0].strip(), '='.join(field_translation.split('=')[1:]).strip().replace(f'{method}', f'{modified_class_name}.{method}' if f'{modified_class_name}.{method}' not in field_translation.split('=')[1].strip() else f'{method}')))
                        recomposed_file += ''.join(data['classes'][class_]['fields'][field]['partial_translation']).rstrip() + 'None'
                        recomposed_file += '\n'
                        found = True
                
                if found:
                    continue

                for a_class in class_order:
                    a_class = a_class.split(':')[1]
                    if f'{a_class}.' in field_translation or \
                        f'{a_class}(' in field_translation or \
                        f'({a_class}' in field_translation or \
                        f'{a_class})' in field_translation or \
                        f'{a_class},' in field_translation or \
                        f',{a_class}' in field_translation or \
                        f'{a_class}' in field_translation.split('=')[1].strip():

                        intialize_later_fields.append((field, field_translation.split('=')[0].strip(), '='.join(field_translation.split('=')[1:]).strip()))
                        recomposed_file += ''.join(data['classes'][class_]['fields'][field]['partial_translation']).rstrip() + 'None'
                        recomposed_file += '\n'
                        found = True
                
                if found:
                    continue

                if '='.join(field_translation.split('=')[1:]).strip() == 'self':
                    continue

                recomposed_file += '\n'.join(data['classes'][class_]['fields'][field]['translation'])
                recomposed_file += '\n'
                total_fragments += 1

            if 'static_initializers' in data['classes'][class_]:
                for static_initializer in data['classes'][class_]['static_initializers']:
                    static_init_translation = data['classes'][class_]['static_initializers'][static_initializer]['translation']
                    if static_init_translation == [] or data['classes'][class_]['static_initializers'][static_initializer]['field_exercise'] == 'failed' or (args.fragment_name and args.fragment_name != static_initializer):
                        recomposed_file += '    def run_static_init():\n        pass # LLM could not translate this static initializer\n'
                    else:
                        recomposed_file += '\n'.join(data['classes'][class_]['static_initializers'][static_initializer]['translation'])
                    recomposed_file += '\n'
                class_initialize_methods.append(f'{class_name}.run_static_init()')

            # create static method for field initialization
            if intialize_later_fields != []:
                if len(intialize_later_fields) == 1 and intialize_later_fields[0][2] == 'self':
                    pass
                else:
                    recomposed_file += f'\n\n    @staticmethod\n    def initialize_fields() -> None:\n'
                    for field, field_name, field_value in intialize_later_fields:
                        if field_value == 'self':
                            continue
                        partial_field_name = ''.join(data['classes'][class_]['fields'][field]['partial_translation']).split('=')[0].strip().split(':')[0].strip()
                        field_name = field_name.replace(partial_field_name, f'{class_name}.{partial_field_name}')
                        field_name_lines = field_name.split('    ')
                        recomposed_file += '        '
                        for i in range(len(field_name_lines)):
                            recomposed_file += field_name_lines[i]
                            recomposed_file += '\n        ' if i != len(field_name_lines) - 1 else ''
                        recomposed_file += ' = ' + field_value
                        # recomposed_file += '    ' + ''.join(data['classes'][class_]['fields'][field]['partial_translation']).replace(f'{field_name}', f'{class_.split(":")[1]}.{field_name}') + field_value
                        recomposed_file += '\n\n'
                    class_initialize_methods.append(f'{class_name}.initialize_fields()')
                        
            for method in data['classes'][class_]['methods']:

                if data['classes'][class_]['methods'][method]['is_overload']:
                    continue

                # ignore constructors in test files
                if data['classes'][class_]['methods'][method]['is_constructor'] and 'src.test' in schema and 'unittest.TestCase' in data['classes'][class_]['python_class_declaration']:
                    continue

                if args.fragment_name:
                    if args.fragment_name != method:
                        recomposed_file += '\n'.join(data['classes'][class_]['methods'][method]['partial_translation']).replace('    pass', '    pass # LLM could not translate this method')
                        recomposed_file += '\n'
                        total_fragments += 1
                        continue

                # ignore constructors in test files
                # if data['classes'][class_]['methods'][method]['is_constructor'] and 'src.test' in schema and has_test_method(data['classes'][class_]['methods']):
                #     continue

                if '@Ignore' in [x.split('(')[0] for x in data['classes'][class_]['methods'][method]['annotations']] or '@ParameterizedTest' in [x.split('(')[0] for x in data['classes'][class_]['methods'][method]['annotations']]:
                    recomposed_file += '\n    @pytest.mark.skip(reason="Ignore")\n'

                if data['classes'][class_]['methods'][method]['translation'] == []:
                    if '@Test' in [x.split('(')[0] for x in data['classes'][class_]['methods'][method]['annotations']]:
                        recomposed_file += '\n'.join([''] + data['classes'][class_]['methods'][method]['partial_translation']).replace('    pass', '    pytest.fail("LLM could not translate this method")')
                    else:
                        recomposed_file += '\n'.join([''] + data['classes'][class_]['methods'][method]['partial_translation']).replace('    pass', '    pass # LLM could not translate this method')
                    recomposed_file += '\n'
                    total_unsuccessful += 1
                    continue
                
                method_translation = '\n'.join(data['classes'][class_]['methods'][method]['translation']).replace('_setUp(', 'setUp(').replace('_tearDown(', 'tearDown(')
                
                if data['classes'][class_]['methods'][method]['is_constructor']:
                    
                    method_translation = method_translation.split('\n')
                    private_field_lines = []

                    for field in non_static_fields:
                        field_translation = ''
                        if data['classes'][class_]['fields'][field]['translation'] == [] or data['classes'][class_]['fields'][field]['field_exercise'] == 'failed':
                            field_translation = '\n'.join([''] + data['classes'][class_]['fields'][field]['partial_translation']).rstrip() + ' None'
                        else:
                            field_translation = '\n'.join(data['classes'][class_]['fields'][field]['translation'])
                        
                        import_lines, translation_lines = [], []
                        
                        for line in field_translation.split('\n'):
                            if line.strip() == '':
                                continue
                            if line.strip().startswith('from '):
                                import_lines.append(line)
                            else:
                                assignment = line.split('=')[1].strip()
                                if assignment in [x.split(':')[1].strip() for x in static_fields]:
                                    line = line.replace(assignment, f'{class_name}.{assignment}')
                                translation_lines.append(line)
                        
                        partial_field_translation = field.split(':')[1].strip()
                        if 'private' in data['classes'][class_]['fields'][field]['modifiers']:
                            partial_field_translation = f'__{partial_field_translation}'
                        elif 'protected' in data['classes'][class_]['fields'][field]['modifiers']:
                            partial_field_translation = f'_{partial_field_translation}'
                            
                        if f'self.{partial_field_translation} ' in method_translation:
                            continue
                        
                        for line in import_lines:
                            # method_translation += f'\n        {line.strip()}'
                            private_field_lines.append(f'        {line.strip()}')
                        
                        for line in translation_lines:
                            # method_translation += f'\n        self.{line.strip()}'
                            private_field_lines.append(f'        self.{line.strip()}')
                    
                    constructor_first_line = 0
                    for i, line in enumerate(method_translation):
                        if line.strip().endswith(':'):
                            constructor_first_line = i
                            break
                    for line in private_field_lines[::-1]:
                        method_translation.insert(constructor_first_line+1, line)
                    
                    method_translation = '\n'.join(method_translation)

                recomposed_file += method_translation
                recomposed_file += '\n'
                total_fragments += 1

                if '@Test' in [x.split('(')[0] for x in data['classes'][class_]['methods'][method]['annotations']]:
                    if not method.split(':')[1].startswith('test'):
                        recomposed_file = recomposed_file.replace(f'def {method.split(":")[1]}', f'def test{method.split(":")[1]}')

            has_toString_method = False
            for method in data['classes'][class_]['methods']:
                if method.split(':')[1] == 'toString':
                    has_toString_method = True
                    break
            
            if has_toString_method:
                recomposed_file += f'    def __repr__(self) -> str:\n        return self.toString()\n'
                
            is_comparator = False
            for method in data['classes'][class_]['methods']:
                if method.split(':')[1] == 'compare' and '@Override' in [x.split('(')[0] for x in data['classes'][class_]['methods'][method]['annotations']]:
                    is_comparator = True
                    break
            
            if is_comparator:
                recomposed_file += f'    def __call__(self, opt1, opt2) -> int:\n        return self.compare(opt1, opt2)\n'

        for initialize_method in class_initialize_methods:
            recomposed_file += f'\n\n{initialize_method}'

        import_map = {'ABC': 'from abc import ABC\n', 'Path': 'import pathlib\n', 'IOBase': 'import io\n', 'StringIO': 'import io\n', 'io': 'import io\n', 'threading': 'import threading\n',
                      'BytesIO': 'import io\n', 'TextIOWrapper': 'import io\n', 'Number': 'import numbers\n', 'Callable': 'import typing\nfrom typing import *\n', 'enum': 'import enum\n',
                      'Type': 'import typing\nfrom typing import *\n', 'Any': 'import typing\nfrom typing import *\n', 'Iterator': 'import typing\nfrom typing import *\n', 'decimal': 'import decimal\n',
                      'Dict': 'import typing\nfrom typing import *\n', 'List': 'import typing\nfrom typing import *\n', 'Union': 'import typing\nfrom typing import *\n', 'datetime': 'import datetime\n', 
                      'os': 'import os\n', 'pickle': 'import pickle\n', 'itertools': 'import itertools\n', 'sys': 'import sys\n', 'collections': 'import collections\n', 
                      'unittest.TestCase': 'import unittest\n', 'uuid': 'import uuid\n', 'tempfile': 'import tempfile\n', 'typing': 'import typing\n', 'BytesIO': 'from io import BytesIO\n',
                      'configparser': 'import configparser\n', 'StringIO': 'from io import StringIO\n', 'IOBase': 'from io import IOBase\n', 'Number': 'import numbers\n', 'zoneinfo': 'import zoneinfo\n',
                      'urllib': 'import urllib\n', 'logging': 'import logging\n', 'mock': 'import mock\n', 'cmp_to_key': 'from functools import cmp_to_key\n', 'random': 'import random\n',
                      're': 'import re\n', 'locale': 'import locale\n', 'copy': 'import copy\n', 'traceback': 'import traceback\n', 'inspect': 'import inspect\n', 'time': 'import time\n',
                      'sqrt': 'from math import *\n', 'math': 'import math\n', 'abstractmethod': 'from abc import abstractmethod\n', 'functools': 'import functools\n'}

        python_imports = data['python_imports']
        for key in import_map:
            if key in recomposed_file and import_map[key] not in recomposed_file:
                recomposed_file = recomposed_file.replace('from __future__ import annotations\n', 'from __future__ import annotations\n' + import_map[key])
                python_imports.append(import_map[key].strip())
        
        formatted_schema_fname = '.'.join(schema.split('.')[:-1])
        sub_dir = "/".join(formatted_schema_fname.replace(".", "/").split("/")[1:-1])
        if 'collections' in sub_dir:
            sub_dir = sub_dir.replace('collections', 'collections_')
        os.makedirs(f'{args.output_dir}/{args.model_name}/{args.temperature}/{args.project_name}/{sub_dir}', exist_ok=True)

        file_path = f"{args.output_dir}/{args.model_name}/{args.temperature}/{args.project_name}/{sub_dir}/{formatted_schema_fname.split('.')[-1]}.py"

        recomposed_file = recomposed_file.replace('\u0000', '\\u0000')

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(recomposed_file)
        
        os.system(f"python3 -m black '{file_path}'")

    # add __init__.py files for each subdirectory
    for schema in os.listdir(translation_dir):
        formatted_schema_fname = '.'.join(schema.split('.')[:-1])
        sub_dir = "/".join(formatted_schema_fname.replace(".", "/").split("/")[1:-1])
        if 'collections' in sub_dir:
            sub_dir = sub_dir.replace('collections', 'collections_')
        os.makedirs(f'{args.output_dir}/{args.model_name}/{args.temperature}/{args.project_name}/{sub_dir}', exist_ok=True)

        sub_dirs = sub_dir.split('/')
        for i in range(len(sub_dirs)):
            current_sub_dir = '/'.join(sub_dirs[:i+1])
            with open(f'{args.output_dir}/{args.model_name}/{args.temperature}/{args.project_name}/{current_sub_dir}/__init__.py', 'w') as f:
                f.write('')

        file_path = f"{args.output_dir}/{args.model_name}/{args.temperature}/{args.project_name}/{sub_dir}/__init__.py"
        with open(file_path, 'w') as f:
            f.write('')
    
    with open(f'{args.output_dir}/{args.model_name}/{args.temperature}/{args.project_name}/pytest.ini', 'w') as f:
        f.write('# pytest.ini\n\n[pytest]\n# Require at least this version of pytest\nminversion = 8.2.1\n\n# Add options to control the pytest output\naddopts = -ra -q --continue-on-collection-errors --tb=native --junitxml=pytest-report.xml\n\n# Define directories to look for tests\n;testpaths = evosuite-test\ntestpaths = src/test\n\npython_files = *.py\n\npython_classes = *Test\n\npython_functions = test*\n')
    
    with open(f'{args.output_dir}/{args.model_name}/{args.temperature}/{args.project_name}/run.sh', 'w') as f:
        f.write('CURRENT_DIR=$(pwd)\nexport PYTHONPATH=$CURRENT_DIR\npython3 -m pytest\nxmllint --format pytest-report.xml -o pytest-report.xml')

    with open(f'{args.output_dir}/{args.model_name}/{args.temperature}/{args.project_name}/conftest.py', 'w') as f:
        f.write("""
# conftest.py
import pytest
import inspect
from abc import ABC

def pytest_collection_modifyitems(config, items):
    def is_abstract_class(item):
        # Check if the class of the item is a subclass of ABC (abstract base class)
        if inspect.isclass(item.cls):
            # Check if the class is actually abstract
            return ABC in item.cls.__bases__
        return False

    # Filter out items that belong to abstract classes
    items[:] = [item for item in items if not is_abstract_class(item)]
""")


if __name__ == '__main__':
    parser_ = argparse.ArgumentParser(description='Translate java types to python types')
    parser_.add_argument('--project_name', type=str, dest='project_name', help='project name to translate')
    parser_.add_argument('--model_name', type=str, dest='model_name', help='model name to translate')
    parser_.add_argument('--output_dir', type=str, dest='output_dir', help='directory to store recomposed projects')
    parser_.add_argument('--temperature', type=float, dest='temperature', help='temperature for sampling')
    parser_.add_argument('--fragment_name', type=str, dest='fragment_name', help='fragment name to recompose')
    parser_.add_argument('--suffix', type=str, dest='suffix', help='suffix to add to the recomposed files')
    args = parser_.parse_args()
    main(args)
