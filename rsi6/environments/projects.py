"""Single-mode resource-constrained project scheduling: the sets j30 and j60 of PSPLIB (R. Kolisch, A. Sprecher).

Published form. An instance file (.sm, in the archives j30.sm.tgz and j60.sm.tgz, which are read in
memory and parsed as text) describes one project of J jobs (32 in j30, 62 in j60). Job 1 and job J
are the "supersource" and the "supersink" (the file's words): duration 0, no request. Every other
job j has a duration d(j) in whole periods (1 to 10 in these sets) and requests r(j,k) units of
each renewable resource k in every period in which it is in process; resource k has R(k) units in
every period (section RESOURCEAVAILABILITIES); the section PRECEDENCE RELATIONS lists the
successors of every job. A schedule gives every job a start time S(j) >= 0. It is valid when every
job starts after each of its predecessors has finished (S(j) >= S(i) + d(i)) and in every period t
the jobs in process (S(j) <= t < S(j) + d(j)) request together at most R(k) of every resource k.
Its value is the makespan, the time at which the last job finishes (the start of the supersink),
to be made small. Every file of both sets has one mode per job, four renewable resources and no
nonrenewable or doubly constrained resource (checked on every file): this is the single-mode
problem. The fields rel.date, duedate and tardcost of the project line belong to no part of this
problem and are not used; the fields MPM-Time and horizon are used as checks only (MPM-Time must be
the critical-path length the adapter computes, see Instances left out; horizon must be the sum of
the durations, see the score).

Reference, and where each value comes from. The data page (getdata.php?mode=sm, pinned as
getdata_sm.html) says what each file holds; its statements "480 instances (fully optimal)" for
j30 and "382/480 proven optimal" for j60 are checked when the environment is built.
  j30: the file j30opt.sm ("OPT (Optimal Solutions): Solutions for which optimality has been
  formally proven"), one line "parameter instance makespan cpu-time" per instance, the third
  number taken: 480 proven optimal makespans.
  j60: the file j60hrs.sm ("HRS (Heuristic Solutions): Best known feasible solutions obtained by
  heuristic methods. These solutions are not guaranteed to be optimal"), one line "par inst
  makespan date author" per instance, the third number taken: 480 makespans of valid schedules
  reported to the library, that is upper bounds. The file j60lb.sm gives lower bounds (third
  number) for the 410 instances of classes 1 to 41. Where the lower bound equals the reference
  (382 instances) the library has proven the reference optimal. Of the other 98, 46 (all of
  classes 42 to 48, for which j60lb.sm gives no bound) have a reference equal to the critical-path
  length of the instance, the largest sum of durations along a chain of activities each of which
  precedes the next (see Instances left out); no schedule is shorter, so these references are
  optima too, although the library does not mark them. On the remaining 52 (28 of classes 1 to 41 whose lower bound is smaller, 24 of classes 42
  to 48) the reference is an upper bound only, and an answer can beat it. Among the 720 instances
  used (see Instances left out): 360 j30 optima, 308 j60 optima (282 proven by the library, 26 by
  the critical-path length) and the 52 upper bounds, none of which is left out. ``reference_kind``
  says which.
  A line of a solution file is read when it begins with three whole numbers, and every pair (class,
  instance) must be listed exactly once. The site's JSON summaries j30.json and j60.json are pinned
  too and must state the same values and the same proven or unproven status as the library's
  files for every instance (checked when the environment is built; like the files, they mark the
  382 proofs of the library, not the 46 by the critical-path length). No reference is below the
  critical-path length (checked). The source publishes values only, no schedule of any instance:
  there is no reference answer to score.

Instances left out: those whose earliest-start schedule already fits. The earliest-start schedule
starts every activity as soon as all of its predecessors have finished, the resources disregarded
(a forward pass over the durations and the successor lists of the file); its makespan is the
critical-path length, which equals the field MPM-Time on every file (checked when the environment
is built). When this schedule requests at most R(k) of every resource k in every period, every list
in precedence order denotes exactly this schedule under the rule of the answer form below. By
induction along the list: the activities placed before the next activity j stand at their earliest
starts, its predecessors among them; so (a) allows j no start before its own earliest start, and in
each period from there to its end they request, together with j, no more than the whole
earliest-start schedule does in that period, which fits; so the rule places j at its earliest
start. Every valid answer then has the critical-path length as its makespan, which no schedule
beats, and scores 1: such an instance measures nothing. The test reads the instance file only
(durations, successors, requests, capacities), never a reference value. On the pinned files it
leaves out exactly the 240 instances of the 24 classes with resource strength RS = 1 (classes 4, 8,
..., 48 of both sets; checked when the environment is built), and 720 instances remain, 360 of each
set. It was added after an audit had found that every valid answer scores 1 on these instances
(17 of the 24 fresh instances of the kernel's split were among them before).

Answer form. The variables are the positions 0..n-1 of a list, assigned in index order; the options
are the n = J - 2 real jobs (activity p is job p + 2 of the file), each with capacity one, so a
complete answer is a permutation of the activities: an activity list. The schedule an answer denotes
is fixed by one rule, the serial schedule-generation rule: the activities are taken in list order,
and each starts at the earliest whole period t at which (a) every predecessor that stands before it
in the list has finished and (b) in each period from t to t + d - 1 every resource has enough units
left beside the activities already placed. The rule compares no alternatives: it takes the
activities in the order the answer gives and never moves one once placed. But it is a decoding
chosen by this adapter, not part of the benchmark, and it shapes difficulty: it does part of the
scheduling (every activity starts as early as the ones placed before it allow), many lists denote
the same schedule, and what an answer decides is the order in which the activities claim the
resources.

The answer form and the published problem, exactly:
  (1) Every list in precedence order (every activity after all of its predecessors) denotes a valid
  schedule: precedence holds by (a), the capacities by (b), and a start time always exists, since
  once every activity placed so far has finished every resource is free and no request exceeds its
  capacity (checked on every file).
  (2) For every valid schedule S, the list of the activities by start time in S (ties in any order:
  every real activity lasts at least one period, so a tie never puts an activity before one of its
  predecessors) denotes a schedule in which no activity starts later than in S. By induction along
  the list: the activities placed before activity j start no later than in S and last as long, so
  in every period from S(j) on they occupy no more than they do in S, where j fits beside them; its
  predecessors finish no later; so the rule places j at S(j) or earlier. Hence the published optimum
  is the makespan of the schedule of some list, and no list beats a proven optimum.
  (3) Not every optimal schedule is itself the schedule of a list. The schedules of lists are
  exactly the active ones, those that no other valid schedule improves by starting some activity
  earlier and none later: if one did, the first activity of the list that starts earlier in it
  would have fitted there when the rule placed it; and by (2) an active schedule is the schedule of
  its own list by start time. A valid schedule that is not active (an optimal one among them) is not
  an answer of this form, but its list by start time is, and is no longer.
  (4) The supersource and the supersink are not in the answer: they last no time and request
  nothing, and job 1 is the only job without a predecessor and job J the only one without a
  successor (checked), so the supersource starts at 0 and the makespan is the largest finish time of
  the real jobs. Arcs from job 1 and arcs to job J are dropped; every other arc is kept.
  (5) A list not in precedence order is an invalid answer: the hard group [2] counts every activity
  placed before one of its predecessors, and the score is 0, whether or not the schedule the list
  denotes breaks a precedence relation. It need not: the rule places such an activity without
  waiting for its missing predecessors, and the resources may push it past their finish, so that
  the schedule meets every published constraint (measured outside the adapter: of 199 lists made
  from random lists in precedence order by exchanging an adjacent predecessor and successor, 51
  denote such a schedule). Nothing reachable is lost: by (2), the list by start time of any valid schedule is in precedence order
  and denotes a schedule that is no longer.

Groups. The activity at position p gets its start and finish time from positions 0 to p, so a term
of position p counts as soon as positions 0 to p are assigned (the totals of a partial list are
those of its assigned prefix):
  [0] the makespan of the activities placed so far, the largest of their finish times (soft; for a
      complete list in precedence order it is the published objective);
  [1] the sum of the finish times of the activities placed so far (detail: the terms whose largest
      is [0]; it is not part of the cost, it says what each newly determined finish time is);
  [2] the number of activities placed while one of their predecessors is not yet placed, that is
      placed before one of their predecessors (hard: zero exactly when the list is in precedence
      order). Such an activity is placed by (a) and (b) without waiting for its missing
      predecessors; the schedule may then break a precedence relation or, when the resources push
      the activity past them, may not; either way the answer is invalid whatever [0] is (see (5)).
What these choices give the learner, said plainly: the change of [1] tells, for every activity,
when it would finish if it were placed next, and the change of [2] whether its predecessors are all
placed. A published instance says neither; the evaluator does, by the rule.

Exposed arrays, each a field of the instance file: opt_attr[o] = (d, r(.,1), ..., r(.,4), R(1), ...,
R(4)), the duration and the four requests of the activity and the four capacities of the instance,
the capacities the same in every row (the generic form has no place for an attribute of a
resource; this way the request and the capacity of a resource stand side by side); opt_opt[0][o, o']
= 1 when the file lists o' among the successors of o (real jobs only), a directed relation, not
symmetric. Nothing else is exposed: no attribute of a position, no relation of positions, nothing of
the project line (due date, tardiness cost, the critical-path length MPM-Time), not the horizon,
and nothing the adapter keeps for the kernel (the critical-path length it computes, the test of
Instances left out, the kind of the reference). Activities and resources are relabelled with the
seed (positions are not: the list is ordered), and decode maps an answer to the file's activity
indices. The relabelling matters here: the file numbers the jobs in a precedence order (every
successor has a larger number, checked), and that list is already good (its schedule scores 0.916
on j30 and 0.948 on j60 on average over the 720 instances, measured outside the adapter).

One layout: every instance has the same three groups, nine activity attributes, one relation between
activities, capacity one on every option and ordered variables; j30 instances have 30 activities and
j60 instances 60, which the layout allows; nothing is padded (every file has four resources).

Score. An answer that is a permutation of the activities (of an integer type) in precedence order
scores (Z - M) / (Z - ref), cut to [0, 1]: M the makespan of its schedule by the rule, ref the
reference, Z the sum of the durations of all activities, the makespan of doing one activity at a
time. Z is exact (no sampler; it is the field horizon of every file, checked). Every list in
precedence order has M <= Z under the rule (the k-th activity starts at the latest when the k - 1
before it have all finished), so a valid answer lies in [0, 1] before the cut; the score is 1 at the
reference, and the cut at 1 matters only on the 52 j60 instances whose reference is an upper bound
only. Any other answer scores 0 and is never repaired. Z exceeds the reference on every instance,
by 40 periods at least. Said plainly, Z is the worst a valid list can do under the rule, not what a
random one does: lists drawn by taking at each position one of the activities whose predecessors
are all placed, uniformly at random, scored 0.889 on j30 (makespans 17.2 % above the reference on
average) and 0.928 on j60 (20.0 %), with 3 lists per instance on the 720 instances, measured outside
the adapter after the threshold had been fixed. The scale is compressed at the top: 0.01 of score
is about 1.8 % of makespan on j30 and 3.2 % on j60.

Threshold: an operating point, not an external fact. It is the mean score that schedules five per
cent longer than the reference would get on the same instances (``threshold_for``; ``threshold`` is
its value on the 24 fresh instances of the kernel's split, 0.9864; over all 720 instances 0.9760; per
instance from 0.844 to 0.991). The five per cent is this builder's choice, fixed before any answer
was scored on these instances and before the random lists above were drawn; nothing was measured to
set it. It is computed from the durations and the reference values alone. The test of Instances
left out came later, after an audit; it changed which instances are fresh, not the five per cent.
On the 52 instances whose reference is an upper bound only, five per cent above it is no harder
than five per cent above the optimum.
What reaches it, measured outside the adapter after both were fixed, on the 24 fresh instances
(threshold 0.9864; halves 0.9876 and 0.9840): one random list in precedence order per instance, as
above, has a mean score of 0.970 (200 draws: from 0.960 to 0.978, none reaches the threshold). The
latest-finish-time rule of the textbooks reaches it: at each position it takes, among the
activities whose predecessors are all placed, the one whose latest finish time is smallest (one
backward pass from the critical-path length over the durations and the successor relation, both
exposed; ties at random), and its list, decoded by the same serial rule, scores 0.9989 on the fresh
instances (0.9982 to 0.9996 over 20 draws of the ties) and more than the threshold on both halves.
On the 16 training instances it scores 0.950 against their threshold 0.9726 (random lists 0.887),
and 0.945 on the 360 j30 and 0.968 on the 360 j60 instances (one draw each): the three fresh
classes are easy ones for this rule. A mean score at the threshold on this category is therefore not by itself a
capability beyond this one-pass rule; an operating point above it would have to be fixed again,
before any answer of a learner is scored here (this adapter does not do that).

Groups of instances: the published generation parameter classes. The file j30<P>_<I>.sm (or
j60<P>_<I>.sm) is instance I of class P of its set; the parameter file par.sm, pinned, lists for each
set the 48 classes by network complexity NC (1.5, 1.8, 2.1), resource factor RF (0.25, 0.5, 0.75, 1)
and resource strength RS (0.2, 0.5, 0.7, 1). A group is a set and a class, "j30-10" for example: 72
groups of ten instances remain (the 24 classes with RS = 1 are left out, see Instances left out),
each generated from one base-data file (its "file with basedata" line, checked for all 96 classes;
the number in that file name is not the class number). The j30 and the j60 class of the same number
share NC, RF and RS but not the number of jobs, which par.sm sets as a generation parameter too (30,
adapted to 60), so they are different groups. Outside the adapter: the class in the file name is
the class of par.sm (the arcs per job of every file lie within 0.025 of its class's NC and the share
of nonzero requests within 0.009 of its RF; par.sm states a tolerance of 0.05).
split(env, 16, 24) puts the groups j60-2 (NC 1.5, RF 0.25, RS 0.5), j60-11 (1.5, 0.75, 0.7) and
j60-43 (2.1, 0.75, 0.7) on the fresh side (their 30 instances cut to 24) and 16 instances of 13 other
groups on the training side, no class number on both sides; halves() puts j60-2 and j60-11 in one
half (16 instances) and j60-43 in the other (8).

Size rule (the one of the other adapters, fixed before anything was scored): at most 1,000 variables
and variables times options at most 30,000. j30 has 30 x 30 = 900 and j60 60 x 60 = 3,600, so all 960
instances pass it; the 240 of Instances left out are left out for the reason given there, not by
this rule, and 720 are used. One construction of the largest instance costs
60 x 61 + 1 = 3,661 units. Left out: the sets j90 and j120 of the same page, which the size rule
would admit (8,100 and 14,400): this category is defined as j30 and j60 (the data page gives 375/480
and 89/600 proven optima for those two). The other problems of PSPLIB (several modes, time lags,
resource investment) are other problems.
"""
from __future__ import annotations

