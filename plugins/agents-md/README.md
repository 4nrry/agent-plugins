# AGENTS.md

Arquivo de instrucoes de agente cresce, envelhece e para de ser seguido. Numa
auditoria de 19 repositorios, os arquivos tinham ate 974 linhas, um deles
estava 159 commits atrasado em relacao ao codigo, e sete eram invisiveis para o
Antigravity porque viviam em `CLAUDE.md`. Este plugin e o checklist que saiu
dessa limpeza, mais um checador que pega o erro barato sem gastar agente.

## Componentes

| componente | o que faz |
|---|---|
| `skills/agents-md/` | O que entra, o que sai, forma, limites por ferramenta, como auditar barato e como manter. |
| `scripts/check_agents_md.py` | Checagem mecanica de um repo: teto de tamanho, `npm run` inexistente, caminho citado que nao existe, grito, `CLAUDE.md` que esconde o `AGENTS.md`, `GEMINI.md` com `@arquivo` que o Antigravity nao expande. `--self-test`. Sai 1 quando aponta algo. |

## O que o checador nao sabe

Caminho citado relativo a outro repo (contrato do backend vizinho, por exemplo)
aparece como inexistente: e falso positivo esperado, confira antes de mexer.
Fila, porta, env var e nome de modulo ficam fora do alcance de um regex; para
esses, a skill descreve um verificador barato por arquivo.

## O que isto nao estabelece

Nao ha run records. Os numeros acima sao da auditoria que originou o plugin,
nao de uma comparacao com e sem a skill; pela regra do `bench/PROTOCOL.md`,
isso proibe qualquer alegacao de melhoria.
