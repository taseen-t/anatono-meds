"""Anatono: never miss a medicine.

Photograph a medicine (or a prescription) and Gemma 4 reads it. Type or say how you take it, and Gemma 4 understands
it, in Urdu, Roman Urdu or English, and turns it into a routine. Code checks everything Gemma read (expiry, missing
details, double doses, dose patterns) before it becomes a reminder, and the person confirms before anything is saved.
"""
import base64
import calendar
import copy
import hashlib
import io
import os
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from PIL import Image

load_dotenv(Path(__file__).with_name(".env"))
MODEL = "gemma-4-26b-a4b-it"
MODEL_BACKUP = "gemma-4-31b-it"            # used only if the 26B model fails twice
# optional second engine, picked with the switch in the app: Claude Haiku through the Anthropic API (ANTHROPIC_API_KEY)
CLAUDE_MODEL = "claude-haiku-5-5"
# Gemma 4 on the API refuses audio ("Audio input modality is not enabled"), so Gemini Flash-Lite only writes down
# what was said (as Taseen's Uplink bot does); Gemma 4 does all the understanding.
HEARING = "gemini-3.5-flash-lite"
VOICE_ASK = ("Transcribe this voice note exactly as spoken. Write Urdu or Punjabi in Roman Urdu (Latin letters) "
             "and English as English. Reply with the words only, nothing else. If there is no speech, reply with nothing.")
SLOT_TIME = {"morning": "08:00", "afternoon": "14:00", "evening": "18:00", "night": "21:00"}

READ_PROMPT = """You are Anatono, a careful pharmacist's helper. This photo shows a medicine (strip, box, bottle,
tube or inhaler) or a doctor's prescription. Read it.
Reply with JSON only:
{"kind": "medicine" or "prescription" or "other",
 "medicines": [{"name": "brand name as printed", "salt": "active ingredient(s)", "strength": "e.g. 500 mg",
   "form": "tablet|capsule|syrup|drops|injection|cream|inhaler|other", "manufacturer": "", "batch": "",
   "mfg": "YYYY-MM or ''", "expiry": "YYYY-MM or ''", "reg_no": "registration number as printed, or ''",
   "dose_written": "the dose as written on a prescription (e.g. 1+0+1, BD x 5 days), or ''"}],
 "warning_signs": ["anything that looks wrong for a genuine medicine: spelling mistakes, blurry or uneven print,
   missing batch, expiry or manufacturer, damaged packaging. [] if none"]}
Never invent anything that isn't visible. If you can't read something, leave it ''.
Keep it short: no text outside the JSON."""

# asked after the photo is read, so the first (slow) call only has to read what's on the page
EXPLAIN_PROMPT = """You are Anatono. For each medicine below, say in one simple sentence what it is usually used for,
in English and in simple Urdu. Medicines: {meds}
Reply with JSON only: {{"medicines": [{{"what_for": "...", "what_for_urdu": "..."}}]}}, in the same order."""

DOSE_PROMPT = """You are Anatono. The person is telling you how they take {med}. They may use Urdu, Roman Urdu,
Punjabi or English, for example "subah aur raat ek goli khane ke baad", "1+0+1", "twice a day for 5 days".
{said}
Reply with JSON only:
{{"heard": "what they said, written out in their words",
 "amount": "how much each time, e.g. 1 tablet, half tablet, 2 spoons",
 "times": ["morning", "afternoon", "evening", "night", or an exact time like "07:30"],
 "food": "before" or "after" or "with" or "any",
 "days": number of days, or null if they didn't say,
 "as_needed": true only if it's just when needed (SOS, jab zaroorat ho),
 "unclear": "anything you weren't sure about, '' if it's clear"}}"""


# ---------- Gemma ----------

_answers = {}   # ponytail: in memory per server process (lost on restart / a new Vercel instance); the app keeps its own copy


def ask(contents, engine="gemma"):
    """One model call that must return JSON. The same question (same text, same photo, same engine) is answered once
    and then served from memory, so a prescription that was already read isn't read again."""
    key = hashlib.sha256(engine.encode())
    for c in contents:
        key.update(c.tobytes() if isinstance(c, Image.Image) else str(c).encode())
    key = key.hexdigest()
    if key not in _answers:
        _answers[key] = (ask_claude if engine == "claude" else ask_gemma)(contents)
    return copy.deepcopy(_answers[key])


def as_json(text):
    return json.loads(re.search(r"\{.*\}", text or "", re.S).group(0))


