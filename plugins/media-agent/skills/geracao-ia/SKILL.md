---
name: geracao-ia
description: Usar IA generativa como ferramenta de design numa peca de marketing — explorar direcoes de cena com stills rapidos, escolher o enquadramento, animar o still escolhido em video e encaixar o plano no video ou no carrossel sem que ele destoe da marca. Cobre qual ferramenta usar para cada tarefa (Grok Build para explorar, Antigravity `agy` para o still final, Veo para o plano em 1080p, Grok para clipe de fundo em 480p), como escrever o prompt de cada uma, o fluxo still→video que controla a composicao, a folha de contato para escolher, e o que nunca gerar (o produto, texto, pessoas reais). Use quando a tarefa pedir imagem gerada, cena, b-roll gerado, animar uma foto, plano aereo, ambientacao, moodboard, storyboard, Veo, Nano Banana, Grok Imagine, agy, Grok Build, ou "gera uma imagem/video de..." para uma peca.
---

# IA generativa como ferramenta de design

Gerar e o passo barato; escolher e encaixar e o que faz a peca. Esta skill e o
processo: explorar varias direcoes rapido, escolher na folha de contato,
produzir o still final, animar a partir dele e encaixar no video com a mesma
tipografia, cor e ritmo do resto.

Pre-requisito: `grok`, `agy` e `GEMINI_API_KEY` funcionando. Se algum falhar,
a montagem esta em `references/montagem.md`.

## Qual ferramenta para qual tarefa

| tarefa | use | medido | por que |
|---|---|---|---|
| explorar 3 a 6 direcoes de cena | `grok-imagem.sh` | ~40 a 65 s, 1280x720 | rapido; tom mais sobrio e documental |
| still final, carrossel, capa | `agy-imagem.sh` | 100 a 175 s, 1376x768 | mais rico em detalhe e luz; tambem mais "cara de IA" |
| plano de video que aparece inteiro na tela | `veo.py --image still.png` | ~110 s, 8 s em 1080p | mantem a composicao do still e move a camera de verdade |
| fundo com desfoque, card pequeno, fundo de Reels | `grok-video.sh --image` | ~85 s, 6 s em 480p | sai da assinatura; movimento sutil, resolucao baixa |

Nao amplie o clipe do Grok para usar em 1080p: DAT2 leva ~9,5 s por quadro
(23 min para 6 s). Se o plano precisa de 1080p, e Veo.

## Porte do modelo: rapido, medio, grande

Escolha pelo uso do plano na peca, nao pelo ranking. **Medido** = rodou aqui, uma vez (n=1), em
13/10/2026, a partir do mesmo still de leiras ao amanhecer; **so lista** = o
modelo aparece na `models.list` da chave, mas nada foi gerado com ele; **so
docs** = so fonte externa.
Precos da pagina de precos do Gemini API e da xAI em 13/10/2026; ranking da
Artificial Analysis no mesmo dia (a pagina nao data o snapshot).

**Imagem**

