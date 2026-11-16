"""C1's search engine: bottom-up enumeration with observational equivalence.

``bottomup.py`` builds programs of size n from programs of size < n in typed contexts
(one per lambda-binder chain), keeps one program per behaviour on the task's public
inputs plus the frozen probe set (``oe.py``), skips terms that are not in the normal
form of ``NORMAL_FORMS.md`` (``normal_forms.py``), and evaluates with vectorised
primitive operations for first-order constructions and compiled Python closures for
higher-order ones (``closures.py``). The budget unit is one candidate evaluation: one
constructed term evaluated on the example set.
"""
