# Plugin icons

One SVG per plugin. Each is the source of that plugin's
`plugins/<plugin>/.claude-plugin/icon.png`, the file a plugin directory shows
beside the listing.

| Plugin | Drawing | Background |
|---|---|---|
| agent-fleet | three paper planes in formation | `#4338CA` |
| agents-md | the Markdown mark | `#334155` |
| crew | one filled circle above three open ones | `#0F766E` |
| extension-audit | a puzzle piece | `#C2410C` |
| game-facts | a joystick | `#7E22CE` |
| homelab | a laboratory flask | `#15803D` |
| media-agent | a clapperboard | `#BE123C` |
| mobile-agent | a phone with a face | `#0369A1` |

The drawings use no text and no fonts, so any SVG renderer gives the same
result. After editing an SVG, render its PNG again (libvips 8.18 here):

```bash
vips copy "assets/icons/crew.svg[scale=2]" "plugins/crew/.claude-plugin/icon.png[compression=9,strip]"
```

The PNG is 1024 × 1024 with transparent corners. The size and format rules a
directory applies are in extension-audit's
[checklist](../../plugins/extension-audit/skills/auditing-agent-extensions/references/checklist.md),
and `lint_extensions.py --directory plugins` checks them.
