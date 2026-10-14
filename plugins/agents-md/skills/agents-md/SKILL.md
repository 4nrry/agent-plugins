---
name: agents-md
description: Escrever, enxugar ou auditar o AGENTS.md (ou CLAUDE.md, GEMINI.md) de um repositorio — o que entra, o que sai, tamanho, onde cada coisa mora, e como checar que o arquivo nao mente sobre o codigo. Cobre os limites de cada ferramenta (Claude Code, Antigravity, Codex), o CLAUDE.md que esconde o AGENTS.md, e um checador mecanico que pega comando inexistente, ponteiro quebrado e arquivo grande demais sem gastar agente. Use quando a tarefa mencionar AGENTS.md, CLAUDE.md, GEMINI.md, .cursorrules, instrucoes do agente, "rules token budget", arquivo de instrucoes desatualizado ou gigante, ou /init.
---

# AGENTS.md que o agente segue

Arquivo de instrucoes e contexto carregado em toda sessao. Cada linha custa
token em toda tarefa, e arquivo inchado faz o agente ignorar justamente a
regra que importa. O teste de toda linha: **se eu tirar isto, o agente erra?**
Se nao erra, sai.

## Entra

- Comandos exatos e que existem: instalar, rodar, o teste mais estreito,
  lint/typecheck, migration. Agente roda o check que estiver listado.
- Como provar que terminou: o comando que da passou/falhou. Sem ele, "parece
  pronto" e o unico sinal que o agente tem.
- Armadilhas que falham em silencio: o comando que passa sem testar nada, a env
  var sem a qual tudo sobe errado, a config que precisa de restart.
- Contratos com outros repos que daqui nao se deduzem: fila/routing key,
  header, formato de ID, porta exposta.
- Convencoes que fogem do padrao da linguagem ou do framework.
- Etiqueta do repo: branch base, nome de branch, squash ou nao, o que rodar
  antes de commitar.
- Decisao de arquitetura com o porque, so quando o codigo nao explica sozinho.
- Mapa curto: onde moram as 3 a 5 coisas que se procuram toda hora.
- Ponteiro com gatilho para o que mora em outro arquivo: "antes de mexer em
  X, leia `<subpasta>/AGENTS.md`" ou o `AGENTS.md` comum acima dos repos.

## Sai

- Arvore de diretorios, lista de endpoints, dump de schema, lista de
  dependencias, descricao arquivo por arquivo. O agente le o codigo.
- Tutorial e documentacao de API: link, nao copia.
- O que muda toda hora: versao, contagem, "ultima atualizacao", estado de
  sprint. E o primeiro trecho a ficar velho.
- Conselho obvio ("escreva codigo limpo", "use tipos").
- Changelog e historia de ticket: o git guarda.
- Instrucao de uma ferramenta so ("use o MCP X primeiro").
- Segredo, URL com token, dado de cliente.

## Forma

- Bullets curtos sob cabecalhos. Paragrafo denso e seguido pior.
- Concreto e verificavel: "rode `npm test -- foo`", nao "teste suas mudancas".
- Tom calmo, com o motivo. `IMPORTANT` em no maximo uma linha; se tudo grita,
  nada se destaca, e modelos atuais aplicam frase agressiva demais.
- Duas instrucoes que se contradizem fazem o agente escolher no chute: revise o
  arquivo da raiz contra os aninhados.
- Nota so para humanos vai em `<!-- comentario -->` de bloco: o Claude Code a
  remove antes de carregar.

## Tamanho e onde mora

| ferramenta | o que le | limite |
|---|---|---|
| Claude Code | `CLAUDE.md`; `AGENTS.md` nativo desde 2.1.277, **so se nao houver `CLAUDE.md` nem `CLAUDE.local.md` na pasta ou acima** | recomenda < 200 linhas; carrega ate 4 MiB |
| Antigravity | `AGENTS.md`, `GEMINI.md`, `.agents/rules/`; **nao le `CLAUDE.md`**; `@arquivo` solto nao e inlinado, so `@[label](path)` | 24 KB por arquivo (corta o resto); 20 mil tokens somando tudo que esta always-on |
| Codex | `AGENTS.override.md` ou `AGENTS.md`, da raiz do git ate o cwd | para de juntar em 32 KiB somados |

- Meta: 60 a 100 linhas e menos de 6 KB. Teto: 150 linhas / 10 KB.
- `@import` nao economiza: o importado tambem carrega no inicio.
- Um arquivo so, `AGENTS.md`, para todas as ferramentas. Um `CLAUDE.md` ou
  `CLAUDE.local.md` na mesma pasta ou acima esconde o `AGENTS.md` do Claude.
- O que vale para parte do codigo vai para um `AGENTS.md` aninhado na
  subpasta (o mais proximo vence). Doc solto em `docs/` so se alguem o audita:
  doc velho engana o agente que o le, e ninguem o confere contra o codigo.
- Procedimento de varios passos vira skill. Regra que nao pode falhar nunca
  vira hook: o arquivo e orientacao, o hook e garantia.
- Arquivo global: o Claude Code le so `~/.claude/CLAUDE.md` (nao ha
  `AGENTS.md` de usuario); o Antigravity le `~/.gemini/config/AGENTS.md` (ou
  `GEMINI.md`). Sao dois arquivos: mantenha um e gere o outro a partir dele.
- O Claude Code procura `AGENTS.md` em todas as pastas acima do cwd; o
  Antigravity e o Codex param na raiz do git. Um `AGENTS.md` comum acima dos
  repos so chega a eles por ponteiro no `AGENTS.md` de cada repo.
- Workspace com varios repos abertos soma os arquivos de todos no Antigravity.
  Abra o repo da tarefa, nao a pasta-mae, antes de cortar arquivo bom.

## Auditar sem torrar uso

1. Checagem mecanica primeiro, de graca:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_agents_md.py" <repo>
   ```

   Aponta: arquivo acima do teto, `npm run X` que nao existe no
   `package.json`, caminho citado em crase que nao existe, palavras de grito,
   `CLAUDE.md`/`CLAUDE.local.md` que escondem o `AGENTS.md`, `GEMINI.md` com
   `@arquivo` que o Antigravity nao expande. Caminho relativo curto pode dar
   falso positivo: confira antes de mexer.
2. Audite contra o codigo da branch padrao do origin, nao o checkout local
   (que costuma estar atrasado): `git archive origin/<padrao> | tar -x -C <dir>`.
3. Para fatos que o script nao alcanca (fila, porta, env var, nome de modulo),
   um agente barato (Haiku) por arquivo, que devolve **so** as afirmacoes
   falsas com `path:linha`. Confira cada apontamento antes de aplicar: o
   verificador acerta muito, mas nao sempre.
4. No Claude Code, `/doctor` sugere cortes e `/doctor prompt-audit` acha
   comando inexistente e contradicao entre arquivos.

## Manter

- Revise no PR que muda comando, porta, fila ou layout. Arquivo velho e pior
  que arquivo nenhum: o agente acredita nele.
- Acrescente uma linha quando o agente repete um erro, quando o review pega
  algo que ele deveria saber, ou quando voce digita a mesma correcao de novo.
- Mudou uma regra? Veja se o comportamento mudou. Se o agente continua
  ignorando, o arquivo esta longo demais ou a frase esta ambigua.
