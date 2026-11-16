"""Confinement for exploration: forked child, rlimits, empty cwd, default-deny audit hook.

run_confined(fn, *args) forks; the child sets limits, installs the hook, runs fn, and
returns a pickled result over a pipe. Anything the hook refuses raises inside the child.
"""
import os, sys, pickle, resource, signal, tempfile

# Events a pure computation may raise. Everything else is refused once the hook is armed.
ALLOW = {"object.__getattr__", "object.__setattr__", "object.__delattr__", "compile", "exec",
         "sys._getframe", "sys._getframemodulename", "builtins.id", "code.__new__",
         "function.__new__", "marshal.loads", "import"}
# 'import' is allowed only for modules already loaded before arming (checked below).

_armed = False
_preloaded = set()
DENIED = []


def _hook(event, args):
    if not _armed:
        return
    if event == "import":
        name = args[0]
        if name.split(".")[0] in _preloaded:
            return
        DENIED.append((event, str(args)[:80]))
        raise PermissionError("sandbox: import " + str(name))
    if event in ALLOW:
        return
    DENIED.append((event, str(args)[:80]))
    raise PermissionError("sandbox: " + event)


def arm():
    global _armed, _preloaded
    _preloaded = {m.split(".")[0] for m in sys.modules}
    sys.addaudithook(_hook)
    _armed = True


def run_confined(fn, *args, cpu_s=120, mem_bytes=3 << 30):
    r, w = os.pipe()
    pid = os.fork()
    if pid == 0:  # child
        try:
            os.close(r)
            d = tempfile.mkdtemp(prefix="owt_jail_")
            os.chdir(d)
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s))
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
            resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))   # no file may grow
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
            arm()
            try:
                out = ("ok", fn(*args), DENIED[:50])
            except BaseException as e:
                out = ("err", repr(e)[:300], DENIED[:50])
            data = pickle.dumps(out)
            os.write(w, data)
        finally:
            os._exit(0)
    os.close(w)
    chunks = []
    while True:
        b = os.read(r, 1 << 20)
        if not b:
            break
        chunks.append(b)
    os.close(r)
    os.waitpid(pid, 0)
    return pickle.loads(b"".join(chunks)) if chunks else ("crash", None, [])


class Timeout(Exception):
    pass


def _alarm(sig, frm):
    raise Timeout()


signal.signal(signal.SIGALRM, _alarm)


def call_limited(f, args, seconds=0.02):
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        return f(*args)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
