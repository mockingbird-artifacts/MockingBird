import argparse
import json
import tqdm
import os
import time
import re
import requests
import datetime
import yaml
import shutil

from src.compositional_glue_tests.script import NOT_EXERCISED, SUCCESS, ERROR, FAILURE
from syntactic_validation import syntactic_validation
from field_exercise_validation import field_exercise_validation
from test_validation import test_validation
from graal_validation import graal_validation
from get_reverse_traversal import get_reverse_traversal
from prompt_generator import PromptGenerator
from src.model.model import Model
from src.mocking.validate_by_mocking import ValidateByMocking
from src.decomposition.create_schema import get_language_parser, extract_text_by_bytes
from src.translation.fix_by_advance_llm import fix_by_advance_llm

py_language_parser = get_language_parser('python')

class Interaction:
    def __init__(self, role, content):
        self.role = role
        self.content = content


def get_eligible_tests(fragment, processed_fragments, args):

    global_call_graph = {}
    with open(f'data/call_graphs/{args.project_name}/call_graph.json', 'r') as f:
        global_call_graph = json.load(f)

    test_focal_method_map = {}
    for class_ in global_call_graph:
        for method_ in global_call_graph[class_]:
            if method_ == 'schema_file' or 'src/test' not in global_call_graph[class_]['schema_file']:
                continue

            test_method = f"{global_call_graph[class_]['schema_file']}|{class_}|{method_}"

            test_focal_method_map.setdefault(test_method, [])
            for focal_method in global_call_graph[class_][method_]:
                test_focal_method_map[test_method].append(f"{focal_method['schema']}|{focal_method['class']}|{focal_method['method']}")

    executable_tests = []
    for test in test_focal_method_map:

        if f"{fragment['schema_name']}|{fragment['class_name']}|{fragment['fragment_name']}" not in test_focal_method_map[test]:
            continue

        other_fragments = [x for x in test_focal_method_map[test] if x != f"{fragment['schema_name']}|{fragment['class_name']}|{fragment['fragment_name']}"]        
        
        if all(focal_method in processed_fragments for focal_method in other_fragments) or other_fragments == []:
            test_schema = '.'.join(test.split('|')[0].split('/')[2:]).replace('.java', '')
            test_class = test.split('|')[1]
            test_method = test.split('|')[2]

            test_schema_data = {}
            with open(f'{args.schemas_dir}/{test_schema}.json', 'r') as f:
                test_schema_data = json.load(f)
            if test_class not in test_schema_data['classes']:
                continue
            if test_method not in test_schema_data['classes'][test_class]['methods']:
                continue
            if '@Test' not in [x.split('(')[0] for x in test_schema_data['classes'][test_class]['methods'][test_method]['annotations']]:
                continue
            if '@Ignore' in [x.split('(')[0] for x in test_schema_data['classes'][test_class]['methods'][test_method]['annotations']]:
                continue
            if '@Disabled' in [x.split('(')[0] for x in test_schema_data['classes'][test_class]['methods'][test_method]['annotations']]:
                continue

            executable_tests.append({'schema_name': test_schema, 'class_name': test_class, 'fragment_name': test_method, 'fragment_type': 'method', 'is_test_method': True})

    non_decomposed_tests = [x for x in executable_tests if '_decomposed' not in x['fragment_name']]
    executable_tests = [x for x in executable_tests if '_decomposed' in x['fragment_name']]
    executable_tests = sorted(executable_tests, key=lambda x: int(x['fragment_name'].split('_')[-2][4:]))
    executable_tests = executable_tests + non_decomposed_tests
    return executable_tests


def get_pending_fragments(fragment_traversal, args):
    """
    Extract all pending fragments which require translation
    """

    processed_fragments, pending_fragments = [], []
    for fragment in fragment_traversal:
        schema_data = {}
        with open(f'{args.schemas_dir}/{fragment["schema_name"]}.json', 'r') as f:
            schema_data = json.load(f)

        if schema_data['classes'][fragment['class_name']][f'{fragment["fragment_type"]}s'][fragment['fragment_name']]['translation_status'] in ['attempted', 'out_of_context']:
            processed_fragments.append(f'{fragment["schema_name"]}|{fragment["class_name"]}|{fragment["fragment_name"]}')
            continue

        pending_fragments.append(fragment)
    
    return processed_fragments, pending_fragments


