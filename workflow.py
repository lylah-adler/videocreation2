"""
workflow.py — 5-step Moodsters asset analysis pipeline (OpenAI)

Key design: Step 1 produces a rich ASSET PROFILE (structured text).
Every subsequent step receives that profile and is explicitly instructed
to build FROM it — not generate generic content.
"""
import base64
from pathlib import Path
from openai import OpenAI
from PIL import Image
import io

# ── PDF extraction ────────────────────────────────────────────────────────────
try:
    from pypdf import PdfReader
    def extract_pdf_text(path: str) -> str:
        reader = PdfReader(path, strict=False)
        pages  = []
        for i, page in enumerate(reader.pages):
            try:
                t = page.extract_text() or ""
                if t.strip():
                    pages.append(f"[Page {i+1}]\n{t.strip()}")
            except Exception:
                pass
        text = "\n\n".join(pages).strip()
        if not text:
            raise ValueError(
                "No readable text found in PDF. "
                "Try uploading an image or paste the text manually."
            )
        return text
except ImportError:
    def extract_pdf_text(path: str) -> str:
        raise ImportError("pypdf not installed.")


# ── Image helpers ─────────────────────────────────────────────────────────────
def encode_image(path: str):
    """Return (base64, media_type). Resize to ≤1024px so GPT-4o gets a clean image."""
    ext = Path(path).suffix.lower()
    mt  = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
           ".png": "image/png",  ".gif": "image/gif",
           ".webp": "image/webp"}.get(ext, "image/png")

    img = Image.open(path).convert("RGB")
    # Resize if larger than 1024px on longest side (keeps aspect ratio)
    max_px = 1024
    if max(img.width, img.height) > max_px:
        img.thumbnail((max_px, max_px), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return b64, "image/jpeg"   # always JPEG after resize


# ── Moodsters knowledge ───────────────────────────────────────────────────────
MOODSTERS_GUIDE = """
MOODSTERS CHARACTER & EMOTION GUIDE:
- Coz      = Happy          | Color: Yellow  #FFD700 | Personality: Energetic, sunny, loves to dance and cheer
- Lolly    = Loving         | Color: Pink    #FF69B4 | Personality: Warm, nurturing, loves hugs and kind words
- Tully    = Calm           | Color: Green   #4CAF50 | Personality: Peaceful, slow-breathing, loves nature and quiet
- Razzy    = Angry          | Color: Red     #E53935 | Personality: Hot-headed but learns to cool down, stomp & shake
- Quigly   = Scared/Afraid  | Color: Orange  #FF9800 | Personality: Nervous but brave, wide-eyed, loves comfort
- Snorf    = Sad            | Color: Blue    #1976D2 | Personality: Gentle, tearful, feels better with hugs

TONE: Warm, encouraging, playful — like Bluey or Daniel Tiger.
Short sentences. Big feelings. Lots of celebration.
"""

SYSTEM = (
    "You are a children's digital game designer specializing in early childhood "
    "education (ages 3–6) and social-emotional learning, working exclusively with "
    "the Moodsters brand.\n" + MOODSTERS_GUIDE
)

MODEL = "gpt-4o"


# ── LLM helpers ───────────────────────────────────────────────────────────────
def _chat(client: OpenAI, user: str, max_tokens: int = 2500) -> str:
    resp = client.chat.completions.create(
        model=MODEL, max_tokens=max_tokens, temperature=0.7,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user",   "content": user},
        ],
    )
    return resp.choices[0].message.content.strip()


def _chat_vision(client: OpenAI, prompt: str,
                 b64: str, media_type: str, max_tokens: int = 2500) -> str:
    resp = client.chat.completions.create(
        model=MODEL, max_tokens=max_tokens, temperature=0.7,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url",
                 "image_url": {"url": f"data:{media_type};base64,{b64}", "detail": "high"}},
            ],
        }],
    )
    return resp.choices[0].message.content.strip()


# ── Step prompts ──────────────────────────────────────────────────────────────

