# Archive Manifest Builder

A `nanoagent.plugin/v0001` plugin for the COMP 480/580 verifiable-tasks
milestone. It applies deterministic include and exclude patterns to a supplied
fixture directory and reports every selected file's relative path, byte size,
and SHA-256 digest.

## Tools

| Tool | Does | Code |
|---|---|---|
| `read_archive_request` | Reads the requested patterns and inspects every available regular file | `src/plugin/tools.py` |
| `write_manifest` | Writes the final selected entries to `archive-manifest.json` | `src/plugin/tools.py` |

### Task

| Task | Does | Runner |
|---|---|---|
| `build-archive-manifest` | Selects files and creates a canonical size-and-hash manifest | `agent`, with `read_archive_request` and `write_manifest` |

## Manifest rules

The task names a workspace-relative fixture directory and supplies include and
exclude patterns. Paths in tool results and manifests are relative to that
fixture directory and always use `/` separators.

Patterns match complete paths using this deliberately small glob syntax:

- `*` matches zero or more characters other than `/`;
- `?` matches exactly one character other than `/`;
- `**` matches across directory boundaries;
- `**/` may match zero or more complete directories.

A regular file is selected when the include list is empty or at least one
include pattern matches. A matching exclude pattern always removes the file.
The plugin does not implement `.gitignore` semantics.

Entries are sorted in ascending lexical path order. File sizes count raw bytes,
and hashes are lowercase SHA-256 values of those exact bytes. Symlinks are not
followed or included. The fixture directory cannot escape the workspace, and
the generated `archive-manifest.json` is never treated as fixture input.

The verifier independently walks the fixture tree, applies the documented
patterns, recomputes every size and hash, and rejects missing, extra, duplicate,
reordered, or incorrect entries.

## Layout

```text
.
├── nanoagent.yaml
├── contract.py
├── README.md
├── LICENSE
├── pyproject.toml
├── uv.lock
├── .gitignore
├── .env
├── src/plugin/
├── tests/
├── ui/
├── product/
└── verifier/
```

`contract.py` declares the typed inputs and outputs used by the MCP server,
agent, and deterministic verifier. `verifier/rules.py` owns safe traversal,
glob matching, and canonical manifest construction. `verifier/task.py`
compares the submitted answer with that independently generated result.

The tracked `.env` file is required by RUSH Lab. This plugin needs no secret or
runtime environment variables, so the file contains declarations only and no
values.

## Develop and run

```bash
uv sync --extra dev
uv run ruff check .
uv run pytest -q
nanoagent plugin inspect .
```

To publish, push the plugin to a public GitHub repository and submit its URL
through RUSH Lab.
