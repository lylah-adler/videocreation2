"""
content_creator.py — generates short-form social content from Moodsters character assets
"""
import base64
from pathlib import Path
from openai import OpenAI

MODEL = "gpt-4o"

MOODSTERS = """
MOODSTERS CHARACTERS:
- Coz    = Happy         | Yellow  #FFD700 | Energetic, sunny, loves to dance and cheer
- Lolly  = Loving        | Pink    #FF69B4 | Warm, nurturing, loves hugs and kind words
- Tully  = Calm          | Green   #4CAF50 | Peaceful, slow-breathing, loves nature
- Razzy  = Angry         | Red     #E53935 | Hot-headed but learns to cool down
- Quigly = Scared/Afraid | Orange  #FF9800 | Nervous but brave, loves comfort
- Snorf  = Sad           | Blue    #1976D2 | Gentle, tearful, feels better with kindness

BRAND VOICE: Warm, playful, empowering. Speaks to parents, educators, and caregivers.
Mission: Help children understand and manage their emotions through loveable characters.
"""

SYSTEM = (
    "You are a social media content strategist and copywriter for Moodsters, "
    "a children's social-emotional learning brand.\n" + MOODSTERS
)

PLATFORM_SPECS = {
    "instagram": {
        "name": "Instagram",
        "caption_limit": "2,200 characters",
        "hashtag_count": "20–30 hashtags",
        "notes": "Engaging hook in first line. Line breaks for readability. Emojis throughout.",
    },
    "tiktok": {
        "name": "TikTok",
        "caption_limit": "2,200 characters",
        "hashtag_count": "5–10 hashtags",
        "notes": "Very casual, Gen Z-friendly tone for parents. Hook in first 3 words.",
    },
    "twitter": {
        "name": "Twitter / X",
        "caption_limit": "280 characters",
        "hashtag_count": "1–3 hashtags",
        "notes": "Short, punchy, shareable. One clear idea.",
    },
    "facebook": {
        "name": "Facebook",
        "caption_limit": "500 characters",
        "hashtag_count": "3–5 hashtags",
        "notes": "Conversational, community-focused. Ask a question to drive comments.",
    },
    "pinterest": {
        "name": "Pinterest",
        "caption_limit": "500 characters",
        "hashtag_count": "5–10 hashtags",
        "notes": "SEO-focused. Describe the pin's value. Keywords for parents/educators.",
    },
    "email": {
        "name": "Email Newsletter",
        "caption_limit": "150-word snippet",
        "hashtag_count": "no hashtags",
        "notes": "Subject line + preview text + body snippet. Warm, personal tone.",
    },
    "youtube": {
        "name": "YouTube Shorts",
        "caption_limit": "300 characters",
        "hashtag_count": "3–5 hashtags",
        "notes": "Describe what viewers will see/learn. CTA to subscribe.",
    },
}

CONTENT_PROMPTS = {
    "caption": """Write a social media POST CAPTION for {platform_name}.

CHARACTER ANALYSIS:
{character_info}

PLATFORM SPECS:
- Max length: {caption_limit}
- Hashtags: {hashtag_count}
- Style notes: {notes}

TONE: {tone}

OUTPUT exactly:
📝 CAPTION:
[caption text here]

#️⃣ HASHTAGS:
[hashtags here]

🔑 KEY MESSAGE: [one sentence — the emotional/educational takeaway for parents]""",

    "reel_script": """Write a SHORT-FORM VIDEO SCRIPT for {platform_name} featuring this Moodsters character.
Duration: {duration}

CHARACTER ANALYSIS:
{character_info}

TONE: {tone}

OUTPUT exactly:
🎬 HOOK (0–3 sec): [opening line spoken or shown on screen]

📋 SCRIPT:
[00:00] [action/visual description] — "[dialogue or text on screen]"
[00:03] [action/visual description] — "[dialogue or text on screen]"
... continue for full duration

🎵 SUGGESTED AUDIO: [music style or sound effect]
📌 CAPTION: [short caption for the post]
#️⃣ HASHTAGS: [hashtags]""",

    "story": """Write an INSTAGRAM/FACEBOOK STORY CONCEPT for {platform_name}.
(Multiple story slides, 5–7 slides)

CHARACTER ANALYSIS:
{character_info}

TONE: {tone}

OUTPUT exactly:
📖 STORY SERIES TITLE: [title]

For each slide:
Slide [N]:
  🖼️ VISUAL: [what the image/animation shows]
  📝 TEXT OVERLAY: "[text on screen]"
  🎯 STICKER/POLL (optional): [engagement element]
  ➡️ TRANSITION: [how it leads to next slide]

📌 FINAL CTA: [what to do after the last slide]""",

    "carousel": """Write CAROUSEL SLIDE COPY for {platform_name}.
(6–8 slides, educational/informative style)

CHARACTER ANALYSIS:
{character_info}

TONE: {tone}

OUTPUT exactly:
🎠 CAROUSEL TITLE: [series title]
📌 COVER SLIDE: [headline text — must stop the scroll]

For each slide:
Slide [N]: [Slide Title]
  Headline: [bold text, 5–8 words]
  Body: [1–3 short sentences]
  Visual note: [what image/graphic to use]

LAST SLIDE — CTA:
  Text: [call to action]
  Visual: [what to show]

📝 CAPTION: [overall post caption]
#️⃣ HASHTAGS: [hashtags]""",

    "email": """Write an EMAIL NEWSLETTER SNIPPET for the Moodsters brand.

CHARACTER ANALYSIS:
{character_info}

TONE: {tone}

OUTPUT exactly:
📧 SUBJECT LINE: [subject — creates curiosity or urgency]
👀 PREVIEW TEXT: [40–90 chars shown in inbox preview]

📝 EMAIL BODY:
[Opening line — warm, personal]

[2–3 paragraphs — educational, on-brand, references the character]

[CTA button text]: [text for the button]
[CTA URL hint]: [type of page to link to, e.g. "product page" or "free activity download"]

🔖 P.S. LINE: [optional — extra hook or offer]""",
}