def get_graal_failure_fragments(fragment_traversal, args):
    """
    Extract all graal failure fragments which require translation
    """

    processed_fragments, pending_fragments = [], []
    for fragment in fragment_traversal:
        schema_data = {}
        with open(f'{args.schemas_dir}/{fragment["schema_name"]}.json', 'r') as f:
            schema_data = json.load(f)
        
        graal_outcome = None
        if isinstance(schema_data['classes'][fragment['class_name']][f'{fragment["fragment_type"]}s'][fragment['fragment_name']]['graal_validation'], dict):
            if 'outcome' in schema_data['classes'][fragment['class_name']][f'{fragment["fragment_type"]}s'][fragment['fragment_name']]['graal_validation']:
                graal_outcome = schema_data['classes'][fragment['class_name']][f'{fragment["fragment_type"]}s'][fragment['fragment_name']]['graal_validation']['outcome']

            elif 'graal_outcome' in schema_data['classes'][fragment['class_name']][f'{fragment["fragment_type"]}s'][fragment['fragment_name']]['graal_validation']:
                graal_outcome = schema_data['classes'][fragment['class_name']][f'{fragment["fragment_type"]}s'][fragment['fragment_name']]['graal_validation']['graal_outcome']

        else:
            graal_outcome = schema_data['classes'][fragment['class_name']][f'{fragment["fragment_type"]}s'][fragment['fragment_name']]['graal_validation']

        assert graal_outcome != None

        if graal_outcome not in ['failed', 'failure']:
            processed_fragments.append(f'{fragment["schema_name"]}|{fragment["class_name"]}|{fragment["fragment_name"]}')
            continue

        pending_fragments.append(fragment)
    
    return processed_fragments, pending_fragments


def update_labels(args, fragment, translation, translation_status, syntactic_validation, field_exercise, graal_validation, mocking_validation, test_execution, elapsed_time, update_test_execution=False, fixed_by_simple_reprompt=False, fixed_by_advanced_reprompt=False):
    """
    Update the labels of the fragment in the schema file
    """
    schema_data = {}
    with open(f'{args.schemas_dir}/{fragment["schema_name"]}.json', 'r') as f:
        schema_data = json.load(f)
    
    if update_test_execution:
        # if dict ... update test_execution
        if isinstance(schema_data['classes'][fragment['class_name']]['methods'][fragment['fragment_name']]['test_execution'], dict):
            schema_data['classes'][fragment['class_name']]['methods'][fragment['fragment_name']]['test_execution'].update(test_execution)
        else:
            schema_data['classes'][fragment['class_name']]['methods'][fragment['fragment_name']]['test_execution'] = test_execution
    else:
        schema_data['classes'][fragment['class_name']][f'{fragment["fragment_type"]}s'][fragment['fragment_name']]['translation'] = translation
        schema_data['classes'][fragment['class_name']][f'{fragment["fragment_type"]}s'][fragment['fragment_name']]['translation_status'] = translation_status
        schema_data['classes'][fragment['class_name']][f'{fragment["fragment_type"]}s'][fragment['fragment_name']]['syntactic_validation'] = syntactic_validation
        schema_data['classes'][fragment['class_name']][f'{fragment["fragment_type"]}s'][fragment['fragment_name']]['field_exercise'] = field_exercise
        schema_data['classes'][fragment['class_name']][f'{fragment["fragment_type"]}s'][fragment['fragment_name']]['graal_validation'] = graal_validation
        schema_data['classes'][fragment['class_name']][f'{fragment["fragment_type"]}s'][fragment['fragment_name']]['mocking_validation'] = mocking_validation
        if isinstance(schema_data['classes'][fragment['class_name']][f'{fragment["fragment_type"]}s'][fragment['fragment_name']]['test_execution'], dict):
            pass
        else:
            schema_data['classes'][fragment['class_name']][f'{fragment["fragment_type"]}s'][fragment['fragment_name']]['test_execution'] = test_execution
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


