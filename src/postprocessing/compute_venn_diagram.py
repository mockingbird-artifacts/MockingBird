import os
import argparse

def normalize_entry(entry: str) -> str:
    if not entry or '|' not in entry:
        return entry
    class_part, method_part = entry.split('|', 1)
    if ':' in class_part:
        class_name = class_part.split(':', 1)[1]
    else:
        class_name = class_part
    if ':' in method_part:
        method_name = method_part.split(':', 1)[1]
    else:
        method_name = method_part
    return f'{class_name}|{method_name}'

def parse_log(filepath):
    entries = set()
    if not os.path.exists(filepath):
        return entries
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entries.add(normalize_entry(line))
    return entries

def save_to_log(filename, items):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'w') as f:
        for item in sorted(items):
            f.write(item + '\n')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True)
    parser.add_argument('--temperature', required=True)
    parser.add_argument('--model', required=True)
    args = parser.parse_args()

    base_dir = f'data/AMF_validation_results/{args.model}/{args.temperature}'
    mock_file = f'{base_dir}/{args.project}_mock_success.log'
    atp_file = f'{base_dir}/{args.project}_atp.log'
    graal_file = f'{base_dir}/{args.project}_graal_success.log'

    mock_set = parse_log(mock_file)
    atp_set = parse_log(atp_file)
    graal_set = parse_log(graal_file)

    only_atp = atp_set - (mock_set | graal_set)
    only_mock = mock_set - (atp_set | graal_set)
    only_graal = graal_set - (mock_set | atp_set)

    atp_graal = (atp_set & graal_set) - mock_set
    atp_mock = (atp_set & mock_set) - graal_set
    graal_mock = (graal_set & mock_set) - atp_set

    all_three = atp_set & graal_set & mock_set

    print(f'ATP only: {len(only_atp)}')
    print(f'GRAAL only: {len(only_graal)}')
    print(f'MOCK only: {len(only_mock)}')
    print(f'ATP + GRAAL: {len(atp_graal)}')
    print(f'ATP + MOCK: {len(atp_mock)}')
    print(f'GRAAL + MOCK: {len(graal_mock)}')
    print(f'ALL PASSED: {len(all_three)}')

    save_to_log(f'{base_dir}/{args.project}_only_atp.log', only_atp)
    save_to_log(f'{base_dir}/{args.project}_only_graal.log', only_graal)
    save_to_log(f'{base_dir}/{args.project}_only_mock.log', only_mock)
    save_to_log(f'{base_dir}/{args.project}_atp_graal.log', atp_graal)
    save_to_log(f'{base_dir}/{args.project}_atp_mock.log', atp_mock)
    save_to_log(f'{base_dir}/{args.project}_graal_mock.log', graal_mock)
    save_to_log(f'{base_dir}/{args.project}_all_passed.log', all_three)

if __name__ == '__main__':
    main()
