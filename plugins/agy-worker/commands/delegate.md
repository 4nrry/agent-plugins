---
description: Delega uma fatia bem delimitada ao Gemini pelo agy, sob guard rails e gate, e devolve um veredito JSON
argument-hint: <task.json> [--model slug] [--no-quota-probe]
---

Leia a skill `agy-worker` antes, se ainda nao leu nesta sessao: ela diz se esta
fatia deve ser delegada e como a task tem que estar escrita.

Rode, com `run_in_background: true` porque o run pode passar de 10 minutos:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/agy_worker.py" delegate '<task.json>' [--model slug] [--no-quota-probe]
```

Monte a linha a partir de `$ARGUMENTS`; nao cole `$ARGUMENTS` cru na shell.
O caminho da task vai entre aspas simples, como um argumento so (pode ter
espaco). Se for o primeiro `delegate` ou `review` da sessao, pergunte antes ao
usuario: o codigo vai para a Google e gasta a quota dele.

Quando terminar:

1. Saida 2 = recusado antes de rodar. Mostre o motivo ao usuario; nada rodou.
2. Leia o veredito (stdout, e `verdict.json` no run dir). Reporte `ok`,
   `failures`, `warnings` e `guard_denials` sem suavizar.
3. **Revise o diff mesmo com `ok: true`**: `git diff HEAD` contra a fonte da
   verdade, seguindo a secao de revisao da skill. Nao commite antes disso, e
   nao commite sem o usuario pedir.