ANALYSIS_PROMPT_IMAGE = """Analyze this Moodsters character image and provide a character profile.
{moodsters_guide}

OUTPUT:
CHARACTER NAME: [name if identifiable, or "Unknown Moodster"]
EMOTION: [emotion they represent]
COLOR: [hex color]
VISIBLE EXPRESSION: [describe their face/pose exactly]
VISIBLE PROPS/OBJECTS: [anything they're holding or near]
BACKGROUND/SETTING: [describe the scene]
ANY TEXT VISIBLE: [transcribe any text in the image]
CONTENT IDEAS: [3 specific content angles this image suggests]
"""

ANALYSIS_PROMPT_TEXT = """Analyze this Moodsters character description and provide a character profile.
{moodsters_guide}

DESCRIPTION: {text}

OUTPUT:
CHARACTER NAME: [name]
EMOTION: [emotion they represent]
COLOR: [hex color]
KEY TRAITS: [personality traits relevant for content]
CONTENT ANGLES: [3 specific content angles based on this description]
"""


def _encode_image(path: str):
    from PIL import Image
    import io as _io
    ext = Path(path).suffix.lower()
    img = Image.open(path).convert("RGB")
    if max(img.width, img.height) > 1024:
        img.thumbnail((1024, 1024))
    buf = _io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode(), "image/jpeg"


def _analyze_character(client: OpenAI,
                        image_b64: str = None, image_type: str = None,
                        text: str = None) -> str:
    """Step 1: extract character info from upload."""
    if image_b64:
        resp = client.chat.completions.create(
            model=MODEL, max_tokens=800, temperature=0.3,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text",
                     "text": ANALYSIS_PROMPT_IMAGE.format(moodsters_guide=MOODSTERS)},
                    {"type": "image_url",
                     "image_url": {"url": f"data:{image_type};base64,{image_b64}",
                                   "detail": "high"}},
                ],
            }],
        )
    else:
        resp = client.chat.completions.create(
            model=MODEL, max_tokens=600, temperature=0.3,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user",   "content":
                    ANALYSIS_PROMPT_TEXT.format(
                        moodsters_guide=MOODSTERS, text=text)},
            ],
        )
    return resp.choices[0].message.content.strip()


def generate_content(api_key: str,
                     platform: str,
                     content_type: str,
                     tone: str,
                     image_path: str = None,
                     text: str = None,
                     duration: str = "30 seconds") -> dict:
    """
    Generate short-form content for one platform + content type.
    Returns dict with character_info + generated content.
    """
    client = OpenAI(api_key=api_key)

    image_b64 = image_type = None
    if image_path:
        image_b64, image_type = _encode_image(image_path)

    # Step 1: understand the character
    char_info = _analyze_character(client, image_b64, image_type, text)

    # Step 2: generate the content
    spec = PLATFORM_SPECS.get(platform, PLATFORM_SPECS["instagram"])
    template = CONTENT_PROMPTS.get(content_type, CONTENT_PROMPTS["caption"])

    prompt = template.format(
        platform_name=spec["name"],
        character_info=char_info,
        caption_limit=spec["caption_limit"],
        hashtag_count=spec["hashtag_count"],
        notes=spec["notes"],
        tone=tone,
        duration=duration,
    )

    resp = client.chat.completions.create(
        model=MODEL, max_tokens=1500, temperature=0.8,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user",   "content": prompt},
        ],
    )
    content_text = resp.choices[0].message.content.strip()

    return {
        "character_info": char_info,
        "platform":       spec["name"],
        "content_type":   content_type,
        "content":        content_text,
    }
