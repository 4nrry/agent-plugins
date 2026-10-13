---
description: Delega uma fatia bem delimitada a um worker (agy com Gemini, opencode com modelo gratis do Zen, ou GitHub Copilot CLI sem shell), sob guard rails e gate, e devolve um veredito JSON
argument-hint: <task.json> [--backend agy|opencode|copilot] [--model slug] [--no-quota-probe]
---

Leia antes, se ainda nao leu nesta sessao, `${CLAUDE_PLUGIN_ROOT}/shared/delegate.md`
(se esta fatia deve ser delegada e como a task tem que estar escrita) e a skill
do backend: `crew:agy` (padrao), `crew:opencode` ou `crew:copilot`.

Rode, com `run_in_background: true` porque o run pode passar de 10 minutos:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew.py" delegate '<task.json>' [--backend agy|opencode|copilot] [--model slug] [--no-quota-probe]
```

`--backend` sobrepoe o campo `backend` da task (padrao `agy`). `opencode` so
quando a quota do agy acabou ou para capacidade extra gratis, e diga ao usuario
que o guard do shell e mais fraco. `copilot` gasta AI credits a cada run, nao
tem shell e so aceita `--model auto`. `--no-quota-probe` so vale para o agy.

Monte a linha a partir de `$ARGUMENTS`; nao cole `$ARGUMENTS` cru na shell.
O caminho da task vai entre aspas simples, como um argumento so (pode ter
espaco). Se for o primeiro `delegate` ou `review` da sessao, pergunte antes ao
usuario: o codigo vai para a Google (agy), para o provedor do modelo do Zen
(opencode) ou para a GitHub (copilot); no agy gasta a quota dele, no copilot
os AI credits. No copilot, reporte `copilot.usage.ai_credits` do veredito.

Quando terminar:

1. Saida 2 = recusado antes de rodar. Mostre o motivo ao usuario; nada rodou.
2. Leia o veredito (stdout, e `verdict.json` no run dir). Reporte `ok`,
   `failures`, `warnings` e `guard_denials` sem suavizar.
3. **Revise o diff mesmo com `ok: true`**: `git diff HEAD` contra a fonte da
   verdade, seguindo a secao de revisao do documento comum. Nao commite antes
   disso, e nao commite sem o usuario pedir.
