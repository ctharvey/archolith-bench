"""Multi-turn LED context-quality experiment.

Drives an identical 12-turn complex task against the proxy in two arms
(passthrough vs full-curator). Each turn is a USER turn (so the curator engages
on the full arm). Later turns CALL BACK to decisions/field-names the model made
in earlier turns -- the coherence signal: does curated context keep a weak model
consistent across a long session better than raw history?

Same turn-script for both arms (clean A/B; only the proxy context mode varies).
Run:  python run_multiturn.py <arm> <model>
  arm   : passthrough | full   (label)
  model : deepseek-v4-flash-passthrough  (passthrough)  | deepseek-v4-flash (full)
"""
import json, sys, os, urllib.request, time

ARM, MODEL = sys.argv[1], sys.argv[2]
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, ARM)
os.makedirs(OUT, exist_ok=True)
SID = f"mt-{ARM}-{int(time.time())}"

SYSTEM = ("You are a senior Python developer building a library incrementally with a lead engineer. "
          "Each message is one step. When asked for code, output the COMPLETE current version of the "
          "file in a single ```python block with a first-line comment naming the file (# inventory.py). "
          "Honor every decision and exact name you established in earlier steps. Be precise.")

# 12 turns. Turns marked [CALLBACK] deliberately depend on earlier decisions/names
# the MODEL produced -- testing cross-turn coherence (the curator's value for a weak model).
TURNS = [
 "We are building inventory.py. Decisions you must follow for the whole session: (a) every Item has a UUID string id; (b) field names are exactly: id, sku, name, quantity, unit_price; (c) money is stored as integer cents, never floats. Acknowledge these three rules and restate the exact Item field names.",
 "Write the Item class: a dataclass with those exact fields, id auto-generated as a uuid4 string, plus a method total_value() returning quantity * unit_price (in cents). Output inventory.py.",
 "Add a Warehouse class to inventory.py: it has a name and holds Items keyed by their id. Methods: add_item(item), remove_item(item_id), get_item(item_id). remove_item/get_item raise KeyError if the id is absent. Output the full inventory.py.",
 "[CALLBACK] Add Warehouse.transfer(item_id, other_warehouse): move the Item with that id from this warehouse to other_warehouse. It must use the exact id field and the add/remove methods you already defined. Output full inventory.py.",
 "Change of plan: add a 'reserved' integer field to Item (default 0), representing units reserved but not yet shipped. Update the dataclass and any code that constructs Items. Keep all earlier field names unchanged. Output full inventory.py.",
 "[CALLBACK] Add a method Item.available() returning quantity minus reserved, and make reserving validate: add Warehouse.reserve(item_id, n) that raises ValueError if n would make reserved exceed quantity. Use the reserved field you just added. Output full inventory.py.",
 "Add a TransactionLog class: records every add_item, remove_item, transfer, and reserve as a dict with keys: action, item_id, timestamp (time.time()), and detail. Wire Warehouse to append to a shared log passed into its constructor. Output full inventory.py.",
 "[CALLBACK] Add Warehouse.low_stock(threshold): return a list of Items whose available() (the method from earlier) is below threshold, sorted by available() ascending. Output full inventory.py.",
 "[CALLBACK] Add Item.to_dict() that serializes using the EXACT field names you defined in step 1/5 (id, sku, name, quantity, unit_price, reserved) plus a derived 'available' key. Do not rename anything. Output full inventory.py.",
 "[CALLBACK] Review your transfer() method: does it record to the TransactionLog you added in step 7? If it does not, fix it so transfer logs a 'transfer' action with both warehouse names in detail. Output full inventory.py.",
 "Add Warehouse.to_json() returning a JSON string of all items (using Item.to_dict()) and the warehouse name; and a classmethod Warehouse.from_json(s, log) reconstructing it. Money stays integer cents. Output full inventory.py.",
 "[CALLBACK] Final: write a __main__ block that exercises EVERY feature in order: create a log + two warehouses, add 3 items, reserve some, transfer one between warehouses, print low_stock, dump to_json and reload via from_json, and print the transaction log. It must run without error and honor all earlier decisions. Output the full final inventory.py.",
]

def call(conv):
    req = urllib.request.Request(
        "http://127.0.0.1:9800/v1/chat/completions",
        data=json.dumps({"model": MODEL, "messages": conv, "max_tokens": 4000, "temperature": 0.2}).encode(),
        headers={"Content-Type": "application/json", "X-Session-ID": SID})
    t0 = time.time()
    r = json.load(urllib.request.urlopen(req, timeout=240))
    return r["choices"][0]["message"].get("content") or "", r.get("usage", {}), time.time() - t0

conv = [{"role": "system", "content": SYSTEM}]
log = []
for i, t in enumerate(TURNS, 1):
    conv.append({"role": "user", "content": t})
    try:
        content, usage, dt = call(conv)
    except Exception as e:
        print(f"[{ARM} turn {i}] ERROR {e}"); break
    conv.append({"role": "assistant", "content": content})
    log.append({"turn": i, "callback": "[CALLBACK]" in t,
                "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"),
                "dt": round(dt, 1), "reply_chars": len(content)})
    print(f"[{ARM} turn {i:>2}] {usage.get('prompt_tokens'):>6} in / {usage.get('completion_tokens'):>5} out / {dt:.0f}s  {'CB' if '[CALLBACK]' in t else '  '}")
    time.sleep(1)

json.dump(conv, open(os.path.join(OUT, "conversation.json"), "w", encoding="utf-8"), indent=1)
json.dump(log, open(os.path.join(OUT, "turnlog.json"), "w", encoding="utf-8"), indent=1)

# extract final code block -> inventory.py
import re
final = conv[-1]["content"]
blocks = re.findall(r"```(?:python)?\s*\n(.*?)```", final, re.S)
open(os.path.join(OUT, "inventory.py"), "w", encoding="utf-8").write(max(blocks, key=len) if blocks else "")
print(f"[{ARM}] done: {len(log)} turns, final inventory.py extracted, session={SID}")
