export const meta = {
  name: 'breadth-tier-arm',
  description: 'One arm-run of the breadth-tier paired comparison (eval: plasma67-citations)',
  phases: [{ title: 'Breadth', detail: '5 read-only collectors, one eval item each' }],
}

// The single manipulated variable arrives via args; everything else in this
// file is byte-identical across arms — its sha256 is each record's
// orchestrator_prompt_sha256. Some harness builds deliver args as a JSON
// string rather than an object; accept both.
const parsedArgs = typeof args === 'string' ? JSON.parse(args) : args
const MODEL = parsedArgs && parsedArgs.model
if (MODEL !== 'haiku' && MODEL !== 'sonnet') throw new Error('args.model must be haiku or sonnet')

phase('Breadth')

const SCHEMA = {
  type: 'object',
  required: ['findings', 'unreachable'],
  additionalProperties: false,
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        required: ['claim', 'url', 'quote', 'where'],
        additionalProperties: false,
        properties: {
          claim: { type: 'string', description: 'One factual claim, one sentence, in English.' },
          url: { type: 'string', description: 'The exact URL you fetched this from.' },
          quote: { type: 'string', description: 'Verbatim text copied exactly from the fetched page. On prose pages: one contiguous span, 15-40 words, no ellipses, no fusing separate sentences. On structured pages (package tables, milestone lists) where no sentence exists: the exact cell or row string, verbatim — a version string beats a synthesized sentence.' },
          where: { type: 'string', description: 'Section heading or nearest visible anchor on the page where the quote sits.' },
        },
      },
    },
    unreachable: {
      type: 'array',
      items: {
        type: 'object',
        required: ['url', 'why'],
        additionalProperties: false,
        properties: { url: { type: 'string' }, why: { type: 'string' } },
      },
    },
  },
}

const DISCIPLINE = `
Rules (non-negotiable):
- Prefer primary sources (kde.org, bugs.kde.org, launchpad.net, packages.ubuntu.com, kubuntu.org).
- Every claim carries the URL you ACTUALLY fetched and a verbatim quote copied exactly from that page. If you remember a fact but cannot fetch a page stating it, it is not a finding.
- If a page refuses to load or renders empty, put it in "unreachable" with the reason and move on — do not quote it from memory.
- 3 to 6 findings is the expected size. Do not pad.
- Do not write, create, or modify any files anywhere.`

const QUESTIONS = [
  { key: 'schedule', prompt: `When was (or will be) KDE Plasma 6.7 released, and what is its 6.7.x bugfix schedule? Fetch the kde.org announcement for Plasma 6.7.0 and the announcements listing. Return dated claims.` },
  { key: 'feature', prompt: `Does KDE Plasma 6.7 include per-monitor (per-screen) virtual desktops — a different virtual desktop on each monitor? Fetch the official Plasma 6.7.0 announcement on kde.org. State whether the feature landed, and whether the announcement says it is default or optional.` },
  { key: 'tracker', prompt: `What is the status of KDE bug 107302 (https://bugs.kde.org/show_bug.cgi?id=107302), and which Plasma version fixed it? Fetch the bug page. Return the bug title, status, and the 'Version Fixed/Implemented In' value.` },
  { key: 'backports', prompt: `What plasma-desktop version does the Kubuntu Backports PPA currently publish for Ubuntu 26.04 (Resolute)? Fetch https://launchpad.net/~kubuntu-ppa/+archive/ubuntu/backports?field.name_filter=plasma&field.status_filter=published and read the package rows. Is any 6.7.x build present for 26.04?` },
  { key: 'distro', prompt: `Which plasma-desktop version does Ubuntu 26.10 (Stonking) currently carry? Fetch https://packages.ubuntu.com/stonking/plasma-desktop and https://launchpad.net/ubuntu/stonking/+source/plasma-desktop. Return the version and its upload date.` },
]

const results = await parallel(QUESTIONS.map(q => () =>
  agent(q.prompt + '\n' + DISCIPLINE, {
    label: 'breadth:' + q.key,
    phase: 'Breadth',
    model: MODEL,
    agentType: 'Explore',
    schema: SCHEMA,
  })
))

log('arm=' + MODEL + ': ' + results.filter(Boolean).length + '/5 collectors returned')
return { model: MODEL, perQuestion: QUESTIONS.map((q, i) => ({ key: q.key, result: results[i] })) }
