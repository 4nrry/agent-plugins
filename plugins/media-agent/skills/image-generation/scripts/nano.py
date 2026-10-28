#!/usr/bin/env python3
"""Generate or edit an image with a Gemini image model (generateContent). Stdlib only.

  nano.py MODEL "prompt" -o out.png [--image input.png] [--aspect 16:9]

MODEL: gemini-nano-banana-2.1 (generate) or gemini-3-pro-image (edit a still).
GEMINI_API_KEY comes from the environment (inject it with your secrets manager's `run`).
"""
import argparse, base64, json, mimetypes, os, sys, time, urllib.error, urllib.request

API = "https://generativelanguage.googleapis.com/v1beta"

p = argparse.ArgumentParser()
p.add_argument("model")
p.add_argument("prompt")
p.add_argument("-o", "--out", required=True)
p.add_argument("--image")
p.add_argument("--aspect", default="16:9")
a = p.parse_args()
key = os.environ.get("GEMINI_API_KEY") or sys.exit("GEMINI_API_KEY is not in the environment")
parts = [{"text": a.prompt}]
if a.image:
    mime = mimetypes.guess_type(a.image)[0] or "image/png"
    parts.append({"inlineData": {"mimeType": mime, "data": base64.b64encode(open(a.image, "rb").read()).decode()}})
body = {"contents": [{"parts": parts}],
        "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": a.aspect}}}
t0 = time.time()
req = urllib.request.Request(f"{API}/models/{a.model}:generateContent", data=json.dumps(body).encode(),
                             headers={"x-goog-api-key": key, "Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=300) as r:
        resp = json.load(r)
except urllib.error.HTTPError as e:
    sys.exit(f"HTTP {e.code}: {e.read().decode(errors='replace')[:800]}")
for c in resp.get("candidates", []):
    for part in c.get("content", {}).get("parts", []):
        if "inlineData" in part:
            data = base64.b64decode(part["inlineData"]["data"])
            open(a.out, "wb").write(data)
            usage = resp.get("usageMetadata", {})
            print(f"{a.out} {len(data)/1e6:.2f} MB {time.time()-t0:.0f}s model={a.model} "
                  f"tokens_in={usage.get('promptTokenCount')} tokens_out={usage.get('candidatesTokenCount')}")
            sys.exit(0)
sys.exit("no image in response: " + json.dumps(resp)[:800])
