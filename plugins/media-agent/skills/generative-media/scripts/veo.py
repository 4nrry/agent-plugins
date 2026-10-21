#!/usr/bin/env python3
"""Generate a clip with Veo through the Gemini API and download the MP4. Stdlib only.

  veo.py "prompt" -o clip.mp4 [--image frame.png] [--model veo-3.1-fast-generate-preview]
         [--res 1080p|720p] [--aspect 16:9|9:16] [--seconds 8] [--negative "text, people"]

GEMINI_API_KEY comes from the environment (inject it with your secrets manager's `run`).
The key's project should have a monthly spend cap in Cloud Billing; once the cap pauses
the service, the API returns an error and nothing more is charged.
"""
import argparse, base64, json, mimetypes, os, sys, time, urllib.error, urllib.request

API = "https://generativelanguage.googleapis.com/v1beta"


def call(method, url, key, body=None, raw=False, timeout=120):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"x-goog-api-key": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read() if raw else json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode(errors='replace')[:1500]}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("prompt")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--image", help="first frame (png/jpg)")
    p.add_argument("--model", default="veo-3.1-fast-generate-preview")
    p.add_argument("--res", default="1080p", choices=["720p", "1080p"])
    p.add_argument("--aspect", default="16:9", choices=["16:9", "9:16"])
    p.add_argument("--seconds", type=int, default=8)
    p.add_argument("--negative", default="text, captions, watermark, people",
                   help='"" omits the field; veo-3.1-lite does not accept it')
    a = p.parse_args()
    key = os.environ.get("GEMINI_API_KEY") or sys.exit("GEMINI_API_KEY is missing (inject it via your secrets manager)")

    inst = {"prompt": a.prompt}
    if a.image:
        mime = mimetypes.guess_type(a.image)[0] or "image/png"
        inst["image"] = {"bytesBase64Encoded": base64.b64encode(open(a.image, "rb").read()).decode(), "mimeType": mime}
    params = {"aspectRatio": a.aspect, "resolution": a.res, "durationSeconds": a.seconds}
    if a.negative:  # veo-3.1-lite rejects the field (HTTP 400): pass --negative ""
        params["negativePrompt"] = a.negative
    body = {"instances": [inst], "parameters": params}
    t0 = time.time()
    op = call("POST", f"{API}/models/{a.model}:predictLongRunning", key, body)
    name = op["name"]
    while not op.get("done"):
        time.sleep(10)
        op = call("GET", f"{API}/{name}", key)
    if "error" in op:
        sys.exit("Veo failed: " + json.dumps(op["error"], ensure_ascii=False)[:1500])
    resp = op.get("response", {})
    samples = (resp.get("generateVideoResponse") or resp).get("generatedSamples") or (resp.get("generateVideoResponse") or resp).get("generatedVideos") or []
    if not samples:
        sys.exit("response has no video: " + json.dumps(resp, ensure_ascii=False)[:1500])
    uri = samples[0]["video"]["uri"]
    data = call("GET", uri, key, raw=True, timeout=600)
    with open(a.out, "wb") as f:
        f.write(data)
    print(f"{a.out}  {len(data)/1e6:.1f} MB  {time.time()-t0:.0f}s  model={a.model} {a.res} {a.seconds}s")


if __name__ == "__main__":
    main()