| porte | quando | use | estado |
|---|---|---|---|
| rapido | explorar direcoes, folha de contato, descartavel | `grok-imagem.sh` (assinatura) | medido |
| medio | still final de carrossel, capa, fundo de video | `agy-imagem.sh` (assinatura) | medido; o modelo por tras do `generate_image` do agy nao foi identificado |
| medio, pela API | quando a assinatura do agy esgotar, ou para lote | `nano.py gemini-nano-banana-2.1` (US$ 0,034 por imagem 1K; #4 em texto→imagem, empatado com o Grok Image 2.0) | medido: 12 s, 1376x768, still forte, luz e neblina coerentes |
| grande | edicao fina de um still existente, detalhe que o medio erra | `nano.py gemini-3-pro-image --image still.png` | medido: 17 s; manteve composicao e enquadramento exatos, mas exagerou o que foi pedido ("vapor" saiu como labareda): peca a mudanca com moderacao |

**Video**

| porte | quando | use | estado |
|---|---|---|---|
| rapido | fundo desfocado, card pequeno, Reels com tipografia por cima | `grok-video.sh --image` (480p, padrao da API) ou `--res 720p` quando o clipe fica visivel | medido: 480p como antes; com `--res 720p`, 1280x704, 6 s, 86 s |
| rascunho barato | testar movimento de camera antes de gastar no definitivo; tambem plano final em 720p | `veo.py --model veo-3.1-lite-generate-preview --res 720p --negative ""` (US$ 0,05/s) | medido: 44 s, 8 s em 720p com audio; manteve as leiras continuas. **Recusa `negativePrompt`** (HTTP 400): passe `--negative ""` |
| medio | plano que aparece inteiro na tela, 1080p | `veo.py` (padrao `veo-3.1-fast-generate-preview`) | medido (~110 s, 8 s em 1080p) |
| grande | plano principal, close, onde artefato aparece | `veo.py --model veo-3.1-generate-preview` (US$ 0,40/s em 1080p) | medido: 107 s, 8 s em 1080p com audio. **1080p so com `--seconds 8`** (4 s recusa). Neste still avancou mais que o pedido e quebrou as leiras em montes separados: pior fidelidade que o Lite, n=1 |

No unico teste, o Veo mais caro nao foi o melhor: o Lite seguiu o still, o
Standard reinventou a geometria. Antes de pagar o Standard num plano, rode o
Lite com o mesmo prompt e so suba se o Lite falhar no que importa (detalhe em
1080p, artefato no meio do clipe).

Candidato que o `veo.py` ainda nao chama: `gemini-omni-1.1-flash` aparece na
lista da chave e fica acima do Veo 3.1 no ranking de video com audio (#7-8,
contra o Veo fora do top 10), a ~US$ 0,10/s em 720p. A API e outra (por token,
nao `predictLongRunning`), e imagem→video com ele nao foi testado: nao troque o
Veo por ele numa peca antes de um teste.

O Grok Video 1.5 gera 1080p nativo de texto ou imagem, mas fica em 720p quando
segue um video de referencia, e o 1.5-lite so chega a 1080p por upscale (so
docs). Na imagem→video o `aspect_ratio` e ignorado: sai na proporcao do still.

## O fluxo que controla a composicao

Video gerado direto do texto escolhe o enquadramento sozinho: pedindo "plano
aereo ao longo das leiras", o Veo entregou camera rente ao chao, sem leiras
longas. Partindo de um still, ele respeitou a composicao e so animou a camera.
Entao:

1. **Explorar**: 3 a 6 stills com `grok-imagem.sh`, variando uma coisa por vez
   (altura da camera, hora do dia, quanto do horizonte aparece).
2. **Escolher**: `folha.sh folha.jpg *.png` e olhar lado a lado. Escolha pelo
   que serve a peca (espaco para o titulo, leitura em tela pequena), nao pela
   imagem mais bonita sozinha.
3. **Still final** com `agy-imagem.sh`, repetindo o prompt da direcao escolhida.
4. **Animar** o still com `veo.py --image` (1080p) ou `grok-video.sh --image` (fundo).
5. **Conferir** com `folha.sh` (o video entra como 4 quadros) antes de por na timeline.

```bash
S="${CLAUDE_PLUGIN_ROOT}/skills/geracao-ia/scripts"
for alt in "drone a media altura" "drone alto, quase de cima" "camera baixa entre as leiras"; do
  "$S/grok-imagem.sh" "leiras de compostagem ao amanhecer, $alt, neblina leve, sem pessoas, sem texto, 16:9" "dir-${alt// /-}.png"
done
"$S/folha.sh" direcoes.jpg dir-*.png
"$S/agy-imagem.sh" "<prompt da direcao escolhida>" still.png
python3 "$S/veo.py" "slow drone push forward along the windrows, mist drifting, no text" -o plano.mp4 --image still.png
"$S/folha.sh" conferencia.jpg still.png plano.mp4
```

As chamadas foram testadas uma de cada vez; paralelismo e limite de cota em
volume nao foram medidos.

## Escrevendo o prompt

- **Cena, nao conceito.** "Leiras de compostagem ao amanhecer, drone a media
  altura, neblina leve" funciona; "sustentabilidade e tecnologia" devolve
  clichê.
- **Sempre "sem pessoas, sem texto"** no still. Texto gerado sai com letra
  inventada; o titulo entra depois, na tipografia da marca. Pessoa gerada numa
  peca de empresa passa por depoimento ou funcionario que nao existe.
- **Proporcao no prompt** do still ("16:9", "9:16"); o Veo segue a do still e
  aceita `--aspect 9:16` para Reels.
- **Veo em ingles e com verbo de camera**: "slow push forward", "gentle orbit
  left", "static shot, mist drifting". Descreva o movimento, nao a cena: a cena
  ja esta no still. **Um** movimento de camera por plano, com o enquadramento
  ("medium shot"); dois movimentos concorrentes saem tremidos (guia de prompt
  da DeepMind para o Veo).
- **Som do Veo numa linha propria**, "Audio: vento leve, passaros ao longe".
  Fala com dois-pontos depois de quem fala, nao entre aspas: aspas podem virar
  texto na tela (so docs, nao testado aqui).
- **Grok sem negativo no still**: a API de imagem nao tem campo de negativo;
  descreva o material que quer em vez de listar o que evitar.
- **Uma mudanca por rodada.** Mudou a hora e a altura juntas, nao sabe qual
  melhorou.

## O que nunca gerar

- **O produto.** O gerador inventa um aparelho parecido, com outra cor, outro
  logo e outros conectores. O produto entra por foto real, turntable do glb
  (skill `turntable-blender`) ou Three.js. Gere o ambiente e componha o
  produto por cima.
- **Logo, dado, numero, certificado.** Tudo que e afirmacao factual vem do
  material real.
- **Pessoa real ou parecida com alguem.** Ver a regra de voz na skill `locucao`.

## Encaixe na peca

- O plano gerado entra **curto** (2 a 4 s) e **como apoio**: ambientacao antes
  ou depois de um plano real, nunca no lugar da prova (o produto, o painel, o
  laudo).
- Passe o mesmo tratamento de cor no gerado e no real, ou eles se separam a
  olho. No Remotion, o caminho mais curto e o mesmo `filter` de CSS no
  `<OffthreadVideo>` dos dois (nao medido contra gradacao de verdade).
- O titulo vai por cima, na tipografia da marca, na area que o still deixou
  livre: e por isso que se escolhe o still pensando no layout.
- Grok com fundo desfocado (`filter: blur(6px) brightness(.6)`) esconde os 480p
  e serve de fundo de Reels com tipografia por cima.

## Antes de publicar

- O Instagram le a marca invisivel (SynthID, C2PA) e mostra "AI info" no post.
  Tirar marca visivel nao esconde que e IA, e no Grok remover viola a politica
  de uso.
- Assista ao clipe inteiro: IA erra no meio do clipe (objeto que some, maquina
  que atravessa a leira), nao no primeiro quadro.

## O que nao foi verificado

- Custo real de um clipe de Veo contra os creditos: o Cloud leva horas para
  mostrar o consumo.
- Cota das assinaturas para geracao em volume (dezenas de imagens por dia).
- Consistencia de uma mesma cena em varios stills: cada chamada reinventa
  detalhes; para uma serie, gere um still e derive variacoes por corte e
  movimento, nao por nova geracao.
