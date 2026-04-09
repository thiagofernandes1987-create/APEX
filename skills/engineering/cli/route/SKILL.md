---
skill_id: engineering_cli.route
name: "x-route"
description: "|"
version: v00.33.0
status: CANDIDATE
domain_path: engineering/cli
anchors:
  - route
source_repo: x-cmd
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# x route - Route Table Viewer

> Display network routing table with multiple output formats.

---

## Quick Start

```bash
# Display route table (default)
x route

# CSV format
x route --csv

# TSV format  
x route --tsv
```

---

## Features

- **Route Table**: Display system routing table
- **Multiple Formats**: CSV, TSV, and raw output
- **Cross-platform**: Linux, macOS, Windows support

---

## Commands

| Command | Description |
|---------|-------------|
| `x route` | Display route table (default) |
| `x route ls` | Display route table |
| `x route ls --csv` | Output in CSV format |
| `x route ls --tsv` | Output in TSV format |
| `x route ls --raw` | Output in raw format |

---

## Examples

### Basic Usage

```bash
# Default route table view
x route

# CSV format for processing
x route --csv

# TSV format
x route --tsv

# Raw format
x route --raw
```

### Data Processing

```bash
# Filter routes
x route --csv | x csv sql "SELECT * WHERE destination LIKE '192.168%'"

# Parse with awk
x route --tsv | awk -F'\t' 'NR>1 {print $1, $2}'
```

---

## Output Fields

Typical fields include:

| Field | Description |
|-------|-------------|
| Destination | Target network or host |
| Gateway | Next hop router |
| Genmask | Netmask |
| Flags | Route flags |
| Metric | Route metric/cost |
| Ref | Reference count |
| Use | Route usage |
| Iface | Network interface |

---

## Platform Notes

- **Linux**: Uses `ip route` or `route` command
- **macOS**: Uses `netstat -rn` or `route` command
- **Windows**: Uses `route print` command

---

## Related

## Diff History
- **v00.33.0**: Ingested from x-cmd