def ask_gemma(contents):
    """Gemma 4 through the Gemini API. It sometimes answers 500 or loose JSON: try the 26B model twice, then the 31B
    one (both Gemma 4)."""
    client = genai.Client()                       # keep a reference: a dropped client closes its connection
    tries = [MODEL, MODEL, MODEL_BACKUP]
    for attempt, model in enumerate(tries):
        try:
            return as_json(client.models.generate_content(model=model, contents=contents).text)
        except Exception:  # noqa: BLE001
            if attempt == len(tries) - 1:
                raise
            time.sleep(2 * (attempt + 1))


def ask_claude(contents):
    """Claude Haiku through the Anthropic API: photos go as JPEG blocks, text as text."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise ValueError("Claude isn't set up on this server: add ANTHROPIC_API_KEY to .env, or switch back to Gemma 4.")
    import anthropic
    blocks = []
    for c in contents:
        if isinstance(c, Image.Image):
            buf = io.BytesIO()
            c.save(buf, "JPEG", quality=88)
            blocks.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                       "data": base64.standard_b64encode(buf.getvalue()).decode()}})
        else:
            blocks.append({"type": "text", "text": str(c)})
    r = anthropic.Anthropic().messages.create(model=CLAUDE_MODEL, max_tokens=8000, messages=[{"role": "user", "content": blocks}])
    if r.stop_reason == "refusal":
        raise ValueError("Claude wouldn't read this one. Try Gemma 4.")
    return as_json("".join(b.text for b in r.content if b.type == "text"))


def image_from(data_url_or_bytes):
    raw = data_url_or_bytes
    if isinstance(raw, str):
        raw = base64.b64decode(raw.split(",", 1)[-1])
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    img.thumbnail((1600, 1600))
    return img


def pieces(img):
    """A tall page (a full prescription) is cut into two overlapping halves, because Gemma 4 on the API is slow and
    two short answers come back sooner than one long one. The overlap keeps a line cut in half readable in one piece."""
    w, h = img.size
    if h < 1.2 * w:
        return [img]
    return [img.crop((0, 0, w, int(h * .58))), img.crop((0, int(h * .42), w, h))]


def read_photo(image, routine=(), today=None, piece=None, engine="gemma"):
    """Gemma reads the medicine or prescription; code checks it against today's date and the person's routine.
    piece=None reads every piece at once; piece=0, 1 reads just that one (the app shows part 1 and offers the rest)."""
    img = image if isinstance(image, Image.Image) else image_from(image)
    cut = pieces(img)
    todo = cut if piece is None else [cut[min(int(piece), len(cut) - 1)]]
    with ThreadPoolExecutor() as pool:
        parts = list(pool.map(lambda p: ask([READ_PROMPT, p], engine), todo))
    meds, seen = [], set()
    for part in parts:                            # a medicine in the overlap is read twice: keep it once
        for m in part.get("medicines") or []:
            key = norm(m.get("name")) + norm(m.get("strength"))
            if key and key not in seen:
                seen.add(key)
                meds.append(m)
    d = {"kind": next((p["kind"] for p in parts if p.get("kind") == "prescription"), parts[0].get("kind")),
         "medicines": meds, "warning_signs": sorted({w for p in parts for w in p.get("warning_signs") or []})}
    return checked({**d, "pieces": len(cut)}, routine, today)


def checked(d, routine=(), today=None):
    """The code checks on what was read. Run again on every cached read, because they depend on today and the routine."""
    return {**d, "checks": [check_medicine(m, d, routine, today) for m in d.get("medicines") or []]}


def explain(medicines, engine="gemma"):
    """What each medicine is usually for, in English and Urdu (a second, quick call after the photo is read)."""
    names = "; ".join(" ".join(x for x in (m.get("name"), m.get("salt")) if x) for m in medicines)
    got = ask([EXPLAIN_PROMPT.format(meds=names)], engine).get("medicines") or []
    return [got[i] if i < len(got) else {} for i in range(len(medicines))]


def hear(audio, mime="audio/webm"):
    """A voice clip -> its words (Roman Urdu / English). Only writes down what was said."""
    from google.genai import types
    raw = base64.b64decode(audio.split(",", 1)[-1]) if isinstance(audio, str) else audio
    client = genai.Client()
    r = client.models.generate_content(model=HEARING, contents=[types.Part.from_bytes(data=raw, mime_type=mime), VOICE_ASK])
    return (r.text or "").strip()


def understand_dose(medicine, text=None, audio=None, mime="audio/webm", engine="gemma"):
    """Gemma understands how the person takes it, typed or spoken; code checks the routine."""
    if audio is not None:
        text = hear(audio, mime)
        if not text:
            raise ValueError("I couldn't hear any words. Try again a little closer to the phone.")
    med = " ".join(x for x in (medicine.get("name"), medicine.get("strength")) if x) or "this medicine"
    d = ask([DOSE_PROMPT.format(med=med, said=f"They said or typed: {text!r}")], engine)
    return {"dose": d, "check": check_dose(d), "heard": text}


# ---------- code checks (the harness) ----------

def month_end(ym):
    """'2027-03' -> date(2027, 3, 31); None if it isn't a YYYY-MM."""
    m = re.fullmatch(r"(\d{4})-(\d{1,2})", str(ym or "").strip()[:7])
    if not m or not 1 <= int(m[2]) <= 12:
        return None
    y, mo = int(m[1]), int(m[2])
    return date(y, mo, calendar.monthrange(y, mo)[1])


