#!/usr/bin/env python3
"""Run the workflows in ../workflows/ on a local ComfyUI, without opening the UI. Stdlib only.

  comfy-run.py generate   "prompt"         -o out.png [--size 1344x768] [--seed N]
  comfy-run.py upscale    photo.jpg        -o out.png [--factor 2]     # 4xRealWebPhoto DAT2, resampled to the factor
  comfy-run.py background photo.jpg        -o out.png                  # BiRefNet, PNG with alpha
  comfy-run.py remove     frame.png        -o out.png --mask m.png | --rect x,y,w,h    # LaMa: logo, object
  comfy-run.py inpaint    photo.jpg "prompt" -o out.png --mask m.png | --rect x,y,w,h  # Z-Image, masked area only
  comfy-run.py edit       photo.jpg "instruction" -o out.png [--seed N]   # FLUX.2 klein 4B, no mask; output ~1 MP

Mask: PNG where white = area to change. --rect builds the mask inside the graph
(GetImageSize + SolidMask + MaskComposite), so no PIL is needed here.
Starts the server (comfy-serve.sh, needs COMFY_HOME) if none answers on --server, on
that URL's port, and stops it when done, or when it fails to come up. --keep leaves it
running and prints its PID. Never kills a server it did not start.
"""
import argparse, json, os, random, subprocess, sys, time, urllib.error, urllib.parse, urllib.request, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
STARTUP_POLLS = int(os.environ.get("COMFY_STARTUP_POLLS", "240"))   # 0.5 s each: 120 s for a cold model load
WORKFLOWS = os.path.join(os.path.dirname(HERE), "workflows")
IMAGE_NODE = {"upscale": "1", "background": "1", "remove": "1", "inpaint": "7", "edit": "6"}
STEPS = {"generate": 8, "inpaint": 8, "edit": 4}   # Z-Image Turbo is distilled for 8, FLUX.2 klein for 4
MASK_LOAD_NODE = {"remove": "2", "inpaint": "8"}
MASK_NODE = {"remove": "3", "inpaint": "9"}


def get(server, path, raw=False):
    with urllib.request.urlopen(server + path, timeout=30) as r:
        return r.read() if raw else json.load(r)


def alive(server):
    try:
        get(server, "/system_stats")
        return True
    except (urllib.error.URLError, ConnectionError, TimeoutError):
        return False


def upload(server, path):
    name = f"{uuid.uuid4().hex}{os.path.splitext(path)[1] or '.png'}"
    boundary = uuid.uuid4().hex
    with open(path, "rb") as f:
        data = f.read()
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{name}\"\r\n"
            f"Content-Type: application/octet-stream\r\n\r\n").encode() + data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(server + "/upload/image", data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)["name"]


def rect_mask_nodes(wf, image_node, mask_node, rect):
    """Replace the mask LoadImage+ImageToMask with a rectangle built in the graph."""
    x, y, w, h = (int(v) for v in rect.split(","))
    wf["90"] = {"class_type": "GetImageSize", "inputs": {"image": [image_node, 0]}}
    wf["91"] = {"class_type": "SolidMask", "inputs": {"value": 0.0, "width": ["90", 0], "height": ["90", 1]}}
    wf["92"] = {"class_type": "SolidMask", "inputs": {"value": 1.0, "width": w, "height": h}}
    wf[mask_node] = {"class_type": "MaskComposite", "inputs": {"destination": ["91", 0], "source": ["92", 0], "x": x, "y": y, "operation": "add"}}


