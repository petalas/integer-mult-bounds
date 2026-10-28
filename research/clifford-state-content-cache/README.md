# Bounded exact Clifford state reuse in the PR6030 primary replay

This contribution was produced by Nick Petalas. Apache-2.0.

This opt-in runner adds a bounded cache of complete literal Clifford states to
Charles Bethin's gate-table evaluator. On the unchanged PR6030 primary replay,
it replaces 12,806 of 32,766 state evaluations with immutable-state lookups.
All existing source, native, caller, invoice, compiler, outer and expected-result
checks still execute. This is verifier engineering, with no new kappa,
physical multiplier improvement or supplier-admission claim.

## What is new

The cache keys the dimension, ordered literal circuit and basis input. It
copies every nested matrix row and phase list into immutable tuples. The
cached vector is a tuple of immutable Gaussian-integer pairs. Each request
returns a fresh list, so a caller can mutate its returned vector without
changing any later result. There are at most 512 resident states. Eviction
recomputes from the original evaluator, and exceptions are never cached.

The cache deliberately uses literal gates rather than the Pauli tableau.
A tableau alone omits absolute phase. Two operators with equal tableaus and
different literal phase gates must receive distinct keys. No acceptance
predicate, whole scientific result or persistent PASS is cached.

The existing evaluator reads only `n`, `circuit` and `basis`, and is pure for
these immutable values. Equal keys therefore imply exactly equal vectors and
denominators. Snapshotting mutable operands preserves this implication after
mutation. Copying the result list preserves the original ownership contract.
The retained evaluator supplies the gate semantics. These statements justify
the cache; they do not independently re-prove Clifford simulation.

## Evidence and measurement

The isolated complete candidate passes with 19,960 misses, 12,806 hits and
512 resident states. Its complete scientific stdout has SHA256
`2ecf25db6f4d4aebea5633e97ba7101979e954e07853ca1bfd5485735e3c90f8`.
The unchanged primary verifies its entire committed `RESULT.json` internally.
A differential mode additionally compares every answer with a fresh gate-table
state during that complete primary replay.

The finite controls check 480 input cases and 5,440 amplitude entries, plus
mutable inputs and outputs, absolute phase, dimensions, basis inputs,
eviction, explicit release, exceptions and invalid domains. One byte corruption
of each of the fifteen live inputs must reject. Four additional controls reject
mixed source samples, mixed implementation
samples, an implementation changed during a replay and an altered extracted
compiler before execution. All 35 control groups use explicit failures and
survive Python `-O`.

Five alternating fresh-process pairs did not establish a measurable full-replay
speedup on this shared macOS arm64 / CPython 3.12.15 host. The observed medians
are 51.75 seconds for gate tables and 50.43 seconds with complete-state reuse.
Their ranges overlap, and the median difference is smaller than the observed
variation. This is an inconclusive performance result for this fixed 512-state
cache, not a proof that every cache or host loses. It does not justify adopting
this cache as an optimization. No larger cache or successor search was run.

Every sample passes the complete primary and returns the same scientific stdout
hash above. The process-wall samples in seconds are:

| Pair | Gate tables | State reuse |
| --- | ---: | ---: |
| 1 | 50.626589 | 51.546820 |
| 2 | 53.575063 | 50.788896 |
| 3 | 51.747539 | 49.980646 |
| 4 | 51.806063 | 50.434506 |
| 5 | 50.342550 | 47.876590 |

The table-only range is 50.34 to 53.58 seconds. The cache range is 47.88 to
51.55 seconds. There are zero failed timed runs. CPU affinity and OS cache
flushing were not imposed. Entry load averages were 3.71/3.84/3.83 on 18 logical
CPUs. Counts are not proportional to evaluator cost, so the 12,806 hits alone
do not predict a corresponding wall-time saving. A fresh cost-weighted profile
would be needed before attributing the timing difference to a particular loop.

Timing is measured by `benchmark.py`, including authentication, private
snapshot preparation and the complete primary replay. Both modes use the same
gate-table backend and source closure.
Every sample must retain the same source hashes, implementation hashes,
request count and scientific stdout hash. Profiling and exploratory runs are
excluded. No timing threshold affects mathematical acceptance.

## Reproduction

From the worktree root, with CPython 3.12 and the standard library:

```sh
/Users/nick/git/integer-mult-bounds/.venv/bin/python3.12 -B scripts/research_package.py --package research/clifford-state-content-cache
/Users/nick/git/integer-mult-bounds/.venv/bin/python3.12 -I -B research/clifford-state-content-cache/run.py --mode cached
/Users/nick/git/integer-mult-bounds/.venv/bin/python3.12 -I -B research/clifford-state-content-cache/run.py --mode differential
```

