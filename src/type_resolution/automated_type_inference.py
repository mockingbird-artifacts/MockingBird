import json
import os
import re
import argparse


class Pattern:
    def __init__(self):
        pass

    def has_pattern_0(self, s): # "List<String>"
        return bool(re.match(r"^[^<>]*<[^<>]*>[^<>]*$", s))
    
    def has_pattern_1(self, s): # TypeA.TypeB
        total_dots = s.count('.')
        if total_dots == 1 and '<' not in s and '>' not in s:
            return True
        return False

    def has_pattern_2(self, s): # "Map<String, String>"
        return bool(re.match(r".*<.*,.*>", s)) and s.count(',') == 1 and '.' not in s

    def has_pattern_3(self, s): # "Map<String, String, String>"
        return bool(re.match(r".*<.*,.*,.*>", s)) and s.count(',') == 2 and '.' not in s


def is_available_in_universal_type_map(type_, other_projects):
    for other_project in other_projects:
        with open(f'data/type_resolution/{other_project}/type_mapping.json', 'r') as f:
            project_type_map = json.load(f)
            if type_ in project_type_map and project_type_map[type_]:
                return True, project_type_map[type_]

    return False, None

def get_custom_types(schema_dir):
    custom_types = []
    for schema_file in os.listdir(schema_dir):
        data = {}
        with open(f'{schema_dir}/{schema_file}', 'r') as f:
            data = json.load(f)
        
        for class_ in data['classes']:
            class_name = class_.split(':')[1]
            custom_types.append(class_name)
            if data['classes'][class_]['nested_inside'] != '':
                outer_class = data['classes'][class_]['nested_inside'].split(':')[1]
                custom_types.append(f'{outer_class}.{class_name}')
    
    return custom_types    


def main(args):

    args.schema_dir = f'data/schemas{args.suffix}/{args.model_name}/{args.temperature}/{args.project_name}'

    custom_types = get_custom_types(args.schema_dir)
    # print(custom_types)

    project_type_map = {}
    with open(f'data/type_resolution/{args.project_name}/type_mapping.json', 'r') as f:
        project_type_map = json.load(f)

    other_projects = [p for p in os.listdir('data/type_resolution') if p != args.project_name and os.path.isdir(f'data/type_resolution/{p}')]

    for type_ in project_type_map:
        if not project_type_map[type_]:
            
            # 1. Check if the type is available in universal type map (other projects)
            is_available, type_translation = is_available_in_universal_type_map(type_, other_projects)
            if is_available:
                project_type_map[type_] = type_translation
                continue

            # 2. Check if the type is a custom type
            if type_.endswith("<>"):
                if type_[:-2] in custom_types:
                    project_type_map[type_] = [{'translated_type': type_[:-2], 'imports': '', 'reasoning': f'Custom type {type_[:-2]} is an application-level type which does not require any translation.'}]
                    continue

            # 3. Check if the type is a generic type
            if '<' in type_ and '>' in type_:
                if type_[:type_.find('<')] in custom_types:
                    project_type_map[type_] = [{'translated_type': type_[:type_.find('<')], 'imports': '', 'reasoning': f'Custom type {type_[:type_.find("<")]} is an application-level type which does not require any translation.'}]
                    continue
                
                elif type_[:type_.find('<')] in ['Iterable', 'Iterator', 'PriorityQueue', 'Collection', 'Enumeration']:
                    project_type_map[type_] = [{'translated_type': 'list', 'imports': '', 'reasoning': f'Generic type {type_} is a collection type which is translated to a list.'}]
                    continue

            # 4. Check if the type is a complex type
            if type_ in ['Iterable', 'Iterator', 'PriorityQueue', 'Collection', 'Enumeration']:
                project_type_map[type_] = [{'translated_type': 'list', 'imports': '', 'reasoning': f'Generic type {type_} is a collection type which is translated to a list.'}]
                continue

            # 5. Check if the type is a pattern
            if type_.startswith('<') and type_.endswith('>'):
                project_type_map[type_] = [{'translated_type': 'object', 'imports': '', 'reasoning': f'Generic type {type_} is a pattern which is translated to an object.'}]
                continue

    print(f'type mapping after automated inference: {args.project_name}')
    print(f'type mapping success (%): {len([1 for k, v in project_type_map.items() if v]) / len(project_type_map) * 100:.2f}')
    print('******' * 10)

    with open(f'data/type_resolution/{args.project_name}/type_mapping.json', 'w') as f:
        json.dump(project_type_map, f, indent=4)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Automated type inference of complex types')
    parser.add_argument('--project_name', type=str, dest='project_name', help='project name')
    parser.add_argument('--model_name', type=str, dest='model_name', help='model name to use for translation')
    parser.add_argument('--temperature', type=float, dest='temperature', help='temperature for generation')
    parser.add_argument('--suffix', type=str, dest='suffix', help='suffix for schema files')
    args = parser.parse_args()
    main(args)
