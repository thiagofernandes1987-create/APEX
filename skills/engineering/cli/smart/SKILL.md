---
skill_id: engineering_cli.smart
name: "x-smart"
description: "|"
version: v00.33.0
status: CANDIDATE
domain_path: engineering/cli
anchors:
  - smart
source_repo: x-cmd
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# x smart - Disk Health Monitor

> SMART (Self-Monitoring, Analysis, and Reporting Technology) disk health checking tool.

---

## Quick Start

### List Available Disks

```bash
x smart --ls
```

### Check Disk Health

```bash
# macOS
x smart -a /dev/disk0

# Linux
x smart -a /dev/sda

# Windows
x smart -a C:
```

### Interactive Mode

```bash
x smart
```

Opens interactive UI to select disk and display SMART information.

---

## Common Commands

| Command | Description |
|---------|-------------|
| `x smart --ls` | List available disk paths |
| `x smart -a <disk>` | Display all SMART information for the disk |
| `x smart -H <disk>` | Display disk health status only |
| `x smart --app` | Interactive disk selection (default) |
| `x smart : disk health` | Search smartmontools.com via DuckDuckGo |
| `x smart --help` | Show help information |

---

## Examples

### Basic Usage

```bash
# List all disks
x smart --ls

# Check specific disk (macOS)
x smart -a /dev/disk0

# Check specific disk (Linux)
x smart -a /dev/sda

# Check health only
x smart -H /dev/disk0
```

### Search Documentation

```bash
x smart : disk health
x smart : temperature threshold
```

---

## Platform Notes

### macOS
- Disks: `/dev/disk0`, `/dev/disk1`, etc.
- No sudo required for most operations

### Linux
- Disks: `/dev/sda`, `/dev/nvme0n1`, etc.
- Automatically uses `sudo` for disk access
- smartctl installed via snap if not present

### Windows
- Drives: `C:`, `D:`, etc.
- May require administrator privileges

---

## Tips

- **Root privileges**: smartctl needs root to access SMART data
- **Linux**: sudo is automatically invoked, no manual prefix needed
- **Snap**: smartctl is auto-installed via snap if missing

---

## Related

- [smartmontools.com](https://www.smartmontools.org/)

## Diff History
- **v00.33.0**: Ingested from x-cmd