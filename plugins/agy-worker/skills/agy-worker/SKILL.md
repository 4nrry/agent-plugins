---
name: agy-worker
description: Delegar uma fatia de codigo bem delimitada e checavel por maquina ao Gemini pelo Antigravity CLI (`agy`) headless, sob guard rails e gate, e pedir segunda opiniao somente leitura. Diz quando delegar (porte mecanico, testes a partir de spec, migracao repetitiva com gate objetivo) e quando nao (spike exploratorio, decisao de design, mudanca sem gate), como escrever a task (prompt, escopo, gate, schema do relatorio), como ler o veredito, e que o diff tem que ser revisado contra a fonte da verdade depois de todo run, porque o gate e necessario e nao suficiente. Use quando a tarefa mencionar agy, Antigravity, Gemini como worker, delegar para um modelo mais barato, poupar quota do Claude, segunda opiniao do Gemini, ou quando houver uma lista de fatias repetitivas com teste objetivo e o usuario quiser tira-las da sessao.
---

# Gemini como worker, Claude como dono

A divisao e fixa: **voce** planeja, escreve a task, define escopo e gate, le o
veredito e revisa o diff. O `agy` com Gemini **executa**, headless, uma fatia
por vez. Nunca o contrario: o worker nao decide design, nao commita e nao
declara nada pronto por conta propria.

Sem guard rails isso nao funciona. Forcado a continuar, o Gemini Flash foi
procurar o checador em `~/.claude`, `/tmp`, na lista de processos e em `../`
em vez de consertar o codigo; "consertou" arquivo que o Nx escreve sozinho;
inventou alias que nao existia; pulou formatacao. O script deste plugin e o
guard rail; esta skill e o resto, que o script nao consegue fazer por voce.

## Pergunte antes do primeiro run

Delegar e revisar mandam o prompt, os arquivos que o worker ler e o diff para
a Google, gastam a quota do agy do usuario e rodam com
`--dangerously-skip-permissions` (os hooks sao o limite). Antes do primeiro
`delegate` ou `review` da sessao, pergunte; depois do sim, nao precisa
perguntar de novo a cada fatia.

## Quando delegar

- Existe **fonte da verdade concreta**: codigo legado a portar, spec, schema,
  um exemplo ja aprovado do mesmo padrao.
- Existe **gate mecanico** que roda em minutos: testes, typecheck, lint,
  formatter. Se a unica forma de saber se ficou certo e ler, nao delegue.
- O escopo cabe em **poucos globs** (`src/server/orders/*`).
- Melhor ainda se **repete**: N fatias iguais (servico por servico, rota por
  rota). A primeira voce revisa linha a linha; as seguintes ja tem padrao.

## Quando nao delegar

- Spike exploratorio, causa de bug desconhecida, decisao de arquitetura ou de
  API publica, nomeacao. O worker escolhe a primeira coisa plausivel.
- Mudanca espalhada por muitos diretorios, ou que exige install, rede,
  migracao de banco ou deploy: o guard nega, e o worker passa a contornar.
- Quando revisar custa mais do que fazer. Uma mudanca de 10 linhas sai mais
  barata feita direto.

## Antes do primeiro run num projeto

1. **Arvore limpa.** O script recusa arvore suja: o diff do worker tem que
   ser so dele. Commite antes.
