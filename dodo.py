from pathlib import Path

from doit.tools import run_once


def _path_sortkey(p):
    """Sort paths lexicographically, but put directories last
    This ensures easy clean-ups while still getting a nicer output
    """
    return (p.is_dir(), *p.parts)


THIS = Path(__file__).resolve()
HERE = THIS.parent
PYPROJECT = HERE / "pyproject.toml"
SRC_PATH = HERE / "tiddlyparse"
SRC_FILES = sorted(SRC_PATH.rglob("*.py"), key=_path_sortkey)
TESTS_PATH = HERE / "tests"
TESTS_FILES = sorted(TESTS_PATH.rglob("*.py"), key=_path_sortkey)

ALL_PY_FILES = sorted([THIS, *SRC_FILES, *TESTS_FILES], key=_path_sortkey)

# outputs
DIST_PATH = HERE / "dist"
DIST_FILES = sorted(
    [*DIST_PATH.glob("*.tar.gz"), *DIST_PATH.glob("*.whl")], key=_path_sortkey
)


def with_poetry(*actions):
    return [
        f"poetry run {action}"
        if isinstance(action, str)
        else ["poetry", "run", *action]
        for action in actions
    ]


def task_poetry_install():
    # in case we have doit installed outside of poetry
    # and there is no lock file, run poetry first.
    return {
        "actions": [["poetry", "install"]],
        "targets": ["poetry.lock"],
        "uptodate": [run_once],
    }


def task_lint():
    """Lint the code with isort, flake8 and mypy"""
    yield {
        "name": "isort_check",
        "setup": ["poetry_install"],
        "actions": with_poetry("isort --check-only %(changed)s"),
        "file_dep": ALL_PY_FILES,
    }
    yield {
        "name": "flake8",
        "setup": ["poetry_install"],
        "actions": with_poetry("flake8 %(changed)s"),
        "file_dep": ALL_PY_FILES,
    }
    yield {
        "name": "mypy",
        "setup": ["poetry_install"],
        "actions": with_poetry(["mypy", "--strict", SRC_PATH]),
        "file_dep": SRC_FILES,
    }