Another CPython 3.12 interpreter can replace that local path. Direct commands
emit a generated companion receipt with the executed implementation and source
hashes. `--mode tables` runs the same wrapper without complete-state reuse.
The benchmark requires a new output path outside the checkout:

```sh
/Users/nick/git/integer-mult-bounds/.venv/bin/python3.12 -I -B research/clifford-state-content-cache/benchmark.py --output /tmp/clifford-cache-benchmark.json
```

## Source and scope

Scientific base is `721c03822c421b7f7fcbb2598993b947c4d88419`, priority revision 8.
`SOURCES.json` pins fifteen runtime inputs, including the entire source archive,
consumer expected result, table evaluator and exact compiler bytes. The runner
captures them before execution, copies them into a private temporary tree and
checks both the live inputs and private snapshot afterward. Extracted compiler
modules must match the pinned compiler bytes before compilation. The loader
executes those captured bytes and replaces only `Op.zero_state`.

The predecessor's source comments and notices remain unchanged. No frozen
package, default command or selected record is edited. The retained expected
result identifies the predecessor's scientific claim. The companion receipt
identifies this opt-in execution. These are separate records.

This runner covers the source-bound primary replay, not the full
`make frontier6030-verify` admission command. It does not supply an independent
second literal oracle. All five inherited framework assumptions remain.
Lean, Docker, physical tensor execution, a complete rounded multiplier,
independent human review and formal proof-kernel review are unclaimed.

## Implementation bounds

Inputs have zero through nine axes and at most 256 literal gates. Keys contain
only bounded integer fields and immutable tuples. A state has at most 512
Gaussian-integer pairs. Each C gate increases the largest numerator magnitude
by at most four before normalization, so 256 gates bound each component by
`2^512`. The cache retains at most 512 such states and their keys. The existing
gate-table backend separately bounds each of its two caches at 64 tables.

All new functions are below 60 lines and control flow is nonrecursive. The
managed Python runtime allocates during execution, a Power of Ten rule-3
deviation constrained by the fixed domains and cache capacity. Rule 8 permits
compilation of authenticated predecessor bytes for the required isolated
loader. The backend and loader callbacks have explicit fixed targets. Strict
warnings, normal/optimized controls and in-memory compilation provide the
available diagnostics; no repository-wide analyzer configuration changes.

## Credit and related work

Charles Bethin's PR662 supplies the reused gate-table evaluator. The original
compiler and native/frame lineage remain credited in their unchanged files.
PR1092 already reuses one saved monomial state locally; it does not supply this
bounded cross-call literal-circuit cache. Ali Romman's PR5704 supplies a distinct
quadratic-state algorithm, which is neither modified nor claimed here.
Clear1nsight's PR5832 reuses scalar gate setup in a different literal oracle
and explicitly leaves state answers uncached.

VictorLiwentao's open PR2329 wires the same gate-table algorithm into an older
production consumer. This experiment changes neither that consumer nor its
reported timing.

JosieElliston's open PR6112 binds the gate-table evaluator to this same primary
consumer. That binding motivates the present source-specific experiment.
The new contribution is bounded complete-state reuse and its independently
replayable ownership, invalidation and measurement contract. Standard
memoization is not claimed as a new algorithm. The scientific construction,
source archive and expected result are DreamingOfClouds' PR6030, built on
Ali Romman's PR5827 chain and its retained predecessors, with Douglas Colkitt's
portability repair.

## Open next questions

Which actual work is removed by the repeated keys? Start with a fresh
cost-weighted profile of the pinned primary and separate the key, copying,
gate-evaluation and remaining-caller costs. This experiment counts exact hits
but does not attribute the observed noise to one root cause.

Does the source-bound effect persist on another host? Run the same alternating
benchmark and retain every sample and hash. A shared-host measurement does not
answer this. Adoption into a maintained verifier also requires a separate
source-bound decision about the changed execution and memory budget.

## Local validation

All four registered commands pass. The normal and optimized control commands
finish in 0.061 and 0.063 seconds. The registered complete cached and
all-request differential commands finish in 47.89 and 56.58 seconds,
respectively. These are command qualifications, separate from the five-pair
benchmark. The direct verifier also passes. Strict-warning execution and
in-memory compilation pass; Ruff is unavailable in the local environment.
No hosted CI certification is claimed for this handoff.
