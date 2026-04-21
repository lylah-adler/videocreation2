# 🎮 Moodsters Game Builder

Upload a Moodsters product asset (PDF workbook, product image, or text description)
and get back a **complete, playable HTML5 interactive game** in minutes.

## What It Does

1. **Analyzes** your asset — extracts emotion, characters, and mechanics  
2. **Adapts** the content for ages 3–6 (tap, drag, swipe interactions)  
3. **Writes** a full game script with character dialogue  
4. **Designs** each screen layout and interaction mechanic  
5. **Integrates** Moodster character animations and voice direction  
6. **Generates** a playable HTML5 game — preview it live, then download  

## Quick Start (Local)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the app
python app.py

# 3. Open http://localhost:5000
# 4. Enter your OpenAI API key, upload an asset, click Generate!
```

## Deploy to Railway (Recommended — Free Tier)

1. Push this repo to GitHub
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Select your repo — Railway auto-detects the config
4. Set environment variable (optional): `SECRET_KEY=your-secret`
5. Your app is live in ~2 minutes ✅

## Deploy to Render

1. Push to GitHub
2. Go to [render.com](https://render.com) → New Web Service
3. Connect repo, set:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `gunicorn app:app --workers 4 --bind 0.0.0.0:$PORT --timeout 300`
4. Deploy ✅

## Deploy with Docker

```bash
docker build -t moodsters-game-builder .
docker run -p 8080:8080 moodsters-game-builder
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `PORT`   | Server port (default 5000) | No |

> **Note:** Your OpenAI API key is entered in the UI per-session and never stored on the server.

## Supported Asset Formats

- 📄 PDF workbooks (text extracted automatically)
- 🖼️ JPG / PNG / GIF / WEBP product images (analyzed via GPT-4o Vision)
- ✏️ Text descriptions (paste directly into the text field)

## Moodsters Characters

| Character | Emotion | Color |
|-----------|---------|-------|
| 😄 Coz    | Happy   | #FFD700 Yellow |
| 🥰 Lolly  | Loving  | #FF69B4 Pink   |
| 😌 Tully  | Calm    | #4CAF50 Green  |
| 😡 Razzy  | Angry   | #E53935 Red    |
| 😨 Quigly | Scared  | #FF9800 Orange |
| 😢 Snorf  | Sad     | #1976D2 Blue   |

## Tech Stack

- **Backend:** Python / Flask
- **AI:** OpenAI GPT-4o (vision + text)
- **Frontend:** Vanilla HTML/CSS/JS (no framework)
- **Game Output:** Self-contained HTML5 (no dependencies)
- **PDF Parsing:** PyMuPDF