STEP1_IMAGE = """You are analyzing a Moodsters product image to build a detailed asset profile.
Look at EVERYTHING visible in the image and answer each section precisely.

{guide}

## ASSET PROFILE — answer every section:

### 1. CHARACTERS VISIBLE
List every Moodster character you can see. For each one state:
- Name (match to the guide above by color/design)
- Emotion they represent
- Their hex color
- What expression/pose they are in RIGHT NOW in this image
- Any text or labels next to them

### 2. DOMINANT EMOTIONAL THEME
What is the PRIMARY emotion or emotional journey shown? Be specific — e.g. "moving from angry to calm" not just "anger".

### 3. ACTIVITIES & INTERACTIONS SHOWN
List every specific activity, exercise, or interaction visible:
- Coloring pages, breathing exercises, matching games, stickers, etc.
- Be very literal — describe exactly what you see on the page/product

### 4. COLORS & VISUAL STYLE
- Primary background color(s)
- Accent colors used
- Overall art style (cartoon, flat, watercolor, etc.)
- Any patterns or textures

### 5. TEXT & LABELS VISIBLE
Transcribe any readable text, titles, instructions, or labels you can see.

### 6. PROPS & OBJECTS
List specific objects, tools, or items shown (pillow, thermometer, heart, etc.)

### 7. SETTING / SCENE
Where does this take place? What is the background environment?

### 8. GAME ADAPTATION NOTES
Based on what you see, list 4–6 specific game interactions this asset suggests, e.g.:
- "Tap the thermometer to watch it rise" (from thermometer visual)
- "Drag the pillow to the sad character" (from pillow prop)"""

STEP1_TEXT = """You are analyzing a Moodsters product description/workbook to build a detailed asset profile.
Extract ONLY what is explicitly described — do not invent content.

{guide}

## ASSET PROFILE — answer every section:

### 1. CHARACTERS MENTIONED
For each Moodster character named or described:
- Name, emotion, color
- Their specific role in this asset
- Any dialogue or phrases attributed to them

### 2. DOMINANT EMOTIONAL THEME
What is the PRIMARY emotion or emotional journey? Be specific about the arc (e.g. "child recognizes anger → uses coping tool → feels calm").

### 3. ACTIVITIES & INTERACTIONS (most important — be very specific)
List EVERY activity, exercise, or interaction mentioned:
- The exact name/description of each activity
- What the child physically does
- What the Moodster character does during this activity
- Any specific instructions or steps

### 4. SPECIFIC OBJECTS & TOOLS MENTIONED
List every physical prop, tool, or object referenced (thermometer, pillow, water, stickers, crayons, etc.)

### 5. EXACT TEXT / PHRASES
Transcribe any specific phrases, instructions, or character dialogue mentioned.

### 6. VISUAL DESCRIPTIONS
Any colors, scenes, or visual elements described.

### 7. GAME ADAPTATION NOTES
Based on the content, list 4–6 specific game interactions this asset suggests, e.g.:
- "Drag the breathing cloud to Razzy's face" (from breathing exercise)
- "Tap the anger thermometer to cool it down" (from thermometer activity)

ASSET CONTENT:
{asset}"""

STEP2_PROMPT = """You are adapting a Moodsters asset for a touch-screen game for ages 3–6.

## ASSET PROFILE (from the uploaded asset — use THIS, not generic content):
{profile}

## YOUR TASK:
For EACH specific activity listed in the Asset Profile above, design a touch interaction.
Do NOT invent new activities — transform the EXACT ones found in the asset.

Output:

### 1. SIMPLIFIED EMOTIONAL CONCEPT
One 5-word sentence per emotion shown in the asset.

### 2. INTERACTION ADAPTATIONS
For EACH activity from the profile:
- Original activity name (from asset)
- Touch mechanic: tap / drag / swipe / press-and-hold (pick the best fit)
- Exact interaction: what does the child do with their finger?
- Time limit: must complete in under 30 seconds
- Success signal: what happens when done correctly?

### 3. VISUAL CUE REPLACEMENTS
Replace any text labels from the asset with emoji or color codes.
List each substitution using actual text/labels from the asset.

### 4. SENSORY HOOKS
2–3 specific sounds or animations tied to THIS asset's theme.
Reference specific props or characters from the profile.

### 5. PACING & SCENE ORDER
Suggest the order these activities should appear as game screens.
Base this on the natural flow of the original asset."""

STEP3_PROMPT = """Write a complete interactive game script for a Moodsters touch-screen game.

## ASSET PROFILE (what was actually uploaded):
{profile}

## INTERACTION PLAN (how those assets become touch interactions):
{interactions}

## RULES — this script must:
1. Use the EXACT characters identified in the asset profile (not random Moodsters)
2. Base EVERY scene on a SPECIFIC activity from the asset (not invented ones)
3. Use character dialogue that matches each character's personality AND references what they're doing in the asset
4. Mirror the emotional arc found in the asset (start → middle → resolution)

## OUTPUT FORMAT:

🎮 GAME TITLE: (3–5 words, includes the lead character's name from the asset)

📖 CONCEPT SUMMARY: (1 sentence describing exactly what the child does, referencing the asset's theme)

🎬 SCENES (one scene per activity identified in the asset profile):
For each scene write:
  Scene [N]: [Name]
  Based on: [which specific activity from the asset]
  Setting: [visual environment — reference colors/style from asset profile]
  Child action: [the exact touch interaction from the interaction plan]
  [CHARACTER NAME] says: "[dialogue in their voice, referencing this specific activity]"
  What happens: [result of the child's action]
  Transition: [how we move to next scene]

🏆 WIN CONDITION: (tied to completing all activities from the asset)

🎉 CELEBRATION: (which characters from the asset celebrate, what they do)"""

