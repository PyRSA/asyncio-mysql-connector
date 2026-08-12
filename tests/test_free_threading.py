import os
import subprocess
import sys
import sysconfig
import textwrap
from concurrent.futures import ThreadPoolExecutor

import pytest

from asyncmy.converters import convert_datetime, convert_timedelta, escape_item
from asyncmy.protocol import MysqlPacket

MODULES = [
    "asyncmy.charset",
    "asyncmy.connection",
    "asyncmy.converters",
    "asyncmy.cursors",
    "asyncmy.errors",
    "asyncmy.pool",
    "asyncmy.protocol",
]

free_threaded_only = pytest.mark.skipif(
    not sysconfig.get_config_var("Py_GIL_DISABLED"),
    reason="requires a free-threaded CPython build",
)


@free_threaded_only
def test_imports_do_not_enable_gil():
    """A module that has not declared freethreading_compatible re-enables the
    GIL for the whole process on import, which defeats the point of running a
    free-threaded build at all."""
    code = textwrap.dedent(
        """
        import sys
        {imports}
        assert not sys._is_gil_enabled(), "importing asyncmy re-enabled the GIL"
        """
    ).format(imports="\n".join(f"import {name}" for name in MODULES))
    env = os.environ.copy()
    # PYTHON_GIL=0 would force the GIL off and hide exactly what we are testing.
    env.pop("PYTHON_GIL", None)
    env["PYTHONNOUSERSITE"] = "1"
    subprocess.run([sys.executable, "-c", code], check=True, env=env)


@free_threaded_only
def test_converter_and_protocol_paths_run_from_multiple_threads():
    """The declaration only claims module-level state is safe. This exercises
    that claim on the shared tables: encoders/decoders, the escape table and
    packet parsing, hit concurrently."""
    assert not sys._is_gil_enabled()
    packet_data = b"\x03abc\x01x\xfc\x05\x00"

    def worker(iterations: int) -> int:
        total = 0
        for _ in range(iterations):
            # escape_str walks the shared escape table; escape_int and the
            # sequence path go through the shared encoders dict.
            total += len(escape_item("a 'quoted' \\ text", "utf8mb4"))
            total += len(escape_item(2**64 - 1, "utf8mb4"))
            total += len(escape_item(("a", 1), "utf8mb4"))
            # str() rather than .second/.seconds: these converters return the
            # input unchanged for illegal values, so their type is `object`.
            total += len(str(convert_datetime("2026-06-11 12:34:56")))
            total += len(str(convert_timedelta("12:34:56")))
            packet = MysqlPacket(packet_data, "utf8mb4")
            total += len(packet.read_length_coded_string())
            total += len(packet.read_length_coded_string())
            total += packet.read_length_encoded_integer()
        return total

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(worker, [1000] * 4))

    # Same deterministic input in every thread: divergence would mean the
    # shared tables were being mutated underneath.
    assert results == [results[0]] * 4
