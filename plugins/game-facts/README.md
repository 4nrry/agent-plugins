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

## A hierarquia de fonte, medida

A primeira versao desta secao era opiniao: uma lista unica com wiki no quinto
degrau e proibida para numero. Um levantamento de **80 fontes** sobre 10
arquetipos de pergunta derrubou tres afirmacoes dela, e a skill foi reescrita
com os dados.

| tipo | n | com data | declara versao | pos-patch |
|---|---|---|---|---|
| blog-hosting | 22 | 77% | 64% | **0** |
| wiki | 16 | **88%** | 56% | **3** |
| site-de-jogos | 14 | **100%** | 79% | 2 |
| oficial | 12 | 67% | **92%** | 3 |
| forum | 12 | 100% | 17% | 0 |
| reddit | 2 | 0% | 0% | 0 |
| **geral** | **80** | **84%** | **59%** | **8** |

O que caiu:

- **"Tem data" era o sinal errado.** 84% tinham data e 90% eram pre-patch. O que
  discrimina e `data > ultimo patch do subsistema`: 10%, nao 84%.
- **Concordancia nao eleva confianca.** Voto de maioria resolveu **0 de 41**
  contradicoes, e o maior aglomerado do corpus eram cinco dominios repetindo um
  numero que uma sexta fonte chama de mito refutado — uma fonte copiada cinco
  vezes. Triangulacao so conta entre tipos diferentes.
- **Volume nao e rigor.** A categoria com 14 fontes teve o **pior** veredito; a
  com 10 fontes, das quais 3 pos-patch, foi a unica com uma afirmacao
  **confirmada**. O limiar util e >= 3 fontes pos-patch, teto de ~6 no total.
- **Wiki nao merecia o quinto degrau.** Data em 88% das paginas, acima de blog
  de hosting e acima da propria oficial; 3 das 8 paginas pos-patch do corpus,
  empatada com a oficial, contra **0 de 22** dos blogs de hosting. E foi o unico
  tipo com proveniencia de versao **por conteudo** — o que permitiu rejeitar a
  propria wiki em dois casos. A regra certa e por pagina: *use um numero de wiki
  se e so se a pagina exibir last-edited E (tag de versao OU data pos-patch)*.
- **"Oficial primeiro" era largo demais.** Oficial venceu em versao (92%) e
  perdeu em data (67%). E **0 das 12 fontes oficiais respondeu uma pergunta
  meta** — a doc da a mecanica e o aviso de carga, e deliberadamente nunca da o
  valor recomendado. O enunciado correto: *a nota de patch e o unico relogio e a
  unica arbitra de contradicao; o dominio oficial nao e a resposta.*

## Video: o buraco da camada de comunidade

O levantamento mediu o degrau de comunidade como quase inalcancavel: Reddit sem
uma thread real em 10/10 categorias, `site:reddit.com` substituido por
`steamcommunity.com` em >=7 delas, Fandom com HTTP 402 em 2/2. Build, rota e
tatica vivem muito em video, e `WebFetch` numa pagina de video devolve so a
navegacao.

