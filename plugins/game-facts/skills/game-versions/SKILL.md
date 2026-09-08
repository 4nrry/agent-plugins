---
name: game-versions
description: Fixar a versao de um jogo instalado antes de responder qualquer coisa sobre mecanica, config, patch, balanceamento ou "melhor setting" — em vez de responder de memoria de treino, que envelhece a cada patch. Cobre appmanifest da Steam (appid, buildid, LastUpdated), por que buildid nao e a versao de marketing, onde achar a versao que o jogador ve, jogo fora da Steam (Heroic, flatpak, RetroDECK) e a regra de que o arquivo de config no disco ganha de qualquer guia. Use quando a tarefa mencionar um jogo, um arquivo de save, um .ini de servidor, patch notes, ou "qual a melhor config para".
---

# Versao de jogo, antes de responder

Sua memoria de treino tem data. Jogo tem patch. Responder "o padrao de
`DeathPenalty` e X" sem saber qual versao esta instalada e chutar com cara de
fato — e patch renomeia chave, muda valor padrao e remove mecanica inteira.

Esta skill existe para que o usuario **nao precise digitar a versao no prompt**.
Ela sai do disco.

## O que a maquina entrega de graca

Um jogo instalado pela Steam tem um `appmanifest_<appid>.acf` em
`~/.local/share/Steam/steamapps/` (ou nas bibliotecas listadas em
`libraryfolders.vdf`). Cinco campos importam:

| campo | o que e |
|---|---|
| `appid` | o id da Steam — chave para SteamDB, patch notes, protocolos |
| `name` | o nome como a Steam o chama |
| `buildid` | **o que identifica o binario no disco** |
| `LastUpdated` | epoch da ultima atualizacao |
| `StateFlags` | `4` = instalado e integro; outro valor = download parcial ou update pendente |

O script empacotado faz isso, filtrando runtimes e Proton:

```bash
"${CLAUDE_PLUGIN_ROOT}"/scripts/steam_games.py          # tabela
"${CLAUDE_PLUGIN_ROOT}"/scripts/steam_games.py --json   # para consumo
```

## A armadilha central: buildid nao e a versao

**O `.acf` nao guarda "1.0.4" em lugar nenhum.** `buildid=25094871` e um
contador da Steam; `v1.0.4.102642` e o que o jogador ve. Nao existe formula
entre os dois, e inventar a correspondencia e o erro mais facil de cometer aqui
— o numero sai plausivel e errado.

Onde a versao de marketing realmente aparece:

- **O proprio jogo, ao subir.** Servidor dedicado costuma imprimir. No
  Palworld: `journalctl --user -u palworld | grep 'Game version is'`.
- **Tela de titulo ou menu de opcoes**, para jogo com interface.
- **Arquivo de versao no diretorio de instalacao** — varia por engine, nao ha
  regra geral.
- **Notas oficiais na Steam**, pelo `appid` — ver a secao abaixo. E a fonte que
  liga o buildid do disco ao numero que o jogador ve.

Se nenhuma dessas estiver disponivel, reporte o `buildid` e diga que a versao de
marketing nao foi determinada. Nao converta um no outro.

## Onde buscar, e em que ordem

Esta secao nao e opiniao: saiu de um levantamento de **80 fontes** sobre 10
arquetipos de pergunta de um jogo so, num dia so. As ressalvas do metodo estao
no fim da secao, e elas importam.

### Passo zero, obrigatorio, antes de abrir qualquer guia

**Leia o changelog primario e liste toda entrada que toca o subsistema da
pergunta**, andando para tras ate o ultimo patch que mexeu nele. Uma a duas
chamadas. No levantamento, so esse passo produziu **53 invalidacoes em 10 de 10
categorias**.

Cerca de um quarto delas eram **correcoes de bug** — a fonte mediu com
honestidade uma build quebrada. Um exemplo do que isso significa: a passiva
`Mercy Hit` nao se aplicava a ataques de Pal montado, e foi corrigida na 1.0.4.
Todo guia de combate de fim de jogo escrito antes disso avaliou aquela passiva
num estado que nao existe mais. **Nenhum grau de qualidade editorial protege
contra isso. So o diff do changelog protege.**

