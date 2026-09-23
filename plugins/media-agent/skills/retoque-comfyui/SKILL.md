---
name: retoque-comfyui
description: Retocar e gerar imagem com ComfyUI sem abrir a interface, numa GPU de 8 GB e so com modelos de licenca comercial — tirar fundo (BiRefNet), upscale de foto (4xRealWebPhoto DAT2), remover logo ou objeto (LaMa), inpaint e still (Z-Image Turbo). Use quando a tarefa envolver ComfyUI, Stable Diffusion, FLUX, upscale, remover fundo, PNG transparente, tirar marca d'agua ou logo de um frame, inpainting, gerar imagem local, VRAM, ou quando alguem for usar 4x-UltraSharp, RMBG-2.0 ou FLUX.1 dev numa peca de empresa.
---

# Retoque de imagem com ComfyUI, sem interface

O ComfyUI e um servidor HTTP; a interface e um cliente. Um agente nao precisa
dela: sobe o servidor, envia o grafo em formato API, espera o `/history`, baixa
o PNG. Os scripts desta skill fazem isso.

## Uso

```bash
export COMFY_HOME=~/.local/opt/comfyui        # contem ComfyUI/ (clone) e .venv/
S="${CLAUDE_PLUGIN_ROOT}/skills/retoque-comfyui/scripts/comfy-run.py"
python3 "$S" fundo   foto.png  -o sem-fundo.png
python3 "$S" upscale foto.png  -o 2x.png --factor 2
python3 "$S" remover frame.png -o limpo.png --rect 1500,60,360,120
python3 "$S" inpaint foto.png "o que por ali" -o out.png --mask m.png
python3 "$S" gerar "descricao" -o still.png --size 1344x768 --seed 7
```

`comfy-run.py` sobe o servidor por `comfy-serve.sh` se nao houver um, e derruba
ao terminar o que ele mesmo subiu. Para uma sessao com varios jobs, rode
`comfy-serve.sh` a parte (ou passe `--keep` no primeiro). Um job por vez na GPU:
o modelo de difusao ocupa 6 GB em fp8, e um TTS ou o ACE-Step ao lado estoura.

## Licenca: o modelo mais citado e o errado

Os tutoriais apontam para o modelo mais famoso de cada categoria, e em tres
delas ele e nao comercial. Esta tabela foi conferida nas paginas oficiais em
2026-09:

| tarefa | use | licenca | nao use | por que |
|---|---|---|---|---|
| gerar / inpaint | Z-Image-Turbo 6B (Tongyi-MAI) | Apache-2.0 | FLUX.1 dev, FLUX.2 grandes | licenca paga para uso comercial |
| upscale de foto | 4xRealWebPhoto_v4_dat2 (Phips) | CC-BY-4.0, creditar | 4x-UltraSharp | CC-BY-NC-SA |
| upscale rapido | RealESRGAN_x4plus | BSD-3 | | |
| tirar fundo | BiRefNet-general | MIT | RMBG-2.0 (BRIA) | CC-BY-NC, comercial so com contrato |
| tirar objeto | big-lama (Samsung) | Apache-2.0 | | |
| no de fundo/LaMa | ComfyUI-RMBG (1038lab) | GPL-3, codigo do no | | nao afeta a licenca das imagens |

Z-Image Turbo, FLUX.1 schnell e FLUX.2 klein 4B sao os tres geradores que cabem
em 8 GB com licenca Apache. O Turbo faz 1024x1024 em 8 passos com `cfg 1`,
`res_multistep` + `simple`, `ModelSamplingAuraFlow shift 3`; sem
`ConditioningZeroOut` no negativo ele nao roda.

## Tirar logo: LaMa, nao difusao

