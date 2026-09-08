---
name: palserver
description: Gerenciar um servidor dedicado Palworld self-hosted em Linux — instalar por steamcmd, subir e parar por systemd, editar PalWorldSettings.ini sem perder a edicao, comandos de admin pela REST API, acesso dos jogadores, backups, atualizar apos patch, rodar um segundo servidor e troubleshooting. Use quando a tarefa envolver Palworld, PalServer, PalWorldSettings.ini, DeathPenalty, palworld.service, AppID 2394010, guilda ou Guild Master, ou "meu servidor de Palworld".
---

# Servidor dedicado Palworld em Linux

Como operar um PalServer self-hosted em Linux. Tudo o que esta aqui vale
para qualquer instalacao: enderecos de rede, versoes instaladas e numeros
medidos nao moram na skill.

O que e especifico de uma maquina vive em `~/.claude/palserver.local.md`,
fora deste repositorio. **Se esse arquivo existir, leia antes de responder
qualquer coisa sobre "meu servidor"** — ele ganha da skill em todo ponto
onde os dois discordem. O molde para cria-lo, com placeholders no lugar dos
enderecos, esta em `references/exemplo-de-maquina.md`.

Onde a doc oficial e a medicao divergem, isto esta anotado. A doc oficial e
incompleta em varios pontos — ela nao lista todas as chaves do ini, por exemplo.
**Na duvida, o arquivo local da instalacao ganha.**

## Onde as coisas ficam

O prefixo depende de **como foi instalado**, e as duas formas sao validas:

| Metodo | Prefixo |
|---|---|
| steamcmd (oficial) | `~/Steam/steamapps/common/PalServer` |
| Cliente Steam nativo | `~/.local/share/Steam/steamapps/common/PalServer` |

O resto e relativo a esse prefixo — chame de `$PALSERVER`:

| O que | Onde |
|---|---|
| Config ATIVA | `$PALSERVER/Pal/Saved/Config/LinuxServer/PalWorldSettings.ini` |
| Config de referencia | `$PALSERVER/DefaultPalWorldSettings.ini` — **so amostra, editar nao faz nada** |
| Qual mundo carrega | `$PALSERVER/Pal/Saved/Config/LinuxServer/GameUserSettings.ini` -> `DedicatedServerName=` |
| Mundos | `$PALSERVER/Pal/Saved/SaveGames/0/<HEX>/` |
| Backup automatico | `$PALSERVER/Pal/Saved/SaveGames/0/<HEX>/backup/world/<timestamp>/` |
| Logs do jogo | `$PALSERVER/Pal/Saved/Logs/` |

As pastas so aparecem **depois do primeiro boot** do servidor. Antes disso nao
adianta procurar o `PalWorldSettings.ini`: ele nao existe.

Instalacao, unit do systemd e atualizacao: `references/instalacao.md`.

## Operacao basica

Assumindo uma unit chamada `palworld` (ver `references/instalacao.md`):

```bash
systemctl --user status palworld          # esta no ar?
systemctl --user start|stop palworld      # subir / parar
journalctl --user -u palworld -f          # log ao vivo
```

Com systemd de **usuario**, ative o linger (`loginctl enable-linger $USER`) para
o servidor subir no boot sem ninguem logar. Com unit de **sistema**, troque
`--user` por `sudo` e nao precisa de linger.

**Nunca pare com `kill`.** O servidor sai com status 130 ao receber SIGINT, e um
`Restart=on-failure` interpreta isso como falha e reinicia sozinho. Pelo
`systemctl stop` o systemd sabe que a parada foi comandada e nao ressuscita.
Use sempre `systemctl stop`.

## ARMADILHA CENTRAL: editar a config

O PalServer **reescreve** o `PalWorldSettings.ini` no shutdown com o que carregou
na memoria. Se ele subiu com o arquivo vazio, ele ZERA sua edicao ao desligar.
Consequencia: **`systemctl restart` nao aplica config** — o stop apaga a edicao
antes do start conseguir ler.

A unica ordem que funciona:

```bash
systemctl --user stop palworld
# editar o PalWorldSettings.ini AGORA, com o servidor parado
systemctl --user start palworld
wc -c "$PALSERVER/Pal/Saved/Config/LinuxServer/PalWorldSettings.ini"
```

**Teste**: alguns milhares de bytes = config carregada. **1 byte = foi ignorada.**
Nao compare com um numero exato: o servidor apaga linhas de comentario ao
regravar, entao o tamanho encolhe sem perda de config.

Formato, opcoes e a armadilha da linha unica: `references/configuracao.md`.

## Comandos de admin