Disso sai a **cerca de patch**: a data do ultimo patch que tocou o subsistema.
Fonte anterior a essa data e suspeita por construcao, por melhor que seja.

### Roteamento, antes de qualquer busca

```
Pede um valor DESTA instancia (chave, estado atual, o que aconteceu aqui)?
  -> LOCAL: leia o arquivo. Zero rede. Fim.
Pede um dado embarcado no jogo (default, nivel, custo, o que mudou)?
  -> FACTUAL
Pede ordenacao, superlativo, rota, ou "vale a pena"?
  -> META
```

Pergunta hibrida — "que valor eu devo usar para X?" — e **FACTUAL** para o
intervalo e a mecanica, e **META** para a recomendacao. Responda os dois
separados e rotulados; nunca funda num paragrafo so.

Tres testes mecanicos para saber se o disco responde:

1. **Divergencia entre instancias.** Dois jogadores no mesmo patch teriam
   respostas diferentes? Sim -> estado local, leia o disco.
2. **Forma da resposta.** E um `chave=valor` ou uma linha de estado? -> local.
   E um superlativo, uma ordenacao, uma porcentagem de mecanica? -> nunca local.
3. **Arquivo dono.** O dado e escrito pelo servidor/jogador (ini, sav, log) ou
   embarcado pelo desenvolvedor (pak)? So o primeiro grupo esta no disco.

O caso que define a fronteira: `PalWorldSettings.ini` esta no disco do usuario,
mas "que valores a comunidade recomenda" e META. **Mesmo arquivo, mesma chave,
duas perguntas, dois ramos.** A doc oficial confirma a assimetria pelo lado de
fora — ela da a mecanica e o aviso de carga, e deliberadamente nunca da o valor
recomendado.

### Ramo FACTUAL

1. **Disco local**, se a pergunta e sobre esta instancia.
2. **Nota de patch oficial**, da mais nova para tras. **E o unico relogio.**
3. **Doc oficial**, so para semantica, mecanica e aviso — nunca para "que valor
   usar". Carimbe como doc viva sem timestamp: no levantamento,
   `docs.palworldgame.com` apareceu em 4 categorias e tinha data em **0 delas**.
4. **Pagina de wiki que exiba last-edited E tag de versao.**
5. **Todo o resto**: corroboracao, nunca portador unico de um numero.

Amarras:

- Todo numero sai com a tripla **(valor, versao, data-da-fonte)**. Faltando
  qualquer um dos tres, diga o buraco em vez do numero.
- Fonte que declara a versao V mas tem data anterior ao lancamento de V esta
  **desqualificada**, nao corroborando. Aconteceu em 3 dos 47 selos de versao.
- Prefira API JSON a pagina renderizada por JS — mas **revalide a data que a API
  devolve**: uma consulta do levantamento voltou com a v1.0.4 datada de janeiro
  de 2025, anterior ao proprio 1.0. Oficial tambem devolve data impossivel.

### Ramo META

1. **Changelog primario primeiro**, sempre — passo zero.
2. **Site de jogos com data E versao.** Foi o melhor tipo meta do corpus.
3. **Wiki**, para taxonomia, nomes, estrutura e fluxo. Foi a camada que
   sobreviveu a verificacao em 6 dos 10 vereditos.
4. **Forum e comunidade**, so para "e assim que se comporta de verdade", e
   tratando a data da thread como **piso** do conteudo, nunca como rotulo: uma
   thread de 2024 continha resposta citando dados do 1.0.
5. **Blog de hosting, por ultimo.**

Amarras:

- Toda resposta meta abre com a cerca: *"valido para a build X; fontes de Y a Z;
  N de M anteriores a build X."* No levantamento, essa linha caberia em 10/10.
- Superlativo sem versao e data nao e dito. Uma das categorias devolveu **tres
  combos de passiva mutuamente exclusivos, cada um apresentado como "o
  melhor"**, nenhum reconhecendo os outros.
- Numero comportamental medido pela comunidade e **relato**, nao dado, a menos
  que venha com `n` e metodo. Diferenca que cabe no ruido de uma amostra de ~100
  e folclore.
- Conflito **nao se resolve por maioria**. Ordem de desempate: o changelog
  decide; senao, vence a fonte mais nova que o ultimo patch do subsistema;
  senao, **declare irresolvido e mostre os dois lados**. Deixar uma divergencia
  de pe e a saida correta, nao um consenso sintetizado.

