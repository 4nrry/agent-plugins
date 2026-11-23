#!/usr/bin/env python3
# Adapted from digitalsamba/claude-code-video-toolkit, tools/copy_lint.py
#   read from the fork 4nrry/claude-code-video-toolkit at commit
#   5430de721de2d162e0ee5c02e6d824d7e774c359
#   MIT License, Copyright (c) 2024 Digital Samba
#   (COPY_RULES verbatim; lint_text, prose_lines and lint_file; the self-test cases
#   ported from tests/python/test_copy_lint.py)
# The MIT licence asks that its copyright notice and permission notice travel with
# substantial portions: the full text is in THIRD_PARTY_NOTICES.md beside this script.
# Changed from upstream: findings warn and exit 0 unless --strict (upstream exits 1);
# the voice JSON is read; a pt-BR rule list is added. Not ported: --diff and --commits,
# which lint a repository's own pages and commit subjects, not a voice-over script.
"""Lint a voice-over script for stock, AI-sounding phrasing before it goes to the TTS.

  copy_lint.py [--lang pt|en] [--strict] [--json] FILE... [--text TEXT]...
  copy_lint.py --self-test

FILE is the voice JSON ([{id, text, say}]: both `say`, what is spoken, and
`text`, the caption, are linted), or plain text, Markdown or HTML read as prose
(code, tags and comments skipped, as upstream).

  en  upstream's rules as they are: any dash, stock AI phrasing, stock
      marketing phrases.
  pt  (default) the pt-BR house rules below plus upstream's English phrase
      rules (anglicisms turn up in Brazilian copy); upstream's any-dash rule
      is replaced by a dash-overuse rule.

The pt-BR list is a house list, not measured: clichéd openers, "não é apenas
X, é Y", and Portuguese translations of the phrases upstream flags in English.
A style lint never fails a build: findings print and the exit is 0. With
--strict any finding exits 1. Exit 2 when a file is missing or unreadable.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

# ---------------------------------------------------------------- upstream rules (verbatim)
COPY_RULES = [
    (re.compile(r"—|\s–\s|\s--\s"), "a dash; use a comma, a full stop or a new sentence"),
    (re.compile(r"\bit'?s worth noting\b|\bit is (worth|important) (noting|to note)\b", re.I),
     "'it's worth noting'; say the point"),
    (re.compile(r"\bin today'?s (fast-paced |busy |modern )?(world|age|landscape)\b|\bmoving forward\b"
                r"|\bfirst and foremost\b|\blast but not least\b|\bwithout further ado\b|\ball in all\b"
                r"|\bin conclusion\b|\bshed light on\b|\bpave the way\b|\bat the forefront\b|\bdeep[- ]dive\b"
                r"|\bdelve\b|\btapestry\b|\bembark on a journey\b|\bunlock (your|the) (full )?potential\b"
                r"|\bgame[- ]changer\b|\bnavigat(e|ing) the (complexities|world|landscape)\b"
                r"|\bseamless(ly)?\b|\bresonate(s)? with\b|\btestament to\b", re.I),
     "stock AI phrasing; say it the way a person would"),
    # taste-skill's stock marketing phrases (scripts/lint.mjs, 'copy'), so one list covers both
    (re.compile(r"\b(unleash|supercharge|elevate[sd]?|empower(s|ing)?|revolutioni[sz]e[sd]?|game[- ]changing"
                r"|cutting[- ]edge|next[- ]gen(eration)?|world[- ]class|best[- ]in[- ]class|all[- ]in[- ]one"
                r"|effortless(ly)?|blazing(ly)?[- ]fast|lightning[- ]fast|reimagin(e|ed|ing)|leverag(e|es|ing)"
                r"|synergy|streamline[sd]?|holistic|turbocharge[sd]?|transform the way"
                r"|take your .{1,30} to the next level|say goodbye to|the future of|built for the modern)\b", re.I),
     "a stock marketing phrase; say the specific thing it does"),
]

# ---------------------------------------------------------------- pt-BR house rules (not measured)
# Each entry is either a cliché opener or the Portuguese form of a phrase upstream
# flags in English, so upstream's reason carries over. Nothing here was counted
# in a corpus; it is this plugin's taste, and every hit is a warning.
DASH = re.compile(r"—|\s–\s|\s--\s")
PT_MAX_DASHES = 2   # one aside set off by a pair is fine; a third dash is a pile-up the TTS reads unevenly
SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")
PT_RULES = [
    (re.compile(r"\bvocê sabia que\b|\bneste vídeo\b(?!-)|\bno vídeo de hoje\b"
                r"|\bhoje (nós )?vamos (falar|conversar|explorar|mergulhar|descobrir|entender)\b"
                r"|\bvamos mergulhar\b|\bmergulh(ar|e|o|amos) (fundo|de cabeça)\b|\bprepare-se para\b"
                r"|\bsem mais delongas\b", re.I),
     "a stock opener; start with the point"),
    (re.compile(r"\bnão (é|são|foi|era) (apenas|só|somente|simplesmente)\b[^.!?\n]{1,80}?[,;:—–]\s*(é|são|foi|era)\b"
                r"|\bnão se trata (apenas|só|somente) de\b"
                r"|\bmais do que (apenas|só)\b[^.!?\n]{1,60}?,\s*(é|são)\b", re.I),
     "'não é apenas X, é Y'; say what it is"),
    (re.compile(r"\bvale (a pena )?(notar|ressaltar|destacar|lembrar|mencionar) que\b"
                r"|\bé importante (notar|ressaltar|destacar|lembrar) que\b", re.I),
     "'vale ressaltar que' (it's worth noting); say the point"),
    (re.compile(r"\bno mundo (acelerado |moderno |digital |atual )?de hoje\b|\bnos dias (de hoje|atuais)\b"
                r"|\bem constante (evolução|transformação)\b|\bpor (último|fim),? mas não menos importante\b"
                r"|\blançar luz sobre\b|\babrir (o )?caminho para\b|\bna vanguarda\b"
                r"|\b(é|foi|será|seria|representa|representou) (um )?(verdadeiro )?divisor de águas\b"
                r"|\bembarc(ar|ue|amos) (nessa|nesta|numa|em uma) jornada\b"
                r"|\bdesbloque(ar|ie) (o seu |seu |todo o (seu )?)?potencial\b"
                r"|\bnavegar (pelas|nas) complexidades\b|\bde forma (fluida|integrada)\b", re.I),
     "a stock phrase translated from English; say it the way a person would"),
    # verb forms only: "alavanca" and "turbina" are also nouns (a lever, a turbine)
    (re.compile(r"\b(alavanc(ar|ando|ou|aram|amos|ará|arão|arem)|potencializ(ar|a|am|ando|ou)"
                r"|revolucion(ar|a|am|ou|ando)|turbin(ar|ando|ou|aram|ará|arem)"
                r"|de última geração|de classe mundial|tudo[- ]em[- ]um"
                r"|(leve|levar|eleve|elevar) [^.!?\n]{1,30} (ao|a um|para o) (próximo|outro) nível(?=\s*([.,;:!?]|$))"
                r"|diga adeus (aos?|às?|a))\b", re.I),
     "a stock marketing phrase; say the specific thing it does"),
]


def lint_text(text: str, lang: str = "en") -> list[tuple[str, str]]:
    """(matched text, reason) for every rule hit in a piece of prose."""
    text = unicodedata.normalize("NFC", text)     # decomposed accents would slip past the pt patterns
    rules = COPY_RULES if lang == "en" else PT_RULES + COPY_RULES[1:]
    out = []
    for rx, why in rules:
        for m in rx.finditer(text):
            out.append((m.group(0).strip(), why))
    if lang == "pt":
        for sentence in SENTENCE_END.split(text):
            dashes = DASH.findall(sentence)
            if len(dashes) > PT_MAX_DASHES:
                out.append((f"{len(dashes)} dashes", f"dash overuse (more than {PT_MAX_DASHES} in one sentence); "
                                                     "use a comma, a full stop or a new sentence"))
    return out


def prose_lines(path: Path) -> list[tuple[int, str]]:
    """The file's prose, line by line, with code, tags and comments blanked so line numbers still match."""
    src = path.read_text(encoding="utf-8")
    keep_newlines = lambda m: "\n" * m.group(0).count("\n")
    if path.suffix.lower() in (".html", ".htm"):
        src = re.sub(r"<!--.*?-->|<(pre|code|script|style)\b.*?</\1>", keep_newlines, src, flags=re.S | re.I)
        # the title and meta description are public too (search results, link previews): keep their text
        src = re.sub(r"<meta\b[^>]*\bcontent=\"([^\"]*)\"[^>]*>", r" \1 ", src, flags=re.I)
        src = re.sub(r"<[^>]+>", " ", src)
        src = html.unescape(src)
    elif path.suffix.lower() in (".md", ".markdown"):
        src = re.sub(r"```.*?```|<!--.*?-->", keep_newlines, src, flags=re.S)
        src = re.sub(r"`[^`\n]*`", " ", src)
        src = re.sub(r"\]\([^)]*\)", "]", src)  # link targets
    return list(enumerate(src.split("\n"), 1))