Num servidor headless nao ha console. Para rodar `/Broadcast`, `/Save`,
`/ShowPlayers` e afins voce precisa de **REST API** (recomendado) ou de um
jogador com `AdminPassword` digitando no chat do jogo.

**RCON esta deprecado** — a doc oficial diz que vai parar de funcionar num
update futuro. Nao construa nada novo em cima dele.

Rotas, autenticacao, os 13 comandos e o aviso de seguranca:
`references/api-e-comandos.md`.

## Acesso dos jogadores

Porta **8211/UDP** (jogo, obrigatoria) e **27015/UDP** (query Steam, opcional).
Nunca TCP. A porta do jogo muda com `-port=`; **a de query nao e configuravel**.

Dois modelos, e a escolha nao e so cosmetica:

| Modelo | Como entram | Consoles |
|---|---|---|
| Dedicated (padrao) | **Join Multiplayer Game (Dedicated Server)** -> campo abaixo da lista -> `IP:porta` | Xbox e PS5 **nao conseguem** |
| Community (`-publiclobby`) | Aba `Community server`, achando pelo nome | Unico jeito para Xbox e PS5 |

Ou seja: se algum jogador for de console, community server deixa de ser opcional.
Crossplay cobre Steam, Xbox Series X|S, Microsoft Store, macOS e PS5.

Para expor o servidor sem abrir o roteador, uma VPN mesh (Tailscale, Netbird,
ZeroTier) funciona bem: os jogadores usam o IP da VPN e a porta 8211, e nada fica
publico. A alternativa classica e port forward de 8211/UDP no roteador — e ai
`ServerPassword` deixa de ser opcional.

## Backups

A doc oficial nao tem pagina de backup. O que ela oferece e **uma chave**:

```
bIsUseBackupSaveData=True
```

Descrita como "Enable world backups. Enabling this increases disk load." Cria
`backup/` dentro do save, com esta rotacao:

| Frequencia | Quantos guarda |
|---|---|
| 30 segundos | 5 |
| 10 minutos | 6 |
| 1 hora | 12 |
| 1 dia | 7 |

**Isso nao substitui backup de verdade.** Esses arquivos moram dentro da mesma
arvore do mundo, no mesmo disco. Perdeu o disco ou apagou a pasta errada, foram
junto. Um mundo inteiro tem dezenas de MB, entao copia externa e barata:

```bash
tar czf ~/palworld-backup/save-$(date +%Y%m%d-%H%M%S).tar.gz \
  -C "$PALSERVER/Pal/Saved" SaveGames
```

Restaurar exige o servidor **parado**. Para forcar um save antes de copiar com o
servidor no ar, use a rota REST `save` ou o comando `/Save`.

## Restart: por sintoma, nao por relogio

Uma versao anterior desta skill afirmava que a memoria do PalServer cresce com o
uptime, nao estabiliza, e que um restart diario por timer resolve. **A medicao
que sustentava isso nao se repetiu**, na mesma maquina: 0,59 GB com 11h39 no ar,
contra 2,13 GB com 2h medidos duas semanas antes — um quarto da memoria com
quase seis vezes o uptime.

Isso nao prova o contrario. Prova que **uptime sozinho nao prediz RSS**, e que a
carga (jogadores online, densidade de spawn, raids) explica mais do que o tempo
no ar. As leituras nao foram isoladas por variavel, entao a unica conclusao
honesta e que nao existe taxa de crescimento para citar — nem para cima, nem
para baixo.

**A doc oficial da Pocketpair nao recomenda restart periodico** — a pratica vem
de hosts. Um restart agendado que nao responde a sintoma nenhum e cerimonia com
custo: derruba quem estiver jogando, e sem `AdminPassword` nao ha como avisar.

O gatilho util e sintoma, em ordem:

1. **Jogador reclamando de rubber-banding ou lag com Pals trabalhando.** E o
   unico sinal que importa; numero so confirma.
2. **RSS ou CPU acima de qualquer coisa que voce ja tenha medido** nessa
   instalacao. Nao ha limiar universal para citar — o seu sai da sua propria
   serie (`references/hardware-rede.md` mostra como levantar).
3. **Save parado.** Com jogador online, o `Level.sav` muda a cada `AutoSaveSpan`
   segundos. Parado com gente dentro = autosave travado.

`Signal 11` no journal **nao** entra na lista: `Restart=on-failure` ja cobre.

Para o reinicio manual, `systemctl --user restart palworld` **e seguro** — a
armadilha do ini so existe quando ha edicao a preservar, porque o stop grava em
disco o que estava em memoria e o start le de volta. Restart sem edicao devolve a
mesma config.

