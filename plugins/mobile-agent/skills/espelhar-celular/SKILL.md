---
name: espelhar-celular
description: Ver e controlar a tela de um aparelho Android fisico no PC, como se fosse o emulador — scrcpy pela depuracao sem fio ja conectada, sem instalar um segundo adb que derruba os tuneis. Diz o que NAO serve (KDE Connect nao espelha; Phone Link e so Windows; DeX para Linux acabou), como instalar sem sombrear o adb do SDK, como provar que funciona sem abrir janela, e as armadilhas em Wayland, com GPU hibrida e com tela protegida. Leia quando precisar olhar um celular real sem pegar nele, gravar um teste em video, ou quando o espelho "nao conecta" e o adb some junto.
---

# Espelhar o celular no PC

O emulador tem uma janela; o aparelho fisico nao. Quando o teste exige hardware
real — radio, sensor, o toque de verdade — voce precisa ver a tela dele sem
segurar o telefone. A ferramenta para isso e o **scrcpy**, e o que da errado
nao e o espelho: e o segundo `adb` que vem junto e derruba o que ja estava de pe.

## O que nao serve, para nao perder tempo

- **KDE Connect nao espelha a tela.** O site lista notificacoes, arquivos, area
  de transferencia, controle de midia e "remote input" (um trackpad virtual).
  Nada de video do aparelho. Documentado por omissao: a lista de recursos e a
  lista inteira.
- **Phone Link / Link to Windows** e so Windows.
- **Samsung DeX para Linux foi descontinuado**; nao ha cliente Samsung em Linux.
- **Vysor** faz o mesmo que o scrcpy, pago para o uso completo. Os frontends
  graficos (QtScrcpy e afins) sao casca sobre o scrcpy.
- **Android Studio "Running Devices"** espelha o aparelho dentro da IDE, por
  USB ou Wi-Fi. Serve se a IDE ja esta aberta; a doc nao fala de gravacao.

## scrcpy: o que e

Espelha, controla por mouse e teclado, grava (`--record`), audio (Android 11+),
camera (12+), display virtual (`--new-display`). Fala com o aparelho pelo adb,
e por isso funciona com a depuracao sem fio que ja esta conectada. Projeto da
Genymobile, mantido ativamente: <https://github.com/Genymobile/scrcpy>.

Confira as flags citadas aqui contra o binario que voce tem (`scrcpy --help`,
`man scrcpy`): foram conferidas na **5.0.1** (2026-10-08).

## Instalar sem um segundo adb

O ponto que decide tudo. **Documentado:** o pacote `scrcpy` do Ubuntu depende do
pacote `adb`. **Medido (Ubuntu 26.04, 2026-10-09):** `apt-get install -s scrcpy`
traz o scrcpy 3.3.4 (duas versoes atras) e instala `adb` 34.0.5 em `/usr/bin`.

O `adb` do SDK mora em `$ANDROID_HOME/platform-tools`, e a doc do React Native
manda **anexar** isso ao `PATH`, nao prefixar. Entao `/usr/bin/adb` passa a
vencer. **Observado:** com dois binarios de versoes diferentes, cada chamada
diz `adb server version doesn't match this client; killing...` e reinicia o
servidor — e isso leva junto todos os `adb reverse` e a conexao sem fio (ver a
skill `android-device`: e o mesmo estrago do `adb kill-server`, so que a cada
comando).

O caminho que nao sombreia nada e o **tarball oficial do release**, instalado
por usuario, com um wrapper que fixa o adb do SDK. **Documentado (man scrcpy,
secao ENVIRONMENT):** a variavel `ADB` e o caminho do adb que o scrcpy usa.

```bash
# release oficial; o tarball Linux traz scrcpy, scrcpy-server, um adb e o man
gh release download v5.0.1 --repo Genymobile/scrcpy \
  --pattern 'scrcpy-linux-x86_64-v5.0.1.tar.gz'
tar -tzf scrcpy-linux-x86_64-v5.0.1.tar.gz | head     # olhe antes de extrair
```

