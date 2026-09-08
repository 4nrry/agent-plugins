---
name: wireguard-networkmanager
description: Importar e verificar VPN WireGuard no NetworkManager a partir de arquivos .conf de Proton VPN, Mullvad, IVPN, AirVPN ou Windscribe, para usar pelo applet de rede do Plasma sem instalar o cliente do provedor. Use sempre que aparecer um .conf de WireGuard, quando a tarefa for VPN no KDE sem app GTK/Electron, quando o app do provedor tropeçar no keyring, ou quando o assunto for vazamento de IPv6/DNS, kill switch, `nmcli connection import type wireguard`, ou o erro "The name of the WireGuard config must be a valid interface name". Cobre também a escolha do servidor, que é onde o vazamento de IPv6 nasce.
---

# VPN WireGuard pelo NetworkManager (KDE)

Os clientes de VPN para Linux são feitos para GNOME. No KDE o que quebra
raramente é o toolkit — é o keyring: o app do provedor pede um Secret Service,
e numa sessão Plasma o `gnome-keyring` e o `ksecretd` disputam o mesmo nome no
D-Bus, então quem ganha a corrida no boot decide se o login sobrevive.

Só que o desktop já tem um cliente WireGuard. O NetworkManager fala WireGuard
nativamente desde a 1.16 e o plasma-nm tem interface para ele, então um `.conf`
importado vira uma conexão comum no applet de rede — sem daemon extra, sem
keyring, sem app do provedor. Este skill cobre esse caminho: escolher o servidor
sem vazar, importar, verificar e remover.

## Antes de gerar a config: o IPv6 decide qual servidor serve

Esta é a parte que os tutoriais pulam e que faz a VPN vazar em silêncio.

```bash
ip -6 -brief address show scope global
```

Se aparecer um endereço global numa interface física, a rede tem IPv6 de
verdade. Aí a config precisa rotear `::/0` além de `0.0.0.0/0` — caso contrário
o IPv4 entra no túnel, o teste de IP passa, e todo o tráfego IPv6 (Google,
YouTube, qualquer coisa atrás da Cloudflare) continua saindo com o endereço
real. A VPN parece funcionar enquanto vaza metade da navegação.

Os provedores marcam quais servidores têm IPv6 — o Proton põe uma etiqueta
"IPv6" na lista de servidores da página de geração. Com IPv6 na rede, essa
etiqueta deixa de ser detalhe e vira requisito. Entre os que sobram, escolha
carga abaixo de ~80% e o país mais próximo (latência), nessa ordem.

Confirme antes de importar:

```bash
grep -i '^AllowedIPs' arquivo.conf
```

Deve conter `0.0.0.0/0, ::/0`.

## Importar

```bash
${CLAUDE_PLUGIN_ROOT}/skills/wireguard-networkmanager/scripts/wg-import.sh ~/Downloads/arquivo.conf Proton
```

O script faz o que dá errado quando feito à mão: fecha a permissão do `.conf`
(vem 644 do navegador, com chave privada dentro), avisa se a rede tem IPv6 e a
config não, encurta o nome para o limite do NM, importa, desliga o autoconnect e
renomeia para o rótulo que aparece no applet.

O segundo argumento é opcional e é só o **prefixo** — normalmente o provedor.
O resto do nome sai de dentro do próprio `.conf`: o provedor grava o rótulo do
servidor como primeiro comentário sob `[Peer]` (`# US-FREE#63`), e o script lê
dali. Então `Proton` vira `Proton US-FREE#63`.

Derivar em vez de digitar é o que mantém a nomenclatura estável. Cada servidor é
um `.conf` separado, e nome escrito à mão diverge entre uma importação e outra
(`Proton US #63` ao lado de `Proton US-FREE#122`). Além disso o nome no applet
passa a ser exatamente o que o painel do provedor mostra — que é onde você
compara carga e a etiqueta IPv6 na hora de escolher o próximo servidor.

## Verificar antes de confiar

