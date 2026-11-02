"""Registry type for actions beyond the v0.4.0 core set (intentions, experiments, memory)."""
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Spec:
    """``run(world, agent, params, payload)`` must validate completely *before* mutating
    anything and return an error string, or ``None`` after performing the action."""
    required: frozenset
    run: Callable
    optional: frozenset = frozenset()
    min_age: float = 3.0
    skill: str = ""

    def accepts(self, params):
        keys = set(params)
        return self.required <= keys <= (self.required | self.optional)
