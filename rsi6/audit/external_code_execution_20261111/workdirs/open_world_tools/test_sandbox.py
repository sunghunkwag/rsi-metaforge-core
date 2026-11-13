import os, sys, shutil, subprocess, socket
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sandbox import run_confined, call_limited, Timeout

HERE = os.path.dirname(os.path.abspath(__file__))
CAN = os.path.join(HERE, "canary_dir")
os.makedirs(CAN, exist_ok=True)
open(os.path.join(CAN, "c.txt"), "w").write("alive")


def attacks():
    res = {}
    tests = {
        "os.remove": lambda: os.remove(os.path.join(CAN, "c.txt")),
        "os.unlink": lambda: os.unlink(os.path.join(CAN, "c.txt")),
        "shutil.rmtree": lambda: shutil.rmtree(CAN),
        "open_w": lambda: open(os.path.join(CAN, "c.txt"), "w"),
        "open_r": lambda: open(os.path.join(CAN, "c.txt")).read(),
        "os.system": lambda: os.system("rm -rf " + CAN),
        "subprocess": lambda: subprocess.run(["rm", "-rf", CAN]),
        "os.fork": lambda: os.fork(),
        "socket": lambda: socket.socket(),
        "import_ctypes": lambda: __import__("ctypes"),
        "os.rename": lambda: os.rename(CAN, CAN + "_x"),
        "os.chmod": lambda: os.chmod(CAN, 0),
        "os.kill": lambda: os.kill(os.getppid(), 9),
        "exec_rm": lambda: exec("import os; os.remove(%r)" % os.path.join(CAN, "c.txt")),
        "hang": lambda: call_limited(lambda: [i for i in iter(int, 1)], (), 0.05),
    }
    for k, f in tests.items():
        try:
            f(); res[k] = "NOT BLOCKED"
        except Timeout:
            res[k] = "timeout"
        except BaseException as e:
            res[k] = "blocked:" + type(e).__name__

    return res


def blind():
    res = {}
    n = 0; ok = 0
    for mod in (os, shutil):
        for name in dir(mod):
            f = getattr(mod, name)
            if not callable(f):
                continue
            for args in [(), (CAN,), (os.path.join(CAN, "c.txt"),), (CAN, CAN + "_y"), (0,), (1, 1)]:
                n += 1
                try:
                    call_limited(f, args, 0.05); ok += 1
                except BaseException:
                    pass
    res["blind_probe_calls"] = n
    res["blind_probe_returned"] = ok
    return res


st, out, denied = run_confined(attacks)
print(st)
for k, v in (out.items() if isinstance(out, dict) else [("x", out)]):
    print(" ", k, v)
import os as _o
# blind probe: one child per callable so os._exit/abort only kill that child
names=[(m,n) for m in ("os","shutil") for n in dir(__import__(m)) if callable(getattr(__import__(m),n))]
def one(m,n):
    f=getattr(__import__(m),n); c=0
    for args in [(), (CAN,), (os.path.join(CAN, "c.txt"),), (CAN, CAN + "_y"), (0,), (1, 1)]:
        try: call_limited(f,args,0.05); c+=1
        except BaseException: pass
    return c
crash=0; ret=0; allden=set()
for m,n in names:
    st2,o2,d2=run_confined(one,m,n,cpu_s=5)
    if st2=="crash": crash+=1
    elif st2=="ok": ret+=o2
    allden|={e for e,_ in d2}
print("blind probe callables",len(names),"children that died (e.g. _exit/abort)",crash,"calls returning normally",ret)
print("denied events in blind probe:",sorted(allden))
out={}
for k, v in (out.items() if isinstance(out, dict) else [("x", out)]):
    print(" ", k, v)
print("distinct denied events:", sorted({e for e, _ in denied}))
print("canary intact:", os.path.exists(os.path.join(CAN, "c.txt")) and open(os.path.join(CAN, "c.txt")).read() == "alive",
      "dir names:", sorted(os.listdir(HERE)))
