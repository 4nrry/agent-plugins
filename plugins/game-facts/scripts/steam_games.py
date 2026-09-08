#!/usr/bin/env python3
"""Ler os appmanifests da Steam e casar nomes de jogo contra um prompt.

Isolado do hook de proposito: o casamento de nome e a parte que produz falso
positivo, entao e a parte que precisa de teste. O hook em bash so passa o
prompt para ca.

O que a Steam entrega de graca, por jogo instalado: `appid`, `name`, `buildid`,
`LastUpdated` e `StateFlags`. O que ela **nao** entrega e a versao de marketing
("1.0.4"): essa nao existe em lugar nenhum do `.acf`. Quem confunde as duas
reporta um numero que o usuario nunca viu na tela.

Sem dependencia externa: stdlib apenas, igual ao resto do repositorio.

    steam_games.py --json          lista os jogos instalados
    steam_games.py --match-stdin   le um prompt na stdin, imprime o bloco
    steam_games.py --self-test     exercita parse, filtro, casamento e URL
"""

import json
import os
import pathlib
import re
import sys
import tempfile

# Bibliotecas padrao. `libraryfolders.vdf` pode apontar para outras, e e lido
# quando existe — quem tem jogo em HD externo cai nesse caminho.
STEAM_ROOTS = [
    pathlib.Path.home() / ".local/share/Steam/steamapps",
    pathlib.Path.home() / "Steam/steamapps",
    pathlib.Path.home() / ".steam/steam/steamapps",
]

# O que a Steam instala e nao e jogo. Por nome, nao por appid: appid novo de
# Proton aparece a cada versao, e uma lista de ids envelhece calada.
NOT_A_GAME = re.compile(
    r"^(Steam Linux Runtime|Proton |Proton$|Steamworks Common|SteamVR|"
    r"Steam Controller|Blender$)",
    re.I,
)

# Nome curto demais casa qualquer coisa. Quatro caracteres deixa passar "DOOM"
# e barra ruido de duas letras.
MIN_NAME_LEN = 4


def _acf_field(text: str, key: str) -> str | None:
    """Extrai um campo de topo do .acf.

    Deliberadamente raso: os campos que interessam vivem todos no primeiro
    nivel do `AppState`, como `"chave"<tab>"valor"`. Um parser VDF completo
    seria mais codigo para ler exatamente os mesmos cinco campos.
    """
    m = re.search(r'"%s"\s+"([^"]*)"' % re.escape(key), text)
    return m.group(1) if m else None


def steam_roots() -> list[pathlib.Path]:
    roots = [p for p in STEAM_ROOTS if p.is_dir()]
    for root in list(roots):
        vdf = root / "libraryfolders.vdf"
        if not vdf.is_file():
            continue
        try:
            text = vdf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for path in re.findall(r'"path"\s+"([^"]+)"', text):
            extra = pathlib.Path(path) / "steamapps"
            if extra.is_dir() and extra not in roots:
                roots.append(extra)
    return roots


def installed_games(roots=None) -> list[dict]:
    """Jogos instalados e integros, ordenados por nome."""
    out, seen = [], set()
    for root in roots if roots is not None else steam_roots():
        for acf in sorted(root.glob("appmanifest_*.acf")):
            try:
                text = acf.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            name = _acf_field(text, "name")
            appid = _acf_field(text, "appid")
            if not name or not appid or appid in seen:
                continue
            if NOT_A_GAME.search(name) or len(name) < MIN_NAME_LEN:
                continue
            seen.add(appid)
            updated = _acf_field(text, "LastUpdated") or "0"
            out.append({
                "appid": appid,
                "name": name,
                "buildid": _acf_field(text, "buildid") or "?",
                # StateFlags 4 = instalado e integro. Outro valor significa
                # download parcial, update pendente ou arquivos faltando — o
                # buildid nesse caso nao descreve o que esta no disco.
                "state_ok": _acf_field(text, "StateFlags") == "4",
                "updated_epoch": int(updated) if updated.isdigit() else 0,
                "manifest": str(acf),
            })
    return sorted(out, key=lambda g: g["name"].lower())


def match(prompt: str, games: list[dict]) -> list[dict]:
    """Jogos cujo nome aparece no prompt, como frase inteira.

    Frase inteira e nao token: "It Takes Two" so casa se as tres palavras
    vierem juntas. Casar por token faria "two" disparar em qualquer prompt de
    matematica. A borda e nao alfanumerica dos dois lados, entao "palworld"
    casa e "palworldish" nao.
    """
    hits = []
    for g in games:
        pattern = r"(?<![0-9A-Za-z])%s(?![0-9A-Za-z])" % re.escape(g["name"])
        if re.search(pattern, prompt, re.I):
            hits.append(g)
    return hits


