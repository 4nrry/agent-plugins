# Homelab

Servicos self-hosted numa maquina Linux. Uma skill hoje — PalServer dedicado — e
espaco para as proximas, que sao do mesmo feitio: coisa que roda na sua maquina,
onde a doc oficial para antes de chegar no ponto em que voce quebra a cara.

## Componentes

| componente | o que faz |
|---|---|
| `skills/palserver/` | Operar um servidor dedicado de Palworld: instalar, subir por systemd, editar o ini sem perder a edicao, admin por REST API, acesso dos jogadores, backup, atualizar apos patch, segundo servidor, guilda. |

## O que ele nao faz, de proposito

**Nao guarda o estado da sua maquina.** Nenhum IP, nenhuma versao instalada,
nenhum numero medido esta neste repositorio — e isso e uma decisao, nao um
esquecimento. Esses valores vao para `~/.claude/palserver.local.md`, que a skill
le se existir. O que fica publicado e o molde:
[`references/exemplo-de-maquina.md`](skills/palserver/references/exemplo-de-maquina.md).

O caminho obvio seria `.gitignore`. Ele resolve metade do problema e cria outra:
um arquivo ignorado existe so na maquina de quem escreveu, entao a skill
funciona para o autor e chega quebrada para quem instala o plugin, com uma
referencia apontando para nada. E nao ha check que pegue isso — `validate.py`
nao valida link de referencia. Falha silenciosa que so aparece na maquina dos
outros, que e exatamente a classe de bug que o `mobile-agent` deste repo existe
para documentar.

**Nao ensina Palworld.** Nada sobre Pals, base, boss ou progressao. A skill
comeca onde o jogo termina: o processo, o arquivo de config, a unit do systemd.

## As armadilhas que sustentam a skill

Cada uma custou uma sessao de depuracao antes de virar paragrafo:

| armadilha | o que acontece |
|---|---|
| Config apagada no shutdown | O servidor **reescreve** o `PalWorldSettings.ini` ao sair, com o que carregou em memoria. Logo, `systemctl restart` **nunca** aplica uma edicao: o stop apaga antes do start ler. A unica ordem que funciona e stop -> editar -> start. |
| O teste de 1 byte | Config carregada deixa o ini com alguns milhares de bytes. **1 byte = foi ignorada.** Nao compare com numero exato: o servidor apaga comentarios ao regravar. |
| `kill` que ressuscita | O servidor sai com status 130 no SIGINT, e `Restart=on-failure` le isso como falha e sobe outro. So `systemctl stop` para de verdade. |
| Atualizar com o servidor no ar | A Steam troca o binario debaixo do processo e ele morre de `Signal 11`. Observado nesta maquina em 2026-09-07: o save foi para o disco por autosave, nao por shutdown gracioso. |
| Duas ferramentas, um manifesto | Instalou pelo cliente Steam e depois apontou o steamcmd para a mesma pasta: as duas disputam o `appmanifest_2394010.acf`. |
| Folclore de early access | `-useperfthreads -NoAsyncLoadingThread -UseMultithreadForDS` circula em todo guia. A doc oficial diz que na v1.0+ **deixar sem** esses parametros pode melhorar a performance. |
| Guilda nao tem lado servidor | Nenhum dos 13 comandos de admin toca em guilda, e a REST API tambem nao. Passou o Guild Master sem querer, so a outra pessoa devolve. |

## Documentado contra observado

O texto marca a diferenca em cada afirmacao, porque a doc da Pocketpair e
incompleta de um jeito que engana: ela nao lista todas as chaves do ini, entao
"nao esta documentado" nao quer dizer "nao existe".

Tres exemplos do corte:

- Que `bIsUseBackupSaveData` cria backups **e** documentado. Que a rotacao seja
  5/6/12/7 tambem. Que esses arquivos morem dentro da mesma arvore do mundo, no
  mesmo disco, e portanto **nao sejam backup**, e leitura minha.
- Que RCON esta deprecado **e** documentado. Que a porta de query 27015 nao seja
  configuravel nao esta em lugar nenhum — foi verificado no binario, que nao tem
  a string `queryport` nem o literal `27015`.
- `AutoTransferMasterThresholdDays` existe no ini e o binario tem o motivo
  `AutoTransfer`. A doc **nao documenta a chave**, e um guia de hosting afirma
  que o sistema nao existe. A skill diz que o comportamento **nao foi
  verificado**, e nao promete a ninguem que o cargo volta sozinho.

Multiplas instancias, restart periodico e a unit do systemd tambem sao
derivados: a doc oficial nao cobre nenhum dos tres, e o texto diz isso onde
aparecem.

## Estado da medicao

**Nao ha run records.** Pela regra zero do [`bench/PROTOCOL.md`](../../bench/PROTOCOL.md),
alegacao de melhoria sem registro e marketing, entao esta versao nao faz
nenhuma.

O que existe e comportamento observado numa instalacao real ao longo de duas
semanas: 14 subidas registradas no journal, 4 crashes `Signal 11` — todos
cobertos pelo `Restart=on-failure` —, e uma curva de RSS que **nao** estabiliza e
que se contradiz entre sessoes (2,13 GB em 2h numa, 1,47 GB em 4h noutra). A
skill publica a contradicao em vez de escolher o numero mais bonito, porque a
conclusao honesta e que nao ha taxa estavel para citar.

O que falta medir: se o restart diario e mesmo necessario, e a partir de quantas
horas. O timer esta desligado de proposito para descobrir.
