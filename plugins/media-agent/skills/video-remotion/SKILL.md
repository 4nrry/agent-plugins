---
name: video-remotion
description: Montar um video institucional ou de marketing como codigo — Remotion (React) ou HTML com timeline deterministica capturada por Chrome headless e ffmpeg — com legenda derivada do JSON da locucao, b-roll, trilha com ducking, e o mesmo filme em 16:9, 1:1, 9:16 e 4:5 mais carrossel de stills. Use quando a tarefa pedir video de marketing, institucional, Remotion, motion graphics em React, animacao por frame, legenda embutida, formatos para LinkedIn, Instagram, Reels, carrossel, ou quando alguem perguntar se pode usar o Remotion numa empresa.
---

# Video como codigo: Remotion ou HTML + Chrome + ffmpeg

Video de marketing feito em codigo tem uma vantagem que nenhum editor da:
mudar uma frase da locucao e re-renderizar, e o mesmo fonte sair em quatro
formatos. O custo e um conjunto de armadilhas que nao aparecem no preview.

## Antes de escolher o Remotion: a licenca

O Remotion e gratis para pessoa fisica e para **empresa com ate 3
funcionarios**; acima disso e licenca paga por seat. A pagina de FAQ fala em
"time de ate 3 pessoas", o LICENSE.md fala em funcionarios; co-fundador sem
vinculo e zona cinzenta que **o usuario decide**, nao voce. Diga a regra, deixe
a decisao com quem assina.

Sem Remotion o mesmo resultado sai de um `comp.html` com uma funcao `seek(t)`
que posiciona tudo no tempo `t`, Playwright capturando um PNG por frame em
varias abas, e `ffmpeg -f image2pipe` codificando. E deterministico e sem
licenca; o que perde e o preview interativo, o `<Audio>` com ducking (vira
`amix`/`adelay` no ffmpeg) e o b-roll em `<video>`, que o Chrome headless nao
avanca frame a frame de forma confiavel — extraia os frames do clipe em PNG
antes e troque a imagem por frame.

## Armadilhas do Remotion, cada uma custou uma sessao

- **`TransitionSeries` recusa Fragment como filho.** Montar as cenas com
  `<>...</>` dentro de um `.map` da erro obscuro; use `flatMap` devolvendo
  `[<Transition/>, <Sequence/>]`.
- **B-roll e `OffthreadVideo`**, nao `<Video>`: o segundo decodifica no Chrome
  e derruba frames na renderizacao paralela.
- **Grafico com animacao propria (ECharts, Chart.js) nao sabe que existe frame.**
  Ou desliga a animacao e desenha o estado em `t`, ou `delayRender` ate a
  animacao terminar (ECharts precisou de ~1,5 s) — e ai cada frame paga isso.
  Canvas desenhado a mao a partir de `useCurrentFrame` e mais simples e
  deterministico.
- **`dangerouslySetInnerHTML` por frame esvazia a cena** em renderizacao com
  varias abas: o React reaplica o HTML e solta os nos que o timeline segurava.
  Se for hibrido, defina `innerHTML` uma vez no mount. Melhor: portar para
  componentes.
- **Legenda vem do JSON da locucao** (`id`, `text`, `duration`, `start`), nao
  de transcricao. Uma cena declara `vo: {id, at}`, o filme calcula o inicio
  absoluto descontando a sobreposicao das transicoes, e a mesma tabela alimenta
  o `<Audio>` da frase, a faixa de legenda e o ducking da trilha. Regravar uma
  frase muda um `duration`.
- **Loudness**: o `--crf 17` do render nao normaliza audio. Passe `loudnorm`
  a -16 LUFS no MP4 final (`-c:v copy`), alem de cada frase antes (ver a skill
  `locucao`).
- **Rspack (`Config.setRspack(true)`)** corta o bundling em 3x, e o alias `@`
  de um pacote de UI vizinho com Tailwind v4 precisa do `theme.css` importado
  no root e de `npm ci` naquele pacote, senao os componentes vem sem estilo e
  sem erro.

## Transicao cruzada com texto

