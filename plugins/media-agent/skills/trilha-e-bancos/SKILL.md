---
name: trilha-e-bancos
description: Conseguir musica, efeitos sonoros, fotos e videos de banco com licenca que permite uso comercial — ACE-Step 1.5 local para trilha, Openverse, Freesound, Pexels e Pixabay por API — e registrar a licenca por item. Use quando a tarefa pedir trilha sonora, musica de fundo, "sem copyright", royalty-free, b-roll, stock footage, SFX, whoosh, banco de imagens, Creative Commons, CC0, CC-BY, atribuicao, ou quando alguem for usar Jamendo, YouTube Audio Library ou "uma musica do Pixabay" num video de empresa.
---

# Trilha, efeitos e banco de midia com licenca comercial

"Sem copyright" nao existe; o que existe e licenca que permite o uso que voce
vai fazer. A armadilha e que todo servico mostra a musica de graca e esconde a
condicao no termo de uso.

## O mapa, com o que cada um esconde

| fonte | o que tem | licenca | armadilha |
|---|---|---|---|
| **ACE-Step 1.5** (local, GPU) | musica gerada, instrumental ou com voz | MIT (codigo e pesos) | carrega um LM de 1,7B mesmo com `thinking=false` e estoura 8 GB; ver toml abaixo |
| **Openverse** (API, sem chave) | audio e imagem CC | por item; `license_type=commercial` filtra | o filtro e por licenca declarada, o item pode estar mal marcado: confira a pagina |
| **Freesound** (API, chave) | SFX | por item; filtre `license:"Creative Commons 0"` | o download original exige OAuth2; o preview HQ mp3 nao, e serve para SFX |
| **Pexels** (API, chave) | foto e video | Pexels License: comercial, sem atribuicao obrigatoria | a CDN devolve 403 sem `User-Agent`; o JSON tem varios `video_files`, pegue o de maior largura |
| **Pixabay** (API, chave) | foto e video | Pixabay Content License: comercial, sem revenda avulsa | **nao serve musica pela API**; termos exigem cache de 24 h das respostas |
| Jamendo | musica | API gratuita e **so nao comercial** | video institucional precisa de licenca paga |
| YouTube Audio Library | musica | so para uso no YouTube | LinkedIn e Instagram estao fora |

CC-BY e credito obrigatorio por item, visivel na peca ou na descricao. Guarde
um `CREDITS.json` ao lado dos arquivos com id, autor, licenca e URL; o script
abaixo imprime exatamente esses campos.

## Buscar e baixar

```bash
S="${CLAUDE_PLUGIN_ROOT}/skills/trilha-e-bancos/scripts/media-search.py"
python3 "$S" openverse "ambient piano" --type audio --download DIR
python3 "$S" freesound "whoosh" --license cc0 --download DIR       # FREESOUND_API_KEY
python3 "$S" pexels "industrial plant drone" --type video --download DIR   # PEXELS_API_KEY
python3 "$S" pixabay "wastewater treatment" --type photo           # PIXABAY_API_KEY
```

So stdlib. Chaves vem do ambiente; injete com o `run` do seu gerenciador de
segredos, nao com `.env` no repositorio.

## ACE-Step 1.5 em 8 GB de VRAM

O modelo de difusao cabe. O que nao cabe e o LM auxiliar de 1,7B que a config
padrao carrega para "pensar" caption, letra e metadados — e `thinking = false`
nao o desliga. Use o molde em `references/ace-step-8gb.toml`: cada `use_cot_*`
em `false`, `use_format` e `sample_mode` em `false`, `offload_to_cpu` e
`offload_dit_to_cpu` em `true`. Com isso um trecho de 40 s sai em 8 passos numa
RTX 4070 Laptop.

```bash
cd ~/.../ACE-Step-1.5 && uv run python cli.py --config /caminho/ace-step-8gb.toml
```

Instalacao: `uv sync` no clone (Python 3.11 ou 3.12; 3.13+ nao resolve). O
`save_dir` do toml e absoluto: aponte para fora do clone, senao a saida some
no `git status` de outro repositorio.

Trilha institucional que funcionou: caption com "calm ambient, warm analog
pad, soft piano, no drums, minimal, slow evolving", `instrumental = true`,
70 bpm, 8 passos, `guidance_scale` 7. Gere 40 s, nao 60: o final tende a
degradar, e loop com crossfade de 2 s cobre a duracao que faltar.

## Uso no video

- Trilha a 0.5 sozinha, 0.16 sob a locucao, rampa de ~0.35 s. Ver a skill
  `locucao` para o alvo de -16 LUFS.
- B-roll: pegue 1080p30 e corte no NLE ou no Remotion; reencodar 4K para 1080
  na hora do render custa mais que baixar certo.

## O que nao foi verificado

- Que o filtro `license_type=commercial` do Openverse nunca deixa passar item
  mal marcado. E metadado do provedor, nao auditoria.
- A regra de cache de 24 h do Pixabay foi lida nos termos, nao testada contra
  bloqueio.