### Video, e o buraco na camada de comunidade

O degrau 4 do ramo META — forum e comunidade — foi medido como **em grande parte
inalcancavel** neste ambiente: Reddit nao devolveu uma thread real em nenhuma das
10 categorias, `site:reddit.com` foi substituido por `steamcommunity.com` em pelo
menos 7 delas, e Fandom devolveu HTTP 402 em 2 de 2. Muito do conteudo de build,
rota e chefe vive em video, e `WebFetch` numa pagina de video devolve so a
navegacao do site, nunca a legenda.

Ha um caminho, e ele e **condicional**: se `yt-dlp` estiver no PATH, a trilha de
legenda e recuperavel. Ausente, a fonte e inalcancavel — e isso **e** a resposta.
Detecte a capacidade, nunca assuma, e **nunca instale nem instrua a instalar**.

```bash
command -v yt-dlp >/dev/null || { echo "video: fonte inalcancavel"; exit 0; }

yt-dlp --skip-download --write-subs --write-auto-subs \
       --sub-langs 'en.*' --sub-format json3 -o 'v.%(ext)s' "$URL"
```

Quatro coisas que essa invocacao carrega, cada uma medida:

- **A forma estreita `--write-auto-sub --sub-lang en` e dependente do video, nao
  quebrada.** Ela acerta quando existe trilha manual em ingles e falha quando o
  ingles so existe no pool automatico, onde a trilha se chama `en-en` e escapa do
  filtro. Reproduzido em 2026-09-07: zero arquivo no video de teste
  `jNQXAC9IVRw`, tres trilhas com a forma acima.
- **Afirme saida nao-vazia; nao confie no codigo de saida.** As rotas sem
  instalacao (curl na `baseUrl`, Invidious) devolvem **HTTP 200 com corpo
  vazio**. Script ingenuo grava 0 byte e reporta sucesso.
- **Renderize juntando na fronteira de evento**, nunca `"".join()` sobre os
  segmentos. Se o defeito aparece depende da trilha: uma trilha medida tinha
  **0 de 6** eventos com espaco nas bordas e o join ingenuo perdeu 5 de 39
  palavras; outra tinha **338 de 677** e nao perdeu nenhuma. Juntar por evento
  esta certo nos dois casos.
- **A dependencia esta derivando.** Em 2026-08-18 o aviso era de runtime JS
  ausente; em 2026-09-07, na mesma maquina e mesma versao do yt-dlp, o aviso e
  outro (`impersonation`). Conte com quebra, nao com estabilidade.

Nao existe plano B portatil, medido: `curl` na `baseUrl` do `captionTracks` deu
200 com 0 byte, Invidious deu 200/0 byte e 403, Piped deu 526, e o
`youtube-transcript-api` esta ~19 meses sem release e expoe uma excecao
`PoTokenRequired` — reconhece a barreira sem resolve-la. Metadado de legenda e
livre; **conteudo e fechado**.

**Onde video entra e onde nao entra:**

Entra no ramo **META** — rota, tatica, "como as pessoas realmente fazem", a forma
de uma build. A data de upload e uma data de verdade, entao a cerca de patch se
aplica igual.

**Nao entra no ramo FACTUAL.** Nao porque o ASR corrompa nome proprio: medido num
guia real, os nomes sobreviveram bem (`Anubis` 28x, alem de `Artisan`,
`Serenity`, `Musclehead`, `Work Slave`) — e ausencia nao se distingue de "nunca
foi dito" sem assistir. A razao e outra e mais forte: **a transcricao nao tem
ancora de versao nenhuma.** Ela traz numeros — no guia medido, `70`, `40`, `20`,
`115`, `117` — sem nada que diga a que build pertencem. Um numero de la falha a
tripla `(valor, versao, data)` pela coluna do meio, sempre.

E a busca do YouTube **nao ordena por recencia**: os dois primeiros resultados
para uma consulta de build de Palworld eram de 2024-10-05 e 2025-01-30, ambos
anteriores ao 1.0 inteiro. Ordene por data voce mesmo, ou aplique a cerca de
patch antes de ler.

