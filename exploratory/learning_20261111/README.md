# Set aside: a learned search policy for the list domain

Development code of 2026-11-11, written before the Owner's directive of the same day and
stopped by it. A small network (NumPy, Adam, an output layer that can grow) is trained on the
list-domain engine's own experience to rank which routines a task needs; `train_policy.py`
prints how often every routine of a solved task is among the K most likely. It was never used
in a registered run and nothing here is evidence. The list domain is no longer a primary
experimental domain (`rsi6/OWNER_DIRECTIVE.md`).
