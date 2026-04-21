"""
video_creator.py — Real video generation using HeyGen, ElevenLabs, and fal.ai

Modes:
  "talking"    — HeyGen Talking Photo: character image + ElevenLabs voice → lip-synced video
  "animation"  — fal.ai Kling: character image → animated motion video
  "voice_only" — ElevenLabs: text → audio file (mp3)

HeyGen talking pipeline:
  1. GPT-4o writes a character-appropriate script
  2. ElevenLabs TTS → saves .mp3 to local /tmp/audio/
  3. HeyGen uploads the image as a "talking photo"
  4. HeyGen generates a lip-synced video using the audio URL
  5. Poll HeyGen until complete, download .mp4 locally

fal.ai animation pipeline:
  1. GPT-4o writes a Kling motion prompt
  2. fal_client.subscribe() → Kling image-to-video
  3. Download .mp4 locally
"""

import os
import uuid
import io
import base64
import time
import requests
from pathlib import Path
from PIL import Image
from openai import OpenAI

# ── ElevenLabs ────────────────────────────────────────────────────────────────
try:
    from elevenlabs.client import ElevenLabs
    from elevenlabs import VoiceSettings
    HAS_EL = True
except ImportError:
    HAS_EL = False

# ── fal.ai ────────────────────────────────────────────────────────────────────
try:
    import fal_client
    HAS_FAL = True
except ImportError:
    HAS_FAL = False

# ── Constants ─────────────────────────────────────────────────────────────────
OPENAI_MODEL  = "gpt-4o"
HEYGEN_BASE   = "https://api.heygen.com"
FAL_IMG2VID   = "fal-ai/kling-video/v1/standard/image-to-video"
FAL_TXT2VID   = "fal-ai/kling-video/v1/standard/text-to-video"

# Default ElevenLabs voice IDs per Moodster character
# Users can override these in Settings → Character Voices
DEFAULT_VOICES = {
    "Coz":    "jBpfuIE2acCO8z3wKNLl",  # Gigi — bright, energetic
    "Lolly":  "XrExE9yKIg1WjnnlVkGX",  # Matilda — warm, nurturing
    "Tully":  "onwK4e9ZLuTAKqWW03F9",  # Daniel — calm, measured
    "Razzy":  "N2lVS1w4EtoT3dr4eOWO",  # Callum — intense, dynamic
    "Quigly": "IKne3meq5aSn9XLyUdCD",  # Charlie — nervous, gentle
    "Snorf":  "pFZP5JQG7iQjIQuC4Bku",  # Lily — soft, gentle
}

MOODSTERS = {
    "Coz":    {"emotion": "Happy",    "color": "#FFD700", "style": "energetic and joyful"},
    "Lolly":  {"emotion": "Loving",   "color": "#FF69B4", "style": "warm and nurturing"},
    "Tully":  {"emotion": "Calm",     "color": "#4CAF50", "style": "peaceful and slow"},
    "Razzy":  {"emotion": "Angry",    "color": "#E53935", "style": "passionate then cooling"},
    "Quigly": {"emotion": "Scared",   "color": "#FF9800", "style": "timid then brave"},
    "Snorf":  {"emotion": "Sad",      "color": "#1976D2", "style": "gentle and soft"},
}

VIDEO_TYPES = {
    "social_reel":      "Fun, upbeat 15–30s social media clip",
    "character_intro":  "Character introduces themselves and their emotion",
    "coping_tip":       "Character teaches a coping strategy (breathing, counting, etc.)",
    "story_moment":     "Character acts out a short emotional moment",
    "celebration":      "Character celebrates with dancing and confetti energy",
}

ASPECT_RATIOS = {
    "9:16": "Vertical (Reels, TikTok, Stories)",
    "1:1":  "Square (Instagram feed)",
    "16:9": "Landscape (YouTube)",
}