STEP4_PROMPT = """Create a screen-by-screen digitization plan for a Moodsters HTML5 game.

## ASSET PROFILE:
{profile}

## GAME SCRIPT (scenes to digitize):
{script}

For EACH scene, output a structured block using ONLY elements from the asset profile and script:

--- SCREEN [N]: [Scene Name] ---
📐 LAYOUT: (exact positions — where is the character, interactive element, background)
🎯 MECHANIC: (single touch mechanic: tap / drag-to-target / swipe-up-down / slider)
   HOW IT WORKS: (step by step — finger does X, Y happens, Z completes it)
🎭 CHARACTER: (which Moodster, their hex color, where on screen, animation state)
🗣️ DIALOGUE:
   INTRO: "[exact words from script]"
   SUCCESS: "[what they say when child succeeds]"
   NUDGE: "[what they say after 5s if child hasn't interacted]"
🌄 BACKGROUND: (colors, props, atmosphere — match asset profile colors)
✨ ANIMATIONS: (list every visual event triggered by the child's action)
🎨 UI ACCENT COLOR: (hex from asset profile matching this scene's character/emotion)"""

STEP5_PROMPT = """Write detailed character animation and voice notes for every screen.

## ASSET PROFILE:
{profile}

## DIGITIZATION PLAN:
{plan}

For EACH screen produce:

--- CHARACTER NOTES: Screen [N] ---
🌟 LEAD: [character name] — [why they lead THIS screen based on the asset]
🎬 ANIMATIONS:
  Idle:        [what the character does while waiting, specific to this scene]
  Correct:     [exact animation when child succeeds — reference the asset activity]
  Nudge:       [gentle prompt animation after 5s inactivity]
  Exit:        [how character leaves screen]
💬 INTRO PROMPT: "[≤10 words, enthusiastic, references the specific activity]"
🎁 REWARD LINE: "[≤12 words celebrating what the child just did]"
🔊 VOICE NOTE: [pace, tone, energy level for this specific scene]
🎨 COLOR ACCENT: [hex] — [character color from asset profile]
🔑 ASSET TIE-IN: [one sentence explaining how this screen directly reflects the uploaded asset]"""


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_workflow(api_key: str, asset_text: str = None,
                 image_b64: str = None, image_type: str = None,
                 progress_cb=None):

    client = OpenAI(api_key=api_key)

    def emit(n, label):
        if progress_cb:
            progress_cb(n, label)

    # ── Step 1: Rich asset profile ────────────────────────────────────────────
    if image_b64:
        s1 = _chat_vision(
            client,
            STEP1_IMAGE.format(guide=MOODSTERS_GUIDE),
            image_b64, image_type, max_tokens=2000
        )
    else:
        s1 = _chat(
            client,
            STEP1_TEXT.format(guide=MOODSTERS_GUIDE, asset=asset_text),
            max_tokens=2000
        )
    emit(1, "Asset Analysis")

    # ── Step 2: Touch interactions tied to the asset ──────────────────────────
    s2 = _chat(client, STEP2_PROMPT.format(profile=s1), max_tokens=2000)
    emit(2, "Simplified for Young Children")

    # ── Step 3: Script built from the asset ──────────────────────────────────
    s3 = _chat(
        client,
        STEP3_PROMPT.format(profile=s1, interactions=s2),
        max_tokens=3000
    )
    emit(3, "Game Script")

    # ── Step 4: Digitization plan ─────────────────────────────────────────────
    s4 = _chat(
        client,
        STEP4_PROMPT.format(profile=s1, script=s3),
        max_tokens=3000
    )
    emit(4, "Digitization Plan")

    # ── Step 5: Character notes ───────────────────────────────────────────────
    s5 = _chat(
        client,
        STEP5_PROMPT.format(profile=s1, plan=s4),
        max_tokens=3000
    )
    emit(5, "Character Integration")

    return dict(s1=s1, s2=s2, s3=s3, s4=s4, s5=s5)
