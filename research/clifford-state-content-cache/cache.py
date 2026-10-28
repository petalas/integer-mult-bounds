"""Bounded reuse of pure literal Clifford evaluations. Apache-2.0."""
from functools import lru_cache
from types import SimpleNamespace

MAX_AXES = 9
MAX_GATES = 256
MAX_STATES = 512


def need(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value, low, high):
    need(type(value) is int and low <= value <= high, "bounded integer gate field")
    return value


def rows(values, n):
    need(type(values) in (list, tuple) and len(values) == n, "complete gate rows")
    return tuple(integer(value, 0, (1 << n) - 1) for value in values)


def snapshot(op, basis):
    """Copy every value read by the pinned evaluator, without reading its tableau."""
    n = integer(op.n, 0, MAX_AXES)
    integer(basis, 0, (1 << n) - 1)
    need(type(op.circuit) in (list, tuple) and len(op.circuit) <= MAX_GATES,
         "bounded literal circuit")
    gates = []
    for gate in op.circuit:
        need(type(gate) in (list, tuple) and 1 <= len(gate) <= 3, "literal gate")
        kind = gate[0]
        need(type(kind) is str, "literal gate kind")
        if kind == "P":
            need(len(gate) == 2, "P gate shape")
            gates.append((kind, rows(gate[1], n)))
        elif kind == "D":
            need(len(gate) == 3, "D gate shape")
            need(type(gate[2]) in (list, tuple) and len(gate[2]) == n, "D phases")
            gates.append((kind, rows(gate[1], n),
                          tuple(integer(x, 0, 3) for x in gate[2])))
        elif kind in ("X", "phase"):
            need(len(gate) == 2, "unary gate shape")
            limit = (1 << n) - 1 if kind == "X" else 3
            gates.append((kind, integer(gate[1], 0, limit)))
        elif kind == "C":
            need(len(gate) == 3, "C gate shape")
            q = integer(gate[1], 1, (1 << n) - 1)
            sign = integer(gate[2], -1, 1)
            need(sign != 0, "C sign")
            gates.append((kind, q, sign))
        else:
            raise ValueError("unknown literal gate")
    return n, tuple(gates), basis


def make_evaluator(backend, capacity=MAX_STATES):
    """Backend must be pure and depend only on n, literal gates and basis."""
    integer(capacity, 1, MAX_STATES)

    @lru_cache(maxsize=capacity)
    def evaluate(n, circuit, basis):
        vector, denominator = backend(SimpleNamespace(n=n, circuit=circuit), basis)
        # The pinned backend returns immutable Gaussian integer pairs.
        return tuple(vector), denominator

    def cached(op, basis=0):
        vector, denominator = evaluate(*snapshot(op, basis))
        # The original API returns a mutable list. Never expose the cached tuple.
        return list(vector), denominator

    cached.cache_info = evaluate.cache_info
    cached.cache_clear = evaluate.cache_clear
    return cached