import io
import json
import re
import tarfile

import numpy as np

from rsi6 import fetch
from rsi6.kernel.environment import Environment, relabel, split
from rsi6.kernel.problem import AssignProblem

SETS = ("j30", "j60")                 # the instance sets of this category
RESOURCES = 4                         # renewable resources in every file of both sets (checked on every file)
CLASSES = 48                          # generation parameter classes of each set (par.sm), ten instances each
N_INSTANCES = 720                     # 960 published; the 240 whose earliest-start schedule fits are left out
MAX_VARS, MAX_CELLS = 1000, 30000     # the size rule
EXCESS = 0.05                         # the threshold: makespans five per cent longer than the reference


def _count(text: str, pattern: str) -> int:
    found = re.findall(pattern, text)
    if len(found) != 1:
        raise ValueError(f"the instance file does not have the published format ({pattern})")
    return int(found[0])


def _numbers(text: str, title: str) -> list:
    """The lines of whole numbers of one section of an instance file: after its title, up to the
    next line of stars (header and rule lines carry words or dashes and are not kept)."""
    if text.count(title) != 1:
        raise ValueError(f"the instance file has not exactly one section {title}")
    body = text.split(title, 1)[1].split("****", 1)[0]
    return [[int(x) for x in line.split()] for line in body.splitlines()
            if line.split() and all(re.fullmatch(r"\d+", x) for x in line.split())]


