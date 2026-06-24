import os
import json
import argparse
import keyword
import subprocess

from src.utils.get_dependencies import get_dependencies
from src.utils.get_class_order import get_class_order
from src.utils.get_custom_types import get_custom_types
from src.utils.get_schema_file import get_schema_file


def remove_duplicate_methods(schema):
    duplicate_methods = {}
    for class_ in schema['classes']:
        duplicate_methods.setdefault(class_, {})
        for method in schema['classes'][class_]['methods']:
            schema['classes'][class_]['methods'][method]['is_overload'] = False
            method_name = method.split(':')[1].strip()
            duplicate_methods[class_].setdefault(method_name, [])
            duplicate_methods[class_][method_name].append(method)

    for class_ in duplicate_methods:
        for method_name in duplicate_methods[class_]:
            if len(duplicate_methods[class_][method_name]) > 1:
                for k in duplicate_methods[class_][method_name]:
                    schema['classes'][class_]['methods'][k]['is_overload'] = True
    
    return schema


def main(args):
    args.schemas_dir = f'data/schemas{args.suffix}/{args.model_name}/{args.temperature}/{args.project_name}'
    reserved_tokens = dir(__builtins__) + keyword.kwlist

    dependencies = get_dependencies(args)

    additional_custom_types = ['Exception']
    custom_types = get_custom_types(args.schemas_dir) + additional_custom_types

    type_mapping = {}
    with open(f'data/type_resolution/{args.project_name}/type_mapping.json', 'r') as f:
        type_mapping = json.load(f)

    with open("data/type_resolution/fixed_type_map.json", "r") as f:
        fixed_type_map = json.load(f)

    for schema_fname in os.listdir(args.schemas_dir):

        if 'package-info' in schema_fname or 'module-info' in schema_fname:
            continue

        if f'{args.project_name}.src.main' not in schema_fname and f'{args.project_name}.src.test' not in schema_fname:
            continue

        schema_path = f'{args.schemas_dir}/{schema_fname}'
        
        schema = {}
        with open(schema_path, 'r') as f:
            schema = json.load(f)
        
        schema = remove_duplicate_methods(schema)

        skeleton = 'from __future__ import annotations\n'
        skeleton += '# Imports Begin\n'
        skeleton += '# Imports End\n\n'

        target_schema = schema.copy()
        python_imports = []
        
        class_order = get_class_order(schema)
        extended_classes = set()

        for class_ in class_order:
            
            class_declaration = ''
            class_name = class_.split(':')[1].strip()
            exceptional_superclasses = {'typing.', 'Comparator', 'Queue', 'Comparable', 'threading.RLock', 'Closeable', 'Enum', 'Iterator', 'Iterable', 'scaffolding', 'Supplier', 'Runnable', '.'}          
            if schema['classes'][class_]['extends'] != []:
                schema['classes'][class_]['extends'] = [
                    cls_name.split(".")[-1]
                    if cls_name.split(".")[-1] in custom_types
                    else fixed_type_map[cls_name]
                    for cls_name in schema['classes'][class_]['extends']
                    if cls_name.split(".")[-1] in custom_types or cls_name in fixed_type_map
                ] 
                fixed_values = set(fixed_type_map.values())
                for cls_name in schema['classes'][class_]['extends']:
                    if cls_name in fixed_values and "." in cls_name:
                        python_imports.append("import " + cls_name.split(".")[0])
                schema['classes'][class_]['extends'] = [
                    cls_name
                    for cls_name in schema['classes'][class_]['extends']
                    if not any((substring in cls_name and cls_name not in fixed_values)
                        for substring in exceptional_superclasses)
                    and cls_name != class_name
                ]
                extended_classes.update(schema['classes'][class_]['extends'])

                if schema['classes'][class_]['is_abstract'] or schema['classes'][class_]['is_interface']:
                    class_declaration = 'class ' + class_name + '(' + ', '.join(schema['classes'][class_]['extends'] + ['ABC']) + '):\n\n'
                    python_imports.append('from abc import ABC')
                else:
                    class_declaration = 'class ' + class_name + '(' + ', '.join(schema['classes'][class_]['extends']) + '):\n\n'

            elif schema['classes'][class_]['implements'] != []:
                schema['classes'][class_]['implements'] = [cls_name for cls_name in schema['classes'][class_]['implements'] if cls_name in custom_types]
                schema['classes'][class_]['implements'] = [cls_name for cls_name in schema['classes'][class_]['implements'] if not any(substring in cls_name for substring in exceptional_superclasses) and cls_name != class_name]

                extended_classes.update(schema['classes'][class_]['implements'])

                for impl in schema['classes'][class_]['implements']:
                    for java_import in schema['imports']:
                        if impl in schema['imports'][java_import]['body']:
                            partial_path = schema['imports'][java_import]['body'].split()[1].replace(';', '')
                            schema_file = get_schema_file(args.project_name, partial_path, args)
                            if not schema_file:
                                continue
                            if 'src.main' in schema_file:
                                partial_path = f'src.main.{partial_path}'
                            elif 'src.test' in schema_file:
                                partial_path = f'src.test.{partial_path}'
                            python_imports.append(f'from {partial_path} import {impl}')
                            break


                if schema['classes'][class_]['is_abstract'] or schema['classes'][class_]['is_interface']:
                    class_declaration = 'class ' + class_name + '(' + ', '.join(schema['classes'][class_]['implements'] + ['ABC']) + '):\n\n'
                    python_imports.append('from abc import ABC')
                else:
                    class_declaration = 'class ' + class_name + '(' + ', '.join(schema['classes'][class_]['implements']) + '):\n\n'
            else:
                if schema['classes'][class_]['is_abstract'] or schema['classes'][class_]['is_interface']:
                    class_declaration = 'class ' + class_name + '(ABC):\n\n'
                    python_imports.append('from abc import ABC')
                else:
                    class_declaration = 'class ' + class_name + ':\n\n'

            is_test_class = False
            for method_ in schema['classes'][class_]['methods']:
                if '@Test' in [x.split('(')[0] for x in schema['classes'][class_]['methods'][method_]['annotations']]:
                    is_test_class = True
                    break

            if 'src.test' in schema_fname and is_test_class:
                if '):' not in class_declaration:
                    class_declaration = class_declaration.replace(':', '(unittest.TestCase):')
                elif '():' in class_declaration:
                    class_declaration = class_declaration.replace('():', '(unittest.TestCase):')
                elif '):' in class_declaration and 'unittest.TestCase' not in class_declaration:
                    class_declaration = class_declaration.replace('):', ', unittest.TestCase):')

            if 'src.test' in schema_fname and 'import unittest' not in python_imports:
                python_imports.append('import unittest')
            if 'src.test' in schema_fname and 'import pytest' not in python_imports:
                python_imports.append('import pytest')
            
            if schema['classes'][class_]['is_enum']:
                python_imports.append('import enum')
                if '):' not in class_declaration:
                    class_declaration = class_declaration.replace(':', '(enum.Enum):')
                elif '():' in class_declaration:
                    class_declaration = class_declaration.replace('():', '(enum.Enum):')
                else:
                    class_declaration = class_declaration.replace('):', ', enum.Enum):')
            
            if '():' in class_declaration:
                class_declaration = class_declaration.replace('():', ':')

            if '$' in class_declaration:
                class_declaration = f'class {class_declaration.split("$")[1]}'

            skeleton += class_declaration

            target_schema['classes'][class_]['python_class_declaration'] = class_declaration

            if 'static_initializers' in target_schema['classes'][class_]:
                for static_initializer_se in target_schema['classes'][class_]['static_initializers']:
                    target_schema['classes'][class_]['static_initializers'][static_initializer_se]['partial_translation'] = []

            is_empty_class = True
            skeleton += '\t# Class Fields Begin\n'
            for field in sorted(schema['classes'][class_]['fields']):
                is_empty_class = False
                field_name = field.split(':')[1].strip()
                if 'protected' in schema['classes'][class_]['fields'][field]['modifiers']:
                    field_name = '_' + field_name
                elif 'private' in schema['classes'][class_]['fields'][field]['modifiers']:
                    field_name = '__' + field_name
                
                field_type = 'object'
                assert len(schema['classes'][class_]['fields'][field]['types']) == 1 or len(schema['classes'][class_]['fields'][field]['types']) == 0

                if len(schema['classes'][class_]['fields'][field]['types']) == 1:
                    source_type = schema['classes'][class_]['fields'][field]['types'][0]
                    if schema['classes'][class_]['fields'][field]['type_translations']['types'][source_type]['translated']:
                        field_type = schema['classes'][class_]['fields'][field]['type_translations']['types'][source_type]['translated_target_type']
                    elif not schema['classes'][class_]['fields'][field]['type_translations']['types'][source_type]['translated'] and source_type and type_mapping.get(source_type):
                        field_type = type_mapping[source_type][0]['translated_type']
                        
                        schema['classes'][class_]['fields'][field]['type_translations']['types'][source_type]['translated'] = True
                        schema['classes'][class_]['fields'][field]['type_translations']['types'][source_type]['translated_target_type'] = field_type
                        schema['classes'][class_]['fields'][field]['type_translations']['types'][source_type]['imports'] = type_mapping[source_type][0]['imports']
                        schema['classes'][class_]['fields'][field]['type_translations']['types'][source_type]['reasoning'] = type_mapping[source_type][0]['reasoning']
                    else:
                        field_type = 'object'
                        schema['classes'][class_]['fields'][field]['type_translations']['types'][source_type]['translated'] = True
                        schema['classes'][class_]['fields'][field]['type_translations']['types'][source_type]['translated_target_type'] = field_type
                        schema['classes'][class_]['fields'][field]['type_translations']['types'][source_type]['imports'] = ''
                        schema['classes'][class_]['fields'][field]['type_translations']['types'][source_type]['reasoning'] = f'Type {source_type} has been translated to "object"'
                        
                    python_imports.append(schema['classes'][class_]['fields'][field]['type_translations']['types'][source_type]['imports'])

                if field_type in custom_types:
                    field_type = f'"{field_type}"'

                field_body = field_name + f': {field_type} = \n'
                if '=' not in ''.join(schema['classes'][class_]['fields'][field]['body']) and not schema['classes'][class_]['fields'][field]['enum_constant']:
                    if field_type == 'str' and 'char' in schema['classes'][class_]['fields'][field]['types']:
                        field_body = field_body.rstrip() + " '\\u0000'"
                    elif field_type == 'str' and 'String' in schema['classes'][class_]['fields'][field]['types']:
                        field_body = field_body.rstrip() + " ''"
                    elif field_type == 'int' and 'byte' in schema['classes'][class_]['fields'][field]['types']:
                        field_body = field_body.rstrip() + ' 0'
                    elif field_type == 'int' and 'short' in schema['classes'][class_]['fields'][field]['types']:
                        field_body = field_body.rstrip() + ' 0'
                    elif field_type == 'int' and 'long' in schema['classes'][class_]['fields'][field]['types']:
                        field_body = field_body.rstrip() + ' 0'
                    elif field_type == 'int' and 'int' in schema['classes'][class_]['fields'][field]['types']:
                        field_body = field_body.rstrip() + ' 0'
                    elif field_type == 'float' and 'double' in schema['classes'][class_]['fields'][field]['types']:
                        field_body = field_body.rstrip() + ' 0.0'
                    elif field_type == 'float' and 'float' in schema['classes'][class_]['fields'][field]['types']:
                        field_body = field_body.rstrip() + ' 0.0'
                    elif field_type == 'bool' and 'boolean' in schema['classes'][class_]['fields'][field]['types']:
                        field_body = field_body.rstrip() + ' False'
                    else:
                        field_body = field_body.rstrip() + ' None'
                    
                    target_schema['classes'][class_]['fields'][field]['translation'] = f'    {field_body}'.split('\n')
                    target_schema['classes'][class_]['fields'][field]['translation_status'] = 'attempted'
                    target_schema['classes'][class_]['fields'][field]['syntactic_validation'] = 'parseable'
                    target_schema['classes'][class_]['fields'][field]['field_exercise'] = 'success'
                        
                target_schema['classes'][class_]['fields'][field]['partial_translation'] = f'    {field_body}'.split('\n')
                skeleton += f'\t{field_name}: {field_type} = None\n'
            
            skeleton += '\t# Class Fields End\n\n'

            skeleton += '\t# Class Methods Begin\n'
            for method in schema['classes'][class_]['methods']:

                if schema['classes'][class_]['methods'][method]['is_overload']:
                    continue

                is_empty_class = False

                current_method = []
                method_name = method.split(':')[1].strip()

                if method_name in reserved_tokens:
                    method_name = f'{method_name}_'

                is_static = False
                if 'static' in schema['classes'][class_]['methods'][method]['modifiers']:
                    is_static = True
                    skeleton += '\t@staticmethod\n'
                    current_method += ['\t@staticmethod\n']
                
                updated_method_name = method_name
                if 'protected' in schema['classes'][class_]['methods'][method]['modifiers']:
                    updated_method_name = '_' + method_name if method_name not in ['setUp', 'tearDown'] else method_name
                elif 'private' in schema['classes'][class_]['methods'][method]['modifiers']:
                    updated_method_name = '__' + method_name if method_name not in ['setUp', 'tearDown'] else method_name

                if len(schema["classes"][class_]["methods"][method]["parameters"]) == 0:
                    if schema['classes'][class_]['methods'][method]['is_constructor']:
                        skeleton += '\tdef __init__(self) -> '
                        current_method += ['\tdef __init__(self) -> ']
                    else:
                        if not is_static:
                            skeleton += '\tdef ' + updated_method_name + '(self) -> '
                            current_method += ['\tdef ' + updated_method_name + '(self) -> ']
                        else:
                            skeleton += '\tdef ' + updated_method_name + '() -> '
                            current_method += ['\tdef ' + updated_method_name + '() -> ']
                else:
                    parameter_types = []
                    for x, y in schema["classes"][class_]["methods"][method]["type_translations"]["parameters"].items():
                        if y['translated']:
                            if y['translated_target_type'] in custom_types:
                                parameter_types.append(f'"{y["translated_target_type"]}"')
                            else:
                                parameter_types.append(y['translated_target_type'])
                        elif not y['translated'] and y['source_type'] and type_mapping.get(y['source_type']):

                            translation = type_mapping[y['source_type']][0]['translated_type']

                            schema["classes"][class_]["methods"][method]["type_translations"]["parameters"][x]['translated'] = True
                            schema["classes"][class_]["methods"][method]["type_translations"]["parameters"][x]['translated_target_type'] = translation
                            schema["classes"][class_]["methods"][method]["type_translations"]["parameters"][x]['imports'] = type_mapping[y['source_type']][0]['imports']
                            schema["classes"][class_]["methods"][method]["type_translations"]["parameters"][x]['reasoning'] = type_mapping[y['source_type']][0]['reasoning']

                            if translation in custom_types:
                                parameter_types.append(f'"{translation}"')
                            else:
                                parameter_types.append(translation)
                        else:
                            schema["classes"][class_]["methods"][method]["type_translations"]["parameters"][x]['translated'] = True
                            schema["classes"][class_]["methods"][method]["type_translations"]["parameters"][x]['translated_target_type'] = 'object'
                            schema["classes"][class_]["methods"][method]["type_translations"]["parameters"][x]['imports'] = ''
                            schema["classes"][class_]["methods"][method]["type_translations"]["parameters"][x]['reasoning'] = f'Type {y["source_type"]} has been translated to "object"'
                            parameter_types.append('object')
                                        
                    python_imports += [y['imports'] for x, y in schema["classes"][class_]["methods"][method]["type_translations"]["parameters"].items() if y['translated']]
                    parameters = [x['name'] for x in schema["classes"][class_]["methods"][method]["parameters"]]
                    param_types = [(x, y) for x, y in zip(parameters, parameter_types)]
                    param_types = [(f'{x}_', y) if x in reserved_tokens else (x, y) for x, y in param_types]

                    if schema['classes'][class_]['methods'][method]['is_constructor']:
                        skeleton += '\tdef __init__(self, ' + ', '.join([x + f': {y.strip()}' for x, y in param_types]) + ') -> '
                        current_method += ['\tdef __init__(self, ' + ', '.join([x + f': {y.strip()}' for x, y in param_types]) + ') -> ']
                    else:
                        if not is_static:
                            skeleton += '\tdef ' + updated_method_name + '(self, ' + ', '.join([x + f': {y.strip()}' for x, y in param_types]) + ') -> '
                            current_method += ['\tdef ' + updated_method_name + '(self, ' + ', '.join([x + f': {y.strip()}' for x, y in param_types]) + ') -> ']
                        else:
                            skeleton += '\tdef ' + updated_method_name + '(' + ', '.join([x + f': {y.strip()}' for x, y in param_types]) + ') -> '
                            current_method += ['\tdef ' + updated_method_name + '(' + ', '.join([x + f': {y.strip()}' for x, y in param_types]) + ') -> ']

                return_type = 'None'
                if len(schema['classes'][class_]['methods'][method]['return_types']) > 0:
                    for source_type in schema['classes'][class_]['methods'][method]['return_types']:
                        if not schema['classes'][class_]['methods'][method]['type_translations']['return_types'][source_type]['translated'] and type_mapping[source_type]:
                            
                            return_type = type_mapping[source_type][0]['translated_type']
                            python_imports.append(type_mapping[source_type][0]['imports'])

                            schema['classes'][class_]['methods'][method]['type_translations']['return_types'][source_type]['translated'] = True
                            schema['classes'][class_]['methods'][method]['type_translations']['return_types'][source_type]['translated_target_type'] = return_type
                            schema['classes'][class_]['methods'][method]['type_translations']['return_types'][source_type]['imports'] = type_mapping[source_type][0]['imports']
                            schema['classes'][class_]['methods'][method]['type_translations']['return_types'][source_type]['reasoning'] = type_mapping[source_type][0]['reasoning']
                            continue

                        elif not schema['classes'][class_]['methods'][method]['type_translations']['return_types'][source_type]['translated']:
                            return_type = 'object'
                            schema['classes'][class_]['methods'][method]['type_translations']['return_types'][source_type]['translated'] = True
                            schema['classes'][class_]['methods'][method]['type_translations']['return_types'][source_type]['translated_target_type'] = return_type
                            schema['classes'][class_]['methods'][method]['type_translations']['return_types'][source_type]['imports'] = ''
                            schema['classes'][class_]['methods'][method]['type_translations']['return_types'][source_type]['reasoning'] = f'Type {source_type} has been translated to "object"'
                            continue
                        return_type = schema['classes'][class_]['methods'][method]['type_translations']['return_types'][source_type]['translated_target_type']
                        python_imports.append(schema['classes'][class_]['methods'][method]['type_translations']['return_types'][source_type]['imports'])
                
                for body_type in schema['classes'][class_]['methods'][method]['type_translations']['body_types']:
                    if body_type in type_mapping and len(type_mapping[body_type]) > 0:
                        python_imports.append(type_mapping[body_type][0]['imports'])
                    if not schema['classes'][class_]['methods'][method]['type_translations']['body_types'][body_type]['translated'] and body_type and type_mapping.get(body_type):
                        schema['classes'][class_]['methods'][method]['type_translations']['body_types'][body_type]['translated'] = True
                        schema['classes'][class_]['methods'][method]['type_translations']['body_types'][body_type]['translated_target_type'] = type_mapping[body_type][0]['translated_type']
                        schema['classes'][class_]['methods'][method]['type_translations']['body_types'][body_type]['imports'] = type_mapping[body_type][0]['imports']
                        schema['classes'][class_]['methods'][method]['type_translations']['body_types'][body_type]['reasoning'] = type_mapping[body_type][0]['reasoning']
                    elif not schema['classes'][class_]['methods'][method]['type_translations']['body_types'][body_type]['translated']:
                        schema['classes'][class_]['methods'][method]['type_translations']['body_types'][body_type]['translated'] = True
                        schema['classes'][class_]['methods'][method]['type_translations']['body_types'][body_type]['translated_target_type'] = 'object'
                        schema['classes'][class_]['methods'][method]['type_translations']['body_types'][body_type]['imports'] = ''
                        schema['classes'][class_]['methods'][method]['type_translations']['body_types'][body_type]['reasoning'] = f'Type {body_type} has been translated to "object"'

                if 'src.test' in schema_fname:
                    has_setup_method = False
                    setup_method = ''
                    for m in schema['classes'][class_]['methods']:
                        if '@Before' in [x.split('(')[0] for x in schema['classes'][class_]['methods'][m]['annotations']]:
                            has_setup_method = True
                            setup_method = m
                            break
                    
                    if has_setup_method and method != setup_method and [schema_fname.replace('.json', ''), class_, setup_method] not in schema['classes'][class_]['methods'][method]['calls']:
                        schema['classes'][class_]['methods'][method]['calls'].append([schema_fname.replace('.json', ''), class_, setup_method])
                
                if return_type in custom_types:
                    return_type = f'"{return_type}"'

                skeleton += f'{return_type}:\n\t\tpass\n\n'

                current_method[-1] = current_method[-1] + f'{return_type}:\n'
                current_method += ['\t\tpass\n\n']
                current_method = [x.replace('\t', '    ') for x in current_method]

                target_schema['classes'][class_]['methods'][method]['partial_translation'] = current_method

            skeleton += '\t# Class Methods End\n\n\n'

            if is_empty_class:
                skeleton += '\tpass\n\n'

        dependency_key = [x for x in dependencies if f'{x}.json' in schema_fname][0]

        for dependent_class in dependencies[dependency_key]:

            dependent_class_name = dependent_class[0]
            dependent_class_path = dependent_class[1]

            schema_file = get_schema_file(args.project_name, dependent_class_path, args)

            path = dependent_class_path
            if 'src.main' in schema_file:
                path = f'src.main.{path}'
            elif 'src.test' in schema_file:
                path = f'src.test.{path}'

            if f'from {path} import {dependent_class_name}' in skeleton:
                continue

            if dependent_class_name not in extended_classes:
                continue

            path = path.replace('collections', 'collections_')

            python_imports.append(f'from {path} import {dependent_class_name}')
        
        python_imports = [x for x in python_imports if x and not any(pattern in x for pattern in ('# No import', 'None', 'NoneType', 'assertNotEqual'))]

        for imports in python_imports:
            if imports not in skeleton:
                skeleton = skeleton.replace('# Imports End\n', f'{imports}\n# Imports End\n')

        target_schema.setdefault('python_imports', [])

        skeleton = skeleton.replace('\t', '    ')
        skeleton_lines = skeleton.split('\n')
        for i in range(len(skeleton_lines)):
            current_line = skeleton_lines[i]
            for exceptional_import in ['commons.io', 'commons.logging', 'opentest4j', 'com.google', 'org.evosuite', 'scaffolding']:
                if exceptional_import in current_line:
                    skeleton_lines[i] = f'# {current_line}'
                    if current_line in python_imports:
                        python_imports[python_imports.index(current_line)] = f'# {current_line}'

        python_imports = list(set(python_imports))
        python_imports.sort()
        python_imports.insert(0, 'from __future__ import annotations')
        target_schema['python_imports'] = python_imports

        skeleton = '\n'.join(skeleton_lines)

        skeletons_dir = f'data/recomposed_projects/{args.model_name}/{args.temperature}/{args.project_name}'

        os.makedirs(skeletons_dir, exist_ok=True)

        formatted_schema_fname = '.'.join(schema_fname.split('.')[:-1])
        sub_dir = "/".join(formatted_schema_fname.replace(".", "/").split("/")[1:-1])

        if 'collections' in sub_dir:
            sub_dir = sub_dir.replace('collections', 'collections_')

        os.makedirs(f'{skeletons_dir}/{sub_dir}', exist_ok=True)
        file_path = f"{skeletons_dir}/{sub_dir}/{formatted_schema_fname.split('.')[-1]}.py"
        with open(file_path, 'w') as f:
            f.write(skeleton)

        os.system(f"python3 -m black '{file_path}'") # check for syntactical errors

        # add __init__.py files for each subdirectory
        sub_dirs = sub_dir.split('/')
        for i in range(len(sub_dirs)):
            current_sub_dir = '/'.join(sub_dirs[:i+1])
            with open(f'{skeletons_dir}/{current_sub_dir}/__init__.py', 'w') as f:
                f.write('')

        fp = f"{skeletons_dir}/{sub_dir}/__init__.py"
        with open(fp, 'w') as f:
            f.write('')

        with open(f'{args.schemas_dir}/{schema_fname}', 'w') as f:
            json.dump(target_schema, f, indent=4)

    def find_files(directory):
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.endswith('.py'):
                    yield os.path.join(root, file)
    
    for file in find_files(skeletons_dir):
        print(f'checking {file} for runtime errors...')
        env = os.environ.copy()
        env['PYTHONPATH'] = f'{os.getcwd()}/{skeletons_dir}'

        try:
            subprocess.run(['python3', file], check=True, capture_output=True, text=True, env=env)
        except subprocess.CalledProcessError as e:
            print(f'Error in {file}: {e.stderr}')
            exit()
        
    os.system(f'find ./data/recomposed_projects -name "__pycache__" -type d -exec rm -rf {{}} +')
    os.system(f'find ./data/recomposed_projects -name ".pytest_cache" -type d -exec rm -rf {{}} +')

    # copy resources folders (i.e., all dirs under java_projects/cleaned_final_projects{suffix}/{project_name}/src/test excluding "java")
    all_dirs = []
    for root, dirs, files in os.walk(f'java_projects/cleaned_final_projects{args.suffix}/{args.project_name}/src/test'):
        all_dirs.extend(dirs)
        break

    for dir_ in all_dirs:
        if dir_ == 'java':
            continue
        os.system(f'cp -r java_projects/cleaned_final_projects{args.suffix}/{args.project_name}/src/test/{dir_} data/recomposed_projects/{args.model_name}/{args.temperature}/{args.project_name}/src/test')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create a class skeleton')
    parser.add_argument('--project_name', type=str, dest='project_name', help='name of the project')
    parser.add_argument('--model_name', type=str, dest='model_name', help='name of the model')
    parser.add_argument('--suffix', type=str, dest='suffix', help='suffix')
    parser.add_argument('--temperature', type=float, dest='temperature', help='temperature')
    args = parser.parse_args()
    
    main(args)