# Feed oficial do estudio na Steam. Sem chave, publico, e datado — a unica
# fonte que liga o buildid do disco a versao que o jogador ve. `count` baixo
# porque o feed mistura imprensa (PC Gamer, PCGamesN) com anuncio do estudio;
# quem filtra e quem consome, por feedname == "steam_community_announcements".
NEWS_API = "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/"


def news_url(appid: str, count: int = 5, maxlength: int = 1500) -> str:
    """URL das notas oficiais desse appid. Nao faz rede: so monta.

    Rede fica fora deste script de proposito — ele roda no hook, a cada prompt,
    e latencia de rede em todo prompt custa mais do que a dica vale.
    """
    return f"{NEWS_API}?appid={appid}&count={count}&maxlength={maxlength}"


def render(hits: list[dict]) -> str:
    import datetime as _dt

    linhas = [
        "O prompt menciona jogo instalado nesta maquina. Antes de responder "
        "qualquer coisa sobre mecanica, config, patch ou balanceamento:",
        "",
    ]
    for g in hits:
        quando = (_dt.datetime.fromtimestamp(g["updated_epoch"]).strftime("%Y-%m-%d")
                  if g["updated_epoch"] else "desconhecida")
        estado = "" if g["state_ok"] else "  [StateFlags != 4: instalacao incompleta ou update pendente]"
        linhas.append(f"  {g['name']}  appid={g['appid']}  buildid={g['buildid']}  "
                      f"atualizado={quando}{estado}")
        linhas.append(f"      notas oficiais: {news_url(g['appid'])}")
    linhas += [
        "",
        "1. `buildid` NAO e a versao de marketing. O .acf nao guarda \"1.0.4\" em "
        "lugar nenhum. Se voce precisa do numero que o jogador ve, ele sai do log "
        "do proprio jogo, da tela de titulo, ou de consulta externa — nunca "
        "invente a correspondencia entre os dois.",
        "2. Compare a data acima com o seu corte de treino. Se o jogo foi "
        "atualizado depois, voce NAO sabe o que mudou: patch altera valor "
        "padrao, renomeia chave de config e remove mecanica inteira.",
        "3. Respondendo de memoria mesmo assim, diga que e de memoria e de "
        "quando. Nao apresente lembranca de treino como estado atual do jogo.",
        "4. Havendo arquivo de config ou save no disco, ele ganha da sua "
        "memoria e ganha de qualquer guia. Leia o arquivo.",
        "5. Roteie a pergunta antes de buscar. Valor DESTA instancia (chave, "
        "estado atual) -> leia o disco, zero rede. Dado embarcado (default, "
        "nivel, custo, o que mudou) -> FACTUAL. Ordenacao, superlativo, rota, "
        "\"vale a pena\" -> META. Hibrida responde os dois ramos separados e "
        "rotulados.",
        "6. Passo zero dos dois ramos: leia as notas oficiais acima e liste o que "
        "tocou o subsistema da pergunta, ate o ultimo patch que mexeu nele. "
        "Medido em levantamento de 80 fontes: so esse passo invalidou conteudo em "
        "10 de 10 categorias, e ~1/4 eram correcoes de bug — a fonte mediu com "
        "honestidade uma build quebrada, e nenhuma qualidade editorial pega isso.",
        "7. Ao pesar fontes: \"tem data\" nao e sinal de frescor (84% tinham data, "
        "90% eram pre-patch); o que discrimina e data POSTERIOR ao ultimo patch do "
        "subsistema. Concordancia nao eleva confianca — maioria resolveu 0 de 41 "
        "contradicoes, e o maior aglomerado era uma fonte copiada cinco vezes; "
        "triangule entre TIPOS diferentes. Numero de wiki vale se e so se a pagina "
        "exibir last-edited E (tag de versao OU data pos-patch) — por pagina, nao "
        "por dominio. Detalhe e ressalvas do metodo na SKILL.md.",
    ]
    return "\n".join(linhas)


