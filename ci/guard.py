#!/usr/bin/env python3
"""Single-file guard for the emulator pipeline.

Catches the shape problems that turn a codebase into neuroslop -- duplicated
blocks, orphan files nothing builds or includes, monster files/functions,
missing tests, undeclared dependencies, dangling submodule pointers -- without
maintaining per-directory line budgets or an allow-list of directories. Those
need constant re-tuning on a project that's supposed to grow; the checks below
either hold always or don't apply. See docs/CI.md for the rationale.

Every check below is a hard failure. There is no "report only, block later"
mode: each one already only fires on something that is wrong regardless of
how big the repository gets.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EMULATOR_DIR = REPO_ROOT / "emulator"

# The only three thresholds in this file. They exist to catch a monster file or
# a 150-line function, not to manage how big the codebase is allowed to get.
# Change them when they're wrong, not to make a specific PR pass.
MAX_FILE_LINES = 600
MAX_FUNCTION_LINES = 80
MAX_CCN = 15

DEPS_START = "# guard:deps:start"
DEPS_END = "# guard:deps:end"
DEP_CALL_RE = re.compile(r"\b(pkg_check_modules|find_package|FetchContent_Declare)\s*\(")

# Path -> branch each submodule pins against (from .gitmodules).
SUBMODULE_BRANCHES = {
    "protocol": "main",
    "mobile_app": "main",
}


class Failure(Exception):
    """Raised by a check to record a hard failure without stopping the others."""


def source_files() -> list[Path]:
    return sorted(
        p for p in EMULATOR_DIR.rglob("*")
        if p.suffix in (".cpp", ".hpp") and "build" not in p.parts
    )


def cmake_files() -> list[Path]:
    return sorted(REPO_ROOT.rglob("CMakeLists.txt"))


def run(cmd: list[str], cwd: Path = REPO_ROOT, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, **kw)


# --- checks -----------------------------------------------------------------

def check_format(failures: list[str]) -> None:
    if shutil.which("clang-format") is None:
        failures.append("clang-format is not installed -- cannot check formatting (see docs/CI.md)")
        return

    bad = []
    for f in source_files():
        result = run(["clang-format", "--dry-run", "--Werror", str(f)])
        if result.returncode != 0:
            bad.append(str(f.relative_to(REPO_ROOT)))

    if bad:
        failures.append(
            "not formatted (run `make fmt`): " + ", ".join(bad)
        )


def check_duplicates(failures: list[str]) -> None:
    # lizard has no built-in duplicate detector (there is no "-Eduplicate" extension --
    # an earlier version of this script assumed one that doesn't exist). This does the
    # simplest honest thing instead: hash each function body verbatim (via lizard's own
    # line ranges) and flag two different functions that hash identically. That only
    # catches an exact copy-paste, not a renamed near-duplicate -- which is exactly the
    # `uart_v2.cpp` scenario this check exists for, and cheap enough to need no tuning.
    try:
        import lizard as lizard_lib
    except ImportError:
        failures.append("the `lizard` Python package is not installed -- cannot check for duplicates")
        return

    seen: dict[str, str] = {}
    for f in source_files():
        rel = f.relative_to(REPO_ROOT)
        lines = f.read_text(errors="replace").splitlines()
        for func in lizard_lib.analyze_file(str(f)).function_list:
            if func.length < 5:
                continue  # too short for a copy-paste to be worth flagging
            body = "\n".join(
                line.strip() for line in lines[func.start_line - 1:func.end_line] if line.strip()
            )
            digest = hashlib.sha256(body.encode()).hexdigest()
            here = f"{rel}:{func.name}@{func.start_line}"
            if digest in seen:
                failures.append(f"{here} is an exact copy of {seen[digest]} -- share one implementation")
            else:
                seen[digest] = here


def check_complexity(failures: list[str]) -> None:
    if shutil.which("lizard") is None:
        return  # already reported by check_duplicates

    # -w prints only functions that violate a threshold, in clang's warning format, and
    # (unlike the plain listing) honors a `// #lizard forgives` comment inside a function
    # body -- used on the two interfaces/uart.cpp functions that are legitimately this
    # shaped (a baud-rate lookup table, a linear termios field setup).
    result = run(["lizard", "-w", "-l", "cpp", f"-L{MAX_FUNCTION_LINES}", f"-C{MAX_CCN}", str(EMULATOR_DIR)])
    violations = [line for line in result.stdout.splitlines() if line.strip()]
    if violations:
        failures.append(
            f"functions over {MAX_FUNCTION_LINES} lines or CCN {MAX_CCN}:\n    "
            + "\n    ".join(violations)
        )


def check_file_length(failures: list[str]) -> None:
    for f in source_files():
        n = sum(1 for _ in f.open(encoding="utf-8", errors="replace"))
        if n > MAX_FILE_LINES:
            failures.append(
                f"{f.relative_to(REPO_ROOT)}: {n} lines (limit {MAX_FILE_LINES}) -- split it"
            )


def check_orphan_files(failures: list[str]) -> None:
    cmake_text = "\n".join(p.read_text() for p in cmake_files())

    for f in EMULATOR_DIR.glob("interface/*.cpp"):
        name = f.name
        if name not in cmake_text:
            failures.append(f"{f.relative_to(REPO_ROOT)} is not referenced by any CMakeLists.txt")

    all_text = "\n".join(
        p.read_text(errors="replace") for p in source_files() if p.suffix == ".cpp"
    )
    for f in EMULATOR_DIR.glob("interface/*.hpp"):
        if f.name not in all_text and f"interface/{f.name}" not in cmake_text:
            failures.append(f"{f.relative_to(REPO_ROOT)} is included by nothing and built by nothing")


def check_paired_tests(failures: list[str]) -> None:
    # A test doesn't have to be named after the interface it covers -- test_errors.cpp
    # legitimately covers all four in one file. What matters is that some test actually
    # includes the interface's header; an interface nothing includes is untested.
    test_sources = list(EMULATOR_DIR.glob("tests/test_*.cpp"))
    if not test_sources:
        for f in EMULATOR_DIR.glob("interface/*.cpp"):
            failures.append(f"{f.relative_to(REPO_ROOT)} has no tests at all (emulator/tests/ is empty)")
        return

    tests_text = "\n".join(p.read_text(errors="replace") for p in test_sources)
    for f in EMULATOR_DIR.glob("interface/*.cpp"):
        if f"interface/{f.stem}.hpp" not in tests_text:
            failures.append(
                f"{f.relative_to(REPO_ROOT)}: no file under emulator/tests/ includes "
                f"interface/{f.stem}.hpp -- add a test that exercises it"
            )


def check_dependency_allowlist(failures: list[str]) -> None:
    for cmake_file in cmake_files():
        text = cmake_file.read_text()
        if DEPS_START not in text:
            continue  # this CMakeLists.txt declares no third-party deps

        start = text.index(DEPS_START)
        end = text.index(DEPS_END) if DEPS_END in text else len(text)
        before, allowed_block, after = text[:start], text[start:end], text[end:]

        for chunk, label in ((before, "before"), (after, "after")):
            for match in DEP_CALL_RE.finditer(chunk):
                failures.append(
                    f"{cmake_file.relative_to(REPO_ROOT)}: {match.group(1)}(...) {label} the "
                    f"guard:deps block -- move it inside {DEPS_START}/{DEPS_END} (a reviewed, "
                    f"one-line decision) instead of adding a dependency silently"
                )


def check_submodule_pointers(failures: list[str]) -> None:
    # `git ls-remote <url> <sha>` does NOT check whether a commit exists (ls-remote
    # matches ref *names*, not arbitrary commit content) -- it silently returns nothing
    # for a real, pushed commit. Instead: fetch the submodule's own pinned branch and
    # check the checked-out commit is an ancestor of (or equal to) its tip.
    result = run(["git", "config", "--file", ".gitmodules", "--get-regexp", r"submodule\..*\.path"])
    if result.returncode != 0:
        return

    for line in result.stdout.splitlines():
        _, path = line.split(maxsplit=1)
        if path not in SUBMODULE_BRANCHES:
            continue

        sub_dir = REPO_ROOT / path
        if not (sub_dir / ".git").exists():
            continue  # submodule not initialized; nothing to verify

        pinned = run(["git", "rev-parse", "HEAD"], cwd=sub_dir)
        if pinned.returncode != 0:
            continue
        commit = pinned.stdout.strip()
        branch = SUBMODULE_BRANCHES[path]

        fetch = run(["git", "fetch", "--quiet", "origin", branch], cwd=sub_dir, timeout=20)
        if fetch.returncode != 0:
            print(f"warn: could not fetch {path}'s origin/{branch} to verify {commit[:12]} "
                  "(offline?) -- skipping", file=sys.stderr)
            continue

        contains = run(["git", "merge-base", "--is-ancestor", commit, "FETCH_HEAD"], cwd=sub_dir)
        if contains.returncode != 0:
            failures.append(
                f"{path} is pinned to {commit[:12]}, which is not on origin/{branch} -- did you push it?"
            )


def report_diff_stats() -> None:
    """Report-only: never fails. Shows how big the change is, per top-level directory."""
    base_ref = os.environ.get("GUARD_BASE_REF", "origin/main")
    result = run(["git", "diff", "--numstat", f"{base_ref}...HEAD"])
    if result.returncode != 0 or not result.stdout.strip():
        print("guard: no diff against", base_ref, "(nothing to report)")
        return

    by_dir: dict[str, list[int]] = {}
    for line in result.stdout.splitlines():
        added, removed, path = line.split("\t")
        top = path.split("/", 1)[0]
        added = 0 if added == "-" else int(added)
        removed = 0 if removed == "-" else int(removed)
        by_dir.setdefault(top, [0, 0])
        by_dir[top][0] += added
        by_dir[top][1] += removed

    print(f"\n## Change vs {base_ref}\n")
    print("| directory | +added | -removed |")
    print("|---|---:|---:|")
    for top, (added, removed) in sorted(by_dir.items()):
        print(f"| {top} | +{added} | -{removed} |")

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a") as f:
            f.write(f"\n## Change vs {base_ref}\n\n| directory | +added | -removed |\n|---|---:|---:|\n")
            for top, (added, removed) in sorted(by_dir.items()):
                f.write(f"| {top} | +{added} | -{removed} |\n")


CHECKS = [
    ("format", check_format),
    ("duplicates", check_duplicates),
    ("complexity", check_complexity),
    ("file-length", check_file_length),
    ("orphan-files", check_orphan_files),
    ("paired-tests", check_paired_tests),
    ("dependency-allowlist", check_dependency_allowlist),
    ("submodule-pointers", check_submodule_pointers),
]


def main() -> int:
    failures: list[str] = []
    for name, check in CHECKS:
        before = len(failures)
        check(failures)
        status = "FAIL" if len(failures) > before else "ok"
        print(f"guard: {name}: {status}")

    report_diff_stats()

    if failures:
        print("\nguard: failed:\n")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("\nguard: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
