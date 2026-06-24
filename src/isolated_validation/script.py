import os
import sys
import json
from log_parser import parse_logs
from mock_helper import clear_reference_dict

def process_test_log(log_path, parse_logs):
    """
    Process a test log, mock methods, and save decomposed test files.

    Args:
        log_path (str): Path to the test log file.
        parse_logs (callable): Function to parse logs into a list of dictionaries.
    """
    test_name = log_path.split('.')[-2]
    all_mock_workflows = parse_logs(log_path)

    test_path = log_path.replace('.', os.sep).rsplit(os.sep, 1)[0].rsplit(os.sep, 1)[0]
    os.makedirs(f'src{os.sep}test{os.sep}{os.sep.join(test_path.split(os.sep)[:-1])}', exist_ok=True)

    for i, mock_workflow in enumerate(all_mock_workflows):
        focal_method = None
        for method_mock in mock_workflow:
            if "note" in method_mock and method_mock.get("note", "") == "skip":
                focal_method = method_mock.get("method_name", "")

        # Create mocked version of the tests
        focal_method = '_'.join(focal_method.split(".")[-2:])
        mock_test_path = f"src{os.sep}test{os.sep}{test_path}_{test_name}_decomposed_mocker_{i}_{focal_method}.py"

        with open(mock_test_path, 'w') as mock_test_file:
            mock_test_file.write(
                "from unittest.mock import patch, MagicMock\n"
                "from mock_helper import update_static_fields, set_object_instance_fields, convert_to_python, recursive_equal, side_effect_is_correct, clear_reference_dict\n"
                "import unittest, importlib, pkgutil, os, json, sys, inspect\n"
                "import sys\n"
                "import inspect\n"
                "class SideEffect:\n"
                "    def __init__(self, *fns):\n"
                "        self.fs = iter(fns)\n"
                "    def __call__(self, *args, **kwargs):\n"
                "        f = next(self.fs)\n"
                "        return None if f is None else f(*args, **kwargs)\n"
                "def import_all_modules_from_folder(folder_path):\n"
                "    relative_folder_path = folder_path.replace(os.sep, '.')\n"
                "    folder_path = os.path.abspath(folder_path)\n"
                "    parent_folder = os.path.dirname(folder_path)\n"
                "    if parent_folder not in sys.path:\n"
                "        sys.path.insert(0, parent_folder)\n"
                "    for _, module_name, _ in pkgutil.walk_packages([folder_path], f\"{relative_folder_path}.\"):\n"
                "        full_module_name = f\"{module_name}\"\n"
                "        try:\n"
                "            module = importlib.import_module(full_module_name)\n"
                "            for name, obj in inspect.getmembers(module):\n"
                "                if isinstance(obj, type) and 'src.main' in module_name:\n"
                "                    globals()[f\"{module_name}.{name}\"] = obj\n"
                "        except Exception as e:\n"
                "            continue\n"
                "import_all_modules_from_folder('src/main')\n"
                "class MockTest(unittest.TestCase):\n"
                "    def test_mocking(self) -> None:\n"
                "        # mocker test\n"
            )
        clear_reference_dict_line_added = False
        for method_mock in mock_workflow:
            process_mocking(method_mock, mock_test_path, clear_reference_dict_line_added)
            clear_reference_dict_line_added = True


