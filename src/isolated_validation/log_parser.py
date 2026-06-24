import re
import sys



def process_side_effect(line: str) -> dict:
    lhs, rhs = line.split(':', 1)
    method_name, modifier = lhs.split("[")
    modifier = modifier.strip()

    entry = {
        "method_name": method_name,
        "modifier": modifier
    }

    args_initial = extract_args(rhs, '(Arg\d+)( initial state: )')
    if args_initial:
        entry["Args Initial"] = args_initial

    args_final = extract_args(rhs, '(Arg\d+)( final state: )')
    if args_final:
        entry["Args Final"] = args_final

    for key in ["Return value", "Instance Initial", "Instance Final", "Static Fields Changed", "Static Fields Initial", "Exception thrown"]:
        key_match = re.search(f'{key}: (\{{.*\}}|\[.*\])', rhs)
        if key_match:
            value = match_json_structure(rhs[key_match.start(1):])
            if value:
                entry[key] = value
    return entry

def extract_args(text, regex):
    args_initial = []

    for match in re.finditer(regex, text):
        arg_idx = match.group(1).split("Arg")[1]
        start = match.end()

        stack = []
        json_start = None
        in_quote = None
        escaped = False

        for i in range(start, len(text)):
            char = text[i]

            if escaped:
                escaped = False
                continue

            if char == "\\":
                escaped = True
                continue

            if char in "\"'" and not escaped:
                if in_quote is None:
                    in_quote = char
                elif in_quote == char:
                    in_quote = None

            elif char == "{" and in_quote is None:
                if not stack:
                    json_start = i
                stack.append(char)

            elif char == "}" and in_quote is None:
                if stack:
                    stack.pop()
                    if not stack:
                        args_initial.append((arg_idx, text[json_start:i+1]))
                        break

    return args_initial

def match_json_structure(text):
    stack = []
    start_index = None
    in_quote = None
    escape = False

    for i, char in enumerate(text):
        if escape:
            escape = False
            continue

        if char == "\\":
            escape = True
            continue

        if char in "\"'":
            if in_quote is None:
                in_quote = char
            elif in_quote == char:
                in_quote = None
            continue

        if in_quote:
            continue

        if char in "{[":
            if not stack:
                start_index = i
            stack.append(char)
        elif char in "}]":
            if stack:
                stack.pop()
                if not stack:
                    return text[start_index:i+1]

    return None


def match_nested_braces(s: str) -> str:
    stack = []
    for i, char in enumerate(s):
        if char == '{':
            stack.append(char)
        elif char == '}':
            stack.pop()
        if not stack:
            return s[:i+1]
    return None

def get_side_effect_and_end_line(start_line_index: int, lines: list) -> list:
    counter = 1
    for line_index in range(start_line_index + 1, len(lines)):
        line = lines[line_index].strip()
        if line.startswith("==========START OF"):
            counter += 1
        elif line.startswith("==========END OF"):
            counter -= 1
            if counter == 0:
                return [process_side_effect(lines[line_index - 1]), line_index]

def parse_logs(input_log_file: str) -> dict:
    with open(input_log_file, 'r') as file:
        lines = file.readlines()
    all_mock_workflows = []
    for start_line_index in range(len(lines)):
        start_line = lines[start_line_index].strip()
        if start_line.startswith("==========START OF"):
            methods_to_mock = []
            mock_indices = {}
            retrieve_mocking_info_for_one_method(methods_to_mock, mock_indices, 0, len(lines) - 1, start_line_index, lines)
            all_mock_workflows.append(methods_to_mock)
    return all_mock_workflows
            


def retrieve_mocking_info_for_one_method(methods_to_mock: list, mock_indices: dict, start: int, end: int, method_index: int, lines: list) -> None:
    chunk_start = start
    while chunk_start <= end:
        line = lines[chunk_start].strip()
        if line.startswith("==========START OF"):
            method_name = line.split("==========START OF ")[1].split("==========")[0]
            chunk_side_effect, chunk_end = get_side_effect_and_end_line(chunk_start, lines)
            if chunk_start == method_index:
                if not method_name in mock_indices:
                    mock_indices[method_name] = 0
                mock_indices[method_name] += 1
                modifier = lines[chunk_end - 1].split(':', 1)[0].split("[")[1].strip()
                chunk_side_effect.update({
                    "occurrence_idx": mock_indices[method_name],
                    "note": "skip",
                    "modifier": modifier
                })
                methods_to_mock.append(chunk_side_effect)
                find_mocks_in_call_chain(methods_to_mock, mock_indices, chunk_start + 1, chunk_end - 1, lines)
                break
            elif chunk_end < method_index:
                chunk_start = chunk_end + 1
            else:
                chunk_start += 1
        else:
            break

def find_mocks_in_call_chain(methods_to_mock: list, mock_indices: dict, start: int, end: int, lines: list) -> None:
    chunk_start = start
    while chunk_start <= end:
        line = lines[chunk_start].strip()
        if line.startswith("==========START OF"):
            method_name = line.split("==========START OF ")[1].split("==========")[0]
            chunk_side_effect, chunk_end = get_side_effect_and_end_line(chunk_start, lines)
            if method_name not in mock_indices:
                mock_indices[method_name] = -1
            mock_indices[method_name] += 1
            chunk_side_effect["occurrence_idx"] = mock_indices[method_name]
            methods_to_mock.append(chunk_side_effect)
            chunk_start = chunk_end + 1
        else:
            break





             


if __name__ == "__main__":
    input_log_file = sys.argv[1]
    result = parse_logs(input_log_file)
    import pprint
    pprint.pprint(result)