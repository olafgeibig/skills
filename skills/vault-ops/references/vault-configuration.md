# Vault Configuration

The vault-ops configuration file `~/.vault-ops.json` is in the user's home directory. It sets some flags and contains a lit of availabale vaults.

File Format:

```json
{
  "version": 2
  "rg": true,
  "turbovault": true,
  "vaults": [
    "personal": {
      "path": "/home/user/Documents/personal"
    },
    "work-notes": {
      "path": "/home/user/work/work-notes"
    }
  ]
}
```

Logic in pseudocode
```
if jq is not installed
  Tell the user that it is required. Ask user if you shall install it and retry.
  exit
endif

if .vault-ops.json is missing
  create `~/.vault-ops.json`
  detect tools
  detect vaults
  show results
else
  if the version is smaller that in the file format
    migrate the existing file to the new format.
    detect tools
  endif
  if vaults are missing
    detect vaults
  endif
endif
show results.
```

## Detect tools

Check if tools are installed and set the flag in `~/.vault-ops.json` accordingly

### ripgrep
Check if rg is installed, e.g. do `rg --version`. Set the flag. If it is not installed, tell the user to install it: ripgrep (rg) at `https://github.com/burntsushi/ripgrep`

### turbovault
For turbovault we need a two stage check
1. Check if it is installed. Do `turbovault --version`. if yes, move on to stage 2. If it is not installed, tell the user and warn the user that without turbovault the skill will fall back to ripgrep and will miss safety and search features. Point to turbovault at `https://github.com/Epistates/turbovault`, explain that mcp server should run with with `--profile production` option.
2. Check if the turbovault MCP server is available. Try to use `mcp_turbovault_list_vaults`. If it can be called, even if result is empty, turbovault is available.

If both checks are successful, set the trubovaul flag to true, otherwise, false. 


## Detect vaults

1. Look for existing Obsidian vaults.
2. If you find them, tell the user what you found and propose a `~/.vault-ops.json` file.
3. If you do not find any vaults, ask the user for vault paths and create the file from the provided paths.

Obsidian desktop tracks vaults in `obsidian.json`. Common locations:

- macOS: `/Users/<username>/Library/Application Support/obsidian/obsidian.json`
- Windows: `%APPDATA%\obsidian\obsidian.json`
- Linux: `~/.config/obsidian/obsidian.json`

If the user runs the Flatpak version of Obsidian, also check `~/.var/app/md.obsidian.Obsidian/config/obsidian/obsidian.json`.

Use a short, stable vault name as the key, ideally the name of the vault. The `path` must point to the vault root directory.

### If No Vaults Are Discoverable

If there are no traces of Obsidian or no discoverable vaults, tell the user to configure `~/.vault-ops.json` manually or provide vault paths. Show the example format.

When the user gives you a path, use the directory name as the default vault name unless the user wants a different name.

Do not assume a default vault from this skill alone. If multiple vaults are configured and the user does not specify one, ask.
