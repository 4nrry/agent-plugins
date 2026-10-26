# Short vertical video: platform numbers

Checked against each platform's own pages on 2026-10-26. Community lists of
pixel margins disagree with each other and with these; use the platform's
number or template.

## Per platform

| Platform | Length | Safe zone | Notes |
|---|---|---|---|
| YouTube Shorts | up to 3 min, square or vertical (uploads since 2024-10-15) | no published margins; likes, comments and share sit in a right-hand panel | as an ad, only the first 60 s play in the Shorts feed |
| Instagram Reels (Meta ads) | video ads 0 s to 15 min | keep 14% of the top, 35% of the bottom and 6% of each side free of text, logos and key elements | ad spec asks 1440x2560; 1080x1920 is the same 9:16 |
| TikTok (in-feed ads) | up to 10 min | download the safe-zone file from TikTok's in-feed ad specs; it shrinks as the ad caption grows | 9:16 at 540x960 or more, up to 500 MB |

At 1080x1920, Meta's margins are 269 px top, 672 px bottom and 65 px a side.
Organic posts carry a shorter caption and no call-to-action button, so they
cover less; designing to the ad margins fits both.

## Delivery

YouTube's upload recommendations, as an MP4 the other two also take: H.264 High
profile, 4:2:0 chroma, AAC-LC at 48 kHz, the moov atom at the front, and the
frame rate the piece was made in (1080p SDR: 8 Mbps at 24–30 fps, 12 Mbps at
48–60 fps).

```bash
ffmpeg -i master.mov -c:v libx264 -profile:v high -pix_fmt yuv420p -b:v 8M \
  -c:a aac -ar 48000 -b:a 192k -movflags +faststart short.mp4
```

No platform publishes a loudness target; keep the -16 LUFS master from the
skill.

## Sources

- YouTube Help, "Understand three-minute YouTube Shorts" (answer 15424877).
- YouTube Help, "Recommended upload encoding settings" (answer 1722171).
- Google Ads Help, "YouTube Shorts ads: Asset specs and best practices"
  (answer 16041697).
- Meta Ads Guide, Instagram Reels video and image ad specs.
- TikTok Ads Help, "TikTok Auction In-Feed Ads".