def parse(text: str) -> dict:
    """One instance file (.sm) in the published format. The real jobs 2..J-1 of the file become
    the activities 0..J-3; the supersource (job 1) and the supersink (job J) are checked and dropped.
    Also the critical-path length (checked against MPM-Time) and whether the earliest-start schedule
    fits, both for the kernel only."""
    jobs = _count(text, r"jobs \(incl\. supersource/sink \):\s*(\d+)")
    if (_count(text, r"projects\s*:\s*(\d+)"), _count(text, r"- renewable\s*:\s*(\d+)\s*R"),
            _count(text, r"- nonrenewable\s*:\s*(\d+)\s*N"), _count(text, r"- doubly constrained\s*:\s*(\d+)\s*D")) \
            != (1, RESOURCES, 0, 0):
        raise ValueError("not one project with four renewable and no other resources")
    horizon = _count(text, r"horizon\s*:\s*(\d+)")
    info = _numbers(text, "PROJECT INFORMATION:")
    if len(info) != 1 or len(info[0]) != 6 or info[0][1] != jobs - 2:
        raise ValueError("the project line does not give the number of real jobs")
    prec = _numbers(text, "PRECEDENCE RELATIONS:")
    rows = _numbers(text, "REQUESTS/DURATIONS:")
    avail = _numbers(text, "RESOURCEAVAILABILITIES:")
    if [p[0] for p in prec] != list(range(1, jobs + 1)) or [r[0] for r in rows] != list(range(1, jobs + 1)):
        raise ValueError("jobs are not listed 1..J")
    if any(p[1] != 1 or len(p) != 3 + p[2] for p in prec) or any(r[1] != 1 or len(r) != 3 + RESOURCES for r in rows):
        raise ValueError("a job has more than one mode or a malformed line")
    if len(avail) != 1 or len(avail[0]) != RESOURCES:
        raise ValueError("no line of resource availabilities")
    succ = {p[0]: p[3:] for p in prec}
    duration = np.array([r[2] for r in rows], dtype=np.int64)
    request = np.array([r[3:] for r in rows], dtype=np.int64)
    capacity = np.array(avail[0], dtype=np.int64)
    if any(not all(j < k <= jobs for k in succ[j]) for j in succ):
        raise ValueError("a successor does not have a larger number (the numbering is not topological)")
    has_pred = np.zeros(jobs + 1, dtype=bool)
    for j in succ:
        has_pred[succ[j]] = True
    if has_pred[1] or not has_pred[2:].all() or succ[jobs] or not all(succ[j] for j in range(1, jobs)):
        raise ValueError("job 1 is not the only job without a predecessor or job J not the only one without a successor")
    if duration[0] or duration[-1] or request[0].any() or request[-1].any():
        raise ValueError("the supersource or the supersink has a duration or a request")
    if np.any(request > capacity):
        raise ValueError("a job requests more of a resource than its capacity: no schedule exists")
    if horizon != int(duration.sum()):
        raise ValueError("the horizon is not the sum of the durations")
    n = jobs - 2
    pred = np.zeros((n, n), dtype=bool)                  # pred[i, k]: activity i is a direct predecessor of k
    for j in range(2, jobs):
        for k in succ[j]:
            if k < jobs:
                pred[j - 2, k - 2] = True
    span, fits = earliest(duration[1:-1], request[1:-1], capacity, pred)
    if span != info[0][5]:
        raise ValueError("the critical-path length is not the field MPM-Time of the project line")
    base = re.findall(r"file with basedata\s*:\s*(\S+)", text)
    return {"duration": duration[1:-1].copy(), "request": request[1:-1].copy(), "capacity": capacity, "pred": pred,
            "span": span, "fits": fits, "base": base[0] if len(base) == 1 else None}


