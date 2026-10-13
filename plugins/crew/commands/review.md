---
description: Segunda opiniao somente leitura do Gemini pelo agy (--mode plan, relatorio com schema), de um modelo gratis pelo opencode, ou do GitHub Copilot CLI (Auto) sem shell nem escrita
argument-hint: [--backend agy|opencode|copilot] [--diff HEAD~1] [--model slug] <o que revisar>
---

Leia antes, se ainda nao leu nesta sessao, a skill do backend: `crew:agy`
(padrao), `crew:opencode` ou `crew:copilot`. Rode:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew.py" review [--backend agy|opencode|copilot] [--diff HEAD~1] [--model slug] --prompt-file /caminho/pergunta.md
```

Nao cole `$ARGUMENTS` cru na shell: a pergunta e texto livre, e parenteses,
aspas, `;` ou crase nela quebram ou mudam o comando. Escreva a pergunta num
arquivo fora da arvore (o scratchpad) e passe com `--prompt-file`; so as opcoes
(`--backend`, `--diff`, `--model`) vao na linha. Se for o primeiro `delegate`
ou `review` da sessao, pergunte antes ao usuario: o codigo vai para a Google
(agy), para o provedor do modelo do Zen (opencode) ou para a GitHub (copilot);
no agy gasta a quota dele, no copilot os AI credits (0,41 num review pequeno,
n=1).

Sem `--diff`, o revisor so le arquivos; passe o intervalo quando a pergunta for
sobre uma mudanca.

Ao reportar: o veredito e de um modelo mais barato e serve de segundo par de
olhos, nao de decisao. Para cada finding, confira o `evidence` no codigo antes
de repassar, porque o numero de linha pode vir errado. Diga quais voce confirmou
e quais nao.
