import argparse
import json
import os
import re
import yaml
from datetime import datetime
from src.model.model import Model
from jinja2 import Template

from src.utils.get_custom_types import get_custom_types


class TypePromptGenerator:
    def __init__(self, context_code_snippet, fragment_type, source_type, source_type_description, type_variation, prompt_type, source_language, target_language, feedback):
        self.context_code_snippet = context_code_snippet
        self.fragment_type = fragment_type
        self.source_type = source_type if type_variation in ['FIELD TYPE', 'RETURN TYPE', 'METHOD BODY TYPE'] else source_type['type']
        self.source_type_description = source_type_description
        self.type_variation = type_variation
        self.prompt_type = prompt_type
        self.source_language = source_language
        self.target_language = target_language
        self.feedback = feedback
        self.prompt = ''

        self.prompt_template_config = yaml.safe_load(open('configs/prompt_templates.yaml', 'r'))

    def generate_prompt(self):
        self.prompt += self.add_instance_prompt()
        self.prompt += '\n\n'
        if self.feedback != '':
            self.prompt += self.add_feedback_prompt()
            self.prompt += '\n\n'
        self.prompt += self.add_response_format_prompt()
        return self.prompt

    def add_instance_prompt(self):
        template = Template(self.prompt_template_config['templates'][f'type_resolution_{self.prompt_type}_instance'])
        return template.render(**self.__dict__)

    def add_feedback_prompt(self):
        template = Template(self.prompt_template_config['templates'][f'type_resolution_{self.prompt_type}_feedback'])
        return template.render(**self.__dict__)

    def add_response_format_prompt(self):
        template = Template(self.prompt_template_config['templates'][f'type_resolution_{self.prompt_type}_response_format'])
        return template.render(**self.__dict__)


class Interaction:
    def __init__(self, role, content):
        self.role = role
        self.content = content


class Result:
    def __init__(self):
        self.identifier = ''
        self.translated = False
        self.attempted = False
        self.type_variation = ''
        self.timestamp = ''
        self.source_type = ''
        self.generation = ''
        self.imports = ''
        self.translated_target_type = ''
        self.reasoning = ''
        self.prompt = ''


class Parser:
    def extract_imports(self, text):
        pattern = re.search(r'PYTHON IMPORTS:\s*```(?:python)?\s*(.*?)\s*```', text, re.DOTALL)
        return pattern.group(1).strip() if pattern else None

    def extract_translation(self, text):
        pattern = re.search(r'PYTHON TRANSLATION:\s*```(?:python)?\s*(.*?)\s*```', text, re.DOTALL)
        return pattern.group(1).strip() if pattern else None

    def extract_reasoning(self, text):
        pattern = re.search(r'REASONING:\s*(.*?)(?=\n\n|$)', text, re.DOTALL)
        return pattern.group(1).strip() if pattern else None

    def parse_response(self, generation):
        imports = self.extract_imports(generation)
        translation = self.extract_translation(generation)
        reasoning = self.extract_reasoning(generation)
        return imports, translation, reasoning


def get_source_type_description(source_type):
    source_type = source_type.strip()
    if '[' in source_type:
        source_type = source_type.split('[')[0]
    if '<' in source_type:
        source_type = source_type.split('<')[0]
    type_documentation = {}
    with open('data/crawl/java.base_module_doc.json') as f:
        type_documentation = json.load(f)
    
    for module_name in type_documentation:
        for package_name in type_documentation[module_name]:
            for class_name in type_documentation[module_name][package_name]:
                if source_type in type_documentation[module_name][package_name][class_name]:
                    if 'description' in type_documentation[module_name][package_name][class_name][source_type]:
                        return type_documentation[module_name][package_name][class_name][source_type]['description']
                    return ''
 
    return ''
    

def append_result(data, class_, fragment_type, fragment, type_variation, type_, result):
    type_identifier = type_ if type_variation in ['types', 'return_types', 'body_types'] else f'{type_["modifier"]}|{type_["type"]}|{type_["name"]}'
    data['classes'][class_][f'{fragment_type}s'][fragment]['type_translations'][type_variation][type_identifier] = result.__dict__
    return data

def save_results(data, schema_dir, schema_file):
    with open(f'{schema_dir}/{schema_file}', 'w') as f:
        json.dump(data, f, indent=4)

