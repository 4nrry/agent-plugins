---
name: agy
description: Especificos do backend agy (Antigravity CLI, Gemini) do plugin crew - flags do run, modelo padrao gemini-3.8-flash-high, escalada para gemini-4-argon-medium e depois claude-sonnet-5-5-medium, nunca Opus, preflight de quota, hooks em .agents/hooks.json e os comandos que o agy joga para segundo plano. Use quando for delegar uma fatia ou pedir review pelo agy.
---

# crew pelo agy

Antes de tudo, leia `${CLAUDE_PLUGIN_ROOT}/shared/delegate.md` se ainda nao leu
nesta sessao: quando delegar e quando nao, como escrever a task, o gate, como
ler o veredito, a revisao obrigatoria do diff contra a fonte da verdade, os
arquivos de segredo e a pergunta ao usuario antes do primeiro run. Aqui esta
so o que e do agy. O agy e o backend padrao (`"backend": "agy"`).

## O run

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew.py" delegate /caminho/TASK.json [--model slug] [--no-quota-probe]
```

O script roda `agy -p <prompt> --model <m> --output-format json --json-schema
<report> --print-timeout <timeout>s --dangerously-skip-permissions` na raiz do
repo. O skip-permissions e necessario (sem ele `run_command` e auto-negado
headless e o worker nao roda teste); os hooks sao o limite. Diga isso ao
usuario na primeira pergunta. O `--sandbox` do agy nao confinou escrita
nenhuma no lab: nao conte com ele.

## Modelo e escalada

- Comece no `gemini-3.8-flash-high` (padrao).
- Se o Flash nao der conta de uma fatia (gate vermelho ate o limite, ou diff
  que nao sobrevive a revisao), suba para `gemini-4-argon-medium`. O Argon
  tem quota semanal propria no plano Pro: nao gasta a dos Gemini Flash nem a
  dos Claude. `-high` so se o `-medium` tambem falhar.
- Se o Argon tambem nao der conta, `claude-sonnet-5-5-medium`.
- O Argon so passou por fumaca (n=1, fatia trivial; ver "Smoke tests" no README): nada
  diz ainda que ele resolve o que o Flash erra. Revise o diff igual.
- **Nunca Opus pelo agy.** Os modelos Claude do agy dividem uma quota semanal,
  e o Opus a esgota em poucas fatias.
- O modelo e validado contra `agy models` antes de rodar.

## Quota

O preflight le `agy -p /usage` (responde sem turno de modelo) e recusa, saida
2, se o grupo do modelo tiver menos que `min_quota` (padrao 0.05) restante,
dizendo quando renova. O grupo e achado pela linha do modelo (`flash`,
`argon`, `sonnet`, `oss`) no nome ou na descricao do grupo, e so pela familia
(`gemini`, `claude`) se nenhum grupo citar a linha: no agy 1.4.2 o Argon tem
grupo proprio ao lado de "Gemini Models", e no plano Pro as duas quotas sao
separadas. `--no-quota-probe` pula. Com a quota esgotada, o
`opencode` e a alternativa gratis (skill `crew:opencode`).

## Antes do primeiro run

- **Nenhum `.agents/hooks.json` no repo.** O agy le um arquivo de hooks por
  workspace; o script escreve o dele no comeco do run, remove no fim (tambem em
  SIGTERM/SIGHUP) e recusa se ja existir. Depois de um SIGKILL o proximo run
  recusa e diz qual arquivo remover.
- **Os hooks tem que carregar.** Sem `SessionStart` registrado o veredito falha
  com "hooks nao carregaram". A causa nunca foi reproduzida: os hooks
  dispararam headless ate em pastas fora de `trustedWorkspaces`. Hipoteses,
  nenhuma testada: `hooks.json` invalido, hooks desligados nesta versao,
  confianca no workspace. Diga isso ao usuario; nao edite `~/.gemini`.
- Testado no agy **1.3.4** e, por smoke tests n=1, no **1.4.2**; outra versao
  que nao a 1.4.2 vira aviso no veredito.

## O guard e o gate no agy

- `PreToolUse` com allowlist de ferramentas: so as de arquivo e o
  `run_command`; rede, subagente, workflow e MCP sao negados.
- O gate roda na ferramenta `finish` (a do `--json-schema`) e no `Stop`
  (`NO_TOOL_CALL` ou `TERMINAL_STEP_TYPE`), e nega o "terminei" enquanto
  falhar, ate `max_gate_attempts`.

## Comandos em segundo plano

O `run_command` do agy (1.3.4, e ainda na 1.4.2) manda comando longo (`nx run web:typecheck`) para
uma background task depois de ~4 s, **qualquer que seja** o
`WaitMsBeforeAsync`: reescrever esse argumento num hook nao funciona (o agy
aplicou a reescrita e mandou para segundo plano mesmo assim). Depois que o
worker para, o agy espera ate 30 min por essa task. O script vigia o run:
depois de o worker terminar com gate verde, espera 15 s e encerra os comandos
que o worker deixou rodando (so processos com a marca do run, descendentes do
agy, que nao sejam MCP servers nem os hooks do gate, nunca o proprio agy). O
que foi encerrado aparece em `agy.background_killed` e num aviso. Isso e
esperado; o gate que conta e o do hook, nao o comando do worker.

## Falhas que so o agy tem

| falha | por que existe |
|---|---|
| print timeout do agy | o agy sai 0 com saida parcial quando o tempo acaba |
| structured_output nulo | o agy devolve `SUCCESS` e exit 0 sem relatorio |
| `denied_actions` / auto-negada | acao recusada sai 0 |
| hooks nao carregaram | ver acima |

## Review

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew.py" review --diff HEAD~1 --prompt-file /scratchpad/pergunta.md
```

Roda com `--mode plan`, sem skip-permissions, escopo vazio e os mesmos guards
de caminho; confere que a arvore nao mudou. O modo plan tenta gravar um plano
em `~/.gemini/antigravity-cli/brain/`, e o guard nega (fora do repo).