def _self_test() -> int:
    falhas = []

    def check(cond, msg):
        if not cond:
            falhas.append(msg)

    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)

        def escreve(appid, name, buildid, updated, state="4"):
            (root / f"appmanifest_{appid}.acf").write_text(
                '"AppState"\n{\n'
                f'\t"appid"\t\t"{appid}"\n'
                f'\t"name"\t\t"{name}"\n'
                f'\t"StateFlags"\t\t"{state}"\n'
                f'\t"buildid"\t\t"{buildid}"\n'
                f'\t"LastUpdated"\t\t"{updated}"\n'
                "}\n", encoding="utf-8")

        escreve("1623730", "Palworld", "25094871", "1788752359")
        escreve("2394010", "Palworld Dedicated Server", "25080279", "1788753730")
        escreve("1426210", "It Takes Two", "18385016", "1754000000")
        escreve("105600", "Terraria", "24893155", "1755000000")
        escreve("1391110", "Steam Linux Runtime 2.0 (soldier)", "1", "1")
        escreve("1493710", "Proton Experimental", "2", "2")
        escreve("999999", "Half-Life", "3", "3", state="1026")

        jogos = installed_games([root])
        nomes = [g["name"] for g in jogos]

        check("Palworld" in nomes, "nao achou Palworld")
        check("Terraria" in nomes, "nao achou Terraria")
        check(not any("Steam Linux Runtime" in n for n in nomes),
              "runtime da Steam nao foi filtrado")
        check(not any(n.startswith("Proton ") for n in nomes),
              "Proton nao foi filtrado")
        check(nomes == sorted(nomes, key=str.lower), "saida nao esta ordenada por nome")

        pal = next(g for g in jogos if g["name"] == "Palworld")
        check(pal["buildid"] == "25094871", f"buildid errado: {pal['buildid']}")
        check(pal["appid"] == "1623730", "appid errado")
        check(pal["state_ok"] is True, "StateFlags 4 deveria ser integro")

        hl = next(g for g in jogos if g["name"] == "Half-Life")
        check(hl["state_ok"] is False, "StateFlags 1026 deveria ser nao-integro")

        # --- casamento ---
        m = [g["name"] for g in match("como configura guilda no palworld", jogos)]
        check(m == ["Palworld"], f"minusculo deveria casar so Palworld, casou {m}")

        m = [g["name"] for g in match("subir o Palworld Dedicated Server", jogos)]
        check("Palworld Dedicated Server" in m and "Palworld" in m,
              f"o nome longo e o curto deveriam casar, casou {m}")

        m = match("um prompt sobre kubernetes e postgres", jogos)
        check(m == [], f"prompt sem jogo deveria casar nada, casou {m}")

        m = match("palworldish nao e o jogo", jogos)
        check(m == [], "borda direita falhou: palworldish casou")

        m = match("no-palworld-branch", jogos)
        check([g["name"] for g in m] == ["Palworld"],
              "hifen deveria contar como borda")

        m = match("it takes two hours to compile", jogos)
        check([g["name"] for g in m] == ["It Takes Two"],
              "frase inteira deveria casar mesmo em outro sentido")

        m = match("this takes two hours", jogos)
        check(m == [], "casar por token e falso positivo: 'takes two' sem 'it'")

        bloco = render(match("terraria", jogos))
        check("buildid=24893155" in bloco, "render nao trouxe o buildid")
        check("NAO e a versao de marketing" in bloco, "render perdeu a regra 1")

        # --- notas oficiais: a URL e montada, nunca buscada ---
        u = news_url("1623730")
        check(u.startswith("https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/"),
              f"endpoint errado: {u}")
        check("appid=1623730" in u, f"appid nao entrou na URL: {u}")
        check("&count=" in u and "&maxlength=" in u, f"faltou count/maxlength: {u}")
        check(news_url("105600") != news_url("1623730"),
              "appids diferentes deveriam gerar URLs diferentes")
        check(news_url("1623730", count=1) != news_url("1623730", count=5),
              "count deveria entrar na URL")
        check("api.steampowered.com" in bloco,
              "render deveria citar as notas oficiais do jogo casado")
        check("FACTUAL" in bloco and "META" in bloco,
              "render perdeu o roteamento (regra 5)")
        check("Passo zero" in bloco, "render perdeu o passo zero (regra 6)")
        check("last-edited" in bloco and "por dominio" in bloco,
              "render perdeu o portao de wiki por pagina (regra 7)")
        check("0 de 41" in bloco,
              "render perdeu o dado que derruba voto de maioria")

    for f in falhas:
        print(f"FALHA: {f}", file=sys.stderr)
    print(f"self-test: {len(falhas)} falha(s)")
    return 1 if falhas else 0


def main() -> int:
    args = sys.argv[1:]
    if "--self-test" in args:
        return _self_test()

    if "--match-stdin" in args:
        prompt = sys.stdin.read()
        if not prompt.strip():
            return 0
        hits = match(prompt, installed_games())
        if hits:
            print(render(hits))
        return 0

    games = installed_games()
    if "--json" in args:
        json.dump(games, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        for g in games:
            flag = "" if g["state_ok"] else "  (instalacao incompleta)"
            print(f"{g['appid']:>10}  {g['name']:<36} buildid={g['buildid']}{flag}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(0)