def earliest(duration, request, capacity, pred):
    """The precedence-only earliest-start schedule: every activity starts when the last of its
    predecessors has finished, the resources disregarded (a forward pass in the file's numbering,
    which is topological, checked in ``parse``). Returns its makespan, the critical-path length,
    and whether it requests at most the capacity of every resource in every period."""
    n = len(duration)
    start = np.zeros(n, dtype=np.int64)
    for k in range(n):
        before = np.flatnonzero(pred[:, k])
        if len(before):
            start[k] = int(np.max(start[before] + duration[before]))
    span = int(np.max(start + duration, initial=0))
    load = np.zeros((span + 1, len(capacity)), dtype=np.int64)
    for j in range(n):
        load[start[j]:start[j] + duration[j]] += request[j]
    return span, bool(np.all(load <= capacity))


def parse_values(text: str) -> dict:
    """``{(parameter, instance): value}`` from a solution file of the library: the lines that start
    with three whole numbers (class, instance, makespan or bound); a pair listed twice is an error."""
    out = {}
    for line in text.splitlines():
        found = re.match(r"\s*(\d+)\s+(\d+)\s+(\d+)(\s|$)", line)
        if found:
            key = (int(found.group(1)), int(found.group(2)))
            if key in out:
                raise ValueError(f"{key} is listed twice")
            out[key] = int(found.group(3))
    return out


