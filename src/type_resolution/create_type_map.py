import json
import os
import argparse


def main(args):

    args.schema_dir = f'data/schemas{args.suffix}/{args.model_name}/{args.temperature}/{args.project_name}'

    project_type_mapping = {}

    type_counts = {'total': 0, 'pending': 0, 'attempted': 0, 'translated': 0}
    
    for schema_file in os.listdir(args.schema_dir):
        data = {}
        with open(f'{args.schema_dir}/{schema_file}', 'r') as f:
            data = json.load(f)

        for class_ in data['classes']:
            for fragment_type in ['field', 'method']:
                for fragment in data['classes'][class_][f'{fragment_type}s']:
                    type_variations = {'types': 'FIELD TYPE', 'return_types': 'RETURN TYPE', 'parameters': 'PARAMETER TYPE', 'body_types': 'METHOD BODY TYPE'}
                    for type_variation in type_variations:

                        if fragment_type == 'field' and type_variation != 'types':
                            continue
                        elif fragment_type == 'method' and type_variation == 'types':
                            continue

                        for type_translation in data['classes'][class_][f'{fragment_type}s'][fragment]['type_translations'][type_variation]:
                            type_translation_key = type_translation
                            if '|' in type_translation:
                                type_translation_key = type_translation.split('|')[1]

                            project_type_mapping.setdefault(type_translation_key, [])

                            type_counts['total'] += 1
                            if not data['classes'][class_][f'{fragment_type}s'][fragment]['type_translations'][type_variation][type_translation]['translated'] and not data['classes'][class_][f'{fragment_type}s'][fragment]['type_translations'][type_variation][type_translation]['attempted']:
                                type_counts['pending'] += 1
                            elif data['classes'][class_][f'{fragment_type}s'][fragment]['type_translations'][type_variation][type_translation]['attempted']:
                                type_counts['attempted'] += 1

                            if data['classes'][class_][f'{fragment_type}s'][fragment]['type_translations'][type_variation][type_translation]['translated']:
                                type_counts['translated'] += 1
                                imports = data['classes'][class_][f'{fragment_type}s'][fragment]['type_translations'][type_variation][type_translation]['imports']
                                translated_type = data['classes'][class_][f'{fragment_type}s'][fragment]['type_translations'][type_variation][type_translation]['translated_target_type'].rsplit('\n', 1)[-1]
                                reasoning = data['classes'][class_][f'{fragment_type}s'][fragment]['type_translations'][type_variation][type_translation]['reasoning']

                                project_type_mapping[type_translation_key].append({'translated_type': translated_type, 'imports': imports, 'reasoning': reasoning})

    print(f'project: {args.project_name}')
    print(f'type counts: {type_counts}')
    print(f'type mapping success (%): {len([1 for k, v in project_type_mapping.items() if v]) / len(project_type_mapping) * 100:.2f}')
    print(f'unique types: {len(project_type_mapping)}')
    print('******' * 10)

    os.makedirs(f'data/type_resolution/{args.project_name}', exist_ok=True)
    with open(f'data/type_resolution/{args.project_name}/type_mapping.json', 'w') as f:
        json.dump(project_type_mapping, f, indent=4)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create type map')
    parser.add_argument('--project_name', type=str, dest='project_name', help='project name')
    parser.add_argument('--model_name', type=str, dest='model_name', help='model name to use for translation')
    parser.add_argument('--temperature', type=float, dest='temperature', help='temperature for generation')
    parser.add_argument('--suffix', type=str, dest='suffix', help='suffix for schema files')
    args = parser.parse_args()
    main(args)
