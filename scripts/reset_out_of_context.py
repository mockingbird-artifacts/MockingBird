#!/usr/bin/env python3
"""Mark every fragment of a project whose translation_status is 'out_of_context' as pending again, so that a further
`scripts/run_project.sh <project> translate results` re-attempts exactly those fragments (the harness now shrinks the
prompt before declaring a fragment out of context, so most of them translate on the second pass).
usage: python3 scripts/reset_out_of_context.py <project> [--model deepseek-coder-33b-instruct] [--temperature 0.0] [--suffix _evosuite_cleaned]"""
import argparse, glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils.atomic_json import dump_json_atomic

ap = argparse.ArgumentParser(); ap.add_argument('project'); ap.add_argument('--model', default='deepseek-coder-33b-instruct')
ap.add_argument('--temperature', default='0.0'); ap.add_argument('--suffix', default='_evosuite_cleaned'); a = ap.parse_args()
sd = f'data/schemas{a.suffix}/{a.model}/{a.temperature}/{a.project}'
reset = 0
for f in sorted(glob.glob(f'{sd}/*.json')):
    d = json.load(open(f)); changed = False
    for cls in d.get('classes', {}).values():
        for kind in ('methods', 'fields'):
            for name, r in cls.get(kind, {}).items():
                if r.get('translation_status') == 'out_of_context':
                    r['translation_status'] = 'pending'; r['translation'] = []
                    for k in ('syntactic_validation', 'field_exercise', 'graal_validation', 'mocking_validation', 'test_validation'):
                        if k in r: r[k] = 'pending'
                    reset += 1; changed = True
    if changed: dump_json_atomic(d, f)
print(f'{a.project}: {reset} out_of_context fragments reset to pending')