def parse_classes(text: str, name: str) -> dict:
    """``{parameter: (NC, RF, RS)}`` of one instance set from the parameter file par.sm."""
    body = text.split(f"Instance Sets: {name.upper()}", 1)[1].split("Instance Sets:", 1)[0]
    out = {}
    for line in body.splitlines():
        parts = line.split()
        if len(parts) == 4 and re.fullmatch(r"\d+", parts[0]):
            out[int(parts[0])] = tuple(float(x) for x in parts[1:])
    return out


def serial(duration, request, capacity, preds, order):
    """The schedule a list denotes, by the serial rule of the module text (plain reference code).
    ``order``: activities in list order (a prefix of a list is allowed). Returns the start and the
    finish time of every listed activity (-1 for the others) and the number of listed activities
    that were placed while one of their predecessors was not yet placed."""
    n = len(duration)
    load = np.zeros((int(np.sum(duration)) + 1, len(capacity)), dtype=np.int64)    # every period a schedule of the rule can use
    start, finish = np.full(n, -1, dtype=np.int64), np.full(n, -1, dtype=np.int64)
    late = 0
    for j in order:
        j = int(j)
        placed = [int(finish[i]) for i in preds[j] if finish[i] >= 0]
        if len(placed) < len(preds[j]):
            late += 1
        t, d = max(placed, default=0), int(duration[j])
        while np.any(load[t:t + d] + request[j] > capacity):
            t += 1
        load[t:t + d] += request[j]
        start[j], finish[j] = t, t + d
    return start, finish, late


