import json
import os
import yaml
from jinja2 import Template
from src.utils.get_dependencies import get_dependencies
from src.decomposition.create_schema import get_language_parser

java_language_parser = get_language_parser('java')


class PromptGenerator:
        
    def __init__(self, is_feedback, args, fragment_details, feedback='', use_icl_pool=False):
        self.is_feedback = is_feedback
        self.args = args
        self.prompt = ''
        self.feedback = feedback
        self.requires_translation = True
        self.use_icl_pool = use_icl_pool
        self.fragment_details = fragment_details
        self.signature = None
        self.is_enum_constant = False

        self.assert_map = json.load(open('data/type_resolution/assert_map.json', 'r'))
        self.prompt_template_config = yaml.safe_load(open('configs/prompt_templates.yaml', 'r'))
        
        self.load_fragment(fragment_details)
        if self.fragment_details['fragment_type'] == 'method':
            self.check_requires_translation()
        self.construct_adaptive_icl()
        self.build_base_prompt()
    
    def build_base_prompt(self):

        # add in-context learning example
        self.prompt += self.adaptive_icl

        self.double_line_break()

        # add instruction
        self.add_instruction()

        self.double_line_break()

        # add source code
        self.add_source_code()

        self.double_line_break()

        if self.is_feedback:
            self.add_incorrect_translation()
            self.double_line_break()
            self.add_feedback()
            self.double_line_break()

        # add partial translation
        self.add_partial_translation()

        self.double_line_break()

        self.add_type_translation_details()

        self.double_line_break()

        if self.fragment_type == 'method':
            self.add_api_description()
            self.double_line_break()

        self.add_response_format()

        self.double_line_break()

        self.add_notes()

        self.double_line_break()

        # add target translation
        self.add_target_translation()

    def construct_adaptive_icl(self):
        used_assertions = []
        for source_assert in self.assert_map:
            if source_assert in self.source_fragment_body:
                used_assertions.append(source_assert)

        source_statements = ''
        target_statements = ''
        for source_assert in self.assert_map:
            if source_assert not in used_assertions:
                continue
            for i in range(2):
                source_statements += self.assert_map[source_assert][i]['java'] + ';\n        '
                target_statements += 'self.' + self.assert_map[source_assert][i]['python'] + '\n        '

        if self.is_feedback:
            test_icl = self.prompt_template_config['templates']['fragment_translation_feedback_test_static_icl']
        else:
            template = Template(self.prompt_template_config['templates'][f'fragment_translation_test_static_icl'])
            test_icl = template.render({'source_statements': source_statements, 'target_statements': target_statements})
            test_icl = test_icl.replace('self.pytest.', 'pytest.')
        
        fragment_type = 'field'
        if self.fragment_type in ['method', 'static_initializer']:
            fragment_type = 'method'

        if self.is_feedback:
            if used_assertions:
                self.adaptive_icl = test_icl
            else:
                self.adaptive_icl = self.prompt_template_config['templates']['fragment_translation_feedback_static_icl']
        else:
            if used_assertions:
                self.adaptive_icl = test_icl
            else:
                self.adaptive_icl = self.prompt_template_config['templates'][f'fragment_translation_{fragment_type}_static_icl']

    def load_fragment(self, fragment_details):
        self.schema_name = fragment_details['schema_name']
        self.class_name = fragment_details['class_name']
        self.fragment_name = fragment_details['fragment_name']
        self.fragment_actual_name = self.fragment_name.split(':')[1]
        self.fragment_type = fragment_details['fragment_type']
        self.is_test_method = fragment_details['is_test_method']

        self.schema_data = {}
        with open(f'{self.args.schemas_dir}/{self.schema_name}.json', 'r') as f:
            self.schema_data = json.load(f)
        
        self.fragment_dict = self.schema_data['classes'][self.class_name][f'{self.fragment_type}s'][self.fragment_name]

        self.source_fragment_body = '    ' + '\n'.join(self.fragment_dict['body'])

        # add source class fields for reference
        self.source_class_dependent_fields = ''
        for field in self.schema_data['classes'][self.class_name]['fields']:
            if self.schema_data['classes'][self.class_name]['fields'][field]['enum_constant']:
                self.is_enum_constant = True
            if field == self.fragment_name:
                continue
            if field.split(':')[1] in self.source_fragment_body:
                self.source_class_dependent_fields += '    ' + '\n'.join(self.schema_data['classes'][self.class_name]['fields'][field]['body'])
                self.source_class_dependent_fields += '\n'

        class_name = self.class_name.split(':')[1]
        self.source_fragment_code = f'class {class_name} {{\n{self.source_class_dependent_fields}\n{self.source_fragment_body}\n}}'

    def check_requires_translation(self):
        content = self.source_fragment_body

        tree = java_language_parser.parse(bytes(content, "utf8"))

        has_body = [True]

        def traverse_tree(node):
            if node.type in ['method_declaration', 'constructor_declaration']:  # Check method or constructor

                body_node = node.child_by_field_name('body')  # Retrieve method body
                
                if body_node:
                    # Check if the body is empty (only contains `{}`)
                    non_brace_children = [child for child in body_node.children if child.type not in ['{', '}']]
                    
                    if non_brace_children:
                        has_body[0] = True
                    else:
                        has_body[0] = False
                else:
                    has_body[0] = False

            for child in node.children:
                traverse_tree(child)

        traverse_tree(tree.root_node)

        if not has_body[0]:
            self.requires_translation = False

    def add_instruction(self):
        if self.is_feedback:
            template = Template(self.prompt_template_config['templates']['fragment_translation_feedback_instruction'])
            self.prompt += template.render({'fragment_type': self.fragment_type, 'fragment_actual_name': self.fragment_actual_name})
        else:
            template = Template(self.prompt_template_config['templates']['fragment_translation_instruction'])
            self.prompt += template.render({'fragment_type': self.fragment_type, 'fragment_actual_name': self.fragment_actual_name})

    def add_source_code(self):
        self.prompt += f'{self.args.from_lang.upper()} CODE:\n```\n{self.source_fragment_code}\n```'

    def add_incorrect_translation(self):
        translation = '\n'.join(self.schema_data['classes'][self.class_name][f'{self.fragment_type}s'][self.fragment_name]['translation'])
        self.prompt += f'INCORRECT {self.args.to_lang.upper()} TRANSLATION:\n```\n{translation}\n```'

    def add_feedback(self):
        self.prompt += 'EXECUTION FEEDBACK:\n```\n'
        self.prompt += self.feedback if len(self.feedback) < 10000 else self.feedback[-10000:]
        self.prompt += '\n```'

    def add_partial_translation(self):
        self.build_partial_translation()
        template = Template(self.prompt_template_config['templates']['fragment_translation_partial_translation'])
        self.prompt += template.render({'partial_translation': self.partial_translation})

    def build_partial_translation(self):
        self.partial_translation = '\n'.join(self.schema_data['python_imports'])
        self.partial_translation += '\n\n'

        # add inner and outer classes
        inner_outer_classes = self.schema_data['classes'][self.class_name]['nests'] + [self.schema_data['classes'][self.class_name]['nested_inside']]
        for inner_outer_class in inner_outer_classes:
            if inner_outer_class == '':
                continue
            
            inner_outer_classes_py = [f"{self.schema_data['classes'][inner_outer_class]['python_class_declaration']}"]
            for field in self.schema_data['classes'][inner_outer_class]['fields']:
                if field.split(':')[1] in ''.join(self.schema_data['classes'][self.class_name][f'{self.fragment_type}s'][self.fragment_name]['body']):
                    field_translation = self.schema_data['classes'][inner_outer_class]['fields'][field]['translation']
                    inner_outer_classes_py.append('\n'.join(field_translation) if field_translation else ''.join(self.schema_data['classes'][inner_outer_class]['fields'][field]['partial_translation']) + 'None')
                    inner_outer_classes_py.append('\n')
            
            if len(inner_outer_classes_py) > 1:
                self.partial_translation += '\n'.join(inner_outer_classes_py) + '\n\n'

        # add necessary dependencies from imported classes
        dependencies = get_dependencies(self.args)

        imported_classes = []
        partial_class_path = self.schema_name.replace(self.args.project_name + '.', '', 1).replace('src.main.', '').replace('src.test.', '')
        if partial_class_path in dependencies:
            imported_classes = dependencies[partial_class_path]

        for (dependenct_class_name, dependent_class_path) in imported_classes:
            
            has_exceptional_import = False
            for exceptional_import in ['commons.io', 'commons.logging', 'opentest4j', 'com.google', 'org.evosuite', 'scaffolding']:
                if exceptional_import in dependent_class_path:
                    has_exceptional_import = True
                    break
            
            if has_exceptional_import:
                continue

            imported_class_path = self.get_dependency_path(dependent_class_path)
            
            imported_class_data = {}
            with open(f'{self.args.schemas_dir}/{self.args.project_name}.{imported_class_path}.json', 'r') as f:
                imported_class_data = json.load(f)
            
            for key in imported_class_data['classes']:
                if key.split(':')[1] == dependenct_class_name:
                    dependenct_class_key = key
                    break

            imported_classes_list = [f'{imported_class_data["classes"][dependenct_class_key]["python_class_declaration"]}'.strip()]

            for field in imported_class_data['classes'][dependenct_class_key]['fields']:
                if field.split(':')[1] in ''.join(self.schema_data['classes'][self.class_name][f'{self.fragment_type}s'][self.fragment_name]['body']):
                    field_translation = imported_class_data['classes'][dependenct_class_key]['fields'][field]['translation']
                    imported_classes_list += ['\n'.join(field_translation)] if field_translation else [''.join(imported_class_data['classes'][dependenct_class_key]['fields'][field]['partial_translation']) + 'None']
            
            if len(imported_classes_list) > 1:
                self.partial_translation += '\n'.join(imported_classes_list) + '\n\n\n'

        # include fields of superclass
        for super_class in self.schema_data['classes'][self.class_name]['extends']:            
            super_class_schema = ''
            for schema_file in os.listdir(self.args.schemas_dir):
                if f'.{super_class}.json' in schema_file:
                    super_class_schema = schema_file
                    break
            
            if super_class_schema == '':
                continue

            super_class_data = {}
            with open(f'{self.args.schemas_dir}/{super_class_schema}', 'r') as f:
                super_class_data = json.load(f)

            if f'class {super_class}:' in self.partial_translation or f'class {super_class}(' in self.partial_translation:
                continue

            super_class_key = ''
            for key in super_class_data['classes']:
                if key.split(':')[1] == super_class:
                    super_class_key = key
                    break

            super_class_declaration = [super_class_data['classes'][super_class_key]['python_class_declaration']]
            for field in super_class_data['classes'][super_class_key]['fields']:
                if field.split(':')[1] in ''.join(self.schema_data['classes'][self.class_name][f'{self.fragment_type}s'][self.fragment_name]['body']):
                    field_translation = super_class_data['classes'][super_class_key]['fields'][field]['translation']
                    super_class_declaration.append('\n'.join(field_translation) if field_translation else ''.join(super_class_data['classes'][super_class_key]['fields'][field]['partial_translation']) + 'None')
                    super_class_declaration.append('\n')
            
            if len(super_class_declaration) > 1:
                self.partial_translation += '\n'.join(super_class_declaration) + '\n\n'

        # add the fragment partial translation
        main_class_partial_translation = self.schema_data['classes'][self.class_name]['python_class_declaration']
        
        # add related fields of the main class 
        for field in self.schema_data['classes'][self.class_name]['fields']:
            if field.split(':')[1] == self.fragment_actual_name and self.fragment_type == 'field':
                continue
            if field.split(':')[1] in ''.join(''.join(self.schema_data['classes'][self.class_name][f'{self.fragment_type}s'][self.fragment_name]['body'])):
                field_translation = self.schema_data['classes'][self.class_name]['fields'][field]['translation']
                main_class_partial_translation += '\n'.join(field_translation) if field_translation else ''.join(self.schema_data['classes'][self.class_name]['fields'][field]['partial_translation']) + 'None'
                main_class_partial_translation += '\n\n'

        # add related methods of the main class
        if self.fragment_type == 'method':

            if len(self.schema_data['classes'][self.class_name]['methods'][self.fragment_name]['calls']) != 0:

                out_of_file_dependencies = []
                out_of_class_dependencies = []
                for callee_schema, callee_class, callee_method in self.schema_data['classes'][self.class_name]['methods'][self.fragment_name]['calls']:

                    if callee_schema == 'library':
                        continue

                    callee_schema_data = {}
                    with open(f'{self.args.schemas_dir}/{callee_schema}.json', 'r') as f:
                        callee_schema_data = json.load(f)
                    
                    if ':' not in callee_method:
                        continue

                    if callee_schema != self.schema_name.replace('.json', ''):
                        out_of_file_dependencies.append((callee_schema, callee_class, callee_method))
                        continue

                    if callee_class != self.class_name:
                        out_of_class_dependencies.append((callee_schema, callee_class, callee_method))
                        continue

                    method_translation = callee_schema_data['classes'][callee_class]['methods'][callee_method]['translation']
                    callee_partial_translation = '\n'.join(method_translation).rstrip() if method_translation else ''.join(callee_schema_data['classes'][callee_class]['methods'][callee_method]['partial_translation']).rstrip()

                    main_class_partial_translation += f"{callee_partial_translation}\n\n"

                main_class_partial_translation += ''.join(self.schema_data['classes'][self.class_name]['methods'][self.fragment_name]['partial_translation']).rstrip()

                if len(out_of_file_dependencies) != 0:
                    ordered_out_of_file_dependencies = {}
                    for callee_schema, callee_class, callee_method in out_of_file_dependencies:
                        ordered_out_of_file_dependencies.setdefault(callee_schema, [])
                        ordered_out_of_file_dependencies[callee_schema].append((callee_class, callee_method))

                    for callee_schema in ordered_out_of_file_dependencies:
                        for callee_class, callee_method in ordered_out_of_file_dependencies[callee_schema]:

                            callee_schema_data = {}
                            with open(f'{self.args.schemas_dir}/{callee_schema}.json', 'r') as f:
                                callee_schema_data = json.load(f)
                            
                            if callee_schema_data['classes'][callee_class]['python_class_declaration'] not in self.partial_translation:
                                self.partial_translation += f"{callee_schema_data['classes'][callee_class]['python_class_declaration']}"
                                for field in callee_schema_data['classes'][callee_class]['fields']:
                                    field_translation = callee_schema_data['classes'][callee_class]['fields'][field]['translation']
                                    self.partial_translation += '\n'.join(field_translation) if field_translation else ''.join(callee_schema_data['classes'][callee_class]['fields'][field]['partial_translation']) + 'None'
                                    self.partial_translation += '\n'
                            
                            self.partial_translation += '\n'

                            callee_method_translation = callee_schema_data['classes'][callee_class]['methods'][callee_method]['translation']
                            if not callee_schema_data['classes'][callee_class]['methods'][callee_method]['is_overload']:
                                self.partial_translation += '\n'.join(callee_method_translation).rstrip() if callee_method_translation else ''.join(callee_schema_data['classes'][callee_class]['methods'][callee_method]['partial_translation']).rstrip()
                            
                            self.partial_translation += '\n\n'

                if len(out_of_class_dependencies) != 0:
                    ordered_out_of_file_dependencies = {}
                    for callee_schema, callee_class, callee_method in out_of_class_dependencies:
                        ordered_out_of_file_dependencies.setdefault(callee_schema, [])
                        ordered_out_of_file_dependencies[callee_schema].append((callee_class, callee_method))

                    for callee_schema in ordered_out_of_file_dependencies:
                        for callee_class, callee_method in ordered_out_of_file_dependencies[callee_schema]:
                            callee_schema_data = {}
                            with open(f'{self.args.schemas_dir}/{callee_schema}.json', 'r') as f:
                                callee_schema_data = json.load(f)
                            
                            self.partial_translation += f"{callee_schema_data['classes'][callee_class]['python_class_declaration']}"
                            for field in callee_schema_data['classes'][callee_class]['fields']:
                                field_translation = callee_schema_data['classes'][callee_class]['fields'][field]['translation']
                                self.partial_translation += '\n'.join(field_translation) + '\n' if field_translation else ''.join(callee_schema_data['classes'][callee_class]['fields'][field]['partial_translation']) + 'None'
                                self.partial_translation += '\n'
                            
                            callee_method_translation = callee_schema_data['classes'][callee_class]['methods'][callee_method]['translation']
                            self.partial_translation += '\n'.join(callee_method_translation) if callee_method_translation else ''.join(callee_schema_data['classes'][callee_class]['methods'][callee_method]['partial_translation'])
                            
                            self.partial_translation += '\n\n'
                        
                main_class_partial_translation += '\n'
                
            else:
                main_class_partial_translation += ''.join(self.schema_data['classes'][self.class_name]['methods'][self.fragment_name]['partial_translation']).rstrip()
                main_class_partial_translation += '\n'
            
        else:
            for method in self.schema_data['classes'][self.class_name]['methods']:

                if self.schema_data['classes'][self.class_name]['methods'][method]['is_overload']:
                    continue

                if method.split(':')[1] in ''.join(''.join(self.schema_data['classes'][self.class_name][f'{self.fragment_type}s'][self.fragment_name]['body'])):

                    method_translation = self.schema_data['classes'][self.class_name]['methods'][method]['translation']

                    main_class_partial_translation += '\n'.join(method_translation) if method_translation else ''.join(self.schema_data['classes'][self.class_name]['methods'][method]['partial_translation'])
                    main_class_partial_translation += '\n\n'
        
        if self.fragment_type == 'field':
            main_class_partial_translation += ''.join(self.fragment_dict['partial_translation']) + '\n'
        elif self.fragment_type == 'static_initializer':
            main_class_partial_translation += '    @staticmethod\n    def run_static_init():\n        pass'
        
        self.partial_translation += main_class_partial_translation
    
    def add_type_translation_details(self):
        added_types = []
        template = Template(self.prompt_template_config['templates']['type_translation_details'])
        type_translation_details = ''

        for type_variation in self.schema_data['classes'][self.class_name][f'{self.fragment_type}s'][self.fragment_name]['type_translations']:
            for type_ in self.schema_data['classes'][self.class_name][f'{self.fragment_type}s'][self.fragment_name]['type_translations'][type_variation]:
                source_type = self.schema_data['classes'][self.class_name][f'{self.fragment_type}s'][self.fragment_name]['type_translations'][type_variation][type_]['source_type']

                if source_type in added_types:
                    continue

                target_type = self.schema_data['classes'][self.class_name][f'{self.fragment_type}s'][self.fragment_name]['type_translations'][type_variation][type_]['translated_target_type']
                reasoning = self.schema_data['classes'][self.class_name][f'{self.fragment_type}s'][self.fragment_name]['type_translations'][type_variation][type_]['reasoning']
                type_translation_details += f'JAVA TYPE: {source_type}\n'
                type_translation_details += f'TRANSLATED PYTHON TYPE: {target_type}\n'
                type_translation_details += f'REASONING: {reasoning}\n'
                type_translation_details += '\n'
                added_types.append(source_type)
        
        if type_translation_details:
            self.prompt += template.render({'type_translation_details': type_translation_details.strip()})
    
    def add_response_format(self):
        self.target_translation_headings = {
            'field': 'PYTHON FIELD TRANSLATION',
            'method': 'PYTHON METHOD TRANSLATION',
            'static_initializer': 'PYTHON METHOD TRANSLATION'
        }

        template = Template(self.prompt_template_config['templates']['fragment_translation_response_format'])
        self.prompt += template.render({
            'fragment_type': self.fragment_type, 
            'target_translation_heading': self.target_translation_headings[self.fragment_type],
            'target_language': self.args.to_lang
        })
    
    def add_notes(self):
        template = Template(self.prompt_template_config['templates']['fragment_translation_notes'])
        self.prompt += template.render({'fragment_type': self.fragment_type})

    def add_target_translation(self):

        template = Template(self.prompt_template_config['templates']['target_translation'])

        partial_target_translation = '    @staticmethod\n    def run_static_init():\n        '
        if self.fragment_type == 'field':
            partial_target_translation = ''.join(self.schema_data['classes'][self.class_name]['fields'][self.fragment_name]['partial_translation']).rstrip()
        
        elif self.fragment_type == 'method':
            partial_target_translation = ''.join(self.schema_data['classes'][self.class_name]['methods'][self.fragment_name]['partial_translation']).rstrip().replace('    pass', '    ')
            self.signature = ''.join(self.schema_data['classes'][self.class_name]['methods'][self.fragment_name]['partial_translation']).strip()
        
        elif self.fragment_type == 'static_initializer':
            self.signature = 'def run_static_init():'

        self.prompt += template.render({'target_translation_heading': self.target_translation_headings[self.fragment_type], 'partial_target_translation': partial_target_translation})

    def get_api_description(self, api_signature, class_name):
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
    
    def add_api_description(self):
        library_api_calls = []
        for call in self.schema_data['classes'][self.class_name][f'{self.fragment_type}s'][self.fragment_name]['calls']:
            if call[0] == 'library':
                library_api_calls.append(call)
        
        if not library_api_calls:
            return
        
        api_call_description = ''
        for call in library_api_calls:
            class_ = call[1]
            signature = call[2]
            api_description = self.get_api_description(signature, class_)
            if not api_description:
                continue
            api_call_description += f'API CALL SIGNATURE: {api_description["signature"]}\n'
            api_call_description += f'DESCRIPTION: {api_description["description"]}\n\n'
        
        template = Template(self.prompt_template_config['templates']['api_call_description'])
        self.prompt += template.render({'api_call_description': api_call_description.rstrip()})

    def get_dependency_path(self, dependent_class):
        if os.path.exists(f'{self.args.schemas_dir}/{self.args.project_name}.src.main.{dependent_class}.json'):
            return f'src.main.{dependent_class}'
        elif os.path.exists(f'{self.args.schemas_dir}/{self.args.project_name}.src.test.{dependent_class}.json'):
            return f'src.test.{dependent_class}'
        else:
            raise Exception(f'Could not find dependency path for {dependent_class}')

    def single_line_break(self):
        self.prompt += '\n'
    
    def double_line_break(self):
        self.prompt += '\n\n'

    def generate_prompt(self):
        self.prompt = self.prompt.replace('\u0000', '')
        return self.prompt
