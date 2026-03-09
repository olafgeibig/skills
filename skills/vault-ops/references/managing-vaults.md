## Vaults Config

We need to know which vaults exists and where. For this purpose we need to maintain a config file `<your-workspace-dir>/.vault-ops.json` that is stored in the root of the workspace. It has this format:

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

The name of the vault is the name of its directory. If it does not exists, you must create it. If you create the file, try to find the existing vaults, see below.

## Find existing Obsidian vaults

Obsidian desktop tracks vaults in its config file `obsidian.json` (source of truth). The locations differs among OS platforms:

- macOS	/Users/<username>/Library/Application Support/obsidian/obsidian.json
- Windows	%APPDATA%\obsidian\obsidian.json
- Linux	~/.config/obsidian/obsidian.json

If you are using the Flatpak version of Obsidian, the path will differ significantly to comply with containerization: ~/.var/app/md.obsidian.Obsidian/config/obsidian/obsidian.json.

## Finding other non-obsidian vaults
If there are no traces of an installed Obsidian, then inform the user about manually configuring the vaults in `.vault-ops.json`. Offer the user to tell you the paths to a vault. And then name the vault the same as the directory of the vault. 

## The default vault
To simplify using the skill, there should be a default vauly. The default vault should be declared in TOOLS.md in a section for this skill. If this section does not exist, list the found vaults and ask the user to choose a default vault. The section should look like this:

```markdown
## notes-vault-ops
Purpose: Working with vaults of markdown notes like an Obsidian or Foam vault.
- The default vault is "Work". 
- Use the default vault unless the user tells you otherwise.
```
