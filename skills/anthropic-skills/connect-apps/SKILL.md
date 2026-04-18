---
name: connect-apps
description: "Apply — Connect Claude to external apps like Gmail, Slack, GitHub. Use this skill when the user wants to send emails, create issues, post messages, or take actions in external services."
executor: LLM_BEHAVIOR
skill_id: anthropic-skills.connect-apps
status: ADOPTED
security: {level: standard, pii: true, approval_required: false}
anchors:
  - git
  - llm
tier: 2
input_schema:
  - name: code_or_task
    type: string
    description: "Code snippet, script, or task description to process"
    required: true
output_schema:
  - name: result
    type: string
    description: "Primary output from connect apps"
---

# Connect Apps

Connect Claude to 1000+ apps. Actually send emails, create issues, post messages - not just generate text about it.

## Quick Start

### Step 1: Install the Plugin

```
/plugin install composio-toolrouter
```

### Step 2: Run Setup

```
/composio-toolrouter:setup
```

This will:
- Ask for your free API key (get one at [platform.composio.dev](https://platform.composio.dev/?utm_source=Github&utm_content=AwesomeSkills))
- Configure Claude's connection to 1000+ apps
- Take about 60 seconds

### Step 3: Try It!

After setup, restart Claude Code and try:

```
Send me a test email at YOUR_EMAIL@example.com
```

If it works, you're connected!

## What You Can Do

| Ask Claude to... | What happens |
|------------------|--------------|
| "Send email to sarah@acme.com about the launch" | Actually sends the email |
| "Create GitHub issue: fix login bug" | Creates the issue |
| "Post to Slack #general: deploy complete" | Posts the message |
| "Add meeting notes to Notion" | Adds to Notion |

## Supported Apps

**Email:** Gmail, Outlook, SendGrid
**Chat:** Slack, Discord, Teams, Telegram
**Dev:** GitHub, GitLab, Jira, Linear
**Docs:** Notion, Google Docs, Confluence
**Data:** Sheets, Airtable, PostgreSQL
**And 1000+ more...**

## How It Works

1. You ask Claude to do something
2. Composio Tool Router finds the right tool
3. First time? You'll authorize via OAuth (one-time)
4. Action executes and returns result

## Troubleshooting

- **"Plugin not found"** → Make sure you ran `/plugin install composio-toolrouter`
- **"Need to authorize"** → Click the OAuth link Claude provides, then say "done"
- **Action failed** → Check you have permissions in the target app

---

<p align="center">
  <b>Join 20,000+ developers building agents that ship</b>
</p>

<p align="center">
  <a href="https://platform.composio.dev/?utm_source=Github&utm_content=AwesomeSkills">
    <img src="https://img.shields.io/badge/Get_Started_Free-4F46E5?style=for-the-badge" alt="Get Started"/>
  </a>
</p>

---

## Why This Skill Exists

Apply — Connect Claude to external apps like Gmail, Slack, GitHub. Use this skill when the user wants to send emails, create issues, post messages, or take actions in external services.

<!-- SR_40: auto-generated from frontmatter `purpose`/`description` (OPP-Phase3). Expand with domain-specific rationale. -->

## When to Use

Use this skill when the task requires connect apps capabilities.

<!-- SR_40: auto-generated from frontmatter `when`/`description` (OPP-Phase3). -->

## What If Fails

If this skill fails to produce the expected output: (1) verify input completeness, (2) retry with more specific context, (3) fall back to the parent workflow without this skill.

<!-- SR_40: auto-generated from frontmatter `what_if_fails` (OPP-Phase3). -->
