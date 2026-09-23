---
name: edicao-kinocut
description: Editar video ja renderizado por agente com o Kinocut — cortar, juntar, redimensionar, normalizar audio, queimar legenda, extrair frame, checar qualidade — pelo MCP que este plugin registra ou pela CLI `kino`, com resposta em JSON e erro estruturado em vez de stderr do ffmpeg. Use quando a tarefa pedir corte de teaser, versao curta, trim, merge, concat, resize, crop, legenda queimada, normalizar audio de um mp4, extrair frame, thumbnail, ou "passar o video por um ffmpeg" depois do render, e quando a escolha for entre Kinocut, ffmpeg na mao e re-renderizar no Remotion.
---

# Edicao de video pronto com o Kinocut

O Kinocut (KyaniteLabs, Apache-2.0, local, sem conta nem chave) embrulha o
ffmpeg em operacoes tipadas para agente: valida a entrada antes de rodar e
devolve JSON com `success` e o caminho da saida. O ganho real sobre ffmpeg na
mao e o erro: arquivo inexistente vira
`{"success": false, "error": {"code": "invalid_input", "suggested_action": ...}}`
em vez de trinta linhas de stderr para o agente interpretar.

Este plugin registra o servidor MCP `kinocut` (via `uvx`, fixado em 1.15.1).
As ferramentas aparecem numa sessao nova. A mesma coisa pela CLI:

```bash
uvx --from kinocut==1.15.1 kino --format json info video.mp4
uvx --from kinocut==1.15.1 kino --format json trim video.mp4 -s 0 -d 15 -o teaser.mp4
uvx --from kinocut==1.15.1 kino --format json normalize-audio video.mp4 -l -16 -o norm.mp4
uvx --from kinocut==1.15.1 kino doctor
```

Sempre `--format json` na CLI: sem ele a saida e uma tabela para humano.

## Quando usar qual

| tarefa | use | por que |
|---|---|---|
| corte, junta, resize, crop, frame, legenda .srt queimada num mp4 pronto | Kinocut | operacao validada, resposta estruturada |
| mudar texto, cena, ordem, formato do filme | re-renderizar (skill `video-remotion`) | editar o fonte custa menos que remendar o mp4 |
| normalizar cada frase de locucao antes da montagem | `vo-normalize.sh` (skill `locucao`) | chega a -16,0..-16,2; o `normalize-audio` do Kinocut chegou a -16,5 |
| normalizar o mp4 final | Kinocut ou `ffmpeg loudnorm` | meio LU nao se ouve no produto final |
| filtro que o Kinocut nao tem | ffmpeg na mao | e o que ele chama por baixo |

## O que o `doctor` nao conta

- Sao mais de 190 comandos, e parte e casca: `sound-qa-loudness` na 1.15.1 nao
  aceita argumento nenhum e so imprime o uso. Antes de montar um fluxo em cima
  de um comando, rode-o uma vez num arquivo real e confira `success` e o
  arquivo de saida.
- Os comandos `video-ai-*`, `hyperframes-*` e varios `sound-*` dependem de
  extras opcionais (Whisper, Demucs, Real-ESRGAN, torch, um pacote Node). O
  `doctor` lista o que falta; nao instale para ter "tudo verde" — a stack deste
  plugin ja cobre transcricao, trilha e upscale com ferramentas medidas.
- Precisa de `uv` no PATH e de `ffmpeg`/`ffprobe`. Sem `uv`, o servidor MCP
  nao sobe e o erro aparece so na lista de MCPs, nao na conversa.

## O que nao foi verificado

- O conjunto de ferramentas expostas pelo MCP contra o da CLI: o teste foi pela
  CLI (`info`, `trim`, `normalize-audio`, `doctor` e o erro de entrada), mais o
  servidor registrado e conectado.
- Comportamento em arquivos com varias faixas de audio ou VFR.
