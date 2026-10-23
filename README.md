# Anatono

**Never miss a dose again.** Snap a medicine strip, a box or a whole handwritten prescription. Say or type how you
take it, in English, Urdu or Roman Urdu. Anatono turns it into reminders, and checks every medicine for warning signs
before you take it. Made for elders and the people who look after them, at Hack Day Faisalabad, 23 Oct 2026.

> **Verify in 30 seconds**
> | | |
> |---|---|
> | **Model** | **Gemma 4** (`gemma-4-26b-a4b-it`; `gemma-4-31b-it` only as a fallback) through the **Gemini API** (`google-genai`). [`anatono.py` lines 21–22](anatono.py#L21) |
> | **Where Gemma is called** | `ask()` in [`anatono.py` line 60](anatono.py#L60): reads every photo (`read_photo`) and understands every dose (`understand_dose`) |
> | **Voice** | `gemini-3.5-flash-lite` **only writes down what was said** ([line 25](anatono.py#L25)), because Gemma 4 on the API doesn't take audio. Gemma 4 does all the understanding. |
> | **Harness** | Plain-code checks after every Gemma answer: expiry, impossible dates, missing batch / registration number, same ingredient twice, prescription shorthand (`1+0+1`, `BD`, `TDS`) cross-checked against Gemma's times, max 6 a day, 1–365 days. `python3 anatono.py` runs the self-check. |
> | **Agent skill** | [`skills/anatono-nuskha/SKILL.md`](skills/anatono-nuskha/SKILL.md) + script (`agentskills validate` → valid) |
> | **Licence** | MIT ([LICENSE](LICENSE)) |
> | **Key dependencies** | `google-genai`, `starlette`, `uvicorn`, `pillow`, `python-dotenv` ([requirements.txt](requirements.txt)); in the browser: Lucide icons (ISC), GSAP (free licence), Simple Icons (CC0), EB Garamond and Figtree (OFL) |

## How it works

```
photo (camera or gallery) ──► Gemma 4 reads it ──► code checks it ──► the person sees what was read + any warnings
"subah aur raat khane ke baad" ──► Gemma 4 understands it ──► code turns it into times and days ──► the person confirms
                                                                  └──► reminders: on the phone + calendar alarms (.ics)
```

1. **Read.** Gemma 4 reads the name, salt, strength, maker, batch, dates and registration number off a pack, or every
   line of a handwritten prescription, plus what each medicine is for in English and Urdu.
2. **Check.** Code, not the model, decides `ok` / `careful` / `stop`. An expired medicine gets no reminders.
3. **Understand the dose.** Typed or spoken, in any mix of languages. Code maps it to clock times (morning 8:00,
   afternoon 2:00, evening 6:00, night 9:00) and flags anything unclear.
4. **Confirm and remind.** Nothing is saved until the person taps "Add to my routine". Reminders show in the app and go
   into the phone's own calendar, so they ring even when the app is closed.

## Run it

```bash
pip install -r requirements.txt
echo "GEMINI_API_KEY=your-key-from-aistudio.google.com" > .env
python3 server.py            # http://localhost:8600 (landing page) and http://localhost:8600/app.html (the app)
```

In the app, **Try a sample** loads [`site/samples/prescription.jpg`](site/samples/prescription.jpg), a made-up
prescription (no real doctor or patient).

## Layout

| Path | What it is |
|---|---|
| `anatono.py` | Gemma 4 calls, the checks, the dose rules, the calendar file |
| `server.py` | Starlette server: `/api/read`, `/api/dose`, `/api/calendar`, and the site |
| `site/index.html` | The landing page |
| `site/app.html` | The app (phone first): photo, checks, dose, routine, reminders |
| `skills/anatono-nuskha/` | The agent skill |

## Limits, honestly

- A photo can't prove a medicine is genuine. Anatono shows **warning signs**, and says so.
- It helps people remember what their doctor prescribed. It isn't medical advice and never changes a dose.
- Photos are sent to Google's Gemini API to be read. The routine stays on the phone.
- Testimonials on the landing page are placeholders, marked SAMPLE.
