"""Regenerate the .pyi stubs for the Cython modules.

stubgen-pyx parses the .pyx sources, so unlike mypy's stubgen it recovers real
signatures for cdef classes instead of (*args, **kwargs). It gets a few things
wrong that this script patches afterwards, so regeneration stays a single
reproducible command:

    make stubs

Run `make stubtest` after regenerating; it compares every stub against the
compiled module and fails on drift.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "asyncmy"

# The .pyx sources carry no return annotations, so every generated signature
# would end in an implicit Any and callers would get no attribute checking on
# what they get back. Annotating the sources instead would hand the types to
# Cython's annotation_typing and change codegen, so the public surface is
# annotated here. {file: {function: return type}}
RETURN_TYPES = {
    "connection.pyi": {
        "connect": "_ConnectionContextManager[Connection]",
        "cursor": "Cursor",
        "ensure_closed": "None",
        "close": "None",
        "begin": "None",
        "commit": "None",
        "rollback": "None",
        "ping": "None",
        "select_db": "None",
        "set_charset": "None",
        "get_server_info": "str",
        "get_host_info": "str",
        "get_proto_info": "int",
        "thread_id": "int",
        "affected_rows": "int",
        "insert_id": "int",
        "get_transaction_status": "bool",
        "get_autocommit": "bool",
        "escape_string": "str",
        "__aenter__": "Self",
    },
    "cursors.pyi": {
        "execute": "int",
        "executemany": "int | None",
        "fetchone": "Any",
        "fetchall": "list[Any]",
        "fetchmany": "list[Any]",
        "nextset": "bool | None",
        "close": "None",
        "mogrify": "str",
        # scroll is deliberately absent: Cursor.scroll is sync while
        # SSCursor.scroll is `async def`, so no single return type is true for
        # both and annotating it would only assert the inconsistency louder.
        "__aenter__": "Self",
        "__await__": "Generator[Any, None, Self]",
    },
    "pool.pyi": {
        "create_pool": "_PoolContextManager[Pool]",
        "acquire": "_PoolAcquireContextManager[Connection]",
        "release": "Any",
        "clear": "None",
        "close": "None",
        "terminate": "None",
        "wait_closed": "None",
        "__aenter__": "Self",
    },
}

# Imports the annotations above need, appended after the generated imports.
EXTRA_IMPORTS = {
    "connection.pyi": (
        "from typing_extensions import Self\n"
        "from asyncmy.contexts import _ConnectionContextManager\n"
    ),
    "cursors.pyi": (
        "from collections.abc import Generator\n"
        "from typing import Any\n"
        "from typing_extensions import Self\n"
    ),
    "pool.pyi": (
        "from typing import Any\n"
        "from typing_extensions import Self\n"
        "from asyncmy.contexts import _PoolAcquireContextManager, _PoolContextManager\n"
    ),
}

# (file, before, after, reason)
PATCHES = [
    (
        "converters.pyi",
        "from cpython import datetime\n",
        "import datetime\n",
        "`cimport`ed cpython.datetime is Cython-only; the stub must name the real module",
    ),
    (
        "converters.pyi",
        "conversions = ...",
        "conversions: dict",
        "the initialiser copies a cdef dict, which stubgen-pyx cannot evaluate",
    ),
    (
        # Anchored to __init__, not to `class Connection:` — inserting straight
        # after the class line would push the docstring below a statement and
        # stop it being a docstring at all.
        "connection.pyi",
        "    def __init__(self, *, user=None",
        "    # Injected onto the instance by BinLogStream\n"
        "    # (replication/binlogstream.py), hence declared but not defined.\n"
        "    _get_table_information: Any\n\n"
        "    def __init__(self, *, user=None",
        "replication attaches this attribute at runtime",
    ),
]


def apply_return_types(path: Path, returns: dict[str, str]) -> list[str]:
    """Give each named def an explicit return type, leaving parameters alone."""
    source = path.read_text()
    missing = []
    for name, return_type in returns.items():
        # `    async def fetchone(self):` -> `    async def fetchone(self) -> Any:`
        # Matches whatever parameter list is currently generated, so a signature
        # change does not silently skip the annotation.
        pattern = re.compile(
            r"^(?P<indent>[ ]*)(?P<async>async )?def (?P<name>%s)\((?P<params>.*)\)(?P<ret>[ ]*->[^:]+)?:"
            % re.escape(name),
            re.MULTILINE,
        )
        source, count = pattern.subn(
            lambda m: (
                "%s%sdef %s(%s) -> %s:"
                % (
                    m.group("indent"),
                    m.group("async") or "",
                    m.group("name"),
                    m.group("params"),
                    return_type,
                )
            ),
            source,
        )
        if not count:
            missing.append(name)
    path.write_text(source)
    return missing


def main() -> int:
    subprocess.run(["stubgen-pyx", str(PACKAGE)], check=True)

    for filename, before, after, reason in PATCHES:
        path = PACKAGE / filename
        source = path.read_text()
        if before not in source:
            print(
                f"warning: {filename} no longer contains the text patched for "
                f"'{reason}'. stubgen-pyx may have fixed it upstream — drop the "
                f"entry from {Path(__file__).name} if so.",
                file=sys.stderr,
            )
            continue
        path.write_text(source.replace(before, after, 1))
        print(f"patched {filename}: {reason}")

    failed = False
    for filename, returns in RETURN_TYPES.items():
        path = PACKAGE / filename
        source = path.read_text()
        extra = EXTRA_IMPORTS.get(filename, "")
        if extra and extra not in source:
            # After the generated header comment, before the first declaration.
            lines = source.splitlines(keepends=True)
            insert_at = 1 if lines and lines[0].startswith("#") else 0
            source = "".join(lines[:insert_at]) + extra + "".join(lines[insert_at:])
            path.write_text(source)
        missing = apply_return_types(path, returns)
        print(f"annotated {filename}: {len(returns) - len(missing)} return types")
        if missing:
            failed = True
            print(
                f"error: {filename} has no def for {sorted(missing)} — the API "
                f"changed, so update RETURN_TYPES in {Path(__file__).name}",
                file=sys.stderr,
            )

    # Format here so the generated files satisfy `make check` as-is, rather
    # than every regeneration leaving the tree dirty.
    stubs = sorted(str(p) for p in PACKAGE.glob("*.pyi"))
    subprocess.run(["ruff", "format", "--quiet", *stubs], check=True)
    subprocess.run(["ruff", "check", "--quiet", "--fix", *stubs], check=False)
    print(f"formatted {len(stubs)} stub files")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
