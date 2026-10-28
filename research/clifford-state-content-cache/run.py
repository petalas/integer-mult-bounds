"""Run the complete frozen primary replay with optional state reuse. Apache-2.0."""
import argparse
from contextlib import redirect_stdout
from hashlib import sha256
import importlib.util
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
import time
from types import ModuleType

sys.path.insert(0, str(Path(__file__).resolve().parent))

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
COMPILER = "research/p104-native-channel/vendor/clifford_exact.py"
TABLES = "research/clifford-state-performance/fast_state.py"
CONSUMER = "research/p104-helper470-twin-rung-removal/verify.py"


def need(condition, message):
    if not condition:
        raise ValueError(message)


def capture(root=ROOT):
    pins = json.loads((HERE / "SOURCES.json").read_bytes())
    values = {}
    for pin in pins["files"]:
        if pin["usage"] != "input":
            continue
        raw = (root / pin["path"]).read_bytes()
        need(sha256(raw).hexdigest() == pin["sha256"], "source drift: " + pin["path"])
        values[pin["path"]] = raw
    need(len(values) == 15, "complete fifteen-input closure")
    return values


def module_bytes(name, raw, filename):
    module = ModuleType(name)
    module.__file__ = str(filename)
    sys.modules[name] = module
    exec(compile(raw, str(filename), "exec"), module.__dict__)
    return module


def install(values, mode, implementation):
    cache = module_bytes("content_cache_impl", implementation["cache.py"], HERE / "cache.py")
    tables = module_bytes("content_cache_tables", values[TABLES], TABLES)
    original = importlib.util.spec_from_file_location
    evaluations = []
    calls = [0, 0]

    def evaluate(op, basis=0):
        calls[0] += 1
        if mode == "tables":
            calls[1] += 1
            return tables.zero_state(op, basis)
        answer = cached(op, basis)
        if mode == "differential":
            need(answer == tables.zero_state(op, basis), "fresh-state differential mismatch")
            calls[1] += 1
        return answer

    cached = cache.make_evaluator(tables.zero_state)

    def specification(name, location, *args, **kwargs):
        spec = original(name, location, *args, **kwargs)
        if Path(location).name != "clifford_exact.py":
            return spec
        raw = Path(location).read_bytes()
        need(raw == values[COMPILER], "extracted compiler differs from source pin")

        class Loader:
            def create_module(self, spec):
                return None

            def exec_module(self, module):
                exec(compile(raw, str(location), "exec"), module.__dict__)
                module.Op.zero_state = evaluate
                evaluations.append(module)

        spec.loader = Loader()
        return spec

    importlib.util.spec_from_file_location = specification
    return original, cached, evaluations, calls, evaluate, tables


def replay(mode, values, implementation):
    start = time.perf_counter()
    output = StringIO()
    old_spec, cached, modules, calls, replacement, tables = install(values, mode, implementation)
    old_argv, old_path = sys.argv[:], sys.path[:]
    try:
        with tempfile.TemporaryDirectory(prefix="clifford-content-cache-") as name:
            root = Path(name)
            for path, raw in values.items():
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
            target = root / CONSUMER
            sys.argv = [str(target)]
            with redirect_stdout(output):
                module_bytes("__main__", values[CONSUMER], target)
            need(modules and all(m.Op.zero_state is replacement for m in modules),
                 "every extracted compiler retains the replacement")
            need(all((root / p).read_bytes() == raw for p, raw in values.items()),
                 "unchanged private source snapshot")
        need(calls[0] > 0, "complete replay made state requests")
        receipt = dict(mode=mode, requests=calls[0], fresh_comparisons=calls[1],
                       cache=cached.cache_info()._asdict(),
                       wall_seconds=time.perf_counter() - start,
                       scientific_stdout_sha256=sha256(output.getvalue().encode()).hexdigest())
        return output.getvalue(), receipt
    finally:
        importlib.util.spec_from_file_location = old_spec
        sys.argv, sys.path[:] = old_argv, old_path
        cached.cache_clear()
        tables.clear_caches()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("tables", "cached", "differential"), default="cached")
    args = parser.parse_args()
    implementation = {p: (HERE / p).read_bytes() for p in ("cache.py", "run.py")}
    values = capture()
    output, receipt = replay(args.mode, values, implementation)
    need(capture() == values, "unchanged live inputs after replay")
    need("PASS_P104_BASE5907_EDIT_KAPPA_312580400" in output, "complete primary PASS")
    receipt["status"] = "PASS_CLIFFORD_STATE_CONTENT_CACHE"
    receipt["source_sha256"] = {p: sha256(raw).hexdigest() for p, raw in values.items()}
    need(all((HERE / p).read_bytes() == raw for p, raw in implementation.items()),
         "implementation changed during replay")
    receipt["implementation_sha256"] = {p: sha256(raw).hexdigest()
                                         for p, raw in implementation.items()}
    print(output, end="")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
