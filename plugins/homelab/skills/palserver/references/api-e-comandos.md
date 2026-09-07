# Comandos de admin, REST API e RCON

Num servidor dedicado headless nao existe console para digitar comando. Ha tres
caminhos, e dois deles estao em fim de vida ou dependem de alguem dentro do jogo.

## Os 13 comandos

Lista completa da doc oficial:

| Comando | O que faz |
|---|---|
| `/AdminPassword` | Obter privilegio de admin |
| `/Shutdown` | Desligar com delay opcional |
| `/DoExit` | Parada forcada |
| `/Broadcast` | Mensagem para todos |
| `/KickPlayer` | Expulsar |
| `/BanPlayer` | Banir |
| `/UnBanPlayer` | Desbanir |
| `/TeleportToPlayer` | Ir ate um jogador |
| `/TeleportToMe` | Trazer um jogador |
| `/ShowPlayers` | Lista de conectados |
| `/Info` | Informacao do servidor |
| `/Save` | Salvar o mundo |
| `/ToggleSpectate` | Modo espectador |

**Nenhum toca em guilda.** Nao ha comando para cargo, Guild Master ou expulsar de
guilda pelo servidor.

Pelo chat do jogo, quem se autentica com `/AdminPassword <senha>` usa os
comandos ali mesmo — exige `AdminPassword` preenchido no ini e alguem logado.

## REST API — o caminho recomendado

Habilitar no `PalWorldSettings.ini` (servidor parado, ver a armadilha de edicao):

```
RESTAPIEnabled=True
RESTAPIPort=8212
AdminPassword="alguma-senha"
```

Autenticacao: **HTTP Basic Auth**. A senha e a `AdminPassword` do ini.

> O **usuario** do Basic Auth nao aparece na doc estatica — a pagina renderiza os
> exemplos dinamicamente. Por convencao e `admin`, mas **isso nao foi
> confirmado**. Descubra na primeira chamada, com uma rota inofensiva:
>
> ```bash
> curl -su admin:"$ADMIN_PASSWORD" http://127.0.0.1:8212/v1/api/info
> ```
>
> 401 = usuario errado. 200 com JSON = e esse mesmo.

Rotas (prefixo `/v1/api/`):

| Rota | Metodo | O que faz |
|---|---|---|
| `info` | GET | Versao e nome do servidor |
| `players` | GET | Lista de jogadores |
| `settings` | GET | Config em vigor |
| `metrics` | GET | FPS, uptime, jogadores, memoria |
| `announce` | POST | Mensagem para todos (corpo: `{"message": "..."}`) |
| `kick` | POST | Expulsar |
| `ban` | POST | Banir |
| `unban` | POST | Desbanir |
| `save` | POST | Salvar o mundo |
| `shutdown` | POST | Desligar |
| `stop` | POST | Parada forcada |
| `game-data` | GET | Snapshot dos atores do mundo |

`game-data` exige o argumento `-enable-gamedata-api` na linha de comando.

### Aviso de seguranca — literal da doc

> "These APIs are not designed to be exposed directly to the Internet.
> Publishing directly to the Internet may result in unauthorized manipulation of
> the server, which may interfere with play."

Deixe a REST API em `127.0.0.1` ou na rede interna/VPN. Nunca em port forward.

Uso pratico: `save` antes de um backup a quente, `announce` avisando restart,
`metrics` para monitorar memoria sem depender do `ps`.

## RCON — deprecado

A doc e direta:

> "RCON is now deprecated. Please consider to use REST API. RCON is scheduled to
> stop functioning in an upcoming update."

O ini ainda tem `RCONEnabled` e `RCONPort` (padrao **25575**), e clientes RCON
genericos ainda conectam. **Nao construa nada novo em cima disso.** Se ja houver
script usando RCON, migre para a REST API antes que pare sozinho.

Consequencia colateral: a porta 25575 continua reservada no ini mesmo com RCON
desligado — leve isso em conta ao escolher portas de um segundo servidor.
