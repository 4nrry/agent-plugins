# Games outside Steam

Only Steam is parsed by `scripts/steam_games.py`. For the rest these are places
to look, with formats **not verified**: open the file and confirm its format
before citing anything from it.

| Launcher | Where to look |
|---|---|
| Heroic (Epic/GOG) | `~/.config/heroic/` — library and install JSON |
| flatpak | `flatpak list --app --columns=application,version` |
| RetroDECK | flatpak `net.retrodeck.retrodeck`; the game version is the ROM's, not the app's |
| Lutris | `~/.config/lutris/` and its sqlite, when present |
| Plain Wine/Proton | no manifest; only the executable and its file date |
