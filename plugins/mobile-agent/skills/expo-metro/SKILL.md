---
name: expo-metro
description: O que quebra em silencio num projeto Expo/React Native — o prebuild que nao roda e nao avisa, o Metro que serve o bundle de outro checkout, node_modules ausente que derruba so o bundler enquanto tsc e jest passam, e EXPO_PUBLIC_ que carrega segredo para dentro do APK. Leia antes de gerar build local, antes de mexer em app.json ou em config plugin, e quando uma mudanca "nao fizer efeito" sem erro nenhum.
---

# Expo / Metro

O padrao das falhas aqui e o mesmo: **sucesso aparente**. O comando termina em
zero, o build diz `BUILD SUCCESSFUL`, e o efeito que voce esperava nao aconteceu.
Voce entao depura o lugar errado.

## O prebuild que nao roda

A armadilha mais cara, porque nao emite aviso nenhum.

**Documentado.** Com o diretorio `android/` ja presente, `expo run:android`
**nao prebuilda**. A doc de Continuous Native Generation e explicita: *"If native
directories are absent, npx expo prebuild will run once for the specific
platform. On subsequent uses of these run commands, manually run npx expo
prebuild --clean"*.

**Observado, nao documentado:** que isso acontece **sem aviso nenhum**. Mudanca em
`app.json`, em config plugin ou em icone e ignorada, o Gradle reaproveita os
recursos antigos e responde `BUILD SUCCESSFUL` em segundos. A doc descreve o
comportamento; nao caracteriza o silencio.

Sintoma para reconhecer: build que **deveria** regenerar recurso e termina rapido
demais, com o log indo direto para a fase de compilacao sem nenhuma linha de
prebuild.

```bash
npx expo prebuild --platform android --clean
```

O `--clean` importa: *"The --clean option deletes any existing native directories
before generating. Re-running npx expo prebuild without the --clean option will
layer changes on top of the existing files, which is faster, but may not produce
the same results in some cases."*

Um falso positivo comum ao procurar isso no log: as tarefas `> Task :algo:preBuild`
do Gradle **nao** sao o prebuild do Expo. E coincidencia de nome, e um `grep
prebuild` no log dispara nelas.

## Um Metro por porta, e a porta e do primeiro

O bundler escuta 8081 por padrao — documentado do lado do React Native
(*"The Metro bundler runs on port 8081"*), nao na doc do Metro, que so expoe
`server.port` como opcao sem default declarado.

**Observado:** se ja ha um Metro ali, o segundo nao sobe limpo, e o dev client
continua falando com o primeiro. Voce edita um checkout e ve o bundle do outro,
sem nada indicando isso. A doc oficial trata apenas o conflito de porta e oferece
duas saidas — matar o processo, ou trocar a porta. **Prefira trocar a porta**: o
processo pode ser de outra sessao.

A pergunta que importa, quando ha mais de um checkout ou worktree, e de qual
diretorio e o processo que esta no ar:

```bash
ss -ltnp | grep ':8081'
readlink /proc/<pid>/cwd
```

Para trabalhar em paralelo, porta explicita (`--port 8082`) e o deep link
correspondente. Nao basta subir na outra porta e esperar que o app siga.

## node_modules ausente derruba so o bundler

Assimetria que confunde: num diretorio sem `node_modules` proprio — worktree, ou
um checkout onde o install nao rodou — `npx expo`, `tsc` e `jest` funcionam
normalmente, porque o Node resolve subindo a arvore. **So o Metro quebra**, com
404 no bundle e uma mensagem de modulo nao resolvido.

**Observado, nao documentado:** o Metro parece pedir o caminho literal relativo
a raiz do projeto, e ali ele nao existe. Nenhuma doc oficial descreve esse modo
de falha. Se tudo passa menos carregar o bundle, suspeite disso antes de
suspeitar do codigo.

Cuidado ao remediar com symlink, e ha base documentada para a cautela: o Metro
**nao segue symlinks automaticamente**, e arquivos fora do `projectRoot` exigem
`watchFolders` explicito. Alem disso o symlink entrega a arvore de dependencias
de OUTRO checkout — serve para rodar o app, **nao serve para gerar build**. Se a
branch mexeu em `package.json`, o artefato sai compilado contra a versao errada e
nada avisa; o erro so aparece em runtime.

Sobre paralelismo, o que e documentado: `maxWorkers` do Metro tem default de
aproximadamente **metade** dos cores reportados por `os.availableParallelism()`,
valores acima do numero de cores nao tem efeito, e ha dois pools independentes —
transformacao e construcao do mapa de arquivos — cada um com essa contagem.

## Fast Refresh pode ficar preso

**Observado, nao documentado.** Ao renomear ou criar uma constante de modulo em
duas edicoes separadas, o HMR as vezes fica no estado intermediario e mostra erro
de render com o typecheck limpo. Recarregue o app antes de caçar bug inexistente.

Nao confunda com o que a doc DESCREVE, que e outro caso: quando o arquivo editado
exporta algo consumido fora da arvore React, o Fast Refresh cai para reload
completo. Isso e degradacao prevista, nao o travamento acima.

Corolario para automacao: quando um teste depende de codigo novo ter chegado ao
aparelho, prove que chegou. Um marcador visivel na tela — um texto que voce
mudou de proposito — custa nada e distingue "a mudanca nao funcionou" de "a
mudanca nao chegou".

## EXPO_PUBLIC_ viaja dentro do artefato

**Documentado, e com aviso explicito na propria doc:** *"Do not store sensitive
info, such as private keys, in EXPO_PUBLIC_ variables. These variables will be
visible in plain-text in your compiled application."*

Tudo que comeca com `EXPO_PUBLIC_` e substituido no bundle em tempo de build. Nao
e lido em runtime, nao fica no servidor: **vai dentro do APK**, e sai de la com
`unzip` mais `strings`.

Consequencia pratica: um `.env.local` com credencial de bancada produz um
artefato com aquela credencial embutida. Aceitavel num build interno apontando
para homologacao; vazamento num build de producao.

Para gerar um artefato sem carregar os arquivos `.env`:

```bash
EXPO_NO_DOTENV=1 npx expo ...
```

Antes de distribuir qualquer artefato, confira o que foi parar dentro dele. O
bundle e bytecode Hermes, entao `grep` direto da falso negativo — extraia as
strings primeiro:

```bash
unzip -p app.apk assets/index.android.bundle | strings -n 6 | grep -F "<valor>"
```

## Quando o dev client abre no launcher

Depois de subir o Metro, o dev client pode abrir a tela do launcher em vez de
carregar o bundle, e a tela parada parece travamento.

A doc oferece os caminhos previstos: conectar pelo bundler detectado na rede
local, pela conta Expo logada nos dois lados, ou pelo QR code. **Nenhum deles e o
deep link.** O deep link abaixo e atalho util em automacao, quando nao ha quem
escaneie QR code — nao e o mecanismo documentado:

```
<scheme>://expo-development-client/?url=http%3A%2F%2Flocalhost%3A8081
```

O menu de desenvolvedor costuma abrir por cima na primeira carga. Feche antes de
concluir que a tela nao respondeu.

## O que este documento nao cobre

API de pacote, configuracao de `app.json`, EAS Build e workflow do Expo: use a
documentacao versionada oficial. Ela e a fonte, e envelhece menos que qualquer
copia. Este documento cobre so o que falha sem dizer que falhou.
