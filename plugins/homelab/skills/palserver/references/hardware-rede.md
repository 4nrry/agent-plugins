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

A faixa observada numa maquina real ficou entre **0,6 e 2,4 GB**, com CPU de
0,4 a 2,1 nucleos. Dentro dessa faixa, **o uptime nao explicou o RSS**:

| uptime | RSS | contexto |
|---|---|---|
| 2h | 2,13 GB | jogadores online |
| 4h | 1,47 GB (pico 1,80) | sessao anterior |
| 6h10 | 2,40 GB | logo apos dobrar a densidade de spawn |
| 14h | 2,20 GB | jogadores online |
| 20h | 1,73 GB | sessao anterior |
| 11h39 | **0,59 GB** | servidor ocioso |

A leitura mais longa e a mais leve. Uma versao anterior deste texto afirmava que
o RSS "cresce com o uptime e nao estabiliza" — a serie acima **nao sustenta a
afirmacao**, e tambem nao sustenta a oposta. O que ela sugere e que **carga
explica mais que tempo**: as leituras altas tem jogadores dentro ou densidade de
spawn dobrada, e a mais baixa esta ociosa.

As variaveis nunca foram isoladas, entao trate isto como faixa observada e nao
como curva. **Meça a sua**, e desconfie de qualquer numero — inclusive destes —
que venha sem dizer quantos jogadores estavam online.

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
