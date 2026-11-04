#!/usr/bin/env python3
"""Repair schema files truncated by a failed write (e.g. a full disk). For every unparseable file of the project, the
longest parseable prefix is recovered (everything written before the cut: structure, type resolution, translation
status and translations of the fragments that precede it) and overlaid on a freshly generated base schema of the same
class, which supplies the structure of everything after the cut; those fragments return to 'pending' and lose their
type-resolution entries, which the type stages fill in again (they skip entries that are already resolved).
usage: python3 scripts/repair_truncated_schemas.py <project> <base schemas dir> [--schemas-dir <damaged schemas dir>] [--dry-run]
       (base schemas: run scripts/create_project_schema.sh with a scratch model name, e.g. schema_probe)"""
import argparse, glob, json, os, shutil, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils.atomic_json import dump_json_atomic


def closers_for(text):
    """Bracket closers needed to complete `text`, or None if it ends inside a string / after a dangling key."""
    stack, in_str, esc, i = [], False, False, 0
    last_sig = ''
    while i < len(text):
        c = text[i]
        if in_str:
            if esc: esc = False
            elif c == '\\': esc = True
            elif c == '"': in_str = False; last_sig = '"'
        else:
            if c == '"': in_str = True
            elif c in '{[': stack.append(c); last_sig = c
            elif c in '}]':
                if not stack: return None
                stack.pop(); last_sig = c
            elif not c.isspace(): last_sig = c
        i += 1
    if in_str or last_sig in (':', ','): return None
    return ''.join('}' if c == '{' else ']' for c in reversed(stack))


def longest_valid_prefix(text):
    cut = len(text)
    while cut > 0:
        cand = text[:cut].rstrip()
        if cand.endswith(','): cand = cand[:-1]
        cl = closers_for(cand)
        if cl is not None:
            try: return json.loads(cand + cl), cut
            except json.JSONDecodeError: pass
        nl = text.rfind('\n', 0, cut - 1)
        cut = nl if nl > 0 else 0
    return None, 0


def overlay(base, prefix):
    """prefix values win; dicts merge recursively; lists/scalars from the prefix replace the base."""
    if isinstance(base, dict) and isinstance(prefix, dict):
        out = dict(base)
        for k, v in prefix.items(): out[k] = overlay(base.get(k), v) if k in base else v
        return out
    return prefix if prefix is not None else base


ap = argparse.ArgumentParser(); ap.add_argument('project'); ap.add_argument('base_dir')
ap.add_argument('--schemas-dir', default=None); ap.add_argument('--dry-run', action='store_true')
ap.add_argument('--reset-repaired', action='store_true', help='return every fragment of a repaired file to pending (the per-file import list follows the fragment records and is lost at any cut)')
a = ap.parse_args()
sd = a.schemas_dir or f'data/schemas_evosuite_cleaned/deepseek-coder-33b-instruct/0.0/{a.project}'
stamp = time.strftime('%Y%m%dT%H%M%S'); repaired = 0
for f in sorted(glob.glob(f'{sd}/*.json')):
    text = open(f).read()
    try: json.loads(text); continue
    except json.JSONDecodeError: pass
    base_f = os.path.join(a.base_dir, os.path.basename(f))
    if not os.path.exists(base_f):
        print(f'  {os.path.basename(f)}: DAMAGED but no base schema at {base_f}; skipped'); continue
    base = json.load(open(base_f)); prefix, cut = longest_valid_prefix(text)
    # only the last fragment record of the prefix can be the one the cut fell into (dump order); never trust it
    last = None
    for cname, cls in (prefix or {}).get('classes', {}).items():
        for kind in ('methods', 'fields'):
            for name in cls.get(kind, {}): last = (cname, kind, name)
    if last: del prefix['classes'][last[0]][last[1]][last[2]]
    kept = sum(len(c.get(k, {})) for c in (prefix or {}).get('classes', {}).values() for k in ('methods', 'fields'))
    total = sum(len(c.get(k, {})) for c in base.get('classes', {}).values() for k in ('methods', 'fields'))
    merged = overlay(base, prefix) if prefix else base
    if a.reset_repaired:
        for cls in merged.get('classes', {}).values():
            for kind in ('methods', 'fields'):
                for r in cls.get(kind, {}).values():
                    r['translation_status'] = 'pending'; r['translation'] = []
    print(f'  {os.path.basename(f)}: {len(text)} bytes, prefix {cut} bytes kept {kept}/{total} fragment records')
    if not a.dry_run:
        shutil.copy(f, f + f'.damaged_{stamp}'); dump_json_atomic(merged, f); repaired += 1
print(f'{a.project}: {repaired} files repaired' + (' (dry run)' if a.dry_run else ''))
