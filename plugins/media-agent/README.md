# Media Agent

Producao de midia por agente numa maquina propria — locucao, trilha, banco de
imagens e video, retoque, turntable 3D e o render do filme — no ponto em que a
GPU tem 8 GB, a empresa precisa de licenca comercial e a ferramenta nao avisa
que voce acabou de violar uma das duas. Seis skills, um servidor MCP e um hook, um feitio:
falha que nao levanta erro.

Saiu de uma producao real: um video institucional de 64 s com locucao pt-BR,
trilha gerada, b-roll de banco, turntable do produto em Blender e render em
Remotion, entregue em 16:9, 1:1, 9:16, 4:5 e carrossel PDF, numa RTX 4070
Laptop de 8 GB.

## Componentes

| componente | o que faz |
|---|---|
| `skills/locucao/` | TTS local ou ElevenLabs, uma frase por arquivo, `say` separado de `text`, -16 LUFS por frase e no final, JSON de duracoes que alimenta legenda e ducking. Um script: `vo-normalize.sh` (loudnorm em duas passadas + duracoes). |
| `skills/trilha-e-bancos/` | ACE-Step 1.5 cabendo em 8 GB, e Openverse/Freesound/Pexels/Pixabay por API com a licenca de cada item. Um script (`media-search.py`, so stdlib) e um molde de config (`ace-step-8gb.toml`). |
| `skills/retoque-comfyui/` | ComfyUI como servidor, sem interface: tirar fundo, upscale, remover logo, inpaint e still, so com modelos de licenca comercial. Dois scripts (`comfy-run.py`, `comfy-serve.sh`) e cinco workflows em formato API. |
| `skills/turntable-blender/` | Giro 360 de um `.glb` em Cycles/GPU headless, PNG RGBA. Um script (`turntable.py`). |
| `skills/video-remotion/` | Video como codigo: Remotion ou HTML + Chrome + ffmpeg, legenda derivada da locucao, quatro formatos e carrossel de um fonte so, a regra de licenca do Remotion, e quando por um `.glb` em cena com Three.js em vez do Blender. Um componente de referencia verificado (`references/glb-turntable.tsx`). |
| `skills/edicao-kinocut/` + `.mcp.json` | Registra o MCP do Kinocut (Apache-2.0, local, `uvx`, fixado em 1.15.1) para editar video pronto com resposta em JSON, e diz quando usar ele, ffmpeg na mao ou re-render. So texto mais a definicao do servidor. |
| `hooks/guard-vipsthumbnail.sh` | PreToolUse em `Bash(vipsthumbnail *)`: avisa quando `-o NOME` sem barra vai gravar no diretorio do arquivo de entrada. Avisa, nao bloqueia. |

## O que ele nao faz, de proposito

