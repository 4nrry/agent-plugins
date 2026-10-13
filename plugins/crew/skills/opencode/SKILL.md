---
name: opencode
description: Especificos do backend opencode do plugin crew - modelos gratis do Zen e os termos de dados de cada um, guard do shell mais fraco que o do agy, gate como loop externo que retoma a sessao, o $schema que o opencode grava no opencode.json do cwd. Use quando for delegar uma fatia ou pedir review pelo opencode, ou quando a quota do agy acabou.
---

# crew pelo opencode

Antes de tudo, leia `${CLAUDE_PLUGIN_ROOT}/shared/delegate.md` se ainda nao leu
nesta sessao: quando delegar e quando nao, como escrever a task, o gate, como
ler o veredito, a revisao obrigatoria do diff contra a fonte da verdade, os
arquivos de segredo e a pergunta ao usuario antes do primeiro run. Aqui esta
so o que e do opencode.

## Quando usar

O agy continua o primario. Use `"backend": "opencode"` (ou `--backend
opencode`) quando a quota do agy acabou (o preflight do agy recusa com a data
de renovacao) ou para rodar fatias extras sem gastar quota nenhuma. Requer o
`opencode` no PATH ou em `~/.opencode/bin`; testado so no **1.19.0** (outra
versao vira aviso).

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew.py" delegate /caminho/TASK.json --backend opencode [--model slug]
```

## Modelos e dados

- Padrao: `opencode/longcat-2.5-preview-free`, o unico exercitado com o plugin
  de guard e o loop externo. O modelo e validado contra `opencode models`.
- longcat, space-bunny e step-5 sao de **retencao zero** pelos docs do Zen.
- **muse-spark treina com o prompt.** So em projeto pessoal, e so se o usuario
  aceitar explicitamente.
- No unico bench de qualidade (n=1, porte de um servico CJS com 16 casos),
  longcat, space-bunny e muse-spark passaram o gate; o longcat manteve as
  assercoes um a um, o space-bunny moveu metade para helpers; o longcat foi o
  mais lento.

## O guard e mais fraco: diga isso ao usuario

As regras de caminho, escopo e comando sao as mesmas (um plugin do opencode
gerado no run dir manda cada chamada para `crew.py hook oc-pre`, que aplica a
politica do agy), mas:

- nao ha allowlist de ferramenta no nivel do processo nem modo plan;
- tudo depende de o plugin carregar (sem o `SessionStart` dele, o run falha);
- os modelos do opencode escrevem mais pelo shell, entao o backend nega tambem
  `cp`, `mv`, `touch`, `mkdir`, `rm`, `truncate`, `patch`.

Nao use opencode numa fatia em que um escape custe caro.

## Gate e relatorio

- **O gate e um loop externo**: cada tentativa e um `opencode run -s
  <sessao>` com a saida do gate. `max_gate_attempts` conta runs.
- **O relatorio e texto**: o ultimo objeto JSON da mensagem final. Pode faltar
  campo; o loop pede de novo.
- Sucesso vem dos eventos JSON (nenhum `error`, ultimo `step_finish` com
  `reason=stop`) mais o gate; exit 0 nao conta.

## cwd, opencode.json e $schema

- O opencode grava `"$schema"` no `opencode.json` do cwd, mesmo com `--dir`.
  O script guarda os bytes de `opencode.json`/`.jsonc` antes de qualquer
  processo do opencode e os restaura depois de cada um (vira aviso); o
  preflight roda num diretorio temporario vazio.
- **Nao cubra `opencode.json` no `scope`**: a task e recusada.
- O config do run vai so pelo `OPENCODE_CONFIG_CONTENT` daquele processo
  (substitui um que o usuario tenha no ambiente); nada entra na arvore nem em
  `~/.config/opencode`.
- O worker carrega o `~/.claude/CLAUDE.md` do usuario, como um subagente
  nativo. `"disable_claude_code": true` na task desliga.

## Falhas que so o opencode tem

| falha | por que existe |
|---|---|
| plugin de guard do opencode nao carregou | sem `SessionStart` o run nao teve guard rail nenhum |
| evento `error`, ultimo step sem `reason=stop` | o opencode sai 0 com erro de API ou run cortado |
| relatorio ausente | nenhum objeto JSON na mensagem final, mesmo depois de pedido de novo |

## Review

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew.py" review --backend opencode --diff HEAD~1 --prompt-file /scratchpad/pergunta.md
```

Sem modo plan: escopo vazio e **todo** comando de shell negado pelo plugin.