class ProjectProblem(AssignProblem):
    """Positions are the variables (in index order), activities the options (capacity one).
    ``duration[o]``, ``request[o, k]``: activity o; ``supply[k]``: capacity of resource k;
    ``pred[i, o]``: activity i is a direct predecessor of activity o."""

    def __init__(self, duration, request, supply, pred, meter):
        n = len(duration)
        self.duration, self.request, self.supply, self.pred = duration, request, supply, pred
        self.preds = tuple(np.flatnonzero(pred[:, o]) for o in range(n))
        self.succs = tuple(np.flatnonzero(pred[o]) for o in range(n))
        self.periods = int(duration.sum()) + 1
        attr = np.column_stack([duration, request, np.tile(supply, (n, 1))]).astype(float)
        super().__init__(n_vars=n, n_opts=n, hard=[False, False, True], detail=[False, True, False], ordered=True,
                         capacity=np.ones(n, dtype=np.int64), opt_attr=attr, opt_opt=(pred.astype(float),), meter=meter)

    def partial_totals(self, a):
        a = np.asarray(a, dtype=np.int64)
        first = np.flatnonzero(a < 0)
        order = a[:first[0]] if len(first) else a              # the term of a position reads every earlier position
        _, finish, late = serial(self.duration, self.request, self.supply, self.preds, order)
        done = finish[order]
        return np.array([float(done.max(initial=0)), float(done.sum()), float(late)])

    # ---- fast exact state: the resource profile, the earliest start and the missing predecessors
    def _new(self):
        s = super()._new()
        s["load"] = np.zeros((self.periods, len(self.supply)), dtype=np.int64)
        s["ready"] = np.zeros(self.n_opts, dtype=np.int64)               # latest finish of the placed predecessors
        s["missing"] = self.pred.sum(axis=0).astype(np.int64)           # predecessors not yet placed
        return s

    def _starts(self, s, acts):
        """The start time the rule gives each of these activities if it were placed next."""
        span = np.arange(self.periods)
        fits = np.all(self.request[acts][:, None, :] <= (self.supply - s["load"])[None, :, :], axis=2)
        blocked = np.minimum.accumulate(np.where(fits, self.periods, span)[:, ::-1], axis=1)[:, ::-1]
        ok = (span[None, :] >= s["ready"][acts][:, None]) & (blocked - span[None, :] >= self.duration[acts][:, None])
        if not ok.any(axis=1).all():
            raise RuntimeError("no start time within the periods of the rule")
        return np.argmax(ok, axis=1)

    def _rows(self, s, variables):
        variables = np.asarray(variables, dtype=np.int64)
        out = np.zeros((len(variables), self.n_opts, 3))
        for i, v in enumerate(variables):
            if not 0 <= v < self.n_vars:
                raise ValueError("no such variable")
            if v == s["n"]:
                acts = np.flatnonzero(s["used"] == 0)
                finish = self._starts(s, acts) + self.duration[acts]
                out[i, acts, 0] = np.maximum(finish - s["tot"][0], 0.0)
                out[i, acts, 1] = finish
                out[i, acts, 2] = s["missing"][acts] > 0
            elif v < s["n"]:                                      # a position already assigned: the slow exact rows
                out[i] = AssignProblem._rows(self, s, np.array([v]))[0]
            # a later position: none of its terms can be complete, so every change is zero
        return out

    def _push(self, s, v, o):
        if v != s["n"]:
            raise ValueError("variables of this problem are assigned in index order")
        t = int(self._starts(s, np.array([o]))[0])
        f = t + int(self.duration[o])
        s["load"][t:f] += self.request[o]
        late = 1.0 if s["missing"][o] > 0 else 0.0
        after = self.succs[o]
        s["ready"][after] = np.maximum(s["ready"][after], f)
        s["missing"][after] -= 1
        s["a"][v] = o
        s["tot"] = np.array([max(s["tot"][0], float(f)), s["tot"][1] + f, s["tot"][2] + late])