def is_type_loadable(import_stmt, type_name, custom_classes=None):
    """
    Validates if a type can be loaded or used in the Python type system.
    
    Args:
        import_stmt (str): The import statement needed to access the type, or empty if built-in
        type_name (str): The name of the type to validate
        custom_classes (list, optional): List of custom class names to treat as valid types
        
    Returns:
        tuple: (bool, str) indicating if the type can be loaded and an error message if applicable
    """
    import builtins
    import typing
    import types
    from typing import _GenericAlias

    if import_stmt:
        try:
            exec(import_stmt, {})
        except BaseException as e:
            return False, f'Import Statement throws error: {str(e)}'

    if isinstance(type_name, str):
        if "#" in type_name:
            return False, 'invalid type name'
    
    type_name = type_name.strip() if type_name else ''
    import_stmt = import_stmt.strip() if import_stmt else ''
    custom_classes = custom_classes or []
    
    if import_stmt == '' and type_name == '':
        return False, 'no type translation has been provided'
        
    # Special case for None type
    if type_name == 'None':
        return True, ''
    
    exec_globals = {}
    
    try:
        # Execute the import statement if provided
        if import_stmt:
            exec(import_stmt, exec_globals)
        
        # Create a namespace with all relevant types for evaluation
        namespace = {
            **exec_globals, 
            **{k: getattr(builtins, k) for k in dir(builtins)}, 
            'typing': typing,
            'None': None
        }
        
        # Add only the explicitly provided custom classes to the namespace
        for custom_class in custom_classes:
            namespace[custom_class] = type(custom_class, (), {})
        
        # Try to evaluate the type directly
        try:
            eval_type = eval(type_name, namespace)
            if eval_type is None or isinstance(eval_type, (type, _GenericAlias, types.GenericAlias)):
                return True, ''
            return False, f'{type_name} is not a valid type'
        except Exception as e:
            return False, f'Error evaluating type: {str(e)}'
            
    except BaseException as e:  # catch things like pytest.skip
        return False, str(e)