2. **Baseline verde.** Rode o gate na arvore limpa so com os comandos:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/agy_worker.py" gate TASK.json --baseline
   ```
   Gate vermelho antes de comecar e o pior caso: o worker nao tem o que
   consertar e vai procurar o gate.
3. **Nenhum `.agents/hooks.json` no repo.** O agy le um arquivo de hooks por
   workspace; o script nao sobrescreve o seu e recusa.
4. **Os hooks tem que carregar.** O veredito falha com "hooks nao carregaram"
   se nenhum `SessionStart` chegou. A causa **nao e conhecida**: nunca
   aconteceu nos testes, e os hooks dispararam headless ate em pastas fora de
   `trustedWorkspaces`. Hipoteses, nenhuma testada: `hooks.json` invalido,
   hooks desligados nesta versao do agy, confianca no workspace. Diga isso ao
   usuario; abrir `agy` interativo uma vez na pasta e uma sugestao, nao um
   diagnostico. Nao edite `~/.gemini`.

## Escrevendo a task

Um JSON **fora da arvore** (o scratchpad, ou
`$(git rev-parse --git-path agy-worker)/tasks/`), senao ele mesmo suja a arvore.
Uma task completa de exemplo esta em `task.example.json`, ao lado desta skill.

| campo | o que e |
|---|---|
| `prompt` ou `prompt_file` | o enunciado (arquivo relativo ao JSON) |
| `scope` | globs relativos a raiz; `*` atravessa `/`. Unica coisa que o worker pode escrever |
| `gate.forbid` | regex contra as linhas **adicionadas**: `any`, `@ts-ignore`, `.skip(` |
| `gate.format` | o ponto do formatter. `{files}` vira os arquivos do escopo alterados |
| `gate.checks` | lint, typecheck, testes estreitos. Todos tem que sair 0 |
| `report_schema` | opcional; o padrao pede `status`, `files_changed`, `checks_run`, `divergences`, `out_of_scope_needs` |
| `side_effects` | globs que ferramentas reescrevem sozinhas (`nx.json`); toleradas, mas listadas no veredito |
| `model` | padrao `gemini-3.8-flash-high`; validado contra `agy models` antes de rodar |
| `timeout`, `gate_timeout`, `max_gate_attempts` | `30m`, 900 s por comando, 5 |
| `allow_paths`, `deny_commands`, `min_quota` | caminhos extra de leitura, regex extra de comando negado, quota minima (0.05) |

O prompt:

- **Nomeie a fonte da verdade e mande ler inteira antes de escrever**, com os
  caminhos. Aponte um exemplo ja aprovado do mesmo padrao: copiar padrao o
  Flash faz bem; inferir padrao, nao.
- **Liste as mudancas obrigatorias e diga "so elas"**: sem refatorar, renomear,
  reordenar ou "melhorar".
- **Nomes exatos** dos arquivos a criar. Regras de estilo que o formatter nao
  pega.
- **Aponte caminhos em vez de colar arquivos.** O prompt vai num argumento de
  linha de comando; o script recusa acima de 100 KB.
- **Nao repita** escopo, gate, proibicoes nem o pedido de divergencias: o
  script anexa um bloco "Operating rules" com tudo isso, gerado da task. Leia
  o `prompt.md` no run dir se quiser ver o que o worker recebeu.

O gate:

- **Coloque o formatter em `format`.** Sem ele no gate o Gemini pula
  formatacao, visto. Um `grep` de espaco no fim da linha nao substitui
  formatter: no lab ele deixou passar linha em branco sobrando no fim do
  arquivo.
- **Comandos rapidos e deterministicos.** Falha nunca e reaproveitada (cada
  tentativa roda de novo), mas teste flaky queima tentativas.
- Os comandos rodam com `AGY_WORKER_GATE=1` no ambiente, caso um deles precise
  saber que e o gate e nao o worker rodando o mesmo comando.

## Rodando

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/agy_worker.py" delegate /caminho/TASK.json
```

Pode passar dos 10 minutos do Bash: rode com `run_in_background` e espere a
notificacao. **Enquanto o run durar, nao edite nada nessa arvore** (nem
formatter, nem `git checkout`): o veredito atribui toda mudanca ao worker, e
uma edicao sua conta como dele ou reprova o run por "fora do escopo". Se
precisar continuar trabalhando, delegue num `git worktree` separado. O veredito sai em stdout e em `<run_dir>/verdict.json`; o
`run_dir` e impresso na primeira linha do stderr.

**Uma fatia por vez por worktree.** Arvore limpa e um `hooks.json` por
workspace serializam os runs. Para paralelizar, um `git worktree` por fatia,
cada um com seu estado em `git rev-parse --git-path agy-worker`. Isso **nao foi
testado**: diga ao usuario que e a primeira vez, se for fazer.

## Lendo o veredito

Saida 0 = ok, 1 = o run falhou, 2 = recusado antes de rodar (nada rodou,
nenhuma quota gasta). `ok: false` sempre vem com `failures`, cada um dizendo
qual checagem pegou:

| falha | por que existe |
|---|---|
| print timeout do agy | o agy sai 0 com saida parcial quando o tempo acaba |
| structured_output nulo | o agy devolve `SUCCESS` e exit 0 sem relatorio |
| stdout vazio, `rc != 0`, `status != SUCCESS` | o basico, que o exit code sozinho nao diz |
| denied_actions / auto-negada | acao recusada sai 0 |
| hooks nao carregaram | sem `SessionStart` o run nao teve guard rail nenhum |
| HEAD mudou | um commit ou checkout passou pelo guard |
| gate falhou no estado final | o gate e rodado de novo sobre a arvore como ficou, salvo se o ultimo gate verde do hook foi exatamente nesse estado |
| fora do escopo | `git status` depois do run; ve arquivo rastreado e nao rastreado, **nao** arquivo ignorado pelo git |
| config, hooks ou flags do git mudaram | escrita no `.git` que faria o proprio git do script rodar codigo, ou esconderia mudanca do `git status` |
| worker se declarou partial/blocked | o proprio relatorio dele |

Leia tambem os `warnings`: arquivos ignorados pelo git criados ou alterados
(o gate escreve alguns, como `.eslintcache`; um `.env` novo nao e do gate),
versao do agy diferente da testada, `guard_denials` (tentativas de sair do escopo;
varias seguidas quase sempre e enunciado ambiguo ou gate impossivel),
`side_effects` (reverta se nao forem desejados) e processos novos com cwd no
repo que ficaram vivos (o script lista e **nao** mata).

Em falha o diff **fica na arvore**, sem commit e sem revert. Decida voce:
aproveitar e terminar a mao, ou reescrever a task e descartar o diff. Nao
re-delegue a mesma task sem mudar nada nela: o mesmo enunciado tende a dar o
mesmo erro.

## Revisao: obrigatoria depois de todo run, inclusive os ok

O gate prova o que ele mede, e so isso. Antes de aceitar:

1. Leia `git diff HEAD` inteiro **lado a lado com a fonte da verdade**, nao
   so contra o enunciado.
2. Confira cada item de `divergences` e de `out_of_scope_needs`. Lista vazia
   nao e prova de que nao ha divergencia.
3. Procure o que o Gemini faz e gate nenhum pega, todos ja vistos: alias ou
   shim inventado com nome plausivel (`NotFoundException`), "conserto" de
   efeito colateral fora do escopo, divergencia de comportamento nao
   reportada, `import` dentro de funcao, linha em branco sobrando.
4. Testes portados: estao todos os casos do original? Algum assert ficou mais
   fraco? O numero de casos bater nao prova que sao os mesmos casos.
5. `report.checks_run` e autodeclarado. So o gate conta.
6. Commit e seu (ou do usuario), nunca do worker.

## Segunda opiniao, somente leitura

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/agy_worker.py" review --diff HEAD~1 --prompt-file /scratchpad/pergunta.md
```

A pergunta vai num arquivo fora da arvore: texto livre na linha de comando
quebra com aspas, parenteses ou `;`.

Roda com `--mode plan`, sem `--dangerously-skip-permissions`, com os mesmos
guards de caminho e escopo vazio, e confere que a arvore nao mudou. O diff vai
no prompt porque o revisor nao roda comando. Serve como segundo par de olhos
barato sobre um diff seu ou do worker. Cada finding traz `evidence`: confira no
codigo antes de agir, porque o numero de linha pode vir errado. E opiniao, nao
veredito.

## O que os guards sao, e o que nao sao

Sao um quebra-molas para um modelo cooperativo que se perde, nao um sandbox.
O `--sandbox` do agy nao confinou escrita nenhuma no lab. Um comando que monta
o caminho em tempo de execucao (`python3 -c`, `node -e`) passa pelos guards. A
checagem de escopo pos-run pega o que ele escrever em arquivo rastreado ou
novo nao ignorado dentro do repo; arquivo ignorado novo ou alterado vira so
aviso; dentro de diretorio ignorado (`node_modules/`, `dist/`) e fora do repo,
nada pega. E o worker herda o seu ambiente: `env` e
`printenv` sao negados, mas `python3 -c 'import os; ...'` nao. Nao delegue com
segredo em variavel de ambiente que o worker nao deva ver.
