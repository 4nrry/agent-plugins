# crew

Tres CLIs de agente como workers baratos **sem brigar com o harness do
Claude**: o Claude planeja, escreve a task, define escopo e gate e revisa o
diff; o worker executa headless, uma fatia por vez, sob guard rails que existem
so durante o run. Ate a 0.3.0 este plugin se chamava `agy-worker` (ver
[Changelog](#changelog)).

```
/plugin install crew@4nrry
```

| backend | CLI | quando |
|---|---|---|
| `agy` (padrao) | Antigravity CLI, Gemini | primario |
| `opencode` | opencode, modelos gratis do Zen | quota do agy acabou, ou capacidade extra; guard do shell mais fraco |
| `copilot` | GitHub Copilot CLI, plano Free | outra familia de modelo; sem shell, pago em AI credits |

Requer `git`, `python3` (so stdlib), Linux (`/proc`, para achar os processos
do run) e o CLI do backend autenticado. So foi exercitado no agy **1.3.4** e
**1.4.2** (este so por smoke tests n=1, abaixo), no opencode **1.19.0** e no
copilot **1.0.96**; com outra versao (no agy, qualquer uma que nao a 1.4.2) o
veredito traz um aviso, porque decisao de hook, a ferramenta `finish`, os motivos de Stop e o
formato do `/usage` sao comportamento observado, nao contrato. Os hooks que o
run instala sao **do CLI do worker** (no agy, `.agents/hooks.json`, escrito no
comeco do run e removido no fim, inclusive em SIGTERM e SIGHUP; depois de um
SIGKILL o proximo run recusa e diz qual arquivo remover). Do Claude Code ha um
hook so, o de injecao descrito abaixo.

**O codigo sai da maquina.** Delegar ou pedir review manda o prompt, os
arquivos que o worker ler e o diff para o provedor do backend (Google, o
provedor do modelo do Zen, ou GitHub), e gasta a quota do agy ou os creditos
do Copilot. O documento comum manda o Claude perguntar antes do primeiro run na
sessao.

## Componentes

| componente | o que faz |
|---|---|
| `scripts/crew.py` | `delegate`, `review`, `gate`, os handlers de hook do agy, o guard e o loop do opencode, os hooks do Copilot, o vigia de processos em segundo plano, e `--self-test`. Um arquivo |
| `shared/delegate.md` | a parte comum: quando delegar e quando nao, como escrever a task, gate, como ler o veredito, a revisao do diff contra a fonte da verdade, arquivos de segredo, a pergunta antes do primeiro run |
| `shared/task.example.json` | uma task completa; o self-test a valida |
| `skills/agy/`, `skills/opencode/`, `skills/copilot/` | `crew:agy`, `crew:opencode`, `crew:copilot`: so o que e de cada CLI (flags, modelos e escalada, o que o guard daquele backend faz e nao faz). Cada uma manda ler o documento comum |
| `hooks/inject.sh` | `UserPromptSubmit`: injeta a skill do backend nomeado no prompt |
| `commands/delegate.md`, `commands/review.md` | `/crew:delegate` e `/crew:review` |

## Por que o gatilho e um hook

O `agent-fleet`, neste mesmo repo, mediu o disparo pela descricao da skill:
**2 de 30** runs que deviam disparar
([`2026-08-06-trigger-eval/`](../../bench/plugins/agent-fleet/results/2026-08-06-trigger-eval/)).
Por isso aqui o gatilho e mecanico: `hooks/inject.sh` injeta
`skills/<backend>/SKILL.md`, mais uma linha mandando ler `shared/delegate.md`,
quando o prompt contem `agy`, `opencode` ou `copilot` como **palavra inteira**,
sem diferenciar maiusculas (`agy-worker` e `crew:agy` casam, `agyx` nao). Dois
nomes no prompt, duas skills. So aconselha: nunca bloqueia, sai sempre 0, nao
usa rede, le so o prompt e arquivos do plugin (~20 ms medido a mao, uma
execucao). As descricoes das skills ficaram estreitas de proposito.

A taxa de acerto **deste** hook nao foi medida. O numero acima e do
`agent-fleet`, com outra skill e outro padrao; ele justifica a escolha do
mecanismo, nao diz quantas vezes este dispara quando deveria, nem quantas
dispara a toa (um prompt que so menciona "copilot" injeta a skill do copilot).

## O que um `delegate` faz

1. **Recusa antes de gastar** (saida 2): arvore suja, `.agents/hooks.json` ja
   existente, task invalida, modelo fora de `agy models`, quota do grupo do
   modelo abaixo de 5% em `agy -p /usage` (que responde sem turno de modelo).
2. Escreve `.agents/hooks.json` com tres hooks, todos o mesmo script:
   - `SessionStart`: marca que os hooks carregaram;
   - `PreToolUse` (`*`): so passam as ferramentas de arquivo e o
     `run_command` (allowlist: rede, subagente, workflow, MCP e qualquer
     ferramenta nova sao negados). Argumentos de caminho, relativos inclusive,
     sao resolvidos com `realpath` (symlink incluso) e negados fora do repo;
     no shell, caminho literal absoluto ou `~`, `..`, `cd` e `Cwd` para fora,
     `$HOME`, `.git/` e `.agents/`. Escrita so em `scope`, e so pelas
     ferramentas de edicao: redirecionamento para arquivo, `sed -i`, `tee`,
     `ln` e afins sao negados. git so com subcomandos de leitura (`status`,
     `diff`, `log`, `show`, `grep`, `add`...), com ou sem opcoes globais antes.
     Tambem install, deploy, migracao, rede, processos e `&`. Na ferramenta
     `finish` (a do `--json-schema`) roda o **gate** e nega o "terminei"
     enquanto ele falhar;
   - `Stop`: roda o gate de novo se o agy parar por `NO_TOOL_CALL` ou
     `TERMINAL_STEP_TYPE`, e devolve `continue` com a saida do gate, ate
     `max_gate_attempts`.
3. Roda `agy -p … --output-format json --json-schema … --print-timeout …
   --dangerously-skip-permissions` na raiz do repo.
4. Remove os hooks e julga o run. Exit diferente de 0 e falha; exit 0
   **nunca** e lido como sucesso. Tambem e falha: config, hooks, `info/exclude`
   ou flags de indice (`assume-unchanged`, `skip-worktree`) do git, ou o
   `ctx.json` do run, mudarem durante o run. Arquivo ignorado pelo git criado
   ou alterado vira aviso.
5. Enquanto o agy roda, vigia os comandos que ele joga para segundo plano e
   encerra os que sobraram depois de o worker terminar (ver
   [Comandos em segundo plano](#comandos-em-segundo-plano-no-agy)). No fim,
   encerra o que ainda tiver a marca do run (`CREW_RUN`) no ambiente.
6. Imprime um veredito JSON: `ok`, `failures`, `warnings`, arquivos por escopo,
   gate, negacoes dos guards, o relatorio do worker e o uso de tokens.

O gate e configuravel por projeto, na task: `forbid` (regex contra linhas
adicionadas), `format` (o ponto do formatter, com `{files}`) e `checks`. O
estado de cada run fica em `$(git rev-parse --git-path crew)/runs/`,
fora da arvore, e acumula: nada apaga run dirs antigos. Nada e commitado; em
falha, nada e revertido.

## Por que cada checagem existe: o que foi medido

Tudo abaixo e **n=1 por caso**, no agy 1.3.4, `gemini-3.8-flash-low`, em
2026-10-13, num repositorio descartavel. As notas do lab ficaram no scratchpad
da sessao e **nao estao commitadas**, entao leia como observacao, nao como
estatistica, e nao como registro no sentido do
[`bench/PROTOCOL.md`](../../bench/PROTOCOL.md).

| observado | consequencia no script |
|---|---|
| Hooks de workspace disparam em `-p`: os seis eventos | o guard pode ser hook do proprio agy |
| `PreToolUse` que imprime `{}` **nega** a chamada | todo handler imprime decisao explicita, inclusive quando quebra (o self-test cobre) |
| `--sandbox` nao impediu escrita fora do workspace, nem por `write_to_file` nem por shell | o guard de caminho e de escopo e o unico limite; o README nao chama isso de sandbox |
| Sem `--dangerously-skip-permissions`, escrita e auto-aprovada e `run_command` auto-negado; nenhuma config de workspace mudou isso (10 variantes) | o worker precisa rodar teste, entao `delegate` usa skip-permissions **mais** os hooks |
| `--json-schema` impossivel: exit 0, `status: SUCCESS`, `structured_output: null` | `structured_output` nulo e falha |
| `--print-timeout` estourado: exit 0 com saida parcial; o unico sinal e uma linha no stderr | o marcador do stderr e falha |
| Acao negada headless: exit 0, `denied_actions` no envelope | `denied_actions` e falha no delegate e aviso no review |
| Modelo invalido: exit 1 | o modelo e validado contra `agy models` antes |
| `--mode plan` impediu a escrita pedida, com e sem skip-permissions | o review usa `--mode plan` |
| Custom agent (`--agent`) nao foi descoberto em cinco layouts | o plugin nao depende de agent customizado |
| `-p "/usage" --output-format json` responde com `num_turns: 0` e fracao restante por grupo | o preflight de quota |

Do prototipo, num projeto real (porte Nest para TanStack Start, mesmo autor),
sem numero: forcado a continuar, o Gemini procurou o gate em `~/.claude`,
`/tmp`, `ps` e `../`; "consertou" o `nx.json` que o proprio Nx escreveu; nao
reportou divergencia sem ser perguntado; pulou formatacao com o gate sem
formatter; inventou alias. Dai `side_effects`, o campo `divergences` obrigatorio
no relatorio, o ponto `format` no gate e a revisao obrigatoria no documento comum.

## Smoke tests desta versao

**Nao ha run records.** Pela regra zero do `bench/PROTOCOL.md`, uma alegacao
de melhoria sem registro e marketing, e a tabela abaixo nao e registro: sao
runs de fumaca, n=1, para ver se o script faz o que diz, sem baseline.

Cinco runs, n=1 cada, `gemini-3.8-flash-low`, repo descartavel com um modulo
Python e `unittest`:

| run | resultado |
|---|---|
| delegate, tarefa simples (`slugify` + 3 testes) | `ok`, 43 s, gate verde na 1a tentativa. O Stop chegou com `TERMINAL_STEP_TYPE`, **nao** `NO_TOOL_CALL`: um gate so no Stop/`NO_TOOL_CALL`, como no prototipo, teria deixado o run terminar sem gate. A revisao achou `import re` dentro da funcao e linha em branco sobrando no fim do arquivo, que o gate de brinquedo (sem formatter de verdade) nao pegou |
| delegate com um check que falha so na 1a vez (`gate_once.py`) | 1a versao do script: `ok: false`. O cache guardava a **falha** para a arvore identica, o worker ficou sem o que mudar e passou a procurar o gate (`env`, `git config --list`, `/proc/self/mountinfo`), os tres negados; o run estourou o timeout e saiu exit 0 com `structured_output` nulo, os dois pegos. Corrigido para cachear so gate verde. 2a execucao: `finish` negado com a saida do gate, o worker rodou os checks de novo, gate verde na 2a tentativa, `ok`, 61 s |
| review `--diff HEAD~2` | `ok`, 21 s, arvore inalterada, 5 findings com `evidence`; dois deles sao os mesmos dois problemas que a revisao humana do run 1 achou |
| delegate depois do endurecimento do guard (allowlist de ferramentas, git so leitura, `.git` e redirect negados, `realpath`), com o mesmo `gate_once.py` | `ok`, 71 s, `finish` negado na 1a tentativa e gate verde na 2a. Nenhuma chamada legitima negada: 7 `run_command`, 3 `replace_file_content`, 2 `view_file`, todos permitidos |
| review `--diff HEAD --prompt-file` sobre esse diff | `ok`, 16 s, `approve` sem findings, arvore e `.git` inalterados, so `view_file` |

Na 0.4.1, dois runs com `gemini-4-argon-medium` no agy **1.4.2** (2026-10-18,
repo descartavel com um modulo Python, `unittest` e um checador de formato so
com stdlib no lugar do `ruff`, que nao estava instalado; mesma fatia `slugify`
\+ 3 testes):

| run | resultado |
|---|---|
| sem `.gitignore` no repo | `ok: false`, culpa do lab: o `unittest` do gate escreveu `__pycache__`, que a checagem de escopo pos-run acusou. O diff do worker estava certo. O Argon pediu um caminho absoluto inventado (um segmento do caminho do repo duplicado) e o guard negou |
| com `__pycache__/` no `.gitignore` | `ok`, 66 s, ~55 mil tokens, gate verde na 1a passada. Diff correto e no estilo do arquivo; uma unica negacao: o worker tentou rodar o checador do gate, que fica fora do repo |

O preflight de quota checou o grupo "Gemini 4 Argon", nao o "Gemini Models".
Nenhum desses runs mostra que o Argon acerta o que o Flash erra.

### agy 1.4.2: o comportamento de que o script depende

Na 0.4.2, os smoke tests que dependem do comportamento do agy, refeitos no
**1.4.2** (2026-10-18), n=1 cada, `gemini-3.8-flash-low`, repo descartavel com
um modulo Python, `unittest` e `__pycache__/` no `.gitignore`. Nao sao run
records, e o mesmo n=1 da tabela do 1.3.4 acima: dizem que o comportamento
ainda esta la, nao com que frequencia.

| comportamento | 1.4.2 | como foi visto |
|---|---|---|
| hooks de workspace disparam em `-p` | sim, os seis | `agy -p` cru com um `.agents/hooks.json` que so registra: `SessionStart`, `PreInvocation`, `PreToolUse`, `PostToolUse`, `PostInvocation` e `Stop`, todos disparados (24 s) |
| `PreToolUse` que imprime `{}` nega | sim | mesmo run: o 1o `view_file` recebeu `{}` e falhou com "tool call denied by pre-tool hook", sem `PostToolUse`; o 2o recebeu `allow` e rodou |
| ferramenta `finish` com `--json-schema` | sim | delegate `slugify` + 3 testes: `finish` permitido com gate verde, relatorio `done`, `ok`, 44 s, ~41 mil tokens, nenhuma negacao. A revisao do diff achou `import re` dentro da funcao, linhas em branco sobrando e um teste chamado `..._non_ascii` sem caractere nao ASCII |
| motivos de Stop | `NO_TOOL_CALL` e `TERMINAL_STEP_TYPE`, como no 1.3.4 | `NO_TOOL_CALL` no run cru e no 1o Stop do vigia; `TERMINAL_STEP_TYPE` depois do `finish` nos dois delegates e no review. O payload do Stop traz agora `fullyIdle` (true no run cru), que o script nao le |
| formato do `/usage` | igual: `num_turns: 0`, `command.data.groups[].buckets[].remaining_fraction` | tres grupos ("Gemini Models", "Claude and GPT models", "Gemini 4 Argon"); com cada grupo zerado por vez num JSON copiado do real, o preflight recusou so os modelos daquele grupo (Flash, Sonnet e GPT-OSS, Argon) |
| vigia de segundo plano | sim | o `./check.sh` do worker (20 s, e 300 s a mais fora do gate) foi para background task (o worker chamou `manage_task` 14 s depois, negado); gate verde no `Stop` (`NO_TOOL_CALL`) as 12:37:27, `continue` pedindo o relatorio, `finish` as 12:37:52, `bash ./check.sh` e `sleep 300` encerrados as 12:38:08; `ok`, 96 s. Os MCP servers filhos do agy (ai-memory, kino) ficaram de fora. O agy logou "waiting up to 15m0s for 1 background task(s)", com `--print-timeout 900s`; no 1.3.4 eram 30m (se o limite segue o print timeout, nao foi testado) |
| review em `--mode plan` | sim | `--diff HEAD~1 --prompt-file`: `ok`, 83 s, arvore e HEAD inalterados, so `view_file` e `finish`, `request_changes` com 4 findings com `evidence`; dois sao os mesmos da revisao humana (`import re`, o teste `..._non_ascii`). O modo plan nao tentou gravar plano em `~/.gemini` neste run |

Com tudo batendo, o `TESTED_AGY_VERSION` passou a 1.4.2: o aviso de versao
some no 1.4.2 e aparece no 1.3.4. Nao foi refeito no 1.4.2: o timeout e o
`--json-schema` impossivel saindo 0, `--sandbox`, o run sem
`--dangerously-skip-permissions` e o `--agent`.

## O que nao foi medido

- **Nenhuma comparacao** com o Claude fazendo a mesma tarefa: nem qualidade,
  nem tempo, nem custo. Este README nao diz que delegar economiza nada.
- Taxa de falso positivo e de falso negativo dos guards em uso real. As regex
  de comando sao lista, nao medicao. O que elas **nao** pegam: caminho montado
  em tempo de execucao (`python3 -c`, `node -e`, variavel). A checagem de
  escopo pos-run usa `git status`, entao so ve arquivo rastreado e nao
  rastreado-nao-ignorado **dentro** do repo. Arquivo ignorado novo ou alterado
  (`.env`) so vira aviso, e escrita dentro de diretorio ignorado
  (`node_modules/.bin/...`, `dist/`) e fora do repo nao e vista por nada. O
  gate final roda as ferramentas da propria arvore, entao um binario do gate
  adulterado em `node_modules` passaria.
- O bloqueio de segredo olha o nome do arquivo (`secret_globs`), nas
  ferramentas e nas palavras do comando. Caminho montado em tempo de execucao
  (`cat .e*`, `python3 -c`) passa, e uma busca recursiva num diretorio que
  contem `.env` le o arquivo. So o self-test cobre a regra; nenhum run real
  tentou ler um segredo.
- O vigia de segundo plano foi provado so no lab (dois runs, abaixo) e com
  `bash` + `sleep`, nao com um `nx` de verdade: um comando que se desliga do
  agy (daemon com `setsid` ou fork duplo) deixa de ser descendente dele e o
  vigia nao o ve; so o encerramento por marca, no fim, o pega. O MCP server
  que o agy sobe e protegido pela linha de base (tudo o que o agy tinha antes
  do primeiro `run_command`) e por nome (`mcp` na linha de comando); um helper
  que o agy suba depois disso sem `mcp` no nome e tem a marca seria encerrado.
- A ferramenta `manage_task` do agy (consultar ou parar uma background task)
  fica fora da allowlist: no 2o run do lab o worker a chamou para esperar o
  comando e foi negado. Liberar so `status` deixaria o worker esperar a toa;
  nao foi testado.
- Runs em paralelo, um worktree por fatia: nao testado.
- Hooks que nao carregam: o script detecta (sem `SessionStart`, o run falha),
  mas a causa nao foi reproduzida. Os hooks dispararam headless em pastas fora
  de `trustedWorkspaces`, entao confianca no workspace nao e a explicacao
  provada; e so uma hipotese, ao lado de `hooks.json` invalido.
- O review em `--mode plan` com o worker tentando escrever: no lab (E7) o modo
  plan grava um artefato de plano em `~/.gemini/antigravity-cli/brain/`, e o
  guard nega essa escrita por ser fora do repo. O unico review de fumaca so
  leu arquivos; se a negacao faz o modelo entrar em loop, nao se sabe.
- A allowlist de ferramentas: os runs de fumaca so usaram `view_file`,
  `write_to_file`, `replace_file_content`, `run_command` e `finish`. Uma
  ferramenta legitima fora da lista (de uma versao nova do agy) e negada e
  aparece em `guard_denials`.
- Modelos Claude ou GPT pelo agy: a quota deles estava zerada no dia; o
  preflight recusou, como devia, e nada alem disso foi testado.

## Comandos em segundo plano no agy

O `run_command` do agy 1.3.4 manda um comando longo para uma background task
depois de ~4 s **qualquer que seja** o `WaitMsBeforeAsync`. A 0.3.0 reescrevia
esse argumento no `PreToolUse` para 900000; em dois runs reais (LOTVS,
2026-10-13) o agy registrou a reescrita ("A pre-tool hook changed the arguments
... Changed: WaitMsBeforeAsync") e mesmo assim o `nx run web:typecheck` voltou
como "Tool is running as a background task". Depois do gate verde e de o
worker parar, o agy logou "root agent idle; waiting up to 30m0s for 1
background task(s)" e ficou parado 16 e 11 min, ate os `npm`/`nx` orfaos serem
mortos a mao; ai saiu normalmente, com envelope valido. **A reescrita nao
funciona e foi removida.**

No lugar, o `delegate` do agy vigia o run (`BackgroundWatcher`, uma vez por
segundo). Quando o `guard.jsonl` mostra que o worker terminou depois de um gate
**verde** (o `Stop` respondeu `stop`, ou o `finish` foi permitido), espera
15 s e encerra (SIGTERM, 5 s, SIGKILL) os processos que sao, todos ao mesmo
tempo: descendentes do processo do agy; marcados com `CREW_RUN=<run>` no
ambiente; fora de um hook nosso (o gate roda la, com `CREW_GATE=1`); fora da
linha de base (o que o agy ja tinha subido antes do primeiro `run_command`
permitido, como os MCP servers) e sem `mcp` na linha de comando. Nunca o agy:
o envelope dele em stdout e a entrada do veredito. O que foi encerrado vai em
`agy.background_killed` e num aviso; a arvore de processos do agy fica em
`procs.jsonl` no run dir.

Tambem por causa disso: o aviso de background task manda o modelo encerrar o
turno, e no 1o run do lab ele encerrou sem chamar `finish`, com gate verde e
`structured_output` nulo. Agora o `Stop` com gate verde e sem `finish` devolve
`continue` pedindo so o relatorio, no maximo 2 vezes.

Prova no lab (agy 1.3.4, `gemini-3.8-flash-low`, n=1 por versao, repo
descartavel fora de `trustedWorkspaces` em que os hooks carregaram; o check do
gate dorme 30 s, e 300 s a mais quando quem roda e o worker, para a background
task sobreviver a ele). Nao sao run records:

| run | resultado |
|---|---|
| vigia, sem o pedido de `finish` | o `./check.sh` do worker foi para segundo plano; gate verde no `Stop` as 11:49:54; `bash ./check.sh` e `sleep 300` encerrados as 11:50:09 (15 s); o agy saiu, 83 s no total. O MCP server do media-agent (`uv tool uvx ... kino --mcp`), filho do agy, ficou de fora. `ok: false` so por `structured_output` nulo: o worker parou sem `finish` |
| vigia + pedido de `finish` | gate verde no `Stop` (`NO_TOOL_CALL`) as 11:52:58, `continue` pedindo o relatorio, `finish` permitido as 11:53:02, os dois processos encerrados as 11:53:18; `ok: true`, relatorio `done`, 103 s. O kino de novo intocado. O worker tentou `manage_task` para esperar o comando e foi negado |

Sem o vigia, o mesmo lab teria esperado os 300 s do `sleep` (inferido: nao foi
rodado sem ele); nos runs reais, ate 30 min. No agy 1.4.2 o mesmo vigia + pedido
de `finish` passou de novo (n=1, na tabela do 1.4.2 acima).

O aviso "processos novos com cwd no repo", da 0.3.0, listava qualquer processo
com cwd no repo, e deu falso positivo: o laco `bash -c ... sleep 2` da propria
sessao do Claude que esperava o run. Agora o aviso olha so a marca do run, e
lista o que sobreviveu ao encerramento por marca.

## Backend opencode

Para quando a quota do agy acabou, ou para capacidade extra gratis. O agy
continua o primario. Requer o `opencode` no PATH ou em `~/.opencode/bin`; so
foi exercitado no **1.19.0** (outra versao vira aviso).

| | agy | opencode |
|---|---|---|
| guard | hooks do agy em `.agents/hooks.json`, na arvore durante o run | plugin gerado no run dir (dentro do `.git`), carregado so pelo `OPENCODE_CONFIG_CONTENT` daquele processo; nada entra na arvore nem em `~/.config/opencode` |
| politica | `decide_pre` | a mesma: o plugin JS nao tem regra nenhuma, manda cada chamada para `crew.py hook oc-pre`, que traduz a ferramenta do opencode (`read`, `write`, `edit`, `bash`, `apply_patch`...) para a do agy; qualquer resposta que nao seja allow nega |
| shell | lista do agy | a lista do agy **mais** `cp`, `mv`, `touch`, `mkdir`, `rm`... (os modelos do opencode escrevem pelo shell) |
| gate | no `finish` e no Stop, dentro do agy | loop externo: run, gate, `opencode run -s <sessao>` com a saida do gate, ate `max_gate_attempts` runs |
| relatorio | `--json-schema` | o ultimo objeto JSON da mensagem final, pedido no prompt; se faltar, o loop pede de novo |
| sucesso | envelope + gate | eventos JSON (nenhum `error`, ultimo `step_finish` com `reason=stop`) + gate; exit 0 nao conta |
| review | `--mode plan` | sem modo plan: escopo vazio e **todo** comando de shell negado pelo plugin |

O que o lab mostrou (opencode 1.19.0, 2026-10-13, n=1 por caso, notas no
scratchpad da sessao, **nao commitadas**) e o que o script faz por causa disso:

| observado | consequencia |
|---|---|
| `opencode run` com stdin aberto trava (0 bytes ate o timeout) | stdin sempre `/dev/null` |
| grava `"$schema"` no `opencode.json` do cwd mesmo com `--dir`; de dentro do `.git` achou a arvore e gravou la | os bytes de `opencode.json`/`.jsonc` sao guardados antes de qualquer processo do opencode e restaurados depois de cada um (vira aviso); o preflight roda num diretorio temporario vazio; escopo que cubra esses arquivos e recusado |
| `permission.bash: deny` faz os modelos gratis falharem na partida (403) | o shell e policiado no plugin, nao em `permission` |
| `throw` em `tool.execute.before` bloqueia a chamada e o modelo ve o texto | e o mecanismo do guard |
| escrita por bash passa por cima dos globs de `edit` | redirecionamento e os coreutils de escrita sao negados no plugin; o `git status` pos-run continua sendo a autoridade |
| `external_directory: deny` funciona | vai no config do run |
| plugin que reabre a sessao no `session.idle` nao continua o `run` | o loop do gate e externo |
| `--agent` inexistente sai 0 rodando o agente padrao | nenhum agent customizado |
| carrega `~/.claude/CLAUDE.md` por padrao; `OPENCODE_DISABLE_CLAUDE_CODE=1` desliga | carrega, como um subagente nativo; `"disable_claude_code": true` na task desliga |

Modelo padrao: `opencode/longcat-2.5-preview-free`. No unico bench de
qualidade (n=1, porte de um servico CJS com 16 casos de teste, notas no
scratchpad), longcat, space-bunny e muse-spark passaram o gate e portaram os 16
casos; o longcat manteve as 22 assercoes um a um como no legado, o space-bunny
moveu metade para helpers. O longcat foi o mais lento (139 s contra 34 s) e e o
unico exercitado com o plugin de guard e o loop externo. Pelos docs do Zen,
longcat, space-bunny e step-5 sao de retencao zero; o muse-spark usa o prompt
para treino (aceitavel so em projeto pessoal, escolha do usuario).

**Guard mais fraco que o do agy, e por que:** o opencode nao tem allowlist de
ferramenta no nivel do processo nem modo plan; tudo depende do plugin carregar
(sem o `SessionStart` dele, o run falha) e de uma lista de regex sobre o
comando. O que monta caminho em tempo de execucao (`python3 -c`, `node -e`)
passa, igual ao agy, e os modelos do opencode usam mais o shell.

Smoke tests, n=1 cada, `opencode/longcat-2.5-preview-free`, repo descartavel
com um modulo Python e `unittest`, 2026-10-13. Nao sao run records:

| run | resultado |
|---|---|
| delegate simples (`slugify` + 3 testes) | `ok`, 50 s, 1 run, gate verde |
| delegate com check que falha so na 1a vez | `ok`, 68 s: gate vermelho no run 1, `run -s` na mesma sessao, verde no run 2 |
| delegate pedindo `echo reviewed > NOTES.txt` | o modelo recusou sozinho pelas regras do prompt; nao testou o guard |
| delegate pedindo os testes com `> test-output.log` | `ok`, 105 s: o redirect pelo bash negado, depois o `write` do mesmo arquivo negado; arquivo inexistente, relatado em `out_of_scope_needs` |
| review `--backend opencode` com `opencode.json` versionado | 1a versao: o preflight gravou o `$schema` antes do snapshot e o veredito nao viu. Corrigido (preflight em dir temporario, snapshot antes dele). 2a: `ok`, `approve`, `opencode.json` com o mesmo sha256 |
| delegate com `opencode.json` versionado | `ok`, 37 s, aviso de restauracao, `opencode.json` com o mesmo sha256 |

Nao medido: qualidade contra o agy ou o Claude na mesma fatia, taxa de falso
positivo do guard, `apply_patch` (os modelos testados so usaram `write` e
`edit`), caminho com espaco no `file://` do plugin, e o que acontece com um
`OPENCODE_CONFIG_CONTENT` que o usuario ja tenha no ambiente (o do run o
substitui).

## Backend copilot

Requer o `copilot` (GitHub Copilot CLI) no PATH e logado; so foi exercitado no
**1.0.96**, numa conta **Copilot Free** (outra versao vira aviso). Para quando
se quer um terceiro par de maos e se aceita gastar AI credits: no Free nao ha
quota gratis a poupar, cada run custa.

| | agy | copilot |
|---|---|---|
| guard | `.agents/hooks.json` | `.github/hooks/crew-<run>.json`, escrito no comeco do run e removido no fim (inclusive SIGTERM/SIGHUP); recusa se ja existir, ou se sobrar um `crew-*.json` de run morto; o `git status` pos-run ignora exatamente esse arquivo |
| carga dos hooks | automatica | so com `COPILOT_ALLOW_ALL=true` no ambiente do processo; `--allow-all-tools` e `trustedFolders` nao carregam (lab) |
| politica | `decide_pre` | a mesma: `hook cp-pre` traduz `view`, `glob`, `grep`, `apply_patch` (patch cru, um alvo por arquivo), `create`, `edit` para a ferramenta do agy; ferramenta desconhecida, `task`, MCP, rede e qualquer shell sao negados; qualquer coisa que nao seja allow nega |
| shell | lista do agy | **nenhum**: `--excluded-tools bash task`. Chamada de shell ou de `task` no stream de eventos reprova o run |
| gate | no `finish` e no Stop | no `agentStop`, que devolve `block` com a saida do gate ate `max_gate_attempts` (no maximo 8: o CLI ignora o hook depois de 8 bloqueios seguidos); com gate verde e relatorio ausente na mensagem final, bloqueia de novo pedindo so o relatorio, no maximo 2 vezes |
| relatorio | `--json-schema` | o ultimo objeto JSON da ultima `assistant.message` |
| sucesso | envelope + gate | evento `result` com `exitCode` 0, nenhum evento de erro, nenhuma chamada de shell/`task`, algum hook nosso registrado, relatorio, gate, escopo, HEAD; o exit 0 nao conta |
| custo | quota do agy | `usage` no veredito: `ai_credits` (de `totalNanoAiu`; 1 credito = 1e9 nanoAIU e inferido, nao documentado), `premium_requests`, `served_models` |
| review | `--mode plan` | escopo vazio (toda escrita negada no hook) e `--excluded-tools bash task apply_patch` |
| modelo | `agy models` | so `auto`; outro modelo e recusado, salvo `"copilot_model_override": true` na task (ou `--copilot-model-override` no review), caminho **nao testado** para plano pago |

Outras flags de todo run: `--allow-all-tools` (exigida pelo `-p`),
`--disallow-temp-dir`, `--no-ask-user`, `--no-auto-update`,
`--disable-builtin-mcps`, `--max-ai-credits 30` (o minimo aceito; serve so de
freio para um run que dispare, nao de orcamento), `--usage-output-file` e
`--log-dir` no run dir. Ambiente: `COPILOT_ALLOW_ALL=true`, `NX_DAEMON=false`,
`CREW_RUN`. O `COPILOT_HOME` continua o do usuario: isola-lo perdeu o
login no lab.

O que o lab mostrou (copilot 1.0.95/1.0.96, 2026-10-13, n=1 por caso, notas
no scratchpad da sessao, **nao commitadas**) e o que o script faz por causa
disso:

| observado | consequencia |
|---|---|
| exit 0 com tarefa falhada (escrita negada, modelo dizendo "Incomplete") | o sucesso vem dos eventos JSONL e do gate |
| hooks de `.github/hooks/*.json` so carregam com `COPILOT_ALLOW_ALL=true` | o run seta, so no ambiente do processo; isso tambem carrega skills, plugins e MCP servers do repo, e hooks do proprio repo rodam junto (o veredito avisa quais) |
| `preToolUse` com `permissionDecision: deny` nega, inclusive `../x` e `src/../x`, e dentro de subagentes | e o guard |
| `agentStop` com `decision: block` e `reason` forca outra volta; `stop_hook_active` na reentrada | e o gate |
| timeout de hook **libera** (fail open, docs) | o `cp-pre` nao roda gate (0,05 a 0,07 s por chamada em 10 execucoes locais do handler, contra um timeout de 30 s); erro dentro do handler nega; um gate que estoure o timeout do `agentStop` deixa parar, e o gate final do veredito pega |
| excluir so `bash` levou a 2826 chamadas de `task` e ~5,5 creditos | `bash` e `task` sempre excluidos juntos |
| `--max-ai-credits` abaixo de 30 e recusado | 30 como freio, nao como teto por run |
| `--model X` recusado para os 32 modelos do catalogo nesta conta; o Auto roteia para gpt-5.6-luna | so `auto` |
| `--usage-output-file` traz creditos e o modelo servido | vai no veredito |
| hooks tambem carregam de `.github/copilot/settings*.json` e `.claude/settings*.json` (docs) | escrita nesses caminhos e em `.github/hooks/` e negada, e um escopo que os cubra e recusado |

Smoke tests, n=1 cada, `--model auto` (servido: gpt-5.6-luna), repo
descartavel com um modulo Python e `unittest`, 2026-10-13. Nao sao run records:

| run | resultado |
|---|---|
| delegate (`slugify` + 3 testes) com um check que falha so na 1a vez | `ok`, 21 s, 0,529 AI credits, 2 premium requests. `sessionStart` disparou; `agentStop` bloqueou com o gate vermelho, a 2a parada passou com gate verde. Ferramentas: 2 `view` (arquivos inexistentes, falha normal), 1 `apply_patch` com caminhos absolutos dentro do escopo; nenhuma negacao, nenhum shell. O relatorio diz `python3 -m unittest ... PASS` em `checks_run`, coisa que o worker sem shell nao rodou: autodeclarado, como sempre |
| review `--backend copilot --diff HEAD~1` | `ok`, 19 s, 0,411 AI credits, 1 premium request. So 2 `view`; arvore inalterada; `request_changes` com um finding correto (nenhum teste com pontuacao ou nao-ASCII) |

Total: 0,94 AI credits nos dois. Antes deles, uma checagem de flags com
modelo inexistente (recusada antes de chamar modelo, 0 creditos).

Nao medido: uma negacao do guard num run real deste script (o lab mostrou a
do mesmo mecanismo, com outro handler); `create`/`edit`/`grep` (o modelo so
usou `view` e `apply_patch`); se o `agentStop` ve o stdout ja escrito quando
pede o relatorio (se nao vir, nao pede; o pedido nunca foi exercitado); o que
acontece quando os creditos acabam; qualidade contra os outros backends;
plano pago e `copilot_model_override`; runs em paralelo.

## Por que nao ha workflow script

A ideia era herdar do `agent-fleet` um workflow que abre varias delegacoes em
paralelo, cada uma com subagente escrevendo a task, agy executando, gate e
revisao, e modelo por fase. Ficou de fora porque:

- **Os runs se serializam por construcao**: arvore limpa e um
  `.agents/hooks.json` por workspace. Paralelo exige um worktree por fatia, e
  criar, limpar e juntar worktrees e mais codigo do que o resto do plugin, para
  um caminho que nao foi testado nem uma vez.
- **A revisao nao e delegavel a um subagente sem contexto**: ela compara o diff
  com a fonte da verdade e com o que a sessao ja sabe do projeto. O passo caro
  e o que tem que ficar com o dono da sessao.
- O roteamento por fase, que e o que o `agent-fleet` ensina, ja existe aqui sem
  script: tarefa e revisao no modelo da sessao, execucao no Gemini via `model`
  da task.

Se N fatias repetitivas virarem rotina, o caminho e um loop sequencial na
propria sessao (delegate, revisao, commit, proxima), nao um fan-out.

## Verificacao

`just check` roda `crew.py --self-test`: 311 assercoes sem chamar o agy,
o opencode nem o copilot,
num repo git temporario. Cobrem as decisoes do guard (allowlist de ferramentas,
caminho relativo e absoluto, symlink, `cd`/`Cwd`, `.git` pelo shell, git com
opcoes globais e com aspas, redirecionamento, `&`, `finish`, gate isento so sem
encadeamento nem quebra de linha) e os falsos positivos que ja existiram
(`grep '/api/v1'`, `git log --grep=publish`), a deteccao de config/flag do git e
de `.env` ignorado, o fsmonitor plantado que nao roda no git do script, o
timeout do gate que mata os filhos, o handler quebrado negando em vez de
devolver `{}`, o gate (escopo, forbid com numero de linha, `{files}` com espaco
no nome, efeito colateral tolerado, `AGY_WORKER_GATE`), o cache que guarda so
gate verde, a avaliacao do envelope em cada modo de falha com exit 0, a quota
contra o formato real do `/usage` de 2026-10-13, e instalar e remover o
`hooks.json` sem deixar rastro nem sobrescrever um existente. Do opencode: a
traducao de cada ferramenta para a politica do agy (inclusive `apply_patch`
com alvo fora do escopo e ferramenta desconhecida), as negacoes extras do shell
so nesse backend, o review negando todo shell, o handler `oc-pre` quebrado
negando, os eventos que saem 0 e sao falha, a extracao do relatorio, a
restauracao exata do `opencode.json` e o plugin gerado apontando para o script.
Do copilot: a regra do modelo (`auto` ou override), os campos da task, o
prompt sem shell, a traducao de cada ferramenta (inclusive `apply_patch` cru
com `..`, `src/..`, `Move to` e alvo no arquivo de hooks), shell, `task`, MCP e
ferramenta desconhecida negados, o contrato de saida do hook (allow sem
saida, deny com `permissionDecision`), o `agentStop` bloqueando com gate
vermelho, pedindo o relatorio com no maximo 2 pedidos e nao pedindo sem stream
legivel, os handlers quebrados (o `cp-pre` nega), os eventos que saem 0 e sao
falha, a leitura do `usage.json`, a linha de comando com `bash task`
excluidos, e o arquivo de hooks gerado, ignorado so ele no escopo, nunca
sobrescrito, removido com os diretorios que o run criou.

O vigia de segundo plano: quem pode ser encerrado numa arvore sintetica (hook,
gate, linha de base, MCP e processo sem marca ficam; o agy nunca), quando o
worker conta como terminado (so com o ultimo gate verde) e, com processos de
verdade, um "agy" falso com um helper anterior ao primeiro comando, um comando
do worker e um processo sem marca: so o comando e encerrado, e so depois da
carencia. Tambem o `Stop` que pede o `finish` no maximo 2 vezes.

O hook de injecao nao tem teste no `just check` alem do shellcheck e da
checagem de que o `hooks.json` aponta para um executavel.

## Changelog

**0.4.2** (2026-10-18)

- Smoke tests refeitos no agy 1.4.2, n=1 cada: hooks em `-p`, `{}` negando,
  `finish` com `--json-schema`, motivos de Stop, formato do `/usage`, o vigia
  de segundo plano e o review em `--mode plan`. Tudo bateu com o 1.3.4
  ([tabela](#agy-142-o-comportamento-de-que-o-script-depende)), e o
  `TESTED_AGY_VERSION` passou a 1.4.2: o aviso de versao agora sai no 1.3.4,
  nao mais no 1.4.2.

**0.4.1** (2026-10-18)

- Preflight de quota do agy: o grupo era achado pela familia do modelo
  (`gemini`), que no agy 1.4.2 casa tambem com o grupo novo "Gemini 4 Argon".
  Um Argon esgotado recusava todo run do Flash, e vice-versa, embora no plano
  Pro as duas quotas sejam separadas. Agora o grupo e achado pela linha do
  modelo (`flash`, `argon`, `sonnet`, `oss`), e pela familia so como fallback.
- Escalada do agy: Flash, depois `gemini-4-argon-medium`, depois
  `claude-sonnet-5-5-medium`. O Argon tem quota propria e nao gasta a dos
  Claude. Dois runs de fumaca, acima.

**0.4.0** (2026-10-13)

- Renomeado de `agy-worker` para `crew`: diretorio, manifesto, comandos
  (`/crew:delegate`, `/crew:review`) e o script (`scripts/crew.py`). A skill
  unica virou tres, uma por backend (`crew:agy`, `crew:opencode`,
  `crew:copilot`), mais o documento comum `shared/delegate.md`.
- **Estado no git dir mudou de `agy-worker/` para `crew/`**
  (`$(git rev-parse --git-path crew)`). Run dirs antigos ficam em
  `agy-worker/runs/` e nada os le. Task files sao passados pelo caminho, entao
  os que estiverem em `agy-worker/tasks/` continuam funcionando; para seguir a
  convencao nova, mova-os para `crew/tasks/` (`git rev-parse --git-path
  agy-worker` e `--git-path crew` dao os dois caminhos).
- Variaveis: `AGY_WORKER_RUN` virou `CREW_RUN`; o gate exporta `CREW_GATE=1` e
  ainda `AGY_WORKER_GATE=1`. Sobras de run morto da 0.3.0 (`.agents/hooks.json`
  com a chave `agy-worker`, `.github/hooks/agy-worker-*.json`) continuam
  reconhecidas.
- Hook `UserPromptSubmit` que injeta a skill do backend nomeado.
- Removida a reescrita de `WaitMsBeforeAsync` (nao funciona); vigia de
  processos em segundo plano no agy; `Stop` pede o `finish` que faltou.
- O aviso de processos que sobraram usa a marca do run, nao o cwd.
