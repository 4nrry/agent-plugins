# Instalacao, unit do systemd e atualizacao

## Instalar — o caminho oficial

A doc oficial documenta steamcmd, e so isso:

```bash
steamcmd +login anonymous +app_update 2394010 validate +quit
cd ~/Steam/steamapps/common/PalServer
./PalServer.sh
```

- **AppID 2394010** = Palworld Dedicated Server. E `anonymous`: nao precisa de
  conta nem de possuir o jogo.
- O mesmo comando **instala e atualiza**. `validate` conferere a integridade.
- A doc avisa que o diretorio varia conforme a configuracao do steamcmd.

Requisitos oficiais: **4 nucleos+**, **16 GB recomendado** ("8GB is also
bootable"), SSD — "Low-performance storage may corrupt saved data". SO: Windows
64bit ou Linux 64bit ("Ubuntu, AlmaLinux etc...").

O primeiro boot cria `Pal/Saved/`. Antes dele nao existe `PalWorldSettings.ini`
para editar.

### Variante: instalado pelo cliente Steam

Quem instala pela interface do Steam (o dedicated server aparece na biblioteca)
recebe a mesma coisa em outro lugar:

```
~/.local/share/Steam/steamapps/common/PalServer
```

Funciona igual. A diferenca que importa: **quem gerencia a pasta e o cliente
Steam**, com um `appmanifest_2394010.acf` controlando versao e integridade.
Apontar o steamcmd para essa arvore mete duas ferramentas na mesma pasta,
disputando o manifesto. Escolha um dono e fique com ele.

Conferir o que esta instalado:

```bash
grep -E '"(buildid|LastUpdated|StateFlags)"' \
  ~/.local/share/Steam/steamapps/appmanifest_2394010.acf
```

`StateFlags 4` = instalado e integro.

## A unit do systemd

A doc oficial nao fornece unit. Este modelo funciona; ajuste os caminhos:

```ini
[Unit]
Description=Palworld Dedicated Server
Documentation=https://docs.palworldgame.com/
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=300
StartLimitBurst=3

[Service]
Type=simple
WorkingDirectory=%h/Steam/steamapps/common/PalServer
ExecStart=%h/Steam/steamapps/common/PalServer/PalServer.sh

# Desligamento gracioso: SIGINT deixa a Unreal salvar o mundo antes de sair.
KillSignal=SIGINT
KillMode=control-group
TimeoutStopSec=120

# Reinicia se cair, mas desiste se falhar 3x em 5min (evita loop se a porta
# 8211 ja estiver ocupada por outra instancia).
Restart=on-failure
RestartSec=15

[Install]
WantedBy=default.target
```

Pontos que nao sao enfeite:

- **`KillSignal=SIGINT`** — a Unreal salva o mundo ao receber SIGINT. Sem isso o
  systemd manda SIGTERM e o encerramento e menos gracioso.
- **`TimeoutStopSec=120`** — salvar um mundo grande leva tempo. Timeout curto
  vira SIGKILL no meio do save.
- **`Restart=on-failure` + `RestartSec=15`** — o servidor crasha de vez em quando
  (`Signal 11 caught.` no journal) e volta sozinho.
- **`StartLimitBurst=3` em 300s** — evita loop infinito quando a porta 8211 ja
  esta ocupada por outra instancia.

Como o exit de SIGINT e 130, um `kill -INT` na mao dispara o
`Restart=on-failure`. Pelo `systemctl stop` nao dispara, porque o systemd sabe
que a parada foi comandada.

Argumentos uteis no `ExecStart` (o `PalServer.sh` repassa `"$@"`):

| Argumento | Para que |
|---|---|
| `-port=8211` | Porta do jogo |
| `-players=32` | Maximo de jogadores |
| `-publiclobby` | Vira community server (necessario para Xbox/PS5) |
| `-publicip=` / `-publicport=` | Quando o servidor nao detecta sozinho |
| `-logformat=text` | `text` ou `json` |
| `-enable-gamedata-api` | Habilita a rota REST `game-data` |
| `-NumberOfWorkerThreadsServer=X` | Numero de worker threads |

## Atualizar apos patch

O problema: quando sai patch, o Steam atualiza o **cliente** dos jogadores
sozinho e o **servidor** fica para tras. Quem tentar entrar leva erro de versao.
Nada disso e automatico.

Conferir a versao no ar — o servidor imprime no boot:

```bash
journalctl --user -u palworld | grep 'Game version is' | tail -1
```

Ordem correta:

1. Avisar quem estiver jogando (rota REST `announce`).
2. `systemctl --user stop palworld` — atualizar binario debaixo de processo
   rodando nao termina bem.
3. Backup do save.
4. Atualizar:
   - **instalado por steamcmd**: `steamcmd +login anonymous +app_update 2394010 validate +quit`
   - **instalado pelo cliente Steam**: atualize pelo proprio cliente, para nao
     criar disputa de manifesto.
5. Conferir que o `PalWorldSettings.ini` sobreviveu — `wc -c`, 1 byte = ignorado.
6. Subir e conferir a versao nova no journal.

> O comando de steamcmd e o documentado pela Pocketpair, mas **nao foi executado
> em uma maquina instalada pelo cliente Steam** — que e justamente o caso onde
> ele pode brigar com o `appmanifest`. Em instalacao por steamcmd, e o caminho
> normal e testado pela propria doc.