A skill documenta o caminho condicional (`yt-dlp` no PATH, senao a fonte e
inalcancavel e isso e a resposta), com quatro pontos medidos em 2026-09-07,
reproduzindo e corrigindo [#6](https://github.com/4nrry/agent-plugins/issues/6):

- A forma estreita `--sub-lang en` e **dependente do video**, nao quebrada.
- Afirme saida nao-vazia: as rotas sem instalacao dao **200 com corpo vazio**.
- Junte na **fronteira de evento**. O defeito do join ingenuo tambem e por
  trilha: uma tinha 0 de 6 eventos com espaco nas bordas e perdeu 5 de 39
  palavras; outra tinha 338 de 677 e perdeu zero.
- A dependencia **deriva**: o aviso de 2026-08-18 era runtime JS ausente; hoje,
  mesma maquina e mesma versao, o aviso e `impersonation`.

Video entra no ramo META e **nunca no FACTUAL** — nao por corrupcao de ASR
(nomes proprios sobreviveram: `Anubis` 28x num guia medido), mas porque a
transcricao **nao tem ancora de versao**. Ela traz numeros sem dizer a que build
pertencem, entao falha a tripla `(valor, versao, data)` pela coluna do meio. E a
busca do YouTube nao ordena por recencia: os dois primeiros resultados de uma
consulta de build eram de 2024-10 e 2025-01, anteriores ao 1.0.

O que subiu no lugar e o **passo zero**: ler o changelog primario e listar o que
tocou o subsistema antes de abrir qualquer guia. Sozinho, invalidou conteudo em
**10 de 10** categorias, com 53 itens nomeados — e cerca de um quarto eram
correcoes de bug, onde a fonte mediu com honestidade uma build quebrada. Nenhum
grau de qualidade editorial pega isso; so o diff do changelog pega.

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

- `steam_games.py --self-test`: **28 asserções** — parse dos cinco campos,
  filtro de runtime e Proton, ordenacao, `StateFlags` integro contra pendente,
  as seis linhas da tabela de casamento acima, e a montagem da URL de notas
  pelo appid.
- O `curl`+`jq` publicado na skill foi executado como esta escrito, contra
  `appid=1623730` e `appid=105600`: filtra a imprensa e devolve so o estudio.
- Exercitado contra a biblioteca real desta maquina: 15 appmanifests no disco,
  **7 jogos** reportados, 8 runtimes/Proton filtrados.

- Levantamento de fontes, 2026-09-07: 22 agentes, 10 arquetipos de pergunta,
  **80 fontes** com metadado por fonte, verificacao adversarial contra as notas
  oficiais da v1.0.4. Produziu a tabela acima e as regras da skill.

**Ressalvas do levantamento, que estao tambem na skill:** um jogo, um dia, horas
depois de um patch — o que exagera a obsolescencia contra um dia comum. As 10
perguntas eram META ou FACTUAL e **nenhuma era LOCAL**, entao o ramo local da
skill e derivado dos tres testes, nao medido. `sensibilidade_versao` deu "alta"
em 10/10, entao nao ha correlacao alta-contra-baixa a extrair. O verificador foi
instruido a marcar obsoleto na duvida, entao 10/10 e o vies pedido, nao um
achado — o que vale sao os 53 itens nomeados, cada um checavel. E o metadado de
fonte foi julgado por agente, nao conferido a mao pagina por pagina.

### Primeiro uso real, 2026-09-08

Uma pergunta de verdade — quais Pals farmam "organ" na base — rodada como
fan-out de 11 agentes seguindo as regras da skill. **23 fontes, zero
posteriores ao patch** do dia anterior. O que o uso mostrou:

- **O passo zero pagou, mas nao onde se esperava.** Ele nao achou nada sobre o
  item em 1.0.1-1.0.4. O valor foi matar duas fontes que entrariam como fato
  (foruns de 2024 e 2025, anteriores a um rework que o changelog de 1.0
  nomeia) e rebaixar uma terceira que declara versao pre-1.0. Sem ele, quatro
  listas teriam saido com confianca identica.
- **O ramo LOCAL foi a parte mais util, e inverteu a recomendacao.** A chave
  que governa o subsistema perguntado estava a 1.5x no `.ini` da maquina, e
  outra chave a 2.0x buffava a rota concorrente. Nenhuma fonte externa poderia
  ter dito isso. O disco tambem encerrou um conflito que a web deixou aberto.
- **Um degrau da hierarquia simplesmente nao existe para esse jogo.** Nao ha
  documentacao oficial de mecanica — so patch notes. A hierarquia desaba de
  "changelog oficial" direto para "wiki comunitaria", e toda a substancia vive
  num degrau so. Os buracos da resposta nao sao falha de busca: o dado nao
  existe publicado.

E duas falhas da propria skill, ambas corrigidas nesta versao:

1. **A cerca de patch nao tinha saida.** Com o patch de ontem, 18 de 18 fontes
   falharam o criterio de recencia enquanto o changelog auditado provava que
   nada relevante mudara. A regra forcava a resposta a soar mais insegura que a
   evidencia. Agora a cerca se satisfaz por fonte posterior **ou** por auditoria
   negativa, com o rotulo mais fraco que essa via autoriza.
2. **Nao havia degrau para fonte unica disfarcada de consenso.** Uma tabela
   inteira saiu de um dominio so mais "sintese de busca" — o buscador resumindo
   paginas que copiaram a mesma origem. Quem pegou foram os verificadores, nao
   a skill. Agora ha teste de origem contra dominio, e "resumo de buscador nao
   e fonte" e regra explicita.

Custo: o bloco injetado foi de 2143 para 2760 bytes.

O que falta medir e o que decide se o plugin serve: se o usuario para de digitar
a versao no prompt.

## Cobertura

Steam, porque o formato e estavel e foi verificado. Heroic, flatpak, RetroDECK e
Lutris estao na skill como **onde procurar**, com o formato explicitamente
marcado como nao verificado. Escrever parser para um launcher sem jogo instalado
seria prosa nao testada — o mesmo defeito que o plugin existe para evitar.
