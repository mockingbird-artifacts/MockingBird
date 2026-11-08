#!/usr/bin/env bash
# scripts/run_coverage_comparison.sh
#
# Reports JaCoCo line, branch, and method coverage for each of the 10 Java
# projects in this repo, comparing the without-Evosuite variant
# (java_projects/cleaned_final_projects/) against the with-Evosuite variant
# (java_projects/cleaned_final_projects_evosuite/).
#
# Both variants are built and tested under the SAME JDK (OpenJDK 11). JaCoCo
# measures bytecode; mixing JDK 8 and JDK 11 produces a few units of
# LineNumberTable drift that isn't a real source difference. JDK 11 is the
# choice because (a) Evosuite *_ESTest.java sources call Writer.nullWriter(),
# a Java 11+ API, so JDK 8 cannot compile them; (b) jansi's spotless-maven-
# plugin v2.38.0 was compiled for JDK 11 and cannot load on JDK 8.
#
# The with-Evosuite variant has multiple latent pom/source bugs that silently
# skip tests, evade coverage instrumentation, or crash the JVM mid-run if not
# patched. The script applies all five fixes in place at the start of each
# with-Evosuite run and restores the working tree with 'git checkout -- .'
# after the run, so the on-disk repo is never permanently mutated.
#
# Fix 1 (surefire-junit4 force-binding). The with-Evosuite poms for
#   commons-csv, commons-exec, commons-pool, and jansi pin the surefire-junit4
#   provider so the JUnit-4-styled Evosuite tests run. That provider only
#   discovers JUnit 4 classes; these projects' original tests use JUnit 5
#   (org.junit.jupiter.api.Test) and were silently dropped. We strip the
#   <dependencies> block; surefire 3.0.0-M5 then auto-detects both engines.
#
# Fix 2 (junit-vintage-engine injection). Once Fix 1 lifts the junit4 pin,
#   the JUnit Platform's Jupiter engine runs the originals but ignores
#   Evosuite's @RunWith(EvoRunner.class) tests (JUnit 4 vintage syntax). We
#   inject junit-vintage-engine:5.8.2 and junit:junit:4.13.2 as test deps;
#   the 4.13.2 pin is needed because commons-graph transitively pulls
#   junit:4.10 which Vintage rejects as unsupported.
#
# Fix 3 ('$' in *_ESTest.java filenames and class declarations). Evosuite
#   generates inner-class tests with literal '$' in the filename and class
#   name (e.g. FileUploadBase$SizeException_ESTest.java declaring class
#   FileUploadBase$SizeException_ESTest). This compiles ('$' is a legal
#   identifier character per JLS 3.8), but Class.forName(name) tries to
#   resolve such names as 'outer$inner', fails, and surefire silently skips
#   them. We rename every '*$*_ESTest*.java' file to '*_*_ESTest*.java' and
#   rewrite the class/extends declarations to match.
#
# Fix 4 (@EvoRunnerParameters(separateClassLoader = true)). Many _ESTest
#   files set this flag, which makes the Evosuite runner load the
#   class-under-test in a fresh, isolated classloader. JaCoCo's bytecode
#   agent attaches to the JVM's system classloader and never sees the
#   uninstrumented copy loaded by Evosuite's isolated loader; the tests
#   succeed but no coverage is recorded for the class-under-test. We
#   rewrite 'separateClassLoader = true' to 'separateClassLoader = false'
#   across all *_ESTest.java files.
#
# Fix 5 (<reuseForks>true</reuseForks>). jansi ships a CLibrary-backed
#   *_ESTest that triggers a SIGABRT in the test JVM. With reuseForks=true,
#   the single JVM crash skips the JaCoCo agent's shutdown hook, leaving
#   jacoco.exec at 0 bytes -- the entire project then reports 0% coverage.
#   We rewrite the surefire config to reuseForks=false so each test class
#   forks its own JVM and only the crashing class's coverage is lost.
#
# Usage: scripts/run_coverage_comparison.sh [path/to/repo/root]
# Output: tab-separated table on stdout with line/branch/method cov%;
#         JaCoCo CSVs preserved per project at target/site/jacoco/jacoco.csv.

set -uo pipefail

ROOT="${1:-$(pwd)}"
PROJECTS=(
  JavaFastPFOR
  commons-cli
  commons-codec
  commons-csv
  commons-exec
  commons-fileupload
  commons-graph
  commons-pool
  commons-validator
  jansi
)
VARIANTS=(cleaned_final_projects cleaned_final_projects_evosuite)
if [[ -n "${PROJECTS_OVERRIDE:-}" ]]; then PROJECTS=($PROJECTS_OVERRIDE); fi
if [[ -n "${VARIANTS_OVERRIDE:-}" ]]; then VARIANTS=($VARIANTS_OVERRIDE); fi
JDK_HOME="/usr/lib/jvm/java-11-openjdk-amd64"

