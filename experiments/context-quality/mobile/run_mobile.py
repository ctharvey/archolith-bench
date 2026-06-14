"""Long page-by-page LED experiment: build a mobile version of yawn.frontend.

Contract: each yawn.frontend page gets a matching mobile screen, and EVERY screen
must reuse the shared design system + API client + app-shell established in turn 1.
Page-by-page => ~20 turns => long session => real context pressure + cross-turn
coherence (the curator's actual regime). Identical script both arms; only the
proxy context mode varies.

Run: python run_mobile.py <arm> <model>
"""
import json, sys, os, urllib.request, time, re

ARM, MODEL = sys.argv[1], sys.argv[2]
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, ARM); os.makedirs(OUT, exist_ok=True)
SID = f"mob-{ARM}-{int(time.time())}"

SYSTEM = ("You are a senior frontend engineer building a mobile web version of 'Yawn', a Pokemon TCG "
          "market-data app, page by page with a lead. Each message is one step. Output the COMPLETE "
          "file(s) for that step, each in its own ```html/```css/```js block whose FIRST LINE is a "
          "comment naming the path (e.g. <!-- screens/cards.html --> or /* mobile.css */). "
          "CRITICAL: every screen MUST reuse the shared design system (mobile.css tokens), the shared "
          "API client (api.js), and the bottom-tab app shell you establish in step 1. Stay visually "
          "and structurally consistent across all screens. Mobile-first: 100% width, large touch "
          "targets, bottom tab nav, dark theme.")

# Turn 1 = scaffold (establishes conventions). Turns 2..N = one screen per real
# yawn.frontend page. Each screen turn CALLS BACK to the turn-1 system + earlier
# components (the coherence pressure). The page list IS the contract.
SCAFFOLD = (
 "Establish the mobile foundation in three files. (1) mobile.css: design tokens for a DARK theme "
 "matching Yawn -- backgrounds #0a0b0d/#0f1014/#14161b, green accents #16a34a/#4ade80, muted text "
 "#8a909c; plus base mobile styles (full-width, >=44px touch targets, card, list-row, button, "
 "bottom-nav). (2) api.js: a shared client `api(path, params)` hitting base '/api', with named "
 "helpers for the endpoints we'll use (sets matrix, market breadth, card search, card detail, sealed "
 "list, sealed detail, graded, sets list, set detail, series, transactions, vs-compare). (3) "
 "app-shell.html: the mobile shell with a fixed bottom tab nav with tabs Pulse / Cards / Sealed / "
 "Sets / VS (dark, green active state). These three files are the contract every later screen reuses. "
 "Output all three.")

