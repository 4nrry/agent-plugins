---
description: Segunda opiniao somente leitura do Gemini pelo agy (--mode plan, relatorio com schema), de um modelo gratis pelo opencode, ou do GitHub Copilot CLI (Auto) sem shell nem escrita
argument-hint: [--backend agy|opencode|copilot] [--diff HEAD~1] [--model slug] <o que revisar>
---

Rode:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/agy_worker.py" review [--backend agy|opencode|copilot] [--diff HEAD~1] [--model slug] --prompt-file /caminho/pergunta.md
```

Nao cole `$ARGUMENTS` cru na shell: a pergunta e texto livre, e parenteses,
aspas, `;` ou crase nela quebram ou mudam o comando. Escreva a pergunta num
arquivo fora da arvore (o scratchpad) e passe com `--prompt-file`; so as opcoes
(`--backend`, `--diff`, `--model`) vao na linha. `--backend opencode` (padrao
`agy`) e para quando a quota do agy acabou: sem modo plan, o plugin de guard
nega toda escrita e todo comando de shell. `--backend copilot` gasta AI
credits (0,41 num review pequeno, n=1), so aceita `--model auto` e roda sem
shell nem `apply_patch`, com o hook negando toda escrita. Se for o primeiro `delegate` ou `review` da
sessao, pergunte antes ao usuario: o codigo vai para a Google (agy), para o
provedor do modelo do Zen (opencode) ou para a GitHub (copilot); no agy gasta a
quota dele, no copilot os AI credits.

Sem `--diff`, o revisor so le arquivos; passe o intervalo quando a pergunta for
sobre uma mudanca.

Ao reportar: o veredito e de um modelo mais barato e serve de segundo par de
olhos, nao de decisao. Para cada finding, confira o `evidence` no codigo antes
de repassar, porque o numero de linha pode vir errado. Diga quais voce confirmou
e quais nao.