def get_adaptive_budget(fragment, args, feedback=False):
    return 4


def is_test_parseable(test, args):
    """
    Check if a test is translated properly
    """
    schema_data = {}
    with open(f'{args.schemas_dir}/{test["schema_name"]}.json', 'r') as f:
        schema_data = json.load(f)

    if schema_data['classes'][test['class_name']]['methods'][test['fragment_name']]['syntactic_validation'] == 'parseable':
        return True

    return False


def get_test_fragment(test, executable_eligible_tests):

    test_schema = test.split('::')[0].replace('/', '.').replace('.py', '')
    test_class = test.split('::')[1]
    test_method = test.split('::')[2]

    test_fragment = {}
    for test_ in executable_eligible_tests:
        
        if test_schema == '.'.join(test_['schema_name'].split('.')[1:]) and test_class == test_['class_name'].split(':')[1] and len(test_method) - 4 == len(test_['fragment_name'].split(':')[1]):
            test_method = test_method[4:]

        if test_schema == '.'.join(test_['schema_name'].split('.')[1:]) and test_class == test_['class_name'].split(':')[1] and test_method == test_['fragment_name'].split(':')[1]:
            test_fragment = test_
            break
    
    return test_fragment


def test_has_attribute_error(test_execution_details):
    # Regular expression to match the AttributeError
    error_regex = r"AttributeError: (.+)"
    method_regex = r"File \"(.+)\", line \d+, in (\w+)"
    
    error_message = None
    filepath = None
    method_name = None
    traceback_str = test_execution_details['feedback']

    lines = traceback_str.strip().splitlines()
    
    for i, line in enumerate(lines):
        # Match the error message
        error_match = re.search(error_regex, line)
        if error_match:
            error_message = "AttributeError: " + error_match.group(1)
        
        # Match the method name and file path
        method_match = re.search(method_regex, line)
        if method_match:
            filepath = method_match.group(1)
            method_name = method_match.group(2)
    
    if method_name is None or filepath is None:
        return False
    
    if '_decomposed' not in method_name or 'test' not in method_name:
        return False

    if 'src/test' in filepath and (error_message and 'AttributeError' in error_message):
        return True
    
    return False


