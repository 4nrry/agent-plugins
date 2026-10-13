---
name: elevenlabs
description: Usar a ElevenLabs alem da locucao numa peca de video — efeito sonoro de transicao e de interface, trilha com duracao exata, limpar a voz de uma gravacao real feita no celular, transcrever audio real com tempo por palavra para legenda, dublar o video em outro idioma, criar a voz da marca, e o canvas ElevenCreative (MCP) para imagem, video, upscale e trilha a partir do video. Diz quando usar a API REST (arquivo local entra e sai) e quando usar o MCP, quanto cada coisa custa em creditos do plano, e o que a licenca do Starter cobre. Use quando a tarefa pedir SFX, whoosh, som de clique, trilha, musica sob medida, limpar audio, tirar ruido, voice isolator, transcrever, legenda de video gravado, dublagem, versao em ingles ou espanhol, voz da marca, voice design, ElevenCreative, ou quando alguem disser que esta usando pouco a ElevenLabs.
---

# ElevenLabs alem da locucao

A locucao esta na skill `locucao`. Esta cobre o resto do plano, pensando no que
entra numa peca de video: som, trilha, limpeza de gravacao real, legenda,
outro idioma.

## Qual caminho

| | API REST (`scripts/eleven.py`) | MCP ElevenCreative (`creative_*`) |
|---|---|---|
| arquivo local na entrada | sim: o script envia | **nao sozinho**: o upload abre um seletor que o usuario precisa usar |
| saida | arquivo no disco | URL assinada que **expira em 2 h**; baixe na hora |
| o que oferece | SFX, musica, isolamento de voz, transcricao, dublagem, TTS | tudo isso mais modelos de imagem e video de terceiros, upscale Topaz, trilha a partir do video, efeitos de audio, brand kit, fluxos encadeados |
| bom para | etapas do pipeline local, em lote, sem humano | gerar a partir de texto, encadear nos, e quando o usuario vai mexer no canvas depois |

Regra pratica: se a entrada e um arquivo da maquina (gravacao, video renderizado),
REST. Se tudo nasce de prompt ou o usuario quer continuar no canvas, MCP.

## Custo em creditos (Starter, ~40 mil por mes)

Confira o saldo com `eleven.py credits` antes de lotes grandes. O contador da
API atrasa alguns minutos depois do uso.

| tarefa | custo observado | nota |
|---|---|---|
| SFX de 2 s | ~17 creditos | o `estimate_only` do MCP disse 50 |
| musica, sem duracao no prompt | ~1.500 (estimativa) | defina a duracao; 15 s pela REST passou sem custo visivel no contador na hora |
| imagem Seedream 5 Pro, 1 variacao | ~818 (estimativa) | o MCP gera 4 por padrao: 4x o custo |
| video Veo 3.1 Fast | ~7.272 (estimativa) | ~18% do mes num clipe; use a API do Gemini (skill `geracao-ia`) |
| todos os testes desta skill juntos (2 SFX, 1 musica de 15 s, 2 isolamentos, 1 transcricao) | ~290 | medido pela diferenca do saldo |

- `estimate_only` no MCP nao cobra, mas **cria um fluxo vazio no canvas** a cada
  chamada. Estime uma vez por tipo de tarefa, nao por variacao.
- **Nunca repita uma chamada do MCP para "tentar de novo"**: cada chamada e uma
  geracao nova e cobra de novo. Leia o status da que ja esta rodando.

## Usos que pagam o plano

**SFX de transicao e interface.** Mais rapido que garimpar no Freesound e ja
licenciado pelo plano. Peca curto e concreto: "soft cinematic whoosh
transition, airy", "soft click pop for UI element appearing". `--seconds`
fixa a duracao (0,5 a 30 s), `--loop` faz ambiencia que repete sem emenda.
Normalize junto com a trilha (skill `locucao`).

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/elevenlabs/scripts/eleven.py" sfx "soft whoosh transition" -o whoosh.mp3 --seconds 1.5
```

**Trilha com duracao exata.** `music --seconds 40` entrega exatamente a duracao
do filme, sem loop nem corte: o ACE-Step local tende a degradar no fim e pede
crossfade. A licenca comercial da musica comeca no Starter, mas os planos
self-serve excluem filme, TV e jogos; video de marketing e redes sociais estao
dentro ([precos](https://elevenlabs.io/pricing)). Trilha a partir do proprio
video (o modelo le o ritmo dos cortes) so existe no MCP, no no `video-to-music`.

**Limpar gravacao real.** Depoimento ou fala gravada no celular, com ruido de
rua ou ventilador: `isolate gravacao.wav -o limpa.mp3`. No teste, uma frase com
ruido marrom forte ficou sem pausas detectaveis (o ruido preenchia tudo); depois
do isolamento, as pausas voltaram. E o passo que torna gravacao de celular
utilizavel num video de marca.

**Legenda de audio real.** `stt audio -o x.json --lang por` devolve tempo por
palavra e o script imprime as frases com inicio e fim. Use para material que
voce nao gerou (depoimento, entrevista). Para locucao gerada, a legenda vem do
JSON da locucao, que nao erra. Atencao: a transcricao normaliza numero e moeda
("vinte mil reais" virou "R$ 20 mil") e pode engolir uma conjuncao no comeco da
frase; revise antes de queimar na tela.

**Outro idioma.** Dublagem (`dubbing-video` no MCP, `/v1/dubbing` na REST)
refaz a fala no idioma pedido mantendo a voz. Para versao institucional,
melhor ainda: traduzir o JSON da locucao e gerar o TTS no idioma, que mantem a
legenda exata. Dublagem vale para video com fala real que nao da para regravar.

**Voz da marca.** Voice Design cria uma voz a partir de descricao ("feminina,
calma, tecnica, sotaque paulistano neutro") em vez de escolher da biblioteca, e
fica propria da conta. Nao use para imitar alguem real (regra na skill `locucao`).

## No canvas (MCP), o que vale a pena

- **Brand kit a partir do site**: `creative_create_brand_kit_from_website` le
  logo, cores, tipografia e tom do site e deixa como referencia para as
  geracoes do canvas. Faca uma vez por marca.
- **Topaz upscale** de imagem e video: alternativa ao DAT2 local para o clipe de
  480p do Grok. Custo nao medido; estime antes.
- **Efeitos de audio** (telefone, radio, sala, distancia, ruido de fundo): o
  proprio MCP diz que rodar e gratis e leva segundos. Sempre como ultimo passo,
  depois de isolamento, troca de voz ou dublagem.
- Imagem e video de terceiros (Seedream, FLUX, Kling, Veo): funcionam, mas
  custam creditos do plano que rendem pouco; o still e o video da skill
  `geracao-ia` saem das assinaturas.

## O que nao foi verificado

- Custo real da musica e do isolamento por minuto: o contador nao mostrou o
  gasto separado na hora; o total dos testes foi medido.
- Licenca dos efeitos sonoros: as fontes consultadas so falam de musica. O
  plano pago da licenca comercial ao que e gerado nele, mas confira os termos
  para SFX.
- Dublagem e Voice Design nao foram rodados nesta versao.
