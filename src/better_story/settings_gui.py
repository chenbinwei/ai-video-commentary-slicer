from __future__ import annotations

import html
import socketserver
import urllib.parse
from http.server import BaseHTTPRequestHandler
from typing import Any

from better_story.settings import ProviderSettings, load_settings, save_settings


def run_settings_gui(*, host: str = "127.0.0.1", port: int = 8764) -> None:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            if self.path not in ["/", "/index.html"]:
                self.send_error(404)
                return
            self._send_html(render_page(saved=False))

        def do_POST(self) -> None:
            if self.path != "/save":
                self.send_error(404)
                return
            length = int(self.headers.get("content-length", "0"))
            raw = self.rfile.read(length).decode("utf-8")
            fields = urllib.parse.parse_qs(raw, keep_blank_values=True)
            settings = ProviderSettings(
                provider=value(fields, "provider", "openai_compatible"),
                api_key=value(fields, "api_key", ""),
                base_url=value(fields, "base_url", ""),
                asr_model=value(fields, "asr_model", "whisper-1"),
                llm_model=value(fields, "llm_model", "gpt-4o-mini"),
                tts_provider=value(fields, "tts_provider", "same"),
                tts_api_key=value(fields, "tts_api_key", ""),
                tts_base_url=value(fields, "tts_base_url", ""),
                tts_model=value(fields, "tts_model", "gpt-4o-mini-tts"),
                tts_voice=value(fields, "tts_voice", "alloy"),
            )
            save_settings(settings)
            self._send_html(render_page(saved=True))

        def _send_html(self, body: str) -> None:
            encoded = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    with socketserver.TCPServer((host, port), Handler) as httpd:
        print(f"API settings GUI: http://{host}:{port}")
        print("Press Ctrl+C after saving when you want to return to the terminal.")
        httpd.serve_forever()


def value(fields: dict[str, list[str]], key: str, default: str) -> str:
    return fields.get(key, [default])[0].strip()


def render_page(*, saved: bool) -> str:
    settings = load_settings()
    status = "<p class=\"saved\">Saved to .better_story/settings.json.</p>" if saved else ""
    provider_options = options(
        ["openai_compatible", "openai", "mock"],
        settings.provider,
    )
    tts_provider_options = options(
        ["same", "openai_compatible", "openai", "mock"],
        settings.tts_provider,
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>better-story API Settings</title>
  <style>
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f6f7f9;
      color: #1f2328;
    }}
    header {{
      padding: 16px 20px;
      background: #ffffff;
      border-bottom: 1px solid #d8dee4;
    }}
    h1 {{
      margin: 0;
      font-size: 19px;
    }}
    main {{
      max-width: 760px;
      padding: 20px;
    }}
    form {{
      background: #ffffff;
      border: 1px solid #d8dee4;
      padding: 18px;
    }}
    label {{
      display: block;
      margin: 14px 0 6px;
      font-weight: 600;
      font-size: 14px;
    }}
    input, select {{
      width: 100%;
      box-sizing: border-box;
      border: 1px solid #d0d7de;
      border-radius: 6px;
      padding: 9px 10px;
      font-size: 14px;
    }}
    .hint {{
      color: #57606a;
      font-size: 13px;
      line-height: 1.5;
      margin: 6px 0 0;
    }}
    button {{
      margin-top: 18px;
      border: 1px solid #0969da;
      background: #0969da;
      color: #ffffff;
      padding: 9px 14px;
      border-radius: 6px;
      font-size: 14px;
      cursor: pointer;
    }}
    .saved {{
      color: #1a7f37;
      font-weight: 600;
    }}
    code {{
      background: #f0f3f6;
      padding: 2px 5px;
      border-radius: 4px;
    }}
  </style>
</head>
<body>
  <header>
    <h1>better-story API Settings</h1>
  </header>
  <main>
    {status}
    <form method="post" action="/save">
      <label>Provider</label>
      <select name="provider">{provider_options}</select>
      <p class="hint"><code>openai_compatible</code> 适合 PinAI 或其他兼容 OpenAI SDK 的第三方 API。</p>

      <label>API Key</label>
      <input name="api_key" type="password" value="{escape(settings.api_key)}" autocomplete="off">
      <p class="hint">会保存在本机 <code>.better_story/settings.json</code>，不要上传或分享这个文件。</p>

      <label>Base URL</label>
      <input name="base_url" value="{escape(settings.base_url)}" placeholder="https://api.example.com/v1">
      <p class="hint">官方 OpenAI 可以留空；第三方兼容服务通常需要填写自己的 API base URL。</p>

      <label>ASR Model</label>
      <input name="asr_model" value="{escape(settings.asr_model)}">

      <label>LLM Model</label>
      <input name="llm_model" value="{escape(settings.llm_model)}">

      <label>TTS Provider</label>
      <select name="tts_provider">{tts_provider_options}</select>
      <p class="hint"><code>same</code> 表示配音沿用上面的主 API；需要另一个配音平台时选择兼容 provider 并填写下面字段。</p>

      <label>TTS API Key</label>
      <input name="tts_api_key" type="password" value="{escape(settings.tts_api_key)}" autocomplete="off">

      <label>TTS Base URL</label>
      <input name="tts_base_url" value="{escape(settings.tts_base_url)}" placeholder="https://tts-api.example.com/v1">

      <label>TTS Model</label>
      <input name="tts_model" value="{escape(settings.tts_model)}">

      <label>TTS Voice</label>
      <input name="tts_voice" value="{escape(settings.tts_voice)}">

      <button type="submit">Save Settings</button>
    </form>
  </main>
</body>
</html>"""


def escape(value: str) -> str:
    return html.escape(value or "", quote=True)


def options(values: list[str], selected: str) -> str:
    return "".join(
        f"<option value=\"{escape(value)}\"{' selected' if value == selected else ''}>{escape(value)}</option>"
        for value in values
    )
