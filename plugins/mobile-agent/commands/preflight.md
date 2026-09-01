---
description: Checa o que ja esta de pe antes de subir emulador, bundler ou tunel — e diz de qual checkout e cada processo
---

Rode a checagem abaixo e reporte o resultado em tabela. Nao suba nada, nao mate
nada: este comando so observa.

```bash
echo "── aparelhos ──"
adb devices -l 2>/dev/null || echo "adb nao respondeu"
echo "── tuneis ──"
adb reverse --list 2>/dev/null || echo "nenhum (ou sem device)"
echo "── portas de bundler ──"
ss -ltnp 2>/dev/null | grep -E ':(8081|8082|8083)' || echo "8081-8083 livres"
echo "── locks de emulador ──"
ls -1 ~/.android/avd/*.avd/*.lock 2>/dev/null || echo "nenhum"
echo "── memoria ──"
free -h | awk '/^Mem:/{print "  disponivel: "$7}'
```

Para cada porta ocupada, descubra de qual diretorio e o dono, que e a pergunta
que importa quando ha mais de um checkout ou worktree:

```bash
readlink /proc/<pid>/cwd
```

Ao reportar, seja explicito sobre duas coisas:

- **O que e de outra sessao.** Emulador, bundler e container podem nao ser seus.
  Nomeie o que encontrou e nao proponha derrubar nada sem perguntar.
- **Lock orfao.** Um `.lock` de AVD sem processo vivo e residuo de um
  encerramento que nao passou por `adb emu kill`. Inofensivo na maioria das
  vezes; se a proxima subida reclamar de AVD em uso, e ele.

Se algo estiver ausente ou o `adb` nao responder, diga isso em vez de assumir
que esta tudo livre.
