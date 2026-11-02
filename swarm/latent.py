"""The shared latent field: a bipolar vector-symbolic space, the only channel between the agents.

Port of the original core's HDC/VSA primitives (``rsi_levels_metaforge_unified.py``
§9 ``HDCSpace``: ``random_vector``, ``bind`` as the elementwise product,
``bundle`` as the sign of the sum, ``permute`` as a cyclic shift,
``similarity`` as the normalized dot product; ``HDCAnalogicalTransfer``:
``A : B :: C : D`` with ``D = C ⊗ A ⊗ B``, bind being its own inverse on
bipolar vectors) and of §14's position-permuted sequence encoding
(``hdv_encode``). Re-implemented here in NumPy with provenance; nothing is
imported from the original core. OWNER_DIRECTIVE.md §3.

What crosses the channel is ``np.ndarray`` only. ``Field`` holds two
regions, ``breaker`` and ``builder``; an agent receives a ``Port`` that
writes to its own region and reads the other's, so no agent can write into
the other's region or read anything but vectors. ``Codebook`` maps symbols
to fixed random vectors (deterministic in the codebook seed, grown on
demand); each agent has its own, which is why the mapper exists.

``shuffled`` (arm S5) permutes every vector written by a fixed
permutation seeded by the kernel (from the run seed through a
kernel-side hash the agents cannot import) before it is stored, so what
the other agent reads carries
no information about what was written.
"""
from __future__ import annotations

import hashlib

import numpy as np

DEFAULT_D = 8192


def _seed_from(text: str) -> int:
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")


def random_vector(d: int, seed: int) -> np.ndarray:
    """A bipolar (+1/-1) vector of dimension ``d``, deterministic in ``seed``."""
    rng = np.random.default_rng(int(seed))
    return (rng.integers(0, 2, size=d, dtype=np.int8) * 2 - 1).astype(np.int8)


