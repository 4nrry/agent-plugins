---
name: android-device
description: O que quebra em silencio quando um agente dirige um aparelho Android ou emulador — dump de UI que serve estado velho, superficie de GL invisivel para acessibilidade, screenshot que estoura a sessao por memoria, tuneis do adb que caem sozinhos, e processos que nao sao seus. Leia antes de automatizar qualquer fluxo em device, e de novo quando uma tela "travar" sem erro nenhum. Nao ensina o CLI `android`: para isso use `android skills add` e `android docs search`, que o Google mantem.
---

# Android Device

Dirigir um app num aparelho e diferente de compila-lo. O que falha aqui quase
nunca levanta erro — devolve dado velho, ou nada, e voce diagnostica a coisa
errada por meia hora.

## O que este documento nao cobre, de proposito

O `android` CLI tem catalogo proprio de skills, mantido por quem escreve o
binario, com canal de update ciente de agente:

```bash
android skills list                 # 22 skills no catalogo, hoje
android skills add <skill>          # instala para os agentes detectados
android docs search "<termo>"       # base de conhecimento oficial
```

Se a duvida e sobre um comando do CLI, sobre AGP, Compose, CameraX ou R8, o
catalogo deles responde melhor e envelhece menos. Este documento cobre a camada
que o catalogo nao toca: o agente, e as falhas silenciosas.

## Antes de subir qualquer coisa, veja o que ja esta de pe

Os recursos sao unicos por maquina: uma porta de bundler, um lock por emulador,
um servidor adb. Subir o que ja esta rodando raramente da erro claro — da um
sintoma torto, e em geral na sessao de outra pessoa.

```bash
adb devices                    # ja ha aparelho ou emulador?
adb reverse --list             # que tuneis existem?
ss -ltnp | grep -E ':(8081|8082)'   # quem e dono do bundler
```

Com worktree ou multiplos checkouts, a pergunta que importa e de qual diretorio
e o processo que esta no ar:

```bash
readlink /proc/<pid>/cwd
```

## Ler a tela: dois caminhos, e um ponto cego

**Arvore de acessibilidade** e barata e precisa, e e o caminho padrao. Mas leia
pelo stdout, nunca por arquivo:

```bash
adb exec-out uiautomator dump /dev/tty
```

**Observado, nao documentado.** Nada na doc do UI Automator descreve isso, mas o
dump para arquivo falha em silencio de vez em quando — e quando falha, o arquivo
anterior continua la: voce le a arvore da rodada passada e conclui que a tela
travou quando ela ja mudou. A mitigacao acima custa nada e remove a classe
inteira de erro, entao vale mesmo sem doc que a sustente.

**O ponto cego, e ele e observacao, nao doc.** Superficie de GL nao aparece na
arvore: mapa, video, WebView, canvas — o dump volta vazio ou sem os elementos de
dentro, e isso NAO significa app travado. A doc de acessibilidade de custom views
nao trata desse caso. Medido num app com MapLibre: a arvore devolveu 24 elementos
e nenhum de dentro do mapa; o caminho visual rotulou cerca de 50 la dentro.

Para essas telas, o caminho e visual:

```bash
android screen capture --annotate -o shot.png
adb shell input $(android screen resolve --screenshot shot.png --string "tap #34")
```

Repare em `--screenshot`. A documentacao do proprio skill do Google diz
`--screen`, e o binario responde `Missing required option: '--screenshot=PARAM'`.
O script empacotado aqui checa isso contra o binario instalado:

```bash
scripts/verify_tool_facts.py
```

O plugin tambem empacota a ferramenta, nao so o conselho:

```bash
scripts/adb-ui.sh dump              # rotulo + bounds, pelo stdout
scripts/adb-ui.sh tap "Continuar"   # toca o menor no clicavel que casa
scripts/adb-ui.sh shot out.jpg      # screenshot ja reduzido, seguro de ler
```

Quando a arvore volta vazia, o `dump` explica que provavelmente e superficie de
GL e mostra o caminho visual, em vez de deixar voce concluir que o app travou.

## Screenshot custa mais do que parece

Um screenshot cheio e alguns MB. Ler isso direto numa sessao de agente e o
caminho conhecido para derrubar o processo por memoria — reduza antes:

```bash
adb exec-out screencap -p > shot.png
vipsthumbnail shot.png --size 640x -o small.jpg[Q=85]
```

Duas armadilhas de tempo: `screencap` leva perto de um segundo, entao nao serve
para flagrar transicao rapida — grave com `screenrecord` e extraia quadros. E
ele volta branco as vezes, porque pega o buffer antes do repaint; um micro-swipe
resolve.

## Entrada: nao afogue a fila

`adb shell input swipe` em laco sem pausa deixa a janela "Not Responding". Deixe
cerca de 0,3 s entre eventos.

E confira o que `input text` faz no SEU app antes de confiar: em app com dev
client, certos caracteres disparam atalho de desenvolvedor e recarregam o bundle
no meio do fluxo. Se acontecer, digite em pedacos, cortando antes do caractere
problematico.

## Os tuneis caem sozinhos

`adb reverse` e o mecanismo oficial de forwarding do device para o host, e a doc
confirma que `adb kill-server` termina o servidor, que volta a subir no proximo
comando adb.

**O que e observacao, nao doc:** quando isso acontece, os tuneis **de todas as
sessoes** se perdem. A doc nao diz o que acontece com eles. O sintoma engana — o
app perde a stack e mostra erro de rede, como se o backend estivesse fora.

Antes de cacar bug no backend, confira `adb reverse --list` e reaplique. E nao
rode `adb kill-server` como reflexo de retry — e ele que produz esse estado.

## Processos que nao sao seus

Emulador, bundler, container e dev server podem ser de outra sessao, ou do
usuario. Nao mate o que voce nao subiu; se algo precisa cair, pergunte.

Para casar processo, nunca use `-f` com um padrao que aparece na sua propria
linha de comando: `pkill -f foo` dentro de um comando que contem `foo` mata o
proprio shell, e `pgrep -f` reporta um processo que e voce mesmo. O truque do
colchete nao resolve. Use `-x` com o nome exato, ou o PID de um `ps` anterior.

Para desligar o emulador, o comando documentado e `kill` no console dele; `adb
emu kill` e o atalho que envia esse comando. Qualquer um dos dois, menos SIGTERM
— **observado:** matar direto deixa o lock do AVD para tras.

## O radio do emulador e sintetico

**A causa e documentada:** *"The Android Emulator doesn't include virtual
hardware for the following: Bluetooth"*. Nao ha radio de verdade.

**O modo de falha e observado:** um scan **nao lanca erro, simplesmente nao
encontra nada**. Se vier vazio, isso e o emulador, nao o seu codigo — nao gaste
tempo depurando. Contrato com hardware real exige aparelho fisico.

## Ferramenta muda; verifique antes de citar

O `android` CLI e novo e se move. Nenhum fato de flag aqui vale sem checagem
contra o binario que voce tem:

```bash
scripts/verify_tool_facts.py          # asserta as flags citadas neste documento
scripts/verify_tool_facts.py --self-test
```

Um detalhe que pega: o `android` de `cmdline-tools/latest/bin` e um
bootstrapper. Qualquer invocacao — inclusive `--version` — baixa e instala o CLI
de verdade, na casa das centenas de MB. Nao e um comando de leitura.