Layout: `~/.local/opt/scrcpy/<versao>/` com `current ->` a versao ativa, e o
wrapper em `~/.local/bin/scrcpy` (se o plugin `homelab` estiver instalado,
`tarball-install --name scrcpy --exec scrcpy --app-version 5.0.1 --no-desktop`
faz isso). O wrapper:

```sh
#!/bin/sh
export ADB="${ADB:-${ANDROID_HOME:-$HOME/Android/Sdk}/platform-tools/adb}"
exec "$HOME/.local/opt/scrcpy/current/scrcpy" "$@"
```

O adb que vem no tarball da 5.0.1 e o 37.0.1, o mesmo do SDK de hoje — mas
"mesma versao" e coincidencia de data, nao garantia. O wrapper e a garantia.

O release nao publica SHA-256 do tarball; a origem (repositorio oficial, TLS)
e a unica verificacao disponivel. Diga isso em vez de fingir que conferiu.

## Conectar: use o que ja esta de pe

Se o aparelho ja esta no `adb devices`, o scrcpy o encontra. Com mais de um,
`-s <serial>`. Para depuracao sem fio, conecte **pelo nome mDNS**, nao pelo
`IP:porta`:

```bash
adb mdns services               # lista "adb-<serial>-xxxx  _adb-tls-connect._tcp"
adb connect adb-<serial>-xxxx._adb-tls-connect._tcp
```

**Observado, nao documentado:** `adb connect IP:porta` falhou onde o nome
funcionou, no mesmo aparelho e na mesma rede. A doc do adb descreve os dois;
nao explica a diferenca.

Nao rode `adb kill-server` para "resolver" uma queda: e ele que produz a queda.

## Prove sem abrir janela

Antes de confiar no espelho, prove o caminho inteiro sem interface — serve em
sessao de agente, onde nao ha quem olhe a janela:

```bash
timeout 12 scrcpy -s <serial> --no-playback --no-audio --record saida.mkv
ls -la saida.mkv                 # cresceu?
adb devices; adb reverse --list  # a conexao e os tuneis continuam?
```

**Medido (S20, Android 13, Wi-Fi):** 12 s produziram 10 MB de video, e
`adb reverse --list` ainda mostrava o tunel do Metro depois. O arquivo sai sem
trailer quando o `timeout` mata o processo; e so prova, nao gravacao.

## Usar como emulador

```bash
scrcpy --window-title "S20 · app"              # janela; mouse toca, teclado digita
scrcpy --record ~/Videos/teste.mkv             # grava o teste inteiro
scrcpy --stay-awake                            # so faz efeito COM CABO
```

**Documentado (man):** `--stay-awake` mantem o aparelho acordado "when the
device is plugged in". Por Wi-Fi, nao faz nada — ajuste o tempo de tela no
aparelho.

## Armadilhas

- **Wayland (KDE, GNOME).** O scrcpy roda por XWayland por padrao; nao precisa
  configurar. **Documentado (FAQ):** no Plasma, o KWin pode desligar a
  composicao enquanto a janela esta aberta — e a regra "Block compositing" da
  janela. `SDL_VIDEODRIVER=wayland` testa o backend nativo.
- **GPU hibrida e decodificacao.** **Documentado (release 5.0):** a
  decodificacao por hardware (VA-API) passou a ser padrao. Se a janela ficar
  preta ou o log reclamar do driver, `--hwdec=disabled`.
- **Tela preta so em algumas telas.** **Documentado (Android, `FLAG_SECURE`):**
  conteudo marcado como seguro nao sai em captura de tela nem em espelho.
  Banco, cofre, algumas telas de login. Nao e o scrcpy, e nao tem solucao sem
  root.
- **Mouse que nao toca (Samsung One UI, Xiaomi).** **Documentado (FAQ):** ative
  "USB debugging (Security settings)" nas opcoes de desenvolvedor e reinicie o
  aparelho.
- **Avisos do FFmpeg** sobre "profile 100" sao normais: informam o perfil H.264
  que o aparelho escolheu.

## O que este documento nao cobre

Compilar o scrcpy, usar OTG/gamepad, audio e camera: a doc do projeto
(`doc/linux.md`, `doc/shortcuts.md`) e a fonte e envelhece menos.
