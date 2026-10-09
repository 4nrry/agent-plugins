# Mobile Agent

O que quebra em silencio quando um agente trabalha num app mobile. Duas camadas:
o aparelho (adb, emulador, arvore de UI) e o bundler (Expo, Metro, prebuild).

## O que ele nao faz, de proposito

Nao ensina o CLI `android` nem o SDK. O Google mantem um catalogo proprio de
skills, com canal de update ciente de agente:

```bash
android skills list        # 22 skills no catalogo, medido em 2026-08-31
android skills add <skill>
android docs search "<termo>"
```

Skill nossa que reensine aquilo compete com quem escreve o binario, e perde.
Medido: das 22, **uma** se aplica a um projeto Expo/React Native — o
`android-profiler`, que age sobre o APK instalado via adb. As outras pressupoem
Compose, XML views, Espresso, Kotlin proprio ou R8 ligado.

Este plugin cobre a camada que aquele catalogo nao toca: falha que nao levanta
erro.

## Componentes

| componente | o que faz |
|---|---|
| `skills/android-device/` | Camada de aparelho: dump de UI, superficie de GL, screenshot, tuneis, processos. |
| `skills/expo-metro/` | Camada de bundler: prebuild silencioso, porta do Metro, node_modules ausente, `EXPO_PUBLIC_`, SDK que nao chega ao shell, modulo nativo que o JS nao sente faltar. |
| `skills/espelhar-celular/` | Ver e controlar o aparelho fisico no PC (scrcpy pela depuracao sem fio) sem instalar um segundo adb; o que nao serve (KDE Connect, Phone Link, DeX). |
| `hooks/` | Doze guardas `PreToolUse`, cada um com seu `if`. Avisam, nunca bloqueiam. |
| `commands/preflight.md` | `/mobile-agent:preflight` — checa o que ja esta de pe. |
| `scripts/adb-ui.sh` | Inspecionar e tocar a tela por texto, sem ler screenshot. |
| `scripts/adb_ui.py` | O parser da arvore, isolado para ser testavel. `--self-test`. |
| `scripts/verify_tool_facts.py` | Confere contra o binario instalado cada flag que as skills citam, e reporta versao do CLI e tamanho do catalogo do Google — ambos lidos do disco, sem invocar o bootstrapper. |

## Por que hooks, e nao so skill

Medicao propria deste repo, no plugin `agent-fleet`: trigger por `description`
disparou em 2 de 30 execucoes que deveriam disparar, recall por query entre 0,00
e 0,33, e nenhuma reescrita melhorou o resultado retido. Skill que depende de ser
lembrada nao e lembrada.

Aqui a skill nao e o gatilho. O hook entrega o aviso no momento do comando; o
slash command cobre a invocacao explicita, que dispara sempre. A skill fica como
destino de quem quiser o contexto inteiro.

## Os guardas

Cada handler carrega o proprio `if`, que segura exatamente uma permission rule —
*"There is no `&&`, `||`, or list syntax for combining rules"*. Por isso sao
doze handlers, e cada forma de invocar o mesmo comando vira um handler (o apt
tem quatro: com e sem `sudo`, `apt` e `apt-get`).

| `if` | por que |
|---|---|
| `Bash(adb kill-server)` | derruba os tuneis de todas as sessoes; o sintoma imita backend fora do ar |
| `Bash(apt install *)`, `Bash(apt-get install *)`, e os dois com `sudo` | `scrcpy` do apt depende do pacote `adb`, que vai para `/usr/bin` na frente do adb do SDK: dois servidores se matando |
| `Bash(scrcpy *)`, `Bash(scrcpy)` | sem `ADB=`, o scrcpy usa o adb que achar; se nao for o do resto da sessao, os tuneis caem e o sintoma aparece no app |
| `Bash(pkill *)` | `-f` casa a propria linha de comando: mata o proprio shell |
| `Bash(pgrep *)` | idem, e o lado que so reporta: um processo que e voce mesmo |
| `Bash(adb shell uiautomator *)` | dump para arquivo pode servir a arvore da rodada anterior |
| `Bash(npx expo run:*)` | com o diretorio nativo presente, o prebuild nao roda; e, no Android, se `ANDROID_HOME` esta vazio e nao ha `sdk.dir`, o Gradle vai parar em "SDK location not found" |
| `Bash(expo run:*)` | idem, sem `npx` |

Todos **avisam e saem 0**. Nenhum bloqueia: um hook que barra o comando do
usuario por engano custa mais do que o aviso que evita.

## Documentado contra observado

As skills marcam a diferenca em cada afirmacao, e isso foi verificado: 37
afirmacoes conferidas contra doc oficial de Expo, Metro, React Native, Android e
Claude Code. **Zero refutadas.** Nove eram verdadeiras mas nao documentadas —
essas dizem "observado" no texto, e nao emprestam autoridade que nao tem.

Exemplos do corte: que `expo run:android` nao reexecuta o prebuild **e**
documentado; que ele nao avisa, nao e. Que o emulador nao tem hardware virtual de
Bluetooth **e** documentado; que o scan volta vazio sem erro, nao e.

## Estado da medicao

**Nao ha run records ainda.** Pela regra zero do `bench/PROTOCOL.md`, uma
alegacao de melhoria sem registro e marketing — entao esta versao nao faz
nenhuma. O que existe e comportamento verificado, nao eficacia medida:

- Guardas exercitados com stdin simulado: 17 casos entre casar e nao casar na
  0.1.0; mais 19 na 0.2.0 (apt, scrcpy e a nota do SDK no `expo run`), num
  ambiente falso — SDK, scrcpy e adb de mentira num diretorio temporario —
  para o resultado nao depender da maquina.
- `espelhar-celular`: a prova sem janela rodou contra um S20 real por Wi-Fi —
  12 s de `--no-playback --record` deram 10 MB, com `adb reverse --list`
  intacto depois. E `apt-get install -s scrcpy` no Ubuntu 26.04 listou o
  pacote `adb` 34.0.5 ao lado do scrcpy 3.3.4, que e a premissa do guarda.
- `expo-metro`, modulo nativo: a verificacao por `expo-modules-autolinking
  resolve` listou `expo-haptics` ao lado de `expo-device` e `expo-secure-store`
  num projeto real, depois de `grep` em `android/` nao achar nada — e o
  `expo run:android` sem `ANDROID_HOME` parou em "SDK location not found"
  depois do prebuild, como a skill descreve.
- `adb_ui.py --self-test`: 7 casos, incluindo dump vazio, sem aparelho.
- `adb-ui.sh` exercitado contra emulador real: `dump` devolveu 14 rotulos com
  bounds, `tap "Chrome"` acertou e trocou de activity, `shot` produziu 58 KB.
- `verify_tool_facts.py` roda contra o binario instalado e passa `--self-test`
  sem toca-lo.

O que falta medir, e que decide se o plugin serve: com que frequencia os guardas
disparam em uso real, e quantos disparos mudaram o que foi feito em seguida.

## Uma armadilha do proprio `android`

O binario em `cmdline-tools/latest/bin/android` e um **bootstrapper**. Qualquer
invocacao — inclusive `--version` — baixa e instala o CLI de verdade, na casa das
centenas de MB. Nao e comando de leitura. Por isso o `--self-test` do script de
verificacao nunca o invoca.
