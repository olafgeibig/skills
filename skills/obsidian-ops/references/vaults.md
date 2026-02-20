## Find the active vault(s)

Obsidian desktop tracks vaults in its config file `obsidian.json` (source of truth). The locations differs among OS platforms:

- macOS	/Users/<username>/Library/Application Support/obsidian/obsidian.json
- Windows	%APPDATA%\obsidian\obsidian.json
- Linux	~/.config/obsidian/obsidian.json

If you are using the Flatpak version of Obsidian, the path will differ significantly to comply with containerization: ~/.var/app/md.obsidian.Obsidian/config/obsidian/obsidian.json.

`notesmd-cli` resolves vaults from that file; vault name is typically the **folder name** (path suffix).

Fast “what vault is active / where are the notes?”
- If you’ve already set a default: `notesmd-cli print-default --path-only`
- Otherwise, read the config file `obsidian.json` and use the vault entry with `"open": true`.

Notes
- Multiple vaults common (iCloud vs `~/Documents`, work/personal, etc.). Don’t guess; read config.
- Avoid writing hardcoded vault paths into scripts; prefer reading the config or using `print-default`.