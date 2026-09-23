---
name: locucao
description: Gerar locucao (voice-over) para video com TTS local (Pocket TTS, Kokoro, Qwen3-TTS, Chatterbox) ou ElevenLabs, e deixar o audio pronto para montagem — uma frase por arquivo, -16 LUFS, duracoes num JSON que alimenta a legenda. Use quando a tarefa envolver narracao, dublagem, voice-over, TTS, pt-BR, ElevenLabs, LUFS, loudnorm, legenda sincronizada, ducking da trilha, ou quando a locucao "ficou baixa", "sumiu atras da musica" ou pronunciou uma sigla errado.
---

# Locucao para video

Tres coisas quebram em silencio: o volume, a pronuncia e a licenca. Nenhuma
levanta erro; todas aparecem so na entrega.

## 1. Uma frase por arquivo, e um JSON que manda em tudo

Gere cada frase como um arquivo (`s1.wav`, `s2.wav`, ...) e mantenha um JSON
com o que a legenda mostra, o que o TTS deve falar e quanto durou:

```json
[{"id": "s1", "text": "E cada laudo custa ate vinte mil reais.",
  "say":  "E cada laudo custa ate vinte mil reais.",
  "duration": 6.87, "start": 0.9}]
```

- `text` e a legenda. `say` e o que vai para o TTS. Sao campos diferentes
  porque sigla e nome proprio se escrevem de um jeito e se falam de outro:
  `CETESB` se le "Cetesbi", `SmartCompost` se le "Smart Compost". Numero por
  extenso no `say` evita "24h" virar "vinte e quatro agá".
- `duration` vem do arquivo gerado (`ffprobe`), nunca de estimativa. A legenda
  e a trilha com ducking derivam dele; regravar uma frase e trocar um numero.
- Legenda a partir desse JSON e deterministica e tem zero erro de transcricao.
  Whisper so entra para transcrever audio que nao foi voce quem gerou.

## 2. Volume: TTS local sai baixo e a trilha come

Pocket, Kokoro, Qwen3-TTS e Chatterbox entregam entre -24 e -30 LUFS. Uma
trilha a -20 por cima e a voz some, e ninguem ve erro porque o mix "toca".
Normalize **cada frase** a -16 LUFS (pico -1.5 dBTP) antes de montar, e o
video final de novo:

```bash
"${CLAUDE_PLUGIN_ROOT}/skills/locucao/scripts/vo-normalize.sh" -o vo-norm -j vo-durations.json vo/*.wav
ffmpeg -i final.raw.mp4 -c:v copy -af loudnorm=I=-16:TP=-1.5:LRA=11 -c:a aac -b:a 192k final.mp4
```

O script mede em duas passadas (`loudnorm` com `measured_*`) e depois confere:
voz tem crest factor alto, e o teto de true peak faz o `loudnorm` entregar 1 a
2 LU **abaixo** do alvo em frase curta — medido: -17,3 LUFS pedindo -16, tanto
em uma passada quanto em duas. A terceira passada aplica o ganho que faltou com
`alimiter` no mesmo teto; com ela as frases chegaram a -16,1..-16,4. Ducking da trilha sob a voz: 0.5 → 0.16
com rampa de ~0.35 s funcionou; menos que isso a musica compete, mais que isso
o corte fica audivel.

## 3. Qual TTS, e o que cada um esconde

| ferramenta | roda em | licenca | armadilha |
|---|---|---|---|
| Pocket TTS (Kyutai) | CPU, `uv tool install pocket-tts` | codigo MIT, pesos CC-BY-4.0 (creditar) | sem `--language portuguese_24l` sai em ingles com sotaque; pt-BR aceitavel, ingles muito bom |
| Kokoro-82M | CPU | Apache-2.0 | pip pina Python <3.13: `uv venv -p 3.12` |
| Qwen3-TTS 1.7B | GPU 8 GB | Apache-2.0 | pt soa de Portugal; `--instruct` nao corrige |
| Chatterbox Multilingual | GPU 8 GB, Python 3.11 | MIT | `perth` watermarker vem `None` em alguns builds: cair para o DummyWatermarker; pronuncia pt fraca |
| ElevenLabs | nuvem | ver abaixo | melhor pt-BR por margem, e onde a licenca pega |

ElevenLabs, o que a pagina de precos nao deixa obvio:

- **Free e nao comercial.** Video de empresa exige Starter ou acima.
- Voz da biblioteca (Voice Library) via API no Free devolve `paid_plan_required`.
- `output_format=mp3_44100_192` devolve 403 no Starter: 192 kbps e Creator+.
  Use `mp3_44100_128` e converta para wav se o pipeline pede.
- Modelo `eleven_multilingual_v2` para pt-BR; o `say` do JSON e o que vai no
  `text` da request.

Ouca as vozes antes de decidir: nesta colecao, quatro TTS locais foram
descartados de ouvido por quem fala a lingua, e a metrica de qualidade nao
substitui isso.

## 4. Voz de uma pessoa real

Nao gere voz sintetica falando como uma pessoa real que aparece no video (a
professora, o fundador), nem clone a voz dela a partir de audio publico, sem
que ela grave ou autorize. Texto na tela na primeira pessoa, com a foto dela,
e o que a propria pessoa ja publica no site e funciona: Reels e assistido sem
som na maior parte do tempo. Se ela quiser narracao, ela grava; o pipeline
desta skill (uma frase por arquivo, -16 LUFS, JSON de duracoes) serve igual.

## 5. Chaves

Chave de API vem do ambiente, nunca de arquivo no repositorio nem da linha de
comando (`ps` mostra). Um gerenciador de segredos com `run` (bws, 1Password,
sops) injeta so no processo filho. Atencao: `bws run` junta os argumentos numa
string e passa a um shell — prompt com espaco e aspas precisa ser re-citado
(`printf '%q '`) ou vira erro de sintaxe do `sh`.

## O que nao foi verificado

- Que -16 LUFS e o alvo certo para toda plataforma: e o que LinkedIn e
  Instagram aceitam sem re-normalizar de forma audivel nesta experiencia; nao
  ha medicao controlada.
- Qualidade de pt-BR dos TTS locais e julgamento de um ouvinte nativo em
  2026-09, com os pesos daquela data.
