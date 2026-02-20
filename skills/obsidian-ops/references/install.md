# Install notesmd-cli

Follow the instructions for your OS on https://github.com/Yakitrak/notesmd-cli/blob/main/README.md

If the installation fails, you can download the latest Linux binary release and install it manually from https://github.com/Yakitrak/notesmd-cli/releases The raw binary needs `binutils` and `gcc` installed.

## Headless Linux

Since headless Linux does not have a desktop version of Obsidian installed, you need to create the config files by yourself. You need to ask the user for the absolute path to the vault. You must also generate the id. A good guess to generate it is calculating the CRC32 checksum of the absolute vault path and converting it to a lowercase hexadecimal. string.

```
mkdir -p ~/.config/notesmd-cli
echo "{"vaults":{
  "<id>>":{
    "path":"<absolute path to the vault>",
    "ts":<unix timestamp>,
    "open":true
  }
}}" > ~/.config/notesmd-cli/obsidian.json