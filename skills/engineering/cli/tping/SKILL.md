---
skill_id: engineering_cli.tping
name: "x-tping"
description: "|"
version: v00.33.0
status: CANDIDATE
domain_path: engineering/cli
anchors:
  - tping
source_repo: x-cmd
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# x tping - TCP Ping Tool

> Ping TCP ports to test connectivity using TCP protocol.

---

## Quick Start

```bash
# Ping default port 80
x tping bing.com

# Ping specific port
x tping bing.com:443

# Heatmap visualization
x tping --heatmap bing.com
```

---

## Features

- **TCP Ping**: Test TCP connectivity instead of ICMP
- **Port Specification**: Test any TCP port
- **Visual Output**: Heatmap and bar chart modes
- **Multiple Formats**: CSV, TSV, raw output

---

## Commands

| Command | Description |
|---------|-------------|
| `x tping <host>` | Ping host on port 80 (default) |
| `x tping <host>:<port>` | Ping specific port |
| `x tping -n <count>` | **Limit ping count (recommended)** |
| `x tping --verbose` | Verbose output (default) |
| `x tping --heatmap` | Heatmap visualization |
| `x tping --bar` | Bar chart visualization |
| `x tping --csv` | CSV format output |
| `x tping --tsv` | TSV format output |
| `x tping --raw` | Raw format output |

---

## Examples

### Basic Ping

```bash
# Ping port 80 (default) - runs indefinitely until Ctrl+C
x tping bing.com

# Ping with count limit (recommended - stops after N times)
x tping -n 10 bing.com
x tping -n 20 bing.com:443

# Ping port 443
x tping bing.com:443

# Ping specific IP and port
x tping 8.8.8.8:53
```

### Visual Output

```bash
# Heatmap mode
x tping --heatmap bing.com

# Bar chart mode
x tping --bar bing.com:80
```

### Data Processing

```bash
# CSV output
x tping --csv bing.com

# TSV output
x tping --tsv bing.com:443
```

---

## Comparison with Traditional Ping

| Feature | Traditional Ping | x tping |
|---------|-----------------|---------|
| Protocol | ICMP | TCP |
| Port-specific | No | Yes |
| Firewall-friendly | Often blocked | Usually allowed |
| Output | Text | Visual modes + Data formats |

---

## Platform Notes

Uses `curl` for TCP connections. On Windows and older curl versions (<8.4), uses `x cosmo curl` to avoid connection issues.

---

## Related

## Diff History
- **v00.33.0**: Ingested from x-cmd