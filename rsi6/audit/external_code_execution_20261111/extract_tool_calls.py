"""Extract every tool call and its output from a sub-agent transcript into a plain record.

Only tool calls (name and input) and tool results are kept; prompts, system text and model
reasoning are not. Nothing is executed.
"""
import json, sys, os, hashlib

src, out_dir, label = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(out_dir, exist_ok=True)
calls, results, order = {}, {}, []
first_ts = last_ts = None
for line in open(src):
    try:
        row = json.loads(line)
    except Exception:
        continue
    ts = row.get("timestamp")
    msg = row.get("message") or {}
    content = msg.get("content")
    if not isinstance(content, list):
        continue
    for part in content:
        if not isinstance(part, dict):
            continue
        if part.get("type") == "tool_use":
            calls[part["id"]] = {"tool": part.get("name"), "input": part.get("input"), "time": ts}
            order.append(part["id"])
            first_ts = first_ts or ts
            last_ts = ts or last_ts
        elif part.get("type") == "tool_result":
            body = part.get("content")
            if isinstance(body, list):
                body = "\n".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in body)
            results[part.get("tool_use_id")] = {"output": body, "is_error": bool(part.get("is_error")), "time": ts}
records = []
for i, cid in enumerate(order):
    c = calls[cid]
    r = results.get(cid, {"output": None, "is_error": None, "time": None})
    records.append({"seq": i, "time": c["time"], "reply_time": r["time"], "tool": c["tool"], "input": c["input"],
                    "output": r["output"], "is_error": r["is_error"]})
path = os.path.join(out_dir, f"{label}_tool_calls.jsonl")
with open(path, "w") as handle:
    for rec in records:
        handle.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
tools = {}
for rec in records:
    tools[rec["tool"]] = tools.get(rec["tool"], 0) + 1
print(label, "records", len(records), "tools", tools, "first", first_ts, "last", last_ts,
      "bytes", os.path.getsize(path), "sha256", hashlib.sha256(open(path, "rb").read()).hexdigest()[:16])