Legenda automatica e saida de ASR. Cite dela com parcimonia, e nunca como fonte
primaria citavel palavra por palavra.

### O que o levantamento derrubou

Cinco coisas que parecem obvias e que os dados contradizem. Elas estao aqui
porque a versao anterior desta skill afirmava tres delas.

**"Tem data" nao e sinal de frescor.** 84% do corpus tinha data e ainda assim
90% era anterior ao patch vigente. A variavel que discrimina e `data > ultimo
patch do subsistema`, que valia para **10%**, nao `tem data`, que valia para 84%.

**Concordancia entre fontes nao eleva confianca.** Das 41 contradicoes
registradas, **voto de maioria resolveu zero**. Pior: o maior aglomerado de
concordancia do corpus eram cinco dominios distintos repetindo um numero que uma
sexta fonte chama de mito ja testado e refutado — eram uma fonte copiada cinco
vezes. **Triangulacao so conta entre tipos diferentes de fonte.**

**Numero de fontes nao e proxy de rigor.** A categoria com **14 fontes**, a
maior amostra, recebeu o **pior** veredito. A que teve 10 fontes, das quais 3
posteriores ao patch, foi a unica em que o verificador **confirmou** uma
afirmacao. O limiar util e **>= 3 fontes posteriores ao ultimo patch relevante**,
com teto de ~6 no total. Nao existindo essas 3, a resposta sai rotulada como
retrato historico, nao como estado atual.

**Wiki nao merece o ultimo degrau, e proibi-la para numero e erro.** Wiki teve
data em 87,5% das paginas — acima de blog de hosting (77%) e acima da propria
fonte oficial (67%) — e forneceu 3 das 8 paginas pos-patch do corpus inteiro,
empatada com a oficial. Blog de hosting forneceu **zero de 22**. E wiki foi o
**unico tipo com proveniencia de versao por conteudo** ("introduzido na 0.1.2.0",
changelog por chefe com numero de patch) — que foi exatamente o metadado que
permitiu **rejeitar a propria wiki** em dois casos. Proibir numero de wiki joga
fora o unico carimbo de safra por pagina que existe.

Mas tambem nao e "confie na wiki": a pagina de breeding nao tinha data **nem**
versao e era a portadora unica dos numeros centrais. A regra que os dados
sustentam e **por pagina, nao por dominio**:

> Use um numero de wiki se e somente se a pagina exibir last-edited **E** (tag
> de versao **OU** data posterior ao ultimo patch que tocou o subsistema).

**"Oficial primeiro, sempre" e largo demais.** A oficial ganhou em versao (92%)
e **perdeu em data** (67%), atras de wiki, forum e site de jogos. Tres modos de
falha documentados: doc viva sem timestamp, pagina de patch notes irrecuperavel
por fetch, e API oficial devolvendo data impossivel. E **nenhuma das 12 fontes
oficiais respondeu uma unica pergunta meta**. O enunciado correto e mais estreito
e mais forte: *a nota de patch e o unico relogio e a unica arbitra de
contradicao; o dominio oficial nao e a resposta.*

### Armadilhas de coleta

- **O buscador substitui o dominio calado.** `site:reddit.com` devolveu
  `steamcommunity.com` em pelo menos 7 das 10 categorias, e numa delas a thread
  "sobre a 1.0" discutia um patch de dois anos e meio antes. Registre a
  substituicao; nunca sirva o substituto como se fosse o pedido.
- **Reddit nao e alcancavel por automacao aqui.** Zero das 10 categorias obteve
  uma thread real. Rotear para la produz exatamente a substituicao acima.
- **Fandom devolveu HTTP 402** em 2 de 2 tentativas. Morto como fonte
  automatizada.
- **Rodape "atualizado para X" nao prova nada.** Uma fonte trazia rodape de 1.0
  com o corpo citando cinco torres, quando o jogo tem nove.
- **Nunca cite como lida uma fonte que so foi vista pelo resumo do buscador.**
  Aconteceu no levantamento: o resumo atribuiu a um site uma alegacao que, ao
  abrir, era de outro.
- **Audite a propria lista de fontes contra a propria alegacao de recencia.**
  Um dos agentes afirmou que "nenhuma fonte reflete esse patch" tendo citado uma
  fonte datada daquele mesmo dia.

