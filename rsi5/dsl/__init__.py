"""The RSI-5 fast-closure language C1: a fork of RSI-2's typed functional DSL.

Forked from ``rsi2/types.py``, ``terms.py``, ``evaluator.py`` and ``grammar.py``
(OWNER_DIRECTIVE.md §3.1). The originals are never edited. Changes:

* a ``pair`` type and the primitives ``pair``, ``fst``, ``snd``, ``zip``;
* the restored DreamCoder primitives ``unfold``, ``index``, ``fix1``, ``is_prime``,
  ``is_square`` and the integer constants 3, 4, 5 (``VOCABULARY.md``);
* a ``Vocabulary`` (``vocabulary.py``) selects which primitives and constants a search
  may use; the evaluator understands every primitive in ``PRIMITIVE_TYPES``;
* every primitive terminates under the interpreter's step budget and no primitive raises
  an escaping exception (``evaluator.py``).
"""
