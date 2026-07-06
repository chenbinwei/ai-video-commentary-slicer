from __future__ import annotations

import html
import socketserver
import urllib.parse
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

from better_story.modules.characters import apply_character_map
from better_story.utils.json_io import read_json
from better_story.utils.timecode import format_seconds


def run_review_gui(task_dir: Path, *, host: str = "127.0.0.1", port: int = 8765) -> None:
    task_dir = task_dir.resolve()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            if self.path not in ["/", "/index.html"]:
                self.send_error(404)
                return
            self._send_html(render_page(task_dir, saved=False))

        def do_POST(self) -> None:
            if self.path != "/save":
                self.send_error(404)
                return
            length = int(self.headers.get("content-length", "0"))
            raw = self.rfile.read(length).decode("utf-8")
            fields = urllib.parse.parse_qs(raw, keep_blank_values=True)
            save_character_map(task_dir, fields)
            self._send_html(render_page(task_dir, saved=True))

        def _send_html(self, body: str) -> None:
            encoded = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    with socketserver.TCPServer((host, port), Handler) as httpd:
        print(f"Character review GUI: http://{host}:{port}")
        print("Press Ctrl+C after saving when you want to return to the terminal.")
        httpd.serve_forever()


def render_page(task_dir: Path, *, saved: bool) -> str:
    utterances_path = task_dir / "analysis" / "utterances_with_characters.json"
    if not utterances_path.exists():
        utterances_path = task_dir / "analysis" / "utterances.json"
    utterances = read_json(utterances_path)
    names = sorted({u.get("character_name", "") for u in utterances if u.get("character_name")})
    names.extend(name for name in ["男主", "女主", "反派", "旁白", "路人", "未知"] if name not in names)
    rows = []
    for item in utterances:
        utterance_id = html.escape(item["utterance_id"])
        text = html.escape(item.get("text", ""))
        speaker_id = html.escape(item.get("speaker_id", "spk_00"))
        suggested = html.escape(item.get("suggested_character", ""))
        character = html.escape(item.get("character_name", "未知"))
        rows.append(
            "<tr>"
            f"<td>{utterance_id}</td>"
            f"<td>{format_seconds(float(item['start']))}</td>"
            f"<td>{format_seconds(float(item['end']))}</td>"
            f"<td>{speaker_id}</td>"
            f"<td>{suggested}</td>"
            f"<td><input name=\"char__{utterance_id}\" value=\"{character}\" list=\"character_names\"></td>"
            f"<td class=\"text\">{text}</td>"
            "</tr>"
        )
    options = "\n".join(f"<option value=\"{html.escape(name)}\">" for name in names)
    status = "<p class=\"saved\">Saved. You can close this page or continue editing.</p>" if saved else ""
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>better-story Character Review</title>
  <style>
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f6f7f9;
      color: #1f2328;
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 2;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 14px 18px;
      background: #ffffff;
      border-bottom: 1px solid #d8dee4;
    }}
    h1 {{
      margin: 0;
      font-size: 18px;
    }}
    button {{
      border: 1px solid #0969da;
      background: #0969da;
      color: #ffffff;
      padding: 8px 14px;
      border-radius: 6px;
      font-size: 14px;
      cursor: pointer;
    }}
    .wrap {{
      padding: 16px;
    }}
    .saved {{
      margin: 0 0 12px;
      color: #1a7f37;
      font-weight: 600;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: #ffffff;
      border: 1px solid #d8dee4;
    }}
    th, td {{
      border-bottom: 1px solid #d8dee4;
      padding: 8px;
      vertical-align: top;
      font-size: 13px;
    }}
    th {{
      position: sticky;
      top: 57px;
      background: #f0f3f6;
      text-align: left;
      z-index: 1;
    }}
    input {{
      width: 110px;
      box-sizing: border-box;
      border: 1px solid #d0d7de;
      border-radius: 4px;
      padding: 5px 6px;
    }}
    .text {{
      min-width: 320px;
      line-height: 1.5;
    }}
  </style>
</head>
<body>
  <form method="post" action="/save">
    <header>
      <h1>Character Review: {html.escape(str(task_dir))}</h1>
      <button type="submit">Save Character Labels</button>
    </header>
    <div class="wrap">
      {status}
      <datalist id="character_names">
        {options}
      </datalist>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Start</th>
            <th>End</th>
            <th>Speaker</th>
            <th>AI Suggestion</th>
            <th>Character</th>
            <th>Line</th>
          </tr>
        </thead>
        <tbody>
          {''.join(rows)}
        </tbody>
      </table>
    </div>
  </form>
</body>
</html>"""


def save_character_map(task_dir: Path, fields: dict[str, list[str]]) -> None:
    utterances = read_json(task_dir / "analysis" / "utterances.json")
    existing = read_json(task_dir / "analysis" / "character_map.json")
    overrides = []
    for item in utterances:
        key = f"char__{item['utterance_id']}"
        value = fields.get(key, ["未知"])[0].strip() or "未知"
        overrides.append({"utterance_id": item["utterance_id"], "character_name": value})
    character_map = {
        "speakers": existing.get("speakers", []),
        "utterance_overrides": overrides,
    }
    apply_character_map(task_dir, character_map)
