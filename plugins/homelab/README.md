# Homelab

Servicos e software que voce mesmo mantem numa maquina Linux, no ponto em que a
doc oficial para e voce quebra a cara. Tres skills, um feitio: falha que nao
levanta erro.

## Componentes

| componente | o que faz |
|---|---|
| `skills/palserver/` | Operar um servidor dedicado de Palworld: instalar, subir por systemd, editar o ini sem perder a edicao, admin por REST API, acesso dos jogadores, backup, atualizar apos patch, segundo servidor, guilda. |
| `skills/wireguard-networkmanager/` | Importar `.conf` de provedor no NetworkManager e usar pelo applet do Plasma, sem cliente do provedor nem keyring. Escolha de servidor, importacao, verificacao de vazamento, remocao. Dois scripts. |
| `skills/tarball-installer/` | Instalar tarball de aplicativo com um layout so: diretorio versionado, symlink `current`, wrapper no PATH, `.desktop` validado e icone no hicolor. Um script empacotado, mais um guia de troubleshooting. |

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

**Nao promete kill switch.** O caminho de WireGuard pelo NetworkManager nao tem
um. Se o tunel cair, o trafego volta pela rota normal em silencio, sem aviso na
tela. E por isso que o script de importacao deixa `autoconnect no`: melhor a VPN
existir so quando escolhida do que subir sozinha e dar uma sensacao de protecao
que nao se sustenta. Quem precisa de kill switch precisa do cliente do provedor.

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
| VPN que passa no teste e vaza | Config com `AllowedIPs = 0.0.0.0/0` e sem `::/0` poe o IPv4 no tunel — o teste de IP passa — enquanto todo o trafego IPv6 continua saindo com o endereco real. Metade da navegacao vaza e nada avisa. |
| A rota padrao nao aparece onde voce olha | O NM usa policy routing: a default do tunel vai para uma tabela propria, entao `ip route show default` segue mostrando o Wi-Fi com tudo dentro do tunel. |
| Nome de arquivo vira nome de interface | Maximo 15 caracteres. `Book4Ultra-US-FREE-122.conf` e recusado com "The name of the WireGuard config must be a valid interface name". |
| Auto-updater contra `/opt` | App que se atualiza sozinho (Firefox e forks, VS Code, JetBrains, Obsidian) escreve no proprio diretorio de instalacao. Root-owned em `/opt` faz isso falhar, e os "consertos" usuais sao piores que o problema. |
| Icone grande demais some do menu | O tamanho no hicolor sai das dimensoes reais da imagem, nao do nome do arquivo. Icone so em tamanho grande faz o menu cair no icone de **outro** app quando os nomes compartilham prefixo. |
| `~/.local/bin` fora do PATH | O `~/.profile` do Ubuntu adiciona o diretorio condicionalmente **no login**. Diretorio criado ha cinco minutos ainda nao esta no PATH do shell atual. |

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

## Uma alegacao retirada

A 0.1.0 afirmava que a memoria do PalServer cresce com o uptime, nao estabiliza,
e que um restart diario por timer resolve. **A serie medida nao sustenta.** Na
mesma maquina, a leitura de maior uptime foi a mais leve:

| uptime | RSS | contexto |
|---|---|---|
| 2h | 2,13 GB | jogadores online |
| 6h10 | 2,40 GB | apos dobrar a densidade de spawn |
| 14h | 2,20 GB | jogadores online |
| 11h39 | **0,59 GB** | ocioso |

Isso nao prova o contrario, e o texto nao troca uma alegacao por outra: as
variaveis nunca foram isoladas. O que a serie sustenta e que **uptime sozinho
nao prediz RSS** e que carga explica mais que tempo. A skill passa a mandar
reiniciar **por sintoma** — jogador reclamando de rubber-banding, numeros acima
de qualquer coisa ja medida naquela instalacao, save parado com gente dentro —
e nao por relogio. O molde de maquina ganhou colunas de jogadores online e data,
porque uma tabela so com uptime e RSS registra a variavel errada.

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
