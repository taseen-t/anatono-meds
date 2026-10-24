# Anatono

**Never miss a dose again.** Snap a medicine strip, a box or a whole handwritten prescription. Say or type how you
take it, in English, Urdu or Roman Urdu. Anatono turns it into reminders, and checks every medicine for warning signs
before you take it. Made for elders and the people who look after them.

Made by **Taseen Tariq** at Hack Day Faisalabad, 23 October 2026.

**Try it:** [anatono.site](https://anatono.site) (landing page) · [anatono.site/app.html](https://anatono.site/app.html)
(the app) · [Android app (APK)](https://anatono.site/anatono.apk)

[![Watch the 30-second demo](site/demo-poster.jpg)](https://anatono.site/demo.mp4)

**▶ [Watch the 30-second demo](https://anatono.site/demo.mp4)**: a real run of the app (Gemma 4's waits shown sped up), with captions.

> **Verify in 30 seconds**
> | | |
> |---|---|
> | **Model** | **Gemma 4** (`gemma-4-26b-a4b-it`; `gemma-4-31b-it` only as a fallback) through the **Gemini API** (`google-genai`). Licence: [Apache 2.0](https://ai.google.dev/gemma/apache_2). [`anatono.py` line 24](anatono.py#L24) |
> | **Where Gemma is called** | `ask()` in [`anatono.py` line 69](anatono.py#L69) → `ask_gemma()` ([line 85](anatono.py#L85)). It reads every photo (`read_photo`) and understands every dose (`understand_dose`) |
> | **Voice** | `gemini-3.5-flash-lite` **only writes down what was said** ([line 28](anatono.py#L28)), because Gemma 4 on the API doesn't take audio. Gemma 4 does all the understanding. |
> | **Harness** | Plain-code checks after every answer: expiry, impossible dates, missing batch / registration number, same ingredient twice, prescription shorthand (`1+0+1`, `BD`, `TDS`) cross-checked against Gemma's times, max 6 a day, 1–365 days. `python3 anatono.py` runs the self-check. |
> | **Agent skill** | [`skills/anatono-nuskha/SKILL.md`](skills/anatono-nuskha/SKILL.md) + script (`agentskills validate` → valid) |
> | **Licence** | MIT ([LICENSE](LICENSE)) |
> | **Key dependencies** | `google-genai`, `starlette`, `uvicorn`, `pillow`, `python-dotenv` ([requirements.txt](requirements.txt)); in the browser: Lucide icons (ISC), GSAP (free licence), Simple Icons (CC0), EB Garamond and Figtree (OFL) |

## How it works

1. **Read.** Gemma 4 reads the name, salt, strength, maker, batch, dates and registration number off a pack, or every
   line of a handwritten prescription, plus what each medicine is for in English and Urdu.
2. **Check.** Code, not the model, decides `ok` / `careful` / `stop`. An expired medicine gets no reminders.
3. **Understand the dose.** Typed or spoken, in any mix of languages. Code maps it to clock times (morning 8:00,
   afternoon 2:00, evening 6:00, night 9:00) and flags anything unclear.
4. **Confirm and remind.** Nothing is saved until the person taps "Add to my routine". Reminders show in the app and go
   into the phone's own calendar, so they ring even when the app is closed.

### The complete flow

Colours show where each step runs: **on the phone**, **plain code on the server** (`anatono.py`), or **a Google
model**. The model only reads and understands; code makes every decision.

```mermaid
flowchart TD
  start(["Open the app"]) --> src{"How do you add a medicine?"}
  src -->|"Take a photo · From gallery · Try a sample"| shrink["Photo shrunk to 1600 px,<br/>SHA-256 of the photo"]
  src -->|"No photo? Type the name"| typed["A card from the typed name"]
  shrink --> seen{"Read this photo before?"}
  seen -->|"yes"| cached["Send what was read,<br/>not the photo"]
  seen -->|"no"| tall{"A tall page?<br/>(a full prescription)"}
  tall -->|"yes"| cut["Cut into 2 overlapping halves,<br/>read part 1 first"]
  tall -->|"no"| read
  cut --> read["Gemma 4 reads it:<br/>name, salt, strength, maker, batch,<br/>dates, reg. no., dose as written"]
  read --> checks
  cached --> checks["Code checks each medicine:<br/>expired? made-on after expiry?<br/>batch, expiry, maker, reg. no. printed?<br/>same salt as your routine? warning signs?"]
  checks --> level{"Level, set by code"}
  checks -.-> explain["Gemma 4: what it's for,<br/>in English and Urdu"]
  explain -.-> cards
  level -->|"stop: expired, or 3+ cautions"| stopc["Don't take this one.<br/>Show it to your pharmacist.<br/>No dose form, no reminders"]
  level -->|"careful"| cards["A card per medicine,<br/>with the reasons"]
  level -->|"ok"| cards
  cards --> more{"More of a long<br/>prescription left?"}
  more -->|"Read the remaining medicines"| read
  more -->|"no"| how
  typed --> how{"How do you take it?<br/>English, Urdu, Roman Urdu"}
  how -->|"type it"| understand
  how -->|"tap the mic"| hear["Gemini Flash-Lite writes down<br/>the words, nothing more"]
  hear --> understand["Gemma 4 understands it:<br/>amount, times, food, days,<br/>only when needed"]
  understand --> dosecheck["Code: morning 8:00, afternoon 14:00,<br/>evening 18:00, night 21:00;<br/>1+0+1 cross-checked; max 6 a day;<br/>1-365 days; notes on anything unclear"]
  dosecheck --> confirm["You see what was understood<br/>and can change the times"]
  confirm -->|"Add to my routine"| saved[("Saved on this phone<br/>(nothing is saved before this tap)")]
  saved --> today["Today: a tick per dose,<br/>the next dose"]
  saved --> ics["Add to my calendar:<br/>.ics alarms that ring<br/>with the app closed"]
  saved --> alerts["Alerts while<br/>Anatono is open"]

  classDef phone fill:#E1EEE6,stroke:#0B3B36,color:#0B3B36
  classDef code fill:#FFE7A8,stroke:#0B3B36,color:#0B3B36
  classDef model fill:#FFC7B5,stroke:#0B3B36,color:#0B3B36
  classDef stop fill:#FBE1DC,stroke:#C2412D,color:#C2412D
  class start,src,shrink,typed,seen,cached,cards,more,how,confirm,saved,today,ics,alerts phone
  class tall,cut,checks,level,dosecheck code
  class read,explain,hear,understand model
  class stopc stop
```

### Read once, not twice

A prescription that was already read isn't sent to the model again. The phone keeps what was read (keyed by a SHA-256
of the photo and the part), and the server keeps every answer in memory too. On a repeat, only the code
checks run again, because they depend on today's date and on what's already in the routine. Typed doses and the
"what is it for" lines are kept the same way.

## Architecture

```mermaid
flowchart LR
  subgraph phone["On the phone"]
    app["Web app<br/>site/app.html"]
    apk["Android app<br/>anatono.apk<br/>(Trusted Web Activity)"]
    ios["Native iPhone app<br/>(SwiftUI, same API)"]
    store[("localStorage:<br/>routine, ticks,<br/>what was read")]
    cal["Phone calendar<br/>(.ics alarms)"]
  end

  subgraph vercel["anatono.site on Vercel"]
    static["Static files: site/<br/>landing page, app,<br/>demo video, APK"]
    server["server.py (Starlette)<br/>POST /api/read<br/>POST /api/explain<br/>POST /api/dose<br/>POST /api/calendar"]
    core["anatono.py<br/>ask(): one call per question,<br/>answers kept in memory<br/>checks · dose rules · .ics"]
  end

  subgraph google["Google Gemini API"]
    gemma["Gemma 4<br/>gemma-4-26b-a4b-it<br/>(31b only as a fallback)"]
    lite["Gemini Flash-Lite<br/>voice notes to words only"]
  end

  skill["Agent skill<br/>skills/anatono-nuskha"]

  apk -->|"opens"| app
  static -->|"served to"| app
  app <-->|"read / save"| store
  app -->|"photo, dose, routine (JSON)"| server
  ios -->|"same JSON"| server
  server --> core
  server -->|"anatono-reminders.ics"| cal
  skill -->|"imports"| core
  core -->|"photos, typed doses"| gemma
  core -->|"recordings"| lite
```

- **The phone keeps everything personal.** The routine, the ticks and what was read live in the browser's
  `localStorage`; there is no account and no database.
- **The server holds the key and the rules.** `GEMINI_API_KEY` is a Vercel environment variable, so the browser never
  sees it. `server.py` is a thin layer of four routes; `anatono.py` has the prompts, the model calls, the code checks,
  the dose rules and the calendar file.
- **The model reads, the code decides.** Gemma 4 turns a photo or a sentence into JSON. `check_medicine()` and
  `check_dose()` in plain Python decide `ok` / `careful` / `stop` and the exact reminder times, so a wrong guess by the
  model can't quietly become a wrong dose.
- **The agent skill** runs the same pipeline from the command line (photo in, checks and `.ics` out), no server needed.

## Run it

```bash
pip install -r requirements.txt
echo "GEMINI_API_KEY=your-key-from-aistudio.google.com" > .env
python3 server.py            # http://localhost:8600 (landing page) and http://localhost:8600/app.html (the app)
python3 anatono.py           # self-check of the code checks and the cache (no API call)
```

In the app, **Try a sample** loads [`site/samples/prescription.jpg`](site/samples/prescription.jpg), a made-up
prescription (no real doctor or patient).

On the live site, the key is a Vercel environment variable (`GEMINI_API_KEY`).

## Android app

[`anatono.apk`](https://anatono.site/anatono.apk) is a Trusted Web Activity made with
[Bubblewrap](https://github.com/GoogleChromeLabs/bubblewrap): the real app at anatono.site/app.html, full screen,
with its own icon. [`site/.well-known/assetlinks.json`](site/.well-known/assetlinks.json) proves the app and the site
belong together, so Android shows no browser bar. On a phone: open the link, allow "install unknown apps" for the
browser, install. The web app can also be installed straight from Chrome (⋮ → Add to Home screen).

## Layout

| Path | What it is |
|---|---|
| `anatono.py` | Model calls (Gemma 4), the answer cache, the checks, the dose rules, the calendar file |
| `server.py` | Starlette server: `/api/read`, `/api/explain`, `/api/dose`, `/api/calendar`, and the site |
| `site/index.html` | The landing page, with the demo video |
| `site/app.html` | The app (phone first): photo, checks, dose, routine, reminders |
| `site/anatono.apk` | The Android app |
| `skills/anatono-nuskha/` | The agent skill |

## Limits, honestly

- A photo can't prove a medicine is genuine. Anatono shows **warning signs**, and says so.
- It helps people remember what their doctor prescribed. It isn't medical advice and never changes a dose.
- Photos are sent to Google's Gemini API to be read. The routine stays on the phone.
- Testimonials on the landing page are placeholders, marked SAMPLE.

## Author

Taseen Tariq · [github.com/taseen-t](https://github.com/taseen-t) · MIT licence
