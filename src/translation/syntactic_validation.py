import re
import ast
import json
from typing import Optional


class MethodExtractor:
    """Extracts a Python method that matches a given signature."""
    
    def __init__(self, source_code: str):
        """
        Initialize with source code to analyze.
        
        Args:
            source_code (str): Python source code containing the method
        """
        self.source_code = source_code
        self.tree = ast.parse(source_code)
    
    def parse_signature(self, signature: str) -> tuple:
        """
        Parse a method signature string into its components.
        
        Args:
            signature (str): Method signature like "def method(arg: type) -> return_type:"
            
        Returns:
            tuple: (method_name, args_string, return_type)
        """
        # Remove 'def' and any whitespace
        signature = signature.strip()
        if signature.startswith('def '):
            signature = signature[4:].strip()
            
        # Extract method name and arguments
        match = re.match(r'(\w+)\s*\((.*?)\)\s*(?:->\s*([^:]+)\s*)?:', signature)
        if not match:
            raise ValueError("Invalid method signature format")
            
        method_name = match.group(1)
        args_string = match.group(2).strip()
        return_type = match.group(3).strip() if match.group(3) else None
        
        return method_name, args_string, return_type
    
    def extract_method(self, signature: str) -> Optional[str]:
        """
        Extract a method matching the given signature.
        
        Args:
            signature (str): The complete method signature to match
            
        Returns:
            Optional[str]: The extracted method or None if not found
        """
        try:
            method_name, args_string, return_type = self.parse_signature(signature)
        except ValueError as e:
            print(f"Error parsing signature: {e}")
            return None
            
        class MethodVisitor(ast.NodeVisitor):
            def __init__(self, target_name: str, source_code: str):
                self.target_name = target_name
                self.found_method = None
                self.source_lines = source_code.splitlines()
            
            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                if node.name == self.target_name:
                    # Extract the method's source code
                    start_line = node.lineno - 1
                    end_line = node.end_lineno
                    method_lines = self.source_lines[start_line:end_line]
                    self.found_method = '\n'.join(method_lines)
        
        visitor = MethodVisitor(method_name, self.source_code)
        visitor.visit(self.tree)
        return visitor.found_method
    

def normalize_indentation(s, expected_indent) -> str:
    lines = s.strip('\n').split('\n')
    if not lines:
        return s

    first_line = lines[0]
    leading_spaces = len(first_line) - len(first_line.lstrip(' '))

    if leading_spaces == 8:
        return s  # no change needed

    shift = expected_indent - leading_spaces

    adjusted_lines = []
    for line in lines:
        if shift > 0:
            adjusted_lines.append(' ' * shift + line)
        elif shift < 0:
            remove = min(-shift, len(line) - len(line.lstrip(' ')))
            adjusted_lines.append(line[remove:])
        else:
            adjusted_lines.append(line)

    return '\n'.join(adjusted_lines)



def syntactic_validation(generation, fragment, args, signature):
    if generation.count('```') == 1:
        generation = '```\n' + generation
    unparsed_generation = generation
    
    exception_map = json.load(open('data/type_resolution/exception_map.json'))
    constant_map = json.load(open('data/type_resolution/constant_map.json'))

    generation = generation.replace('```python', '```')
    pattern = r'```(.*?)```'
    match = re.findall(pattern, generation, re.DOTALL)

    if len(match) != 1:
        return False, None, unparsed_generation, 'the model response did not follow the proper RESPONSE FORMAT. Make sure you only have one code block in the response.'
    
    match = match[0]

    try:
        output = match
        original_output = output

        has_annotation = False
        if (signature is not None and '@staticmethod' in signature) or ('def run_static_init()') in output:
            has_annotation = True
            signature = signature.replace('@staticmethod', '')
            original_output = output.replace('@staticmethod', '')

        if signature is not None:

            if original_output.strip().startswith('def '):
                original_output = '    ' + original_output.strip()
                output = f'class dummy:\n{original_output}'
            try:
                method_extractor = MethodExtractor(output)
                extracted_method = method_extractor.extract_method(signature)
            except BaseException:
                extracted_method = None
                output = original_output
            if extracted_method is not None:
                output = extracted_method
            else:
                signature_cleaned = '    ' + signature.strip()
                signature_cleaned = signature_cleaned.rsplit('\n', 1)[0] if '\n' in signature_cleaned else signature_cleaned
                if match.strip().startswith('def '):
                    body = output.split('\n', 1)[1] if len(output.split('\n', 1)) > 1 else 'pass'
                    method_cleaned = signature_cleaned + '\n' + normalize_indentation(body, 8)
                else:
                    method_cleaned = signature_cleaned + '\n' + normalize_indentation(match, 8)
                output = f'class dummy:\n{method_cleaned}'
                unparsed_generation = '```\n' + method_cleaned + '\n```'
                cleaned_method_extractor = MethodExtractor(output)
                extracted_method = cleaned_method_extractor.extract_method(signature)
                if extracted_method is None:
                    return False, None, unparsed_generation, 'the model response is not syntactically correct.'
                output = extracted_method
                    

        if fragment['fragment_type'] == 'field': # remove import lines from generation
            generation_lines = output.strip().split('\n')
            current_index = 0
            if len(generation_lines) == 0:
                return False, None, unparsed_generation, 'the model response did not contain the expected field assignment. Make sure the field translation includes the whole assignment statement.'
            while generation_lines[current_index].strip().startswith('import ') or \
                generation_lines[current_index].strip().startswith('from ') or \
                generation_lines[current_index].strip().startswith('class '):
                
                current_index += 1
                if current_index >= len(generation_lines):
                    return False, None, unparsed_generation, 'the model response did not contain the expected field assignment. Make sure the field translation includes the whole assignment statement.'
            
            generation_lines = generation_lines[current_index:]
            output = '\n'.join(generation_lines)

            if '=' not in output:
                return False, None, unparsed_generation, 'the model response did not contain the expected field assignment. Make sure the field translation includes the whole assignment statement.'

        if not output.startswith('    '):
            output = '    ' + output.strip()
        
        if has_annotation:
            output = '    @staticmethod\n' + output

        ast.parse('class dummy:\n' + output)

        if args.debug:
            print(f'=======================PARSED=======================\n{output}\n' + '---' * 50, flush=True)

        # for key in exception_map:
        #     if key in output:
        #         output = output.replace(key, exception_map[key])
        
        # for key in constant_map:
        #     if key in output:
        #         output = output.replace(key, constant_map[key])
        
        # if fragment['fragment_type'] != 'field':
        #     out_lines = output.split('\n')
        #     out_lines = [line for line in out_lines if line.strip() != '']
        #     new_out_lines = []
        #     if not out_lines[0].startswith('    def'):
        #         for i in range(len(out_lines)):
        #             if i == 0:
        #                 new_out_lines.append(f'    {out_lines[i].strip()}')
        #             else:
        #                 new_out_lines.append(f'        {out_lines[i].strip()}')
            
        #     output = '\n'.join(new_out_lines)
        
        if '```python' in output:
            output = output.replace('```python', '')
            output = output.replace('```', '')

        return True, output.split('\n'), unparsed_generation, None

    except (SyntaxError, MemoryError) as e:
        if args.debug:
            print(f'=======================PARSE ERROR=======================\n{e}\n' + '---' * 50, flush=True)
        feedback = e.msg if hasattr(e, 'msg') else str(e)
        return False, None, unparsed_generation, feedback
