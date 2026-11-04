#!/usr/bin/env python3
import argparse
import json
import os
import signal
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Union
from subprocess import CalledProcessError, TimeoutExpired

# ───────────────────────── helpers ──────────────────────────

def run(cmd: list[str], *, cwd: Path | None = None, env: dict | None = None) -> None:
    """
    Run `cmd` (a list of args) safely (no shell), echoing it and failing fast on error.
    """
    echo = " ".join(str(c) for c in cmd)
    print(f"+ {echo}" if cwd is None else f"+ (cd {cwd}) {echo}")
    subprocess.run(cmd, cwd=cwd, env=env, check=True)

def run_cmd(
    test_class: str,
    test_method: Union[str, Path],
    project: Path,
    *,
    timeout: int = 100,
    run_script: bool = False,
) -> None:
    """
    Launch Maven or our script via a small .sh wrapper, to reduce Python-side variability.
    """
    # always ensure we’re in project dir
    cwd = project

    if run_script:
        script_arg = Path(test_method).name
        cmd = [str(Path(__file__).parent / "run_script.sh"), script_arg]
    else:
        cmd = [
            str(Path(__file__).parent / "run_maven.sh"),
            test_class,
            str(test_method),
        ]
    
    print(f"Running command: {cmd}")

    # start_new_session creates a new process group
    quiet = (not run_script) and os.environ.get("MOCKGEN_QUIET", "1") == "1"   # surefire output of huge-array tests made shard logs tens of GB
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        start_new_session=True,
        stdin=subprocess.DEVNULL,  # we never need to send ENTER
        stdout=(subprocess.DEVNULL if quiet else None),
        stderr=(subprocess.DEVNULL if quiet else None),
    )

    try:
        proc.wait(timeout=timeout)
    except TimeoutExpired:
        # gentle termination
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except TimeoutExpired:
            # force‐kill
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
        _reap_group(proc.pid)
        raise

    # Maven can return while the surefire-forked test JVM is still alive (non-daemon threads of a test keep it running
    # after surefire stops waiting for it); such JVMs are reparented to init and keep their cores and heap for hours.
    _reap_group(proc.pid)

    if proc.returncode != 0:
        raise CalledProcessError(proc.returncode, cmd)


def _reap_group(pgid: int) -> None:
    """Kill whatever is left in the process group of a finished run (the wrapper, Maven and the forked test JVM share it)."""
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass   # nothing left, the normal case


def ensure_sdk(java_version: str = "8.0.432-kona") -> None:
    """
    Instead of sourcing in a subshell, just point PATH and JAVA_HOME at the SDKMAN candidate.
    """
    sdkman_dir = Path.home() / ".sdkman"
    java_candidate = sdkman_dir / "candidates" / "java" / java_version
    if not java_candidate.exists():
        sys.stderr.write(
            f"⚠️  Could not find SDKMAN java candidate at {java_candidate}\n"
            "   Is that version installed? Try `sdk list java` or install via https://sdkman.io/install\n"
        )
        sys.exit(1)

    os.environ["JAVA_HOME"] = str(java_candidate)
    os.environ["PATH"] = str(java_candidate / "bin") + os.pathsep + os.environ.get("PATH", "")

def copy_project_tree(project: str, workdir: str | None = None) -> None:
    """Re-create a fresh working copy of the Java project (optionally under a shard-specific directory name)."""
    src = Path("../../java_projects/cleaned_final_projects") / project
    dst = Path(workdir or project)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)

def save_state(project: str, executed_tests: dict, args) -> None:
    """Atomically write out our JSON state."""
    path = Path(f"{args.json_fname}") / f"{project}.json"
    with open(path, "w") as f:
        json.dump(executed_tests, f, indent=4)

STABILITY_RUNS = int(os.environ.get("MOCKINGBIRD_STABILITY_RUNS", "2"))

