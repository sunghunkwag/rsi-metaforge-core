"""RSI-3: a memory-feedback adaptive core built on the frozen RSI-2 synthesizer.

RSI-3 does not modify RSI-2 or the legacy runtime. It imports RSI-2's frozen
DSL, evaluator, enumerator, corpus, and sleep-phase learners, and replaces only
the wake phase's compute allocation with a closed loop:

    experience -> episodic memory -> pathway control -> execution
               -> frozen external verification -> policy update

See ARCHITECTURE.md for the component map and the evidence behind each design
decision, and OWNER_DIRECTIVE.md for scope.
"""
