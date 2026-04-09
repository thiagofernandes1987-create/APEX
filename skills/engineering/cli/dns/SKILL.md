---
skill_id: engineering_cli.dns
name: "x-dns"
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

# x dns - DNS Configuration Utilities

> DNS (Domain Name System) configuration management utilities.

---

## Quick Start

```bash
# Show current DNS configuration
x dns

# List available DNS servers
x dns ls

# Refresh DNS cache
x dns refresh
```

---

## Features

- **Current DNS**: View current DNS configuration
- **DNS List**: List available DNS server addresses
- **DNS Refresh**: Flush and refresh DNS cache
- **Multiple Formats**: JSON, YAML, CSV output support

---

## Commands

| Command | Description |
|---------|-------------|
| `x dns` | Show current DNS configuration (default) |
| `x dns current` | View detailed current DNS settings |
| `x dns ls` | List all available DNS servers |
| `x dns ls --json` | List DNS servers in JSON format |
| `x dns ls --yml` | List DNS servers in YAML format |
| `x dns ls --csv` | List DNS servers in CSV format |
| `x dns refresh` | Refresh system DNS cache |

---

## Examples

### View DNS Configuration

```bash
# Show current DNS
x dns

# View detailed settings
x dns current
```

### List DNS Servers

```bash
# List all available DNS servers
x dns ls

# JSON format
x dns ls --json

# YAML format
x dns ls --yml

# CSV format
x dns ls --csv
```

### Refresh DNS Cache

```bash
# Flush and refresh DNS cache
x dns refresh
```

---

## Platform Notes

- **Linux**: Uses systemd-resolve, NetworkManager, or resolv.conf
- **macOS**: Uses scutil and dscacheutil
- **Windows**: Uses ipconfig and netsh

---

## Related

## Diff History
- **v00.33.0**: Ingested from x-cmd