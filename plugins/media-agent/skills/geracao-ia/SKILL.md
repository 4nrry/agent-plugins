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
  ja esta no still.
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
