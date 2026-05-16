# Astria CLI

`astria` — a command-line client for the [Astria](https://www.astria.ai) API:
AI image & video generation, fine-tuning (tunes / references), prompts, and
packs, from your terminal.

It's a single self-contained Python 3 script — only the standard library plus
`curl`. Nothing to compile, nothing to `pip install`.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/astriaai/cli/main/install.sh | sh
```

Installs `astria` to `/usr/local/bin` (override with `--prefix="$HOME/.local"`;
pin a version with `--ref=v1.0.0`). Then authenticate once:

```bash
astria login        # prompts for an API key — astria.ai/users/edit/api
```

Already using **Claude Code**? The [`astria` plugin](https://github.com/astriaai/astria-claude-skills)
bundles this CLI — no separate install needed.

## Requirements

- **Python 3.8+** and **curl** — standard on macOS and Linux.

## Quickstart

```bash
astria whoami                                   # the authenticated account
astria models                                   # available models -> tune ids
astria tunes list --title "dress"               # find references
astria generate --text "<faceid:123:1> woman, white studio" --num-images 4 --wait
astria video  --text "a model on a runway" \
              --video-model seedance2_fast_720p --video-prompt "camera tracks her"
astria download 555 556 --out ./shots           # download a prompt's images
astria api GET /prompts --query limit=5          # raw API escape hatch
```

Run `astria --help` for the full command list.

## Profiles

Like the AWS CLI — separate credentials and base URLs per profile:

```bash
astria --profile localhost login --base-url http://localhost:3000
ASTRIA_PROFILE=localhost astria whoami
```

`--profile <name>` (before the subcommand) or `ASTRIA_PROFILE` selects one; each
lives in its own `~/.astria/config.<name>.json`.

## Credentials

Resolved in order: environment variables (`ASTRIA_API_KEY` / `ASTRIA_AUTH_TOKEN`,
`ASTRIA_BASE_URL`, `WORKSPACE_ID`, …) → `~/.astria/config.json` (written by
`astria login`). Scope any command to a workspace with `-w <id>` (or `-w all`).

## License

MIT
