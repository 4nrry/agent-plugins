# Game Facts

O agente responde sobre jogo com a memoria de treino dele, que tem data. Jogo
tem patch. O resultado e "o padrao de `DeathPenalty` e X" dito com cara de fato,
sobre uma versao que nao esta instalada aqui.

A saida obvia e o usuario digitar a versao em todo prompt — "palworld 1.0.4",
toda vez, para todo jogo. Este plugin existe para tornar isso desnecessario: a
versao esta no disco, entao ela sai do disco.

## Componentes

| componente | o que faz |
|---|---|
| `hooks/inject-game-version.sh` | `UserPromptSubmit`. Casa o prompt contra os jogos instalados e injeta appid, buildid e data. Falha aberto. |
| `scripts/steam_games.py` | O detector, o casamento de nome e a URL de notas oficiais, isolados para serem testaveis. `--self-test`, `--json`, `--match-stdin`. |
| `skills/game-versions/` | O contexto inteiro: como fixar versao, onde achar a de marketing, jogo fora da Steam, e a regra de que o arquivo local ganha. |

## Por que hook, e nao so skill

Medicao deste repositorio, no plugin `agent-fleet`: trigger por `description`
disparou em **2 de 30** execucoes que deveriam disparar, com recall por query
entre 0,00 e 0,33, e nenhuma reescrita melhorou o score retido — registros em
[`bench/plugins/agent-fleet/results/2026-08-06-trigger-eval/`](../../bench/plugins/agent-fleet/results/2026-08-06-trigger-eval/).

Skill que depende de ser lembrada nao e lembrada. Uma skill nova aqui falharia
do mesmo jeito, e o usuario continuaria digitando a versao no prompt — que e
exatamente o problema que o plugin recebeu para resolver. Entao o gatilho e
casamento mecanico de string, nao persuasao do modelo.

## A armadilha que o plugin marca

**`buildid` nao e a versao de marketing.** O `.acf` da Steam nao guarda `1.0.4`
em lugar nenhum:

```
1623730  Palworld                   buildid=25094871   atualizado 2026-09-07
2394010  Palworld Dedicated Server  buildid=25080279   atualizado 2026-09-07
```

O jogador ve `v1.0.4.102642`. Nao ha formula entre os dois numeros. Nesta
maquina a versao de marketing so apareceu porque o **servidor** imprime no boot
(`journalctl --user -u palworld | grep 'Game version is'`) — para um jogo
comum, nem isso existe.

Por isso o hook injeta o buildid e uma instrucao explicita de **nao converter**
um no outro. Um numero de versao inventado sai plausivel, e plausivel e pior do
que ausente.

## Onde o agente busca, quando o disco nao basta

O disco diz **qual** build esta instalada. Nao diz o que mudou nela. Para isso
o hook injeta, junto, a URL das notas oficiais do proprio jogo — montada a
partir do `appid` que ele ja tem:

```
https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=1623730&count=5&maxlength=1500
```

Publico, sem chave, e **datado**. Verificado em 2026-09-07: devolveu
`v1.0.4: Balance Adjustments & Bug Fixes`, autor `pocketpair_dev`, do mesmo dia
do `LastUpdated` do manifesto — fechando a ponte entre `buildid=25094871` e o
`v1.0.4` que o jogador ve. O corpo trazia ate chave de config nova
(`Added "Fish Behavior During Fishing Minigames" to World Settings`).

Duas coisas medidas junto: o feed **mistura imprensa** com anuncio do estudio
(PC Gamer e PCGamesN aparecem lado a lado com o `pocketpair_dev`), entao a skill
publica o `select(.feedname=="steam_community_announcements")` junto; e
**ferramenta nao tem feed** — o appid do Palworld Dedicated Server devolve lista
vazia, as notas dele saem no appid do cliente.

O hook **nao** chama essa URL. Ele roda a cada prompt, e rede ali seria
latencia em todo prompt, inclusive nos que nao mencionam jogo nenhum. Ele monta
e entrega; quem busca e o agente, se a pergunta exigir.

A hierarquia completa fica na skill. O resumo: arquivo no disco > saida do
proprio jogo > notas oficiais > doc do estudio > wiki > blog de hosting. Wiki
fica em quinto por um motivo mecanico e nao por desprezo — **pagina de wiki
quase nunca diz de que versao fala**, e ela e boa justamente para o que patch
nao toca (onde acha um item, breeding) e ruim para numero e valor padrao, que e
o que costuma estar sendo perguntado.

Corolario que tambem esta no texto: cliente e servidor dedicado sao appids
diferentes que atualizam em momentos diferentes. Nesta maquina, em 2026-09-07,
o cliente subiu as 00:39 e o servidor as 01:02.

## Casamento por frase inteira

O nome do jogo tem que aparecer no prompt **inteiro e com borda nao
alfanumerica**, nao por token:

| prompt | casa | por que |
|---|---|---|
| `como configura guilda no palworld` | `Palworld` | minusculo, borda por espaco |
| `no-palworld-branch` | `Palworld` | hifen conta como borda |
| `palworldish nao e o jogo` | nada | borda direita falha |
| `it takes two hours to compile` | `It Takes Two` | frase inteira, ainda que noutro sentido |
| `this takes two hours` | nada | por token, `two` dispararia aqui |

A ultima linha e o motivo do desenho. `It Takes Two` casado por token faria
qualquer prompt de matematica injetar contexto de jogo.

Nomes com menos de 4 caracteres sao ignorados, e runtimes da Steam, Proton e
redistribuiveis sao filtrados **por nome**, nao por appid — appid novo de
Proton nasce a cada versao, e uma lista de ids envelhece calada.

## Estado da medicao

**Nao ha run records.** Pela regra zero do
[`bench/PROTOCOL.md`](../../bench/PROTOCOL.md), alegacao de melhoria sem
registro e marketing, entao esta versao nao faz nenhuma. Em particular **nao
esta medido**: com que frequencia o hook dispara em uso real, quantos disparos
mudaram a resposta, e a taxa de falso positivo em prompt sem jogo. As regras de
casamento acima vem do raciocinio, nao de um eval.

O que existe e comportamento verificado, que `just check` reexecuta:

- `steam_games.py --self-test`: **25 asserções** — parse dos cinco campos,
  filtro de runtime e Proton, ordenacao, `StateFlags` integro contra pendente,
  as seis linhas da tabela de casamento acima, e a montagem da URL de notas
  pelo appid.
- O `curl`+`jq` publicado na skill foi executado como esta escrito, contra
  `appid=1623730` e `appid=105600`: filtra a imprensa e devolve so o estudio.
- Exercitado contra a biblioteca real desta maquina: 15 appmanifests no disco,
  **7 jogos** reportados, 8 runtimes/Proton filtrados.

O que falta medir e o que decide se o plugin serve: se o usuario para de digitar
a versao no prompt.

## Cobertura

Steam, porque o formato e estavel e foi verificado. Heroic, flatpak, RetroDECK e
Lutris estao na skill como **onde procurar**, com o formato explicitamente
marcado como nao verificado. Escrever parser para um launcher sem jogo instalado
seria prosa nao testada — o mesmo defeito que o plugin existe para evitar.
