#!/usr/bin/env python3
"""Parser da arvore de acessibilidade do UI Automator. Sem device, sem adb.

O binario `adb-ui.sh` faz a parte suja (falar com o aparelho); aqui fica so a
logica, que e o que da para testar sozinho:

    adb_ui.py list       < dump.xml     rotulo + bounds, um por linha
    adb_ui.py find TEXTO < dump.xml     "X Y" do centro do melhor no que casa
    adb_ui.py --self-test               nao le stdin; exercita as duas acima
"""
from __future__ import annotations

import re
import sys

NODE = re.compile(r"<node[^>]*>")
ATTR = {
    "text": re.compile(r'\btext="([^"]*)"'),
    "desc": re.compile(r'\bcontent-desc="([^"]*)"'),
}
BOUNDS = re.compile(r'\bbounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"')


def nodes(xml: str):
    """(rotulo, (x1,y1,x2,y2), clicavel) de cada no com rotulo e bounds."""
    for m in NODE.finditer(xml):
        n = m.group(0)
        t = ATTR["text"].search(n)
        c = ATTR["desc"].search(n)
        b = BOUNDS.search(n)
        rotulo = (t.group(1) if t else "") or (c.group(1) if c else "")
        if not rotulo.strip() or not b:
            continue
        yield rotulo, tuple(int(g) for g in b.groups()), 'clickable="true"' in n


def listar(xml: str) -> list[str]:
    vistos, saida = set(), []
    for rotulo, (x1, y1, x2, y2), _ in nodes(xml):
        chave = (rotulo, x1, y1, x2, y2)
        if chave in vistos:
            continue
        vistos.add(chave)
        saida.append(f"{rotulo!r:<52} [{x1},{y1}][{x2},{y2}]")
    return saida


def achar(xml: str, alvo: str) -> tuple[int, int] | None:
    """Centro do melhor no que contem `alvo`.

    "Melhor" e o menor no CLICAVEL: o mesmo rotulo costuma aparecer duas vezes,
    no container que recebe o toque e no TextView interno. Tocar o TextView
    funciona por acidente quando ele esta dentro do container, e falha quando
    nao esta — por isso a preferencia e explicita, nao sorte.
    """
    alvo = alvo.lower()
    melhor = None
    for rotulo, (x1, y1, x2, y2), clicavel in nodes(xml):
        if alvo not in rotulo.lower():
            continue
        chave = (0 if clicavel else 1, (x2 - x1) * (y2 - y1))
        if melhor is None or chave < melhor[0]:
            melhor = (chave, ((x1 + x2) // 2, (y1 + y2) // 2))
    return melhor[1] if melhor else None


FIXTURE = """<?xml version='1.0'?><hierarchy rotation="0">
<node text="" bounds="[0,0][1080,2400]" clickable="false">
 <node text="Continuar" bounds="[100,900][980,1100]" clickable="true">
  <node text="Continuar" bounds="[400,960][680,1040]" clickable="false" />
 </node>
 <node content-desc="Voltar" bounds="[10,150][110,250]" clickable="true" />
 <node text="Sem limite" bounds="[0,300][1080,400]" clickable="false" />
 <node text="" bounds="[0,500][1080,600]" clickable="true" />
</node></hierarchy>"""


def self_test() -> int:
    falhas = []

    itens = listar(FIXTURE)
    # No sem rotulo nao entra; o rotulo repetido em bounds diferentes entra duas
    # vezes, porque sao alvos de toque diferentes.
    if len(itens) != 4:
        falhas.append(f"listar: esperava 4 linhas, veio {len(itens)}")
    if not any("Voltar" in i for i in itens):
        falhas.append("listar: content-desc nao virou rotulo")
    if any("[0,500]" in i for i in itens):
        falhas.append("listar: no sem rotulo vazou para a saida")

    # Prefere o container clicavel (100..980) e nao o TextView interno (400..680).
    if achar(FIXTURE, "continuar") != (540, 1000):
        falhas.append(f"achar: preferiu o no errado, veio {achar(FIXTURE, 'continuar')}")
    # Casa por content-desc, e sem diferenciar maiuscula.
    if achar(FIXTURE, "VOLTAR") != (60, 200):
        falhas.append(f"achar: content-desc/case, veio {achar(FIXTURE, 'VOLTAR')}")
    # Substring casa.
    if achar(FIXTURE, "limite") != (540, 350):
        falhas.append(f"achar: substring, veio {achar(FIXTURE, 'limite')}")
    # Ausente devolve None, e nao um chute.
    if achar(FIXTURE, "nao existe na tela") is not None:
        falhas.append("achar: devolveu algo para rotulo ausente")
    # Dump vazio — o caso da superficie de GL — nao pode explodir.
    if achar("", "qualquer") is not None or listar("") != []:
        falhas.append("dump vazio deveria devolver nada, sem excecao")

    for f in falhas:
        print(f)
    print("self-test: ok" if not falhas else f"self-test: {len(falhas)} falha(s)")
    return 1 if falhas else 0


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    if len(sys.argv) < 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    xml = sys.stdin.read()
    if sys.argv[1] == "list":
        for linha in listar(xml):
            print(linha)
        return 0
    if sys.argv[1] == "find" and len(sys.argv) > 2:
        p = achar(xml, sys.argv[2])
        if p is None:
            return 1
        print(p[0], p[1])
        return 0
    print(__doc__.strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
