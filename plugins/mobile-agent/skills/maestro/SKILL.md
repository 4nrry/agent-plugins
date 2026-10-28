---
name: maestro
description: Writing and running Maestro UI flows on a phone or emulator, through the Maestro MCP server or the CLI — reading the screen before writing selectors, env defaults inside flows, clearState and what it wipes, loading a dev client, a device listed twice, and finding why a step failed. Use when asked to write, fix or run an end-to-end test, a Maestro flow, or a .maestro/ suite.
---

# Maestro

Flows are YAML files the user keeps in the app repository, under `.maestro/`.
Only top-level files there run as the suite; put reusable steps in a
subfolder and call them with `runFlow`.

## Read the screen before writing a selector

Inspect first (`inspect_screen` in the MCP, `maestro hierarchy` in the CLI),
then write the step. A React Native `testID` appears as `resource-id` and is
selected with `id:`. Text selectors are regular expressions: escape
parentheses (`Ativas \(\d+\)`), and use `a|b` to wait for either of two
screens. Explore with inline YAML (`run` with `yaml`), then save what worked
to a file and run the file.

## Env values and defaults

`${...}` is JavaScript. An env variable nobody passed is `undefined`, not an
error, so `${APP_ID || "com.example.app"}` and `${URL ?? "http://localhost:8081"}`
give defaults that `-e NAME=value` overrides.

Not every field takes an expression. `launchApp.clearState` must be a literal
`true` or `false`; an expression there fails with `Incorrect Format`. Use the
separate `- clearState: <appId>` command when the choice depends on the flow.

## clearState logs the user out

It wipes the app's data: session, cached state, local settings. On a device
someone is using, ask before running a flow that clears state, and keep
read-only flows (no clearState, no saves) apart, for example by tag, so they
can run against whatever account is logged in.

## Dev clients

A development build opens on its launcher, not the app. After `launchApp`,
open the dev-client deep link with the bundler URL
(`<scheme>://expo-development-client/?url=<encoded URL>`), and dismiss the
developer-menu notice that appears on first load. Make the URL a flow
variable so the same suite runs against another bundler port, or against a
release build with the step skipped.

## Devices

A phone on USB and wireless debugging at once is listed twice. Pass the
serial with `--device`, or the run may pick the other transport.

## Why a step failed

The run prints a debug folder (`~/.maestro/tests/<timestamp>/<flow>/`). Its
`screen-hierarchy/` JSON holds the screen at the failed step; list its texts
before changing the selector:

```bash
jq -r '.. | objects | .attributes?.text // empty | select(. != "")' <file>.json
```

A selector that fails because the app is on another screen (logged out, a
different account type) is not a selector bug.

`maestro check-syntax` reports `config.yaml` as invalid because it is not a
flow; that error is expected.
