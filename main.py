import os
import io
import uuid
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

from database import db, create_document

# External services for translation
import requests

app = FastAPI(title="Indian Regional Language Dubbing API (MVP)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure outputs directory exists for audio files
OUTPUT_DIR = os.path.join(os.getcwd(), "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=OUTPUT_DIR), name="outputs")

class TranslateRequest(BaseModel):
    text: str
    target_language: str  # e.g., 'hi', 'bn', 'ta', 'te', 'ml', 'mr', 'gu', 'kn', 'pa', 'or', 'as'
    source_language: Optional[str] = None

class TTSRequest(BaseModel):
    text: str
    language: str
    voice: Optional[str] = None

SUPPORTED_LANGS = {
    "hi": "Hindi",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "ml": "Malayalam",
    "mr": "Marathi",
    "gu": "Gujarati",
    "kn": "Kannada",
    "pa": "Punjabi",
    "or": "Odia",
    "as": "Assamese",
}

# gTTS supported subset for a reliable MVP (others may fail)
# We'll attempt and gracefully handle unsupported languages at runtime too
GTTS_POSSIBLE = {"hi", "bn", "ta", "te", "ml", "mr", "gu", "kn", "pa"}

@app.get("/")
def read_root():
    return {"message": "Indian Regional Language Dubber API is running"}

@app.get("/supported-languages")
def supported_languages():
    return SUPPORTED_LANGS


def _translate_via_libre(text: str, target: str, source: Optional[str] = None) -> Optional[str]:
    url = os.getenv("LIBRETRANSLATE_URL", "https://libretranslate.com")
    endpoint = f"{url.rstrip('/')}/translate"
    payload = {
        "q": text,
        "source": source or "auto",
        "target": target,
        "format": "text",
    }
    r = requests.post(endpoint, data=payload, timeout=12)
    r.raise_for_status()
    data = r.json()
    return data.get("translatedText")


def _translate_via_mymemory(text: str, target: str, source: Optional[str] = None) -> Optional[str]:
    # MyMemory free endpoint; limited but OK for MVP
    src = source or "auto"
    endpoint = "https://api.mymemory.translated.net/get"
    params = {"q": text, "langpair": f"{src}|{target}"}
    r = requests.get(endpoint, params=params, timeout=12)
    r.raise_for_status()
    data = r.json()
    if data and data.get("responseData"):
        return data["responseData"].get("translatedText")
    return None


@app.post("/translate")
def translate_text(req: TranslateRequest):
    """
    MVP translation with resilient fallbacks:
    1) LibreTranslate (public or custom URL if set)
    2) MyMemory free API
    3) Fallback: return original text (so demo never 504s)
    """
    if req.target_language not in SUPPORTED_LANGS:
        raise HTTPException(status_code=400, detail="Unsupported target language")

    translated = None
    errors = []

    try:
        translated = _translate_via_libre(req.text, req.target_language, req.source_language)
    except Exception as e:
        errors.append(f"LibreTranslate error: {str(e)}")

    if not translated:
        try:
            translated = _translate_via_mymemory(req.text, req.target_language, req.source_language)
        except Exception as e:
            errors.append(f"MyMemory error: {str(e)}")

    if not translated:
        # Last-resort fallback to keep demo flowing
        translated = req.text

    # Try to store a job if DB is configured; ignore errors for MVP stability
    try:
        if db is not None:
            create_document("job", {
                "source_type": "text",
                "source_text": req.text,
                "source_language": req.source_language,
                "target_language": req.target_language,
                "translation": translated,
                "status": "translated",
            })
    except Exception:
        pass

    return {"translated": translated, "notes": errors[:2]}


@app.post("/tts")
def text_to_speech(req: TTSRequest, request: Request):
    """
    MVP TTS using gTTS locally (no external keys). Saves MP3 under /outputs and returns a URL.
    Some languages may not be supported by gTTS; we handle failures gracefully.
    """
    if req.language not in SUPPORTED_LANGS:
        raise HTTPException(status_code=400, detail="Unsupported language for TTS")

    # Lazy import to speed cold starts and avoid import cost for unused endpoint
    try:
        from gtts import gTTS  # type: ignore
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS engine unavailable: {str(e)}")

    # Attempt synthesis
    filename = f"tts_{uuid.uuid4().hex}.mp3"
    filepath = os.path.join(OUTPUT_DIR, filename)

    try:
        tts = gTTS(text=req.text, lang=req.language)
        tts.save(filepath)
    except Exception as e:
        # Provide clear feedback and do not crash the demo
        raise HTTPException(status_code=502, detail=f"TTS failed for '{req.language}'. Try a different language (e.g., hi). Error: {str(e)}")

    audio_url = f"/outputs/{filename}"

    # Try to store job info if DB available; ignore failures
    try:
        if db is not None:
            create_document("job", {
                "source_type": "text",
                "source_text": req.text,
                "target_language": req.language,
                "audio_filename": filename,
                "status": "tts_generated",
            })
    except Exception:
        pass

    return {"audio_url": audio_url}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = getattr(db, 'name', None) or "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
