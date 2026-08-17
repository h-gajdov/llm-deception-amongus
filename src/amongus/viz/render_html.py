from __future__ import annotations

import json
import re
from string import Template

from .layout import GRID_COLS, GRID_ROWS, ROOM_GRID, hex_for
from .reconstruct import Frame, PlayerInfo

_PAGE = Template(
    """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Among Us — $GAME_INDEX</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
         background: #0f1220; color: #e6e8f0; }
  header { padding: 14px 20px; border-bottom: 1px solid #262a40;
           display: flex; align-items: baseline; gap: 16px; flex-wrap: wrap; }
  header h1 { font-size: 18px; margin: 0; }
  .winner { color: #9aa4c8; font-size: 14px; }
  main { display: grid; grid-template-columns: 1fr 340px; gap: 16px; padding: 16px;
         align-items: start; }
  @media (max-width: 860px) { main { grid-template-columns: 1fr; } }
  .board { display: grid; gap: 8px;
           grid-template-columns: repeat($GRID_COLS, 1fr);
           grid-template-rows: repeat($GRID_ROWS, minmax(84px, 1fr)); }
  .room { border: 1px solid #2c3150; border-radius: 10px; background: #171a2e;
          padding: 6px 8px; min-height: 84px; }
  .room.empty { border: none; background: transparent; }
  .room .name { font-size: 11px; color: #8b93bd; text-transform: uppercase;
                letter-spacing: .04em; margin-bottom: 6px; }
  .tokens { display: flex; flex-wrap: wrap; gap: 5px; }
  .token { width: 24px; height: 24px; border-radius: 50%; font-size: 11px;
           display: flex; align-items: center; justify-content: center;
           font-weight: 700; color: #0c0e18; border: 2px solid rgba(255,255,255,.25); }
  .token.dead { filter: grayscale(1) brightness(.6); position: relative; }
  .token.dead::after { content: "💀"; position: absolute; font-size: 15px; }
  .token.impostor { border-color: #ff3b3b;
                    box-shadow: 0 0 0 1px #ff3b3b, 0 0 7px rgba(255,59,59,.55); }
  .imp-text { color: #ff6b6b; }
  .legend { font-size: 12px; color: #9aa4c8; }
  .legend .dot { display: inline-block; width: 11px; height: 11px; border-radius: 50%;
                 border: 2px solid #ff3b3b; vertical-align: -1px; margin-right: 4px; }
  .controls { display: flex; align-items: center; gap: 10px; padding: 4px 16px 0; }
  .controls button { background: #262a44; color: #e6e8f0; border: 1px solid #383e63;
                     border-radius: 8px; padding: 6px 12px; cursor: pointer; font-size: 14px; }
  .controls button:hover { background: #303660; }
  .controls input[type=range] { flex: 1; }
  .caption { padding: 8px 16px 0; min-height: 44px; }
  .caption .ev { font-size: 15px; }
  .caption .speech { color: #ffd479; font-style: italic; margin-top: 4px; }
  .phase-pill { font-size: 11px; padding: 2px 8px; border-radius: 999px; margin-left: 8px; }
  .phase-task { background: #12351f; color: #67e08a; }
  .phase-meeting { background: #35211f; color: #ffb27a; }
  aside { border: 1px solid #262a40; border-radius: 10px; background: #12142400;
          max-height: 70vh; overflow-y: auto; }
  .log-row { padding: 8px 12px; border-bottom: 1px solid #1e2338; cursor: pointer;
             font-size: 13px; display: flex; gap: 8px; }
  .log-row:hover { background: #1a1f38; }
  .log-row.active { background: #232a4d; }
  .log-row .stp { color: #6b73a0; min-width: 42px; }
  .icon { width: 18px; text-align: center; }
</style>
</head>
<body>
<header>
  <h1>Among Us — $GAME_INDEX</h1>
  <span class="winner">$WINNER</span>
  <span class="legend"><span class="dot"></span>red outline / text = Impostor</span>
</header>
<div class="controls">
  <button id="prev">◀</button>
  <button id="play">▶ Play</button>
  <button id="next">▶</button>
  <input type="range" id="slider" min="0" value="0">
  <span id="stepLabel"></span>
</div>
<div class="caption">
  <div class="ev" id="caption"></div>
  <div class="speech" id="speech"></div>
</div>
<main>
  <div class="board" id="board"></div>
  <aside id="log"></aside>
</main>
<script>
const DATA = $DATA;
const KIND_ICON = { move:"→", vent:"🕳", kill:"💀", report:"🚨", meeting:"📢",
                    speak:"💬", vote:"🗳", task:"🔧", other:"⏸" };
const rosterByName = {};
DATA.roster.forEach(p => rosterByName[p.name] = p);

const board = document.getElementById("board");
const slider = document.getElementById("slider");
const caption = document.getElementById("caption");
const speech = document.getElementById("speech");
const stepLabel = document.getElementById("stepLabel");
const log = document.getElementById("log");
slider.max = DATA.frames.length - 1;

function tokenEl(name, dead) {
  const p = rosterByName[name] || { hex:"#888", num:"?" };
  const t = document.createElement("div");
  const imp = p.role === "Impostor";
  t.className = "token" + (dead ? " dead" : "") + (imp ? " impostor" : "");
  t.style.background = p.hex;
  t.title = name + " (" + (p.role||"") + ")";
  t.textContent = dead ? "" : p.num;
  return t;
}

function renderBoard(frame) {
  board.innerHTML = "";
  const byRoom = {};
  DATA.rooms.forEach(r => byRoom[r.name] = []);
  Object.entries(frame.positions).forEach(([name, room]) => {
    if (frame.alive[name] && byRoom[room]) byRoom[room].push({name, dead:false});
  });
  Object.entries(frame.bodies).forEach(([name, room]) => {
    if (byRoom[room]) byRoom[room].push({name, dead:true});
  });
  DATA.rooms.forEach(r => {
    const cell = document.createElement("div");
    cell.className = "room";
    cell.style.gridColumn = (r.col + 1);
    cell.style.gridRow = (r.row + 1);
    const nm = document.createElement("div");
    nm.className = "name"; nm.textContent = r.name;
    const tk = document.createElement("div"); tk.className = "tokens";
    (byRoom[r.name] || []).forEach(o => tk.appendChild(tokenEl(o.name, o.dead)));
    cell.appendChild(nm); cell.appendChild(tk);
    board.appendChild(cell);
  });
}

function renderCaption(frame) {
  const pill = frame.phase.toLowerCase().indexOf("meeting") >= 0
    ? '<span class="phase-pill phase-meeting">meeting</span>'
    : '<span class="phase-pill phase-task">task</span>';
  caption.innerHTML = (KIND_ICON[frame.kind] || "") + " " + frame.text + pill;
  caption.classList.toggle("imp-text", frame.actor_role === "Impostor");
  speech.textContent = frame.speech ? ('"' + frame.speech + '"') : "";
  stepLabel.textContent = "Step " + frame.step;
}

function buildLog() {
  DATA.frames.forEach((f, i) => {
    const row = document.createElement("div");
    row.className = "log-row" + (f.actor_role === "Impostor" ? " imp-text" : "");
    row.id = "row-" + i;
    row.innerHTML = '<span class="stp">' + f.step + '</span>'
      + '<span class="icon">' + (KIND_ICON[f.kind] || "") + '</span>'
      + '<span>' + (f.speech ? ('"' + f.speech + '"') : f.text) + '</span>';
    row.onclick = () => setFrame(i);
    log.appendChild(row);
  });
}

let current = -1;
function setFrame(i) {
  i = Math.max(0, Math.min(DATA.frames.length - 1, i));
  const frame = DATA.frames[i];
  renderBoard(frame); renderCaption(frame);
  slider.value = i;
  if (current >= 0) document.getElementById("row-" + current).classList.remove("active");
  const row = document.getElementById("row-" + i);
  row.classList.add("active");
  row.scrollIntoView({ block: "nearest" });
  current = i;
}

let timer = null;
const playBtn = document.getElementById("play");
function togglePlay() {
  if (timer) { clearInterval(timer); timer = null; playBtn.textContent = "▶ Play"; return; }
  playBtn.textContent = "⏸ Pause";
  timer = setInterval(() => {
    if (current >= DATA.frames.length - 1) { togglePlay(); return; }
    setFrame(current + 1);
  }, 900);
}

slider.oninput = () => setFrame(parseInt(slider.value, 10));
document.getElementById("prev").onclick = () => setFrame(current - 1);
document.getElementById("next").onclick = () => setFrame(current + 1);
playBtn.onclick = togglePlay;
document.addEventListener("keydown", e => {
  if (e.key === "ArrowLeft") setFrame(current - 1);
  else if (e.key === "ArrowRight") setFrame(current + 1);
  else if (e.key === " ") { e.preventDefault(); togglePlay(); }
});

buildLog();
setFrame(0);
</script>
</body>
</html>
"""
)


def build_html(
    game_index: str,
    frames: list[Frame],
    roster: list[PlayerInfo],
    winner: str | None = None,
) -> str:
    data = {
        "game": game_index,
        "winner": winner,
        "rooms": [{"name": room, "row": rc[0], "col": rc[1]} for room, rc in ROOM_GRID.items()],
        "roster": [
            {
                "name": p.name,
                "num": _player_number(p.name),
                "color": p.color,
                "hex": hex_for(p.color),
                "role": p.role,
            }
            for p in roster
        ],
        "frames": [f.to_dict() for f in frames],
    }
    return _PAGE.substitute(
        GAME_INDEX=_escape(game_index),
        WINNER=_escape(winner or "outcome unknown"),
        GRID_COLS=GRID_COLS,
        GRID_ROWS=GRID_ROWS,
        DATA=json.dumps(data, ensure_ascii=False),
    )


def _player_number(name: str) -> str:
    match = re.search(r"Player\s+(\d+)", name)
    return match.group(1) if match else "?"


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


__all__ = ["build_html"]
