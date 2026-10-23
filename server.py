"""Anatono server: the website + app in site/, and three API routes. Run: python3 server.py  (http://localhost:8600)
The Gemini API key stays here on the server; the browser never sees it."""
import json

import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

import anatono as A

MAX_BODY = 12 * 2**20          # a phone photo as base64


async def body(request):
    raw = await request.body()
    if len(raw) > MAX_BODY:
        raise ValueError("That photo is too big. Try again with a smaller one.")
    return json.loads(raw or b"{}")


async def read(request):
    """Photo of a medicine or prescription -> what Gemma read + code checks."""
    try:
        b = await body(request)
        if not str(b.get("image", "")).startswith("data:image/"):
            return JSONResponse({"error": "Send a photo (data:image/...)."}, 400)
        return JSONResponse(A.read_photo(b["image"], b.get("routine") or []))
    except Exception as e:  # noqa: BLE001 - tell the app what went wrong
        return JSONResponse({"error": str(e)}, 500)


async def dose(request):
    """What the person typed or said -> routine Gemma understood + code checks."""
    try:
        b = await body(request)
        text, audio = str(b.get("text") or "").strip()[:500], b.get("audio")
        if audio:
            if not str(audio).startswith("data:audio/"):
                return JSONResponse({"error": "Send the recording as data:audio/..."}, 400)
            mime = str(audio)[5:].split(";")[0]
            return JSONResponse(A.understand_dose(b.get("medicine") or {}, audio=audio, mime=mime))
        if not text:
            return JSONResponse({"error": "Type or say how you take it."}, 400)
        return JSONResponse(A.understand_dose(b.get("medicine") or {}, text))
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": str(e)}, 500)


async def calendar(request):
    """The routine as calendar alarms (.ics), so reminders ring even when the app is closed."""
    b = await body(request)
    return Response(A.ics(b.get("routine") or []), media_type="text/calendar",
                    headers={"Content-Disposition": 'attachment; filename="anatono-reminders.ics"'})


app = Starlette(routes=[Route("/api/read", read, methods=["POST"]), Route("/api/dose", dose, methods=["POST"]),
                        Route("/api/calendar", calendar, methods=["POST"]),
                        Mount("/", StaticFiles(directory="site", html=True))])

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8600)
