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

Installs `astria` to a writable Homebrew bin when it is already on `PATH` (for example `/opt/homebrew/bin`), otherwise `~/.local/bin`. For a system install use
`curl -fsSL https://raw.githubusercontent.com/astriaai/cli/main/install.sh | sh -s -- --prefix=/usr/local --sudo`;
pin a version with `sh -s -- --ref=v1.0.0`. Then authenticate once:

```bash
astria login        # prompts for an API key — https://astria.ai/users/edit/api
```

Already using **Claude Code**? The [`astria` plugin](https://github.com/astriaai/astria-claude-skills)
bundles this CLI — no separate install needed.

## Upgrade

```bash
astria upgrade
```

This downloads the latest `astria` script and replaces the current executable
in place. If your install path is not writable, rerun it with permissions to
update that file.

## Requirements

- **Python 3.8+** and **curl** — standard on macOS and Linux.

## Quickstart

```bash
astria whoami                                   # the authenticated account
astria models                                   # popular models -> tune ids
astria tunes list --gallery --branch partner-1   # discover every partner model
astria tunes list --title "dress"               # find references
astria generate --text "<faceid:123:1> woman, white studio" --num-images 4 --wait
astria generate --text "cinematic portrait" --film-grain --wait
astria generate --model wan-2-7 --text "plain white background" \
  --reference "dress=./dress.jpg" --reference "woman=./woman.jpg" --num-images 1 --wait
astria video --video-model seedance2_fast_720p \
  --video-prompt "<faceid:1234:1> woman walks down a runway" --duration 5 --wait
astria video --video-model seedance2_fast_720p \
  --video-prompt "woman wearing a dress walks down a runway" \
  --reference woman=./model.jpg --reference dress=./dress.jpg --wait
astria video --video-model seedance2_fast_720p \
  --video-prompt "transition through these looks in order" \
  --image-reference ./look-1.jpg --image-reference ./look-2.jpg --wait
astria inspect-video ./clip.mp4                   # timestamped text-to-video description
astria inspect-video https://example.com/clip.mp4 --tune-id 123
astria variate ./clip.mp4 --brief 'Replace the end card with Astria' --wait
astria variate ./clip.mp4 --reference ./dress.jpg --reference woman=./model.jpg --wait
astria prompts wait 555 556 557                  # block until each settles (images or user_error)
astria download 555 556 --out ./shots           # download a prompt's images
astria packs get spring-lookbook                 # inspect templates and pricing
astria api GET /prompts --query limit=5          # raw API escape hatch
```

Run `astria --help` for the full command list.

`astria help` is an alias for `astria --help`; pass a command for focused help,
such as `astria help variate`. Version output is available through
`astria --version`, `astria -v`, or `astria version`.

## Uploads

Local files are uploaded directly to Astria's object storage before the tune,
prompt, pack, or raw API request is submitted. A command with several local
files uploads up to six of them in parallel while preserving their argument
order in the final request. Remote URLs are passed through unchanged.

The raw API escape hatch uses the same flow: `--form 'key=@./file.jpg'`
direct-uploads the file and sends its signed blob id under `key`; it does not
proxy the file through the Astria API server.

## Pricing

Prices are returned as `cost_mc`, an integer number of **millicents**: 1,000
millicents = 1 cent and 100,000 millicents = US $1.
Prompt prices already include `num_images`; do not multiply by it again. Sum
the `cost_mc` values for several prompts, then divide by 100,000 for dollars.

`astria packs get SLUG` returns stored `template_prompts[].cost_mc` values that
can be summed as a baseline for a selected subset. Its class-specific
`costs.*.cost_mc` values include a hypothetical fresh reference plus that
class's prompt group; on a multi-class pack this is not necessarily the entire
pack. These are estimates from stored template settings. Caller/workspace
rules, overrides, discounts, ecommerce pricing, and cartesian variants can
change the result. After a run, use `order.total_cost_mc` when the response
includes an order; it is the authoritative charged total.

Seedance 2 uses references exactly like image generation: write
`<faceid:TUNE_ID:1> TUNE_NAME`, with the tune's class name immediately after
the token. For a new reference, repeat `--reference NAME=PATH_OR_URL`; the CLI
creates each reference and adds its correctly formatted mention to both the
first-frame prompt and video prompt. `--images` remains an alias for
`--reference`.

For models that accept raw image references, repeat
`--image-reference PATH_OR_URL`. These images are attached directly to the video prompt in the
same order they appear on the command line; they do not create reference
tunes. A request may use local files or URLs, but does not mix the two forms.

## Variate a video

`astria variate` carries the Variate mini-app flow into one command: it
inspects a driving video, turns an edit brief and replacement references into
a production-ready Seedance 2.5 video-to-video prompt, then creates the video.

```bash
# Brief-only edit
astria variate ./source.mp4 \
  --brief 'Change the text on the final card to say "Astria"' --wait

# Existing and newly-created replacement references
astria variate ./source.mp4 \
  --tune-id 123 \
  --reference ./dress.jpg \
  --reference woman=https://example.com/model.jpg \
  --brief 'Keep the performance and replace the presenter and wardrobe' --wait

# Skip paid video inspection when a description is already available
astria variate https://example.com/source.mp4 \
  --description-file ./source-description.txt \
  --brief 'Use a warmer end-card treatment'
```

- `SOURCE` accepts a local MP4/MOV or a public HTTPS URL. Local source and
  reference files are direct-uploaded together, in parallel, before API work.
- `--reference [NAME=]PATH_OR_URL` creates one replacement tune per image.
  Omit `NAME=` to auto-detect the class; use it to skip class detection.
- `--tune-id ID` reuses an existing replacement tune. Existing tune ids are
  composed before newly-created references, and each group keeps flag order.
- Either a non-empty `--brief` or at least one reference is required.
- `--description` and `--description-file` bypass source-video inspection.
- Variate intentionally fixes `video_model=seedance25_720p` and audio on, and
  leaves duration and aspect ratio unset so they follow the source video.
- Output is structured JSON containing `description`, `references`,
  `video_prompt`, and `prompt`. `--wait` replaces `prompt` with its settled
  generation record.

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
