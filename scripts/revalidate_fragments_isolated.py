"""One-shot mock re-validation of every attempted main method under isolated
per-fragment recompose semantics (the target fragment real, siblings stubbed).

Usage: python3 scripts/revalidate_fragments_isolated.py <project> <model> [temperature]
Env:   MOCKINGBIRD_NO_ES_TESTS=1   exclude EvoSuite-generated tests (w/o-ES arm)
       MOCKINGBIRD_VALIDATION_WORKERS=N   cap the validation process pool
       RESWEEP_SKIP=N   skip the first N fragments (resume support)
"""
import os, sys, argparse, time

sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), "src/translation"))
from mock_validation import validate, get_processed_fragments, clean_up
from get_reverse_traversal import get_reverse_traversal

P = sys.argv[1]
M = sys.argv[2]
T = sys.argv[3] if len(sys.argv) > 3 else "0.0"
args = argparse.Namespace(model_name=M, project_name=P, from_lang="Java", to_lang="Python",
                          validate_by_graal=False, debug=False, validate_by_mocking=True,
                          temperature=float(T), suffix="_evosuite_cleaned", recursion_depth=1,
                          schemas_dir=f"data/schemas_evosuite_cleaned/{M}/{T}/{P}")
os.environ["MOCKINGBIRD_PROJECT"] = P
traversal = get_reverse_traversal(args)
frags = get_processed_fragments(traversal, args)
main_frags = [f for f in frags if "src.main" in f["schema_name"] and not f["is_test_method"]
              and f.get("fragment_type") == "method"]   # fields have no mock tests; validating them
                                                        # only stamps metadata the isolated recompose keys on
SKIP = int(os.environ.get("RESWEEP_SKIP", "0"))
main_frags = main_frags[SKIP:]
print(f"{P}: {len(main_frags)} main fragments to validate in isolation (skipped first {SKIP})", flush=True)
t0 = time.time()
for i, fragment in enumerate(main_frags):
    rc = os.system(f"python3 src/postprocessing/recompose.py --project_name={P} --model_name={M} "
                   f"--output_dir=data/recomposed_projects --temperature={T} "
                   f"--fragment_name='{fragment['fragment_name']}' --suffix=_evosuite_cleaned "
                   f">> logs/revalidate_recompose_{P}.log 2>&1")
    if rc != 0:
        print(f"  recompose rc={rc} for {fragment['fragment_name']}", flush=True)
        continue
    src_res = f"java_projects/cleaned_final_projects_evosuite/{P}/src/test/resources"
    dst = f"data/recomposed_projects/{M}/{T}/{P}/src/test"
    if os.path.isdir(src_res):
        os.makedirs(dst, exist_ok=True)
        os.system(f"cp -r {src_res} {dst}/ 2>/dev/null")
    validate(fragment, args, budget={"mocking": 1}, recursion_depth=1)
    clean_up(args)
    if (i + 1) % 25 == 0:
        print(f"  {P} {i+1}/{len(main_frags)} elapsed {int(time.time()-t0)}s", flush=True)
print(f"{P} ISOLATED VALIDATION DONE in {int(time.time()-t0)}s", flush=True)
