"""Designs q and r in the kernel's dispatch, at run time.

``rsi6/learner/designs.py`` is pinned by hash by the open registration until its last stage has
run, so it does not name designs q and r. A driver that is registered to measure them calls
``install()`` before it measures anything; the dispatch of that process (and of the workers it
forks) then knows them. Records of the other designs go through ``designs.py`` unchanged: the
same digests, the same learner classes.
"""
from __future__ import annotations

from rsi6.learner import design_q, design_r, designs

_MODULES = {"q": design_q, "r": design_r}
_CLASSES = {"q": design_q.LearnerQ, "r": design_r.LearnerR}


def install() -> None:
    if getattr(designs, "_extra_installed", False):
        return
    make, module = designs.make, designs._module

    def make_extra(version):
        kind = version.get("design")
        return _CLASSES[kind](version) if kind in _CLASSES else make(version)

    def module_extra(version):
        return _MODULES.get(version.get("design"), None) or module(version)

    designs.make = make_extra
    designs._module = module_extra
    designs._extra_installed = True
