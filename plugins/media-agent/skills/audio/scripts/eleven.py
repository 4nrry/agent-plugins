#!/usr/bin/env python3
"""ElevenLabs through the REST API: local file in, local file out. Stdlib only.

  eleven.py sfx "soft transition whoosh" -o whoosh.mp3 [--seconds 1.5] [--loop] [--influence 0.3]
  eleven.py music "calm ambient, piano and pads, no drums" -o music.mp3 --seconds 40 [--vocals]
  eleven.py isolate recording.wav -o clean-voice.mp3
  eleven.py stt audio.mp3 -o transcript.json [--lang por]
  eleven.py credits

ELEVENLABS_API_KEY comes from the environment; inject it with your secrets manager's `run`.
`stt` saves the API JSON and prints sentences with start and end times, ready for captions.
"""
import argparse, json, mimetypes, os, sys, urllib.error, urllib.request, uuid

API = "https://api.elevenlabs.io/v1"


def key():
    return os.environ.get("ELEVENLABS_API_KEY") or sys.exit("ELEVENLABS_API_KEY is not set")


def request(path, *, body=None, files=None, fields=None, method="POST", timeout=600):
    headers = {"xi-api-key": key()}
    data = None
    if files is not None:
        boundary = uuid.uuid4().hex
        parts = []
        for name, value in (fields or {}).items():
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
        for name, path_ in files.items():
            mime = mimetypes.guess_type(path_)[0] or "application/octet-stream"
            head = (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{os.path.basename(path_)}"\r\n'
                    f"Content-Type: {mime}\r\n\r\n").encode()
            parts.append(head + open(path_, "rb").read() + b"\r\n")
        data = b"".join(parts) + f"--{boundary}--\r\n".encode()
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    elif body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(API + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode(errors='replace')[:1200]}")


def save(out, data):
    with open(out, "wb") as f:
        f.write(data)
    print(f"{out}  {len(data)/1e3:.0f} KB")


def sentences(words, gap=0.6):
    """Group words into sentences by final punctuation or a long pause."""
    out, cur = [], []
    for w in words:
        if w.get("type") != "word":
            continue
        if cur and (w["start"] - cur[-1]["end"] > gap):
            out.append(cur); cur = []
        cur.append(w)
        if w["text"].rstrip().endswith((".", "!", "?")):
            out.append(cur); cur = []
    if cur:
        out.append(cur)
    return [{"start": round(c[0]["start"], 2), "end": round(c[-1]["end"], 2), "text": " ".join(x["text"].strip() for x in c)} for c in out]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sfx"); s.add_argument("prompt"); s.add_argument("-o", "--out", required=True)
    s.add_argument("--seconds", type=float); s.add_argument("--loop", action="store_true"); s.add_argument("--influence", type=float, default=0.3)
    s = sub.add_parser("music"); s.add_argument("prompt"); s.add_argument("-o", "--out", required=True)
    s.add_argument("--seconds", type=float, required=True); s.add_argument("--vocals", action="store_true")
    s = sub.add_parser("isolate"); s.add_argument("audio"); s.add_argument("-o", "--out", required=True)
    s = sub.add_parser("stt"); s.add_argument("audio"); s.add_argument("-o", "--out", required=True); s.add_argument("--lang")
    sub.add_parser("credits")
    a = p.parse_args()

    if a.cmd == "sfx":
        body = {"text": a.prompt, "prompt_influence": a.influence, "loop": a.loop}
        if a.seconds:
            body["duration_seconds"] = a.seconds
        save(a.out, request("/sound-generation", body=body))
    elif a.cmd == "music":
        save(a.out, request("/music", body={"prompt": a.prompt, "music_length_ms": int(a.seconds * 1000),
                                            "force_instrumental": not a.vocals}))
    elif a.cmd == "isolate":
        save(a.out, request("/audio-isolation", files={"audio": a.audio}))
    elif a.cmd == "stt":
        fields = {"model_id": "scribe_v2", "timestamps_granularity": "word"}
        if a.lang:
            fields["language_code"] = a.lang
        res = json.loads(request("/speech-to-text", files={"file": a.audio}, fields=fields))
        with open(a.out, "w") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
        for fr in sentences(res.get("words", [])):
            print(f'{fr["start"]:7.2f} {fr["end"]:7.2f}  {fr["text"]}')
    elif a.cmd == "credits":
        sub_ = json.loads(request("/user/subscription", method="GET"))
        print(f'{sub_["tier"]}: {sub_["character_limit"] - sub_["character_count"]} of {sub_["character_limit"]} credits left')


if __name__ == "__main__":
    main()
