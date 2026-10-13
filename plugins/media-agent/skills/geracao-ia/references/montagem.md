# Montagem (uma vez so)

So para quando `grok`, `agy` ou o Veo falharem. Cada passo de faturamento e do usuario.

## agy (Antigravity CLI)

- Assinatura Google AI Pro ou Ultra, `agy` instalado e logado.
- Sem tela: `agy -p "..." --output-format json --dangerously-skip-permissions --sandbox`.
  A ferramenta de imagem e `generate_image`; nao ha ferramenta de video.
- Termos: rodar o binario oficial por script ou por outro agente, na maquina e
  so para o usuario, foi dado como permitido no forum oficial (set/2026), por
  quem nao aparece como funcionario do Google. Usar o login do agy em outra
  ferramenta (MCPs que chamam o endpoint com o token dele) e proibido pelos
  termos.

## grok (Grok Build)

- Assinatura SuperGrok, `grok` instalado e logado.
- Sem tela: `grok -p "..." --cwd DIR --always-approve --output-format json`.
  Ferramentas observadas: `image_gen` e `reference_to_video`.
- Video com privacidade ZDR ligada devolve "Video generation tools are
  unavailable under zero data retention (ZDR)". Ou o usuario desliga
  (`/privacy`), ou configura um bucket S3-compativel seu:
  `S3_ENDPOINT=... S3_BUCKET=... scripts/grok-zdr-bucket.sh`, que grava
  `[tools.zdr_video_output_s3]` em `~/.grok/managed_config.toml`. Chave de R2 so
  se cria no painel da Cloudflare.

## Veo (API do Gemini com creditos do Google)

1. Beneficios do Google Developer Program ativos pela assinatura AI Pro; cada
   credito mensal (US$ 10) aplicado numa conta de faturamento, um por um.
2. Projeto ligado a essa conta e chave criada no AI Studio, nesse projeto.
   `GEMINI_API_KEY` no gerenciador de segredos, injetada so no processo.
3. **Saldo pre-pago acima de zero no AI Studio.** Sem ele: `HTTP 402: Your
   prepayment credits are depleted`, mesmo com creditos do Cloud aplicados. Com
   saldo, os creditos sao gastos antes. Conta nova e pre-paga, sem volta.
4. Teto: orcamento com Spend cap enforcement no servico "Gemini API" do
   projeto. Mede o preco de tabela e ignora creditos; teto mensal abaixo do
   credito mensal mantem o cartao de fora. Nao e instantaneo.

Modelos (out/2026): `veo-3.1-generate-preview`, `veo-3.1-fast-generate-preview`,
`veo-3.1-lite-generate-preview`. Para testar chave e saldo sem gastar Veo, uma
chamada de texto de 1 token; `gemini-2.5-*` devolve 404 para usuario novo.
