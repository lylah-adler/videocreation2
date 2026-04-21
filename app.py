"""
app.py — Moodsters Game Builder Flask Backend
HTML is embedded as a string — no templates/ directory needed.
"""
import os
import uuid
import threading
from pathlib import Path

from flask import Flask, request, jsonify, render_template_string, send_file
from werkzeug.utils import secure_filename

from workflow import run_workflow, extract_pdf_text, encode_image
from game_generator import generate_game
from content_creator import generate_content
from video_creator import (generate_talking_video, generate_animation_video, generate_voice_clip)

# ── HTML template embedded inline — survives any deploy structure ─────────────
INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>🎮 Moodsters Game Builder</title>
<style>
  /* ── Reset & Base ─────────────────────────────────────────── */
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --brand:   #5C35BF;
    --brand-l: #7B52E8;
    --coz:     #FFD700;
    --lolly:   #FF69B4;
    --tully:   #4CAF50;
    --razzy:   #E53935;
    --quigly:  #FF9800;
    --snorf:   #1976D2;
    --bg:      #F8F5FF;
    --card:    #FFFFFF;
    --text:    #2D2347;
    --muted:   #7A6E8A;
    --radius:  16px;
    --shadow:  0 4px 24px rgba(92,53,191,.12);
  }

  body {
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
  }

  /* ── Header ─────────────────────────────────────────────────── */
  header {
    background: linear-gradient(135deg, var(--brand) 0%, #9B59B6 100%);
    color: #fff;
    padding: 28px 40px;
    display: flex;
    align-items: center;
    gap: 16px;
    box-shadow: 0 2px 20px rgba(92,53,191,.3);
  }
  header h1 { font-size: 1.75rem; font-weight: 800; }
  header p  { font-size: .9rem; opacity: .85; margin-top: 2px; }
  .logo { font-size: 2.4rem; }
  .char-strip {
    margin-left: auto;
    display: flex;
    gap: 8px;
  }
  .char-badge {
    width: 36px; height: 36px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.2rem;
    border: 2px solid rgba(255,255,255,.4);
  }

  /* ── Layout ─────────────────────────────────────────────────── */
  .main {
    display: grid;
    grid-template-columns: 420px 1fr;
    gap: 24px;
    padding: 32px 40px;
    max-width: 1400px;
    margin: 0 auto;
  }
  @media (max-width: 900px) {
    .main { grid-template-columns: 1fr; padding: 20px; }
  }

  /* ── Cards ──────────────────────────────────────────────────── */
  .card {
    background: var(--card);
    border-radius: var(--radius);
    padding: 28px;
    box-shadow: var(--shadow);
  }
  .card-title {
    font-size: 1rem;
    font-weight: 700;
    color: var(--brand);
    margin-bottom: 18px;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  /* ── Form ───────────────────────────────────────────────────── */
  label { font-size: .82rem; font-weight: 600; color: var(--muted); display: block; margin-bottom: 6px; }

  input[type="password"], textarea {
    width: 100%;
    padding: 12px 14px;
    border: 1.5px solid #E0D9F5;
    border-radius: 10px;
    font-size: .92rem;
    color: var(--text);
    background: #FAF8FF;
    outline: none;
    transition: border-color .2s;
  }
  input[type="password"]:focus, textarea:focus {
    border-color: var(--brand);
  }
  textarea { resize: vertical; min-height: 100px; }

  .divider {
    text-align: center;
    color: var(--muted);
    font-size: .82rem;
    font-weight: 600;
    margin: 16px 0;
    position: relative;
  }
  .divider::before, .divider::after {
    content: '';
    position: absolute;
    top: 50%;
    width: 40%;
    height: 1px;
    background: #E0D9F5;
  }
  .divider::before { left: 0; }
  .divider::after  { right: 0; }

  /* ── Full-page drag overlay ──────────────────────────── */
  #page-drop-overlay {
    position: fixed; inset: 0;
    background: rgba(92,53,191,.18);
    backdrop-filter: blur(4px);
    z-index: 9999; display: none;
    align-items: center; justify-content: center; flex-direction: column;
    gap: 16px; border: 5px dashed var(--brand-l);
    box-sizing: border-box; pointer-events: none;
  }
  #page-drop-overlay.visible { display: flex; }
  #page-drop-overlay .ov-icon  { font-size: 5rem; animation: float .9s ease-in-out infinite alternate; }
  #page-drop-overlay .ov-label { font-size: 1.5rem; font-weight: 800; color: #fff; text-shadow: 0 2px 14px rgba(0,0,0,.35); }
  #page-drop-overlay .ov-sub   { font-size: .92rem; color: rgba(255,255,255,.8); }
  @keyframes float { 0% { transform: translateY(0) scale(1); } 100% { transform: translateY(-12px) scale(1.1); } }

  /* ── Drop Zone ──────────────────────────────────────────── */
  .drop-zone {
    border: 2.5px dashed #C4B8EC; border-radius: 14px;
    cursor: pointer; text-align: center;
    transition: border-color .2s, background .2s, transform .15s, box-shadow .2s;
    background: #FAF8FF; position: relative; overflow: hidden;
  }
  .drop-zone:hover {
    border-color: var(--brand); background: #F0EBFF;
    transform: translateY(-1px); box-shadow: 0 6px 20px rgba(92,53,191,.15);
  }
  .drop-zone.dragover {
    border-color: var(--brand-l); background: #EDE7FF;
    transform: scale(1.02); box-shadow: 0 0 0 4px rgba(92,53,191,.18), 0 8px 24px rgba(92,53,191,.18);
  }
  .drop-zone.has-file { border-color: var(--tully); border-style: solid; background: #F0FFF4; }
  .drop-zone input[type="file"] { position: absolute; inset: 0; opacity: 0; cursor: pointer; width: 100%; height: 100%; }

  /* idle inner */
  .dz-idle { padding: 28px 20px; pointer-events: none; }
  .dz-idle .dz-icon { font-size: 2.4rem; margin-bottom: 10px; display: block; transition: transform .3s; }
  .drop-zone:hover    .dz-icon  { transform: translateY(-4px) scale(1.1); }
  .drop-zone.dragover .dz-icon  { transform: scale(1.3) rotate(-8deg); }
  .dz-idle .dz-label { font-size: .88rem; color: var(--muted); line-height: 1.6; }
  .dz-idle .dz-label strong { color: var(--brand); }
  .dz-formats { display: flex; gap: 6px; justify-content: center; flex-wrap: wrap; margin-top: 10px; }
  .dz-fmt { background: #EDE7FF; color: var(--brand); border-radius: 20px; padding: 2px 10px; font-size: .72rem; font-weight: 700; }

  /* drag-over hint */
  .dz-drag-hint {
    position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
    font-size: 1rem; font-weight: 700; color: var(--brand);
    opacity: 0; transition: opacity .2s; pointer-events: none;
    background: rgba(92,53,191,.06); border-radius: 12px;
  }
  .drop-zone.dragover .dz-drag-hint { opacity: 1; }

  /* file-loaded state */
  .dz-loaded { display: none; padding: 14px 16px; align-items: center; gap: 12px; text-align: left; pointer-events: none; }
  .drop-zone.has-file .dz-idle   { display: none; }
  .drop-zone.has-file .dz-loaded { display: flex; }
  .dz-file-icon { width: 46px; height: 46px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 1.6rem; flex-shrink: 0; background: #E8F5E9; }
  .dz-file-info { flex: 1; min-width: 0; }
  .dz-file-name { font-size: .88rem; font-weight: 700; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .dz-file-meta { font-size: .75rem; color: var(--muted); margin-top: 2px; }
  .dz-remove {
    width: 28px; height: 28px; border-radius: 50%;
    background: #FFE0E0; border: none; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    font-size: .85rem; color: var(--razzy); flex-shrink: 0;
    transition: background .2s, transform .15s; pointer-events: all; z-index: 2;
  }
  .dz-remove:hover { background: var(--razzy); color: #fff; transform: scale(1.1); }

  /* replace hint */
  .dz-replace-hint {
    position: absolute; inset: 0; background: rgba(76,175,80,.1);
    display: flex; align-items: center; justify-content: center;
    font-size: .82rem; font-weight: 700; color: #2E7D32;
    opacity: 0; transition: opacity .2s; pointer-events: none; border-radius: 12px;
  }
  .drop-zone.has-file:hover .dz-replace-hint { opacity: 1; }

  /* ── Button ─────────────────────────────────────────────────── */
  .btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    width: 100%;
    padding: 15px;
    border-radius: 12px;
    border: none;
    font-size: 1rem;
    font-weight: 700;
    cursor: pointer;
    transition: all .2s;
    margin-top: 20px;
  }
  .btn-primary {
    background: linear-gradient(135deg, var(--brand), var(--brand-l));
    color: #fff;
    box-shadow: 0 4px 16px rgba(92,53,191,.35);
  }
  .btn-primary:hover { transform: translateY(-1px); box-shadow: 0 6px 20px rgba(92,53,191,.4); }
  .btn-primary:disabled { opacity: .55; cursor: not-allowed; transform: none; }

  .btn-green {
    background: linear-gradient(135deg, #2E7D32, var(--tully));
    color: #fff;
    margin-top: 12px;
    box-shadow: 0 4px 16px rgba(76,175,80,.3);
  }
  .btn-green:hover { transform: translateY(-1px); }

  /* ── Progress ───────────────────────────────────────────────── */
  #progress-section { display: none; margin-top: 24px; }

  .progress-track {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .step-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
    border-radius: 10px;
    background: #FAF8FF;
    border: 1.5px solid #E8E2F8;
    transition: all .3s;
  }
  .step-row.active  { border-color: var(--brand); background: #F0EBFF; }
  .step-row.done    { border-color: var(--tully);  background: #F0FFF2; }
  .step-row.error   { border-color: var(--razzy);  background: #FFF2F2; }

  .step-dot {
    width: 28px; height: 28px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: .85rem;
    font-weight: 700;
    flex-shrink: 0;
    background: #E0D9F5;
    color: var(--brand);
    transition: all .3s;
  }
  .step-row.active .step-dot { background: var(--brand); color: #fff; }
  .step-row.done   .step-dot { background: var(--tully);  color: #fff; }

  .step-label { font-size: .88rem; font-weight: 600; color: var(--text); }
  .step-sub   { font-size: .76rem; color: var(--muted); }

  .spinner {
    width: 16px; height: 16px;
    border: 2px solid var(--brand);
    border-top-color: transparent;
    border-radius: 50%;
    animation: spin .7s linear infinite;
    margin-left: auto;
    flex-shrink: 0;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* ── Right panel ─────────────────────────────────────────────── */
  .right-panel { display: flex; flex-direction: column; gap: 24px; }

  /* ── Script Output ───────────────────────────────────────────── */
  #output-section { display: none; }

  .tabs {
    display: flex;
    gap: 4px;
    margin-bottom: 16px;
    background: #F0EBFF;
    border-radius: 10px;
    padding: 4px;
  }
  .tab-btn {
    flex: 1;
    padding: 8px 4px;
    border: none;
    border-radius: 8px;
    font-size: .78rem;
    font-weight: 600;
    cursor: pointer;
    background: transparent;
    color: var(--muted);
    transition: all .2s;
  }
  .tab-btn.active { background: var(--brand); color: #fff; }

  .tab-pane { display: none; }
  .tab-pane.active { display: block; }

  .step-output {
    background: #FAF8FF;
    border: 1.5px solid #E0D9F5;
    border-radius: 10px;
    padding: 16px;
    font-size: .84rem;
    line-height: 1.65;
    white-space: pre-wrap;
    max-height: 340px;
    overflow-y: auto;
    color: var(--text);
  }

  /* ── Game Preview ─────────────────────────────────────────────── */
  #game-section { display: none; }

  .game-preview-wrap {
    background: #1A1A2E;
    border-radius: var(--radius);
    overflow: hidden;
    position: relative;
    box-shadow: var(--shadow);
  }
  .game-preview-wrap iframe {
    width: 100%;
    height: 560px;
    border: none;
    display: block;
  }
  .game-toolbar {
    display: flex;
    gap: 10px;
    align-items: center;
    padding: 12px 16px;
    background: #0F0F1F;
  }
  .game-toolbar span {
    color: #aaa;
    font-size: .82rem;
    flex: 1;
  }
  .btn-small {
    padding: 8px 16px;
    border-radius: 8px;
    border: none;
    font-size: .82rem;
    font-weight: 700;
    cursor: pointer;
    transition: all .2s;
  }
  .btn-open    { background: var(--brand); color: #fff; }
  .btn-dl      { background: #222; color: #ddd; border: 1px solid #444; }
  .btn-open:hover { background: var(--brand-l); }
  .btn-dl:hover   { background: #333; }

  /* ── Character Legend ───────────────────────────────────────── */
  .char-legend {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
    margin-top: 16px;
  }
  .char-pill {
    display: flex;
    align-items: center;
    gap: 7px;
    padding: 7px 10px;
    border-radius: 30px;
    font-size: .78rem;
    font-weight: 600;
    color: #fff;
  }
  .char-pill span { opacity: .92; }

  /* ── Toast ────────────────────────────────────────────────────── */
  #toast {
    position: fixed;
    bottom: 28px;
    right: 28px;
    background: var(--razzy);
    color: #fff;
    padding: 12px 20px;
    border-radius: 10px;
    font-size: .88rem;
    font-weight: 600;
    display: none;
    z-index: 999;
    box-shadow: 0 4px 20px rgba(0,0,0,.2);
  }
</style>
</head>
<body>

<!-- Header -->
<header>
  <div class="logo">🎮</div>
  <div>
    <h1>Moodsters Game Builder</h1>
    <p>Upload a product asset → Get a playable interactive game</p>
  </div>
  <div class="char-strip">
    <div class="char-badge" style="background:#FFD700">😄</div>
    <div class="char-badge" style="background:#FF69B4">🥰</div>
    <div class="char-badge" style="background:#4CAF50">😌</div>
    <div class="char-badge" style="background:#E53935">😡</div>
    <div class="char-badge" style="background:#FF9800">😨</div>
    <div class="char-badge" style="background:#1976D2">😢</div>
  </div>
</header>

<!-- Main Grid -->
<div class="main">

  <!-- LEFT: Input Panel -->
  <div style="display:flex;flex-direction:column;gap:20px;">

    <!-- API Key -->
    <div class="card">
      <div class="card-title">🔑 OpenAI API Key</div>
      <label for="api-key">Your key is used only for this session</label>
      <input type="password" id="api-key" placeholder="sk-..." autocomplete="off"/>
      <p style="font-size:.75rem;color:var(--muted);margin-top:8px;">
        Needs GPT-4o access. Key is never stored.
      </p>
    </div>

    <!-- Upload / Text -->
    <div class="card">
      <div class="card-title">📤 Moodsters Asset</div>

      <!-- Text input -->
      <label for="text-input">Describe the asset (or paste workbook text)</label>
      <textarea id="text-input" placeholder="e.g. Moodsters workbook about Razzy the angry Moodster. Includes breathing exercises, coloring pages, and a calm-down dance..."></textarea>

      <div class="divider">or upload a file</div>

      <!-- File drop zone -->
      <div class="drop-zone" id="drop-zone">
        <input type="file" id="file-input" accept=".pdf,.jpg,.jpeg,.png,.gif,.webp"/>

        <!-- Idle state -->
        <div class="dz-idle">
          <span class="dz-icon">📂</span>
          <div class="dz-label">
            <strong>Click to upload</strong> or drag &amp; drop anywhere on the page
          </div>
          <div class="dz-formats">
            <span class="dz-fmt">PDF</span>
            <span class="dz-fmt">JPG</span>
            <span class="dz-fmt">PNG</span>
            <span class="dz-fmt">GIF</span>
            <span class="dz-fmt">WEBP</span>
            <span class="dz-fmt">max 50 MB</span>
          </div>
        </div>

        <!-- File-loaded state -->
        <div class="dz-loaded" id="dz-loaded">
          <div class="dz-file-icon" id="dz-file-icon">📄</div>
          <div class="dz-file-info">
            <div class="dz-file-name" id="dz-file-name">—</div>
            <div class="dz-file-meta" id="dz-file-meta">—</div>
          </div>
          <button class="dz-remove" id="dz-remove" title="Remove file">✕</button>
        </div>

        <!-- Hints (CSS-driven) -->
        <div class="dz-drag-hint">Drop it here! 🎯</div>
        <div class="dz-replace-hint">🔄 Drop or click to replace</div>
      </div>

      <button class="btn btn-primary" id="generate-btn" onclick="startGeneration()">
        <span>✨</span> Generate Game
      </button>
    </div>

    <!-- Progress -->
    <div class="card" id="progress-section">
      <div class="card-title">⚙️ Building your game…</div>
      <div class="progress-track">
        <div class="step-row" id="step-row-1">
          <div class="step-dot" id="dot-1">1</div>
          <div>
            <div class="step-label">Asset Analysis</div>
            <div class="step-sub">Extracting emotion, characters & mechanics</div>
          </div>
        </div>
        <div class="step-row" id="step-row-2">
          <div class="step-dot" id="dot-2">2</div>
          <div>
            <div class="step-label">Simplify for Ages 3–6</div>
            <div class="step-sub">Adapting to tap, drag & swipe interactions</div>
          </div>
        </div>
        <div class="step-row" id="step-row-3">
          <div class="step-dot" id="dot-3">3</div>
          <div>
            <div class="step-label">Game Script</div>
            <div class="step-sub">Writing scenes, dialogue & celebration</div>
          </div>
        </div>
        <div class="step-row" id="step-row-4">
          <div class="step-dot" id="dot-4">4</div>
          <div>
            <div class="step-label">Digitization Plan</div>
            <div class="step-sub">Designing each screen layout & mechanic</div>
          </div>
        </div>
        <div class="step-row" id="step-row-5">
          <div class="step-dot" id="dot-5">5</div>
          <div>
            <div class="step-label">Character Integration</div>
            <div class="step-sub">Animations, prompts & reward responses</div>
          </div>
        </div>
        <div class="step-row" id="step-row-6">
          <div class="step-dot" id="dot-6">🎮</div>
          <div>
            <div class="step-label">Game Code Generation</div>
            <div class="step-sub">Building the playable HTML5 game</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Character Legend -->
    <div class="card">
      <div class="card-title">🌈 Character Guide</div>
      <div class="char-legend">
        <div class="char-pill" style="background:#FFD700;color:#333">😄 <span>Coz — Happy</span></div>
        <div class="char-pill" style="background:#FF69B4">🥰 <span>Lolly — Loving</span></div>
        <div class="char-pill" style="background:#4CAF50">😌 <span>Tully — Calm</span></div>
        <div class="char-pill" style="background:#E53935">😡 <span>Razzy — Angry</span></div>
        <div class="char-pill" style="background:#FF9800">😨 <span>Quigly — Scared</span></div>
        <div class="char-pill" style="background:#1976D2">😢 <span>Snorf — Sad</span></div>
      </div>
    </div>

  </div><!-- /left -->

  <!-- RIGHT: Output Panel -->
  <div class="right-panel">

    <!-- Placeholder when nothing generated yet -->
    <div class="card" id="placeholder-card" style="display:flex;align-items:center;justify-content:center;min-height:400px;flex-direction:column;gap:16px;text-align:center;">
      <div style="font-size:4rem;">🎮</div>
      <div style="font-weight:700;font-size:1.1rem;color:var(--brand)">Your game will appear here</div>
      <div style="color:var(--muted);font-size:.88rem;max-width:300px">
        Upload a Moodsters PDF, image, or describe an asset — then click Generate Game
      </div>
    </div>

    <!-- Script Tabs -->
    <div class="card" id="output-section">
      <div class="card-title">📄 Generated Game Script</div>
      <div class="tabs">
        <button class="tab-btn active" onclick="showTab('t1',this)">Analysis</button>
        <button class="tab-btn" onclick="showTab('t2',this)">Simplified</button>
        <button class="tab-btn" onclick="showTab('t3',this)">Script</button>
        <button class="tab-btn" onclick="showTab('t4',this)">Screens</button>
        <button class="tab-btn" onclick="showTab('t5',this)">Characters</button>
      </div>
      <div id="t1" class="tab-pane active"><div class="step-output" id="out-s1"></div></div>
      <div id="t2" class="tab-pane"><div class="step-output" id="out-s2"></div></div>
      <div id="t3" class="tab-pane"><div class="step-output" id="out-s3"></div></div>
      <div id="t4" class="tab-pane"><div class="step-output" id="out-s4"></div></div>
      <div id="t5" class="tab-pane"><div class="step-output" id="out-s5"></div></div>
    </div>

    <!-- Game Preview -->
    <div class="card" id="game-section">
      <div class="card-title">🕹️ Live Game Preview</div>
      <div class="game-preview-wrap">
        <div class="game-toolbar">
          <span id="game-label">🎮 Moodsters Interactive Game</span>
          <button class="btn-small btn-open" id="open-btn">↗ Full Screen</button>
          <button class="btn-small btn-dl"   id="dl-btn">⬇ Download</button>
        </div>
        <iframe id="game-frame" title="Moodsters Game Preview" sandbox="allow-scripts allow-same-origin"></iframe>
      </div>
    </div>

  </div><!-- /right -->

</div><!-- /main -->

<!-- Full-page drop overlay -->
<div id="page-drop-overlay">
  <div class="ov-icon">📂</div>
  <div class="ov-label">Drop your file anywhere!</div>
  <div class="ov-sub">PDF · JPG · PNG · GIF · WEBP</div>
</div>

<div id="toast"></div>

<script>
  let currentJobId = null;
  let pollTimer    = null;

  /* ── File drop ─────────────────────────────────────────────── */
  const dropZone  = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');

  const FILE_ICONS = { pdf:'📄', jpg:'🖼️', jpeg:'🖼️', png:'🖼️', gif:'🎞️', webp:'🖼️' };
  const ALLOWED    = new Set(['pdf','jpg','jpeg','png','gif','webp']);

  function fmtBytes(b) {
    if (b < 1024)         return b + ' B';
    if (b < 1024 * 1024)  return (b / 1024).toFixed(1) + ' KB';
    return (b / (1024 * 1024)).toFixed(1) + ' MB';
  }

  function showFile(file) {
    const ext = file.name.split('.').pop().toLowerCase();
    if (!ALLOWED.has(ext)) { toast('Unsupported type. Use PDF, JPG, or PNG.'); clearFile(); return; }
    document.getElementById('dz-file-icon').textContent = FILE_ICONS[ext] || '📄';
    document.getElementById('dz-file-name').textContent = file.name;
    document.getElementById('dz-file-meta').textContent = fmtBytes(file.size) + '  ·  ' + ext.toUpperCase();
    dropZone.classList.add('has-file');
    document.getElementById('text-input').value = '';
  }

  function clearFile() {
    fileInput.value = '';
    dropZone.classList.remove('has-file');
  }

  document.getElementById('dz-remove').addEventListener('click', e => {
    e.stopPropagation(); e.preventDefault(); clearFile();
  });

  dropZone.addEventListener('dragover',  e => { e.preventDefault(); dropZone.classList.add('dragover'); });
  dropZone.addEventListener('dragleave', e => {
    if (!dropZone.contains(e.relatedTarget)) dropZone.classList.remove('dragover');
  });
  dropZone.addEventListener('drop', e => {
    e.preventDefault(); dropZone.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (file) { setFileInput(file); showFile(file); }
  });
  fileInput.addEventListener('change', () => {
    if (fileInput.files[0]) showFile(fileInput.files[0]);
  });

  /* Full-page drag overlay */
  const overlay = document.getElementById('page-drop-overlay');
  let dragCounter = 0;

  document.addEventListener('dragenter', e => {
    if (!e.dataTransfer.types.includes('Files')) return;
    dragCounter++;
    overlay.classList.add('visible');
  });
  document.addEventListener('dragleave', () => {
    dragCounter = Math.max(0, dragCounter - 1);
    if (dragCounter === 0) overlay.classList.remove('visible');
  });
  document.addEventListener('dragover',  e => e.preventDefault());
  document.addEventListener('drop', e => {
    e.preventDefault(); dragCounter = 0; overlay.classList.remove('visible');
    const file = e.dataTransfer.files[0];
    if (file && !dropZone.contains(e.target)) { setFileInput(file); showFile(file); }
  });

  function setFileInput(file) {
    try { const dt = new DataTransfer(); dt.items.add(file); fileInput.files = dt.files; }
    catch(err) { /* Safari fallback */ }
  }

  /* ── Tabs ──────────────────────────────────────────────────── */
  function showTab(id, btn) {
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(id).classList.add('active');
    btn.classList.add('active');
  }

  /* ── Toast ─────────────────────────────────────────────────── */
  function toast(msg, color='#E53935') {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.style.background = color;
    t.style.display = 'block';
    setTimeout(() => t.style.display = 'none', 4000);
  }

  /* ── Step states ────────────────────────────────────────────── */
  function setStep(n, state) {
    // state: 'pending' | 'active' | 'done' | 'error'
    const row = document.getElementById('step-row-' + n);
    const dot = document.getElementById('dot-' + n);
    if (!row) return;
    row.classList.remove('active','done','error');
    // Remove spinner if present
    const existing = row.querySelector('.spinner');
    if (existing) existing.remove();
    if (state === 'active') {
      row.classList.add('active');
      const sp = document.createElement('div');
      sp.className = 'spinner';
      row.appendChild(sp);
    } else if (state === 'done') {
      row.classList.add('done');
      dot.textContent = '✓';
    } else if (state === 'error') {
      row.classList.add('error');
      dot.textContent = '✕';
    }
  }

  /* ── Start generation ────────────────────────────────────────── */
  async function startGeneration() {
    const apiKey = document.getElementById('api-key').value.trim();
    if (!apiKey) { toast('Please enter your OpenAI API key first.'); return; }

    const textInput = document.getElementById('text-input').value.trim();
    const file      = fileInput.files[0];

    if (!textInput && !file) {
      toast('Please upload a file or describe the asset first.');
      return;
    }

    // Reset UI
    document.getElementById('generate-btn').disabled = true;
    document.getElementById('placeholder-card').style.display = 'none';
    document.getElementById('output-section').style.display = 'none';
    document.getElementById('game-section').style.display = 'none';
    document.getElementById('progress-section').style.display = 'block';
    for (let i=1;i<=6;i++) setStep(i,'pending');

    // Build form data
    const fd = new FormData();
    fd.append('api_key', apiKey);
    if (file)      fd.append('file', file);
    else           fd.append('text_input', textInput);

    try {
      const res  = await fetch('/generate', { method: 'POST', body: fd });
      const data = await res.json();
      if (data.error) { toast(data.error); resetBtn(); return; }
      currentJobId = data.job_id;
      pollStatus();
    } catch(e) {
      toast('Network error: ' + e.message);
      resetBtn();
    }
  }

  function resetBtn() {
    document.getElementById('generate-btn').disabled = false;
  }

  /* ── Poll status ─────────────────────────────────────────────── */
  function pollStatus() {
    if (pollTimer) clearTimeout(pollTimer);
    fetch('/status/' + currentJobId)
      .then(r => r.json())
      .then(data => {
        const step = data.step || 0;

        // Update step indicators
        for (let i=1; i<=6; i++) {
          if (i < step)      setStep(i, 'done');
          else if (i===step) setStep(i, 'active');
        }

        if (data.status === 'done') {
          // All done!
          for (let i=1;i<=6;i++) setStep(i,'done');
          showResult(data);
          resetBtn();

        } else if (data.status === 'error') {
          toast('Error: ' + data.error);
          for (let i=1;i<=6;i++) {
            if (i <= step) setStep(i,'done');
            if (i === step+1) setStep(i,'error');
          }
          resetBtn();

        } else {
          // Still running — poll again
          pollTimer = setTimeout(pollStatus, 2500);
        }
      })
      .catch(() => { pollTimer = setTimeout(pollStatus, 3000); });
  }

  /* ── Show result ─────────────────────────────────────────────── */
  function showResult(data) {
    const r = data.result;
    document.getElementById('out-s1').textContent = r.s1 || '';
    document.getElementById('out-s2').textContent = r.s2 || '';
    document.getElementById('out-s3').textContent = r.s3 || '';
    document.getElementById('out-s4').textContent = r.s4 || '';
    document.getElementById('out-s5').textContent = r.s5 || '';

    document.getElementById('output-section').style.display = 'block';

    const gid = data.game_id;
    if (gid) {
      const previewUrl = '/preview/' + gid;
      document.getElementById('game-frame').src = previewUrl;
      document.getElementById('open-btn').onclick = () => window.open(previewUrl, '_blank');
      document.getElementById('dl-btn').onclick   = () => window.open('/download/' + gid, '_blank');

      // Extract title from s3
      const titleMatch = (r.s3 || '').match(/GAME TITLE[:\\s"]+([^\\n"]{3,50})/i);
      if (titleMatch) document.getElementById('game-label').textContent = '🎮 ' + titleMatch[1].trim();

      document.getElementById('game-section').style.display = 'block';
    }

    toast('✅ Game generated successfully!', '#4CAF50');
  }
</script>
</body>
</html>
"""

# ── App setup ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB

UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "/tmp/uploads"))
GAME_DIR   = Path(os.environ.get("GAME_DIR",   "/tmp/games"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
GAME_DIR.mkdir(parents=True,   exist_ok=True)

VIDEO_DIR = Path(os.environ.get("VIDEO_DIR", "/tmp/videos"))
VIDEO_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR = Path(os.environ.get("AUDIO_DIR", "/tmp/audio"))
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXT = {".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp"}
jobs: dict = {}


# ── Health check ──────────────────────────────────────────────────────────────
@app.route("/healthz")
def healthz():
    return {"status": "ok"}, 200


# ── Main UI ───────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    # Serve ui.html if present (3-tab app), else fall back to embedded HTML
    ui_path = Path(__file__).parent / "ui.html"
    if ui_path.exists():
        return ui_path.read_text(encoding="utf-8")
    return render_template_string(INDEX_HTML)


# ── Helpers ───────────────────────────────────────────────────────────────────
def allowed(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXT


def _run_job(job_id, api_key, asset_text, image_b64, image_type):
    try:
        jobs[job_id]["status"] = "running"

        def progress(step_num, label):
            jobs[job_id]["step"]  = step_num
            jobs[job_id]["label"] = label

        result = run_workflow(
            api_key=api_key,
            asset_text=asset_text,
            image_b64=image_b64,
            image_type=image_type,
            progress_cb=progress,
        )

        jobs[job_id].update({"step": 6, "label": "Generating game code…"})

        game_html = generate_game(api_key, result["s1"], result["s3"], result["s4"], result["s5"])
        game_path = GAME_DIR / f"{job_id}.html"
        game_path.write_text(game_html, encoding="utf-8")

        jobs[job_id].update({
            "status": "done",
            "step":    7,
            "label":   "Complete!",
            "result":  result,
            "game_id": job_id,
        })

    except Exception as exc:
        import traceback
        jobs[job_id].update({
            "status": "error",
            "error":  str(exc),
            "trace":  traceback.format_exc(),
        })


# ── API routes ────────────────────────────────────────────────────────────────
@app.route("/generate", methods=["POST"])
def generate():
    api_key = request.form.get("api_key", "").strip()
    if not api_key:
        return jsonify({"error": "OpenAI API key is required."}), 400

    asset_text = image_b64 = image_type = None

    if request.form.get("text_input", "").strip():
        asset_text = request.form["text_input"].strip()
    elif "file" in request.files and request.files["file"].filename:
        f = request.files["file"]
        if not allowed(f.filename):
            return jsonify({"error": "Unsupported file type. Use PDF, JPG, or PNG."}), 400
        fname     = secure_filename(f.filename)
        save_path = UPLOAD_DIR / fname
        f.save(save_path)
        ext = Path(fname).suffix.lower()
        try:
            if ext == ".pdf":
                asset_text = extract_pdf_text(str(save_path))
            else:
                image_b64, image_type = encode_image(str(save_path))
        except Exception as file_err:
            return jsonify({"error": f"Could not read file: {file_err}"}), 400
    else:
        return jsonify({"error": "Provide a file or text description."}), 400

    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "queued", "step": 0, "label": "Starting…"}
    threading.Thread(
        target=_run_job,
        args=(job_id, api_key, asset_text, image_b64, image_type),
        daemon=True,
    ).start()

    return jsonify({"job_id": job_id})


@app.route("/status/<job_id>")
def status(job_id):
    job = jobs.get(job_id)
    if not job:
        return {"error": "Job not found"}, 404
    return {k: v for k, v in job.items() if k != "trace"}


@app.route("/preview/<game_id>")
def preview(game_id):
    path = GAME_DIR / secure_filename(game_id + ".html")
    if not path.exists():
        return "Game not found", 404
    return send_file(path, mimetype="text/html")


@app.route("/download/<game_id>")
def download(game_id):
    path = GAME_DIR / secure_filename(game_id + ".html")
    if not path.exists():
        return "Game not found", 404
    return send_file(path, as_attachment=True,
                     download_name="moodsters_game.html",
                     mimetype="text/html")


@app.route("/generate-content", methods=["POST"])
def create_content():
    api_key = request.form.get("api_key", "").strip()
    if not api_key:
        return jsonify({"error": "OpenAI API key is required."}), 400

    platform     = request.form.get("platform",     "instagram")
    content_type = request.form.get("content_type", "caption")
    tone         = request.form.get("tone",         "Playful and fun")
    duration     = request.form.get("duration",     "30 seconds")
    text_input   = request.form.get("text_input",   "").strip()

    image_path = None
    if "file" in request.files and request.files["file"].filename:
        f = request.files["file"]
        if not allowed(f.filename):
            return jsonify({"error": "Unsupported file type."}), 400
        fname      = secure_filename(f.filename)
        image_path = str(UPLOAD_DIR / fname)
        f.save(image_path)

    if not image_path and not text_input:
        return jsonify({"error": "Provide a character image or description."}), 400

    try:
        result = generate_content(
            api_key=api_key,
            platform=platform,
            content_type=content_type,
            tone=tone,
            image_path=image_path,
            text=text_input if not image_path else None,
            duration=duration,
        )
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500



@app.route("/generate-video", methods=["POST"])
def create_video():
    openai_key   = request.form.get("api_key",        "").strip()
    heygen_key   = request.form.get("heygen_key",     "").strip()
    el_key       = request.form.get("el_key",         "").strip()
    fal_key      = request.form.get("fal_key",        "").strip()
    mode         = request.form.get("video_mode",     "animation")  # talking|animation|voice
    video_type   = request.form.get("video_type",    "social_reel")
    aspect_ratio = request.form.get("aspect_ratio",  "9:16")
    duration     = request.form.get("duration",      "15")
    text_input   = request.form.get("text_input",    "").strip()

    if not openai_key:
        return jsonify({"error": "OpenAI API key is required."}), 400
    if mode == "talking" and not heygen_key:
        return jsonify({"error": "HeyGen API key is required for Talking Character mode."}), 400
    if mode in ("talking", "voice") and not el_key:
        return jsonify({"error": "ElevenLabs API key is required for voice generation."}), 400
    if mode == "animation" and not fal_key:
        return jsonify({"error": "fal.ai API key is required for Animation mode."}), 400

    image_path = None
    if "file" in request.files and request.files["file"].filename:
        f = request.files["file"]
        if not allowed(f.filename):
            return jsonify({"error": "Unsupported file type."}), 400
        fname      = secure_filename(f.filename)
        image_path = str(UPLOAD_DIR / fname)
        f.save(image_path)

    if mode == "talking" and not image_path:
        return jsonify({"error": "Talking Character mode needs a character image."}), 400
    if not image_path and not text_input:
        return jsonify({"error": "Provide a character image or description."}), 400

    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "running", "step": 1, "label": "Starting…"}

    # Capture app base URL now (request context) — needed for HeyGen audio URL
    app_base_url = request.host_url

    def _run():
        def cb(msg):
            jobs[job_id]["label"] = msg

        try:
            if mode == "talking":
                result = generate_talking_video(
                    openai_key=openai_key, heygen_key=heygen_key,
                    elevenlabs_key=el_key, video_type=video_type,
                    aspect_ratio=aspect_ratio, duration=duration,
                    image_path=image_path, text=text_input or None,
                    app_base_url=app_base_url,
                    audio_dir=AUDIO_DIR, video_dir=VIDEO_DIR,
                    progress_cb=cb,
                )
            elif mode == "animation":
                result = generate_animation_video(
                    openai_key=openai_key, fal_key=fal_key,
                    video_type=video_type, aspect_ratio=aspect_ratio,
                    duration=duration, image_path=image_path,
                    text=text_input or None,
                    video_dir=VIDEO_DIR, progress_cb=cb,
                )
            else:  # voice
                result = generate_voice_clip(
                    openai_key=openai_key, elevenlabs_key=el_key,
                    video_type=video_type, duration=duration,
                    image_path=image_path, text=text_input or None,
                    audio_dir=AUDIO_DIR, progress_cb=cb,
                )

            jobs[job_id].update({
                "status": "done", "label": "Complete!", "result": result,
                "video_id":  result.get("video_file"),
                "audio_id":  result.get("audio_id"),
                "mode":      mode,
            })
        except Exception as exc:
            import traceback
            jobs[job_id].update({
                "status": "error",
                "error":  str(exc),
                "trace":  traceback.format_exc(),
            })

    import threading
    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"job_id": job_id})


@app.route("/audio/<audio_id>")
def serve_audio(audio_id):
    """Serve ElevenLabs audio — HeyGen fetches this URL."""
    safe = secure_filename(audio_id + ".mp3")
    path = AUDIO_DIR / safe
    if not path.exists():
        return "Audio not found", 404
    return send_file(path, mimetype="audio/mpeg")


@app.route("/download-audio/<audio_id>")
def download_audio(audio_id):
    safe = secure_filename(audio_id + ".mp3")
    path = AUDIO_DIR / safe
    if not path.exists():
        return "Audio not found", 404
    return send_file(path, as_attachment=True,
                     download_name="moodsters_voice.mp3",
                     mimetype="audio/mpeg")


@app.route("/video/<video_id>")
def serve_video(video_id):
    safe = secure_filename(video_id + ".mp4")
    path = VIDEO_DIR / safe
    if not path.exists():
        return "Video not found", 404
    return send_file(path, mimetype="video/mp4")


@app.route("/download-video/<video_id>")
def download_video(video_id):
    safe = secure_filename(video_id + ".mp4")
    path = VIDEO_DIR / safe
    if not path.exists():
        return "Video not found", 404
    return send_file(path, as_attachment=True,
                     download_name="moodsters_video.mp4",
                     mimetype="video/mp4")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
