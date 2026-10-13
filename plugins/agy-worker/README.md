# agy-worker

Usa os modelos da Google como worker barato **sem brigar com o harness do
Claude**: o Claude planeja, escreve a task, define escopo e gate e revisa o
diff; o Antigravity CLI (`agy`) com Gemini executa headless, uma fatia por vez,
sob guard rails que existem so durante o run.

```
/plugin install agy-worker@4nrry
```

Requer `agy` autenticado, `git`, `python3` (so stdlib) e Linux (`/proc`, para
listar processos que sobraram). So foi exercitado no agy **1.3.4**; com outra
versao o veredito traz um aviso, porque decisao de hook, a ferramenta `finish`,
os motivos de Stop e o formato do `/usage` sao comportamento observado, nao
contrato. Nenhum daemon, nenhum MCP server e nenhum hook do Claude Code: os
hooks que este plugin instala sao **do agy**, escritos em `.agents/hooks.json`
no comeco do run e removidos no fim (inclusive em SIGTERM e SIGHUP; depois de
um SIGKILL o proximo run recusa e diz qual arquivo remover).

Segundo backend, opcional: o **opencode** (`"backend": "opencode"` na task),
com os modelos gratis do Zen. Mesmo veredito, mesmas regras de caminho, escopo
e comando, guard mais fraco no shell; detalhes em
[Backend opencode](#backend-opencode).

**O codigo sai da maquina.** Delegar ou pedir review manda o prompt, os
arquivos que o worker ler e o diff para a Google, e gasta a quota do agy. A
skill manda o Claude perguntar antes do primeiro run na sessao.

## Componentes

| componente | o que faz |
|---|---|
| `scripts/agy_worker.py` | `delegate`, `review`, `gate`, os handlers de hook do agy, o guard e o loop do opencode, e `--self-test`. Um arquivo |
| `skills/agy-worker/` | quando delegar e quando nao, como escrever a task, como ler o veredito, a revisao obrigatoria |
| `skills/agy-worker/task.example.json` | uma task completa; o self-test a valida |
| `commands/delegate.md`, `commands/review.md` | `/agy-worker:delegate` e `/agy-worker:review` |

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
5. Imprime um veredito JSON: `ok`, `failures`, `warnings`, arquivos por escopo,
   gate, negacoes dos guards, o relatorio do worker e o uso de tokens.

O gate e configuravel por projeto, na task: `forbid` (regex contra linhas
adicionadas), `format` (o ponto do formatter, com `{files}`) e `checks`. O
estado de cada run fica em `$(git rev-parse --git-path agy-worker)/runs/`,
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
no relatorio, o ponto `format` no gate e a revisao obrigatoria na skill.

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
- O `overwrite` de `WaitMsBeforeAsync` e o encerramento dos processos marcados
  vieram de um run real que travou 16 min (n=1); o self-test cobre a logica, e
  o primeiro run depois da mudanca e o que vai dizer se o agy aceita o valor.
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

## Backend opencode

Para quando a quota do agy acabou, ou para capacidade extra gratis. O agy
continua o primario. Requer o `opencode` no PATH ou em `~/.opencode/bin`; so
foi exercitado no **1.19.0** (outra versao vira aviso).

| | agy | opencode |
|---|---|---|
| guard | hooks do agy em `.agents/hooks.json`, na arvore durante o run | plugin gerado no run dir (dentro do `.git`), carregado so pelo `OPENCODE_CONFIG_CONTENT` daquele processo; nada entra na arvore nem em `~/.config/opencode` |
| politica | `decide_pre` | a mesma: o plugin JS nao tem regra nenhuma, manda cada chamada para `agy_worker.py hook oc-pre`, que traduz a ferramenta do opencode (`read`, `write`, `edit`, `bash`, `apply_patch`...) para a do agy; qualquer resposta que nao seja allow nega |
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

`just check` roda `agy_worker.py --self-test`: 209 assercoes sem chamar o agy
nem o opencode,
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