def drop_unstable(actual_class: str, test_method: str, project: Path, py_dir: Path, args) -> int:
    """Execute the test a second time and keep a mock test only when both runs recorded the same behavior (stability.py
    canonical form: memory addresses, identity hashes and enumeration order are ignored). Returns the number of mock tests
    dropped. When the second run produces no log at all the check is skipped."""
    sys.path.insert(0, str(Path(__file__).parent))
    from stability import normalize
    prefix = f"{actual_class.split('.')[-1]}_{test_method}_decomposed_mocker_"
    first = {q.name: q for q in py_dir.glob(f"src/**/{prefix}*.py")}
    if not first:
        return 0
    scratch = py_dir.parent / f"{py_dir.name}__stability"
    shutil.rmtree(scratch, ignore_errors=True)
    scratch.mkdir()
    for q in project.glob("*.log"):
        q.unlink()
    try:
        run_cmd(actual_class, test_method, project, timeout=args.timeout)
    except (TimeoutExpired, CalledProcessError):
        pass
    logs = list(project.glob("*.log"))
    if not logs:
        shutil.rmtree(scratch, ignore_errors=True)
        return 0
    for log_path in logs:
        shutil.copy(log_path, scratch)
        log_path.unlink()
    for helper in ("mock_helper.py", "log_parser.py", "script.py"):
        shutil.copy(helper, scratch)
    for log_file in scratch.glob("*.log"):
        try:
            run_cmd("", log_file, scratch, run_script=True, timeout=args.timeout)
        except (TimeoutExpired, CalledProcessError):
            pass
    second = {q.name: q for q in scratch.glob(f"src/**/{prefix}*.py")}
    dropped = 0
    for name, q in first.items():
        other = second.get(name)
        if other is None or normalize(q) != normalize(other):
            q.unlink()
            dropped += 1
    shutil.rmtree(scratch, ignore_errors=True)
    return dropped

