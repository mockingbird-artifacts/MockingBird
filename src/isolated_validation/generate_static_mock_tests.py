#!/usr/bin/env python3
"""Static mock tests for bodyless Java methods (interface methods, abstract methods, empty-body methods).

EvoSuite cannot exercise such methods, so the dynamic mock-test generator never covers them and the translation pipeline
installs the skeleton stub for them without consulting the model. This pass derives, from the schema alone and without
executing any Java, one mock test per bodyless method that checks the Python side of the contract:
  - the translated module imports and defines the class;
  - the class defines the method under the skeleton's name with the same number of positional parameters;
  - the body is trivial (docstring, pass, ..., raise NotImplementedError, bare/None return, or @abstractmethod), i.e. no
    logic was invented for a method that has none in Java;
  - calling it does nothing beyond returning None or raising NotImplementedError.
The files follow the dynamic naming convention (…_mocker_<n>_<Class>_<method>.py) so ValidateByMocking picks them up as
eligible tests of that fragment, and the result printer counts such methods as validatable.
usage: python3 src/isolated_validation/generate_static_mock_tests.py <project> [--model M] [--temperature T] [--suffix S]"""
import argparse, glob, json, os, re, sys

TEMPLATE = r'''import unittest, importlib, pkgutil, os, sys, inspect, ast, textwrap
def import_all_modules_from_folder(folder_path):
    relative_folder_path = folder_path.replace(os.sep, '.')
    folder_path = os.path.abspath(folder_path)
    parent_folder = os.path.dirname(folder_path)
    if parent_folder not in sys.path:
        sys.path.insert(0, parent_folder)
    for _, module_name, _ in pkgutil.walk_packages([folder_path], f"{relative_folder_path}."):
        try:
            module = importlib.import_module(module_name)
            for name, obj in inspect.getmembers(module):
                if isinstance(obj, type) and 'src.main' in module_name:
                    globals()[f"{module_name}.{name}"] = obj
        except Exception:
            continue
import_all_modules_from_folder('src/main')
MODULE = %(module)r
CLASS = %(cls)r
NAMES = %(names)r          # skeleton name first, then Java-name variants
EXPECTED_PARAMS = %(params)d
JAVA = %(java)r

def _is_trivial(stmt):
    if isinstance(stmt, ast.Pass): return True
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, (str, type(...))): return True
    if isinstance(stmt, ast.Return) and (stmt.value is None or (isinstance(stmt.value, ast.Constant) and stmt.value.value is None)): return True
    if isinstance(stmt, ast.Raise):
        exc = stmt.exc
        if isinstance(exc, ast.Call): exc = exc.func
        if isinstance(exc, ast.Name) and exc.id == 'NotImplementedError': return True
    return False

class MockTest(unittest.TestCase):
    def test_mocking(self) -> None:
        clazz = globals().get(f'{MODULE}.{CLASS}')
        if clazz is None:
            module = importlib.import_module(MODULE)
            clazz = getattr(module, CLASS, None)
        self.assertIsNotNone(clazz, f'class {CLASS} is not defined in module {MODULE} (translation of `{JAVA}` is unreachable)')
        name = next((n for n in NAMES if n in vars(clazz)), None) or next((n for n in NAMES if hasattr(clazz, n)), None)
        self.assertIsNotNone(name, f'bodyless method `{JAVA}` is missing from class {CLASS}: expected one of {NAMES}')
        raw = inspect.getattr_static(clazz, name)
        fn = raw.__func__ if isinstance(raw, (staticmethod, classmethod)) else raw
        self.assertTrue(inspect.isfunction(fn), f'{CLASS}.{name} is not a method (found {type(raw).__name__})')
        params = list(inspect.signature(fn).parameters.values())
        positional = [p.name for p in params if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
        if not isinstance(raw, staticmethod) and positional and positional[0] in ('self', 'cls'):
            positional = positional[1:]
        has_varargs = any(p.kind == p.VAR_POSITIONAL for p in params)
        if not has_varargs:
            self.assertEqual(len(positional), EXPECTED_PARAMS, f'signature of {CLASS}.{name} changed: Java declares {EXPECTED_PARAMS} parameter(s), Python has {positional}')
        try:
            source = textwrap.dedent(inspect.getsource(fn))
            node = ast.parse(source).body[0]
        except (OSError, TypeError, SyntaxError) as e:
            self.fail(f'source of {CLASS}.{name} could not be inspected: {e}')
        is_abstract = any((isinstance(d, ast.Name) and d.id == 'abstractmethod') or (isinstance(d, ast.Attribute) and d.attr == 'abstractmethod') for d in node.decorator_list)
        if not is_abstract and not all(_is_trivial(s) for s in node.body):
            self.fail(f'bodyless Java method `{JAVA}` was translated with logic in {CLASS}.{name}: ' + ' | '.join(ast.unparse(s)[:80] for s in node.body if not _is_trivial(s)))
        args = [None] * len(positional)
        try:
            ret = fn(*args) if isinstance(raw, staticmethod) else fn(None, *args)
        except NotImplementedError:
            return
        except Exception as e:
            self.fail(f'calling the stub {CLASS}.{name} raised {type(e).__name__}: {e}')
        self.assertIsNone(ret, f'stub {CLASS}.{name} returned a value ({ret!r}) although the Java method has no body')
'''

