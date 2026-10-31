#!/usr/bin/env python3
"""Rename freshly generated EvoSuite tests X_ESTest -> XES2_ESTest (the logging aspect only recognises test classes whose
name ends in Test, and the archive already has X_ESTest), drop the ones that do not compile against the project, and place
the raw files (with scaffolding) under java_projects/cleaned_final_projects_evosuite/<P>/src/test/java so that
generate_mock_tests.sh cleans, builds and runs them like the original EvoSuite tests.
usage: evosuite_place_tests.py <evosuite out dir> <raw evosuite project dir> <classpath file>"""
import os, re, shutil, subprocess, sys, tempfile
src, dest_proj, cp_file = sys.argv[1], sys.argv[2], sys.argv[3]; dest = os.path.join(dest_proj, "src/test/java")
cp = open(cp_file).read().strip(); tmp = tempfile.mkdtemp(); files = []
for dp, _, fs in os.walk(src):
    for f in fs:
        if not f.endswith(".java"): continue
        txt = open(os.path.join(dp, f), errors="ignore").read()
        txt = re.sub(r"\b(\w+)_ESTest_scaffolding\b", r"\1ES2_ESTest_scaffolding", txt); txt = re.sub(r"\b(\w+)_ESTest\b", r"\1ES2_ESTest", txt)
        nf = f.replace("_ESTest_scaffolding", "ES2_ESTest_scaffolding").replace("_ESTest.java", "ES2_ESTest.java"); rel = os.path.relpath(dp, src)
        os.makedirs(os.path.join(tmp, rel), exist_ok=True); open(os.path.join(tmp, rel, nf), "w").write(txt); files.append(os.path.join(rel, nf))
# compile check (raw files need the EvoSuite runtime for the scaffolding)
runtime = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "misc", "evosuite-standalone-runtime-1.2.0.jar")
tests = [f for f in files if not f.endswith("_scaffolding.java")]; kept = 0
for t in tests:
    sc = t.replace("ES2_ESTest.java", "ES2_ESTest_scaffolding.java"); srcs = [os.path.join(tmp, t)] + ([os.path.join(tmp, sc)] if os.path.exists(os.path.join(tmp, sc)) else [])
    r = subprocess.run(["javac", "-nowarn", "-d", tempfile.mkdtemp(), "-cp", cp + os.pathsep + runtime] + srcs, capture_output=True, text=True)
    if r.returncode != 0: print(f"  dropped (does not compile): {t}"); continue
    for s in srcs: tgt = os.path.join(dest, os.path.relpath(s, tmp)); os.makedirs(os.path.dirname(tgt), exist_ok=True); shutil.copy(s, tgt)
    kept += 1
print(f"[evosuite_place_tests] {kept}/{len(tests)} generated test classes placed under {dest}")
