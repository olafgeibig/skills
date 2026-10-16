# Repository inventory format: verify before parsing

Repository inventory filenames and extensions do not guarantee a serialization format. Inspect local project instructions and the actual file before parsing it.

- Strict JSONL contains one complete JSON value per line.
- A JSON array is one JSON document.
- A stream of pretty-printed objects may require a streaming decoder such as `JSONDecoder.raw_decode`.
- For human-maintained or uncertain inventories, read or search the text rather than forcing a parser.

Choose the parser to match the observed structure; never assume an inventory is strict JSONL merely because of its name.