def run(server, wf, out):
    req = urllib.request.Request(server + "/prompt", data=json.dumps({"prompt": wf}).encode(), headers={"Content-Type": "application/json"})
    try:
        pid = json.load(urllib.request.urlopen(req, timeout=60))["prompt_id"]
    except urllib.error.HTTPError as e:
        sys.exit("ComfyUI rejected the workflow: " + e.read().decode(errors="replace")[:2000])
    t0 = time.time()
    while True:
        hist = get(server, f"/history/{pid}")
        if pid in hist:
            break
        if time.time() - t0 > 3600:
            sys.exit(f"ComfyUI has not finished prompt {pid} after 60 min")
        time.sleep(0.5)
    status = hist[pid].get("status", {})
    if status.get("status_str") == "error":
        msgs = [m for m in status.get("messages", []) if m[0] == "execution_error"]
        sys.exit("ComfyUI error: " + json.dumps(msgs[-1][1] if msgs else status, ensure_ascii=False)[:2000])
    imgs = [i for o in hist[pid]["outputs"].values() for i in o.get("images", [])]
    if not imgs:
        sys.exit("workflow finished without an image")
    q = urllib.parse.urlencode({"filename": imgs[0]["filename"], "subfolder": imgs[0]["subfolder"], "type": imgs[0]["type"]})
    with open(out, "wb") as f:
        f.write(get(server, f"/view?{q}", raw=True))
    print(f"{out}  ({time.time() - t0:.1f}s)")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("workflow", choices=["generate", "upscale", "background", "remove", "inpaint", "edit"])
    p.add_argument("args", nargs="+", help="image and/or prompt, depending on the workflow")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--mask")
    p.add_argument("--rect", help="x,y,w,h in pixels; builds the mask in the graph")
    p.add_argument("--size", default="1024x1024", help="WxH for generate (multiples of 16)")
    p.add_argument("--seed", type=int)
    p.add_argument("--steps", type=int, help="sampling steps (default: 8 for generate and inpaint, 4 for edit)")
    p.add_argument("--factor", type=float, default=4.0, help="final upscale factor (the model does 4x; lower = resample)")
    p.add_argument("--denoise", type=float, default=1.0, help="inpaint: 1.0 redraws the area; lower preserves more")
    p.add_argument("--server", default=os.environ.get("COMFY_SERVER", "http://127.0.0.1:8188"))
    p.add_argument("--keep", action="store_true", help="do not stop the server this command started")
    a = p.parse_args()

    with open(os.path.join(WORKFLOWS, a.workflow + ".json")) as f:
        wf = json.load(f)
    seed = a.seed if a.seed is not None else random.randrange(2**31)
    steps = a.steps or STEPS.get(a.workflow)

    if a.workflow == "generate":
        (prompt,) = a.args
        w, h = (int(v) for v in a.size.lower().split("x"))
        wf["4"]["inputs"]["text"] = prompt
        wf["6"]["inputs"].update(width=w, height=h)
        wf["7"]["inputs"].update(seed=seed, steps=steps)
    else:
        image = a.args[0]
        if not os.path.isfile(image):
            sys.exit(f"image not found: {image}")
    if a.workflow in ("inpaint", "edit") and len(a.args) != 2:
        sys.exit(f"{a.workflow} takes an image and a prompt")
    if a.workflow in MASK_NODE and bool(a.mask) == bool(a.rect):
        sys.exit("pass --mask OR --rect")

    proc, ready = None, False
    try:
        if not alive(a.server):
            serve = os.path.join(HERE, "comfy-serve.sh")
            log_path = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "comfy-run.log")
            url = urllib.parse.urlsplit(a.server)
            port = url.port or (443 if url.scheme == "https" else 80)        # the port this command will poll
            env = dict(os.environ, COMFY_PORT=str(port))
            with open(log_path, "ab") as log:
                proc = subprocess.Popen([serve], stdout=log, stderr=subprocess.STDOUT, env=env)
            for _ in range(STARTUP_POLLS):
                if alive(a.server):
                    break
                if proc.poll() is not None:
                    sys.exit(f"server died on startup; see {log_path}")
                time.sleep(0.5)
            else:
                sys.exit(f"server did not respond within {STARTUP_POLLS // 2} s; see {log_path}")
        ready = True
        if a.workflow != "generate":
            wf[IMAGE_NODE[a.workflow]]["inputs"]["image"] = upload(a.server, image)
        if a.workflow == "upscale":
            wf["4"]["inputs"]["scale_by"] = a.factor / 4.0
        if a.workflow in MASK_NODE:
            if a.mask:
                wf[MASK_LOAD_NODE[a.workflow]]["inputs"]["image"] = upload(a.server, a.mask)
            else:
                del wf[MASK_LOAD_NODE[a.workflow]]
                rect_mask_nodes(wf, IMAGE_NODE[a.workflow], MASK_NODE[a.workflow], a.rect)
        if a.workflow == "inpaint":
            wf["4"]["inputs"]["text"] = a.args[1]
            wf["12"]["inputs"].update(seed=seed, steps=steps, denoise=a.denoise)
        if a.workflow == "edit":
            wf["4"]["inputs"]["text"] = a.args[1]
            wf["14"]["inputs"]["steps"] = steps
            wf["16"]["inputs"]["noise_seed"] = seed
        run(a.server, wf, a.out)
    finally:
        # A server that never came up is stopped even with --keep: nothing can use it.
        if proc and proc.poll() is None and (not a.keep or not ready):
            proc.terminate()
            try:
                proc.wait(15)
            except subprocess.TimeoutExpired:
                proc.kill()
        elif proc and proc.poll() is None:
            print(f"ComfyUI left running (pid {proc.pid}); stop it after the last job: kill {proc.pid}")


if __name__ == "__main__":
    main()
