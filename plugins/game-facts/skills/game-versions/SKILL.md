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

O hook injeta a URL pronta. Ela **nao e chamada** por ele: rede em hook custa
latencia em todo prompt, inclusive nos que nao tem jogo nenhum. Quem busca e
voce, quando a pergunta exigir.

```bash
curl -sS --max-time 20 \
  "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=<APPID>&count=5&maxlength=1500" \
| jq -r '.appnews.newsitems[]
         | select(.feedname=="steam_community_announcements")
         | "\(.date|strftime("%Y-%m-%d"))  \(.title)\n\(.contents)\n\(.url)"'
```

Publico, sem chave. O `select` importa: o feed mistura imprensa (PC Gamer,
PCGamesN) com anuncio do estudio, e materia de site de jogo nao e patch notes.

Verificado em 2026-09-07: `appid=1623730` devolveu
`v1.0.4: Balance Adjustments & Bug Fixes`, autor `pocketpair_dev`, datado do
mesmo dia do `LastUpdated` do manifesto — e o corpo trazia mudanca de chave de
config (`Added "Fish Behavior During Fishing Minigames" to World Settings`).

**Ferramenta nao tem feed.** O appid do Palworld Dedicated Server (2394010)
devolve lista vazia; as notas do servidor saem no appid do cliente. Vale para
dedicated server, SDK e editor em geral.

A ordem, quando for preciso ir para fora:

| ordem | fonte | vale para |
|---|---|---|
| 1 | arquivo no disco (config, save, `Default*.ini`) | **sempre ganha** |
| 2 | saida do proprio jogo (log, journal) | versao de marketing |
| 3 | notas oficiais na Steam, pelo `appid` | o que mudou, datado |
| 4 | doc oficial do estudio | mecanica documentada |
| 5 | wiki da comunidade | mecanica estavel; **nunca** numero ou valor padrao |
| 6 | blog de hosting | ultima instancia, sempre marcado como tal |

Wiki cai no degrau 5 por um motivo mecanico, nao por desprezo: **pagina de wiki
quase nunca diz de que versao fala.** Ela e boa para o que patch raramente toca
— onde acha um item, combinacao de breeding, arvore de missao — e ruim
exatamente para numero, valor padrao e nome de chave, que e o que muda a cada
patch e o que costuma estar sendo perguntado.

Blog de hosting fica por ultimo porque se contradiz e nao data: para Palworld,
guias divergem sobre o proprio padrao de `DeathPenalty`, e uns afirmam que o 1.0
trouxe server clustering enquanto outros negam.

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
