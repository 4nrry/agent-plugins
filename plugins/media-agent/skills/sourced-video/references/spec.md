# The episode spec

One file per video, written before any voice or render. `scripts/check_sources.py`
reads it; the compositor can read the same file for captions, shots and the
source bar.

```yaml
id: ep012
min_sources: 2              # opened sources per fact line
sources:
  g1:       {url: "https://...", opened: true,  note: "timeline, gives 13h22"}
  poder360: {url: "https://...", opened: true}
  valor:    {url: "https://...", opened: false} # seen in search only: supports nothing
narration:
  - id: N1
    text: "Às 13h22, o pedido chegou ao tribunal."
    caption: "13h22: o pedido chega ao tribunal"
    sources: [g1, poder360]
  - id: N2
    kind: quote             # fact (default), quote, question, framing
    text: "O senador disse que não reconhece o resultado."
    sources: [g1]
  - id: N9
    kind: question
    text: "Quando o ônibus não vem, você espera, vai a pé ou pede carona?"
screen:                     # on-screen text that is not a caption
  - id: S1
    text: "PEDIDO: 13H22"
    sources: [g1, poder360]
left_out:                   # true or not, it stays out of voice and screen
  - id: X1
    reason: single_source   # or unconfirmed, contested_number
    forbid: ["944 ônibus", "mais de 900"]
sides:                      # contested stories: screen time per side
  - {name: "pedido A", seconds: 8.0}
  - {name: "pedido B", seconds: 8.0}
balance_tolerance: 0.1
synthetic_real_person: false
needs_verification:         # links someone still has to open
  - {name: "CBN", url: "https://..."}
```

- `opened: true` means a person (or an agent with a fetch tool) read the page
  and the line's claim is in it; a search snippet is not opened.
- `forbid` lists the exact phrasings a rewrite would reach for, numbers
  included, in every form the voice or screen could use.
- A quote needs one opened source that reports it; the claim inside the quote
  is not thereby confirmed.
- `kind: framing` is for neutral connective lines ("Foram dois pedidos.") that
  restate sourced lines; overusing it to skip the source rule defeats the check.
