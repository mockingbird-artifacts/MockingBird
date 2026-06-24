import os
import json
import argparse


def main(args):

    args.schemas_dir = f'data/schemas{args.suffix}/{args.model_name}/{args.temperature}/{args.project_name}'

    os.makedirs(f'data/call_graphs/{args.project_name}', exist_ok=True)

    global_call_graph = {}
    for schema_file in os.listdir(args.schemas_dir):

        data = {}
        with open(f'{args.schemas_dir}/{schema_file}', 'r') as f:
            data = json.load(f)
        
        for class_ in data['classes']:

            global_call_graph.setdefault(class_, {'schema_file': data['path']})

            for method_ in data['classes'][class_]['methods']:
                global_call_graph[class_].setdefault(method_, [])
                for call_ in data['classes'][class_]['methods'][method_]['calls']:
                    if call_[0] == 'library':
                        continue
                    global_call_graph[class_][method_].append({'schema': call_[0], 'class': call_[1], 'method': call_[2]})

        with open(f'data/call_graphs/{args.project_name}/call_graph.json', 'w') as f:
            json.dump(global_call_graph, f, indent=4)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create call graph for test methods')
    parser.add_argument('--project_name', type=str, dest='project_name', help='name of the project')
    parser.add_argument('--model_name', type=str, dest='model_name', help='name of the model')
    parser.add_argument('--suffix', type=str, dest='suffix', help='suffix')
    parser.add_argument('--temperature', type=float, dest='temperature', help='temperature')
    args = parser.parse_args()
    main(args)
