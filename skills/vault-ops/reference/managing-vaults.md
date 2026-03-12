# Vault Configuration

Use `~/.vault-ops.json` in the user's home directory to map vault names to vault paths.

## File Format

Create `./.vault-ops.json` with this structure:

```json
{
  "personal": {
    "path": "/home/user/Documents/personal"
  },
  "work-notes": {
    "path": "/home/user/work/work-notes"
  }
}
```

Use a short, stable vault name as the key. The `path` must point to the vault root directory.

## If The File Is Missing

If `~/.vault-ops.json` does not exist:

1. Look for existing Obsidian vaults.
2. If you find them, tell the user what you found and propose a `~/.vault-ops.json` file.
3. If you do not find any vaults, ask the user for vault paths and create the file from the provided paths.

## Finding Existing Obsidian Vaults

Obsidian desktop tracks vaults in `obsidian.json`. Common locations:

- macOS: `/Users/<username>/Library/Application Support/obsidian/obsidian.json`
- Windows: `%APPDATA%\obsidian\obsidian.json`
- Linux: `~/.config/obsidian/obsidian.json`

If the user runs the Flatpak version of Obsidian, also check `~/.var/app/md.obsidian.Obsidian/config/obsidian/obsidian.json`.

## If No Vaults Are Discoverable

If there are no traces of Obsidian or no discoverable vaults, tell the user to configure `~/.vault-ops.json` manually or provide vault paths.

When the user gives you a path, use the directory name as the default vault name unless the user wants a different name.

Do not assume a default vault from this skill alone. If multiple vaults are configured and the user does not specify one, ask.