Para remover coisa (logo, marca d'agua, objeto pequeno) o LaMa e um passo
feed-forward de 3 s que reconstroi textura do entorno e nao inventa. Inpaint
por difusao com "ceu limpo" numa area de arvores gerou galpoes coloridos em
60 s. Regra: `remover` para tirar, `inpaint` para por algo novo com prompt.

## Cabendo em 8 GB

- `--fp8_e4m3fn-unet` no servidor converte o bf16 de 12 GB para fp8 ao
  carregar; o encoder de texto vai em `qwen_3_4b_fp8_mixed`. Nao existe fp8
  pre-convertido do Z-Image no repo oficial; os menores sao int8 e nvfp4.
- Carregar o Z-Image pela primeira vez leva ~50 s; os jobs seguintes na mesma
  sessao, segundos. Por isso `--keep`.
- `torch` do venv: reaproveite o wheel que outro venv ja tem no cache do `uv`
  (`uv pip install torch==X --index-url .../cu130`), senao sao 3 GB de novo.

## Instalar do zero

```bash
mkdir -p "$COMFY_HOME" && cd "$COMFY_HOME"
git clone --depth 1 https://github.com/comfyanonymous/ComfyUI
git clone --depth 1 https://github.com/1038lab/ComfyUI-RMBG ComfyUI/custom_nodes/ComfyUI-RMBG
uv venv -p 3.12 .venv && uv pip install -p .venv/bin/python torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130
uv pip install -p .venv/bin/python -r ComfyUI/requirements.txt -r ComfyUI/custom_nodes/ComfyUI-RMBG/requirements.txt
```

Pesos (nomes que os workflows esperam): `z_image_turbo_bf16.safetensors` em
`models/diffusion_models`, `qwen_3_4b_fp8_mixed.safetensors` em
`models/text_encoders`, `ae.safetensors` em `models/vae` (os tres de
`Comfy-Org/z_image_turbo`, pasta `split_files/`); `4xRealWebPhoto_v4_dat2.safetensors`
(`Phips/4xRealWebPhoto_v4_dat2`) e `RealESRGAN_x4plus.pth` em `models/upscale_models`;
`1038lab/BiRefNet` (4 arquivos do `BiRefNet-general`) em `models/RMBG/BiRefNet`;
`1038lab/Lama` `big-lama.pt` em `models/RMBG/Lama`. ~19 GB. Os dois ultimos o no
baixa sozinho no primeiro uso; pre-baixar so evita o primeiro job lento.

## Upscale de video: SeedVR2 nao compensa em 8 GB

SeedVR2 (ByteDance, Apache-2.0 no codigo e nos pesos) pelo no
`numz/ComfyUI-SeedVR2_VideoUpscaler` (Apache-2.0, tem CLI propria). Em 8 GB
so rodou com o 3B GGUF Q8, BlockSwap 32, `--swap_io_components`, offload de
DiT e VAE para CPU, tiles de VAE de 512 px e lote de 9 frames; lote de 33
estoura a memoria no decoder do VAE. Medido em 36 frames 540p para 1080p:
292 s (~8 s por frame), pico de 7,8 GB de VRAM e 10 GB de RAM. Um minuto de
video leva horas, e o resultado inventa detalhe: SSIM contra o 1080p real de
0,65, contra 0,84 do bicubico. Serve para salvar video de terceiros em baixa
resolucao, nao para b-roll que ja e 1080p.

## Formato API versus formato da interface

O JSON que a interface salva (`nodes`, `links`, subgraphs) nao e o que o
endpoint `/prompt` aceita. Os workflows desta skill estao no formato API
(`{"id": {"class_type", "inputs"}}`), que a interface tambem importa. Para
converter um template da interface, use "Export (API)" nela — e note que os
templates oficiais recentes escondem os nos dentro de `definitions.subgraphs`.

## O que nao foi verificado

- Qualidade em GPU sem CUDA (ROCm, Apple): os flags de fp8 sao NVIDIA.
- Que `refine_foreground` do BiRefNet melhora cabelo em toda foto; melhorou
  cabo fino em foto de produto.
