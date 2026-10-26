# Google Flow

Checked on 2026-10-26, with one live run. Flow (flow.google.com) is Google's
web studio for Gemini Omni Flash, Veo 3.1 and Nano Banana, paid with the Google
AI Plus, Pro or Ultra subscription's credits; there is also a mobile app. It has
no API, and its credits do not reach the Gemini API.

## Credits

Pro adds 1,000 credits a month (no rollover) to the 50 a day everyone gets.

| Model | Credits |
|---|---|
| Gemini Omni Flash, 360p | 4 (4 s), 5 (6 s), 6 (8 s), 7 (10 s) |
| Gemini Omni Flash, 720p | 7 (4 s), 10 (6 s), 12 (8 s), 15 (10 s) |
| Omni Flash edit of a video | 40 |
| Veo 3.1 Lite / Fast / Quality, 8 s | 10 / 20 / 100 (Ultra pays less for Lite and Fast) |

Image costs are not published; the in-product model picker shows the current
price.

## Driving it from an agent

- Use a browser where the user is already signed in: the desktop app's browser
  pane, Claude in Chrome, or a persistent Chrome profile under Playwright. The
  user signs in; never type their password or answer a CAPTCHA.
- Google's terms forbid automated access only against a site's robots.txt or
  around its protections; labs.google's robots.txt allows everything. Keep it
  to the user's own account and pace.
- Flow's own agent panel takes a plain request. Keep **Agent settings →
  Confirm before generating: Always**: it states the cost and asks Approve /
  Always approve / Reject. Approve one generation at a time, and ask for the
  cost before it starts.
- A still from disk needs a browser tool that can fill a file picker (Claude in
  Chrome's upload, Playwright's `set_input_files`). The desktop app's browser
  pane cannot; there, generate the still in Flow or have the user drop it in.
- The clip opens in an editor that extends it (+), edits it from a prompt
  ("change only the sky"), and has the download button. Downloading is the
  user's call; the file carries SynthID.

## Measured

One run on Pro, 2026-10-26: a 16:9 Nano Banana 2.1 still in about 25 s, which
the agent made without asking for approval; then Omni 1.1 Flash animated it as
the first frame at 360p, 8 s. The agent quoted 6 credits, waited for Approve,
queued the job "due to high demand", and finished about a minute later.

## Flow Music

flowmusic.app makes full songs with Lyria 3.5 on daily credits, but publishes
no commercial terms: keep it out of a commercial piece until it does (`audio`
skill).

## Sources

- Google Flow Help, "Get started with Google Flow" (answer 16353333) and
  "Manage your Google Flow credits" (labs answer 16526234).
- Google Terms of Service; labs.google/robots.txt.
- flowmusic.app home page.
