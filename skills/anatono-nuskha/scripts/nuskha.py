"""Read a medicine or prescription photo with Gemma 4, check it, and turn it into a routine and calendar alarms.

    python3 nuskha.py PHOTO                         # what Gemma read + the safety checks
    python3 nuskha.py PHOTO --dose "1+0+1 x 5 days" # also the routine (otherwise uses the dose written on a prescription)
    python3 nuskha.py PHOTO --ics reminders.ics     # also write calendar alarms

Needs GEMINI_API_KEY (in the repo's .env). Prints JSON.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))      # the repo root, where anatono.py lives
import anatono as A  # noqa: E402

p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
p.add_argument("photo")
p.add_argument("--dose", help="how the person takes it, typed (any language); for a single medicine")
p.add_argument("--ics", help="write calendar alarms to this file")
a = p.parse_args()

read = A.read_photo(Path(a.photo).read_bytes())
out = {"kind": read.get("kind"), "medicines": [], "routine": []}
why = A.explain(read.get("medicines") or []) if read.get("medicines") else []
for m, c, w in zip(read.get("medicines") or [], read["checks"], why):
    out["medicines"].append({"name": m.get("name"), "strength": m.get("strength"), "what_for": w.get("what_for"),
                             "check": c["level"], "flags": c["flags"]})
    said = a.dose if a.dose and len(read["medicines"]) == 1 else m.get("dose_written")
    if c["level"] == "stop" or not said:
        continue                                   # never set reminders for a medicine flagged "stop"
    r = A.understand_dose(m, said)
    out["routine"].append({"name": m.get("name"), "strength": m.get("strength") or "", "amount": r["dose"].get("amount"),
                           "food": r["dose"].get("food"), "times": r["check"]["times"], "days": r["check"]["days"],
                           "notes": r["check"]["notes"]})
if a.ics:
    Path(a.ics).write_text(A.ics([r for r in out["routine"] if r["times"]]))
    out["ics"] = a.ics
print(json.dumps(out, indent=2, ensure_ascii=False))
