"""
game_generator.py — generates a self-contained HTML5 game from the asset pipeline.

The game prompt includes the full asset profile so the generated game directly
mirrors what was in the uploaded image or PDF.
"""
from openai import OpenAI

MODEL = "gpt-4o"

GAME_SYSTEM = (
    "You are an expert HTML5/CSS/JavaScript developer specializing in "
    "children's educational touch-screen games for ages 3–6. "
    "You write complete, self-contained, bug-free vanilla HTML/CSS/JS. "
    "No external libraries. No CDN links."
)

GAME_PROMPT = """Generate a COMPLETE, SELF-CONTAINED HTML5 interactive game based exactly on the content below.

== ASSET PROFILE (what was actually uploaded) ==
{profile}

== GAME SCRIPT (scenes to implement) ==
{script}

== DIGITIZATION PLAN (how each screen works) ==
{plan}

== CHARACTER NOTES (animations & dialogue) ==
{chars}

═══════════════════════ TECHNICAL REQUIREMENTS ═══════════════════════

OUTPUT: One complete HTML file. All CSS and JS inline. No external dependencies.

ASSET FIDELITY — the game must:
- Feature ONLY the characters identified in the Asset Profile
- Include EXACTLY the activities described in the Game Script (not generic ones)
- Use the colors from the Asset Profile for UI, backgrounds, and characters
- Include character dialogue VERBATIM from the Character Notes
- Mirror the emotional arc from the Asset Profile (start state → resolution)

SCENE STRUCTURE:
- One full-screen <div class="scene"> per scene in the script
- Scenes shown one at a time via CSS opacity + pointer-events
- Progress dots at top (one per scene)
- Smooth 0.5s fade between scenes

CHARACTERS:
- Each Moodster = large circle (150px) in their exact hex color + their emoji
  Coz #FFD700 😄 | Lolly #FF69B4 🥰 | Tully #4CAF50 😌
  Razzy #E53935 😡 | Quigly #FF9800 😨 | Snorf #1976D2 😢
- CSS @keyframes bounce on idle (translateY -12px loop)
- CSS @keyframes pop on correct interaction (scale 1→1.4→1)
- Speech bubble appears above character with dialogue text

TOUCH MECHANICS (implement exactly as specified in digitization plan):
- TAP: large target (min 120px), ripple effect on touch, character reacts
- DRAG: full mouse+touch support (mousedown/touchstart, mousemove/touchmove, mouseup/touchend)
  Clone element follows finger; snap to drop zone within 80px; highlight target on hover
- SWIPE: detect swipe direction via touchstart/touchend deltaY; animate expand/contract
- SLIDER: draggable handle on a track; update character expression at 5 levels

FEEDBACK SYSTEM:
- Correct action → character does pop animation + says SUCCESS line + green glow
- No action for 5s → character does gentle wave + says NUDGE line
- "Next" button appears (styled, rounded) after correct action

AUDIO (Web Audio API, no files):
- Correct: short ascending beep (oscillator, 200ms)
- Celebration: 4-note fanfare
- All wrapped in try/catch — silent if blocked

CELEBRATION FINAL SCREEN:
- Background: rainbow gradient
- ALL characters from the asset bounce together
- 60 confetti particles (CSS animation, all 6 Moodster colors)
- Big "⭐ [WIN CONDITION from script] ⭐" text
- Replay button

VISUAL POLISH:
- 100vw × 100vh, overflow hidden, no scroll
- Background gradients match each scene's emotional tone (from asset profile colors)
- Rounded fonts via: font-family: 'Segoe UI', system-ui, sans-serif
- Min 18px text, min 80px touch targets
- Smooth CSS transitions everywhere

Output ONLY the HTML. Start with <!DOCTYPE html>. No explanation, no markdown fences.
"""


def generate_game(api_key: str, s1: str, s3: str, s4: str, s5: str) -> str:
    """
    Now takes s1 (asset profile) in addition to script/plan/chars
    so the game is tightly tied to what was actually uploaded.
    """
    client = OpenAI(api_key=api_key)

    prompt = GAME_PROMPT.format(
        profile=s1[:2000],
        script=s3[:2500],
        plan=s4[:2000],
        chars=s5[:1500],
    )

    resp = client.chat.completions.create(
        model=MODEL,
        max_tokens=4096,
        temperature=0.3,   # lower = more faithful to the spec
        messages=[
            {"role": "system", "content": GAME_SYSTEM},
            {"role": "user",   "content": prompt},
        ],
    )

    html = resp.choices[0].message.content.strip()
    if html.startswith("```"):
        html = "\n".join(html.split("\n")[1:])
    if html.endswith("```"):
        html = html[:-3].rstrip()

    return html
