---
skill_id: community.general.github
name: "github"
description: "'Use the `gh` CLI for issues, pull requests, Actions runs, and GitHub API queries.'"
version: v00.33.0
status: CANDIDATE
domain_path: community/general/github
anchors:
  - github
  - issues
  - pull
  - requests
  - actions
  - runs
  - queries
source_repo: antigravity-awesome-skills
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# GitHub Skill

Use the `gh` CLI to interact with GitHub. Always specify `--repo owner/repo` when not in a git directory, or use URLs directly.

## When to Use

- When the user asks about GitHub issues, pull requests, workflow runs, or CI failures.
- When you need `gh issue`, `gh pr`, `gh run`, or `gh api` from the command line.

## Pull Requests

Check CI status on a PR:
```bash
gh pr checks 55 --repo owner/repo
```

List recent workflow runs:
```bash
gh run list --repo owner/repo --limit 10
```

View a run and see which steps failed:
```bash
gh run view <run-id> --repo owner/repo
```

View logs for failed steps only:
```bash
gh run view <run-id> --repo owner/repo --log-failed
```

### Debugging a CI Failure

Follow this sequence to investigate a failing CI run:

1. **Check PR status** — identify which checks are failing:
   ```bash
   gh pr checks 55 --repo owner/repo
   ```
2. **List recent runs** — find the relevant run ID:
   ```bash
   gh run list --repo owner/repo --limit 10
   ```
3. **View the failed run** — see which jobs and steps failed:
   ```bash
   gh run view <run-id> --repo owner/repo
   ```
4. **Fetch failure logs** — get the detailed output for failed steps:
   ```bash
   gh run view <run-id> --repo owner/repo --log-failed
   ```

## API for Advanced Queries

The `gh api` command is useful for accessing data not available through other subcommands.

Get PR with specific fields:
```bash
gh api repos/owner/repo/pulls/55 --jq '.title, .state, .user.login'
```

## JSON Output

Most commands support `--json` for structured output.  You can use `--jq` to filter:

```bash
gh issue list --repo owner/repo --json number,title --jq '.[] | "\(.number): \(.title)"'
```

## Diff History
- **v00.33.0**: Ingested from antigravity-awesome-skills community repo
