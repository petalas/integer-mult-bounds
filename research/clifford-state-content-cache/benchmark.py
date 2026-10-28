"""Five alternating fresh-process complete replays per mode. Apache-2.0."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent


def measure(mode):
    start = time.perf_counter()
    process = subprocess.run([sys.executable, "-I", "-B", str(HERE / "run.py"),
                              "--mode", mode], capture_output=True, timeout=300)
    elapsed = time.perf_counter() - start
    if process.returncode or process.stderr:
        raise ValueError(f"failed {mode} replay: {process.returncode}\n"
                         + process.stderr.decode(errors="replace"))
    text = process.stdout.decode()
    scientific, companion = text.rsplit("\n", 2)[:2]
    receipt = json.loads(companion)
    if receipt["status"] != "PASS_CLIFFORD_STATE_CONTENT_CACHE":
        raise ValueError("complete consumer did not pass")
    if sha256((scientific + "\n").encode()).hexdigest() != receipt["scientific_stdout_sha256"]:
        raise ValueError("scientific stdout binding")
    return dict(mode=mode, process_wall_seconds=elapsed, receipt=receipt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("output must be a new path")
    frozen = {p: (HERE / p).read_bytes() for p in ("cache.py", "run.py", "benchmark.py")}
    implementation = {p: sha256(raw).hexdigest() for p, raw in frozen.items()}
    samples = []
    for _ in range(5):
        for mode in ("tables", "cached"):
            sample = measure(mode)
            if sample["receipt"]["implementation_sha256"] != {p: implementation[p] for p in ("cache.py", "run.py")}:
                raise ValueError("mixed implementation samples")
            if samples and sample["receipt"]["source_sha256"] != samples[0]["receipt"]["source_sha256"]:
                raise ValueError("mixed source samples")
            samples.append(sample)
            print(mode, sample["process_wall_seconds"], flush=True)
    digests = {x["receipt"]["scientific_stdout_sha256"] for x in samples}
    requests = {x["receipt"]["requests"] for x in samples}
    if len(digests) != 1 or len(requests) != 1:
        raise ValueError("different complete workloads or outputs")
    summary = {}
    for mode in ("tables", "cached"):
        values = [x["process_wall_seconds"] for x in samples if x["mode"] == mode]
        summary[mode] = dict(median=statistics.median(values), low=min(values), high=max(values))
    if any((HERE / p).read_bytes() != raw for p, raw in frozen.items()):
        raise ValueError("benchmark implementation changed")
    result = dict(status="PASS_ALTERNATING_COMPLETE_BENCHMARK", samples=samples,
                  summary=summary, errors=0, python=sys.version, platform=platform.platform(),
                  implementation=implementation)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
