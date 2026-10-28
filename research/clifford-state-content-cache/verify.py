"""Exact invalidation and ownership controls for state reuse. Apache-2.0."""
from contextlib import redirect_stdout
from copy import deepcopy
from hashlib import sha256
from io import StringIO
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cache import MAX_GATES, make_evaluator, snapshot
from run import COMPILER, TABLES, capture, module_bytes


def require(condition, message):
    if not condition:
        raise ValueError(message)


def rejected(action):
    try:
        action()
    except ValueError:
        return
    raise ValueError("invalid fixture accepted")


def conformance(backend, compiler):
    cached = make_evaluator(backend, 8)
    cases = entries = 0
    for n in range(1, 5):
        op = compiler.ident(n)
        for step in range(16):
            q = 1 + (step % ((1 << n) - 1))
            gate = compiler.cgate(n, q, 1 if step % 2 else -1)
            op = op.then(gate)
            if step % 3 == 0:
                op = op.then(compiler.xgate(n, step % (1 << n)))
            if step % 4 == 0:
                op = op.then(compiler.diag(n, tuple(1 << i for i in range(n))))
            for basis in range(1 << n):
                reference = backend(op, basis)
                require(cached(op, basis) == reference, "fresh computation")
                result = cached(op, basis)
                require(result == reference, "cached computation")
                result[0].clear()
                require(cached(op, basis) == reference, "fresh mutable return")
                cases += 1
                entries += 1 << n
    return dict(cases=cases, amplitude_entries=entries,
                final_cache=cached.cache_info()._asdict())


def ownership(backend):
    cache = make_evaluator(backend, 2)
    rows = [1, 2]
    phases = [0, 0]
    op = SimpleNamespace(n=2, circuit=[["D", rows, phases]])
    before = cache(op, 1)
    phases[0] = 2
    require(cache(op, 1) != before, "nested mutable gate changed the key")
    phases[0] = 0
    require(cache(op, 1) == before, "restored gate recovers original state")
    op.circuit = [["phase", 1]]
    require(cache(op)[0][0] == (0, 1), "global phase is in the key")
    op.circuit = []
    require(cache(op, 1)[0][1] == (1, 0), "basis input is in the key")
    op.n = 1
    require(len(cache(op)[0]) == 2, "dimension is in the key")
    require(cache.cache_info().currsize == 2, "capacity and eviction")
    cache.cache_clear()
    require(cache.cache_info().currsize == 0, "explicit release")
    return 7


def failures(backend):
    invalid = [SimpleNamespace(n=10, circuit=[]),
               SimpleNamespace(n=1, circuit=[["unknown", 0]]),
               SimpleNamespace(n=1, circuit=[["P", [2]]]),
               SimpleNamespace(n=1, circuit=[["D", [1], [True]]]),
               SimpleNamespace(n=1, circuit=[["C", 1, 0]]),
               SimpleNamespace(n=1, circuit=[["phase", 0]] * (MAX_GATES + 1))]
    for op in invalid:
        rejected(lambda op=op: snapshot(op, 0))
    rejected(lambda: snapshot(SimpleNamespace(n=1, circuit=[]), 2))
    rejected(lambda: make_evaluator(backend, 0))
    calls = [0]

    def broken(op, basis):
        calls[0] += 1
        raise ValueError("backend failure")

    cached = make_evaluator(broken)
    op = SimpleNamespace(n=1, circuit=[])
    for _ in range(2):
        rejected(lambda: cached(op))
    require(calls[0] == 2 and cached.cache_info().currsize == 0,
            "exceptions are recomputed and never retained")
    return len(invalid) + 3


def provenance_controls(values):
    import benchmark
    import run
    implementation = {p: sha256((run.HERE / p).read_bytes()).hexdigest()
                      for p in ("cache.py", "run.py")}
    receipt = dict(implementation_sha256=implementation,
                   source_sha256={"fixture": "same"})
    with tempfile.TemporaryDirectory(prefix="cache-provenance-controls-") as name:
        root = Path(name)
        for field in ("implementation_sha256", "source_sha256"):
            first = dict(mode="tables", process_wall_seconds=1, receipt=deepcopy(receipt))
            second = deepcopy(first)
            second["receipt"][field][next(iter(second["receipt"][field]))] = "changed"
            with patch.object(benchmark, "measure", side_effect=[first, second]), \
                 patch.object(sys, "argv", ["benchmark.py", "--output", str(root / field)]), \
                 redirect_stdout(StringIO()):
                rejected(benchmark.main)
            require(not (root / field).exists(), "mixed samples produce no receipt")
        for filename in ("cache.py", "run.py"):
            (root / filename).write_bytes((run.HERE / filename).read_bytes())

        def changed(mode, inputs, implementation):
            (root / "cache.py").write_bytes(b"changed during execution")
            return "PASS_P104_BASE5907_EDIT_KAPPA_312580400", {}

        with patch.object(run, "HERE", root), patch.object(run, "capture", return_value={}), \
             patch.object(run, "replay", side_effect=changed), \
             patch.object(sys, "argv", ["run.py"]):
            rejected(run.main)
        target = root / "clifford_exact.py"
        target.write_bytes(values[COMPILER] + b"\n")
        original, cache, modules, calls, replacement, tables = run.install(
            values, "cached", {"cache.py": (Path(__file__).parent / "cache.py").read_bytes()})
        try:
            rejected(lambda: importlib.util.spec_from_file_location("bad_compiler", target))
            require(not modules, "changed compiler rejected before execution")
        finally:
            importlib.util.spec_from_file_location = original
            cache.cache_clear()
            tables.clear_caches()
    return 4


def main():
    start = time.perf_counter()
    values = capture()
    tables = module_bytes("cache_test_tables", values[TABLES], TABLES)
    compiler = module_bytes("cache_test_compiler", values[COMPILER], COMPILER)
    result = dict(status="PASS_CLIFFORD_STATE_CACHE_CONTROLS",
                  conformance=conformance(tables.zero_state, compiler),
                  ownership_controls=ownership(tables.zero_state),
                  failure_controls=failures(tables.zero_state),
                  provenance_controls=provenance_controls(values))
    with tempfile.TemporaryDirectory(prefix="state-cache-corruptions-") as name:
        root = Path(name)
        for path, raw in values.items():
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        require(capture(root) == values, "relocated source capture")
        for path, raw in values.items():
            target = root / path
            target.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
            rejected(lambda: capture(root))
            target.write_bytes(raw)
        result["source_corruption_controls"] = len(values)
    require(capture() == values, "unchanged live sources")
    result["wall_seconds"] = time.perf_counter() - start
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