### O que este levantamento nao mede

Ele vale como orientacao, nao como estatistica publicavel:

- **Um jogo, um dia, 10 perguntas.** Palworld em 2026-09-07, horas depois de um
  patch — o que exagera a taxa de obsolescencia contra um dia comum.
- **Todas as 10 perguntas eram META ou FACTUAL, nenhuma era LOCAL.** Por isso
  `respondivel_localmente` deu 0 de 10. O ramo LOCAL acima e derivado dos tres
  testes, **nao medido**.
- **`sensibilidade_versao` deu "alta" em 10 de 10**, entao nao ha correlacao
  alta-contra-baixa a extrair. O gradiente que sobrou e por recencia de fonte.
- **O verificador foi instruido a marcar obsoleto na duvida.** Que ele tenha
  marcado 10/10 e o vies pedido, nao uma descoberta. O que vale sao os **53
  itens especificos** que ele nomeou, cada um checavel contra o changelog.
- **Metadado de fonte foi julgado por agente**, nao conferido a mao pagina por
  pagina.


## O que fazer antes de responder

1. **Descubra a versao instalada** pelos caminhos acima. Nao pergunte ao
   usuario o que esta no disco dele.
2. **Compare `LastUpdated` com o seu corte de treino.** Atualizado depois? Voce
   nao sabe o que mudou. Diga isso em vez de responder liso.
3. **Prefira o arquivo local a qualquer guia.** Config de servidor, save,
   `Default*.ini` da instalacao — todos ganham da sua memoria e ganham de blog
   de empresa de hosting, que se contradiz e raramente diz de que versao fala.
4. **Marque a fonte.** "Documentado" quando veio da doc oficial; "observado"
   quando veio de medicao local; "de memoria, corte em `<data>`" quando nao deu
   para verificar. As tres sao respostas legitimas; passar a terceira como a
   primeira nao e.

## Diferenca entre padrao e em vigor

Muita instalacao tem os dois arquivos: um de referencia com os padroes do jogo,
e um ativo com o que esta rodando. Comparar os dois responde "o que foi mexido
aqui" sem depender de memoria nenhuma:

```bash
diff <(tr ',' '\n' < Default<Jogo>Settings.ini | sort) \
     <(tr ',' '\n' < <Jogo>Settings.ini | sort)
```

Editar o arquivo de referencia nao faz efeito — ele e amostra. Isso vale para
Palworld e para todo jogo que segue o mesmo padrao.

## Fora da Steam

Coberto hoje: **Steam**, porque o formato e estavel e verificado.

O resto e caminho a percorrer na hora, e o formato **nao foi verificado** por
esta skill — trate o que segue como onde procurar, nao como parser pronto:

| launcher | onde olhar |
|---|---|
| Heroic (Epic/GOG) | `~/.config/heroic/` — JSON de biblioteca e de instalacao |
| flatpak | `flatpak list --app --columns=application,version` |
| RetroDECK | flatpak `net.retrodeck.retrodeck`; a versao do jogo e a da ROM, nao do app |
| Lutris | `~/.config/lutris/` e o sqlite dele, quando existir |
| Wine/Proton avulso | nao ha manifesto; so o executavel e a data do arquivo |

Antes de citar qualquer um desses, **abra o arquivo e confirme o formato**. Um
parser escrito de cabeca para um launcher que voce nao inspecionou produz
numero errado com aparencia de certeza, que e o mesmo defeito que esta skill
existe para evitar.

## Nao faca

- **Nao converta `buildid` em versao de marketing.** Nao ha relacao derivavel.
- **Nao trate `StateFlags` diferente de 4 como instalacao valida.** Update
  pendente significa que o `buildid` descreve o que a Steam quer, nao o que
  esta no disco.
- **Nao peca a versao ao usuario** quando ela esta no disco. O ponto da skill e
  exatamente esse.
- **Nao cite guia de hosting como se fosse doc.** Eles se contradizem e quase
  nunca datam a versao de que falam.
- **Nao confunda a versao do cliente com a do servidor dedicado.** Sao appids
  diferentes, atualizam em momentos diferentes, e a incompatibilidade entre os
  dois e justamente o sintoma que manda o jogador reclamar.
