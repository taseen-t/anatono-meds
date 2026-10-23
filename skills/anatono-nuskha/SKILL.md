---
name: anatono-nuskha
description: Read a photo of a medicine strip, box or handwritten prescription (nuskha) with Gemma 4, flag warning signs (expired, missing batch or registration number, the same ingredient twice), and turn the dose into a daily routine with calendar alarms. Use when someone shares a medicine or prescription photo, asks "how do I take this", or wants medicine reminders. Understands English, Urdu, Roman Urdu and prescription shorthand like 1+0+1, BD, TDS.
license: MIT
---

# Anatono nuskha: medicine photo → checks → reminders

Gemma 4 does the reading and the understanding. Plain code does every check and every time calculation, so a
wrong guess by the model can't silently become a wrong dose.

## Run it

```bash
python3 skills/anatono-nuskha/scripts/nuskha.py PHOTO
python3 skills/anatono-nuskha/scripts/nuskha.py PHOTO --dose "ek goli subah aur raat khane ke baad" --ics reminders.ics
```

Needs `GEMINI_API_KEY` in the repo's `.env` and `pip install -r requirements.txt`. It prints JSON:
`medicines` (name, strength, what it's for, `check`, `flags`) and `routine` (amount, food, `times` as HH:MM, `days`,
`notes`). On a prescription, each medicine's written dose (e.g. `1+0+1 x 5 days`) is used unless you pass `--dose`.

## What the checks mean

- `ok`: nothing wrong found.
- `careful`: something to look at: expires soon, a missing batch/expiry/maker/registration number on a pack, the
  same ingredient as another medicine in the routine, or a warning sign Gemma saw. Tell the person each flag.
- `stop`: expired, or the dates on the pack are impossible. **No reminders are set.** Tell them not to take it
  and to show it to a pharmacist.

## Rules for the agent

1. Read the flags and the routine back to the person and get a yes before saving anything.
2. Never change, round or "fix" a dose. If `notes` say something was unclear, ask the person or their doctor.
3. A photo can't prove a medicine is genuine. Say "warning signs", never "fake" or "real".
4. This is a reminder tool, not medical advice.
