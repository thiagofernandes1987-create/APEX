---
skill_id: community.general.speed
name: "speed"
description: "Launch RSVP speed reader for text"
version: v00.33.0
status: CANDIDATE
domain_path: community/general/speed
anchors:
  - speed
  - launch
  - rsvp
  - reader
  - text
source_repo: antigravity-awesome-skills
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# Speed Reader

Launch the RSVP speed reader to display text one word at a time with Spritz-style ORP (Optimal Recognition Point) highlighting.

## When to Use

- You want to launch the RSVP speed reader for text in the current session.
- The task is to turn either provided text or the assistant's prior response into a word-by-word reading view.
- You need a quick reading aid rather than a document transformation or summary.

## Instructions

1. **Get the text:**
   - If `$ARGUMENTS` is provided, use that text
   - Otherwise, extract the main content from your **previous response** in this conversation

2. **Prepare the content:**
   - Strip markdown formatting (headers, bold, links, code blocks)
   - Keep clean, readable prose
   - Escape quotes and backslashes for JavaScript

3. **Write and launch:**
   - Read `~/.claude/skills/speed/data/reader.html`
   - Replace `<!-- CONTENT_PLACEHOLDER -->` with:
     ```html
     <script>window.SPEED_READER_CONTENT = "your escaped text";</script>
     <!-- CONTENT_PLACEHOLDER -->
     ```
   - Run: `open ~/.claude/skills/speed/data/reader.html`

4. **Confirm:** Tell the user it's opening. Mention `Space` to play/pause.

## Arguments
$ARGUMENTS

## Diff History
- **v00.33.0**: Ingested from antigravity-awesome-skills community repo
