---
skill_id: algorithms.anthropic_cli
name: "Anthropic CLI -- Command Line Interface"
description: "Reference documentation for Anthropic CLI -- Command Line Interface. Source: anthropic-cli-main"
version: v00.33.0
status: CANDIDATE
domain_path: algorithms/anthropic-cli
anchors:
  - anthropic
  - anthropic_cli
source_repo: anthropic-cli-main
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# Anthropic CLI -- Command Line Interface

Source: `anthropic-cli-main` (123 files)

## README

# Claude Platform CLI

The official CLI for the [Claude Developer Platform](https://platform.claude.com/docs/en/api).

<!-- x-release-please-start-version -->

## Installation

### Installing with Homebrew

```sh
brew install anthropics/tap/ant
```

### Installing with Go

To test or install the CLI locally, you need [Go](https://go.dev/doc/install) version 1.22 or later installed.

```sh
go install 'github.com/anthropics/anthropic-cli/cmd/ant@latest'
```

Once you have run `go install`, the binary is placed in your Go bin directory:

- **Default location**: `$HOME/go/bin` (or `$GOPATH/bin` if GOPATH is set)
- **Check your path**: Run `go env GOPATH` to see the base directory

If commands aren't found after installation, add the Go bin directory to your PATH:

```sh
# Add to your shell profile (.zshrc, .bashrc, etc.)
export PATH="$PATH:$(go env GOPATH)/bin"
```

<!-- x-release-please-end -->

### Running Locally

After cloning the git repository for this project, you can use the
`scripts/run` script to run the tool locally:

```sh
./scripts/run args...
```

## Usage

The CLI follows a resource-based command structure:

```sh
ant [resource] <command> [flags...]
```

```sh
ant messages create \
  --api-key my-anthropic-api-key \
  --max-tokens 1024 \
  --message '{content: [{text: x, type: text}], role: user}' \
  --model claude-sonnet-4-5-20250929
```

For details about specific commands, use the `--help` flag.

### Environment variables

| Environment variable   | Required | 

## Diff History
- **v00.33.0**: Ingested from anthropic-cli-main