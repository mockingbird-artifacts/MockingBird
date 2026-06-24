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
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        start_new_session=True,
        stdin=subprocess.DEVNULL,  # we never need to send ENTER
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
        raise

    if proc.returncode != 0:
        raise CalledProcessError(proc.returncode, cmd)


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

def copy_project_tree(project: str) -> None:
    """Re-create a fresh working copy of the Java project."""
    src = Path("../../java_projects/cleaned_final_projects") / project
    dst = Path(project)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)

def save_state(project: str, executed_tests: dict, args) -> None:
    """Atomically write out our JSON state."""
    path = Path(f"{args.json_fname}") / f"{project}.json"
    with open(path, "w") as f:
        json.dump(executed_tests, f, indent=4)

# ───────────────────────── main workflow ──────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate mocks from AlphaTrans build logs (Python port)."
    )
    parser.add_argument("project", help="Project directory name")
    parser.add_argument("timeout", type=int, default=100, help="Timeout for each test method")
    parser.add_argument("json_fname", help="JSON file with executed tests")
    #parser.add_argument("mock_evosuite", type=bool, default=False, help="Whether to mock evosuite tests")
    args = parser.parse_args()

    project = args.project
    state_path = Path(f'{args.json_fname}') / f"{project}.json"

    # 1.  Activate the right Java once
    ensure_sdk("8.0.432-kona")

    # reset project
    copy_project_tree(project)

    # clean project and extract executed tests
    #run(["python3", "clean_evosuite_tests.py", f"../../java_projects/cleaned_final_projects_evosuite/{project}", project])
    cleaned_base = Path("../../java_projects/cleaned_final_projects_no_evosuite_cleaned")
    cleaned_base.mkdir(parents=True, exist_ok=True)
    src_dir = Path(project)
    dst_dir = cleaned_base / project
    if dst_dir.exists():
        shutil.rmtree(dst_dir)
    shutil.copy("modify_pom.py", src_dir)
    run(["python3", "modify_pom.py"], cwd=src_dir)
    shutil.copy("remove_benchmark.py", src_dir)
    run(["python3", "remove_benchmark.py"], cwd=src_dir)
    shutil.copytree(src_dir, dst_dir)
    subprocess.run(["mvn", "clean", "install", "-Drat.skip", "-Dgpg.skip", "-Dmoditect.skip", "-Dcheckstyle.skip", "-Dmaven.javadoc.skip"], cwd=src_dir, check=False)
    run(["python3", "extract_executed_tests.py", src_dir])
    executed_tests = json.loads(state_path.read_text())
    
    # inject our patchers
    for helper in ("modify_pom.py", "add_java_files.py"):
        shutil.copy(helper, project)

    run(["python3", "add_java_files.py"], cwd=Path(project))

    # clean out any stale logs
    for p in Path(project).glob("*.log"):
        p.unlink()

    py_dir = Path(f"{project}-python")

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