**Nao decide licenca por voce.** O Remotion e gratis ate 3 funcionarios e a
propria documentacao redige a regra de dois jeitos (FAQ: "time de ate 3
pessoas"; LICENSE.md: "funcionarios"). Co-fundador sem vinculo e zona cinzenta;
a skill relata as duas redacoes e para. O mesmo para o plano Free da
ElevenLabs, que e nao comercial: a skill diz, o usuario assina.

**Nao vende imagem gerada como conteudo.** O ComfyUI entra para limpar material
real (fundo, upscale, logo) e para still de apoio. Video de empresa que vende
credibilidade tecnica perde com imagem de cara de IA, e a skill diz isso onde
oferece o `gerar`.

**Nao guarda o estado da sua maquina.** Caminho do ComfyUI, chaves de API,
pasta de saida: tudo vem de variavel de ambiente (`COMFY_HOME`, `*_API_KEY`) ou
de argumento. Nenhum caminho absoluto de quem escreveu esta em script ou
workflow — o unico que existia (`save_dir` do toml do ACE-Step) e um
placeholder marcado.

**Nao substitui ouvido.** Quatro TTS locais foram descartados por um falante
nativo em 2026-09. A skill relata o veredito com a data; nao ha metrica que o
substitua.

## As armadilhas que sustentam as skills

| armadilha | o que acontece |
|---|---|
| TTS local sai a -24..-30 LUFS | A trilha a -20 cobre a voz e o mix "toca" sem erro. E `loudnorm` sozinho nao chega: o teto de true peak segura a voz 1 a 2 LU abaixo do alvo (-17,3 pedindo -16, em uma ou duas passadas). O script confere e corrige com ganho mais limiter. |
| Sigla lida letra a letra | `CETESB` vira "cê-é-tê-é-esse-bê". O JSON da locucao tem `say` separado de `text`; a legenda mostra um, o TTS le o outro. |
| ElevenLabs Free e nao comercial | A voz da biblioteca via API devolve `paid_plan_required`; `mp3_44100_192` devolve 403 no Starter (Creator+). `mp3_44100_128` funciona. |
| ACE-Step estoura 8 GB com `thinking = false` | O LM de 1,7B carrega do mesmo jeito. So `use_cot_metas/caption/lyrics/language = false` mais `use_format = false` e `sample_mode = false` desligam; com offload cabe. |
| Jamendo "gratis" | A API e gratuita para uso nao comercial. Video institucional nao e. |
| Pixabay sem musica pela API | Fotos e videos sim; audio nao existe no endpoint. E os termos exigem cache de 24 h. |
| Pexels CDN 403 | Sem `User-Agent` no download o arquivo nao vem; a busca funciona, o `curl` nao. |
| 4x-UltraSharp e RMBG-2.0 | Os modelos mais citados de upscale e fundo sao CC-BY-NC(-SA). Equivalentes livres: 4xRealWebPhoto DAT2 (CC-BY-4.0) e BiRefNet (MIT). Conferido nas paginas oficiais. |
| Difusao para tirar logo | "Ceu limpo" numa area de arvores gerou galpoes coloridos em 60 s. LaMa reconstroi textura em 3 s e nao inventa. |
| `get_devices()` segfaulta | Blender com Arc integrada ao lado da NVIDIA: a enumeracao passa por oneAPI e cai sem traceback. `get_devices_for_type("CUDA")` nao toca no oneAPI. |
| `action.fcurves` sumiu | Blender 5 tem actions em camadas. Interpolacao linear vai em `keyframe_new_interpolation_type` antes do keyframe, nao nas curvas depois. |
| `TransitionSeries` e Fragment | `<>...</>` dentro de `.map` da erro obscuro; `flatMap` devolvendo `[Transition, Sequence]` resolve. |
| ECharts dentro do Remotion | O grafico anima por relogio, nao por frame. Ou `delayRender` de ~1,5 s por frame, ou canvas a mao. |
| `vipsthumbnail -o nome.png` | `-o` e formato de nome: sem barra grava ao lado do arquivo de **entrada**. O thumbnail nasceu untracked dentro de outro repositorio e o cwd ficou vazio. Virou o hook. |
| Kinocut: comando que e casca | Sao 196 ferramentas, e parte nao faz nada: `sound-qa-loudness` na 1.15.1 nao aceita argumento e so imprime o uso. Rode uma vez num arquivo real antes de montar fluxo em cima. |
| Three.js que some no render | No Studio o modelo aparece; no render com `--gl=swangle` o quadro sai vazio, sem erro. So `angle` ou `vulkan` desenham. E o GLB tem de carregar fora do `ThreeCanvas`, senao o frame 0 sai vazio ou o render estoura o timeout. |
| Fade entre cenas de texto | O `fade()` sobrepoe as duas cenas e mostra dois titulos cruzados. A cena nova entra `T` frames depois, dentro de um `Sequence`. |
| SeedVR2 em 8 GB | Roda so com GGUF Q8, BlockSwap e tiles de 512 px; lote de 33 frames estoura. ~8 s por frame e inventa detalhe (SSIM 0,65 contra 0,84 do bicubico). |
| `bws run` re-parseia | Junta os argumentos numa string e passa a um shell; prompt com espaco vira erro de sintaxe do `sh`. `printf '%q '` em cada argumento e `--shell bash`. |

## Documentado contra observado

- Que o Remotion e gratis ate 3 funcionarios **e** documentado, em duas
  redacoes que nao coincidem. Que co-fundador conte ou nao, nao esta em lugar
  nenhum.
- Que `thinking = false` no ACE-Step nao descarrega o LM **nao** esta
  documentado; foi observado pelo OOM e resolvido pelos `use_cot_*`.
- As licencas dos modelos de imagem foram lidas nas paginas do Hugging Face,
  OpenModelDB e GitHub em 2026-09-21. Licenca muda; a skill traz a data.
- O segfault do `get_devices()` foi observado numa maquina (Core Ultra 9 com
  Arc integrada + RTX 4070); a causa (oneAPI/Level Zero) e inferida do ponto
  em que cai, nao confirmada com o time do Blender.

## Estado da medicao

**Nao ha run records.** Pela regra zero do [`bench/PROTOCOL.md`](../../bench/PROTOCOL.md),
alegacao de melhoria sem registro e marketing, entao esta versao nao faz
nenhuma. O que existe e comportamento verificado, nao eficacia medida:

- `comfy-run.py` exercitado contra um ComfyUI real nos cinco workflows; a
  mascara montada no grafo (`--rect`) produziu saida pixel-identica a mascara
  em PNG (`magick compare -metric AE` = 0).
- `vo-normalize.sh` exercitado em tres frases reais (Pocket TTS a -24,4 e
  -28,5 LUFS; ElevenLabs a -16,8): sem a passada corretiva o `loudnorm`
  entregou -17,3; com ela, -16,1, -16,2 e -16,0 pelo `ebur128`.
- `guard-vipsthumbnail.sh` exercitado com stdin simulado: casa `-o nome.png`,
  nao casa `-o ./nome.png` nem `-o /tmp/x.png`.
- `turntable.py` renderizou 120 frames de um glb real em CUDA no Blender 5.2.
- `references/glb-turntable.tsx` renderizou as duas composicoes (giro 900x900
  e dolly 1080x1920) com `--gl=angle`, com modelo desde o frame 0; mesmo `.glb`
  e mesma camera do `turntable.py`, 120 frames em ~7 s contra ~6 min do
  Blender. Com `--gl=swangle`, quadro vazio.
- SeedVR2 medido em 36 frames 540p para 1080p: 292 s, 7,8 GB de VRAM, e
  removido depois; a receita ficou na skill `retoque-comfyui`.
- Kinocut 1.15.1 pelo mesmo comando do `.mcp.json`: o servidor respondeu
  `tools/list` com 196 ferramentas; pela CLI, `info` leu 64,4 s em 1920x1080,
  `trim` cortou 15,000 s, arquivo inexistente voltou como erro estruturado, e
  `normalize-audio` levou uma voz de -28,6 a -16,5 LUFS (o `vo-normalize.sh`
  chega a -16,0..-16,2 no mesmo tipo de arquivo).

O que falta medir: se as skills mudam o resultado de um agente que nao as tem.
Isso pede arms pareados e nao foi feito.