def add_local_imports(args, fragment, generation, is_enum_constant=False):

    content = '\n'.join(generation)

    tree = py_language_parser.parse(bytes(content, "utf8"))

    identifier_nodes = []
    def traverse_tree(node):
        if node.type == 'identifier':
            identifier_nodes.append(extract_text_by_bytes(content, node.start_byte, node.end_byte))

        for child in node.children:
            traverse_tree(child)

    traverse_tree(tree.root_node)
    
    dependencies = []
    if fragment['fragment_type'] == 'method':
        schema_data = {}
        with open(f'{args.schemas_dir}/{fragment["schema_name"]}.json', 'r') as f:
            schema_data = json.load(f)
            for call in schema_data['classes'][fragment['class_name']][f'{fragment["fragment_type"]}s'][fragment['fragment_name']]['calls']:
                dependencies.append(call[0].replace(f'{args.project_name}.', '', 1))

    local_imports = []
    current_global_imports = []
    for schema_file in os.listdir(f'{args.schemas_dir}'):

        if f'{args.project_name}.src.main' not in schema_file and f'{args.project_name}.src.test' not in schema_file:
            continue

        schema_data = {}
        with open(f'{args.schemas_dir}/{schema_file}', 'r') as f:
            schema_data = json.load(f)

        if schema_file == f'{fragment["schema_name"]}.json':
            current_global_imports = schema_data['python_imports']
            continue

        for class_name in schema_data['classes']:
            if class_name.split(':')[1] in identifier_nodes:
                
                has_the_same_class = False
                fragment_schema_data = {}
                with open(f'{args.schemas_dir}/{fragment["schema_name"]}.json', 'r') as f:
                    fragment_schema_data = json.load(f)
                
                for fragment_class_name in fragment_schema_data['classes']:
                    
                    if class_name.split(':')[1] == fragment_class_name.split(':')[1]:
                        has_the_same_class = True
                        break
                
                from_block = schema_file.replace(f'{args.project_name}.', '', 1)
                from_block = from_block.replace('.json', '')
                if from_block not in dependencies and has_the_same_class and fragment['fragment_type'] == 'method':
                    continue
                import_statement = f'from {from_block} import {class_name.split(":")[1]}'
                if import_statement in current_global_imports:
                    continue
                local_imports.append(import_statement)

    if fragment['fragment_type'] == 'field' and not is_enum_constant:
        for import_statement in local_imports:
            content = f'    {import_statement}\n' + content
    else:
        # insert imports after method declaration using AST
        def find_function_body(node):
            if node.type == "function_definition":
                for child in node.children:
                    if child.type == "block":  # Function body
                        return child
            for child in node.children:
                result = find_function_body(child)
                if result:
                    return result
            return None

        function_body = find_function_body(tree.root_node)

        if function_body:
            body_start = function_body.start_byte
            content = content.encode("utf8")
            right_whitespace = content[:body_start].split(b'\n')[-1]

            import_content = b''
            for import_statement in local_imports:
                import_content += right_whitespace + import_statement.encode("utf8") + b'\n'
            import_content += right_whitespace

            modified_code = content[:body_start].rstrip() + b'\n' + import_content + content[body_start:]
            content = modified_code.decode("utf8")
        else:
            pass
    
    if is_enum_constant:
        return content.split('\n'), local_imports
    return content.split('\n'), None


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