MVN_FLAGS=(
  -Drat.skip=true
  -Dgpg.skip=true
  -Dmoditect.skip=true
  -Dcheckstyle.skip=true
  -Dmaven.javadoc.skip=true
  -Dmaven.test.failure.ignore=true
  -DfailIfNoTests=false
  -Dspotless.apply.skip=true
  -Dspotless.check.skip=true
  -Dspotbugs.skip=true
  -Denforcer.skip=true
  -DreuseForks=false
)

patch_pom_reuse_forks_false() {
  local pom="$1"
  python3 - "$pom" <<'PY'
import sys, re
path = sys.argv[1]
src = open(path).read()
new = re.sub(r'<reuseForks>\s*true\s*</reuseForks>', '<reuseForks>false</reuseForks>', src)
if new != src:
    open(path, 'w').write(new)
PY
}

patch_pom_remove_junit4_force() {
  local pom="$1"
  python3 - "$pom" <<'PY'
import re, sys
path = sys.argv[1]
src = open(path).read()
new = re.sub(
    r'(<artifactId>maven-surefire-plugin</artifactId>.*?</configuration>)\s*<dependencies>.*?</dependencies>',
    r'\1', src, count=1, flags=re.DOTALL,
)
if new != src:
    open(path, 'w').write(new)
# Inject junit-vintage-engine as a test dep so the JUnit Platform discovers
# Evosuite's @RunWith(EvoRunner.class) tests when originals are JUnit 5.
src2 = open(path).read()
if 'junit-vintage-engine' not in src2:
    import re as _re
    m = _re.search(r'(<dependencies>)(.*?)(</dependencies>)', src2, flags=_re.DOTALL)
    if m:
        dep = ('    <dependency>\n'
               '      <groupId>org.junit.vintage</groupId>\n'
               '      <artifactId>junit-vintage-engine</artifactId>\n'
               '      <version>5.8.2</version>\n'
               '      <scope>test</scope>\n'
               '    </dependency>\n'
               '    <dependency>\n'
               '      <groupId>junit</groupId>\n'
               '      <artifactId>junit</artifactId>\n'
               '      <version>4.13.2</version>\n'
               '      <scope>test</scope>\n'
               '    </dependency>\n')
        out = src2[:m.end(2)] + dep + src2[m.end(2):]
        open(path, 'w').write(out)
PY
}

restore_pom() {
  local pom="$1"
  if [[ -f "${pom}.bak" ]]; then mv "${pom}.bak" "$pom"; fi
}

patch_dollar_named_estests() {
  local dir="$1"; local variant="$2"; local project="$3"
  local log="/tmp/altp_dollar_rename.${variant}_${project}.log"
  : > "$log"
  python3 - "$dir" "$log" <<'PY'
import os, re, sys
test_root = os.path.join(sys.argv[1], "src", "test", "java")
log_path = sys.argv[2]
if not os.path.isdir(test_root): sys.exit(0)
renames = []
for dirpath, _, files in os.walk(test_root):
    for f in files:
        if "_ESTest" in f and "$" in f and f.endswith(".java"):
            old = os.path.join(dirpath, f)
            new = os.path.join(dirpath, f.replace("$", "_"))
            src = open(old).read()
            patched = re.sub(
                r'\b[A-Za-z_][A-Za-z0-9_]*(?:\$[A-Za-z_][A-Za-z0-9_]*)+_ESTest(?:_scaffolding)?\b',
                lambda m: m.group(0).replace("$", "_"), src)
            open(new, "w").write(patched)
            os.remove(old)
            renames.append((old, new))
with open(log_path, "w") as fp:
    for old, new in renames:
        fp.write(f"{old}\t{new}\n")
PY
}

restore_dollar_named_estests() {
  local variant="$1"; local project="$2"
  local log="/tmp/altp_dollar_rename.${variant}_${project}.log"
  if [[ ! -s "$log" ]]; then return; fi
  python3 - "$log" <<'PY'
import os, sys
for line in open(sys.argv[1]):
    old, new = line.rstrip("\n").split("\t")
    if os.path.exists(new): os.remove(new)
PY
  rm -f "$log"
}

