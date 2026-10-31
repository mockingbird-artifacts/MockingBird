#!/usr/bin/env python3
"""Classes of a project that still have public/protected methods without any mock test (after a first mock-test generation),
as fully-qualified names (nested classes as Outer$Inner), one per line. Interfaces, abstract classes, private, native and
abstract methods are left out. usage: evosuite_targets.py <project> <schemas dir> <mock tests dir>"""
import glob, json, os, re, sys
P, schemas, mock_tests = sys.argv[1], sys.argv[2], sys.argv[3]
suf = set()
for dp, _, fs in os.walk(mock_tests):
    for f in fs:
        if "_mocker_" in f: suf.add(f.rsplit("_mocker_", 1)[1].split("_", 1)[1])
def has(cn, mn): return any(s.endswith(f"_{cn}_{mn}.py") or s == f"{cn}_{mn}.py" or s.endswith(f"${cn}_{mn}.py") for s in suf)
out = {}
for f in glob.glob(os.path.join(schemas, "*.json")):
    if f"{P}.src.main" not in f: continue
    d = json.load(open(f)); file_fqcn = os.path.basename(f).split(".src.main.")[1][:-5]; outer = file_fqcn.rsplit(".", 1)[1]
    for c, cls in d["classes"].items():
        if cls.get("is_interface") or cls.get("is_abstract"): continue
        cn = c.split(":")[-1]; fq = file_fqcn if cn == outer else f"{file_fqcn}${cn}"; n = 0
        for m, v in cls["methods"].items():
            if v.get("is_overload"): continue
            mods = v.get("modifiers") or []
            if "native" in mods or "abstract" in mods or "private" in mods: continue
            mn = m.split(":")[-1]; tn = "<init>" if (v.get("is_constructor") or re.sub(r"\d+$", "", mn) == cn) else mn
            if not has(cn, tn): n += 1
        if n: out[fq] = n
for fq, n in sorted(out.items(), key=lambda t: -t[1]): print(fq)
print(f"# {len(out)} classes, {sum(out.values())} uncovered methods", file=sys.stderr)