# ───────────────────────── main workflow ──────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate mocks from AlphaTrans build logs (Python port)."
    )
    parser.add_argument("project", help="Project directory name")
    parser.add_argument("timeout", type=int, default=100, help="Timeout for each test method")
    parser.add_argument("json_fname", help="JSON file with executed tests")
    parser.add_argument("mock_evosuite", type=bool, default=False, help="Whether to mock evosuite tests")
    parser.add_argument("--shards", type=int, default=1, help="split the test classes of the project across N independent workers")
    parser.add_argument("--shard", type=int, default=0, help="index of this worker (0-based)")
    args = parser.parse_args()

    project = args.project
    # each shard works in its own copy of the project so maven runs do not interfere; shard 0 keeps the shared layout
    workdir = project if args.shards <= 1 else f"{project}__s{args.shard}"
    state_path = Path(f'{args.json_fname}') / f"{workdir}.json"

    # 1.  Activate the right Java once
    ensure_sdk("8.0.432-kona")

    # reset project
    copy_project_tree(project, workdir)

    # clean project and extract executed tests
    run(["python3", "clean_evosuite_tests.py", f"../../java_projects/cleaned_final_projects_evosuite/{project}", workdir])
    cleaned_base = Path("../../java_projects/cleaned_final_projects_evosuite_cleaned")
    cleaned_base.mkdir(parents=True, exist_ok=True)
    src_dir = Path(workdir)
    dst_dir = cleaned_base / project
    shutil.copy("modify_pom.py", src_dir)
    run(["python3", "modify_pom.py"], cwd=src_dir)
    shutil.copy("remove_benchmark.py", src_dir)
    run(["python3", "remove_benchmark.py"], cwd=src_dir)
    if args.shard == 0:
        if dst_dir.exists():
            shutil.rmtree(dst_dir)
        shutil.copytree(src_dir, dst_dir)
    quiet_build = os.environ.get("MOCKGEN_QUIET", "1") == "1"   # the full-suite build only needs to produce surefire reports; a looping test printed 84 GB here
    subprocess.run(["mvn", "clean", "install", "-Drat.skip", "-Dgpg.skip", "-Dmoditect.skip", "-Dcheckstyle.skip", "-Dmaven.javadoc.skip"], cwd=src_dir, check=False,
                   stdout=(subprocess.DEVNULL if quiet_build else None), stderr=(subprocess.DEVNULL if quiet_build else None))
    prev_state = json.loads(state_path.read_text()) if (state_path.exists() and os.environ.get("MOCKINGBIRD_RESUME", "1") == "1") else {}
    run(["python3", "extract_executed_tests.py", str(src_dir)])
    executed_tests = json.loads(state_path.read_text())
    if args.shards > 1:
        # deterministic split of test classes across shards
        selected = sorted(executed_tests.keys())[args.shard::args.shards]
        executed_tests = {k: executed_tests[k] for k in selected}
    if prev_state:
        # resume an interrupted run: carry over per-test flags; a test flagged mocked whose mock tests are absent on disk
        # (e.g. the run died with a full disk) is queued again
        py_dir_prev = Path(f"{project}-python" if args.shards <= 1 else f"{project}-python__s{args.shard}")
        merged_prev = Path("../../data/mock_tests") / project   # where generate_mock_tests*.sh merge the shard outputs
        carried = requeued = 0
        for cls, methods in prev_state.items():
            if cls not in executed_tests or not isinstance(methods, dict): continue
            parts = cls.split("."); short = parts[-1][4:] + "Test" if parts[-1].startswith("Test") else parts[-1]
            for m, info in methods.items():
                if m not in executed_tests[cls] or not isinstance(info, dict): continue
                if info.get("mocked") and not any(py_dir_prev.glob(f"src/**/{short}_{m}_decomposed_mocker_*.py")) \
                        and not any(merged_prev.glob(f"src/**/{short}_{m}_decomposed_mocker_*.py")):
                    requeued += 1; continue
                if info.get("timeout") and not info.get("mocked") and (info.get("mock_duration") or 0) < 60:
                    requeued += 1; continue   # failed within a minute: a build or harness error, not a real timeout
                for k in ("mocked", "timeout", "mock_duration", "unstable_dropped", "oversized_log", "oversized_dropped"):
                    if k in info: executed_tests[cls][m][k] = info[k]
                carried += 1
        print(f"[resume] carried {carried} test records from the previous state, re-queued {requeued} without mock files")
    # tests without a record in this shard's state (e.g. the shard count changed between passes) whose mock tests already
    # sit in the merged directory were generated by an earlier pass: record them as done instead of running them again
    merged_prev = Path("../../data/mock_tests") / project
    if merged_prev.is_dir():
        adopted = 0
        for cls, methods in executed_tests.items():
            if not isinstance(methods, dict): continue
            parts = cls.split("."); short = parts[-1][4:] + "Test" if parts[-1].startswith("Test") else parts[-1]
            for m, info in methods.items():
                if isinstance(info, dict) and not info.get("mocked") and not info.get("timeout") \
                        and any(merged_prev.glob(f"src/**/{short}_{m}_decomposed_mocker_*.py")):
                    info["mocked"] = True; info.setdefault("mock_duration", 0); info["adopted"] = True; adopted += 1
        if adopted: print(f"[resume] adopted {adopted} tests whose mock tests already exist in {merged_prev}")
    save_state(workdir, executed_tests, args)
    
    # inject our patchers
    for helper in ("modify_pom.py", "add_java_files.py"):
        shutil.copy(helper, workdir)

    run(["python3", "add_java_files.py"], cwd=Path(workdir))

    # rebuild once with the logging aspect and the serializer in place; the per-test runs below only execute the test phase
    # on this woven build (a full clean+install per test method is what made log generation so slow)
    subprocess.run(["mvn", "-q", "clean", "test-compile", "-Drat.skip", "-Dgpg.skip", "-Dmoditect.skip", "-Dcheckstyle.skip", "-Dmaven.javadoc.skip"], cwd=Path(workdir), check=False)

    # clean out any stale logs
    for p in Path(workdir).glob("*.log"):
        p.unlink()

    py_dir = Path(f"{project}-python" if args.shards <= 1 else f"{project}-python__s{args.shard}")
    project = workdir   # all per-test work below happens in this shard's copy

    # For each test class, we start from a _fresh_ workspace:
    for test_class, methods in executed_tests.items():

        # now run each test method
        for test_method, info in methods.items():

            # ensure keys
            info.setdefault("mocked", False)
            info.setdefault("timeout", False)
            info.setdefault("mock_duration", None)

            # skip already-done or timed-out
            if info["mocked"] or info["timeout"]:
                continue

            start = time.time()
            # fix up class name if it ends with "Test…"
            parts = test_class.split(".")
            if parts[-1].startswith("Test"):
                parts[-1] = parts[-1][4:] + "Test"
            actual_class = ".".join(parts)

            try:
                run_cmd(actual_class, test_method, Path(project), timeout=args.timeout)
            except subprocess.TimeoutExpired:
                info["timeout"] = True
                info["mock_duration"] = time.time() - start
                save_state(project, executed_tests, args)
                for p in Path(project).glob("*.log"):
                    p.unlink()
                continue
            except subprocess.CalledProcessError:
                # build failure—mark as timeout so we don't retry endlessly
                info["timeout"] = True
                info["mock_duration"] = time.time() - start
                save_state(project, executed_tests, args)
                for p in Path(project).glob("*.log"):
                    p.unlink()
                continue

            if not list(Path(project).glob("*.log")):
                # surefire runs nothing for `Class#method` when the method is inherited from an abstract test base class;
                # a class-level run still produces one log file per test method, so run the class once and keep every log
                try:
                    run_cmd(actual_class, "", Path(project), timeout=2 * args.timeout)
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                    pass

            # 5b. cap: an aspect log above MAX_LOG_MB (default 2048) cannot yield a usable mock test and fills the disk
            max_log_mb = float(os.environ.get("MAX_LOG_MB", "2048"))
            for log_path in Path(project).glob("*.log"):
                if log_path.stat().st_size > max_log_mb * 1e6:
                    log_path.unlink(); info["oversized_log"] = int(info.get("oversized_log") or 0) + 1
                    print(f"[log cap] dropped {log_path.name}: above {max_log_mb:.0f} MB")

            # 6. Collect any new .log files into our python dir
            py_dir.mkdir(exist_ok=True)
            for log_path in Path(project).glob(f"*.log"):
                shutil.copy(log_path, py_dir)

            # 7. Copy over mock helpers
            for helper in ("mock_helper.py", "log_parser.py", "script.py"):
                shutil.copy(helper, py_dir)

            # 8. Generate mocks from each log
            for log_file in py_dir.glob(f"*.log"):
                try:
                    run_cmd("", log_file, py_dir, run_script=True, timeout=args.timeout)
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                    pass

            # 8b. a mock test whose recorded payload is tens of megabytes (huge arrays) cannot be validated meaningfully and
            #     only slows pytest: drop it (env MAX_MOCK_TEST_MB, default 10; MOCKINGBIRD_KEEP_OVERSIZED=1 sets it aside
            #     under <py_dir>__oversized instead, which costs disk and is never read by the pipeline)
            max_mb = float(os.environ.get("MAX_MOCK_TEST_MB", "10")); keep_oversized = os.environ.get("MOCKINGBIRD_KEEP_OVERSIZED", "0") == "1"
            for t in py_dir.glob("src/**/*_mocker_*.py"):
                if t.stat().st_size > max_mb * 1e6:
                    info["oversized_dropped"] = int(info.get("oversized_dropped") or 0) + 1
                    if keep_oversized:
                        aside = py_dir.parent / f"{py_dir.name}__oversized" / t.relative_to(py_dir)
                        aside.parent.mkdir(parents=True, exist_ok=True); shutil.move(str(t), str(aside))
                    else:
                        t.unlink()

            # 8c. Java-side stability: a generated (EvoSuite) test is executed a second time and each of its mock tests is
            #     kept only when both runs recorded the same behavior (env MOCKINGBIRD_STABILITY_RUNS, default 2)
            if STABILITY_RUNS >= 2 and actual_class.endswith("_ESTest"):
                info["unstable_dropped"] = drop_unstable(actual_class, test_method, Path(project), py_dir, args)

            # 9. Clean up logs everywhere
            for p in py_dir.glob("*.log"):
                p.unlink()
            for p in Path(project).glob("*.log"):
                p.unlink()

            info["mocked"] = True
            info["mock_duration"] = time.time() - start
            save_state(project, executed_tests, args)

if __name__ == "__main__":
    main()