# Replace `separateClassLoader = true` with `separateClassLoader = false`
# in every *_ESTest.java file. JaCoCo cannot instrument code loaded by
# Evosuite's isolated classloader, so the flag must be off for coverage
# measurement. A backup of the original file is kept as .bak for restore.
patch_separate_classloader() {
  local dir="$1"; local variant="$2"; local project="$3"
  local log="/tmp/altp_sepcl_patch.${variant}_${project}.log"
  : > "$log"
  python3 - "$dir" "$log" <<'PY'
import os, sys, shutil
test_root = os.path.join(sys.argv[1], "src", "test", "java")
log_path = sys.argv[2]
if not os.path.isdir(test_root): sys.exit(0)
touched = []
for dirpath, _, files in os.walk(test_root):
    for f in files:
        if f.endswith(".java"):
            p = os.path.join(dirpath, f)
            src = open(p).read()
            new = src.replace("separateClassLoader = true", "separateClassLoader = false")
            if new != src:
                shutil.copy(p, p + ".bak")
                open(p, "w").write(new)
                touched.append(p)
with open(log_path, "w") as fp:
    for p in touched:
        fp.write(p + "\n")
PY
}

restore_separate_classloader() {
  local variant="$1"; local project="$2"
  local log="/tmp/altp_sepcl_patch.${variant}_${project}.log"
  if [[ ! -s "$log" ]]; then return; fi
  while IFS= read -r p; do
    if [[ -f "${p}.bak" ]]; then mv "${p}.bak" "$p"; fi
  done < "$log"
  rm -f "$log"
}

parse_csv() {
  local csv="$1"
  if [[ ! -s "$csv" ]]; then echo "NA NA NA NA NA NA NA NA NA"; return; fi
  awk -F, 'NR>1 {bm+=$6; bc+=$7; lm+=$8; lc+=$9; mm+=$12; mc+=$13}
  END {
    btot=bm+bc; ltot=lm+lc; mtot=mm+mc
    lp = (ltot==0) ? 0 : (lc/ltot)*100
    bp = (btot==0) ? 0 : (bc/btot)*100
    mp = (mtot==0) ? 0 : (mc/mtot)*100
    printf "%d %d %d %d %d %d %.2f %.2f %.2f\n", lc, ltot, bc, btot, mc, mtot, lp, bp, mp
  }' "$csv"
}

restore_via_git() {
  local dir="$1"
  (cd "$dir" && git checkout -- . >/dev/null 2>&1 && git clean -fd src pom.xml >/dev/null 2>&1) || true
}

run_one() {
  local variant="$1"; local project="$2"
  local dir="$ROOT/java_projects/$variant/$project"
  if [[ ! -d "$dir" ]]; then echo "[$variant/$project] MISSING DIR"; return; fi
  local patched=0
  if [[ "$variant" == "cleaned_final_projects_evosuite" ]]; then
    patch_pom_remove_junit4_force "$dir/pom.xml"
    patch_pom_reuse_forks_false "$dir/pom.xml"
    patch_dollar_named_estests "$dir" "$variant" "$project"
    patch_separate_classloader "$dir" "$variant" "$project"
    patched=1
  fi
  echo "[$variant/$project] mvn clean test jacoco:report under jdk11 ..." >&2
  (
    cd "$dir" || exit 1
    JAVA_HOME="$JDK_HOME" PATH="$JDK_HOME/bin:$PATH" \
      mvn clean test jacoco:report "${MVN_FLAGS[@]}" \
      > /tmp/mvn_${variant}_${project}.log 2>&1
  )
  local csv="$dir/target/site/jacoco/jacoco.csv"
  local parsed; parsed=$(parse_csv "$csv")
  if [[ "$patched" == "1" ]]; then
    restore_via_git "$dir"
  fi
  echo "$variant $project $parsed"
}

printf '%-35s %-20s %-9s %-9s %-9s %-9s %-9s %-9s %-9s %-9s %-9s\n' \
  variant project line_cov line_tot br_cov br_tot meth_cov meth_tot line% br% meth%
printf '%-35s %-20s %-9s %-9s %-9s %-9s %-9s %-9s %-9s %-9s %-9s\n' \
  '-------' '-------' '---' '---' '---' '---' '---' '---' '---' '---' '---'

for variant in "${VARIANTS[@]}"; do
  for project in "${PROJECTS[@]}"; do
    parsed=$(run_one "$variant" "$project")
    read -r v p lc ltot bc btot mc mtot lp bp mp <<<"$parsed"
    printf '%-35s %-20s %-9s %-9s %-9s %-9s %-9s %-9s %-9s %-9s %-9s\n' \
      "$v" "$p" "$lc" "$ltot" "$bc" "$btot" "$mc" "$mtot" "$lp" "$bp" "$mp"
  done
done
