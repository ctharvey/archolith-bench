"""One directed turn against the proxy, curator route. I (the lead) supply each
instruction via a message file; the driver sends it, saves the reply, extracts any
named files, and reports tokens + curator engagement so I can direct the next page.

Usage: python direct_turn.py <arm_dir> <model> <session_id> <msg_file>
"""
import json, sys, os, urllib.request, time, re

arm_dir, model, sid, msg_file = sys.argv[1:5]
conv_path = os.path.join(arm_dir, "conversation.json")
SYSTEM = ("You are a senior frontend engineer building a mobile web version of 'Yawn', a Pokemon TCG "
          "market-data app, screen by screen with a lead who gives one page at a time. Output ONLY the "
          "file(s) for THIS page, each in its own fenced block whose FIRST LINE is a comment naming the "
          "path (e.g. <!-- screens/home.html --> or /* mobile.css */). Reuse the shared mobile.css "
          "tokens, api.js helpers, and bottom-nav shell exactly as established. Be complete; no prose.")

conv = json.load(open(conv_path, encoding="utf-8")) if os.path.exists(conv_path) else [{"role": "system", "content": SYSTEM}]
msg = open(msg_file, encoding="utf-8").read()
conv.append({"role": "user", "content": msg})

req = urllib.request.Request("http://127.0.0.1:9800/v1/chat/completions",
    data=json.dumps({"model": model, "messages": conv, "max_tokens": 4000, "temperature": 0.2}).encode(),
    headers={"Content-Type": "application/json", "X-Session-ID": sid})
t0 = time.time(); r = json.load(urllib.request.urlopen(req, timeout=300)); dt = time.time() - t0
reply = r["choices"][0]["message"].get("content") or ""
conv.append({"role": "assistant", "content": reply})
json.dump(conv, open(conv_path, "w", encoding="utf-8"), indent=1)
open(os.path.join(arm_dir, "last_reply.txt"), "w", encoding="utf-8").write(reply)

# extract named files
saved = []
for m in re.finditer(r"```[a-zA-Z]*\s*\n(.*?)```", reply, re.S):
    body = m.group(1); first = body.splitlines()[0] if body.splitlines() else ""
    pm = re.search(r"(?:<!--|/\*|//)\s*([\w./-]+\.(?:html|css|js))", first)
    if pm:
        full = os.path.join(arm_dir, pm.group(1)); os.makedirs(os.path.dirname(full) or arm_dir, exist_ok=True)
        open(full, "w", encoding="utf-8").write(body); saved.append(pm.group(1))

u = r.get("usage", {})
steps = sum(1 for m in conv if m["role"] == "user")
print(f"step {steps} | {dt:.0f}s | prompt={u.get('prompt_tokens')} completion={u.get('completion_tokens')} | files={saved}")
print("reply_first_120:", reply[:120].replace(chr(10), " "))