def process_mocking(method_dict, file_path, clear_reference_dict_line_added):
    """
    Add mocking logic for a specific method.

    Args:
        method_dict (dict): Method dictionary containing mocking details.
        file_path (str): Path to the file being modified.
        clear_reference_dict_line_added (bool): Whether `clear_reference_dict()` has been added to test code
    """
    def generate_mocked_method_name(method_name, modifier):
        """Handle name mangling for private and protected methods."""
        method_name_parts = method_name.rsplit('.', 1)
        class_name, method = method_name_parts[0], method_name_parts[1]
        if method == "type" or method == "next" or method == "print" or method == "format": # escape Python keyword
            method += "_"
        if "$" in class_name:
            class_name = class_name.replace("$", '.')
        else:
            class_name += ('.' + class_name.rsplit('.', 1)[-1])
        if modifier == "private":
            return f"{class_name}._{class_name.split('.')[-1]}__{method}"
        elif modifier == "protected":
            return f"{class_name}._{method}"
        else:
            return f"{class_name}.{method}"

    method_name = method_dict.get("method_name", "")
    occurrence_idx = method_dict.get("occurrence_idx", 0)
    is_constructor = method_name.endswith("<init>")

    with open(file_path, 'r') as file:
        lines = file.readlines()

    test_method_start = next((i for i, line in enumerate(lines) if f"def test_mocking" in line), None)
    indentation_level = len(lines[test_method_start]) - len(lines[test_method_start].lstrip())
    
    # Insert @patch decorators before the test method
    mock_decorators = []
    if is_constructor:
        class_name = method_name.rsplit('.', 1)[0]
        if "$" in class_name:
            patched_name = class_name.replace("$", '.')
        else:
            patched_name = class_name + ('.' + class_name.rsplit('.', 1)[1])
        patch_line = next(
                (i for i, line in enumerate(lines)
                    if f"@patch('src.main.{patched_name}.__init__', autospec=True)" in line), None)
        if not patch_line:
            mock_decorators.extend([
                " " * indentation_level + f"@patch('src.main.{patched_name}.__init__', autospec=True)\n"
            ])
    else:
        modifier = method_dict.get("modifier", "")
        patched_name = generate_mocked_method_name(method_name, modifier)
        patch_line = next(
                (i for i, line in enumerate(lines)
                    if f"@patch('src.main.{patched_name}', autospec=True)" in line), None)
        if not patch_line:
            mock_decorators.append(" " * indentation_level + f"@patch('src.main.{patched_name}', autospec=True)\n")
    unique_name = patched_name.replace(".", "_")

    test_method_line = lines[test_method_start]
    current_params = test_method_line[test_method_line.index("(") + 1:test_method_line.index(")")].split(",")
    current_params = [p.strip() for p in current_params if p.strip()]

    new_params = []
    class_name = method_name.rsplit('.', 1)[0].split('.')[-1].split("$")[-1]
    if is_constructor:
        mock_init = f"mock_{unique_name}_init".replace("$", "_")
        if mock_init not in current_params:
            new_params.append(mock_init)
    else:
        mock_param = f"mock_{unique_name}".replace("$", "_")
        if mock_param not in current_params:
            new_params.append(mock_param)

    updated_params = ", ".join(current_params + new_params)
    lines[test_method_start] = test_method_line.replace(
        f"({', '.join(current_params)})",
        f"({updated_params})"
    )
    additional_logic = []
    method_body = []
    leading_spaces = " " * (indentation_level + 4)
    leading_spaces_inner = " " * (indentation_level + 4 * 2)
    leading_spaces_inner_inner = " " * (indentation_level + 4 * 3)
    leading_spaces_inner_inner_inner = " " * (indentation_level + 4 * 4)
    
    if is_constructor:
        init_side_effect_line = next(
                (i for i, line in enumerate(lines[test_method_start:], start=test_method_start)
                    if f"{leading_spaces}{mock_init}.side_effect = SideEffect" in line), None)
        class_name = method_name.rsplit('.', 1)[0].split('.')[-1].split("$")[-1]
        init_side_effect_name = f"{class_name}_init_side_effect_{occurrence_idx}".replace("$", "_")
        if "note" in method_dict and method_dict.get("note", "") == "skip":
            has_args = False
            line_idx_before_test_class = next((i for i, line in enumerate(lines) if line.startswith(f"class MockTest")), None)
            lines_to_save_orig_constructor = []
            full_class_name = method_name.rsplit('.', 1)[0]
            if "$" in full_class_name:
                full_class_name = full_class_name.replace("$", ".")
            else:
                full_class_name = full_class_name + "." + class_name
            lines_to_save_orig_constructor.append(f"{class_name}_clazz = globals().get('src.main.{full_class_name}')\n")
            lines_to_save_orig_constructor.append(f"orig_{class_name}_init = {class_name}_clazz.__init__\n")
            lines[line_idx_before_test_class:line_idx_before_test_class] = lines_to_save_orig_constructor
            test_method_start += 1
            if init_side_effect_line:
                init_side_effect_line += 1
            orig_constructor = f"orig_{class_name}_init"
            additional_logic.append(
                f"{leading_spaces}def {init_side_effect_name}(*args, **kwargs):\n"
                f"{leading_spaces_inner}try:\n"
                f"{leading_spaces_inner_inner}{orig_constructor}(*args, **kwargs)\n"
                f"{leading_spaces_inner}except TypeError as e:\n"
                f"{leading_spaces_inner_inner}if not 'object needs an argument' in str(e):\n"
                f"{leading_spaces_inner_inner_inner}raise\n"
            )
            if 'Static Fields Initial' in method_dict:
                global_fields_str = json.dumps(method_dict.get('Static Fields Initial'))
                method_body.append(f"{leading_spaces}update_static_fields(json.loads({global_fields_str}))\n")
            if 'Args Initial' in method_dict:
                method_body.append(f"{leading_spaces}method_args = []\n")
                for arg_idx, arg_data in method_dict.get('Args Initial'):
                    has_args = True
                    arg_data_str = json.dumps(arg_data)
                    method_body.append(f"{leading_spaces}method_args.append(convert_to_python(json.loads({arg_data_str})))\n")
            return_value_str = json.dumps(method_dict.get('Return value'))
            method_body.append(f"{leading_spaces}clazz = globals().get('src.main.{full_class_name}')\n")
            method_body.append(f"{leading_spaces}try:\n")
            method_body.append(f"{leading_spaces_inner}if issubclass(clazz, BaseException):\n")
            method_body.append(f"{leading_spaces_inner_inner}obj = Exception.__new__(clazz)\n")
            method_body.append(f"{leading_spaces_inner}else:\n")
            method_body.append(f"{leading_spaces_inner_inner}obj = object.__new__(clazz)\n")
            method_body.append(f"{leading_spaces}except TypeError:\n")
            method_body.append(f"{leading_spaces_inner}obj = clazz.__new__(clazz)\n")

            if has_args:
                if 'Exception thrown' in method_dict:
                    exception_str = json.dumps(method_dict.get('Exception thrown'))
                    method_body.append(f"{leading_spaces}e = convert_to_python(json.loads({exception_str}))\n")
                    method_body.append(f"{leading_spaces}with self.assertRaises(type(e)):\n")
                    method_body.append(f"{leading_spaces_inner_inner}{orig_constructor}(obj, *method_args)\n")
                else:
                    method_body.append(f"{leading_spaces}method_ret = {orig_constructor}(obj, *method_args)\n")
                    method_body.append(f"{leading_spaces}self.assertTrue(recursive_equal(obj, convert_to_python(json.loads({return_value_str}), force_new_object=True)))\n")
            else:
                if 'Exception thrown' in method_dict:
                    exception_str = json.dumps(method_dict.get('Exception thrown'))
                    method_body.append(f"{leading_spaces}e = convert_to_python(json.loads({exception_str}))\n")
                    method_body.append(f"{leading_spaces}with self.assertRaises(type(e)):\n")
                    method_body.append(f"{leading_spaces_inner_inner}method_ret = {orig_constructor}(obj)\n")
                else:
                    method_body.append(f"{leading_spaces}method_ret = {orig_constructor}(obj)\n")
                    method_body.append(f"{leading_spaces}self.assertTrue(recursive_equal(obj, convert_to_python(json.loads({return_value_str}), force_new_object=True)))\n")
            if 'Static Fields Changed' in method_dict:
                static_fields_changed_str = json.dumps(method_dict.get('Static Fields Changed'))
                method_body.append(f"{leading_spaces}self.assertTrue(side_effect_is_correct(json.loads({static_fields_changed_str})))\n")
            if has_args and 'Args Final' in method_dict:
                for arg_idx, arg_data in method_dict.get('Args Final'):
                    arg_data_str = json.dumps(arg_data)
                    method_body.append(f"{leading_spaces}arg_{arg_idx} = convert_to_python(json.loads({arg_data_str}), force_new_object=True)\n")
                    method_body.append(f"{leading_spaces}self.assertTrue(recursive_equal(method_args[{arg_idx}], arg_{arg_idx}))\n")
        else:
            additional_logic.append(
                f"{leading_spaces}def {init_side_effect_name}(*args, **kwargs):\n"
                f"{leading_spaces_inner}if len(args) == 0:\n"
                f"{leading_spaces_inner_inner}return\n"
            )
            side_effects = False
            if 'Exception thrown' in method_dict:
                exception_str = json.dumps(method_dict.get('Exception thrown'))
                additional_logic.append(f"{leading_spaces_inner}raise convert_to_python(json.loads({exception_str}))\n")
                side_effects = True
            if 'Static Fields Changed' in method_dict:
                static_fields_changed_str = json.dumps(method_dict.get('Static Fields Changed'))
                additional_logic.append(f"{leading_spaces_inner}update_static_fields(json.loads({static_fields_changed_str}))\n")
                side_effects = True
            if 'Args Final' in method_dict:
                for arg_idx, arg_data in method_dict.get('Args Final'):
                    arg_data_str = json.dumps(arg_data)
                    additional_logic.append(f"{leading_spaces_inner}set_object_instance_fields(args[int({arg_idx}) + 1], json.loads({arg_data_str}))\n")
                side_effects = True
            if 'Return value' in method_dict:
                return_value_str = json.dumps(method_dict.get('Return value', '{}'))
                additional_logic.append(f"{leading_spaces_inner}set_object_instance_fields(args[0], json.loads({return_value_str}))\n")
                side_effects = True
        if init_side_effect_line:
            lines[init_side_effect_line] = lines[init_side_effect_line].replace(
                ")", f", {init_side_effect_name})")
        else:
            additional_logic.append(
                f"{leading_spaces}{mock_init}.side_effect = SideEffect({init_side_effect_name})\n"
            )
    else:
        side_effect_line = next(
            (i for i, line in enumerate(lines[test_method_start:], start=test_method_start)
                if f"{leading_spaces}{mock_param}.side_effect = SideEffect" in line), None)
        name_base = method_name.split('.')[-1]
        if name_base == "type" or name_base == "next" or name_base == "print" or name_base == "format": # escape Python keyword
            name_base += "_"
        class_name = method_name.rsplit('.', 1)[0].split('.')[-1].split("$")[-1]
        if "note" in method_dict and method_dict.get("note", "") == "skip":
            has_args = False
            line_idx_before_test_class = next((i for i, line in enumerate(lines) if line.startswith(f"class MockTest")), None)
            modifier = method_dict.get("modifier", "")
            lines_to_save_orig_method = []
            full_class_name = method_name.rsplit('.', 1)[0]
            if "$" in full_class_name:
                full_class_name = full_class_name.replace("$", ".")
            else:
                full_class_name = full_class_name + "." + class_name
            lines_to_save_orig_method.append(f"{class_name}_clazz = globals().get('src.main.{full_class_name}')\n")
            orig_method = f"orig_{class_name}_{name_base}"
            if modifier == "private":
                lines_to_save_orig_method.append(f"{orig_method} = {class_name}_clazz._{class_name}__{name_base}\n")
            elif modifier == "protected":
                lines_to_save_orig_method.append(f"{orig_method} = {class_name}_clazz._{name_base}\n")
            else:
                lines_to_save_orig_method.append(f"{orig_method} = {class_name}_clazz.{name_base}\n")
            lines_to_save_orig_method.append(f"{class_name}_clazz.{orig_method} = {orig_method}\n")
            lines[line_idx_before_test_class:line_idx_before_test_class] = lines_to_save_orig_method
            test_method_start += 1
            if side_effect_line:
                side_effect_line += 1
            if side_effect_line:
                lines[side_effect_line] = lines[side_effect_line].replace(
                    ")", f", orig_{class_name}_{name_base})")
            else:
                additional_logic.append(
                    f"{leading_spaces}{mock_param}.side_effect = SideEffect(orig_{class_name}_{name_base})\n"
                )
            if 'Static Fields Initial' in method_dict:
                global_fields_str = json.dumps(method_dict.get('Static Fields Initial'))
                method_body.append(f"{leading_spaces}update_static_fields(json.loads({global_fields_str}))\n")
            if 'Args Initial' in method_dict:
                method_body.append(f"{leading_spaces}method_args = []\n")
                for arg_idx, arg_data in method_dict.get('Args Initial'):
                    has_args = True
                    arg_data_str = json.dumps(arg_data)
                    method_body.append(f"{leading_spaces}method_args.append(convert_to_python(json.loads({arg_data_str})))\n")
            instance_additional_str = ""
            if 'Instance Initial' in method_dict:
                instance_initial_str = json.dumps(method_dict.get('Instance Initial'))
                method_body.append(f"{leading_spaces}instance_initial = convert_to_python(json.loads({instance_initial_str}))\n")
                instance_additional_str = f"instance_initial."
            if 'Return value' in method_dict:
                return_value_str = json.dumps(method_dict.get('Return value'))
                if has_args:
                    if 'Exception thrown' in method_dict:
                        exception_str = json.dumps(method_dict.get('Exception thrown'))
                        method_body.append(f"{leading_spaces}e = convert_to_python(json.loads({exception_str}))\n")
                        method_body.append(f"{leading_spaces}with self.assertRaises(type(e)):\n")
                        method_body.append(f"{leading_spaces_inner_inner}method_ret = {instance_additional_str}{orig_method}(*method_args)\n")
                    else:
                        method_body.append(f"{leading_spaces}method_ret = {instance_additional_str}{orig_method}(*method_args)\n")
                        method_body.append(f"{leading_spaces}self.assertTrue(recursive_equal(method_ret, convert_to_python(json.loads({return_value_str}), force_new_object=True)))\n")
                else:
                    if 'Exception thrown' in method_dict:
                        exception_str = json.dumps(method_dict.get('Exception thrown'))
                        method_body.append(f"{leading_spaces}e = convert_to_python(json.loads({exception_str}))\n")
                        method_body.append(f"{leading_spaces}with self.assertRaises(type(e)):\n")
                        method_body.append(f"{leading_spaces_inner_inner}method_ret = {instance_additional_str}{orig_method}()\n")
                    else:
                        method_body.append(f"{leading_spaces}method_ret = {instance_additional_str}{orig_method}()\n")
                        method_body.append(f"{leading_spaces}self.assertTrue(recursive_equal(method_ret, convert_to_python(json.loads({return_value_str}), force_new_object=True)))\n")
            else:
                if has_args:
                    if 'Exception thrown' in method_dict:
                        exception_str = json.dumps(method_dict.get('Exception thrown'))
                        method_body.append(f"{leading_spaces}e = convert_to_python(json.loads({exception_str}))\n")
                        method_body.append(f"{leading_spaces}with self.assertRaises(type(e)):\n")
                        method_body.append(f"{leading_spaces_inner_inner}{instance_additional_str}{orig_method}(*method_args)\n")
                    else:
                        method_body.append(f"{leading_spaces}{instance_additional_str}{orig_method}(*method_args)\n")
                else:
                    if 'Exception thrown' in method_dict:
                        exception_str = json.dumps(method_dict.get('Exception thrown'))
                        method_body.append(f"{leading_spaces}e = convert_to_python(json.loads({exception_str}))\n")
                        method_body.append(f"{leading_spaces}with self.assertRaises(type(e)):\n")
                        method_body.append(f"{leading_spaces_inner_inner}{instance_additional_str}{orig_method}()\n")
                    else:
                        method_body.append(f"{leading_spaces}{instance_additional_str}{orig_method}()\n")
            if 'Instance Final' in method_dict:
                instance_final_str = json.dumps(method_dict.get('Instance Final'))
                method_body.append(f"{leading_spaces}instance_final = convert_to_python(json.loads({instance_final_str}), force_new_object=True)\n")
                method_body.append(f"{leading_spaces}self.assertTrue(recursive_equal(instance_initial, instance_final))\n")
            if 'Static Fields Changed' in method_dict:
                static_fields_changed_str = json.dumps(method_dict.get('Static Fields Changed'))
                method_body.append(f"{leading_spaces}self.assertTrue(side_effect_is_correct(json.loads({static_fields_changed_str})))\n")
            if has_args and 'Args Final' in method_dict:
                for arg_idx, arg_data in method_dict.get('Args Final'):
                    arg_data_str = json.dumps(arg_data)
                    method_body.append(f"{leading_spaces}arg_{arg_idx} = convert_to_python(json.loads({arg_data_str}), force_new_object=True)\n")
                    method_body.append(f"{leading_spaces}self.assertTrue(recursive_equal(method_args[{arg_idx}], arg_{arg_idx}))\n")
        else:
            side_effect_name = f"{unique_name}_side_effect_{occurrence_idx}"
            if 'Instance Final' in method_dict:
                nested_logic = [
                    f"{leading_spaces}def {side_effect_name}(self, *args):\n",
                ]
            else:
                nested_logic = [
                    f"{leading_spaces}def {side_effect_name}(*args):\n",
                ]
            side_effects = False
            if 'Exception thrown' in method_dict:
                exception_str = json.dumps(method_dict.get('Exception thrown'))
                nested_logic.append(f"{leading_spaces_inner}raise convert_to_python(json.loads({exception_str}))\n")
                side_effects = True
            if 'Static Fields Changed' in method_dict:
                static_fields_changed_str = json.dumps(method_dict.get('Static Fields Changed'))
                nested_logic.append(f"{leading_spaces_inner}update_static_fields(json.loads({static_fields_changed_str}))\n")
                side_effects = True
            if 'Instance Final' in method_dict:
                instance_final_str = json.dumps(method_dict.get('Instance Final'))
                nested_logic.append(f"{leading_spaces_inner}set_object_instance_fields(self, json.loads({instance_final_str}))\n")
                side_effects = True
            if 'Args Final' in method_dict:
                for arg_idx, arg_data in method_dict.get('Args Final', []):
                    arg_data_str = json.dumps(arg_data)
                    nested_logic.append(f"{leading_spaces_inner}set_object_instance_fields(args[int({arg_idx})], json.loads({arg_data_str}))\n")
                side_effects = True
            if 'Return value' in method_dict:
                return_value_str = json.dumps(method_dict.get('Return value', '{}'))
                nested_logic.append(f"{leading_spaces_inner}return convert_to_python(json.loads({return_value_str}))\n")
                side_effects = True
            if not side_effects:
                nested_logic.append(f"{leading_spaces_inner}return None\n")
            additional_logic.extend(nested_logic)
            if side_effect_line:
                lines[side_effect_line] = lines[side_effect_line].replace(
                    ")", f", {side_effect_name})")
            else:
                additional_logic.append(
                    f"{leading_spaces}{mock_param}.side_effect = SideEffect({side_effect_name})\n"
                )
    if not clear_reference_dict_line_added:
        method_body.append(f"{leading_spaces}clear_reference_dict()")
    patch_start = next((i for i, line in enumerate(lines) if f"@patch" in line), None)
    new_test_method_start = next((i for i, line in enumerate(lines) if f"def test_mocking" in line), None)
    if new_test_method_start is None:
        new_test_method_start = next((i for i, line in enumerate(lines) if f"def testtest_mocking" in line), None)
    if not patch_start:
        lines[new_test_method_start:new_test_method_start] = mock_decorators
    else:
        lines[patch_start:patch_start] = mock_decorators
    lines[new_test_method_start + len(mock_decorators) + 1:new_test_method_start + len(mock_decorators) + 1] = additional_logic
    lines.extend(method_body)
    with open(file_path, 'w') as file:
        file.writelines(lines)


if __name__ == "__main__":
    clear_reference_dict()
    input_log_file = sys.argv[1]
    result = process_test_log(input_log_file, parse_logs)

# /usr/libexec/java_home -V
# export JAVA_HOME=`/usr/libexec/java_home -v 1.8`
# find . -type f -name '*decomposed_mocker*' -exec rm {} \; 
# for log_file in *.log; do python3 script.py "$log_file"; done  
# python3 -m pytest -k mocker
