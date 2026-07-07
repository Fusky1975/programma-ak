"""Shared test helpers."""

from __future__ import annotations

import random


class ScriptedRandom(random.Random):
    """A Random whose .random()/.choice() replay a fixed script, for deterministic tests.

    random.Random.uniform() calls self.random() internally, so scripting
    .random() also controls .uniform(); .choice() is overridden directly
    since CPython's implementation uses _randbelow (bit generation), not
    .random().
    """

    def __init__(self, randoms, choice_indices=()):
        super().__init__()
        self._randoms = list(randoms)
        self._choice_indices = list(choice_indices)

    def random(self):
        return self._randoms.pop(0)

    def choice(self, seq):
        return seq[self._choice_indices.pop(0)]
