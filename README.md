# ImageMagick Image Operations Agent Skill

A globally installable [Agent Skills](https://agentskills.io/) package that lets coding agents translate natural-language image requests into correct, capability-checked [ImageMagick](https://imagemagick.org/) CLI commands.

It covers inspection and EXIF, format conversion and compression, resizing and cropping, rotation and orientation, color and tone, transparency, compositing and watermarking, text and drawing, effects, montages and contact sheets, animation, batch processing, image comparison, color management, and PDF/SVG/PSD rasterization.

## Install

Clone or copy this directory to a global Agent Skills location:

```bash
mkdir -p ~/.agents/skills
git clone <repository-url> ~/.agents/skills/imagemagick-image-operations
```

Claude Code also discovers skills under `~/.claude/skills/`; symlink it there if you use that layout:

```bash
ln -s ~/.agents/skills/imagemagick-image-operations ~/.claude/skills/imagemagick-image-operations
```

Install ImageMagick separately and ensure it is on `PATH`. If it is missing, the skill instructs the agent to stop and direct the user to <https://imagemagick.org/script/download.php>.

```bash
command -v magick
magick -version
python3 ~/.agents/skills/imagemagick-image-operations/scripts/preflight.py
```

## Why runtime capability detection matters

ImageMagick's behavior varies more by *build* than by version. A command that works on one machine fails on the next because a coder was not compiled, a delegate binary is absent, or `policy.xml` forbids the format. The skill therefore always locates the user's binary, checks `-list format`, `-list delegate`, and `-list policy`, and refuses to invent unavailable options.

**`magick -version` is not authoritative.** Its `Delegates` line reports what the binary was compiled against, not what is loadable now. On the machine this skill was developed against, `-version` advertised `heic` and `jxl` while the coder modules were missing from disk:

```
$ magick -size 1x1 xc:red out.heic
magick: unable to load module '.../coders/heic.la': file not found
```

`preflight.py` detects exactly this delegate/coder mismatch and reports it as a warning rather than letting the agent promise HEIC support it does not have.

**Security:** ImageMagick has a long history of parser and delegate CVEs (ImageTragick; the MSL, MVG, EPHEMERAL, and URL coders). The skill treats files it did not create as untrusted: explicit `./` and `FORMAT:` prefixes, no `@listfile` argument files, `-limit` values set, and a documented preference for a restrictive `policy.xml`.

## Examples

Ask naturally:

- "Make a 300×300 square thumbnail cropped from the centre."
- "Get this JPEG under 200 kilobytes."
- "Stamp a faint diagonal DRAFT across the whole image."
- "These phone photos show up sideways — fix them."
- "Shrink this animated GIF to 320 pixels wide."
- "Remove the GPS location from these photos before I share them."
- "Resize every JPEG in this folder to 1200 pixels wide." (writes to a new directory, because `mogrify` overwrites in place)
- "Are these two files actually the same image?"

## Test

The smoke test creates isolated synthetic fixtures with ImageMagick itself; it never reads personal images.

```bash
python3 tests/smoke.py --workdir /tmp/im-skill-smoke
```

It records a JSON report and makes an operation-specific semantic assertion for every case — exact output dimensions, frame counts, colorspace, alpha state, page offset after `+repage`, byte-size targets, and `compare -metric AE` equality — rather than only checking exit status. Cases whose format or delegate is unavailable on the host are reported as `skipped` with a reason instead of failing.

`tests/check_natural_language_cases.py` separately validates the static prompt-contract schema and confirms every intent the skill advertises is backed by documentation. It is explicitly not a model-behavior test.

Every command in `references/natural-language-recipes.md` is extracted and executed against a real binary as part of development; the file ships only commands that ran.

## Evaluation

The skill was tested by giving six independent agent sessions a folder of real images and plain-English requests — 35 tasks spanning inspection, conversion, geometry, color, transparency, compositing, text, animation, batch processing, comparison, and PDF/SVG rasterization — with no guidance beyond the skill itself.

Result: **34 completed successfully, 1 correctly refused.** The refusal is the interesting one. Asked to "convert the poster to HEIC" on a build whose HEIC coder is missing, ImageMagick writes a JPEG named `.heic` and exits `0`. Four independent layers of the skill caught it — the preflight delegate/coder check, the documented fallback failure mode, the mandatory `%m` verification, and the `FORMAT:` output-prefix rule that turns the silent fallback into a loud exit `1`.

Testing also drove most of this skill's content. Defects found and fixed along the way included a recipe that produced an unusable batch path, a `-draw` example that would have filled a region solid black instead of outlining it, an incorrect claim that `-regard-warnings` catches a missing font (it does not), and `--` guidance that broke on absolute paths.

## Files

- `SKILL.md` — activation metadata and agent workflow
- `references/command-line-processing.md` — anatomy of the command line: settings vs operators vs sequence operators, the image list, parentheses, read modifiers, percent escapes, ordering rules
- `references/operation-reference.md` — options grouped by intent family
- `references/natural-language-recipes.md` — outcome-to-command examples, each verified against a real binary
- `references/formats-and-compatibility.md` — format table, delegates, `policy.xml`, HDRI, IM6→IM7 porting, untrusted-input safety, resource limits
- `scripts/preflight.py` — capability report, including delegate/coder mismatch detection
- `scripts/validate_image.py` — output validation with `--expect-*` assertions
- `tests/smoke.py` — reproducible functional and semantic smoke test
- `tests/check_natural_language_cases.py` — static intent-contract/schema validator
- `tests/natural_language_cases.json` — intent coverage cases (not executed model conversations)

## Licensing and source

The skill files are MIT licensed. ImageMagick is separate software under its own license and is not redistributed here.

Primary reference: *ImageMagick Command-line Processing*, <https://imagemagick.org/command-line-processing/>.