def is_bodyless(body_lines):
    body = ' '.join(l.strip() for l in (body_lines or []))
    body = re.sub(r'@\w+(\([^)]*\))?', '', body).strip()            # drop annotations
    if not body: return False
    if body.endswith(';') and '{' not in body: return True           # abstract / interface declaration
    return bool(re.search(r'\)\s*(throws\s+[\w.,\s]+)?\s*\{\s*\}\s*$', body))   # empty block body `{ }`

def python_names(java_name, modifiers, partial):
    names = []
    if partial:
        m = re.search(r'def\s+(\w+)\s*\(', ''.join(partial))
        if m: names.append(m.group(1))
    for n in (java_name, '_' + java_name, '__' + java_name):
        if n not in names: names.append(n)
    return names

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('project'); ap.add_argument('--model', default='deepseek-coder-33b-instruct')
    ap.add_argument('--temperature', default='0.0'); ap.add_argument('--suffix', default='_evosuite_cleaned'); a = ap.parse_args()
    sd = f'data/schemas{a.suffix}/{a.model}/{a.temperature}/{a.project}'; out_root = f'data/mock_tests/{a.project}'
    written = skipped_ctor = 0; kinds = {'interface': 0, 'abstract': 0, 'empty': 0}
    for f in sorted(glob.glob(f'{sd}/*.json')):
        base = os.path.basename(f)[:-5]
        if '.src.main.' not in base: continue
        module = 'src.main.' + base.split('.src.main.', 1)[1]
        pkg_dir = os.path.join(out_root, 'src', 'test', *module.split('.')[2:-1])
        d = json.load(open(f))
        for cname, cls in d.get('classes', {}).items():
            simple = cname.split(':')[-1]
            for mname, r in cls.get('methods', {}).items():
                if r.get('is_constructor') or not is_bodyless(r.get('body')): continue
                jname = mname.split(':')[-1]
                kind = 'interface' if cls.get('is_interface') else ('abstract' if 'abstract' in (r.get('modifiers') or []) else 'empty')
                kinds[kind] += 1
                test = TEMPLATE % dict(module=module, cls=simple, names=python_names(jname, r.get('modifiers'), r.get('partial_translation')),
                                       params=len(r.get('parameters') or []), java=re.sub(r'\s+', ' ', ' '.join(r.get('body') or []))[:160])
                os.makedirs(pkg_dir, exist_ok=True)
                path = os.path.join(pkg_dir, f'{simple}_{jname}_static_mocker_0_{simple}_{jname}.py')
                with open(path, 'w') as o: o.write(test)
                written += 1
    print(f'{a.project}: wrote {written} static mock tests ({kinds}) under {out_root}/src/test')

if __name__ == '__main__':
    main()