class Projects(Environment):
    name = category = "projects"
    form = "assign"
    threshold = 0.9864            # on the fresh instances of the kernel's split; set again in __init__ by threshold_for
    anchor = ("an operating point, not an external fact: the mean score that schedules five per cent longer than the "
              "published reference makespan (an optimum on j30 and on 308 j60 instances, 282 proven by the library and 26 "
              "by the critical-path length; the best known upper bound on the other 52) would get on the same instances. "
              "On the fresh instances of the kernel's split random lists in precedence order score 0.970 and do not "
              "reach it; the latest-finish-time priority rule of the textbooks (one backward pass, its list decoded by "
              "the same serial rule) scores 0.9989 there and reaches it; see the module text")

    def __init__(self):
        fetch.fetch("projects", quiet=True)
        read = lambda name: open(fetch.path("projects", name), encoding="latin-1").read()
        page = dict(re.findall(r"<b>(j\d+)</b></td>\s*<td>([^<]*)</td>", read("getdata_sm.html")))
        if page.get("j30") != "480 instances (fully optimal)" or page.get("j60") != "382/480 proven optimal":
            raise RuntimeError("the data page does not state the published status of j30 and j60")
        optimum30, best60, lower60 = parse_values(read("j30opt.sm")), parse_values(read("j60hrs.sm")), parse_values(read("j60lb.sm"))
        keys = {(p, i) for p in range(1, CLASSES + 1) for i in range(1, 11)}
        if set(optimum30) != keys or set(best60) != keys or not set(lower60) <= keys:
            raise RuntimeError("a solution file does not list every instance once")
        if any(lower60[k] > best60[k] for k in lower60):
            raise RuntimeError("a lower bound exceeds the best known makespan")
        proven60 = {k for k in lower60 if lower60[k] == best60[k]}
        summary = lambda name: json.loads(open(fetch.path("projects", name), encoding="utf-8").read())
        self._agree(summary("j30.json"), summary("j60.json"), optimum30, best60, lower60, proven60, keys)
        if len(proven60) != 382:
            raise RuntimeError("the lower bounds do not prove the 382 optima the data page states")
        self.instances, self.left_out = {}, []           # both kernel only
        for name in SETS:
            classes = parse_classes(read("par.sm"), name)
            if sorted(classes) != list(range(1, CLASSES + 1)):
                raise RuntimeError(f"par.sm does not list the {CLASSES} classes of {name}")
            bases, trivial = {}, set()
            with tarfile.open(fileobj=io.BytesIO(open(fetch.path("projects", f"{name}.sm.tgz"), "rb").read()), mode="r:gz") as tar:
                for member in tar.getmembers():
                    found = re.fullmatch(rf"{name}(\d+)_(\d+)\.sm", member.name)
                    if not member.isfile() or not found:
                        raise RuntimeError(f"{name}: unexpected archive member {member.name}")
                    key = (int(found.group(1)), int(found.group(2)))
                    inst = parse(tar.extractfile(member).read().decode("latin-1"))
                    bases.setdefault(key[0], set()).add(inst.pop("base"))
                    n = len(inst["duration"])
                    if n > MAX_VARS or n * n > MAX_CELLS:                 # the size rule (no instance of j30 or j60 fails it)
                        continue
                    if name == "j30":
                        value, proven = optimum30[key], True
                    else:
                        value, proven = best60[key], key in proven60
                    zero = int(inst["duration"].sum())
                    if zero <= value:
                        raise RuntimeError(f"{member.name}: the zero point is not above the reference")
                    if value < inst["span"]:
                        raise RuntimeError(f"{member.name}: the reference is below the critical-path length")
                    if inst.pop("fits"):                 # every valid answer denotes the earliest-start schedule and scores 1
                        trivial.add(key)
                        self.left_out.append(member.name[:-3])
                        continue
                    # an optimum when the library proves it, or when it equals the critical-path length, a lower bound
                    kind = "optimum" if proven or value == inst["span"] else "upper bound"
                    self.instances[member.name[:-3]] = dict(inst, set=name, cls=key[0], value=float(value), kind=kind,
                                                            zero=float(zero), params=classes[key[0]])
            if any(len(b) != 1 for b in bases.values()) or sorted(bases) != list(range(1, CLASSES + 1)):
                raise RuntimeError(f"{name}: a class is not one base-data file")
            if trivial != {(p, i) for p in classes if classes[p][2] == 1.0 for i in range(1, 11)}:
                raise RuntimeError(f"{name}: the instances left out are not exactly those of the classes with RS = 1")
        if len(self.instances) != N_INSTANCES:           # a file the source stopped serving must not shrink the set unseen
            raise RuntimeError(f"projects: {len(self.instances)} usable instances, {N_INSTANCES} expected")
        self.threshold = self.threshold_for(split(self, 16, 24)[1])

    @staticmethod
    def _agree(js30, js60, optimum30, best60, lower60, proven60, keys):
        """The site's JSON summaries must state the same values and the same proofs as the text files."""
        rows30 = {(r["parameter"], r["instance"]): r for r in js30["solutions"]}
        rows60 = {(r["parameter"], r["instance"]): r for r in js60["solutions"]}
        same = set(rows30) == keys == set(rows60) and len(js30["solutions"]) == len(js60["solutions"]) == len(keys)
        same = same and all(rows30[k]["optimal_makespan"] == optimum30[k] and rows30[k]["is_proven_optimal"] is True
                            for k in keys)
        same = same and all(rows60[k]["upper_bound"] == best60[k] and rows60[k].get("lower_bound") == lower60.get(k)
                            and rows60[k]["is_proven_optimal"] == (k in proven60) for k in keys)
        if not same:
            raise RuntimeError("the JSON summaries and the solution files disagree")

    def instance_ids(self):
        return sorted(self.instances)

    def reference(self, instance_id):
        return float(self.instances[instance_id]["value"])

    def reference_kind(self, instance_id):
        """``optimum`` (proven by the library, or equal to the critical-path length) or ``upper bound``
        (kernel only, for reports and audits)."""
        return self.instances[instance_id]["kind"]

    def group(self, instance_id):
        inst = self.instances[instance_id]
        return f"{inst['set']}-{inst['cls']}"            # the generation parameter class of its set

    def threshold_for(self, instance_ids):
        """The mean score of makespans ``EXCESS`` longer than the reference, on exactly these instances."""
        rows = [self.instances[i] for i in instance_ids]
        return float(np.mean([min(1.0, max(0.0, (r["zero"] - (1.0 + EXCESS) * r["value"]) / (r["zero"] - r["value"])))
                              for r in rows]))

    def problem(self, instance_id, meter, seed, training):
        inst = self.instances[instance_id]
        n = len(inst["duration"])
        rng = np.random.default_rng(seed)
        perm, _ = relabel(rng, n)                                    # new activity -> activity of the file
        res, _ = relabel(rng, RESOURCES)                             # new resource -> resource of the file
        problem = ProjectProblem(inst["duration"][perm], inst["request"][np.ix_(perm, res)], inst["capacity"][res],
                                 inst["pred"][np.ix_(perm, perm)], meter)

        def decode(answer):
            a = np.asarray(answer)
            if a.shape != (n,) or a.dtype.kind not in "iu" or a.min() < 0 or a.max() >= n:
                return a                                         # malformed: left as it is, and scored 0
            return perm[a.astype(np.int64)]

        return problem, decode

    def score(self, instance_id, answer):
        """``answer[p]``: the activity (0-based: job p + 2 of the file is activity p) at position p of the list."""
        inst = self.instances[instance_id]
        n = len(inst["duration"])
        a = np.asarray(answer)
        if a.shape != (n,) or a.dtype.kind not in "iu" or a.min() < 0 or a.max() >= n \
                or np.any(np.bincount(a.astype(np.int64), minlength=n) != 1):
            return 0.0
        a = a.astype(np.int64)
        preds = [np.flatnonzero(inst["pred"][:, o]) for o in range(n)]
        _, finish, late = serial(inst["duration"], inst["request"], inst["capacity"], preds, a)
        if late:
            return 0.0                                           # not in precedence order: an invalid answer (statement (5))
        zero, value = inst["zero"], inst["value"]
        return float(min(1.0, max(0.0, (zero - float(finish.max())) / (zero - value))))
