#!/usr/bin/env python3
"""Confere contra o binario instalado cada fato de flag que o SKILL.md cita.

Por que existe: o `android` CLI e novo e se move, e a documentacao do proprio
skill oficial do Google ja esta errada num ponto que este plugin cita — ela
manda `--screen`, o binario exige `--screenshot`. Prosa sobre ferramenta
envelhece; a unica defesa e perguntar ao binario.

    verify_tool_facts.py              # pergunta ao binario instalado
    verify_tool_facts.py --json       # o mesmo, em JSON
    verify_tool_facts.py --self-test  # NAO toca no binario; testa o parser

IMPORTANTE, e o motivo de --self-test nunca invocar `android`: o binario em
cmdline-tools/latest/bin e um bootstrapper. Qualquer invocacao, inclusive
--version, baixa e instala centenas de MB. Num runner de CI isso seria um
download surpresa a cada build.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import subprocess
import sys

# (id, argv de ajuda, precisa conter, nao pode conter, o que o fato sustenta)
FACTS = [
    ("screen-resolve-flag", ["screen", "resolve", "--help"],
     ["--screenshot"], ["--screen="],
     "SKILL.md manda `android screen resolve --screenshot`; a doc do skill do "
     "Google diz `--screen`, que o binario rejeita"),
    ("screen-capture-annotate", ["screen", "capture", "--help"],
     ["--annotate"], [],
     "SKILL.md usa --annotate para enxergar dentro de superficie de GL"),
    ("skills-catalog", ["skills", "--help"],
     ["add", "list"], [],
     "SKILL.md delega o ensino do CLI a `android skills add`"),
    ("docs-search", ["docs", "--help"],
     ["search"], [],
     "SKILL.md delega documentacao a `android docs search`"),
]


# O bootstrapper instala aqui. Ler estes caminhos responde "qual versao" e
# "quantas skills" sem invocar nada — que e o contrato deste arquivo.
CLI_HOME = Path.home() / ".android" / "cli"


def versao_instalada(raiz: Path = CLI_HOME) -> str | None:
    """Versao do CLI lida do disco. Nunca invoca o binario."""
    f = raiz / "skills" / "version"
    try:
        v = f.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return v or None


def catalogo_no_disco(raiz: Path = CLI_HOME) -> int | None:
    """Quantas skills o catalogo do Google traz, contadas no disco.

    As skills citam esse numero com data. Contar aqui deixa a deriva visivel
    sem transformar um numero que muda em criterio de falha.
    """
    d = raiz / "skills"
    if not d.is_dir():
        return None
    return sum(1 for _ in d.rglob("SKILL.md"))


def probe(argv: list[str]) -> str:
    """Roda `android <argv>` e devolve stdout+stderr, ou "" se indisponivel."""
    exe = shutil.which("android")
    if not exe:
        return ""
    try:
        p = subprocess.run([exe, *argv], capture_output=True, text=True, timeout=120)
    except (subprocess.TimeoutExpired, OSError):
        return ""
    return (p.stdout or "") + (p.stderr or "")


def judge(help_text: str, must: list[str], must_not: list[str]) -> tuple[str, str]:
    """Veredito sobre um texto de ajuda. Puro: nao chama processo nenhum."""
    if not help_text.strip():
        return "indisponivel", "binario ausente ou sem resposta"
    faltando = [t for t in must if t not in help_text]
    proibido = [t for t in must_not if t in help_text]
    if faltando:
        return "falhou", f"nao encontrei {faltando} na ajuda"
    if proibido:
        return "falhou", f"encontrei {proibido}, que o SKILL.md afirma nao existir"
    return "ok", "confere"


def run() -> int:
    # Nada de `android --version` aqui: e exatamente a invocacao que a docstring
    # acima chama de download surpresa, e o contrato do --self-test so cobre o
    # que esta em FACTS. O caminho resolvido responde a mesma pergunta ("existe
    # binario?") sem tocar no bootstrapper.
    resultado = {
        "android_path": shutil.which("android"),
        "android_version": versao_instalada(),
        "catalogo_skills": catalogo_no_disco(),
        "facts": [],
    }
    for fid, argv, must, must_not, sustenta in FACTS:
        veredito, razao = judge(probe(argv), must, must_not)
        resultado["facts"].append(
            {"id": fid, "veredito": veredito, "razao": razao, "sustenta": sustenta}
        )

    if "--json" in sys.argv:
        print(json.dumps(resultado, indent=2, ensure_ascii=False))
    else:
        v = resultado["android_path"] or "android nao encontrado no PATH"
        print(f"android: {v}")
        print(f"  versao (lida do disco): {resultado['android_version'] or 'n/d'}")
        print(f"  catalogo do Google: {resultado['catalogo_skills'] or 'n/d'} skills")
        for f in resultado["facts"]:
            marca = {"ok": "ok  ", "falhou": "FALHOU", "indisponivel": "n/d "}[f["veredito"]]
            print(f"  {marca} {f['id']}: {f['razao']}")

    # Ausencia do binario nao e falha: o plugin serve maquina sem SDK tambem.
    return 1 if any(f["veredito"] == "falhou" for f in resultado["facts"]) else 0


def self_test() -> int:
    """Testa o julgamento sem tocar no binario — ver o aviso do bootstrapper."""
    casos = [
        ("Usage: android screen resolve --screenshot=PARAM --string=PARAM",
         ["--screenshot"], ["--screen="], "ok"),
        ("Usage: android screen resolve --screen=PARAM --string=PARAM",
         ["--screenshot"], ["--screen="], "falhou"),
        ("", ["--screenshot"], [], "indisponivel"),
        ("   \n  ", ["--screenshot"], [], "indisponivel"),
        ("Commands:\n  add\n  list\n", ["add", "list"], [], "ok"),
        ("Commands:\n  list\n", ["add", "list"], [], "falhou"),
    ]
    falhas = 0
    for i, (texto, must, must_not, esperado) in enumerate(casos, 1):
        got, razao = judge(texto, must, must_not)
        if got != esperado:
            print(f"caso {i}: esperava {esperado!r}, veio {got!r} ({razao})")
            falhas += 1

    # O contrato que protege o CI: FACTS nunca cita um subcomando vazio, senao
    # `android` sozinho e um bootstrapper esperando entrada.
    for fid, argv, *_ in FACTS:
        if not argv or "--help" not in argv:
            print(f"{fid}: argv precisa terminar em --help, veio {argv}")
            falhas += 1

    # As leituras de disco: ausencia devolve None, nunca excecao — o plugin
    # serve maquina sem o CLI instalado, e um traceback ali seria pior que a
    # informacao que falta.
    with tempfile.TemporaryDirectory() as vazio:
        v = Path(vazio)
        checagens = [
            (versao_instalada(v) is None, "versao: diretorio vazio deveria dar None"),
            (catalogo_no_disco(v) is None, "catalogo: sem skills/ deveria dar None"),
        ]
        (v / "skills").mkdir()
        (v / "skills" / "a").mkdir()
        (v / "skills" / "a" / "SKILL.md").write_text("x", encoding="utf-8")
        (v / "skills" / "version").write_text("  9.9.9  \n", encoding="utf-8")
        checagens += [
            (catalogo_no_disco(v) == 1, "catalogo: nao contou o SKILL.md"),
            (versao_instalada(v) == "9.9.9", "versao: nao aparou espaco"),
        ]
        (v / "skills" / "version").write_text("", encoding="utf-8")
        checagens.append(
            (versao_instalada(v) is None, "versao: arquivo vazio deveria dar None")
        )
        for ok, msg in checagens:
            if not ok:
                print(msg)
                falhas += 1

    print("self-test: ok" if not falhas else f"self-test: {falhas} falha(s)")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else run())
