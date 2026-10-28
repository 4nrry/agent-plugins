#!/usr/bin/env bash
# PreToolUse / Kinocut MCP: remind the agent to load a media-agent skill first.
#
# Why: in a 2026-10-28 headless activation test, 7 of 48 media requests went
# straight to a Kinocut tool (audio_sequence, remove_background, video_trim...)
# and never loaded a skill, so its license, loudness and QC rules were skipped.
# Warns at most once per session, and stays silent once any media-agent skill
# has been loaded.
set -uo pipefail

input=$(cat) || exit 0
sid=$(jq -r '.session_id // empty' <<<"$input" 2>/dev/null) || exit 0
transcript=$(jq -r '.transcript_path // empty' <<<"$input" 2>/dev/null) || exit 0
[[ "$sid" =~ ^[A-Za-z0-9_-]+$ ]] || exit 0

marker_dir="${TMPDIR:-/tmp}/media-agent-skill-hint"
marker="$marker_dir/$sid"
[[ -e "$marker" ]] && exit 0
mkdir -p "$marker_dir" 2>/dev/null && : >"$marker" 2>/dev/null

if [[ -r "$transcript" ]] && jq -r 'select(.type == "assistant") | .message.content[]?
    | select(.type == "tool_use" and .name == "Skill") | .input.skill // empty' \
    "$transcript" 2>/dev/null | grep -q '^media-agent:'; then
  exit 0
fi

jq -n '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: (
      "No media-agent skill is loaded yet. Before this Kinocut call, load the " +
      "one that fits with the Skill tool: audio (music, SFX, stock media, noise " +
      "removal, subtitles for a real recording), voice (narration, TTS), " +
      "video-editing (a finished mp4), video-composition (a video built from " +
      "its source project), image-retouching (background removal, upscale, " +
      "inpainting). The skill holds the license, loudness and QC rules that " +
      "Kinocut does not apply."
    )
  }
}'