def bind(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Elementwise product; its own inverse: bind(bind(x, y), y) == x."""
    return (x * y).astype(np.int8)


def bundle(vectors) -> np.ndarray:
    """Majority vote (sign of the sum); ties resolve to +1, deterministically."""
    vectors = list(vectors)
    if not vectors:
        raise ValueError("bundle of nothing")
    total = np.sum(np.stack(vectors).astype(np.int32), axis=0)
    return np.where(total >= 0, 1, -1).astype(np.int8)


def permute(x: np.ndarray, shift: int = 1) -> np.ndarray:
    """Cyclic shift by ``shift`` positions (``permute(permute(x, k), -k) == x``)."""
    return np.roll(x, int(shift)).astype(np.int8)


def similarity(x: np.ndarray, y: np.ndarray) -> float:
    """Normalized dot product in [-1, 1]; two random vectors are near 0."""
    return float(np.dot(x.astype(np.int32), y.astype(np.int32))) / len(x)


def similarities(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    if len(matrix) == 0:
        return np.zeros(0)
    return (matrix.astype(np.int32) @ query.astype(np.int32)) / len(query)


def top_k(query: np.ndarray, matrix: np.ndarray, k: int) -> list:
    """Indices of the ``k`` rows of ``matrix`` most similar to ``query``, with similarities."""
    sims = similarities(query, matrix)
    order = np.argsort(-sims, kind="stable")[:max(int(k), 0)]
    return [(int(i), float(sims[i])) for i in order]


def analogy(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
    """``A : B :: C : D`` (original core ``HDCAnalogicalTransfer.transfer``): D = C ⊗ (A ⊗ B)."""
    return bind(c, bind(a, b))


def encode_sequence(vectors) -> np.ndarray:
    """Position-permuted bundling of a sequence of vectors (original core §14 ``hdv_encode``)."""
    vectors = list(vectors)
    if not vectors:
        raise ValueError("empty sequence")
    return bundle(permute(v, i) for i, v in enumerate(vectors))


class Codebook:
    """Symbol -> fixed random vector, grown on demand; deterministic in (seed, symbol)."""

    def __init__(self, seed: int, d: int = DEFAULT_D):
        self.seed = int(seed)
        self.d = int(d)
        self._vectors: dict = {}

    def __call__(self, symbol: str) -> np.ndarray:
        vector = self._vectors.get(symbol)
        if vector is None:
            vector = random_vector(self.d, _seed_from(f"{self.seed}:{symbol}"))
            self._vectors[symbol] = vector
        return vector

    def __len__(self) -> int:
        return len(self._vectors)

    def cleanup(self, query: np.ndarray, symbols=None) -> tuple:
        """The known symbol nearest to ``query`` and its similarity."""
        names = list(self._vectors if symbols is None else symbols)
        if not names:
            return None, 0.0
        matrix = np.stack([self(name) for name in names])
        index, score = top_k(query, matrix, 1)[0]
        return names[index], score

    def encode_value(self, value) -> np.ndarray:
        """A bipolar vector for an int, bool or (nested) list, from this codebook."""
        if type(value) is bool:
            return self(f"bool:{value}")
        if type(value) is int:
            return self(f"int:{max(-64, min(64, value))}")
        if isinstance(value, (list, tuple)):
            if not value:
                return self("list:empty")
            return encode_sequence(self.encode_value(v) for v in value)
        return self(f"other:{type(value).__name__}")

    def encode_examples(self, examples) -> np.ndarray:
        """Task signature: bundle over (position ⊗ input ⊗ output) of the public examples."""
        parts = []
        for index, item in enumerate(examples):
            inputs, output = item["inputs"], item["output"]
            parts.append(bind(self(f"pos:{index}"), bind(self.encode_value(inputs[0]),
                                                       permute(self.encode_value(output), 1))))
        return bundle(parts)

    def encode_tokens(self, tokens) -> np.ndarray:
        """Program fragment vector: position-permuted bundle of token vectors."""
        tokens = list(tokens)
        if not tokens:
            return self("tokens:empty")
        return encode_sequence(self(f"tok:{t}") for t in tokens)


class Region:
    """One agent's region: an item memory of vectors with integer tags (ids are the agent's own)."""

    def __init__(self, d: int):
        self.d = int(d)
        self._rows: list = []
        self._tags: list = []

    def write(self, vector: np.ndarray, tag: int) -> None:
        if not isinstance(vector, np.ndarray) or vector.shape != (self.d,):
            raise TypeError("region writes are vectors of the field's dimension")
        self._rows.append(vector.astype(np.int8))
        self._tags.append(int(tag))

    def matrix(self) -> np.ndarray:
        if not self._rows:
            return np.zeros((0, self.d), dtype=np.int8)
        return np.stack(self._rows)

    def tags(self) -> list:
        return list(self._tags)

    def summary(self) -> np.ndarray:
        return bundle(self._rows) if self._rows else np.zeros(self.d, dtype=np.int8)

    def __len__(self) -> int:
        return len(self._rows)

    def norm(self) -> float:
        """Mean absolute similarity between consecutive items: how structured the region is."""
        if len(self._rows) < 2:
            return 0.0
        return float(np.mean([abs(similarity(a, b)) for a, b in zip(self._rows, self._rows[1:])]))


class Field:
    def __init__(self, d: int = DEFAULT_D, shuffled: bool = False, seed: int = 0):
        self.d = int(d)
        self.breaker = Region(self.d)
        self.builder = Region(self.d)
        self.shuffled = bool(shuffled)
        self._permutation = (np.random.default_rng(_seed_from(f"shuffle:{seed}")).permutation(self.d)
                             if shuffled else None)

    def _store(self, region: Region, vector: np.ndarray, tag: int) -> None:
        if self._permutation is not None:
            vector = vector[self._permutation]
        region.write(vector, tag)

    def port(self, agent: str) -> "Port":
        if agent == "breaker":
            own, other = self.breaker, self.builder
        elif agent == "builder":
            own, other = self.builder, self.breaker
        else:
            raise KeyError(agent)
        store = self._store
        return Port(lambda vector, tag, own=own: store(own, vector, tag), other, self.d)

    def statistics(self) -> dict:
        return {"breaker_items": len(self.breaker), "builder_items": len(self.builder),
                "breaker_norm": self.breaker.norm(), "builder_norm": self.builder.norm()}


class Port:
    """What an agent holds: write to its own region, read the other's. Vectors only."""

    def __init__(self, store, other: Region, d: int):
        self._store = store            # write callable; the Port holds no reference to the Field
        self._other = other
        self.d = int(d)

    def write(self, vector: np.ndarray, tag: int = 0) -> None:
        self._store(vector, tag)

    def read(self) -> np.ndarray:
        """The other agent's items as a matrix (n x D)."""
        return self._other.matrix()

    def read_tags(self) -> list:
        return self._other.tags()

    def read_summary(self) -> np.ndarray:
        return self._other.summary()
