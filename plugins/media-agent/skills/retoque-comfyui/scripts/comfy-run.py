#!/usr/bin/env python3
"""Roda os workflows de ../workflows/ num ComfyUI local, sem abrir a interface. So stdlib.

  comfy-run.py gerar   "prompt"          -o out.png [--size 1344x768] [--seed N]
  comfy-run.py upscale foto.jpg          -o out.png [--factor 2]     # 4xRealWebPhoto DAT2 e reamostra ao fator
  comfy-run.py fundo   foto.jpg          -o out.png                  # BiRefNet, PNG com alpha
  comfy-run.py remover frame.png         -o out.png --mask m.png | --rect x,y,w,h    # LaMa: logo, objeto
  comfy-run.py inpaint foto.jpg "prompt" -o out.png --mask m.png | --rect x,y,w,h    # Z-Image so na mascara

Mascara: PNG onde branco = area a mexer. --rect monta a mascara dentro do grafo
(GetImageSize + SolidMask + MaskComposite), entao nao precisa de PIL aqui.
Sobe o servidor (comfy-serve.sh, exige COMFY_HOME) se nao houver um em --server e
derruba ao terminar, salvo --keep. Nunca mata um servidor que nao subiu.
"""
import argparse, json, os, random, subprocess, sys, time, urllib.error, urllib.parse, urllib.request, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
WORKFLOWS = os.path.join(os.path.dirname(HERE), "workflows")
IMAGE_NODE = {"upscale": "1", "fundo": "1", "remover": "1", "inpaint": "7"}
MASK_LOAD_NODE = {"remover": "2", "inpaint": "8"}
MASK_NODE = {"remover": "3", "inpaint": "9"}


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
    """Troca o LoadImage+ImageToMask da mascara por um retangulo montado no grafo."""
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
        sys.exit("ComfyUI recusou o workflow: " + e.read().decode(errors="replace")[:2000])
    t0 = time.time()
    while True:
        hist = get(server, f"/history/{pid}")
        if pid in hist:
            break
        time.sleep(0.5)
    status = hist[pid].get("status", {})
    if status.get("status_str") == "error":
        msgs = [m for m in status.get("messages", []) if m[0] == "execution_error"]
        sys.exit("erro no ComfyUI: " + json.dumps(msgs[-1][1] if msgs else status, ensure_ascii=False)[:2000])
    imgs = [i for o in hist[pid]["outputs"].values() for i in o.get("images", [])]
    if not imgs:
        sys.exit("workflow terminou sem imagem")
    q = urllib.parse.urlencode({"filename": imgs[0]["filename"], "subfolder": imgs[0]["subfolder"], "type": imgs[0]["type"]})
    with open(out, "wb") as f:
        f.write(get(server, f"/view?{q}", raw=True))
    print(f"{out}  ({time.time() - t0:.1f}s)")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("workflow", choices=["gerar", "upscale", "fundo", "remover", "inpaint"])
    p.add_argument("args", nargs="+", help="imagem e/ou prompt, conforme o workflow")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--mask")
    p.add_argument("--rect", help="x,y,w,h em pixels; monta a mascara no grafo")
    p.add_argument("--size", default="1024x1024", help="LxA para gerar (multiplos de 16)")
    p.add_argument("--seed", type=int)
    p.add_argument("--steps", type=int, default=8)
    p.add_argument("--factor", type=float, default=4.0, help="fator final do upscale (o modelo faz 4x; menor = reamostra)")
    p.add_argument("--denoise", type=float, default=1.0, help="inpaint: 1.0 refaz a area; menor preserva mais")
    p.add_argument("--server", default=os.environ.get("COMFY_SERVER", "http://127.0.0.1:8188"))
    p.add_argument("--keep", action="store_true", help="nao derruba o servidor que este comando subiu")
    a = p.parse_args()

    with open(os.path.join(WORKFLOWS, a.workflow + ".json")) as f:
        wf = json.load(f)
    seed = a.seed if a.seed is not None else random.randrange(2**31)

    if a.workflow == "gerar":
        (prompt,) = a.args
        w, h = (int(v) for v in a.size.lower().split("x"))
        wf["4"]["inputs"]["text"] = prompt
        wf["6"]["inputs"].update(width=w, height=h)
        wf["7"]["inputs"].update(seed=seed, steps=a.steps)
    else:
        image = a.args[0]
        if not os.path.isfile(image):
            sys.exit(f"imagem nao encontrada: {image}")
    if a.workflow in MASK_NODE and bool(a.mask) == bool(a.rect):
        sys.exit("informe --mask OU --rect")

    proc = None
    if not alive(a.server):
        serve = os.path.join(HERE, "comfy-serve.sh")
        log_path = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "comfy-run.log")
        with open(log_path, "ab") as log:
            proc = subprocess.Popen([serve], stdout=log, stderr=subprocess.STDOUT)
        for _ in range(240):
            if alive(a.server):
                break
            if proc.poll() is not None:
                sys.exit(f"servidor caiu ao subir; veja {log_path}")
            time.sleep(0.5)
        else:
            sys.exit(f"servidor nao respondeu em 120 s; veja {log_path}")
    try:
        if a.workflow != "gerar":
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
            wf["12"]["inputs"].update(seed=seed, steps=a.steps, denoise=a.denoise)
        run(a.server, wf, a.out)
    finally:
        if proc and not a.keep:
            proc.terminate()
            try:
                proc.wait(15)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    main()
