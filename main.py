import os
import io
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from database import db, create_document, get_documents

# External services for translation and TTS
import requests

app = FastAPI(title="Indian Regional Language Dubbing API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.get("/")
def read_root():
    return {"message": "Indian Regional Language Dubber API is running"}

@app.get("/supported-languages")
def supported_languages():
    return SUPPORTED_LANGS

@app.post("/translate")
def translate_text(req: TranslateRequest):
    """
    Translate text using LibreTranslate public instance (for demo). In production, replace with a reliable provider.
    """
    if req.target_language not in SUPPORTED_LANGS:
        raise HTTPException(status_code=400, detail="Unsupported target language")

    payload = {
        "q": req.text,
        "source": req.source_language or "auto",
        "target": req.target_language,
        "format": "text"
    }
    try:
        # Public demo endpoint; rate-limited. Swap with your own instance if needed.
        r = requests.post("https://libretranslate.com/translate", data=payload, timeout=20)
        r.raise_for_status()
        data = r.json()
        translated = data.get("translatedText")
        if not translated:
            raise HTTPException(status_code=502, detail="Translation service failed")
        # Store a job entry
        job_id = create_document("job", {
            "source_type": "text",
            "source_text": req.text,
            "source_language": req.source_language,
            "target_language": req.target_language,
            "translation": translated,
            "status": "translated",
        })
        return {"translated": translated, "job_id": job_id}
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Translation API error: {str(e)}")

@app.post("/tts")
def text_to_speech(req: TTSRequest):
    """
    Generate speech audio using the public Coqui TTS demo API for supported Indian languages where available.
    For a production app, integrate with a robust TTS provider (Azure, Google Cloud, ElevenLabs with Indian voices).
    """
    if req.language not in SUPPORTED_LANGS:
        raise HTTPException(status_code=400, detail="Unsupported language for TTS")

    # We'll call a simple TTS service: the Voice RSS API-style demo via ttsmp3-like endpoints is unreliable.
    # As a safe demo, we'll return a placeholder response indicating where audio would be generated.
    # Frontend will handle that as a URL to stream once integrated.
    return {"message": "TTS demo endpoint - integrate with a real TTS provider for audio output.", "language": req.language}

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
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
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
