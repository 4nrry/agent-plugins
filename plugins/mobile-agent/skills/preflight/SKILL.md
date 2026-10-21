---
name: preflight
description: Checks what is already running before starting an emulator, bundler or adb tunnel — devices, reverse tunnels, bundler ports, AVD locks, free memory — and which checkout owns each process. Read-only. Use before starting mobile tooling, especially with several checkouts, worktrees or agent sessions on one machine.
---

# Preflight

Observe only: start nothing, kill nothing. Report the result as a table.

```bash
echo "-- devices --";       adb devices -l 2>/dev/null || echo "adb did not answer"
echo "-- tunnels --";       adb reverse --list 2>/dev/null || echo "none (or no device)"
echo "-- bundler ports --"; ss -ltnp 2>/dev/null | grep -E ':(8081|8082|8083)' || echo "8081-8083 free"
echo "-- AVD locks --";     ls -1 ~/.android/avd/*.avd/*.lock 2>/dev/null || echo "none"
echo "-- memory --";        free -h | awk '/^Mem:/{print "  available: "$7}'
```

For each busy port, find the owning checkout: `readlink /proc/<pid>/cwd`.

In the report:

- Name what belongs to another session (emulator, bundler, container) and do
  not propose stopping it without asking.
- An AVD `.lock` with no live process is left over from a shutdown that
  skipped `adb emu kill`; it explains an "AVD already in use" error.
- If `adb` did not answer or something is missing, say so; do not assume
  everything is free.
