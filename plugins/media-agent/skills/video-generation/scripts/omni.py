#!/usr/bin/env python3
"""Generate a clip with Gemini Omni through the Gemini API's Interactions API. Stdlib only.

  omni.py "motion prompt" -o clip.mp4 [--image frame.png] [--res 360p|720p|1080p|4k] [--aspect 16:9|9:16]

Gemini Omni replaced the Veo 3.1 preview in the Gemini API (shut down 2026-10-22).
It has no negative-prompt field and no duration setting: say "no text, no people"
in the prompt and trim in the edit. 1080p and 4k are upscaled and come back as a
file URI; 360p and 720p come back inline.

GEMINI_API_KEY comes from the environment (inject it with your secrets manager's `run`).
The key's project should have a monthly spend cap in Cloud Billing.
"""
import argparse, base64, json, mimetypes, os, sys, time, urllib.error, urllib.request

API = "https://generativelanguage.googleapis.com/v1beta"
URI_RESOLUTIONS = ("1080p", "4k")      # over 4 MB: the docs say to use delivery "uri"


def call(method, url, key, body=None, raw=False, timeout=120):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"x-goog-api-key": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read() if raw else json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode(errors='replace')[:1500]}")


def video_part(resp):
    for step in resp.get("steps") or []:
        if step.get("type") != "model_output":
            continue
        for part in step.get("content") or []:
            if part.get("type") == "video":
                return part
    return None


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("prompt")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--image", help="first frame (png/jpg)")
    p.add_argument("--model", default="gemini-omni-1.1-flash")
    p.add_argument("--res", default="720p", choices=["360p", "720p", "1080p", "4k"])
    p.add_argument("--aspect", default="16:9", choices=["16:9", "9:16"])
    a = p.parse_args()
    key = os.environ.get("GEMINI_API_KEY") or sys.exit("GEMINI_API_KEY is missing (inject it via your secrets manager)")

    parts = []
    if a.image:
        mime = mimetypes.guess_type(a.image)[0] or "image/png"
        parts.append({"type": "image", "data": base64.b64encode(open(a.image, "rb").read()).decode(), "mime_type": mime})
    parts.append({"type": "text", "text": a.prompt})
    fmt = {"type": "video", "aspect_ratio": a.aspect, "resolution": a.res}
    if a.res in URI_RESOLUTIONS:
        fmt["delivery"] = "uri"
    body = {"model": a.model, "input": parts, "response_format": fmt,
            "background": False, "store": False, "stream": False}
    if a.image:
        body["generation_config"] = {"video_config": {"task": "image_to_video"}}

    t0 = time.time()
    resp = call("POST", f"{API}/interactions", key, body, timeout=1800)
    if resp.get("status") != "completed":
        sys.exit("Omni did not complete: " + json.dumps({k: v for k, v in resp.items() if k != "steps"},
                                                        ensure_ascii=False)[:1500])
    part = video_part(resp)
    if not part:
        sys.exit("response has no video: " + json.dumps(resp, ensure_ascii=False)[:1500])
    if part.get("data"):
        data = base64.b64decode(part["data"])
    else:
        uri = part.get("uri") or sys.exit("video part has neither data nor uri")
        name = uri.split("/v1beta/", 1)[1].split(":", 1)[0]          # files/<id>
        while (state := call("GET", f"{API}/{name}", key).get("state")) != "ACTIVE":
            if state == "FAILED":
                sys.exit(f"the video file {name} failed to process")
            time.sleep(5)
        data = call("GET", uri, key, raw=True, timeout=600)
    with open(a.out, "wb") as f:
        f.write(data)
    print(f"{a.out}  {len(data)/1e6:.1f} MB  {time.time()-t0:.0f}s  model={a.model} {a.res} {a.aspect}")


if __name__ == "__main__":
    main()
