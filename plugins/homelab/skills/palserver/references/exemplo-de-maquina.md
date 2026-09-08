# O arquivo da sua maquina

A skill e portatil: tudo nela vale para qualquer instalacao. O que **nao** e
portatil — enderecos, versoes, os numeros que voce mediu — nao mora aqui.

Mora em `~/.claude/palserver.local.md`, fora do repositorio. Se esse arquivo
existir, leia antes de responder qualquer coisa sobre "meu servidor": ele ganha
da skill em todo ponto onde os dois discordem.

Este documento e o **molde**, com os valores trocados por placeholders. Copie a
estrutura, preencha com o que e seu, e nunca commite o resultado.

```bash
cp exemplo-de-maquina.md ~/.claude/palserver.local.md
```

## Por que fora do repositorio

Duas razoes, e a segunda pega mais gente:

1. Um arquivo desses carrega IP de VPN, IP da LAN, IP do roteador e as vezes o
   IP publico. Num repositorio publico, um commit basta: `git rm` depois nao
   apaga o historico.
2. `.gitignore` **nao** resolve. Um arquivo ignorado existe so na sua maquina,
   entao a skill funciona para voce e chega quebrada para quem instalar o
   plugin — com uma referencia apontando para nada. Falha silenciosa, que so
   aparece na maquina dos outros. Por isso o molde e publicado e o preenchido
   nao.

---

# Palworld — maquina `<HOSTNAME>`

Medido em `<AAAA-MM-DD>`. Remeça depois de trocar de hardware ou de patch
grande; numero velho e pior do que numero nenhum, porque parece atual.

## A maquina

`<CPU>`, `<RAM>` GB, `<DISTRO E VERSAO>`, `<DE/WM>`.

## Como esta instalado

| Item | Valor |
|---|---|
| Steam | `<como foi instalado: apt/flatpak/etc>` |
| steamcmd | `<caminho, ou "nao instalado">` |
| PalServer | por `<cliente Steam | steamcmd>`, AppID 2394010 |
| Prefixo | `<~/.local/share/Steam/... ou ~/Steam/...>` |
| Versao | `v<X.Y.Z.NNNNNN>`, buildid `<NNNNNNNN>`, atualizado em `<AAAA-MM-DD>` |
| Tamanho | `<N>` GB |
| Mundo ativo | `SaveGames/0/<HEX>/` |
| Backups manuais | `<caminho>` |

Quem instalou pelo cliente Steam **nao** deve apontar o steamcmd para a mesma
pasta: as duas ferramentas disputam o `appmanifest_2394010.acf`. Escolha um
dono.

Conferir versao e buildid sem abrir a Steam:

```bash
grep -E '"(buildid|LastUpdated|StateFlags)"' \
  ~/.local/share/Steam/steamapps/appmanifest_2394010.acf
journalctl --user -u palworld | grep 'Game version is' | tail -1
```

`StateFlags 4` = instalado e integro. As duas fontes tem que concordar: o
manifesto diz o que esta **no disco**, o journal diz o que esta **em memoria**.
Divergiram, o servidor esta rodando binario velho — reinicie.

## Config em vigor

As chaves que voce mexeu, nao o ini inteiro:

```
DeathPenalty=<...>
AutoSaveSpan=<...>
bIsUseBackupSaveData=<True|False>
RESTAPIEnabled=<True|False>
RESTAPIPort=<...>
AdminPassword=<"" se vazio>
PublicPort=<...>
```

`AdminPassword` vazio significa que **nenhum comando de admin funciona**, nem no
chat nem por API. Anote isso explicitamente; e a causa mais comum de "o comando
nao faz nada".

## Rede

| Item | Valor |
|---|---|
| VPN mesh | `<100.x.y.z>` (`<host>.<tailnet>.ts.net`) |
| LAN | `<192.168.N.M>` (`<interface>`) |
| Roteador | `<192.168.N.1>` |
| IP publico | `<estatico | dinamico>` |

Como os jogadores entram, e por que essa escolha: `<VPN mesh | port forward |
community server>`. Se for port forward, registre tambem a reserva de DHCP e o
DDNS — sem IP local fixo a regra do roteador quebra sozinha no proximo lease.

Vale anotar o resultado de `tailscale netcheck` (ou equivalente): `UDP: true` e
`MappingVariesByDestIP: false` indicam NAT que aceita conexao direta. E vale
registrar se ha CGNAT — salto 2 do `traceroute` privado — porque e isso que
decide se port forward era sequer uma opcao.

Firewall local: `<ufw/nftables ativo? o que libera?>`.

## Consumo medido

| Uptime | RSS | CPU | Jogadores online | Data |
|---|---|---|---|---|
| ao subir | `<N>` GB | `<N>`% | `<N>` | `<AAAA-MM-DD>` |
| `<N>`h | `<N>` GB | `<N>`% | `<N>` | `<AAAA-MM-DD>` |

**As colunas de jogadores e data nao sao enfeite — sao o motivo da tabela
existir.** Numa maquina medida, a leitura de maior uptime foi a **mais leve**
(0,59 GB em 11h39, ociosa) e a de 2h foi mais que o triplo (2,13 GB, com gente
dentro). Uptime sozinho nao explicou nada; carga explicou. Uma tabela so com
uptime e RSS registra a variavel errada.

Tres armadilhas ao preencher:

- **Uptime de processo nao prova continuidade.** Um `Signal 11` no meio reseta a
  curva sem aviso. Confira `journalctl --user -u palworld | grep -c 'Game
  version is'` antes de concluir qualquer coisa.
- **Uma parada comandada nao e um crash.** Mudanca de config e atualizacao
  tambem reiniciam o processo; separe as duas no historico ou a serie vira
  ficcao.
- Se duas medicoes discordarem, **registre as duas** e diga qual e de quando.
  Uma curva contraditoria e um dado; uma curva limpa que voce alisou nao e.

## Historico de reinicios

Quantas subidas, quantos crashes, e se o `Restart=on-failure` cobriu todos.

```bash
journalctl --user -u palworld | grep -E 'Signal 11 caught|Game version is'
```

## Timer de restart

Horario escolhido, e **de onde saiu o horario**. O default de meia-noite nao e
sagrado: tire do seu proprio historico de boots qual janela cobre mais noites
com a maquina ligada. O numero de outra pessoa nao e o seu.

`Persistent=true` num timer de usuario dispara o restart logo apos o boot,
derrubando um servidor que acabou de subir. Deixe `false`.

## Se for tirar o servidor daqui

Que maquinas voce ja descartou e por que — poupa refazer a conta. Um alvo de
8 GB de RAM costuma ser o piso pratico; abaixo disso o servidor sozinho come a
maquina depois de algumas horas.

## Segundo servidor, se um dia

Portas ja ocupadas nesta maquina, para nao colidir. Lembre que `RESTAPIPort`
(8212) e `RCONPort` (25575) estao reservados no ini mesmo desligados — escolher
8212 para um segundo servidor cria colisao no dia que a REST API for ligada.