def translate(fragment, args, processed_fragments, budget={}, feedback=None, recursion_depth=2):

    if recursion_depth == 0:
        return
    
    model_info = yaml.safe_load(open('configs/model_configs.yaml', 'r'))['models']
    
    model = Model(model_info[args.model_name])

    if budget == {}:
        adaptive_budget = get_adaptive_budget(fragment, args)
        budget = {'syntactic': adaptive_budget, 'field_exercise': adaptive_budget, 'graal': adaptive_budget, 'mocking': adaptive_budget, 'test_execution': adaptive_budget}
        adaptive_budget_feedback = get_adaptive_budget(fragment, args, feedback=True)
        feedback_budget = {'syntactic': adaptive_budget_feedback, 'field_exercise': adaptive_budget_feedback, 'graal': adaptive_budget_feedback, 'mocking': adaptive_budget_feedback, 'test_execution': adaptive_budget_feedback}

    current_budget = 'syntactic'
    start_time = time.time()
    extracted_eligible_tests = False
    eligible_tests = []
    executable_eligible_tests = []
    interaction_history = []

    while budget[current_budget] > 0:

        if interaction_history == []:
            initial_interaction = Interaction(role='system', content='You are a helpful assistant.')
            interaction_history.append(initial_interaction)

        ############################ <TRANSLATION> ############################
        prompt_gen = PromptGenerator(is_feedback=True if feedback else False, args=args, fragment_details=fragment, feedback=feedback, use_icl_pool=True)
        prompt = prompt_gen.generate_prompt()

        if fragment['fragment_type'] == 'method' and not prompt_gen.requires_translation:
            translation = prompt_gen.schema_data['classes'][fragment['class_name']]['methods'][fragment['fragment_name']]['partial_translation']
            update_labels(args=args, fragment=fragment, translation=translation, translation_status='attempted', syntactic_validation='parseable', field_exercise='pending', graal_validation='pending', mocking_validation='pending', test_execution='not-exercised', elapsed_time=time.time() - start_time)
            break

        interaction = Interaction(role='user', content=prompt)
        interaction_history.append(interaction)

        messages = model.get_messages(interaction_history)

        if args.debug:
            print('=======================PROMPT=======================', flush=True)
            print(prompt, flush=True)
            print('=======================GENERATING=======================', flush=True)
        
        try:
            total_input_tokens = model.tokenize(messages)
        except requests.exceptions.JSONDecodeError:
            interaction_history.pop()
            continue
        
        # if prompt size exceeds model token limit, mark translation out_of_context and move on to next fragment
        if total_input_tokens >= model_info[args.model_name]['total']:
            update_labels(args=args, fragment=fragment, translation=[], translation_status='out_of_context', syntactic_validation='pending', field_exercise='pending', graal_validation='pending', mocking_validation='pending', test_execution='pending', elapsed_time=0)
            break

        api_call_status, generation = model.prompt_model(messages)

        # if there is a problem with api call, re-prompt the model without decrementing the budget
        if not api_call_status:
            interaction_history.pop()
            budget[current_budget] -= 1
            continue

        interaction = Interaction(role='system', content=generation)
        interaction_history.append(interaction)

        if args.debug:
            print(generation, flush=True)
            print('---' * 50, flush=True)
        ############################ </TRANSLATION> ############################


        ############################ <SYNTACTIC VALIDATION> ############################
        current_budget = 'syntactic'
        status, generation, unparsed_generation, feedback = syntactic_validation(generation, fragment, args, prompt_gen.signature)

        if not status:
            if budget[current_budget] - 1 == 0:
                # if syntactic validation fails after all syntactic budget attempts, mark translation as non-parseable
                update_labels(args=args, fragment=fragment, translation=[], translation_status='attempted', syntactic_validation='non-parseable', field_exercise='pending', graal_validation='pending', mocking_validation='pending', test_execution='pending', elapsed_time=time.time() - start_time)
                break

            interaction = Interaction(role='user', content=feedback)
            interaction_history.append(interaction)

            update_labels(args=args, fragment=fragment, translation=unparsed_generation.split('\n'), translation_status='attempted', syntactic_validation='non-parseable', field_exercise='pending', graal_validation='pending', mocking_validation='pending', test_execution='pending', elapsed_time=time.time() - start_time)

            if args.debug:
                print('=======================SYNTACTIC VALIDATION FAILED - REPROMPTING=======================', flush=True)

            budget[current_budget] -= 1
            continue

        # if the fragment has application methods, make sure they are locally imported
        generation, potential_local_imports = add_local_imports(args, fragment, generation, prompt_gen.is_enum_constant)
        if potential_local_imports is not None:
            with open(f'{args.schemas_dir}/{fragment["schema_name"]}.json', 'r') as f:
                schema_data = json.load(f)
            for local_import in potential_local_imports:
                if local_import not in schema_data['python_imports']:
                    schema_data['python_imports'].append(local_import)
            with open(f'{args.schemas_dir}/{fragment["schema_name"]}.json', 'w') as f:
                json.dump(schema_data, f, indent=4)
                f.flush()
                os.fsync(f.fileno())

        update_labels(args=args, fragment=fragment, translation=generation, translation_status='attempted', syntactic_validation='parseable', field_exercise='pending', graal_validation='pending', mocking_validation='pending', test_execution='pending', elapsed_time=time.time() - start_time)
        ############################ </SYNTACTIC VALIDATION> ############################

        if fragment['is_test_method']:
            return

        ############################ <FIELD EXERCISE VALIDATION> ############################
        current_budget = 'field_exercise'
        status, feedback = field_exercise_validation(fragment, args)
        # if execution validation fails, re-prompt the model
        if not status:
            # if execution validation fails after all field_exercise budget attempts, mark field_exercise status as failed
            if budget[current_budget] - 1 == 0:
                if fragment['fragment_type'] == 'method':
                    update_labels(args=args, fragment=fragment, translation=generation, translation_status='attempted', syntactic_validation='non-parseable', field_exercise='pending', graal_validation='pending', mocking_validation='pending', test_execution='pending', elapsed_time=time.time() - start_time)
                else:
                    update_labels(args=args, fragment=fragment, translation=generation, translation_status='attempted', syntactic_validation='parseable', field_exercise='failed', graal_validation='pending', mocking_validation='pending', test_execution='pending', elapsed_time=time.time() - start_time)
                    
                break
            
            interaction = Interaction(role='user', content=feedback)
            interaction_history.append(interaction)
            
            if args.debug:
                print('=======================EXECUTION VALIDATION FAILED - REPROMPTING=======================', flush=True)

            budget[current_budget] -= 1
            
            if budget[current_budget] == 0:
                pass
            else:
                continue

        # immediately store execution validation status and end the loop
        if fragment['fragment_type'] == 'method':
            update_labels(args=args, fragment=fragment, translation=generation, translation_status='attempted', syntactic_validation='parseable', field_exercise='pending', graal_validation='pending', mocking_validation='pending', test_execution='pending', elapsed_time=time.time() - start_time)
        else:
            update_labels(args=args, fragment=fragment, translation=generation, translation_status='attempted', syntactic_validation='parseable', field_exercise='success', graal_validation='pending', mocking_validation='pending', test_execution='pending', elapsed_time=time.time() - start_time)
        
        if fragment['fragment_type'] in ['field', 'static_initializer']:
            break
        ############################ </FIELD EXERCISE VALIDATION> ############################

        assert fragment['fragment_type'] not in ['field', 'static_initializer']

        ############################ <GRAAL VALIDATION> ############################
        current_budget = 'graal'
        graal_status = 'pending'
        if args.validate_by_graal and 'src.main' in fragment['schema_name']:
            status, feedback, message = graal_validation(generation, fragment, args)
            update_labels(args=args, fragment=fragment, translation=generation, translation_status='attempted', syntactic_validation='parseable', field_exercise='pending', graal_validation={'outcome': status, 'message': message}, mocking_validation='pending', test_execution='pending', elapsed_time=time.time() - start_time)

            if status == NOT_EXERCISED:
                graal_status = 'not-exercised'

            elif status == ERROR:
                graal_status = 'error'

            elif status == FAILURE:
                graal_status = 'failed'
                
                if args.debug:
                    print('=======================GRAAL VALIDATION FAILED - REPROMPTING=======================', flush=True)

                interaction = Interaction(role='user', content=feedback)
                interaction_history.append(interaction)

                budget[current_budget] -= 1
                continue
            
            elif status == SUCCESS:
                graal_status = 'success'
        ############################ </GRAAL VALIDATION> ############################
        
        ############################ <MOCKING VALIDATION> ############################
        current_budget = 'mocking'
        mocking_status = 'pending'
        if args.validate_by_mocking and 'src.main' in fragment['schema_name']:
            validate_by_mocking = ValidateByMocking(args, fragment)
            validation_result = validate_by_mocking.validate()
            
            if validation_result['outcome'] == 'success':
                mocking_status = 'success'
            elif validation_result['outcome'] == 'failed':
                mocking_status = validation_result

            if feedback != '' and validation_result['outcome'] == 'success':
                update_labels(args=args, fragment=fragment, translation=generation, translation_status='attempted', syntactic_validation='parseable', field_exercise='pending', graal_validation=graal_status, mocking_validation=mocking_status, test_execution='pending', elapsed_time=time.time() - start_time, fixed_by_simple_reprompt=True)
            else:
                update_labels(args=args, fragment=fragment, translation=generation, translation_status='attempted', syntactic_validation='parseable', field_exercise='pending', graal_validation=graal_status, mocking_validation=mocking_status, test_execution='pending', elapsed_time=time.time() - start_time)
            
            if args.fix_agent_simple and validation_result['outcome'] == 'failed':
                if args.debug:
                    print('=======================MOCKING VALIDATION FAILED - REPROMPTING=======================', flush=True)
                
                feedback = ''
                for test in validation_result['feedback'][0]:
                    feedback = validation_result['feedback'][0][test]
                
                budget[current_budget] -= 1

                if budget[current_budget] == 0:
                    pass
                else:
                    continue
            
        ############################ </MOCKING VALIDATION> ############################

        ############################ <TEST EXECUTION> ############################
        current_budget = 'test_execution'
        if not extracted_eligible_tests:
            eligible_tests = get_eligible_tests(fragment, processed_fragments, args)
            extracted_eligible_tests = True
        
            # if there are no tests ready to be executed, end the loop and mark the fragment as not-exercised
            if eligible_tests == []:
                update_labels(args=args, fragment=fragment, translation=generation, translation_status='attempted', syntactic_validation='parseable', field_exercise='pending', graal_validation=graal_status, mocking_validation=mocking_status, test_execution='not-exercised', elapsed_time=time.time() - start_time)
                break

            # if there are tests ready to be executed, translate them first
            else:
                for test in eligible_tests:

                    if is_test_parseable(test, args):
                        executable_eligible_tests.append(test)
                        continue

                    translate(test, args, processed_fragments, recursion_depth=args.recursion_depth)

                    if not is_test_parseable(test, args):
                        continue

                    processed_fragments.append(f'{test["schema_name"]}|{test["class_name"]}|{test["fragment_name"]}')
                    executable_eligible_tests.append(test)

                # if no tests are executable / syntactically correct, end the loop and mark the fragment as not-exercised
                if executable_eligible_tests == []:
                    update_labels(args=args, fragment=fragment, translation=generation, translation_status='attempted', syntactic_validation='parseable', field_exercise='pending', graal_validation=graal_status, mocking_validation=mocking_status, test_execution='not-exercised', elapsed_time=time.time() - start_time)
                    break

        # after eligible tests are translated, validate the main method fragment with test validation
        test_execution_details = test_validation(args, executable_eligible_tests)

        for test in test_execution_details:
            
            if test_execution_details[test]['test_outcome'] == 'exercised-success':
                for covered_method in test_execution_details[test]['covered_methods']:
                    covered_method_file = covered_method['schema_name']
                    covered_method_class = covered_method['class_name']
                    covered_method_name = covered_method['fragment_name']

                    update_labels(args=args, fragment={'schema_name': covered_method_file, 'class_name': covered_method_class, 'fragment_name': covered_method_name, 'fragment_type': 'method'}, translation=[], translation_status=[], syntactic_validation=[], field_exercise=[], graal_validation=[], mocking_validation=[], test_execution={test: test_execution_details[test]}, elapsed_time=0, update_test_execution=True)
                continue

            # heuristic 1: if no methods are covered and test fails, the problem is guaranteed to be in the test method. re-prompt the test method.
            # heuristic 2: if stacktrace shows an AttributeError in the test method, re-prompt the test method only
            if test_execution_details[test]['covered_methods'] == [] or test_has_attribute_error(test_execution_details[test]):

                if args.debug:
                    print('=======================TEST VALIDATION FAILED - REPROMPTING=======================', flush=True)

                test_fragment = get_test_fragment(test, executable_eligible_tests)
                if test_fragment == {}:
                    continue
                
                translate(test_fragment, args, processed_fragments, budget=feedback_budget if recursion_depth==2 else budget, feedback=test_execution_details[test]['feedback'], recursion_depth=recursion_depth-1)

                higher_order_tests = get_higher_order_tests(test_fragment, args, executable_eligible_tests)

                reprompted_test_execution_details = test_validation(args, [test_fragment] + higher_order_tests)

                if reprompted_test_execution_details[test]['test_outcome'] == 'exercised-success':
                    
                    for covered_method in reprompted_test_execution_details[test]['covered_methods']:
                        covered_method_file = covered_method['schema_name']
                        covered_method_class = covered_method['class_name']
                        covered_method_name = covered_method['fragment_name']

                        update_labels(args=args, fragment={'schema_name': covered_method_file, 'class_name': covered_method_class, 'fragment_name': covered_method_name, 'fragment_type': 'method'}, translation=[], translation_status='attempted', syntactic_validation='parseable', field_exercise='pending', graal_validation='pending', mocking_validation='pending', test_execution={test: reprompted_test_execution_details[test]}, elapsed_time=0, update_test_execution=True, fixed_by_simple_reprompt=True)

                    continue

            # use advanced agent for fixing the bug
            if args.fix_agent_advanced and test_execution_details[test]['test_outcome'] == 'exercised-failed':

                response = fix_by_advance_llm(args, test_execution_details[test])

                if response:
                    test_fragment = get_test_fragment(test, executable_eligible_tests)
                    if test_fragment == {}:
                        continue
                    
                    higher_order_tests = get_higher_order_tests(test_fragment, args, executable_eligible_tests)
                    
                    post_agent_test_execution_details = test_validation(args, [test_fragment] + higher_order_tests)

                    for covered_method in post_agent_test_execution_details[test]['covered_methods']:
                        covered_method_file = covered_method['schema_name']
                        covered_method_class = covered_method['class_name']
                        covered_method_name = covered_method['fragment_name']
                        
                        if post_agent_test_execution_details[test]['test_outcome'] == 'exercised-success':
                            update_labels(args=args, fragment={'schema_name': covered_method_file, 'class_name': covered_method_class, 'fragment_name': covered_method_name, 'fragment_type': 'method'}, translation=[], translation_status='attempted', syntactic_validation='parseable', field_exercise='pending', graal_validation='pending', mocking_validation='pending', test_execution={test: post_agent_test_execution_details[test]}, elapsed_time=0, update_test_execution=True, fixed_by_advanced_reprompt=True)
                        else:
                            update_labels(args=args, fragment={'schema_name': covered_method_file, 'class_name': covered_method_class, 'fragment_name': covered_method_name, 'fragment_type': 'method'}, translation=[], translation_status='attempted', syntactic_validation='parseable', field_exercise='pending', graal_validation='pending', mocking_validation='pending', test_execution={test: post_agent_test_execution_details[test]}, elapsed_time=0, update_test_execution=True)

                    continue

            for covered_method in test_execution_details[test]['covered_methods']:
                covered_method_file = covered_method['schema_name']
                covered_method_class = covered_method['class_name']
                covered_method_name = covered_method['fragment_name']

                update_labels(args=args, fragment={'schema_name': covered_method_file, 'class_name': covered_method_class, 'fragment_name': covered_method_name, 'fragment_type': 'method'}, translation=[], translation_status='attempted', syntactic_validation='parseable', field_exercise='pending', graal_validation='pending', mocking_validation='pending', test_execution={test: test_execution_details[test]}, elapsed_time=0, update_test_execution=True)

        ############################ </TEST EXECUTION> ############################

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
    processed_fragments, pending_fragments = get_pending_fragments(fragment_traversal, args)
    
    for fragment in tqdm.tqdm(pending_fragments):

        if fragment in processed_fragments:
            continue

        # if a fragment requires translation, translate it with LLM
        translate(fragment, args, processed_fragments, recursion_depth=args.recursion_depth)
        processed_fragments.append(f'{fragment["schema_name"]}|{fragment["class_name"]}|{fragment["fragment_name"]}')
        
        clean_up(args)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Translate fragments using LLM')
    parser.add_argument('--model_name', type=str, dest='model_name', help='model name to use for translation')
    parser.add_argument('--project_name', type=str, dest='project_name', help='project name to translate')
    parser.add_argument('--from_lang', type=str, dest='from_lang', help='language to translate from')
    parser.add_argument('--to_lang', type=str, dest='to_lang', help='language to translate to')
    parser.add_argument('--validate_by_graal', action='store_true', help='validate translation by GraalVM')
    parser.add_argument('--debug', action='store_true', help='debug mode')
    parser.add_argument('--validate_by_mocking', action='store_true', help='validate translation by mocking')
    parser.add_argument('--temperature', type=float, dest='temperature', help='temperature for generation')
    parser.add_argument('--suffix', type=str, dest='suffix', help='suffix for the translated files')
    parser.add_argument('--recursion_depth', type=int, dest='recursion_depth', help='depth of recursion for translation')
    parser.add_argument('--fix_agent_simple', action='store_true', help='fix simple agent for translation')
    parser.add_argument('--fix_agent_advanced', action='store_true', help='fix advanced agent for translation')
    args = parser.parse_args()
    main(args)
