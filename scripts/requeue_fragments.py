#!/usr/bin/env python3
"""Return selected fragments of a project to 'pending' so that a further `scripts/run_project.sh <project> translate results`
re-translates exactly those with the full harness (feedback rounds, fix agents, and mock tests that are eligible now).
Selections (combine freely):
  --out-of-context      fragments marked out_of_context (the harness now shrinks prompts before giving up)
  --deferred            translated fragments without a mock verdict whose focal method has mock tests on disk: their tests
                        were not yet eligible when they were translated (a test is eligible only once every focal method it
                        touches is translated), so they were never validated
  --one-shot-validate   verdicts written by an earlier validation-only pass (mock_validation.py: one attempt, no feedback),
                        identified by their timestamp falling inside a 'validate START'..'validate DONE' window of
                        logs/stages_<project>.txt; failed ones are re-queued, successes are kept
usage: python3 scripts/requeue_fragments.py <project> [--out-of-context] [--deferred] [--one-shot-validate] [--dry-run]"""
import argparse, glob, json, os, re, sys
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils.atomic_json import dump_json_atomic

ap = argparse.ArgumentParser(); ap.add_argument('project'); ap.add_argument('--model', default='deepseek-coder-33b-instruct')
ap.add_argument('--temperature', default='0.0'); ap.add_argument('--suffix', default='_evosuite_cleaned')
ap.add_argument('--out-of-context', action='store_true'); ap.add_argument('--deferred', action='store_true')
ap.add_argument('--one-shot-validate', action='store_true'); ap.add_argument('--dry-run', action='store_true'); a = ap.parse_args()
sd = f'data/schemas{a.suffix}/{a.model}/{a.temperature}/{a.project}'

# focal methods that have mock tests on disk (mock test files end in _<Class>_<method>.py)
have_tests = set()
for f in glob.glob(f'data/mock_tests/{a.project}/src/**/*_mocker_*.py', recursive=True):
    m = re.search(r'_decomposed_mocker_\d+_(.+)\.py$', os.path.basename(f))
    if m: have_tests.add(m.group(1))

# windows of validation-only passes
windows = []
stages = f'logs/stages_{a.project}.txt'
if a.one_shot_validate and os.path.exists(stages):
    start = None
    for line in open(stages):
        parts = line.split()
        if len(parts) < 3: continue
        ts = parts[0]; evt = ' '.join(parts[2:4])
        try: t = datetime.strptime(ts, '%Y-%m-%dT%H:%M:%SZ')
        except ValueError: continue
        if evt == 'validate START': start = t
        elif evt.startswith('validate DONE') and start: windows.append((start - timedelta(minutes=2), t + timedelta(minutes=2))); start = None
    if start: windows.append((start - timedelta(minutes=2), datetime.utcnow() + timedelta(minutes=2)))

def in_window(stamp):
    if not stamp: return False
    try: t = datetime.fromisoformat(str(stamp)[:19])
    except ValueError: return False
    return any(lo <= t <= hi for lo, hi in windows)

counts = {'out_of_context': 0, 'deferred': 0, 'one_shot_failed': 0, 'one_shot_kept_success': 0}
for f in sorted(glob.glob(f'{sd}/*.json')):
    if '.src.main.' not in os.path.basename(f): continue
    d = json.load(open(f)); changed = False
    for cname, cls in d.get('classes', {}).items():
        if cls.get('is_interface'): continue
        short = cname.split(':')[-1]
        for kind in ('methods',):
            for name, r in cls.get(kind, {}).items():
                if r.get('is_overload'): continue
                st = r.get('translation_status', 'pending'); mv = r.get('mocking_validation', 'pending')
                out = mv.get('outcome', 'pending') if isinstance(mv, dict) else mv
                why = None
                if a.out_of_context and st == 'out_of_context': why = 'out_of_context'
                elif a.deferred and st == 'attempted' and out not in ('success', 'failed') and f"{short}_{name.split(':')[-1]}" in have_tests: why = 'deferred'
                elif a.one_shot_validate and st == 'attempted' and out in ('success', 'failed') and in_window(r.get('generation_timestamp')):
                    if out == 'success': counts['one_shot_kept_success'] += 1; continue
                    why = 'one_shot_failed'
                if not why: continue
                counts[why] += 1
                if not a.dry_run:
                    r['translation_status'] = 'pending'; r['translation'] = []
                    for k in ('syntactic_validation', 'field_exercise', 'graal_validation', 'mocking_validation', 'test_validation'):
                        if k in r: r[k] = 'pending'
                    changed = True
    if changed: dump_json_atomic(d, f)
total = counts['out_of_context'] + counts['deferred'] + counts['one_shot_failed']
print(f"{a.project}: re-queued {total} fragments ({counts}){' [dry run]' if a.dry_run else ''}; validate windows: {len(windows)}")
sys.exit(0 if total == 0 else 3)   # exit 3 = something was re-queued (callers use it to decide whether to run translate)
