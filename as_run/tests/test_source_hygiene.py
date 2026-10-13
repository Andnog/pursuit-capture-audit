"""Source hygiene checks that protect the written record.

These exist because each one has already caught a real defect in this project.
They use the standard library only, so they run on a bare interpreter.
"""

from __future__ import annotations

import ast
import io
import os
import tokenize
import unittest

from _support import ROOT  # noqa: E402

SCANNED = ("src", "tests", "scripts")


def static_edges(literal: str) -> tuple[str, str] | None:
    """Return a string literal's leading and trailing STATIC text.

    `ast.literal_eval` raises on an f-string, which once made this check crash instead of
    report. Parsing instead yields the static fragments around the substitutions, and those
    are exactly what a glued concatenation would corrupt. An edge that is a substitution
    rather than text yields "", which is correctly read as "nothing to glue". Non-string
    literals (bytes, numbers) return None and are skipped.
    """
    node = ast.parse(literal, mode="eval").body
    if isinstance(node, ast.Constant):
        return (node.value, node.value) if isinstance(node.value, str) else None
    if isinstance(node, ast.JoinedStr):
        parts = node.values
        if not parts:
            return "", ""
        head = parts[0].value if isinstance(parts[0], ast.Constant) else ""
        tail = parts[-1].value if isinstance(parts[-1], ast.Constant) else ""
        return head, tail
    return None


def python_files() -> list[str]:
    out = []
    for top in SCANNED:
        for directory, _, files in os.walk(os.path.join(ROOT, top)):
            if "__pycache__" in directory:
                continue
            out += [os.path.join(directory, n) for n in sorted(files) if n.endswith(".py")]
    return out


FSTRING_START = getattr(tokenize, "FSTRING_START", None)
FSTRING_END = getattr(tokenize, "FSTRING_END", None)


def source_slice(lines: list[str], start: tuple[int, int], end: tuple[int, int]) -> str:
    """Return the source text between two (row, column) token positions. Rows are 1-based."""
    (first_row, first_col), (last_row, last_col) = start, end
    if first_row == last_row:
        return lines[first_row - 1][first_col:last_col]
    return "".join(
        [
            lines[first_row - 1][first_col:],
            *lines[first_row : last_row - 1],
            lines[last_row - 1][:last_col],
        ]
    )


def glued_concatenations(source: str) -> list[tuple[int, str, str]]:
    """Find adjacent string literals on separate lines that glue two words together.

    Returns (line, left_tail, right_head) per offence.

    Python 3.12 changed the tokenizer: an f-string is no longer one STRING token but a
    FSTRING_START / FSTRING_MIDDLE / FSTRING_END group, which can nest. Those groups are
    rejoined here into a single literal, because on the pinned 3.14 interpreter every
    f-string would otherwise be invisible to this check.
    """
    lines = source.splitlines(keepends=True)
    found: list[tuple[int, str, str]] = []
    previous: tuple[tuple[int, int], str] | None = None

    def literal(start: tuple[int, int], end: tuple[int, int]) -> None:
        nonlocal previous
        text = source_slice(lines, start, end)
        if previous is not None and previous[0][0] != start[0]:
            left_edges = static_edges(previous[1])
            right_edges = static_edges(text)
            left = left_edges[1] if left_edges else ""
            right = right_edges[0] if right_edges else ""
            if (
                left
                and right
                and not left.endswith((" ", "\n"))
                and not right.startswith((" ", "\n"))
                and left[-1].isalnum()
                and right[0].isalnum()
            ):
                found.append((previous[0][0], left[-20:], right[:20]))
        previous = (end, text)

    depth = 0
    fstring_start: tuple[int, int] | None = None
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if FSTRING_START is not None and token.type == FSTRING_START:
            if depth == 0:
                fstring_start = token.start
            depth += 1
            continue
        if depth:
            if token.type == FSTRING_END:
                depth -= 1
                if depth == 0 and fstring_start is not None:
                    literal(fstring_start, token.end)
            continue
        if token.type == tokenize.STRING:
            literal(token.start, token.end)
        elif token.type not in (
            tokenize.NL,
            tokenize.NEWLINE,
            tokenize.COMMENT,
            tokenize.INDENT,
            tokenize.DEDENT,
        ):
            previous = None
    return found


