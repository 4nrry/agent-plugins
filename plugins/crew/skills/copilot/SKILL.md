---
name: copilot
description: Especificos do backend copilot (GitHub Copilot CLI) do plugin crew - plano Free so com --model auto, cada run pago em AI credits, worker sem shell e com o gate inteiro no agentStop, COPILOT_ALLOW_ALL so no processo do run, e o worker que declara checks que nao pode ter rodado. Use quando for delegar uma fatia ou pedir review pelo Copilot CLI.
---

# crew pelo Copilot CLI

Antes de tudo, leia `${CLAUDE_PLUGIN_ROOT}/shared/delegate.md` se ainda nao leu
nesta sessao: quando delegar e quando nao, como escrever a task, o gate, como
ler o veredito, a revisao obrigatoria do diff contra a fonte da verdade, os
arquivos de segredo e a pergunta ao usuario antes do primeiro run. Aqui esta
so o que e do Copilot CLI.

## Quando usar

Raramente, e sabendo que custa: no plano **Free** nao ha quota gratis, cada
run gasta **AI credits** (0,53 num delegate pequeno com uma volta de gate e
0,41 num review, n=1 cada). Serve para uma fatia em que se queira um modelo de
outra familia (o Auto serviu gpt-5.6-luna) e em que **o gate inteiro roda sem
o worker**: ele nao tem shell, entao nao roda teste, formatter nem git. O
enunciado tem que bastar sem executar nada. Requer o `copilot` no PATH e
logado; testado so no **1.0.96** (outra versao vira aviso).

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew.py" delegate /caminho/TASK.json --backend copilot
```

## Antes do primeiro run

Pergunte ao usuario: o codigo vai para a GitHub e cada run consome creditos.
Diga tambem que o run seta `COPILOT_ALLOW_ALL=true` so no processo do copilot,
porque e a unica forma de os hooks do repo carregarem, e que isso carrega
tambem skills, plugins, MCP servers e hooks do proprio repo (o veredito avisa
os hooks que encontrar em `.github/hooks/`). Nao use num checkout em que voce
nao confie.

## Modelo e creditos

- So `auto` (validado; outro e recusado). Num plano pago,
  `"copilot_model_override": true` libera outro slug, caminho **nunca
  testado**: diga isso ao usuario se for usar.
- `max_ai_credits`: padrao e minimo 30 (o CLI recusa menos). E freio contra um
  run que dispare, nao orcamento: um run normal gasta menos de 1.
- `copilot.usage` no veredito traz `ai_credits`, `premium_requests` e
  `served_models`: **reporte os creditos gastos ao usuario.**

## Sem shell

- O run passa `--excluded-tools bash task`. **Nunca exclua `bash` sem
  `task`**: excluir so o `bash` levou a 2826 chamadas de subagente `task` e
  ~5,5 creditos no lab. O script sempre exclui os dois.
- Chamada de shell ou de `task` no stream de eventos reprova o run.
- O gate inteiro (escopo, `forbid`, `format`, `checks`) roda do nosso lado no
  `agentStop`, que devolve `block` com a saida do gate ate
  `max_gate_attempts` (**no maximo 8**: o CLI ignora o hook depois de 8
  bloqueios seguidos). Diga no `prompt` o que o worker precisa saber sobre os
  comandos, porque ele nao pode roda-los para ver.

## O worker declara checks que nao rodou

`report.checks_run` e ainda menos confiavel aqui: no smoke o worker escreveu
`python3 -m unittest ... PASS` para um teste que ele, sem shell, nao tinha
como rodar. So o gate conta.

## Task

| campo | o que e |
|---|---|
| `max_gate_attempts` | no maximo 8 |
| `max_ai_credits` | padrao e minimo 30 |
| `copilot_model_override` | `true` para aceitar modelo diferente de `auto` (nao testado) |
| `scope` | nao pode cobrir `.github/hooks/`, `.github/copilot/settings*.json` nem `.claude/settings*.json`: de la o copilot carrega hooks |

O run escreve `.github/hooks/crew-<run>.json` e o remove no fim. Se um run
morrer por SIGKILL, o proximo recusa e diz qual arquivo remover (tambem os
`agy-worker-*.json` de antes da 0.4.0); enquanto ele existir, um `copilot`
com `COPILOT_ALLOW_ALL=true` nesta pasta carrega os hooks de um run morto.

## Falhas que so o copilot tem

| falha | por que existe |
|---|---|
| hooks nao carregaram (nenhum evento de hook) | sem `COPILOT_ALLOW_ALL=true` exato os hooks somem em silencio (lab) |
| chamada de shell observada / subagente observado | `bash` e `task` deviam estar excluidos; se apareceram, a exclusao falhou |
| nenhum evento `result`, ou `exitCode` diferente de 0 | o run foi cortado; o exit 0 do processo nao prova nada |
| arquivo de hooks do run mudou | o guard pode ter sido trocado durante o run |

## Review

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew.py" review --backend copilot --diff HEAD~1 --prompt-file /scratchpad/pergunta.md
```

Sem shell nem `apply_patch` (`--excluded-tools bash task apply_patch`), com o
hook negando toda escrita. Reporte os creditos.
