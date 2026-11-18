"""Unit tests for ci/guard.py (lab 5): the repo guard checks.

guard.py has no content/path deny-lists; it checks shape: file length, orphan files, paired tests, the CMake
dependency allow-list block, formatting, complexity, duplicates and submodule pins. Each check is run here on a
throw-away tree in a temp directory (guard.REPO_ROOT / EMULATOR_DIR / SOURCE_DIRS are patched); external tools
(clang-format, lizard, git) are mocked.

Docstring format of a test: "UT-CI-XX <input> | <expected> | <class>".
"""

import contextlib
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest
import warnings
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

CI_DIR = Path(__file__).resolve().parent


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = load_module("guard_under_test", CI_DIR / "guard.py")


class TreeCase(unittest.TestCase):
    """A fake repo: <tmp>/emulator, <tmp>/rpi-app, with guard's globals pointed at it."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.emulator = self.root / "emulator"
        self.rpi = self.root / "rpi-app"
        for directory in (self.emulator / "interface", self.emulator / "tests", self.rpi):
            directory.mkdir(parents=True)
        for name, value in (("REPO_ROOT", self.root), ("EMULATOR_DIR", self.emulator),
                            ("SOURCE_DIRS", [self.emulator, self.rpi])):
            patcher = mock.patch.object(guard, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def put(self, relative, text=""):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def run_check(self, check):
        failures = []
        with warnings.catch_warnings():
            # guard.check_file_length leaves its file handle to the GC (see the lab report).
            warnings.simplefilter("ignore", ResourceWarning)
            check(failures)
        return failures


class Thresholds(unittest.TestCase):
    def test_documented_constants(self):
        """UT-CI-95 константы модуля | MAX_FILE_LINES=600, MAX_FUNCTION_LINES=80, MAX_CCN=15 (как в docs/CI.md) | успешный"""
        self.assertEqual((guard.MAX_FILE_LINES, guard.MAX_FUNCTION_LINES, guard.MAX_CCN), (600, 80, 15))


class SourceFiles(TreeCase):
    def test_collects_cpp_and_hpp_sorted_and_skips_build_and_other_suffixes(self):
        """UT-CI-96 файлы emulator/b.cpp, emulator/a.hpp, rpi-app/c.cpp, emulator/x.py, emulator/build/skip.cpp, emulator/notes.txt | [emulator/a.hpp, emulator/b.cpp, rpi-app/c.cpp] (отсортированы, без build и .py/.txt) | успешный"""
        for name in ("emulator/b.cpp", "emulator/a.hpp", "rpi-app/c.cpp", "emulator/x.py",
                     "emulator/build/skip.cpp", "emulator/notes.txt"):
            self.put(name)
        got = [str(p.relative_to(self.root)) for p in guard.source_files()]
        self.assertEqual(got, ["emulator/a.hpp", "emulator/b.cpp", "rpi-app/c.cpp"])

    def test_directory_named_like_build_prefix_is_not_skipped(self):
        """UT-CI-97 emulator/builder/x.cpp (часть пути 'builder', не 'build') | файл учитывается | граничный"""
        self.put("emulator/builder/x.cpp")
        self.assertEqual([p.name for p in guard.source_files()], ["x.cpp"])

    def test_cmake_files_found_recursively(self):
        """UT-CI-98 CMakeLists.txt в корне и в emulator/ | оба найдены | успешный"""
        self.put("CMakeLists.txt")
        self.put("emulator/CMakeLists.txt")
        self.assertEqual(len(guard.cmake_files()), 2)


class FileLength(TreeCase):
    def lines(self, count):
        return "x\n" * count

    def test_600_lines_pass(self):
        """UT-CI-99 emulator/ok.cpp ровно 600 строк | failures=[] | граничный"""
        self.put("emulator/ok.cpp", self.lines(600))
        self.assertEqual(self.run_check(guard.check_file_length), [])

    def test_601_lines_fail(self):
        """UT-CI-100 emulator/big.cpp 601 строка | одна ошибка 'emulator/big.cpp: 601 lines (limit 600) -- split it' | граничный"""
        self.put("emulator/big.cpp", self.lines(601))
        self.assertEqual(self.run_check(guard.check_file_length),
                         ["emulator/big.cpp: 601 lines (limit 600) -- split it"])

    def test_599_lines_pass(self):
        """UT-CI-101 файл 599 строк | failures=[] | граничный"""
        self.put("emulator/ok.hpp", self.lines(599))
        self.assertEqual(self.run_check(guard.check_file_length), [])

    def test_last_line_without_newline_counts(self):
        """UT-CI-102 600 строк с '\\n' и 601-я без перевода строки | считается 601 строка, ошибка | граничный"""
        self.put("emulator/edge.cpp", self.lines(600) + "tail")
        self.assertEqual(len(self.run_check(guard.check_file_length)), 1)

    def test_empty_file_passes(self):
        """UT-CI-103 пустой .cpp | failures=[] | граничный"""
        self.put("emulator/empty.cpp", "")
        self.assertEqual(self.run_check(guard.check_file_length), [])

    def test_long_file_in_build_dir_is_ignored(self):
        """UT-CI-104 emulator/build/gen.cpp 5000 строк | failures=[] (build исключён) | успешный"""
        self.put("emulator/build/gen.cpp", self.lines(5000))
        self.assertEqual(self.run_check(guard.check_file_length), [])

    def test_long_python_file_is_not_checked(self):
        """UT-CI-105 emulator/big.py 5000 строк | failures=[] (проверяются только .cpp/.hpp) | успешный"""
        self.put("emulator/big.py", self.lines(5000))
        self.assertEqual(self.run_check(guard.check_file_length), [])

    def test_each_offender_reported(self):
        """UT-CI-106 два файла по 601 строке в emulator/ и rpi-app/ | 2 ошибки | успешный"""
        self.put("emulator/a.cpp", self.lines(601))
        self.put("rpi-app/b.cpp", self.lines(601))
        self.assertEqual(len(self.run_check(guard.check_file_length)), 2)


class OrphanFiles(TreeCase):
    def test_cpp_referenced_by_cmake_is_ok(self):
        """UT-CI-107 interface/uart.cpp и CMakeLists.txt с 'interface/uart.cpp' | failures=[] | успешный"""
        self.put("emulator/interface/uart.cpp")
        self.put("CMakeLists.txt", "add_library(x interface/uart.cpp)\n")
        self.assertEqual(self.run_check(guard.check_orphan_files), [])

    def test_cpp_not_in_cmake_fails(self):
        """UT-CI-108 interface/uart_v2.cpp, CMakeLists.txt его не упоминает | ['emulator/interface/uart_v2.cpp is not referenced by any CMakeLists.txt'] | отрицательный"""
        self.put("emulator/interface/uart_v2.cpp")
        self.put("CMakeLists.txt", "add_library(x interface/uart.cpp)\n")
        self.assertEqual(self.run_check(guard.check_orphan_files),
                         ["emulator/interface/uart_v2.cpp is not referenced by any CMakeLists.txt"])

    def test_hpp_included_by_a_cpp_is_ok(self):
        """UT-CI-109 interface/can.hpp, другой .cpp содержит '#include \"interface/can.hpp\"' | failures=[] | успешный"""
        self.put("emulator/interface/can.hpp")
        self.put("emulator/main.cpp", '#include "interface/can.hpp"\n')
        self.assertEqual(self.run_check(guard.check_orphan_files), [])

    def test_hpp_included_by_nothing_fails(self):
        """UT-CI-110 interface/can.hpp, никто не включает и CMake не упоминает | ['emulator/interface/can.hpp is included by nothing and built by nothing'] | отрицательный"""
        self.put("emulator/interface/can.hpp")
        self.put("emulator/main.cpp", "int main() {}\n")
        self.assertEqual(self.run_check(guard.check_orphan_files),
                         ["emulator/interface/can.hpp is included by nothing and built by nothing"])

    def test_hpp_mentioned_in_cmake_as_interface_path_is_ok(self):
        """UT-CI-111 interface/can.hpp не включён в .cpp, но 'interface/can.hpp' есть в CMakeLists.txt | failures=[] | граничный"""
        self.put("emulator/interface/can.hpp")
        self.put("CMakeLists.txt", "install(FILES interface/can.hpp)\n")
        self.assertEqual(self.run_check(guard.check_orphan_files), [])

    def test_no_interface_dir_files_no_failures(self):
        """UT-CI-112 в emulator/interface нет файлов | failures=[] | граничный"""
        self.assertEqual(self.run_check(guard.check_orphan_files), [])


class PairedTests(TreeCase):
    def test_no_test_sources_flags_every_interface(self):
        """UT-CI-113 interface/a.cpp, interface/b.cpp, нет tests/test_*.cpp | 2 ошибки '... has no tests at all (emulator/tests/ is empty)' | отрицательный"""
        self.put("emulator/interface/a.cpp")
        self.put("emulator/interface/b.cpp")
        failures = self.run_check(guard.check_paired_tests)
        self.assertEqual(sorted(failures), [
            "emulator/interface/a.cpp has no tests at all (emulator/tests/ is empty)",
            "emulator/interface/b.cpp has no tests at all (emulator/tests/ is empty)"])

    def test_one_test_covering_all_interfaces_is_enough(self):
        """UT-CI-114 tests/test_errors.cpp включает interface/a.hpp и interface/b.hpp | failures=[] | успешный"""
        self.put("emulator/interface/a.cpp")
        self.put("emulator/interface/b.cpp")
        self.put("emulator/tests/test_errors.cpp", '#include "interface/a.hpp"\n#include "interface/b.hpp"\n')
        self.assertEqual(self.run_check(guard.check_paired_tests), [])

    def test_uncovered_interface_fails(self):
        """UT-CI-115 interface/a.cpp покрыт, interface/b.cpp не включён ни одним тестом | 1 ошибка про b.cpp, содержит 'includes interface/b.hpp' | отрицательный"""
        self.put("emulator/interface/a.cpp")
        self.put("emulator/interface/b.cpp")
        self.put("emulator/tests/test_a.cpp", '#include "interface/a.hpp"\n')
        failures = self.run_check(guard.check_paired_tests)
        self.assertEqual(len(failures), 1)
        self.assertIn("emulator/interface/b.cpp", failures[0])
        self.assertIn("includes interface/b.hpp", failures[0])

    def test_file_not_named_test_prefix_is_not_a_test(self):
        """UT-CI-116 emulator/tests/helper.cpp включает interface/a.hpp (имя не test_*.cpp) | ошибка 'has no tests at all' | граничный"""
        self.put("emulator/interface/a.cpp")
        self.put("emulator/tests/helper.cpp", '#include "interface/a.hpp"\n')
        self.assertIn("has no tests at all", self.run_check(guard.check_paired_tests)[0])

    def test_no_interfaces_no_failures(self):
        """UT-CI-117 нет interface/*.cpp и нет тестов | failures=[] | граничный"""
        self.assertEqual(self.run_check(guard.check_paired_tests), [])


class DependencyAllowlist(TreeCase):
    def test_dependency_inside_block_ok(self):
        """UT-CI-118 find_package(...) между '# guard:deps:start' и '# guard:deps:end' | failures=[] | успешный"""
        self.put("CMakeLists.txt", "# guard:deps:start\nfind_package(Foo)\n# guard:deps:end\n")
        self.assertEqual(self.run_check(guard.check_dependency_allowlist), [])

    def test_dependency_before_block_fails(self):
        """UT-CI-119 pkg_check_modules(...) до блока | 1 ошибка 'CMakeLists.txt: pkg_check_modules(...) before the guard:deps block ...' | отрицательный"""
        self.put("CMakeLists.txt", "pkg_check_modules(X x)\n# guard:deps:start\n# guard:deps:end\n")
        failures = self.run_check(guard.check_dependency_allowlist)
        self.assertEqual(len(failures), 1)
        self.assertTrue(failures[0].startswith("CMakeLists.txt: pkg_check_modules(...) before the guard:deps block"), failures[0])

    def test_dependency_after_block_fails(self):
        """UT-CI-120 FetchContent_Declare(...) после блока | 1 ошибка, содержит 'FetchContent_Declare(...) after the guard:deps block' | отрицательный"""
        self.put("CMakeLists.txt", "# guard:deps:start\n# guard:deps:end\nFetchContent_Declare(y)\n")
        failures = self.run_check(guard.check_dependency_allowlist)
        self.assertEqual(len(failures), 1)
        self.assertIn("FetchContent_Declare(...) after the guard:deps block", failures[0])

    def test_file_without_markers_is_skipped(self):
        """UT-CI-121 CMakeLists.txt с find_package(Foo), но без маркеров | failures=[] (файл не объявляет сторонних зависимостей по контракту) | граничный"""
        self.put("CMakeLists.txt", "find_package(Foo)\n")
        self.assertEqual(self.run_check(guard.check_dependency_allowlist), [])

    def test_missing_end_marker_means_block_runs_to_eof(self):
        """UT-CI-122 маркер start есть, end нет, find_package после start | failures=[] | граничный"""
        self.put("CMakeLists.txt", "# guard:deps:start\nfind_package(Foo)\n")
        self.assertEqual(self.run_check(guard.check_dependency_allowlist), [])

    def test_call_with_space_before_parenthesis_is_detected(self):
        """UT-CI-123 'find_package (Foo)' до блока | 1 ошибка | граничный"""
        self.put("CMakeLists.txt", "find_package (Foo)\n# guard:deps:start\n# guard:deps:end\n")
        self.assertEqual(len(self.run_check(guard.check_dependency_allowlist)), 1)

    def test_word_boundary_not_a_dependency_call(self):
        """UT-CI-124 'my_find_package(Foo)' до блока | failures=[] (граница слова \\b) | граничный"""
        self.put("CMakeLists.txt", "my_find_package(Foo)\n# guard:deps:start\n# guard:deps:end\n")
        self.assertEqual(self.run_check(guard.check_dependency_allowlist), [])

    def test_two_violations_two_failures_and_nested_file_path(self):
        """UT-CI-125 emulator/CMakeLists.txt: find_package до и FetchContent_Declare после блока | 2 ошибки, обе с префиксом 'emulator/CMakeLists.txt:' | успешный"""
        self.put("emulator/CMakeLists.txt",
                 "find_package(A)\n# guard:deps:start\n# guard:deps:end\nFetchContent_Declare(b)\n")
        failures = self.run_check(guard.check_dependency_allowlist)
        self.assertEqual(len(failures), 2)
        self.assertTrue(all(f.startswith("emulator/CMakeLists.txt:") for f in failures), failures)


class FormatCheck(TreeCase):
    def test_clang_format_missing(self):
        """UT-CI-126 shutil.which('clang-format') -> None | 1 ошибка 'clang-format is not installed -- cannot check formatting (see docs/CI.md)' | отрицательный"""
        with mock.patch.object(guard.shutil, "which", return_value=None):
            self.assertEqual(self.run_check(guard.check_format),
                             ["clang-format is not installed -- cannot check formatting (see docs/CI.md)"])

    def test_unformatted_file_reported_by_relative_path(self):
        """UT-CI-127 clang-format завершается 1 для bad.cpp и 0 для good.cpp | 1 ошибка, содержит 'emulator/bad.cpp' и 'make fmt', не содержит good.cpp | успешный"""
        bad, good = self.put("emulator/bad.cpp"), self.put("emulator/good.cpp")

        def fake_run(cmd, **kw):
            return subprocess.CompletedProcess(cmd, 1 if cmd[-1] == str(bad) else 0, "", "")

        with mock.patch.object(guard.shutil, "which", return_value="/usr/bin/clang-format"), \
                mock.patch.object(guard, "run", side_effect=fake_run):
            failures = self.run_check(guard.check_format)
        self.assertEqual(failures, ["not formatted (run `make fmt`): emulator/bad.cpp"])
        self.assertNotIn(str(good), failures[0])

    def test_all_formatted_passes(self):
        """UT-CI-128 clang-format завершается 0 для всех файлов | failures=[] | успешный"""
        self.put("emulator/a.cpp")
        ok = subprocess.CompletedProcess([], 0, "", "")
        with mock.patch.object(guard.shutil, "which", return_value="/usr/bin/clang-format"), \
                mock.patch.object(guard, "run", return_value=ok) as run:
            self.assertEqual(self.run_check(guard.check_format), [])
        self.assertEqual(run.call_args.args[0][:3], ["clang-format", "--dry-run", "--Werror"])

    def test_no_sources_passes(self):
        """UT-CI-129 clang-format есть, исходников нет | failures=[], clang-format не вызывался | граничный"""
        with mock.patch.object(guard.shutil, "which", return_value="/usr/bin/clang-format"), \
                mock.patch.object(guard, "run") as run:
            self.assertEqual(self.run_check(guard.check_format), [])
        run.assert_not_called()


class ComplexityCheck(TreeCase):
    def test_skipped_when_lizard_missing(self):
        """UT-CI-130 shutil.which('lizard') -> None | failures=[] (об отсутствии сообщает check_duplicates) | граничный"""
        with mock.patch.object(guard.shutil, "which", return_value=None):
            self.assertEqual(self.run_check(guard.check_complexity), [])

    def test_violations_reported(self):
        """UT-CI-131 stdout lizard: 'a.cpp:10: warning: f has 90 NLOC' и пустая строка | 1 ошибка, начинается с 'functions over 80 lines or CCN 15:' и содержит строку нарушения | успешный"""
        out = subprocess.CompletedProcess([], 1, "a.cpp:10: warning: f has 90 NLOC\n\n", "")
        with mock.patch.object(guard.shutil, "which", return_value="/usr/bin/lizard"), \
                mock.patch.object(guard, "run", return_value=out) as run:
            failures = self.run_check(guard.check_complexity)
        self.assertEqual(len(failures), 1)
        self.assertTrue(failures[0].startswith("functions over 80 lines or CCN 15:"), failures[0])
        self.assertIn("a.cpp:10: warning: f has 90 NLOC", failures[0])
        self.assertIn("-L80", run.call_args.args[0])
        self.assertIn("-C15", run.call_args.args[0])

    def test_clean_output_passes(self):
        """UT-CI-132 stdout lizard пуст или только пробелы | failures=[] | граничный"""
        out = subprocess.CompletedProcess([], 0, "  \n\n", "")
        with mock.patch.object(guard.shutil, "which", return_value="/usr/bin/lizard"), \
                mock.patch.object(guard, "run", return_value=out):
            self.assertEqual(self.run_check(guard.check_complexity), [])


class DuplicatesCheck(TreeCase):
    def test_lizard_package_missing(self):
        """UT-CI-133 импорт lizard невозможен | 1 ошибка 'the `lizard` Python package is not installed -- cannot check for duplicates' | отрицательный"""
        with mock.patch.dict(sys.modules, {"lizard": None}):
            self.assertEqual(self.run_check(guard.check_duplicates),
                             ["the `lizard` Python package is not installed -- cannot check for duplicates"])

    def fake_lizard(self, functions_by_file):
        fake = mock.MagicMock()

        def analyze_file(path):
            return SimpleNamespace(function_list=functions_by_file[Path(path).name])

        fake.analyze_file.side_effect = analyze_file
        return fake

    @staticmethod
    def func(name, start, end):
        return SimpleNamespace(name=name, length=end - start + 1, start_line=start, end_line=end)

    BODY = "int f() {\n  int a = 1;\n  int b = 2;\n  return a + b;\n}\n"

    def run_with(self, functions):
        with mock.patch.dict(sys.modules, {"lizard": self.fake_lizard(functions)}):
            return self.run_check(guard.check_duplicates)

    def test_exact_copy_in_two_files_is_flagged(self):
        """UT-CI-134 две функции по 5 строк с одинаковым телом (разные отступы и пустые строки) в a.cpp и b.cpp | 1 ошибка 'emulator/b.cpp:g@1 is an exact copy of emulator/a.cpp:f@1 -- share one implementation' | успешный"""
        self.put("emulator/a.cpp", self.BODY)
        self.put("emulator/b.cpp", self.BODY.replace("  ", "\t") + "\n")
        failures = self.run_with({"a.cpp": [self.func("f", 1, 5)], "b.cpp": [self.func("g", 1, 5)]})
        self.assertEqual(failures, ["emulator/b.cpp:g@1 is an exact copy of emulator/a.cpp:f@1 -- share one implementation"])

    def test_different_bodies_pass(self):
        """UT-CI-135 две функции по 5 строк с разным телом | failures=[] | успешный"""
        self.put("emulator/a.cpp", self.BODY)
        self.put("emulator/b.cpp", self.BODY.replace("a + b", "a - b"))
        self.assertEqual(self.run_with({"a.cpp": [self.func("f", 1, 5)], "b.cpp": [self.func("g", 1, 5)]}), [])

    def test_short_function_is_never_flagged(self):
        """UT-CI-136 две одинаковые функции длиной 4 строки (length < 5) | failures=[] | граничный"""
        self.put("emulator/a.cpp", "void f() {\n  x();\n  y();\n}\n")
        self.put("emulator/b.cpp", "void f() {\n  x();\n  y();\n}\n")
        self.assertEqual(self.run_with({"a.cpp": [self.func("f", 1, 4)], "b.cpp": [self.func("f", 1, 4)]}), [])

    def test_five_line_function_is_flagged(self):
        """UT-CI-137 две одинаковые функции длиной ровно 5 строк | 1 ошибка | граничный"""
        self.put("emulator/a.cpp", self.BODY)
        self.put("emulator/b.cpp", self.BODY)
        self.assertEqual(len(self.run_with({"a.cpp": [self.func("f", 1, 5)], "b.cpp": [self.func("f", 1, 5)]})), 1)


class SubmoduleCheck(TreeCase):
    def fake_git(self, config="submodule.protocol.path protocol\n", merge_base=0, fetch=0, rev_parse=0):
        calls = []

        def run(cmd, cwd=None, **kw):
            calls.append(cmd[:3])
            if cmd[1] == "config":
                return subprocess.CompletedProcess(cmd, 0 if config is not None else 1, config or "", "")
            if cmd[1] == "rev-parse":
                return subprocess.CompletedProcess(cmd, rev_parse, "abcdef1234567890\n", "")
            if cmd[1] == "fetch":
                return subprocess.CompletedProcess(cmd, fetch, "", "")
            if cmd[1] == "merge-base":
                return subprocess.CompletedProcess(cmd, merge_base, "", "")
            raise AssertionError(cmd)

        return run, calls

    def init_submodule(self, name="protocol"):
        (self.root / name / ".git").mkdir(parents=True)

    def check(self, **kwargs):
        run, calls = self.fake_git(**kwargs)
        stderr = io.StringIO()
        with mock.patch.object(guard, "run", side_effect=run), contextlib.redirect_stderr(stderr):
            return self.run_check(guard.check_submodule_pointers), calls, stderr.getvalue()

    def test_no_gitmodules_passes(self):
        """UT-CI-138 'git config --file .gitmodules' завершается с ошибкой | failures=[] | граничный"""
        failures, calls, _ = self.check(config=None)
        self.assertEqual((failures, len(calls)), ([], 1))

    def test_pin_not_on_origin_fails(self):
        """UT-CI-139 submodule protocol инициализирован, merge-base --is-ancestor возвращает 1 | 'protocol is pinned to abcdef123456, which is not on origin/main -- did you push it?' | отрицательный"""
        self.init_submodule()
        failures, _, _ = self.check(merge_base=1)
        self.assertEqual(failures, ["protocol is pinned to abcdef123456, which is not on origin/main -- did you push it?"])

    def test_pin_on_origin_passes(self):
        """UT-CI-140 merge-base --is-ancestor возвращает 0 | failures=[] | успешный"""
        self.init_submodule()
        self.assertEqual(self.check(merge_base=0)[0], [])

    def test_uninitialized_submodule_is_skipped(self):
        """UT-CI-141 в protocol нет .git | failures=[], fetch не вызывался | граничный"""
        failures, calls, _ = self.check(merge_base=1)
        self.assertEqual(failures, [])
        self.assertNotIn(["git", "fetch", "--quiet"], calls)

    def test_unknown_submodule_path_is_ignored(self):
        """UT-CI-142 .gitmodules перечисляет 'other/path', которого нет в SUBMODULE_BRANCHES | failures=[], rev-parse не вызывался | граничный"""
        (self.root / "other" / "path" / ".git").mkdir(parents=True)
        failures, calls, _ = self.check(config="submodule.other.path other/path\n", merge_base=1)
        self.assertEqual(failures, [])
        self.assertNotIn(["git", "rev-parse", "HEAD"], calls)

    def test_offline_fetch_warns_and_skips(self):
        """UT-CI-143 git fetch возвращает 128 | failures=[], на stderr 'warn: could not fetch protocol's origin/main' | отрицательный"""
        self.init_submodule()
        failures, _, err = self.check(fetch=128, merge_base=1)
        self.assertEqual(failures, [])
        self.assertIn("warn: could not fetch protocol's origin/main", err)

    def test_uses_branch_from_table(self):
        """UT-CI-144 SUBMODULE_BRANCHES | {'protocol': 'main', 'mobile_app': 'main'} | успешный"""
        self.assertEqual(guard.SUBMODULE_BRANCHES, {"protocol": "main", "mobile_app": "main"})


class DiffStats(unittest.TestCase):
    def report(self, stdout, returncode=0, env=None):
        out = io.StringIO()
        result = subprocess.CompletedProcess([], returncode, stdout, "")
        with mock.patch.object(guard, "run", return_value=result) as run, \
                mock.patch.dict(os.environ, env or {}, clear=False), \
                contextlib.redirect_stdout(out):
            guard.report_diff_stats()
        return out.getvalue(), run

    def test_aggregates_by_top_directory(self):
        """UT-CI-145 numstat: '3\\t1\\temulator/a.cpp', '2\\t0\\temulator/b.cpp', '5\\t4\\tdocs/x.md' | строки таблицы '| docs | +5 | -4 |' и '| emulator | +5 | -1 |' | успешный"""
        text, _ = self.report("3\t1\temulator/a.cpp\n2\t0\temulator/b.cpp\n5\t4\tdocs/x.md\n")
        self.assertIn("| docs | +5 | -4 |", text)
        self.assertIn("| emulator | +5 | -1 |", text)
        self.assertLess(text.index("| docs |"), text.index("| emulator |"))

    def test_binary_files_count_as_zero(self):
        """UT-CI-146 numstat '-\\t-\\timg/pic.png' | '| img | +0 | -0 |' | граничный"""
        text, _ = self.report("-\t-\timg/pic.png\n")
        self.assertIn("| img | +0 | -0 |", text)

    def test_file_in_repo_root_is_its_own_group(self):
        """UT-CI-147 numstat '1\\t2\\tMakefile' | '| Makefile | +1 | -2 |' | граничный"""
        self.assertIn("| Makefile | +1 | -2 |", self.report("1\t2\tMakefile\n")[0])

    def test_empty_diff_message(self):
        """UT-CI-148 пустой вывод git diff | 'guard: no diff against origin/main (nothing to report)' | граничный"""
        text, _ = self.report("", env={"GUARD_BASE_REF": "origin/main"})
        self.assertIn("guard: no diff against origin/main (nothing to report)", text)

    def test_git_failure_never_fails_the_guard(self):
        """UT-CI-149 git diff завершается 128 | печатает 'no diff against', исключения нет | отрицательный"""
        text, _ = self.report("junk", returncode=128)
        self.assertIn("no diff against", text)

    def test_base_ref_from_environment(self):
        """UT-CI-150 GUARD_BASE_REF=release/1 | git вызван с 'release/1...HEAD', заголовок '## Change vs release/1' | успешный"""
        text, run = self.report("1\t1\ta/b\n", env={"GUARD_BASE_REF": "release/1"})
        self.assertIn("release/1...HEAD", run.call_args.args[0])
        self.assertIn("## Change vs release/1", text)

    def test_step_summary_file_is_appended(self):
        """UT-CI-151 GITHUB_STEP_SUMMARY=<файл> с текстом 'old' | файл дополнен: 'old', '## Change vs', '| a | +1 | -1 |' | успешный"""
        with tempfile.TemporaryDirectory() as tmp:
            summary = Path(tmp) / "summary.md"
            summary.write_text("old\n")
            self.report("1\t1\ta/b\n", env={"GITHUB_STEP_SUMMARY": str(summary)})
            content = summary.read_text()
        self.assertTrue(content.startswith("old\n"))
        self.assertIn("## Change vs", content)
        self.assertIn("| a | +1 | -1 |", content)


class MainEntryPoint(unittest.TestCase):
    def run_main(self, checks):
        out = io.StringIO()
        with mock.patch.object(guard, "CHECKS", checks), \
                mock.patch.object(guard, "report_diff_stats"), \
                contextlib.redirect_stdout(out):
            code = guard.main()
        return code, out.getvalue()

    def test_all_checks_ok_exit_0(self):
        """UT-CI-152 две проверки без ошибок | код 0, 'guard: one: ok', 'guard: all checks passed' | успешный"""
        code, out = self.run_main([("one", lambda f: None), ("two", lambda f: None)])
        self.assertEqual(code, 0)
        self.assertIn("guard: one: ok", out)
        self.assertIn("guard: all checks passed", out)

    def test_one_failing_check_exit_1_and_others_still_run(self):
        """UT-CI-153 проверка 'bad' добавляет ошибку 'broken thing', следующая 'good' чистая | код 1, 'guard: bad: FAIL', 'guard: good: ok', '  - broken thing' | отрицательный"""
        code, out = self.run_main([("bad", lambda f: f.append("broken thing")), ("good", lambda f: None)])
        self.assertEqual(code, 1)
        self.assertIn("guard: bad: FAIL", out)
        self.assertIn("guard: good: ok", out)
        self.assertIn("  - broken thing", out)
        self.assertNotIn("all checks passed", out)

    def test_failure_is_attributed_to_the_check_that_added_it(self):
        """UT-CI-154 первая проверка добавляет ошибку, вторая нет | первая FAIL, вторая ok (подсчёт по приросту списка) | граничный"""
        _, out = self.run_main([("first", lambda f: f.append("x")), ("second", lambda f: None)])
        self.assertIn("guard: first: FAIL", out)
        self.assertIn("guard: second: ok", out)

    def test_registered_checks(self):
        """UT-CI-155 guard.CHECKS | имена по порядку: format, duplicates, complexity, file-length, orphan-files, paired-tests, dependency-allowlist, submodule-pointers | успешный"""
        self.assertEqual([name for name, _ in guard.CHECKS],
                         ["format", "duplicates", "complexity", "file-length", "orphan-files",
                          "paired-tests", "dependency-allowlist", "submodule-pointers"])


if __name__ == "__main__":
    unittest.main()
