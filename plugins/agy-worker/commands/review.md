---
description: Segunda opiniao somente leitura do Gemini pelo agy (--mode plan, relatorio com schema)
argument-hint: [--diff HEAD~1] [--model slug] <o que revisar>
---

Rode:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/agy_worker.py" review $ARGUMENTS
```

Sem `--diff`, o revisor so le arquivos; passe o intervalo quando a pergunta for
sobre uma mudanca.

Ao reportar: o veredito e de um modelo mais barato e serve de segundo par de
olhos, nao de decisao. Para cada finding, confira o `evidence` no codigo antes
de repassar, porque o numero de linha pode vir errado. Diga quais voce confirmou
e quais nao.