`fade()` do `TransitionSeries` sobrepoe as duas cenas por T frames; se as duas
tem titulo, aparecem dois textos um sobre o outro no meio da transicao. Visto
num Reels so de tipografia. Saida: envolver o conteudo de cada cena (menos a
primeira) num `<Sequence from={T} layout="none">`, para a cena nova entrar
depois que a anterior sumiu sobre o fundo.

## Modelo 3D dentro do video: Three.js ou Blender

`@remotion/three` poe uma cena Three.js (React Three Fiber) dentro da
composicao, dirigida por `useCurrentFrame`. Medido com o mesmo `.glb` e a mesma
camera do `turntable.py` (skill `turntable-blender`), RTX 4070 Laptop:

| | Blender Cycles | Three.js no Remotion |
|---|---|---|
| giro de 120 frames a 900 px | ~6 min | ~7 s |
| plano de 5 s 1080x1920 com a camera em movimento | animar no Blender e renderizar de novo | ~8 s, e o movimento e codigo |
| visual | cor saturada, sombra suave, reflexo | cor mais palida, sombra chapada, cara de tempo real |

Use Blender para o heroi do produto e o giro que fica na tela; use Three.js
para plano de apoio com camera que acompanha a legenda ("quatro entradas para
sensores" enquanto a camera chega nos prensa-cabos) e para o mesmo movimento
reenquadrado em 16:9, 9:16 e 4:5. Componente verificado, com giro e dolly:
`references/glb-turntable.tsx`. As quatro coisas que deram quadro vazio ou
cor errada antes de funcionar:

- **`--gl=swangle` desenha vazio**, sem erro nenhum. Use `--gl=angle` ou
  `--gl=vulkan` (os dois funcionaram). No Studio tudo aparece, porque o
  navegador tem GPU: o erro so existe no render.
- **GLB carregado dentro do `ThreeCanvas`** nao segura o `delayRender`: o
  reconciler do R3F nao e o do Remotion. Carregue fora, passe o objeto como
  prop, e so chame `continueRender` depois de `advance()` do R3F com o modelo
  na cena. Liberar no callback do loader deu frame 0 vazio; liberar num
  `useFrame` deu timeout de 28 s em render com varias abas.
- **Luz dentro do grupo que gira** gira junto e lava a cor das faces que se
  afastam da key. O modelo gira, a luz fica.
- **`near`/`far` fixos** cortam o modelo quando a unidade do GLB nao e a que
  voce supoe; calcule a partir do bounding box.

## Formatos a partir de um fonte

- Um `Film` recebe `fmt = fmtOf(w, h)` e as cenas leem `fmt.portrait`,
  `fmt.y(px)` (escala alturas por `h/1920`) e `fmt.f(px)` (fontes por
  `sqrt(h/1920)`). 16:9 e 9:16 saem do mesmo componente.
- 1:1 para LinkedIn: o 16:9 escalado a 0.5625 com barras da cor da marca, nao
  um layout novo.
- 4:5 (feed do Instagram) precisa de empilhamento: o que era lado a lado vira
  coluna; sem isso o titulo cobre a legenda.
- Reels 9:16: a interface do Instagram cobre o topo e sobretudo a base.
  Texto dentro de 250 px do topo e 420 px da base, em 1080x1920, nao ficou
  embaixo de nada no teste; e margem pratica, nao numero oficial.
- Carrossel: uma composicao cujo frame `i` e o slide `i` congelado
  (`Sequence` com `from` negativo para ir ao estado final), renderizada com
  `remotion still --frame i`; `magick` junta em PDF para o LinkedIn.

## Antes de entregar

Contact sheet de 9 stills por formato (`remotion still` em 3x3 com `magick
montage`) pega sobreposicao e corte de texto que o preview a 50% esconde.
`ffprobe` confere fps, duracao e resolucao; `ebur128` confere os -16 LUFS.

## O que nao foi verificado

- Three.js em GPU AMD/Intel ou sem GPU: o teste foi so NVIDIA com `angle`
  e `vulkan`.
- Render distribuido (Lambda) e o comportamento de `OffthreadVideo` la.
- Que a interpretacao de "funcionario" do Remotion cobre co-fundador sem
  vinculo; a skill apenas relata as duas redacoes.