def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def check_medicine(m, d, routine=(), today=None):
    """Expiry, missing details a genuine pack always prints, and a second medicine with the same ingredient."""
    today = today or date.today()
    flags, good = [], []
    exp, mfg = month_end(m.get("expiry")), month_end(m.get("mfg"))
    if exp and exp < today:
        flags.append(("stop", f"Expired at the end of {exp:%B %Y}. Don't take it."))
    elif exp and (exp - today).days <= 30:
        flags.append(("careful", f"Expires soon: end of {exp:%B %Y}."))
    elif exp:
        good.append(f"In date until {exp:%B %Y}.")
    if mfg and exp and mfg >= exp:
        flags.append(("careful", "The made-on date is after the expiry date. That's wrong on a real pack."))
    if mfg and mfg > month_end(f"{today:%Y-%m}"):
        flags.append(("careful", "The made-on date is in the future."))
    if d.get("kind") == "medicine":
        missing = [k for k, label in (("batch", "batch number"), ("expiry", "expiry date"),
                                      ("manufacturer", "maker's name"), ("reg_no", "registration number"))
                   if not m.get(k)]
        for k in missing:
            flags.append(("careful", f"No {dict(batch='batch number', expiry='expiry date', manufacturer='maker', reg_no='registration number')[k]} found on the pack. Genuine packs print it."))
        if not missing:
            good.append("Batch, expiry, maker and registration number are all printed.")
    salt = norm(m.get("salt"))
    for r in routine:
        if salt and norm(r.get("salt")) == salt and norm(r.get("name")) != norm(m.get("name")):
            flags.append(("careful", f"You already take {r.get('name')}, which has the same ingredient "
                                     f"({m.get('salt')}). Taking both could double the dose: ask your doctor."))
    for w in d.get("warning_signs") or []:
        flags.append(("careful", f"Spotted on the pack: {w}"))
    level = ("stop" if any(f[0] == "stop" for f in flags) or sum(f[0] == "careful" for f in flags) >= 3
             else "careful" if flags else "ok")
    return {"level": level, "flags": [f[1] for f in flags], "good": good}


def pattern_slots(text):
    """'1+0+1' / '1-1-1' / '0+0+1' -> the slots it means, or None. Code's own reading, to cross-check Gemma."""
    m = re.search(r"(?<![\d/])([\d½]+)\s*[+\-]\s*([\d½]+)\s*[+\-]\s*([\d½]+)(?:\s*[+\-]\s*([\d½]+))?(?![\d/])", text or "")
    if not m:
        return None
    parts = [p for p in m.groups() if p is not None]
    names = ["morning", "afternoon", "night"] if len(parts) == 3 else ["morning", "afternoon", "evening", "night"]
    return [n for n, p in zip(names, parts) if p not in ("0",)]