def lint_file(path: Path, lang: str = "en") -> list[dict]:
    if path.suffix.lower() == ".json":
        return lint_voice_json(path, lang)
    return [{"file": str(path), "line": n, "match": m, "reason": why}
            for n, line in prose_lines(path) for m, why in lint_text(line, lang)]


def lint_voice_json(path: Path, lang: str) -> list[dict]:
    """Each item's `say` and `text`; "line" is the item's position, 1-based."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("lines") or data.get("sentences") or data.get("items")
    if not isinstance(data, list) or not all(isinstance(i, dict) for i in data):
        raise ValueError("expected a list of {id, text, say} objects")
    out = []
    for n, item in enumerate(data, 1):
        for field in ("say", "text"):
            value = item.get(field)
            if isinstance(value, str):
                out += [{"file": str(path), "line": n, "id": item.get("id"), "field": field, "match": m,
                         "reason": why} for m, why in lint_text(value, lang)]
    return out


def lint(files: list[Path], texts: list[str], lang: str) -> list[dict]:
    findings = [{"file": "--text", "line": i, "match": m, "reason": why}
                for i, t in enumerate(texts, 1) for m, why in lint_text(t, lang)]
    for f in files:
        findings += lint_file(f, lang)
    return findings


# ---------------------------------------------------------------- self-test
def self_test() -> int:
    checks = 0

    def hits(text, lang="en"):
        return [m.lower() for m, _ in lint_text(text, lang)]

    # upstream's RulesTest
    h = hits("A seamless tool — it's worth noting it will elevate you")
    assert {"—", "seamless", "it's worth noting", "elevate"} <= set(h), h
    assert lint_text("It writes the script, voices it and renders the MP4.") == []
    assert lint_text("A 50-second video, well-made, at 9:16.") == []   # hyphens are fine
    checks += 3
    # pt-BR house rules
    for flagged in ("Você sabia que o Brasil tem 27 estados?", "Neste vídeo, vamos ver o orçamento.",
                    "Não é apenas um aplicativo, é uma revolução.", "Não é só sobre dinheiro — é sobre tempo.",
                    "Vale ressaltar que o prazo acabou.", "No mundo acelerado de hoje, tudo muda.",
                    "Essa ferramenta vai alavancar seus resultados.", "Diga adeus às planilhas.",
                    "Foi um divisor de águas para a cidade.", "Uma solução de última geração."):
        assert lint_text(flagged, "pt"), flagged
        checks += 1
    for clean in ("O relatório custa até vinte mil reais por mês.",
                  "A conta, que já era alta, subiu de novo.",
                  "A conta — que já era alta — subiu de novo.",       # one aside: two dashes are fine in pt
                  "Não é só isso: o prazo também mudou.",
                  "Ele não apenas votou, mas também discursou.",
                  "A empresa não era só pequena, mas também endividada.",
                  "A alavanca do freio quebrou e a turbina parou.",
                  "O curso quer levar o aluno ao próximo nível escolar.",
                  "Assista neste vídeo-aula ao resumo.",
                  "O museu guarda uma tapeçaria do século XV.",
                  "A serra é o divisor de águas entre as duas bacias.",
                  "Ela prestou um testemunho de duas horas.",
                  "Em conclusão, o juiz negou o pedido.",
                  "Ganhou a prova sem esforço nenhum.",
                  "Um — dois — três. Quatro — cinco — seis."):     # dashes are counted per sentence
        assert lint_text(clean, "pt") == [], (clean, lint_text(clean, "pt"))
        checks += 1
    for flagged in ("Isso vai alavancar suas vendas.", "Vamos turbinar o seu perfil.",
                    "Leve sua empresa ao próximo nível.", "Foi um verdadeiro divisor de águas.",
                    unicodedata.normalize("NFD", "Você sabia que o prazo acabou?")):
        assert lint_text(flagged, "pt"), flagged
        checks += 1
    assert hits("A conta — que já era alta — subiu de novo.", "en") == ["—", "—"]   # en keeps upstream's rule
    assert any("dash overuse" in w for _, w in lint_text("Um — dois — três — quatro.", "pt"))
    assert hits("Um deep dive no game-changer.", "pt") == ["deep dive", "game-changer"]   # anglicisms in pt copy
    checks += 3
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)

        def write(name, text):
            p = t / name
            p.write_text(text, encoding="utf-8")
            return p

        # upstream's FilesTest
        p = write("a.html", '<head><meta name="description" content="A game-changer"></head>\n'
                            '<p>Plain words.</p>\n<pre><code>ls -- --flag — ok</code></pre>\n'
                            '<!-- a comment — fine -->\n<p class="seamless">tag attributes are not copy</p>\n')
        assert [(f["line"], f["match"]) for f in lint_file(p)] == [(1, "game-changer")]
        p = write("a.md", "Text with `--x — y` code.\n```\ncmd — arg\n```\n[docs](https://x/seamless)\n"
                          "A real dash — here.\n")
        assert [(f["line"], f["match"]) for f in lint_file(p)] == [(6, "—")]
        checks += 2
        # the voice JSON: say and text both
        v = write("v.json", json.dumps([{"id": "s1", "text": "Neste vídeo: custos.", "say": "Os custos subiram."},
                                        {"id": "s2", "text": "Tudo certo.", "say": "Você sabia que custa caro?"}],
                                       ensure_ascii=False))
        got = [(f["id"], f["field"]) for f in lint_file(v, "pt")]
        assert got == [("s1", "text"), ("s2", "say")], got
        checks += 1
        # exit codes: warn by default, 1 with --strict, 2 on a missing file
        cli = lambda *a: subprocess.run([sys.executable, __file__, *a], capture_output=True, text=True)
        ok, warned, strict = cli("--text", "Palavras simples."), cli(str(v)), cli("--strict", str(v))
        missing = cli(str(t / "nope.json"))
        assert (ok.returncode, warned.returncode, strict.returncode, missing.returncode) == (0, 0, 1, 2), \
            (ok.returncode, warned.returncode, strict.returncode, missing.returncode)
        assert "2 finding(s)" in warned.stdout, warned.stdout
        assert cli("--lang", "en", "--strict", "--text", "Delve in").returncode == 1
        assert json.loads(cli("--json", str(v)).stdout)["ok"] is False
        checks += 3
    print(f"self-test: {checks} checks ok")
    return 0


# ---------------------------------------------------------------- main
def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("files", nargs="*", type=Path, help="voice JSON, or text, Markdown or HTML files")
    p.add_argument("--text", action="append", default=[], help="lint a string (repeatable)")
    p.add_argument("--lang", choices=("pt", "en"), default="pt", help="rule set (default pt)")
    p.add_argument("--strict", action="store_true", help="exit 1 on any finding")
    p.add_argument("--json", action="store_true")
    p.add_argument("--self-test", action="store_true", help="run the rule and CLI checks")
    a = p.parse_args()
    if not a.files and not a.text:
        p.error("give files or --text")
    for f in a.files:
        if not f.is_file():
            print(f"copy_lint: {f} not found", file=sys.stderr)
            return 2
    try:
        findings = lint(a.files, a.text, a.lang)
    except (OSError, ValueError, UnicodeDecodeError) as e:
        print(f"copy_lint: cannot read input: {e}", file=sys.stderr)
        return 2

    if a.json:
        print(json.dumps({"ok": not findings, "lang": a.lang, "findings": findings}, indent=2, ensure_ascii=False))
    else:
        for x in findings:
            where = f"{x['file']}:{x['line']}" + (f" {x['id']}.{x['field']}" if "field" in x else "")
            print(f"{where}  '{x['match']}' is {x['reason']}")
        print(f"{len(findings)} finding(s)" + ("" if a.strict else ", warnings only") if findings
              else "copy lint: clean")
    return 1 if findings and a.strict else 0


if __name__ == "__main__":
    sys.exit(main())