```bash
${CLAUDE_PLUGIN_ROOT}/skills/wireguard-networkmanager/scripts/wg-check.sh
```

Checa os três vazamentos que existem nessa montagem — IPv4, IPv6 e DNS — e sai
com código 1 se algum escapar. Rode depois de importar e sempre que a conexão
cair e voltar.

O que ele confere: se o túnel trocou pacotes (RX zerado = handshake nunca
aconteceu), se o IPv6 público é diferente do endereço da rede local, e se as
interfaces com rota padrão ainda resolvem DNS por conta própria. Com o túnel
íntegro, o `systemd-resolved` tira o escopo DNS do Wi-Fi e manda tudo pelo link
do túnel.

## Armadilhas que custam tempo

**O nome do arquivo vira o nome da interface.** Máximo 15 caracteres, sem
caracteres especiais. `Book4Ultra-US-FREE-122.conf` é recusado com "The name of
the WireGuard config must be a valid interface name followed by '.conf'". O
script importa de uma cópia com nome curto.

**Não precisa de `sudo`.** O polkit já autoriza a sessão ativa a criar conexões
de sistema (`pkcheck --action-id org.freedesktop.NetworkManager.settings.modify.system`
responde `yes`). E `sudo` falha em sessão sem terminal, então tentar elevar
atrapalha em vez de ajudar.

**Não teste o IP logo depois de importar.** O handshake e a troca de DNS levam
alguns segundos; consultar na hora dá falso negativo e faz parecer que a VPN não
funcionou. Espere e repita antes de concluir qualquer coisa.

**A rota padrão não aparece onde você espera.** O NM usa policy routing: a
default do túnel vai para uma tabela própria, então `ip route show default`
continua mostrando o Wi-Fi mesmo com tudo dentro do túnel. Confira com `ip rule`
e `ip route show table all default`, ou simplesmente teste o IP público.

**Onde a chave privada acaba.** No Ubuntu 23.10+ o NM grava os perfis via
netplan, em `/etc/netplan/90-NM-<uuid>.yaml` (root, 0600) — não em
`/etc/NetworkManager/system-connections/`, que fica vazio. Em outras distros é o
caminho tradicional. Importa para backup e para remoção.

## Depurar sem derrubar a internet de ninguém

Para testar importação, applet ou detecção de vazamento sem sequestrar o
tráfego real, gere uma config falsa com `AllowedIPs` restrito a `192.0.2.0/24`
(TEST-NET, roteável para lugar nenhum) e chaves de `openssl rand -base64 32`. O
túnel sobe, cria interface, aparece no applet e exercita todo o caminho — sem
tocar na rota padrão. É a diferença entre testar e apostar.

## Uso diário

A conexão liga e desliga pelo ícone de rede do Plasma, ou por
`nmcli connection up "Proton US"` / `nmcli connection down "Proton US"`.

Vários `.conf` de países diferentes podem coexistir; cada um é uma entrada no
applet. Mantenha um ativo por vez — planos gratuitos costumam permitir só uma
conexão simultânea.

## O que este caminho não faz

**Não há kill switch.** Se o túnel cair, o tráfego volta pela rota normal em
silêncio, sem aviso na tela. É a limitação real, e é o motivo de o script deixar
`autoconnect no`: melhor que a VPN exista só quando escolhida do que subir
sozinha e dar uma sensação de proteção que não se sustenta. Quem precisa de kill
switch de verdade precisa do cliente do provedor — `mullvad lockdown-mode on`, por
exemplo.

**Trocar de país é trocar de conexão**, não um menu. E port forwarding, NetShield
e afins são escolhidos na hora de gerar o `.conf`, no site do provedor; depois de
importado, mudar exige gerar outro.

## Remover

```bash
nmcli connection delete "Proton US"
```

O YAML do netplan some junto, mas com um instante de atraso — o netplan reescreve
os arquivos depois. Verificar imediatamente acusa uma sobra que não existe; olhe
de novo antes de sair caçando resíduo.
