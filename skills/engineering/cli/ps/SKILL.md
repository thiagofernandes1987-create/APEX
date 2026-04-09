---
skill_id: engineering_cli.ps
name: "x-ps"
description: "|"
version: v00.33.0
status: CANDIDATE
domain_path: engineering/cli
anchors:

source_repo: x-cmd
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# x ps - Process Status Viewer

> Enhanced process viewer with interactive UI, multiple output formats, and AI-powered filtering.

---

## Quick Start

```bash
# Interactive process viewer (default)
x ps

# List all processes with details
x ps aux
```

---

## Features

- **Interactive UI**: Built-in csv app with sorting and filtering
- **fzf integration**: `x ps fz` for fuzzy search
- **Multiple formats**: CSV, JSON, TSV output
- **AI filtering**: Natural language process selection (`x ps =`)
- **Process management**: Kill processes from interactive view

---

## Commands

| Command | Description |
|---------|-------------|
| `x ps` | Interactive process viewer (default) |
| `x ps aux` | Show all processes |
| `x ps fz` | Interactive fzf view |
| `x ps --csv` | CSV format output |
| `x ps --json` | JSON format output |
| `x ps --tsv` | TSV format output |

---

## Examples

### Interactive View

```bash
# Default interactive mode
x ps

# Use fzf for fuzzy search
x ps fz
```

### Format Conversion

```bash
# Convert ps output to JSON
ps aux | x ps --tojson

# Get CSV format
x ps --csv

# Process and convert
ps -ef | x ps --tocsv
```

### AI-Powered Filtering

```bash
# Natural language process selection
x ps = "heavy cpu processes"
x ps = "nodejs processes using most memory"
```

### Process Management

```bash
# View and kill from interactive UI
x ps
# Select process → Choose action (dump, TERM, INT, KILL)
```

---

## Data Pipeline

```bash
# Chain with other tools
x ps --csv | x csv sql "SELECT * WHERE CPU > 5"
x ps --json | jq '.[] | select(.USER == "root")'
```

---

## Platform Notes

### Linux
- Uses native `ps` command
- Fallback to busybox ps if needed

### macOS
- Full feature support
- Native ps compatible

### Windows
- Via busybox or WSL

---

## Related

- Native `ps(1)` manual page

## Diff History
- **v00.33.0**: Ingested from x-cmd