# (page-key, instruction). [CB] = explicit coherence callback to earlier work.
PAGES = [
 ("home",        "Build screens/home.html -- the 'Pulse' home screen: a market overview with a set-matrix list and a 7d/30d market-breadth summary. [CB] Use mobile.css tokens + api.js (sets matrix + market breadth helpers) + the bottom-nav shell from step 1. Output screens/home.html."),
 ("market_report","Build screens/market-report.html -- a market report screen (top movers, breadth over time). [CB] Reuse the SAME card/list-row styles and api.js you defined. Output the file."),
 ("cards",       "Build screens/cards.html -- the Cards browse/search screen: a search input + a scrollable list of card rows (name, set, price). [CB] Use the api.js card-search helper and mobile.css list-row. Define a reusable card-row markup pattern here; later screens will reuse it. Output the file."),
 ("card_detail", "Build screens/card-detail.html -- a single card detail screen (image, name, set, current price, a price-history placeholder chart, buy links). [CB] Reuse mobile.css + api.js card-detail helper + the header/back pattern. Output the file."),
 ("sealed",      "Build screens/sealed.html -- the Sealed products browse screen (list of sealed products with EV). [CB] Reuse the card-row pattern you established on the Cards screen + api.js sealed-list helper. Output the file."),
 ("sealed_detail","Build screens/sealed-detail.html -- a sealed product detail screen (contents, EV breakdown, price). [CB] Reuse the detail header/back pattern from card-detail + api.js sealed-detail helper. Output the file."),
 ("ev_explorer", "Build screens/ev-explorer.html -- the EV Explorer tool: filter sealed products by expected value with sliders/inputs. [CB] Reuse mobile.css form/button tokens + the sealed list-row. Output the file."),
 ("graded",      "Build screens/graded.html -- the Graded cards screen (PSA/BGS graded prices list). [CB] Reuse the card-row pattern + api.js graded helper + bottom-nav. Output the file."),
 ("sets",        "Build screens/sets.html -- the Sets browse screen (grid/list of TCG sets with logo, name, card count). [CB] Reuse mobile.css + api.js sets-list helper + the Sets bottom-nav tab active state. Output the file."),
 ("set_detail",  "Build screens/set-detail.html -- a single set detail screen (set header, cards in the set as rows). [CB] Reuse the card-row pattern from Cards + the detail header from card-detail + api.js set-detail helper. Output the file."),
 ("set_sealed",  "Build screens/set-sealed.html -- sealed products belonging to one set. [CB] Reuse the sealed list-row + the detail header. Output the file."),
 ("series",      "Build screens/series.html -- a series detail screen (a named series grouping multiple sets). [CB] Reuse the sets list pattern + api.js series helper. Output the file."),
 ("vs",          "Build screens/vs.html -- the VS comparison tool: pick two cards and compare prices side by side. [CB] Reuse the card-search input from Cards + mobile.css + api.js vs-compare + the VS bottom-nav tab. Output the file."),
 ("search",      "Build screens/search.html -- a global search screen across cards and sealed. [CB] Reuse the SAME search input and card-row pattern from the Cards screen exactly. Output the file."),
 ("transactions","Build screens/transactions.html -- a user transactions/portfolio screen (list of buys/sells with P/L). [CB] Reuse mobile.css list-row + api.js transactions helper. Output the file."),
 ("login",       "Build screens/login.html -- a mobile login screen (email, password, submit). [CB] Reuse mobile.css form tokens + button; NO bottom-nav on auth screens. Output the file."),
 ("register",    "Build screens/register.html -- a mobile register screen consistent with login. [CB] Match the login screen's form styling exactly. Output the file."),
 ("verify_email","Build screens/verify-email.html -- an email-verification confirmation screen. [CB] Match the auth screens' minimal styling (no bottom-nav). Output the file."),
 ("not_found",   "Build screens/404.html -- a mobile not-found screen with a link back to Pulse/home. [CB] Reuse mobile.css + the bottom-nav. Output the file. This completes the contract: every yawn.frontend page now has a mobile screen."),
]

def call(conv):
    req = urllib.request.Request("http://127.0.0.1:9800/v1/chat/completions",
        data=json.dumps({"model": MODEL, "messages": conv, "max_tokens": 4000, "temperature": 0.2}).encode(),
        headers={"Content-Type": "application/json", "X-Session-ID": SID})
    t0 = time.time(); r = json.load(urllib.request.urlopen(req, timeout=300))
    return r["choices"][0]["message"].get("content") or "", r.get("usage", {}), time.time() - t0

def extract(content, outdir):
    # save each fenced block to the path named in its first-line comment
    saved = []
    for m in re.finditer(r"```[a-zA-Z]*\s*\n(.*?)```", content, re.S):
        body = m.group(1)
        first = body.splitlines()[0] if body.splitlines() else ""
        pm = re.search(r"(?:<!--|/\*|//)\s*([\w./-]+\.(?:html|css|js))", first)
        if pm:
            path = pm.group(1)
            full = os.path.join(outdir, path); os.makedirs(os.path.dirname(full) or outdir, exist_ok=True)
            open(full, "w", encoding="utf-8").write(body)
            saved.append(path)
    return saved

conv = [{"role": "system", "content": SYSTEM}]
log = []
script = [("scaffold", SCAFFOLD)] + PAGES
for i, (key, instr) in enumerate(script, 1):
    conv.append({"role": "user", "content": instr})
    try:
        content, usage, dt = call(conv)
    except Exception as e:
        print(f"[{ARM} t{i} {key}] ERROR {e}"); break
    conv.append({"role": "assistant", "content": content})
    saved = extract(content, OUT)
    log.append({"turn": i, "page": key, "callback": "[CB]" in instr,
                "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"),
                "dt": round(dt, 1), "files": saved})
    print(f"[{ARM} t{i:>2} {key:<13}] {usage.get('prompt_tokens'):>6} in / {usage.get('completion_tokens'):>5} out / {dt:.0f}s files={saved}")
    time.sleep(1)

json.dump(conv, open(os.path.join(OUT, "conversation.json"), "w", encoding="utf-8"), indent=1)
json.dump(log, open(os.path.join(OUT, "turnlog.json"), "w", encoding="utf-8"), indent=1)
print(f"[{ARM}] done: {len(log)} turns, session={SID}")