class TestImplicitStringConcatenation(unittest.TestCase):
    """Adjacent string literals on separate lines must not glue words together.

    Re-wrapping long prose once produced `"...is a" "pinned declared dependency."`, which
    silently wrote "is apinned" into the provenance record. Nothing else would have caught
    it: the file parsed, the tests passed and the JSON was valid.
    """

    def test_no_glued_implicit_concatenation(self):
        offenders = []
        for path in python_files():
            with open(path, encoding="utf-8") as handle:
                source = handle.read()
            offenders += [
                f"{os.path.relpath(path, ROOT)}:{line} {left!r} + {right!r}"
                for line, left, right in glued_concatenations(source)
            ]
        self.assertEqual(offenders, [], "glued string concatenation:\n" + "\n".join(offenders))

    def test_the_check_would_catch_an_actual_violation(self):
        """The detector must still fire. It once crashed instead, and nothing noticed.

        `ast.literal_eval` raises on an f-string, so a single reflow of this file's own
        message into two adjacent f-strings turned the check into an error rather than a
        report. A detector with no test that it detects is not a detector.
        """
        glued = 'x = (\n    "is a"\n    "pinned dependency"\n)\n'
        self.assertEqual(len(glued_concatenations(glued)), 1)

        fstring = 'x = (\n    f"count {n} is"\n    f"wrong {m}"\n)\n'
        self.assertEqual(
            len(glued_concatenations(fstring)), 1, "f-strings must be checked, not skipped"
        )

        spaced = 'x = (\n    "is a "\n    "pinned dependency"\n)\n'
        self.assertEqual(glued_concatenations(spaced), [])

        substituted = 'x = (\n    f"total {n}"\n    f"{m} items"\n)\n'
        self.assertEqual(
            glued_concatenations(substituted),
            [],
            "an edge that is a substitution has no static text to glue",
        )


class TestEverySourceFileParses(unittest.TestCase):
    def test_all_python_files_parse(self):
        for path in python_files():
            with (
                self.subTest(file=os.path.relpath(path, ROOT)),
                open(path, encoding="utf-8") as handle,
            ):
                ast.parse(handle.read(), filename=path)


class TestNoLegacyRuntimePathIsExecutable(unittest.TestCase):
    """No module may put a legacy runtime root on sys.path.

    The import check in test_information_boundary.py covers `import` statements. This
    covers the other vector: making a legacy tree importable at runtime, after which an
    innocuous-looking import would resolve to legacy code.
    """

    FORBIDDEN = ("urban_dynamic_containment", "urban_capture_cooperation")

    def _path_mutation_arguments(self, tree: ast.AST):
        """Yield the argument nodes of every sys.path.insert/append/extend call."""
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in {"insert", "append", "extend"}:
                continue
            target = node.func.value
            if (
                isinstance(target, ast.Attribute)
                and target.attr == "path"
                and isinstance(target.value, ast.Name)
                and target.value.id == "sys"
            ):
                yield from node.args

    def test_no_legacy_root_is_added_to_sys_path(self):
        offenders = []
        for path in python_files():
            with open(path, encoding="utf-8") as handle:
                tree = ast.parse(handle.read(), filename=path)
            for argument in self._path_mutation_arguments(tree):
                for literal in ast.walk(argument):
                    if (
                        isinstance(literal, ast.Constant)
                        and isinstance(literal.value, str)
                        and any(f in literal.value for f in self.FORBIDDEN)
                    ):
                        offenders.append(f"{os.path.relpath(path, ROOT)}: {literal.value}")
        self.assertEqual(offenders, [], "legacy root added to sys.path")

    def test_the_check_would_catch_an_actual_violation(self):
        """A check that can never fire is not a check."""
        tree = ast.parse("import sys\nsys.path.insert(0, '/x/urban_dynamic_containment/src')\n")
        found = [
            literal.value
            for argument in self._path_mutation_arguments(tree)
            for literal in ast.walk(argument)
            if isinstance(literal, ast.Constant) and isinstance(literal.value, str)
        ]
        self.assertTrue(any("urban_dynamic_containment" in f for f in found))


if __name__ == "__main__":
    unittest.main()
