import yaml
import json
import jinja2
import os
import dotenv
from collections import defaultdict, deque
import openai
from openai import OpenAI
from pydantic import BaseModel

from src.translation.syntactic_validation import syntactic_validation

def get_covered_method_order(covered_methods, call_graph):
    # Step 1: Build dependency graph
    graph = defaultdict(list)
    in_degree = defaultdict(int)
    all_methods = set()

    for class_data in call_graph.values():
        for caller, callees in class_data.items():
            if caller == "schema_file":
                continue
            for callee in callees:
                caller_key = caller
                callee_key = callee["method"]
                graph[caller_key].append(callee_key)
                in_degree[callee_key] += 1
                in_degree.setdefault(caller_key, 0)
                all_methods.update([caller_key, callee_key])

    # Step 2: Prepare covered method fragment names
    covered_set = set(m['fragment_name'] for m in covered_methods)

    # Step 3: Identify leaf nodes (covered methods with no outgoing edges in graph)
    leaf_nodes = {node for node in covered_set if not graph[node]}

    # Step 4: Topological sort for non-leaf nodes in covered_set
    queue = deque([node for node in in_degree if in_degree[node] == 0 and node in covered_set and node not in leaf_nodes])
    visited = set()
    covered_method_order = []

    while queue:
        node = queue.popleft()
        if node not in visited:
            covered_method_order.append(node)
            visited.add(node)
        for neighbor in graph[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0 and neighbor in covered_set and neighbor not in visited and neighbor not in leaf_nodes:
                queue.append(neighbor)

    # Step 5: Add leaf nodes (preserving order from covered_methods)
    leaf_fragments = []
    for m in covered_methods:
        frag = m['fragment_name']
        if frag in leaf_nodes and frag not in visited:
            leaf_fragments.append(frag)
            visited.add(frag)

    # Step 6: Add any disconnected covered methods not visited
    for m in covered_methods:
        frag = m['fragment_name']
        if frag not in visited:
            covered_method_order.append(frag)

    covered_method_order.extend(leaf_fragments)
    
    reverse_call_trace = []
    for covered_method in covered_method_order[::-1]:
        for m in covered_methods:
            if m['fragment_name'] == covered_method:
                reverse_call_trace.append(m)
                break

    return reverse_call_trace


def prompt_generator(args, test_exec_report, covered_method_traversal_order):
    
    execution_trace = ' -> '.join([x['fragment_name'].split(':')[1] for x in covered_method_traversal_order[::-1]])
    
    prompt = ''
    prompt_templates = yaml.safe_load(open('configs/prompt_templates.yaml', 'r'))
    
    prompt += jinja2.Template(prompt_templates['templates']['advanced_llm_prompt_base']).render(execution_trace=execution_trace, stack_trace=test_exec_report['feedback'])
    
    prompt += '\n'
    prompt += '---' * 50
    prompt += '\n'
    
    for fragment in covered_method_traversal_order:
        source_code = ''
        translation = ''
        
        schema_data = {}
        with open(f"{args.schemas_dir}/{fragment['schema_name']}.json", 'r') as f:
            schema_data = json.load(f)

        # skip if the mocking validation is success            
        if schema_data['classes'][fragment['class_name']]['methods'][fragment['fragment_name']]['mocking_validation'] == "success":
            continue
        
        source_code = '\n'.join(schema_data['classes'][fragment['class_name']]['methods'][fragment['fragment_name']]['body'])
        translation = '\n'.join(schema_data['classes'][fragment['class_name']]['methods'][fragment['fragment_name']]['translation'])
        
        api_description = add_api_description(schema_data['classes'][fragment['class_name']]['methods'][fragment['fragment_name']]['calls'])
        
        prompt += jinja2.Template(prompt_templates['templates']['advanced_llm_prompt_instance']).render(
            identifier=f"{fragment['schema_name']}|{fragment['class_name']}|{fragment['fragment_name']}",
            api_description=api_description,
            java_source_code=source_code,
            python_translation=translation
        )
        prompt += '\n'
        prompt += '---' * 50
        prompt += '\n'
    
    processed_fragments = [x['fragment_name'] for x in covered_method_traversal_order]
    
    test_dependencies = ''
    for fragment in covered_method_traversal_order:
        schema_data = {}
        with open(f"{args.schemas_dir}/{fragment['schema_name']}.json", 'r') as f:
            schema_data = json.load(f)
        
        for dependency in schema_data['classes'][fragment['class_name']]['methods'][fragment['fragment_name']]['calls']:
            if dependency[0] == 'library':
                continue
            dependency_schema = dependency[0]
            dependency_class = dependency[1]
            dependency_method = dependency[2]
            
            if dependency_method in processed_fragments:
                continue
            
            dependency_schema_data = {}
            with open(f"{args.schemas_dir}/{dependency_schema}.json", 'r') as f:
                dependency_schema_data = json.load(f)
            
            test_dependencies += '```\n    '            
            test_dependencies += '\n'.join(dependency_schema_data['classes'][dependency_class]['methods'][dependency_method]['body'])
            test_dependencies += '\n```'
            test_dependencies += '\n'

    prompt += jinja2.Template(prompt_templates['templates']['advanced_llm_prompt_dependencies']).render(test_dependencies=test_dependencies)
    
    return prompt

def prompt_model(prompt):

    class Fix(BaseModel):
        id: str
        fixed_python_translation: str
    
    class ListOfFix(BaseModel):
        final_response: list[Fix]
    
    advanced_model_name = 'llama-3-3-70b-instruct'

    model_configs = yaml.safe_load(open('configs/model_configs.yaml', 'r'))['models']
    client = OpenAI(**{k: v for k, v in model_configs[advanced_model_name].items() if k in ['api_key', 'base_url', 'default_headers']})

    messages = [
        {'role': 'system', 'content':   'You are a Java to Python Code Translation debugger.' \
                                        'You will be given a STACK TRACE and a series of JAVA SOURCE CODE snippets and their corresponding PYTHON TRANSLATION.' \
                                        'Your task is to identify and fix issues in the PYTHON TRANSLATIONS based on the provided JAVA SOURCE CODE and STACK TRACE.' \
                                        'The bug can be in one or many PYTHON TRANSLATIONS. Make sure to only fix the bug by comparing Java and Python code. DO NOT add/remove other functional parts of code.' \
                                        'You need to generate fixed PYTHON TRANSLATIONS from scratch including all method decorators and indentations properly.'},
        {'role': 'user', 'content': prompt}
    ]
    
    try:
        completion = client.beta.chat.completions.parse(
            model=model_configs[advanced_model_name]['model_id'],
            temperature=0.0,
            messages=messages,
            response_format=ListOfFix,
            extra_body=dict(guided_decoding_backend="xgrammar"),
        )
    except openai.BadRequestError as e:
        return False, e.message
    except openai.APITimeoutError as e:
        return False, e.message
    except openai.APIConnectionError as e:
        return False, e.message
    
    response = completion.choices[0].message
        
    if response and response.parsed is not None:
        return response.parsed.final_response, None
    
    return False, None


def get_api_description(api_signature, class_name):
    type_documentation = {}
    with open('data/crawl/java.base_module_doc.json') as f:
        type_documentation = json.load(f)

    class_ = class_name.split('.')[-1]
    
    for module_name in type_documentation:
        for package_name in type_documentation[module_name]:
            for class_name in type_documentation[module_name][package_name]:
                for type_ in type_documentation[module_name][package_name][class_name]:
                    if class_ != type_:
                        continue
                    for type__ in type_documentation[module_name][package_name][class_name][type_]:
                        if not isinstance(type_documentation[module_name][package_name][class_name][type_][type__], dict):
                            continue
                        if api_signature in type_documentation[module_name][package_name][class_name][type_][type__]:
                            return type_documentation[module_name][package_name][class_name][type_][type__][api_signature]

    return {}

def add_api_description(calls):
    library_api_calls = []
    for call in calls:
        if call[0] == 'library':
            library_api_calls.append(call)
    
    if not library_api_calls:
        return ''
    
    api_call_description = ''
    for call in library_api_calls:
        class_ = call[1]
        signature = call[2]
        api_description = get_api_description(signature, class_)
        if not api_description:
            continue
        api_call_description += f'API CALL SIGNATURE: {api_description["signature"]}\n'
        api_call_description += f'DESCRIPTION: {api_description["description"]}\n\n'
    
    return api_call_description


def fix_by_advance_llm(args, test_exec_report):
    
    call_graph = {}
    with open(f"data/call_graphs/{args.project_name}/call_graph.json", 'r') as f:
        call_graph = json.load(f)

    covered_method_traversal_order = get_covered_method_order(test_exec_report['covered_methods'], call_graph)
    
    prompt = prompt_generator(args, test_exec_report, covered_method_traversal_order)
    
    response, err_message = prompt_model(prompt)
        
    if not response:
        print("No response from model.")
        print(f"Error message: {err_message}")
        return False

    for fix in response:
        try:
            identifier = fix.id
            fixed_python_translation = fix.fixed_python_translation
                        
            fixed_python_translation_lines = fixed_python_translation.split('\n')
            if fixed_python_translation.startswith('def'):
                adjusted_lines = []
                for i, line in enumerate(fixed_python_translation_lines):
                    if i == 0:
                        adjusted_lines.append(f'    {line.strip()}')
                    else:
                        adjusted_lines.append(f'        {line.strip()}')
                
                fixed_python_translation = '\n'.join(adjusted_lines)
            
            if not fixed_python_translation.startswith('```') and not fixed_python_translation.endswith('```'):
                fixed_python_translation = '```python\n' + fixed_python_translation + '\n```'
                        
            fragment = {'schema_name': identifier.split('|')[0],
                        'class_name': identifier.split('|')[1],
                        'fragment_name': identifier.split('|')[2],
                        'fragment_type': 'method'
                    }
            
            signature = ''
            schema_data = {}
            with open(f'{args.schemas_dir}/{fragment["schema_name"]}.json') as f:
                schema_data = json.load(f)
            
            signature = ''.join(schema_data['classes'][fragment['class_name']]['methods'][fragment['fragment_name']]['partial_translation']).replace('pass', '').strip()

            status, fixed_python_translation, _ = syntactic_validation(fixed_python_translation, fragment, args, signature)

            if not status or fixed_python_translation is None:
                continue
            
            schema_data = {}
            with open(f"{args.schemas_dir}/{identifier.split('|')[0]}.json", 'r') as f:
                schema_data = json.load(f)
            class_name = identifier.split('|')[1]
            fragment_name = identifier.split('|')[2]
            schema_data['classes'][class_name]['methods'][fragment_name]['translation'] = fixed_python_translation
            
            with open(f"{args.schemas_dir}/{identifier.split('|')[0]}.json", 'w') as f:
                json.dump(schema_data, f, indent=4)

            print(f"Fixed translation for {identifier}:\n")
            print('\n'.join(fixed_python_translation))
        except Exception as e:
            print(f"Error processing fix for {identifier}: {e}")
            return False
    
    return True
