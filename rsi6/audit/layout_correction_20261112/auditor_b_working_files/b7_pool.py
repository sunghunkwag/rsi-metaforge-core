"""Auditor B: what does multiprocessing's pool.map do when a job raises?  (Standard library only;
no rsi6 code.)  rsi6.kernel.run.run() hands the jobs of a gate to pool.map(measure, jobs,
chunksize=1); the first gate of round 2 had twelve jobs: knapsack with six seeds, then regression
with six seeds.  Here: twelve toy jobs, the first six raise.  One worker only, to stay within two
processes; the rule in question (map waits for every job, then raises the first error) does not
depend on the number of workers.  Writes marker files in a new temporary directory under WORK."""
import multiprocessing
import os
import tempfile

WORK = "/tmp/claude-0/-home-user-rsi-metaforge-core/49317f35-39aa-5636-a36c-c80f42cd346e/scratchpad/audit2/work_b"
MARK = tempfile.mkdtemp(prefix="pool_", dir=WORK)


def job(k):
    open(os.path.join(MARK, f"started_{k:02d}"), "w").close()
    if k < 6:
        raise ValueError(f"job {k} raises")
    return k


if __name__ == "__main__":
    try:
        with multiprocessing.get_context("fork").Pool(1) as pool:
            pool.map(job, range(12), chunksize=1)
        print("no exception")
    except ValueError as error:
        print("pool.map raised:", error)
    print("jobs that were started before pool.map raised:", sorted(int(n.split("_")[1]) for n in os.listdir(MARK)))