def main(args):

    JAVA_TO_PYTHON_PRIMITIVES = {
        # Integers
        'int': 'int',
        'Integer': 'int',
        'java.lang.Integer': 'int',
        'long': 'int',
        'java.lang.Long': 'int',
        'Long': 'int',
        'short': 'int',
        'java.lang.Short': 'int',
        'Short': 'int',
        'byte': 'int',
        'Byte': 'int',
        'java.lang.Byte': 'int',

        # Floating point
        'float': 'float',
        'java.lang.Float': 'float',
        'Float': 'float',
        'double': 'float',
        'Double': 'float',
        'java.lang.Double': 'float',

        # Boolean
        'boolean': 'bool',
        'Boolean': 'bool',
        'java.lang.Boolean': 'bool',

        # Character / String
        'char': 'str',
        'java.lang.Character': 'str',
        'java.lang.String': 'str',
        'Character': 'str',
        'String': 'str',

        # Void
        'void': 'None',
        'Void': 'None',
        'java.lang.Void': 'None',
}


    model_info = yaml.safe_load(open('configs/model_configs.yaml', 'r'))['models']
    args.schema_dir = f'data/schemas{args.suffix}/{args.model_name}/{args.temperature}/{args.project_name}'
    model = Model(model_info=model_info[args.model_name])

    custom_types = get_custom_types(args.schema_dir)

    for schema_file in os.listdir(args.schema_dir):

        data = {}
        with open(f'{args.schema_dir}/{schema_file}', 'r') as f:
            data = json.load(f)

        for class_ in data['classes']:
            for fragment_type in ['field', 'method']:
                for fragment in data['classes'][class_][f'{fragment_type}s']:
                    fragment_body = '\n'.join(data['classes'][class_][f'{fragment_type}s'][fragment]['body'])
                    fragment_body = '    ' + fragment_body
                    type_variations = {'types': 'FIELD TYPE', 'return_types': 'RETURN TYPE', 'parameters': 'PARAMETER TYPE', 'body_types': 'METHOD BODY TYPE'}

                    for type_variation in type_variations:

                        if fragment_type == 'field' and type_variation != 'types':
                            continue
                        elif fragment_type == 'method' and type_variation == 'types':
                            continue

                        interaction_history = []
                        feedback = ''
                        budget = args.budget
                        i = 0
                        while i < len(data['classes'][class_][f'{fragment_type}s'][fragment][type_variation]):

                            type_ = data['classes'][class_][f'{fragment_type}s'][fragment][type_variation][i]
                            type_identifier = type_ if type_variation in ['types', 'return_types', 'body_types'] else f'{type_["modifier"]}|{type_["type"]}|{type_["name"]}'

                            # skip if type is already translated or attempted
                            if data['classes'][class_][f'{fragment_type}s'][fragment]['type_translations'][type_variation][type_identifier]['translated']:
                                i += 1
                                interaction_history = []
                                feedback = ''
                                budget = args.budget
                                continue

                            # skip if budget is 0
                            if budget == 0:
                                i += 1
                                interaction_history = []
                                feedback = ''
                                budget = args.budget
                                continue
                            
                            if interaction_history == []:
                                initial_interaction = Interaction(role='system', content='You are a helpful assistant.')
                                interaction_history.append(initial_interaction)

                            source_type = type_ if type_variation in ['types', 'return_types', 'body_types'] else type_["type"]

                            result = Result()
                            result.attempted = True
                            result.identifier = type_identifier
                            result.translated = False
                            result.type_variation = type_variation
                            result.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            result.source_type = source_type

                            if source_type in custom_types or source_type in JAVA_TO_PYTHON_PRIMITIVES:
                                result.translated = True
                                if source_type in JAVA_TO_PYTHON_PRIMITIVES:
                                    result.translated_target_type = JAVA_TO_PYTHON_PRIMITIVES.get(source_type)
                                else:
                                    result.translated_target_type = source_type
                                append_result(data, class_, fragment_type, fragment, type_variation, type_, result)
                                i += 1
                                interaction_history = []
                                feedback = ''
                                budget = args.budget

                                save_results(data, args.schema_dir, schema_file)

                                if args.debug:
                                    if source_type in JAVA_TO_PYTHON_PRIMITIVES:
                                        message = 'PRIMITIVE TYPE DETECTED'
                                    else:
                                        message = 'CUSTOM TYPE DETECTED'
                                    print('=' * 50 + message + '=' * 50, flush=True)
                                    print(source_type, flush=True)

                                continue

                            source_type_description = get_source_type_description(source_type)

                            prompt_generator = TypePromptGenerator(
                                fragment_body, 
                                fragment_type, 
                                type_, 
                                source_type_description,
                                type_variations[type_variation],
                                args.prompt_type, 
                                args.source_language, 
                                args.target_language,
                                feedback
                            )
                            prompt = prompt_generator.generate_prompt()

                            interaction = Interaction(role='user', content=prompt)
                            interaction_history.append(interaction)

                            if args.debug:
                                print('=' * 50 + 'PROMPT' + '=' * 50, flush=True)
                                print(prompt, flush=True)

                            messages = model.get_messages(interaction_history)
                            status, generation = model.prompt_model(messages)

                            result.generation = generation
                            result.prompt = prompt
                            append_result(data, class_, fragment_type, fragment, type_variation, type_, result)
                            save_results(data, args.schema_dir, schema_file)

                            if not status:
                                i += 1
                                interaction_history = []
                                feedback = ''
                                budget = args.budget
                                continue

                            interaction = Interaction(role='system', content=generation)
                            interaction_history.append(interaction)

                            if args.debug:
                                print('=' * 50 + 'GENERATION' + '=' * 50, flush=True)
                                print(generation, flush=True)

                            try:
                                imports, translation, reasoning = Parser().parse_response(generation)
                            except BaseException:
                                feedback = 'Your response did not follow the RESPONSE FORMAT guidelines. Make sure you follow the RESPONSE FORMAT in your new response.'
                                budget -= 1
                                continue

                            # model did not follow the response format
                            if imports is None and translation is None and reasoning is None:
                                feedback = 'Your response did not follow the RESPONSE FORMAT guidelines. Make sure you follow the RESPONSE FORMAT in your new response.'
                                budget -= 1
                                continue

                            if isinstance(translation, str):
                                if "#" in translation:
                                    translation = translation.split('#', 1)[0].strip()

                            # type does not pass validation checks
                            validation_result, feedback = is_type_loadable(imports, translation, custom_types)
                            if not validation_result:
                                budget -= 1
                                continue

                            # type validation passes
                            result.translated = True
                            result.imports = imports
                            result.translated_target_type = translation
                            result.reasoning = reasoning

                            if args.debug:
                                print('=' * 50 + 'IMPORTS' + '=' * 50, flush=True)
                                print(imports, flush=True)
                                print('=' * 50 + 'TRANSLATION' + '=' * 50, flush=True)
                                print(translation, flush=True)
                                print('=' * 50 + 'REASONING' + '=' * 50, flush=True)
                                print(reasoning, flush=True)
                            
                            append_result(data, class_, fragment_type, fragment, type_variation, type_, result)
                            i += 1
                            interaction_history = []
                            feedback = ''
                            budget = args.budget

                            save_results(data, args.schema_dir, schema_file)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Translate java types to python types')
    parser.add_argument('--project_name', type=str, dest='project_name', help='project name')
    parser.add_argument('--model_name', type=str, dest='model_name', help='model name to use for translation')
    parser.add_argument('--temperature', type=float, dest='temperature', help='temperature for generation')
    parser.add_argument('--suffix', type=str, dest='suffix', help='suffix for schema files')
    parser.add_argument('--debug', action='store_true', dest='debug', help='debug mode')
    parser.add_argument('--prompt_type', type=str, dest='prompt_type', help='prompt type')
    parser.add_argument('--source_language', type=str, dest='source_language', help='source language')
    parser.add_argument('--target_language', type=str, dest='target_language', help='target language')
    parser.add_argument('--budget', type=int, dest='budget', help='budget for each type translation')
    args = parser.parse_args()
    main(args)