def check_dose(d):
    """Turn Gemma's understanding into exact reminder times, and flag anything that doesn't add up."""
    notes, times = [], []
    for t in d.get("times") or []:
        t = str(t).strip().lower()
        hm = SLOT_TIME.get(t) or (t if re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", t) else None)
        if hm:
            times.append(hm.zfill(5))
        else:
            notes.append(f"Couldn't use the time '{t}'.")
    times = sorted(set(times))
    if d.get("as_needed"):
        times = []
        notes.append("Only when needed, so no daily reminders. It's saved in your list.")
    elif not times:
        notes.append("No time of day was understood. Say or type when you take it.")
    if len(times) > 6:
        notes.append("More than 6 times a day. Please check with your doctor.")
    slots = pattern_slots(d.get("heard"))
    if slots is not None and sorted(SLOT_TIME[s] for s in slots) != times and not d.get("as_needed"):
        notes.append(f"'{re.search(r'[\d½]+\s*[+-][^ ]*', d.get('heard') or '').group(0)}' usually means "
                     f"{' and '.join(slots)}. Please check the times.")
    days = d.get("days")
    days = int(days) if isinstance(days, (int, float)) and 0 < days <= 365 else None
    if days is None and not d.get("as_needed"):
        notes.append("No number of days was said, so it repeats every day until you stop it.")
    if not str(d.get("amount") or "").strip():
        notes.append("How much each time wasn't clear.")
    if d.get("unclear"):
        notes.append(f"Not sure about: {d['unclear']}")
    return {"times": times, "days": days, "notes": notes}


# ---------- calendar alarms (they ring even when the app is closed) ----------

def ics(routine, start=None):
    """An .ics calendar with a daily alarm per medicine and time."""
    start = start or date.today()
    out = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Anatono//Reminders//EN", "CALSCALE:GREGORIAN"]
    for i, r in enumerate(routine):
        for t in r.get("times") or []:
            hh, mm = t.split(":")
            what = f"{r.get('name', 'Medicine')} {r.get('strength', '')}".strip()
            how = ", ".join(x for x in (r.get("amount"), {"before": "before food", "after": "after food",
                                                           "with": "with food"}.get(r.get("food"), "")) if x)
            rule = f"RRULE:FREQ=DAILY;COUNT={int(r['days'])}" if r.get("days") else "RRULE:FREQ=DAILY"
            out += ["BEGIN:VEVENT", f"UID:anatono-{i}-{hh}{mm}-{start:%Y%m%d}@anatono",
                    f"DTSTAMP:{datetime.now():%Y%m%dT%H%M%S}", f"DTSTART:{start:%Y%m%d}T{hh}{mm}00",
                    f"DURATION:PT10M", rule, f"SUMMARY:Anatono: {what}", f"DESCRIPTION:{how}",
                    "BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:Time for {what}", "TRIGGER:-PT0M", "END:VALARM",
                    "END:VEVENT"]
    return "\r\n".join(out + ["END:VCALENDAR"]) + "\r\n"


if __name__ == "__main__":
    # Self-check of the code checks (no API call): known answers.
    today = date(2026, 10, 23)
    d = {"kind": "medicine", "warning_signs": []}
    old = check_medicine({"name": "Panadol", "salt": "Paracetamol", "expiry": "2026-03", "batch": "B1",
                          "manufacturer": "X", "reg_no": "012345"}, d, today=today)
    assert old["level"] == "stop" and "Expired" in old["flags"][0], old
    fine = check_medicine({"name": "Panadol", "salt": "Paracetamol", "expiry": "2027-06", "batch": "B1",
                           "manufacturer": "X", "reg_no": "012345"}, d, today=today)
    assert fine["level"] == "ok", fine
    twice = check_medicine({"name": "Calpol", "salt": "paracetamol", "expiry": "2027-06", "batch": "B",
                            "manufacturer": "Y", "reg_no": "1"}, d, [{"name": "Panadol", "salt": "Paracetamol"}], today)
    assert any("same ingredient" in f for f in twice["flags"]), twice
    assert pattern_slots("Tab Amoxil 1+0+1 x 5/7") == ["morning", "night"]
    assert pattern_slots("1-1-1") == ["morning", "afternoon", "night"]
    ok = check_dose({"heard": "1+0+1 khane ke baad", "amount": "1 tablet", "times": ["morning", "night"],
                     "food": "after", "days": 5})
    assert ok["times"] == ["08:00", "21:00"] and ok["days"] == 5 and not ok["notes"], ok
    wrong = check_dose({"heard": "1+0+1", "amount": "1 tablet", "times": ["morning"], "days": 5})
    assert any("usually means" in n for n in wrong["notes"]), wrong
    cal = ics([{"name": "Amoxil", "strength": "500 mg", "amount": "1 tablet", "food": "after",
                "times": ["08:00", "21:00"], "days": 5}], today)
    assert cal.count("BEGIN:VEVENT") == 2 and "COUNT=5" in cal
    assert len(pieces(Image.new("RGB", (800, 1600)))) == 2 and len(pieces(Image.new("RGB", (1600, 900)))) == 1
    calls = []                                   # the same question is asked once, and a cached answer can't be changed
    ask_gemma = lambda c: calls.append(c) or {"medicines": [{"name": "Panadol"}]}  # noqa: E731
    pic = Image.new("RGB", (40, 40))
    ask([READ_PROMPT, pic])["medicines"].clear()
    assert ask([READ_PROMPT, pic])["medicines"] and len(calls) == 1
    ask([READ_PROMPT, Image.new("RGB", (40, 40), "red")])
    assert len(calls) == 2
    assert checked({"medicines": [{"name": "Calpol", "salt": "paracetamol"}]}, [{"name": "Panadol", "salt": "Paracetamol"}], today)["checks"][0]["flags"]
    print("self-check ok")
