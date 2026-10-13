"""The selector must not be able to reach a prohibited input.

Enumerated in METHOD_SPEC_EN.md section 1.2. This is a structural check at W1: the
selection rule's signature and the objects it receives are inspected for forbidden fields.
It is extended to the real observation schema at W3.
"""

from __future__ import annotations

import inspect
import unittest

from _support import build_opportunity, load_config  # noqa: E402
from joint_interception.policies.memory import select_action  # noqa: E402

PROHIBITED_FIELD_TOKENS = (
    "future",
    "ground_truth",
    "trace",
    "oracle",
    "judge",
    "outcome",
    "label",
    "test_split",
    "heldout",
    "held_out",
    "policy_params",
    "other_memory",
    "evader_route",
    "true_",
)


class TestSelectorInputs(unittest.TestCase):
    def test_signature_exposes_only_permitted_inputs(self):
        permitted = {"t", "scores", "verdicts", "memory", "params"}
        actual = set(inspect.signature(select_action).parameters)
        self.assertEqual(actual, permitted)

    def test_no_prohibited_token_in_selector_signature(self):
        for name in inspect.signature(select_action).parameters:
            for token in PROHIBITED_FIELD_TOKENS:
                self.assertNotIn(token, name.lower())

    def test_opportunity_exposes_no_prohibited_field(self):
        opportunity, _ = build_opportunity(load_config(), "F2")
        for field_name in vars(opportunity):
            for token in PROHIBITED_FIELD_TOKENS:
                with self.subTest(field=field_name, token=token):
                    self.assertNotIn(token, field_name.lower())

    def test_selector_module_does_not_import_evaluation_or_judge(self):
        """The acting side must not import the judging side."""
        import joint_interception.policies.memory as selector

        source = inspect.getsource(selector)
        self.assertNotIn("assistance_audit", source)
        self.assertNotIn("capture_judge", source)
        self.assertNotIn("import evaluation", source)

    def test_no_legacy_runtime_import_anywhere_in_the_package(self):
        import os

        import joint_interception

        root = os.path.dirname(joint_interception.__file__)
        offenders = []
        for directory, _, files in os.walk(root):
            for name in files:
                if not name.endswith(".py"):
                    continue
                path = os.path.join(directory, name)
                with open(path, encoding="utf-8") as handle:
                    text = handle.read()
                for forbidden in ("urban_dynamic_containment", "urban_capture_cooperation"):
                    # Documentation references in comments are permitted; imports are not.
                    for line in text.splitlines():
                        stripped = line.strip()
                        if stripped.startswith(("import ", "from ")) and forbidden in stripped:
                            offenders.append((path, stripped))
        self.assertEqual(offenders, [])

    def test_w0_w1_modules_remain_standard_library_only(self):
        """The finite-example results must stay reproducible with no third-party package.

        W2 introduces `jsonschema`, so a blanket standard-library rule would now be false.
        The property that actually matters is narrower and is preserved: the modules that
        implement the W0-W1 finite examples import nothing outside the standard library,
        so `scripts/run_finite_examples.py` still runs on a bare interpreter.
        """
        import ast
        import os

        import joint_interception

        root = os.path.dirname(joint_interception.__file__)
        w0_w1_modules = [
            os.path.join(root, "opportunities"),
            os.path.join(root, "policies"),
            os.path.join(root, "evaluation", "assistance_audit.py"),
        ]
        found: set[str] = set()
        for target in w0_w1_modules:
            paths = []
            if os.path.isdir(target):
                for directory, _, files in os.walk(target):
                    paths += [os.path.join(directory, n) for n in files if n.endswith(".py")]
            else:
                paths = [target]
            for path in paths:
                with open(path, encoding="utf-8") as handle:
                    tree = ast.parse(handle.read(), filename=path)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            found.add(alias.name.split(".")[0])
                    elif isinstance(node, ast.ImportFrom):
                        if node.level and node.level > 0:
                            continue
                        if node.module:
                            found.add(node.module.split(".")[0])
        stdlib = {
            "dataclasses",
            "enum",
            "typing",
            "itertools",
            "json",
            "os",
            "sys",
            "math",
            "random",
            "collections",
            "functools",
            "hashlib",
            "datetime",
            "pathlib",
            "heapq",
            "argparse",
            "time",
            "platform",
            "unittest",
            "inspect",
            "csv",
            "subprocess",
            "ast",
            "__future__",
            "resource",
            "importlib",
        }
        self.assertEqual(
            found - stdlib, set(), f"W0-W1 modules gained a dependency: {found - stdlib}"
        )

    def test_package_dependencies_match_the_declared_pins(self):
        """Any third-party import anywhere in the package must be a pinned declared one."""
        import ast
        import os
        import re

        import joint_interception

        root = os.path.dirname(joint_interception.__file__)
        project_root = os.path.dirname(os.path.dirname(root))
        with open(os.path.join(project_root, "pyproject.toml"), encoding="utf-8") as handle:
            pyproject = handle.read()
        declared = set(re.findall(r'"([A-Za-z0-9_.-]+)==', pyproject))

        found: set[str] = set()
        for directory, _, files in os.walk(root):
            for name in files:
                if not name.endswith(".py"):
                    continue
                with open(os.path.join(directory, name), encoding="utf-8") as handle:
                    tree = ast.parse(handle.read())
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            found.add(alias.name.split(".")[0])
                    elif isinstance(node, ast.ImportFrom):
                        if node.level and node.level > 0:
                            continue
                        if node.module:
                            found.add(node.module.split(".")[0])
        stdlib = {
            "dataclasses",
            "enum",
            "typing",
            "itertools",
            "json",
            "os",
            "sys",
            "math",
            "random",
            "collections",
            "functools",
            "hashlib",
            "datetime",
            "pathlib",
            "heapq",
            "argparse",
            "time",
            "platform",
            "unittest",
            "inspect",
            "csv",
            "subprocess",
            "ast",
            "__future__",
            "resource",
            "importlib",
            "re",
            "contextlib",
            "multiprocessing",
            "pickle",
        }
        third_party = found - stdlib
        undeclared = third_party - declared
        self.assertEqual(undeclared, set(), f"undeclared dependencies: {undeclared}")


if __name__ == "__main__":
    unittest.main()
