# PalWorldSettings.ini — formato, armadilhas e opcoes

Versao de referencia: **v1.0.3.101283** (120 chaves).

## Formato

O arquivo tem poucas linhas, mas **todas as 120 opcoes vivem numa unica linha**:

```ini
[/Script/Pal.PalGameWorldSettings]
OptionSettings=(Difficulty=None,DayTimeSpeedRate=1.000000,...,bAllowEnemyCampSpawnNearBaseCamp=False)
```

Quebrar essa linha para "ficar legivel" faz o servidor **ignorar o arquivo
inteiro e voltar ao padrao, sem erro nenhum**. E o motivo nº1 de "editei e nao
mudou nada".

## Procedimento seguro de edicao

1. `systemctl --user stop palworld`
2. Gerar a partir do `DefaultPalWorldSettings.ini` (nunca editar o Default em si)
3. Trocar so o que precisa, com match unico verificado
4. `systemctl --user start palworld`
5. Conferir: `wc -c` no arquivo — 1 byte significa que foi ignorado

O servidor apaga linhas de comentario (`;`) ao regravar. Isso e normal.

## DeathPenalty

O que o jogador dropa ao morrer.

| Valor | Efeito |
|---|---|
| `None` | Nada cai. Respawna com inventario, equipamento e Pals |
| `Item` | So itens da mochila. Equipamento e Pals ficam |
| `ItemAndEquipment` | Itens + equipamento. Pals ficam |
| `All` | Tudo, incluindo os Pals do time ATIVO (nao os do Palbox) |

O que cai vira um bau no local da morte — nao some, o dono pode recuperar.
`bCanPickupOtherGuildDeathPenaltyDrop=False` (padrao) impede outra guilda de
saquear.

Atencao: guias na web repetem que o padrao e `All`; no arquivo de fabrica da
v1.0.3 o padrao e **`Item`**. Confie no arquivo local.

## Opcoes mais mexidas

```
ExpRate=1.000000                   # XP
PalCaptureRate=1.000000            # chance de captura
CollectionDropRate=1.000000        # minerio, madeira, pedra
EnemyDropItemRate=1.000000         # drops de inimigos
WorkSpeedRate=1.000000             # Pals na base (nao documentado oficialmente, mas existe)
PalEggDefaultHatchingTime=1.000000 # 0 = choca na hora
DayTimeSpeedRate=1.000000
bEnablePlayerToPlayerDamage=False  # NAO basta sozinha para PvP, ver abaixo
bEnableFriendlyFire=False
ServerName="Default Palworld Server"
ServerPassword=""                  # senha de entrada
AdminPassword=""                   # habilita /Shutdown, /Broadcast, /KickPlayer no chat
GuildPlayerMaxNum=20
BaseCampWorkerMaxNum=15
AutoSaveSpan=30.000000             # segundos
bEnableInvaderEnemy=True           # desligar reduz MUITO a RAM (relato de hosts, nao testado)
```

Consenso da comunidade para grupo pequeno de amigos (fonte: blogs de hosting,
nao oficial): `ExpRate=2.0`, `PalCaptureRate=1.5-2.0`, `CollectionDropRate=2.0`,
`DeathPenalty=None ou Item`. O argumento mais solido e que em multiplayer nao da
para pausar, entao morte punitiva custa a noite do grupo.

## PvP

Ligar PvP exige **tres chaves juntas**, segundo a doc oficial:

```
bIsPvP=True
bEnablePlayerToPlayerDamage=True
bEnableDefenseOtherGuildPlayer=True
```

Mexer so em `bEnablePlayerToPlayerDamage` nao liga PvP de verdade — e o erro
comum de quem le lista de "melhores settings".

A doc avisa: **"this is only a trial feature and is not covered by support"**.
Com PvP ligado, jogadores se ferem, bases recebem notificacao de ataque, quem
esta no ar leva mais dano, missoes ficam desabilitadas, algumas armas tem alcance
e dano ajustados para PvP, e a distancia minima entre bases aumenta bastante.

## Novidades do 1.0 (julho/2026)

Nenhuma opcao classica foi removida ou renomeada — guias de early access seguem
validos no que ensinam. O que mudou e que apareceu muita coisa nova:

| Area | Chaves |
|---|---|
| Hardcore | `bHardcore`, `bPalLost`, `bCharacterRecreateInHardcore` |
| Voice chat | `bEnableVoiceChat`, `VoiceChatMaxVolumeDistance`, `VoiceChatZeroVolumeDistance` |
| Crossplay | `CrossplayPlatforms=(Steam,Xbox,PS5,Mac)` |
| Respawn | `RespawnPenaltyDurationThreshold`, `RespawnPenaltyTimeScale`, `BlockRespawnTime` |
| Guilda inativa | `AutoTransferMasterThresholdDays`, `AutoTransferMasterCheckIntervalSeconds` |
| Progressao | `bAllowEnhanceStat_*` (5), `DenyTechnologyList` (ids na pagina `technologyids` da doc oficial) |
| Automacao | `RESTAPIEnabled`, `RESTAPIPort`, `BanListURL` |
| Performance | `MaxGuildsPerFrame`, `ServerReplicatePawnCullDistance`, `PhysicsActiveDropItemMaxNum` |

`RespawnPenaltyTimeScale` multiplica o cooldown se o jogador morrer de novo
dentro de `RespawnPenaltyDurationThreshold` segundos — anti-suicidio-tatico.

## Qualidade das fontes

A maioria dos guias de "best settings" e blog de empresa de hosting, e eles se
contradizem (uns dizem que o 1.0 trouxe server clustering, outros que nao; o
padrao de DeathPenalty varia). A doc oficial e incompleta — nao lista
`WorkSpeedRate`, que existe. **Na duvida, o arquivo local da instalacao ganha.**

Os valores em vigor em uma instalacao concreta, com o raciocinio por tras de
cada escolha, ficam em `~/.claude/palserver.local.md` — nao aqui. O molde
desse arquivo e `exemplo-de-maquina.md`.