Se ainda assim quiser agendar, escolha um horario de baixa ocupacao — e note que
"maquina ligada" nao e "ninguem jogando" — e evite `Persistent=true` num timer de
usuario: ele dispara o restart logo apos o boot, derrubando um servidor que
acabou de subir.

```bash
systemctl --user disable --now palworld-restart.timer   # desligar
systemctl --user list-timers --all | grep palworld      # conferir
```

## Nao faca

- **Nao adicione** `-useperfthreads -NoAsyncLoadingThread -UseMultithreadForDS`.
  Sao folclore de early access; a doc oficial diz que **na v1.0+ deixar sem esses
  parametros pode melhorar a performance**.
- **Nao edite** `DefaultPalWorldSettings.ini` esperando efeito.
- **Nao quebre** a linha `OptionSettings=` em varias linhas.
- **Nao exponha a REST API a internet.** A doc e explicita: nao foi desenhada
  para isso.
- **Nao conte com mods.** A doc oficial diz que mods so funcionam em servidor
  dedicado **Windows**. Em Linux, nao ha o que instalar.
- **Nao hospede em maquina fraca.** Oficial: 4 nucleos, 16 GB recomendado (8 GB
  "bootable"), SSD — "Low-performance storage may corrupt saved data".

## Mais mundos

Varios mundos convivem em `SaveGames/0/`. Trocar qual sobe = editar
`DedicatedServerName=` no `GameUserSettings.ini` e reiniciar. Esse e o caminho
barato: um servidor so, um mundo por vez.

Rodar dois **ao mesmo tempo** e outra historia — ver abaixo.

## Segundo servidor

Exige **segunda instalacao**, em outra pasta. Duas instancias apontando para a
mesma arvore brigam pelo mesmo config e carregam o mesmo mundo.

**Porta:** o ini ja reserva `RESTAPIPort` (8212 por padrao) e `RCONPort` (25575).
Escolher 8212 para o segundo servidor cria colisao no dia que a REST API for
ligada. Use algo fora dessas: **8213**, por exemplo.

**A porta de query nao e configuravel.** Nao existe `-queryport` na doc de
argumentos, e o binario nao tem a string `queryport` nem o literal `27015` — essa
porta vem do Steam. Nao planeje "27016" para o segundo servidor. Na pratica so
importa para listagem em community server; com direct connect, nao atrapalha.

**Na unit:** o `PalServer.sh` repassa argumentos (`"$@"`) para o binario, entao o
`-port` vai direto no `ExecStart`. Copie a unit e troque `Description`,
`WorkingDirectory` e `ExecStart` (com `-port=8213`).

Cada instalacao tem o proprio `PalWorldSettings.ini`, o proprio
`GameUserSettings.ini` e a propria pasta de mundos. A armadilha de editar config
com o servidor parado vale em cada uma.

**Custo:** cerca de 2 GB de RSS por instancia depois de algumas horas e ~1,3
nucleos. Dois servidores pedem ~4 GB so de servidor.

A doc oficial **nao cobre multiplas instancias** — verificado. O procedimento
acima e derivado, nao documentado.

## Guilda e Guild Master

Cargos na v1.0: **Guild Master**, **Sub Master**, **Member**, **Guest**, com oito
permissoes atribuiveis (aprovar entrada, expulsar, editar permissoes, mudar
cargos, construir, seguranca de estrutura, Palbox, Pals da base).

**Nao da para gerenciar guilda pelo lado do servidor.** Nenhum dos 13 comandos de
admin toca em guilda, e a REST API tambem nao. O `AdminPassword` do ini nao
alcanca cargo de guilda — o "admin" que aparece nas strings do binario e o lider
da guilda, nao o dono da maquina.

Passar o cargo e **so no jogo**, pelo menu da guilda: selecionar o membro ->
**MAKE GUILD MASTER**. Quem faz e o master atual; ninguem muda o proprio cargo
(`FailedCannotChangeOwnRole`) e ninguem rebaixa o master
(`FailedCannotDemoteMaster`). O master tambem nao consegue sair da guilda sem
antes passar o cargo. **Se alguem passou o master sem querer, quem devolve e a
outra pessoa** — nao ha jeito de tomar de volta.

Existem `AutoTransferMasterThresholdDays` e
`AutoTransferMasterCheckIntervalSeconds` no ini, e o binario tem o motivo
`AutoTransfer`. **Mas a doc oficial nao documenta nenhuma das duas chaves** e um
guia de hosting afirma que sistema automatico nao existe. O recurso e real no
codigo; o comportamento exato **nao foi verificado**. Nao prometa a ninguem que o
cargo volta sozinho.

Ultimo recurso, se a pessoa sumiu de vez: editar o `Level.sav` com
`palworld-save-tools` e reatribuir o Guild Master. Servidor parado, backup antes.