# ── Image helpers ──────────────────────────────────────────────────────────────
def _prep_image_b64(path: str, max_px: int = 1024) -> str:
    img = Image.open(path).convert("RGB")
    if max(img.width, img.height) > max_px:
        img.thumbnail((max_px, max_px), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return base64.b64encode(buf.getvalue()).decode()


def _data_url(b64: str) -> str:
    return f"data:image/jpeg;base64,{b64}"


# ── GPT-4o helpers ─────────────────────────────────────────────────────────────
def _analyze_character(openai_key: str, image_path: str = None,
                        text: str = None) -> tuple[str, str]:
    """Returns (character_name, full_analysis_text)."""
    client = OpenAI(api_key=openai_key)

    char_list = "\n".join(
        f"- {n}: {v['emotion']} | {v['color']}" for n, v in MOODSTERS.items()
    )

    if image_path:
        b64 = _prep_image_b64(image_path)
        resp = client.chat.completions.create(
            model=OPENAI_MODEL, max_tokens=500, temperature=0.2,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": f"""Identify this Moodsters character.
Characters: {char_list}
Output:
NAME: [exact character name, or "Unknown"]
EMOTION: [their emotion]
EXPRESSION: [describe pose/expression exactly]
SETTING: [background if visible]
NOTES: [anything else useful]"""},
                {"type": "image_url",
                 "image_url": {"url": _data_url(b64), "detail": "high"}},
            ]}],
        )
    else:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL, max_tokens=300, temperature=0.2,
            messages=[
                {"role": "system", "content": f"You identify Moodsters characters.\nCharacters:\n{char_list}"},
                {"role": "user", "content": f"Identify from: {text}\nOutput NAME, EMOTION, EXPRESSION, NOTES."},
            ],
        )

    analysis = resp.choices[0].message.content.strip()

    # Extract character name
    name = "Razzy"  # fallback
    for line in analysis.split("\n"):
        if line.startswith("NAME:"):
            raw = line.replace("NAME:", "").strip()
            for n in MOODSTERS:
                if n.lower() in raw.lower():
                    name = n
                    break
            break

    return name, analysis


def _write_script(openai_key: str, char_name: str, char_analysis: str,
                   video_type: str, duration: str) -> str:
    """GPT-4o writes a script for the character to speak."""
    client = OpenAI(api_key=openai_key)
    info   = MOODSTERS.get(char_name, MOODSTERS["Razzy"])
    vtype  = VIDEO_TYPES.get(video_type, VIDEO_TYPES["social_reel"])

    resp = client.chat.completions.create(
        model=OPENAI_MODEL, max_tokens=300, temperature=0.8,
        messages=[
            {"role": "system", "content":
                f"You write short scripts for {char_name}, a children's character "
                f"who represents {info['emotion']}. Voice style: {info['style']}. "
                "Speak directly to a child age 3–6. Warm, simple words. Short sentences."},
            {"role": "user", "content":
                f"Write a {duration}-second spoken script for {char_name}.\n"
                f"Video type: {vtype}\n"
                f"Character analysis: {char_analysis}\n\n"
                "Rules:\n"
                "- Speak AS the character (first person)\n"
                "- Max 60 words for 15s, 100 words for 30s\n"
                "- Child-friendly, warm, encouraging\n"
                "- No stage directions — just the spoken words\n"
                "Output ONLY the script text, nothing else."},
        ],
    )
    return resp.choices[0].message.content.strip()


def _write_motion_prompt(openai_key: str, char_name: str, char_analysis: str,
                          video_type: str, aspect_ratio: str, duration: str) -> str:
    """GPT-4o writes a Kling motion prompt."""
    client = OpenAI(api_key=openai_key)
    vtype  = VIDEO_TYPES.get(video_type, VIDEO_TYPES["social_reel"])

    resp = client.chat.completions.create(
        model=OPENAI_MODEL, max_tokens=200, temperature=0.7,
        messages=[
            {"role": "system", "content":
                "You write concise Kling AI motion prompts. "
                "Describe MOTION and ATMOSPHERE only (not appearance). "
                "Be specific: camera movement, character motion, lighting. Max 60 words."},
            {"role": "user", "content":
                f"Motion prompt for {char_name} ({char_analysis[:200]}).\n"
                f"Type: {vtype}. Duration: {duration}s. Ratio: {aspect_ratio}.\n"
                "Make it playful, child-friendly, bright colors, Moodsters energy.\n"
                "Output ONLY the prompt, nothing else."},
        ],
    )
    return resp.choices[0].message.content.strip()


# ── ElevenLabs TTS ─────────────────────────────────────────────────────────────
def _generate_audio(el_key: str, script: str, char_name: str,
                     voice_overrides: dict, save_dir: Path) -> str:
    """Generate .mp3 with ElevenLabs. Returns filename (stem only, no ext)."""
    if not HAS_EL:
        raise ImportError("elevenlabs package not installed.")

    save_dir.mkdir(parents=True, exist_ok=True)
    el      = ElevenLabs(api_key=el_key)
    vid_id  = voice_overrides.get(char_name) or DEFAULT_VOICES.get(char_name, DEFAULT_VOICES["Razzy"])
    info    = MOODSTERS.get(char_name, {})

    # stability/similarity tuned to emotion
    stability   = 0.8 if info.get("emotion") in ("Calm", "Loving", "Sad") else 0.5
    similarity  = 0.75

    audio_gen = el.text_to_speech.convert(
        voice_id   = vid_id,
        text       = script,
        model_id   = "eleven_multilingual_v2",
        voice_settings = VoiceSettings(
            stability        = stability,
            similarity_boost = similarity,
        ),
    )

    filename = str(uuid.uuid4())
    path     = save_dir / f"{filename}.mp3"
    with open(path, "wb") as f:
        for chunk in audio_gen:
            if chunk:
                f.write(chunk)

    return filename


# ── HeyGen Talking Photo ────────────────────────────────────────────────────────
def _heygen_upload_photo(hg_key: str, image_path: str) -> str:
    """Upload image to HeyGen, return talking_photo_id."""
    with open(image_path, "rb") as f:
        img_bytes = f.read()

    # Determine mime type
    ext  = Path(image_path).suffix.lower()
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
            "png": "image/png",  "gif": "image/gif",
            "webp": "image/webp"}.get(ext.strip("."), "image/jpeg")

    resp = requests.post(
        f"{HEYGEN_BASE}/v1/talking_photo",
        headers={"X-Api-Key": hg_key, "Content-Type": mime},
        data=img_bytes,
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()

    if data.get("error"):
        raise RuntimeError(f"HeyGen upload error: {data['error']}")

    return data["data"]["talking_photo_id"]


def _heygen_generate(hg_key: str, talking_photo_id: str,
                      audio_url: str, aspect_ratio: str) -> str:
    """Start HeyGen video generation. Returns video_id."""
    # Map aspect_ratio → HeyGen dimension
    dims = {
        "9:16":  {"width": 720,  "height": 1280},
        "1:1":   {"width": 1080, "height": 1080},
        "16:9":  {"width": 1280, "height": 720},
    }.get(aspect_ratio, {"width": 720, "height": 1280})

    payload = {
        "video_inputs": [{
            "character": {
                "type": "talking_photo",
                "talking_photo_id": talking_photo_id,
            },
            "voice": {
                "type":      "audio",
                "audio_url": audio_url,
            },
            "background": {
                "type":  "color",
                "value": "#1A1A2E",
            },
        }],
        "dimension": dims,
        "test": False,
    }

    resp = requests.post(
        f"{HEYGEN_BASE}/v2/video/generate",
        headers={"X-Api-Key": hg_key, "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()

    if data.get("error"):
        raise RuntimeError(f"HeyGen generate error: {data['error']}")

    return data["data"]["video_id"]


def _heygen_poll(hg_key: str, video_id: str,
                  timeout: int = 600) -> str:
    """Poll until HeyGen video is complete. Returns video download URL."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(
            f"{HEYGEN_BASE}/v1/video_status.get?video_id={video_id}",
            headers={"X-Api-Key": hg_key},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        status = data.get("status", "")

        if status == "completed":
            return data["video_url"]
        if status == "failed":
            raise RuntimeError(f"HeyGen failed: {data.get('error', 'unknown')}")

        time.sleep(8)

    raise TimeoutError("HeyGen video generation timed out after 10 minutes.")


def _download_file(url: str, save_dir: Path, ext: str = "mp4") -> str:
    """Download URL to save_dir. Returns filename stem."""
    save_dir.mkdir(parents=True, exist_ok=True)
    fid  = str(uuid.uuid4())
    path = save_dir / f"{fid}.{ext}"
    r    = requests.get(url, timeout=120)
    r.raise_for_status()
    path.write_bytes(r.content)
    return fid


# ── fal.ai Animation ────────────────────────────────────────────────────────────
def _fal_animate(fal_key: str, prompt: str,
                  image_path: str = None,
                  duration: str = "5",
                  aspect_ratio: str = "9:16") -> str:
    """Run Kling on fal.ai. Returns video URL."""
    if not HAS_FAL:
        raise ImportError("fal_client not installed.")
    os.environ["FAL_KEY"] = fal_key

    if image_path:
        b64    = _prep_image_b64(image_path)
        result = fal_client.subscribe(
            FAL_IMG2VID,
            arguments={
                "prompt":       prompt,
                "image_url":    _data_url(b64),
                "duration":     duration,
                "aspect_ratio": aspect_ratio,
            },
        )
    else:
        result = fal_client.subscribe(
            FAL_TXT2VID,
            arguments={
                "prompt":       prompt,
                "duration":     duration,
                "aspect_ratio": aspect_ratio,
            },
        )

    return result["video"]["url"]


# ── Public entry points ─────────────────────────────────────────────────────────

def generate_talking_video(openai_key: str,
                            heygen_key: str,
                            elevenlabs_key: str,
                            video_type: str    = "social_reel",
                            aspect_ratio: str  = "9:16",
                            duration: str      = "15",
                            image_path: str    = None,
                            text: str          = None,
                            app_base_url: str  = "",
                            audio_dir: Path    = Path("/tmp/audio"),
                            video_dir: Path    = Path("/tmp/videos"),
                            voice_overrides: dict = None,
                            progress_cb=None) -> dict:
    """
    HeyGen + ElevenLabs pipeline: character image → lip-synced talking video.
    app_base_url: the public URL of the Flask app (e.g. https://myapp.railway.app/)
                  used so HeyGen can fetch the ElevenLabs audio file.
    """
    def emit(msg):
        if progress_cb: progress_cb(msg)

    emit("Analyzing character…")
    char_name, char_analysis = _analyze_character(openai_key, image_path, text)

    emit(f"Writing {char_name}'s script…")
    script = _write_script(openai_key, char_name, char_analysis, video_type, duration)

    emit(f"Generating {char_name}'s voice…")
    audio_id = _generate_audio(
        elevenlabs_key, script, char_name,
        voice_overrides or {}, audio_dir
    )
    audio_url = f"{app_base_url.rstrip('/')}/audio/{audio_id}"

    emit("Uploading character to HeyGen…")
    if not image_path:
        raise ValueError("HeyGen Talking Photo requires a character image.")
    photo_id = _heygen_upload_photo(heygen_key, image_path)

    emit("Generating lip-synced video… (this takes 1–3 minutes)")
    video_id = _heygen_generate(heygen_key, photo_id, audio_url, aspect_ratio)

    emit("Waiting for HeyGen to render…")
    video_url = _heygen_poll(heygen_key, video_id)

    emit("Downloading video…")
    fid = _download_file(video_url, video_dir, "mp4")

    return {
        "mode":         "talking",
        "char_name":    char_name,
        "char_analysis": char_analysis,
        "script":       script,
        "audio_id":     audio_id,
        "video_file":   fid,
        "video_type":   VIDEO_TYPES.get(video_type, video_type),
        "aspect_ratio": ASPECT_RATIOS.get(aspect_ratio, aspect_ratio),
    }


def generate_animation_video(openai_key: str,
                              fal_key: str,
                              video_type: str   = "social_reel",
                              aspect_ratio: str = "9:16",
                              duration: str     = "5",
                              image_path: str   = None,
                              text: str         = None,
                              video_dir: Path   = Path("/tmp/videos"),
                              progress_cb=None) -> dict:
    """
    fal.ai Kling pipeline: character image → animated motion video.
    """
    def emit(msg):
        if progress_cb: progress_cb(msg)

    emit("Analyzing character…")
    char_name, char_analysis = _analyze_character(openai_key, image_path, text)

    emit("Writing motion prompt…")
    prompt = _write_motion_prompt(
        openai_key, char_name, char_analysis, video_type, aspect_ratio, duration
    )

    emit("Generating animation… (30–90 seconds)")
    video_url = _fal_animate(fal_key, prompt, image_path, duration, aspect_ratio)

    emit("Downloading video…")
    fid = _download_file(video_url, video_dir, "mp4")

    return {
        "mode":         "animation",
        "char_name":    char_name,
        "char_analysis": char_analysis,
        "prompt":       prompt,
        "video_file":   fid,
        "video_type":   VIDEO_TYPES.get(video_type, video_type),
        "aspect_ratio": ASPECT_RATIOS.get(aspect_ratio, aspect_ratio),
    }


def generate_voice_clip(openai_key: str,
                         elevenlabs_key: str,
                         video_type: str = "social_reel",
                         duration: str   = "15",
                         image_path: str = None,
                         text: str       = None,
                         audio_dir: Path = Path("/tmp/audio"),
                         voice_overrides: dict = None,
                         progress_cb=None) -> dict:
    """
    ElevenLabs-only pipeline: character → voice audio file (mp3).
    """
    def emit(msg):
        if progress_cb: progress_cb(msg)

    emit("Analyzing character…")
    char_name, char_analysis = _analyze_character(openai_key, image_path, text)

    emit(f"Writing {char_name}'s script…")
    script = _write_script(openai_key, char_name, char_analysis, video_type, duration)

    emit(f"Generating voice with ElevenLabs…")
    audio_id = _generate_audio(
        elevenlabs_key, script, char_name,
        voice_overrides or {}, audio_dir
    )

    return {
        "mode":         "voice",
        "char_name":    char_name,
        "char_analysis": char_analysis,
        "script":       script,
        "audio_id":     audio_id,
    }
