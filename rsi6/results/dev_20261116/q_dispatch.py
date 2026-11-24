"""Development only: make the kernel's design dispatch know design q in THIS process (and in the
worker processes it forks), without changing rsi6/learner/designs.py, which the registered open
experiment pins by hash until its last stage has run."""
from rsi6.learner import designs, design_q

_make, _module = designs.make, designs._module


def make(version):
    return design_q.LearnerQ(version) if version.get("design") == "q" else _make(version)


def module(version):
    return design_q if version.get("design") == "q" else _module(version)


designs.make = make
designs._module = module
