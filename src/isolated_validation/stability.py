"""Canonical form of a generated mock test for stability comparison. The JSON records embedded in the test are parsed;
memory addresses and identity hash codes (Object@hex) are dropped and dict keys / single-key list entries (class and field
enumerations) sorted, so JVM-run-specific identities and enumeration order do not matter. The initial static-field snapshot
(update_static_fields(...)) is not compared: it is replayed into the translation as recorded, so per-JVM values in it
(random UIDs, counters) cannot make the mock test flaky; the same holds for the static_fields section of object records,
and in the static side-effect assertion (side_effect_is_correct(...)) only fields whose value differs from that initial
snapshot are compared. Everything the translation
has to reproduce (arguments, return value, instance state, real static-field changes) is compared. Two runs of the same
Java test are considered stable when their canonical forms are identical."""
import ast, json, re
LIT = re.compile(r'json\.loads\((".*?(?<!\\)")\)')
HASH = re.compile(r"@[0-9a-f]{5,8}\b")
def canon(x):
    if isinstance(x, dict):
        return {k: canon(v) for k, v in sorted(x.items()) if k not in ("memory_address", "static_fields")}   # static_fields of an object record = replayed class state
    if isinstance(x, list):
        items = [canon(v) for v in x]
        if all(isinstance(v, dict) and len(v) == 1 for v in items): items.sort(key=lambda v: json.dumps(v, sort_keys=True))
        return items
    if isinstance(x, str): return HASH.sub("@HASH", x)
    return x
def _static_entries(payload):
    """(class, field, canonical details) triples of a static-field record ([{class: [{field: details}, ...]}, ...])."""
    out = set()
    for cls_entry in payload or []:
        if not isinstance(cls_entry, dict): continue
        for cls, fields in cls_entry.items():
            for fe in fields or []:
                if isinstance(fe, dict):
                    for fname, det in fe.items(): out.add((cls, fname, json.dumps(canon(det), sort_keys=True)))
    return out
def _payload(literal):
    return json.loads(ast.literal_eval(literal))
def normalize(path):
    lines = open(path, errors="ignore").read().splitlines(keepends=True)
    initial = set()
    for line in lines:
        if line.lstrip().startswith("update_static_fields("):
            for m in LIT.finditer(line):
                try: initial |= _static_entries(_payload(m.group(1)))
                except Exception: pass
    def generic(m):
        try: return "J<" + json.dumps(canon(_payload(m.group(1))), sort_keys=True) + ">"
        except Exception: return m.group(0)
    def side_effect(m):
        try: return "J<" + json.dumps(sorted(e for e in _static_entries(_payload(m.group(1))) if e not in initial)) + ">"
        except Exception: return m.group(0)
    out = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("update_static_fields("):
            out.append("        update_static_fields(J<initial static state: replayed, not compared>)\n")
        elif "side_effect_is_correct(" in stripped:
            out.append(LIT.sub(side_effect, line))
        else:
            out.append(LIT.sub(generic, line))
    return "".join(out)
def same_test(path_a, path_b):
    return normalize(path_a) == normalize(path_b)
