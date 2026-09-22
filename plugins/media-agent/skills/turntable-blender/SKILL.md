---
name: turntable-blender
description: Renderizar um turntable (giro de 360 graus) de um modelo .glb no Blender sem abrir a interface, em Cycles com GPU, frames PNG com fundo transparente para compor num video. Use quando a tarefa pedir render de produto, giro do dispositivo, animacao 3D de um glb ou gltf, Blender headless, `blender -b -P`, Cycles, CUDA ou OptiX, ou quando o Blender segfaultar ao enumerar dispositivos ou reclamar de `action.fcurves`.
---

# Turntable de um .glb no Blender headless

Um giro de produto em PNG RGBA e o que deixa a peca de video usar o modelo
real em vez de foto de banco. O script empacotado importa o glb, centra pelo
bounding box, poe camera a 3/4, tres area lights e renderiza uma volta.

```bash
blender -b -P "${CLAUDE_PLUGIN_ROOT}/skills/turntable-blender/scripts/turntable.py" -- \
  --glb modelo.glb --out /caminho/frames --frames 120 --samples 128 --res 1080
```

`--preview` renderiza 3 frames a 16 amostras para conferir enquadramento e luz
antes de gastar minutos. `--frames 120` a 30 fps e uma volta em 4 s; no video
use so o trecho que a cena pede.

## O que quebra sem erro util

- **`prefs.get_devices()` segfaulta** em maquina com GPU Intel Arc integrada
  ao lado da NVIDIA: a enumeracao passa por oneAPI/Level Zero e cai. Nao ha
  traceback, so "Segmentation fault". `get_devices_for_type("CUDA")` (ou
  `"OPTIX"`) enumera so aquele backend e nao toca no oneAPI. O script faz isso;
  `CYCLES_BACKEND=OPTIX` forca o backend.
- **Blender 5 nao tem `action.fcurves`**: actions viraram em camadas. Para
  interpolacao linear no giro, defina
  `preferences.edit.keyframe_new_interpolation_type = "LINEAR"` antes de
  inserir os keyframes, em vez de editar as curvas depois.
- **Superexposicao**: area light com energia em watts escala com a area. Com
  luz "razoavel" a 400 W num objeto de 30 cm o render sai branco. O script usa
  60/22/55 x size² para key/fill/rim, com `size` sendo a maior dimensao do
  modelo, e AgX Base Contrast, que segura o laranja sem estourar.
- **PNG RGBA e o formato**: `film_transparent = True` mais `color_mode = "RGBA"`.
  Sem os dois, o fundo vem cinza e a composicao no video mostra uma caixa.
- **Compondo sobre fundo claro**: o PNG com alpha premultiplicado aparece com
  halo branco em alguns compositores; no HTML/Remotion, `mix-blend-mode` no
  container transformado precisa de `isolation: isolate` no pai.

## Tempo

Numa RTX 4070 Laptop, 120 frames a 900 px e 128 amostras com denoise: cerca de
6 minutos em CUDA. OptiX e mais rapido quando disponivel, mas o driver precisa
casar com a versao do Blender; se `get_devices_for_type("OPTIX")` vier vazio,
o script cai para CUDA sozinho.

## O que nao foi verificado

- Modelos com varios materiais transmissivos (vidro) sob AgX: o teste foi um
  gabinete plastico com painel solar.
- Blender abaixo de 4.x: `keyframe_new_interpolation_type` existe, mas o
  restante nao foi testado.
