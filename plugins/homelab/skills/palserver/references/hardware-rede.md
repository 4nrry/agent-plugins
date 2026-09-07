# Hardware, rede e como medir

## Requisitos oficiais

| Item | Oficial |
|---|---|
| CPU | "4 Core +" |
| RAM | "16GB Recommended for larger than 32GB. 8GB is also bootable" |
| Disco | SSD — "Low-performance storage may corrupt saved data" |
| SO | Windows 64bit, Linux 64bit ("Ubuntu, AlmaLinux etc...") |
| Rede | "UDP Port 8211 (Default, Changeable)" |

Palworld depende de **single-core forte**. Mais nucleos lentos nao compensam.

Veredito pratico por maquina (derivado de medicao, nao oficial):

| Maquina | Serve? |
|---|---|
| 16 GB + CPU moderno + SSD | Sim, folgado |
| 8 GB + CPU decente + SSD | Sim, poucos jogadores, restart periodico obrigatorio |
| 8 GB + CPU antigo de 2 nucleos | Nao — rubber-banding com Pals na base |
| 4 GB | **Nao** — o servidor sozinho passa disso |
| Qualquer uma com HDD/eMMC | Problema serio — save frequente trava tudo |

Rodar cliente do jogo + servidor na mesma maquina funciona, mas e o cenario
pesado: some o consumo dos dois.

## Consumo: ordem de grandeza

O RSS do PalServer **cresce com o uptime e nao estabiliza**. A faixa observada em
uma maquina real foi ~1,0 GB ao subir chegando a ~1,7-2,1 GB depois de algumas
horas, com CPU em torno de 1,3 nucleos sustentados. A Pocketpair afirma ter
corrigido vazamentos no 1.0; o crescimento persiste.

Trate esses numeros como ordem de grandeza, **nao como constante** — variam com
mundo, jogadores e versao. Meça a sua.

## Como medir de verdade

```bash
# recursos do processo agora
ps -o pid,etime,rss,%cpu -p "$(pgrep -x PalServer-Linux)"

# amostragem ao longo do tempo, para ter a curva e nao um ponto
while :; do
  printf '%s %s\n' "$(date +%s)" \
    "$(ps -o rss= -p "$(pgrep -x PalServer-Linux)")"
  sleep 300
done >> ~/palworld-rss.log
```

**Uptime de processo nao prova continuidade.** O servidor crasha de vez em quando
e o `Restart=on-failure` sobe outro; a curva reseta sem aviso. Antes de concluir
qualquer coisa sobre crescimento de memoria, confira se houve reinicio no meio:

```bash
journalctl --user -u palworld | grep -c 'Game version is'    # quantas subidas
journalctl --user -u palworld | grep 'Signal 11 caught'      # crashes
```

A rota REST `metrics` tambem devolve uptime, jogadores e memoria, sem depender do
`ps` (ver `references/api-e-comandos.md`).

## Rede

| Porta | Protocolo | Obrigatoria? |
|---|---|---|
| 8211 | UDP | Sim (jogo). Muda com `-port=` |
| 27015 | UDP | Nao (query Steam). **Nao configuravel** |
| 8212 | TCP | So se a REST API for ligada. Nunca exposta |
| 25575 | TCP | So RCON, que esta deprecado |

Nunca TCP para a porta do jogo.

Tres formas de deixar os jogadores entrarem:

**VPN mesh** (Tailscale, Netbird, ZeroTier) — nada exposto, o roteador nao e
tocado, e os jogadores usam o IP da VPN com a porta 8211. Bom para grupo pequeno
e conhecido. Exige que cada jogador instale a VPN.

**Port forward** de 8211/UDP — o classico. Exige IP local fixo (reserva de DHCP,
porque o IP interno costuma ser dinamico) e DDNS se o IP publico tambem for.
Com o servidor exposto, `ServerPassword` deixa de ser opcional.

**Community server** (`-publiclobby`) — aparece na lista publica do jogo. E o
unico jeito de Xbox e PS5 entrarem.

Diagnostico rapido:

```bash
# portas escutando
ss -ulnp | grep -E ':(8211|27015)\b'

# tem gente jogando? keepalive fica na casa de centenas de B/s;
# jogador real sobe para KB/s. Troque IFACE pela interface em uso.
t1=$(awk '/IFACE/{print $10}' /proc/net/dev); sleep 8
t2=$(awk '/IFACE/{print $10}' /proc/net/dev); echo "TX: $(( (t2-t1)/8 )) B/s"
```

Atras de CGNAT, port forward nao funciona — o salto 2 do traceroute ser um IP
privado e o sinal. Nesse caso restam VPN mesh, community server ou VPS.
