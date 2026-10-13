---
name: geracao-ia
description: Gerar imagem e video com IA a partir de assinaturas e creditos que o usuario ja paga — Antigravity CLI (`agy`, Google AI Pro) para still, Grok Build (`grok`, SuperGrok) para clipe curto ou para animar uma imagem, e Veo pela API do Gemini (creditos do Google Developer Program) para plano em 1080p — sem tela, chamando so os binarios e APIs oficiais. Use quando a tarefa pedir imagem gerada, still, video gerado, b-roll gerado, animar uma foto, Veo, Nano Banana, Grok Imagine, agy, Antigravity, Grok Build, Gemini API, creditos do Google Cloud, ou quando o usuario perguntar como usar a assinatura de Gemini ou de Grok num video.
---

# Imagem e video gerados por IA, pelas assinaturas

Tres caminhos, cada um bom numa coisa. Todos rodam sem tela, chamados pelo
agente; nenhum precisa de chave de API paga a parte, exceto o Veo, que gasta
creditos do Google.

| caminho | o que entrega | tempo medido | sai de |
|---|---|---|---|
| `agy` (Antigravity CLI) | still 1376x768, fotorrealista, rico em detalhe | 100 a 175 s | cota do Google AI Pro |
| `grok` (Grok Build) | still 1280x720 em 40 s; clipe de 6 s em 480p, com audio | ~2 min o clipe | cota da SuperGrok |
| Veo 3.1 Fast (API do Gemini) | clipe de 8 s em 1080p, 24 fps, com audio | ~2 min | creditos do Google Cloud |

Fluxo que funcionou: `agy` gera o still → `grok-video.sh --image` anima esse
still como primeiro quadro → o clipe entra como plano curto de apoio. Para
plano que precisa de 1080p, Veo direto.

## Scripts

```bash
S="${CLAUDE_PLUGIN_ROOT}/skills/geracao-ia/scripts"
"$S/agy-imagem.sh" "descricao da cena, sem pessoas, sem texto, 16:9" still.png
"$S/grok-video.sh" "drone avancando devagar, neblina leve" clipe.mp4 --image still.png
python3 "$S/veo.py" "prompt em ingles" -o plano.mp4 --res 1080p --seconds 8 [--image still.png]
```

Os dois `.sh` chamam o binario oficial com o prompt que forca a ferramenta
nativa ("nao escreva codigo para desenhar") e conferem que o arquivo saiu: sem
isso, o agente as vezes escreve um script que desenha algo e diz que gerou.
`veo.py` le `GEMINI_API_KEY` do ambiente; injete com o `run` do gerenciador de
segredos.

## `agy`: still pela cota do Google AI Pro

- Modo sem tela: `agy -p "..." --output-format json --dangerously-skip-permissions --sandbox`.
  A ferramenta de imagem se chama `generate_image`; perguntado, o proprio agy
  disse que nao tem ferramenta de video.
- Termos: em tres respostas do forum oficial (set/2026), rodar o binario
  oficial por script ou por outro agente, na sua maquina e so para voce, foi
  dado como permitido. Quem respondeu nao aparece como funcionario do Google. O
  que os termos proibem explicitamente e usar o login do Antigravity em outra
  ferramenta: MCPs que chamam o endpoint de imagem com o token do agy estao fora.

## `grok`: still e clipe pela cota da SuperGrok

- Modo sem tela: `grok -p "..." --cwd DIR --always-approve --output-format json`.
  Ferramentas observadas: `image_gen` e `reference_to_video`, que gera quadro
  inicial e final e anima entre eles, ou anima a imagem que voce passar.
- **Video sob privacidade ZDR nao sai** sem um bucket seu:
  "Video generation tools are unavailable under zero data retention (ZDR)". Ou
  desliga o modo de privacidade (`/privacy`, decisao do usuario), ou configura um
  bucket S3-compativel (R2, S3, MinIO) com `grok-zdr-bucket.sh`, que grava
  `[tools.zdr_video_output_s3]` em `~/.grok/managed_config.toml`. A chave de R2
  so se cria no painel da Cloudflare; o login do wrangler gerencia bucket, nao
  chave.
- O clipe sai em 480p (848x480 do texto, 736x400 animando imagem). Ampliar nao
  compensa: DAT2 levou 9,5 s por quadro (23 min para 6 s) e RealESRGAN 3,9 s.
  Use onde 480p nao aparece: fundo com desfoque, card pequeno, fundo de Reels.
- O FAQ da xAI diz que imagem e video saem com marca d'agua e que remover viola
  a politica de uso. Nos testes pelo Grok Build nao apareceu marca visivel. Nao
  remova se aparecer.

## Veo pela API do Gemini, com os creditos do Google

Montagem unica, feita pelo usuario porque envolve faturamento:

1. Ativar os beneficios do Google Developer Program da assinatura AI Pro e
   **aplicar cada credito mensal** (US$ 10 cada) numa conta de faturamento, um
   por um, em `me.developers.google.com/benefits`. Creditos de meses anteriores
   ficam acumulados esperando e vencem um ano depois.
2. Criar um projeto ligado a essa conta e a chave no AI Studio, nesse projeto.
3. **Saldo pre-pago acima de zero no AI Studio.** Sem isso a API devolve
   `HTTP 402: Your prepayment credits are depleted` mesmo com creditos do Cloud
   disponiveis. Com saldo, os creditos do Cloud sao gastos antes do saldo.
   Contas novas sao pre-pagas; nao ha como voltar para pos-pago.
4. Teto de gasto: orcamento com **Spend cap enforcement** no servico "Gemini
   API" do projeto. Ele mede o custo de tabela e ignora creditos, entao um teto
   mensal abaixo do credito mensal garante que o cartao nao e tocado. Nao e
   instantaneo: deixe margem.

Uso:

- Modelos (out/2026): `veo-3.1-generate-preview`, `veo-3.1-fast-generate-preview`,
  `veo-3.1-lite-generate-preview`; geracao por `predictLongRunning` e polling
  da operacao.
- Para testar se a chave e o saldo estao vivos sem gastar Veo, uma chamada de
  texto de 1 token serve. `gemini-2.5-*` devolve 404 para usuario novo
  ("no longer available to new users"); use o modelo que a mensagem sugere.

## Antes de publicar

- O Instagram le a marca invisivel (SynthID, C2PA) e poe "AI info" no post nos
  tres casos. Tirar a marca visivel nao esconde que e IA.
- Plano gerado ao lado de filmagem real destoa. Para empresa que vende
  credibilidade tecnica, use como apoio curto, nao como prova.

## O que nao foi verificado

- O custo real de um clipe de Veo contra os creditos: o Cloud leva horas para
  mostrar o consumo, e o teste foi um clipe so.
- Se o video do Grok passa pelo bucket: o R2 seguiu com 0 objetos depois de
  tres videos gerados, e o arquivo chegou na pasta pedida todas as vezes.
- Limite de cota das assinaturas para geracao em volume.
