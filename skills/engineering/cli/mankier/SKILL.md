---
skill_id: engineering_cli.mankier
name: "x-mankier"
description: "|"
version: v00.33.0
status: CANDIDATE
domain_path: engineering/cli
anchors:
  - mankier
source_repo: x-cmd
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# x mankier - Man Page Search & Browser

> Search and browse man pages from ManKier.com via command line.

---

## Quick Start

### Explain Shell Commands

```bash
# Explain a command with options
x mankier explain "tar -czvf"

# Explain specific tool options
x mankier explain jq -cr
```

### Search Man Pages

```bash
# Search for man pages
x mankier query ls

# Interactive search
x mankier query --app regex
```

### Get Man Page Details

```bash
# Get full man page
x mankier page jq.1

# Get specific section
x mankier section NAME tar

# Get all references
x mankier ref tar
```

---

## Common Commands

| Command | Description |
|---------|-------------|
| `x mankier explain <cmd>` | Explain shell command and options |
| `x mankier query <term>` | Search for man pages |
| `x mankier page <page>` | Get full man page content |
| `x mankier section <name> <page>` | Get specific section from man page |
| `x mankier ref <page>` | Get all links to/from the man page |
| `x mankier : <term>` | Search ManKier via DuckDuckGo |
| `x mankier --help` | Show help information |

---

## Examples

### Explain Commands

```bash
# Understand tar options
x mankier explain "tar -czvf archive.tar.gz"

# Explain jq filtering
x mankier explain jq '.foo'
```

### Search and Browse

```bash
# Search for list-related commands
x mankier query ls

# Interactive fuzzy search
x mankier query --app regex

# Get jq manual
x mankier page jq.1
```

### Get Specific Sections

```bash
# Get NAME section from tar manual
x mankier section NAME tar

# Get DESCRIPTION section
x mankier section DESCRIPTION grep
```

### Search via DuckDuckGo

```bash
# Search for nvme documentation
x mankier : nvme

# Search for disk management
x mankier : "disk partition"
```

---

## Tips

- **explain**: Best for understanding complex command options
- **query --app**: Interactive fuzzy finder for browsing
- **page**: Get the complete manual page content
- **section**: Extract only the part you need

---

## Related

- [ManKier.com](https://www.mankier.com/)

## Diff History
- **v00.33.0**: Ingested from x-cmd