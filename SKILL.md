---
name: imagemagick-image-operations
description: Operate on images with the ImageMagick CLI from natural-language requests. Use for inspecting, converting, compressing, resizing, cropping, rotating, trimming, padding, recoloring, transparency, compositing, watermarking, text and drawing, effects, montages, batch-processing folders, animated GIF/WebP, comparing images, EXIF/ICC metadata, and rasterizing PDF/SVG. Also use when the user says ImageMagick, magick, convert, mogrify, montage, composite, compare, identify, resize an image, make a thumbnail, watermark an image, or batch convert photos.
license: MIT (skill files only; ImageMagick has its own license)
compatibility: Requires a local ImageMagick (`magick` v7, `convert` v6). Format support is build-dependent; PDF/EPS needs Ghostscript, video needs FFmpeg, good SVG needs an RSVG/Inkscape delegate. Runtime-gated for v6 and partial builds.
metadata:
  author: SongTonyLi
  primary-reference: "https://imagemagick.org/command-line-processing/"
---

# Natural-language image operations with ImageMagick

Translate the user's requested outcome into a correct, capability-checked `magick` invocation. Do not ask the user to know ImageMagick syntax.

## Mandatory start: locate and identify ImageMagick

**Always do this before every ImageMagick task, even if a path was previously known:**

```bash
MAGICK="$(command -v magick 2>/dev/null || command -v convert 2>/dev/null || true)"
if [ -z "$MAGICK" ]; then
  printf '%s\n' 'ImageMagick is not installed or is not on PATH.'
fi
```

If no executable is found, stop and prompt the user to install ImageMagick from <https://imagemagick.org/script/download.php>. Do not **silently** substitute `sips`, `ffmpeg`, Pillow, or another image tool. Reaching for a different tool is fine when it is the right answer — a dedicated SVG renderer usually beats ImageMagick's built-in one — but say which tool produced the result and why, and never present another tool's output as ImageMagick's.

If found, run:

```bash
"$MAGICK" -version          # version, quantum depth, HDRI, built-in delegates
"$MAGICK" -list format      # per-format read/write modes as registered now
```

For a full environment report:

```bash
python3 scripts/preflight.py
```

**Neither `-version` nor `-list format` is fully trustworthy, and they lie independently.** `-version`'s `Delegates` line reports what the binary was *compiled* against, not what is loadable now: a package upgrade can leave it advertising `heic` and `jxl` after the coder modules are gone from disk. `-list format` can also register a format whose delegate is broken — MP4 lists as `rw+` on a host whose FFmpeg cannot actually decode it back.

The only reliable check is a **round-trip probe**: encode, then read back.

```bash
"$MAGICK" -size 1x1 xc:red WEBP:- 2>/dev/null | "$MAGICK" identify - >/dev/null 2>&1 \
  && echo "WEBP round-trips" || echo "WEBP unusable"
```

**The format you asked for is not necessarily the format you got.** When ImageMagick cannot resolve the output coder — missing module, unknown extension — it falls back to the *input's* coder, writes the file under the name you gave, and **exits 0 with no message**:

```bash
magick base.png out.heic   # exit 0
identify -format '%m' out.heic   # -> PNG, not HEIC
magick base.png out.zzz    # exit 0 -> also a PNG
```

Never take exit status as proof of format. Confirm the output's real coder before reporting success:

```bash
"$MAGICK" identify -format '%m %wx%h\n' -- out.heic
```

Using an explicit `FORMAT:` prefix on the output (`heic:out.heic`) surfaces the failure instead of writing a mislabelled file, so prefer it whenever the format matters.

Check `-list delegate`, `-list policy`, and `-list font` before relying on external converters, restricted coders, or a named font. Never invent an option; confirm it against `"$MAGICK" -help` and the [operation reference](references/operation-reference.md).

Resolve all relative skill paths from this skill directory, not the user's current directory.

## Core workflow

1. **Clarify only ambiguity that changes the result.** Determine input(s), output path, target dimensions and whether aspect ratio may change, quality/compression target, background and transparency handling, which frames or pages, whether metadata must survive, and the overwrite policy.
2. **Inspect before mutation.** The right command depends on whether the source has alpha, is animated, or is CMYK, so look first:

   ```bash
   "$MAGICK" identify -format '%f %m %wx%h %[colorspace] alpha=%A opaque=%[opaque] depth=%z frames=%n\n' -- "$input"
   ```

   `%A` only says an alpha *channel* exists; `%[opaque]` says whether any pixel actually uses it (`alpha=Blend opaque=True` means the channel is dead weight and no flattening decision is needed). For metadata work add `-verbose` or `%[EXIF:*]`.

   **On a multi-frame file `identify` prints one line per frame**, so the command above emits six identical `frames=6` lines for a six-frame GIF. To inspect an animation properly, print per-frame geometry — and note that `%n` under a frame selector reports the size of the *selection*, not the file (`animation.gif[0]` → `%n` is `1`, not `6`):

   ```bash
   "$MAGICK" identify -format 'scene=%s canvas=%g frame=%wx%h delay=%Tcs\n' -- anim.gif
   ```

   Optimized GIFs have frames smaller than the canvas, which only `%g` reveals. There is no valid `%[dispose]` or `%[disposal]` property — both warn and return empty while exiting 0; read disposal from `-verbose`.
3. **Plan the exact command.** ImageMagick is a **left-to-right pipeline**: settings must appear *before* the read or operator they affect. `-density` before a PDF/SVG input, `-quality` before the output, `-background` before `-flatten`. Prefer one invocation; use `\( ... \)` for sub-lists rather than temporary files. Quote every path and text argument. Never use `eval` or concatenate untrusted text into a shell command.
4. **Protect originals.** Default to a new descriptive output path. Ensure the output path differs from every input. **`mogrify` rewrites its inputs in place** — only use it with `-path OUTDIR` pointing at a directory that is not the source, or after the user explicitly approves in-place edits and a backup exists. Create requested output directories first.
5. **Preserve semantics deliberately.** Re-encoding a JPEG is always generation loss; prefer operating once from the original. `-strip` removes EXIF, IPTC, XMP **and the ICC profile** — colors can shift; keep the profile when color fidelity matters. **`-thumbnail` also strips all metadata and profiles** as a side effect (that is the difference from `-resize`, which preserves them) — desirable for web thumbnails, wrong when provenance or color management must survive. Warn before quantizing (`-colors`, `png8`), flattening away alpha, or rasterizing a vector.
6. **Run and check exit status.** ImageMagick exits `0` on success, `1` for most errors (missing file, bad format, policy denial), and `11` for an unrecognized option — so a typo'd flag is distinguishable from a real failure. **Warnings exit `0` while still producing a degraded or wrong file.** `-regard-warnings` promotes *some* warnings to failures (a missing EXIF tag becomes exit 1) but **not a missing font**, which stays exit 0 and silently substitutes a fallback face. Treating a non-empty stderr as failure is the more reliable rule for text work. Never infer success from the absence of a message, and never report success on nonzero exit.
7. **Validate.** Confirm the output exists and is nonempty, then verify the specific claim: **actual format (`%m`)**, dimensions, frame count, colorspace, alpha, file size. Run `python3 scripts/validate_image.py <output>` with the relevant `--expect-*` flags. Checking `%m` is not optional — a silent coder fallback is invisible any other way.

   **Geometry checks cannot catch a direction error.** A 90° rotation the wrong way, a `-flip` that should have been `-flop`, or a mirrored `-transpose` all produce identical dimensions. For any direction-sensitive or content-sensitive operation, probe actual pixels:

   ```bash
   "$MAGICK" out.png -format 'TL=%[pixel:p{0,0}] TR=%[pixel:p{%[fx:w-1],0}]\n' info:
   ```
8. **Report naturally.** State what changed, the output path, the checks performed, and any caveat. Include the exact command when useful.

## Command construction rules

General form:

```bash
"$MAGICK" [input settings] input.png [operators] [output settings] output.jpg
```

- **Three kinds of argument, and order decides meaning:** *settings* (`-density`, `-background`, `-fill`, `-font`, `-quality`, `-gravity`, `-channel`) persist until changed and affect what follows; *operators* (`-resize`, `-crop`, `-rotate`, `-blur`) act immediately on the images already read; *sequence operators* (`-append`, `-flatten`, `-layers`, `-coalesce`, `-delete`) act on the whole image list. Read [command-line processing](references/command-line-processing.md) before writing anything non-trivial.
- The `+` form of an option usually means unset/off, or "apply per image" rather than to the list: `+repage`, `+append`, `+adjoin`, `+profile`.
- **Read modifiers attach to the filename**: `photo.jpg[100x100]` resizes on read, `doc.pdf[0]` takes page 1, `scan.tif[0-3]` takes frames, `PNG32:out.png` forces a coder. Put the frame selector on the *input*, not the output.
- Use `\( ... \)` (escaped in shell) to build a sub-list, with `-clone n` to reuse an image already read.
- `-` means stdin/stdout; `miff:-` is the lossless format for piping between two `magick` calls; `mpr:name` is an in-memory register within one call.
- On ImageMagick 7 the entry point is `magick`; `convert` is a deprecated shim. On ImageMagick 6 only `convert` exists and several option semantics differ — see [formats and compatibility](references/formats-and-compatibility.md).
- `magick` and `magick identify` accept `--` to end option parsing. **`mogrify` does not**: it treats `--` as a filename, writes a file literally named `--`, and still exits 0. Never pass `--` to `mogrify`; guard leading-dash filenames with a `./` prefix instead.
- **`--` does not neutralize a `coder:` prefix** — only the path form does. For an untrusted **relative** path, prefix it with `./`, which defeats both a leading `-` and a `coder:` prefix. An **absolute** path already starts with `/` and needs no guard — prepending `./` to one produces `.//Users/...` and a spurious `unable to open image`. Alternatively state the coder explicitly as `FORMAT:name`, which works for both. Verified:

  | Argument | Result |
  |---|---|
  | `label:missing.png` | exit 0, **synthesizes a text image** — a wrong answer reported as success |
  | `-- label:missing.png` | exit 0, still synthesizes |
  | `./label:missing.png` | exit 1, `unable to open image` |
  | `PNG:label:missing.png` | exit 1, `unable to open image` |

## Geometry arguments

Most sizing options take one geometry string. The suffix changes the rule:

| Request | Geometry |
|---|---|
| fit inside 800×600, keep aspect | `800x600` |
| exactly 800×600, distort if needed | `800x600!` |
| shrink to fit, never enlarge | `800x600>` |
| enlarge to fit, never shrink | `800x600<` |
| cover 800×600, overflow allowed (then crop) | `800x600^` |
| width 800, height automatic | `800x` or `800` |
| height 600, width automatic | `x600` |
| scale to 50% | `50%` (or `50x25%` per axis) |
| about 1 megapixel, keep aspect | `1000000@` |
| region 200×100 at offset (20, 40) | `200x100+20+40` |
| offset only, for placement | `+20+40` |

`-gravity` sets the anchor (`center`, `north`, `southeast`, …) for `-extent`, `-crop`, `-annotate`, `-composite` and `montage`. Set it *before* the option it modifies.

**The square-thumbnail idiom**, because it comes up constantly:

```bash
"$MAGICK" in.jpg -resize 400x400^ -gravity center -extent 400x400 out.jpg
```

## Choose the operation family

Read [the operation reference](references/operation-reference.md) for exact syntax. Read [natural-language recipes](references/natural-language-recipes.md) for verified intent-to-command examples.

| User intent | Primary tools and options |
|---|---|
| inspect/count/audit/EXIF | `identify`, `-format`, `-verbose`, `-ping`, `json:`, `%[exif:*]` |
| convert format / compress | output extension or `FORMAT:`, `-quality`, `-define jpeg:extent`, `-sampling-factor`, `-strip`, `-interlace` |
| resize/thumbnail/fit | `-resize`, `-thumbnail`, `-scale`, `-sample`, `-adaptive-resize`, `-extent` |
| crop/trim/pad/border | `-crop`, `-trim`, `+repage`, `-extent`, `-border`, `-shave`, `-chop`, `-splice` |
| rotate/straighten/orient | `-rotate`, `-auto-orient`, `-deskew`, `-flip`, `-flop`, `-transpose` |
| color/tone/levels | `-colorspace`, `-modulate`, `-level`, `-auto-level`, `-normalize`, `-contrast-stretch`, `-gamma`, `-brightness-contrast`, `-negate`, `-tint`, `-colorize` |
| transparency/background | `-alpha`, `-background`, `-flatten`, `-transparent`, `-fuzz`, `-opaque`, `-channel` |
| composite/overlay/watermark | `-composite`, `-compose`, `-gravity`, `-geometry`, `-tile`, `-define compose:args=`, `composite` |
| combine/append/contact sheet | `+append`, `-append`, `-smush`, `montage`, `-layers` |
| text/labels/captions/drawing | `-annotate`, `-draw`, `label:`, `caption:`, `-font`, `-pointsize`, `-fill`, `-stroke` |
| effects/filters | `-blur`, `-gaussian-blur`, `-sharpen`, `-unsharp`, `-morphology`, `-edge`, `-vignette`, `-shadow`, `-paint`, `-distort` |
| animation/multi-frame | `-coalesce`, `-layers optimize`, `-delay`, `-loop`, `-dispose`, `+adjoin`, frame selectors |
| batch a folder | `mogrify -path OUTDIR`, `find`/`xargs -P`, per-file loop |
| compare/diff/dedupe | `compare -metric`, `-subimage-search`, `identify -format '%#'` |
| color management | `-profile`, `-colorspace`, `-intent`, `-black-point-compensation` |
| rasterize PDF/SVG/PSD | `-density` before input, `pdf:use-cropbox`, `file.psd[0]`, RSVG/Inkscape delegate |
| performance/limits | `-limit`, `-define registry:temporary-path`, `MAGICK_*`, `-bench`, MPC caching |

## Text rendering: knowing it actually rendered

Text is the most fragile subsystem, and every one of its failures exits `0`. The "probe, don't trust the list" rule this skill applies to formats applies just as much to fonts.

- **Font names are the hyphenated PostScript names from `-list font`, not family names.** `-font 'Times New Roman'` warns and falls back; `-font Times-New-Roman` works. A fallback face still renders, so the output looks plausible.
- **A listed font can render nothing.** `-font Zapf-Dingbats` with Latin text exits 0, prints no warning at all, and produces a blank image.
- **Check contrast before choosing ink.** White text on a near-white image exits 0 and is invisible. Read the image's mean first — `-format '%[fx:mean]'` — and pick ink accordingly. The standard inspect line has no brightness field, so add one.
- **`-draw` shape primitives fill with black by default.** `-draw 'rectangle …'` with only `-stroke` set produces a **solid black box** over the region you meant to outline. Always pass `-fill none` for an outline.
- **A missing EXIF tag interpolates to an empty string** and warns on stderr at exit 0. Never build annotation text with `2>&1` — you will burn the warning message into the image.
- `-annotate` promotes the image to an alpha type (`srgb` → `srgba`); harmless but it will show up in your alpha validation.

Verify text with all three of these, not just exit status:

```bash
err=$("$MAGICK" in.png -font Helvetica -pointsize 48 -fill black \
      -gravity center -annotate 0 'Hello' out.png 2>&1)
[ -z "$err" ] || echo "FONT/RENDER WARNING: $err"      # stderr must be empty
"$MAGICK" out.png -format 'sd=%[fx:standard_deviation]\n' info:   # must be > 0
"$MAGICK" compare -metric AE in.png out.png null: 2>&1            # must be > 0
```

## Safety boundaries

- **`mogrify` is destructive by default.** It overwrites every file it touches. Always prefer `mogrify -path OUTDIR` or a loop writing to new names. Say so before running it on a user's folder.
- **Never write into the input.** Reading and writing the same path in one command can truncate the file. Check output ≠ input, including after shell globbing.
- **Lossy actions need explicit intent:** JPEG/WebP re-encoding, `-colors`/`png8` quantization, `-strip` (drops EXIF, IPTC, XMP **and ICC**), `-flatten` (discards alpha), `-resize` down (irreversible), rasterizing PDF/SVG, and `-layers optimize` on an animation.
- **`-strip` is not redaction.** It removes container metadata; it does not remove information visible in the pixels, and it does not scrub every vendor block in every format. Never call a stripped file anonymized without checking.
- **Untrusted input is a real attack surface.** ImageMagick has a long CVE history (ImageTragick and the MSL/MVG/EPHEMERAL/URL coders, delegate command injection through crafted filenames). For files you did not create: quote everything, prefix the path with `./`, pass an explicit `FORMAT:` prefix so the coder is not inferred from content or name, reject filenames beginning with `|` or `@`, avoid `@listfile` argument files, set `-limit` values, and prefer a restrictive `policy.xml`. Verify the outcome instead of assuming.
- **Security policy denials are not bugs.** Many distributions disable PDF, PS, EPS, and XPS in `policy.xml`. The error reads `attempt to perform an operation not allowed by the security policy`. Detect it with `-list policy` and explain it; do not work around a deliberate policy without the user's approval.
- **Resource exhaustion:** a large `-density`, a huge `-resize`, or a `-distort` on a giant image can consume all RAM and disk. Use `-limit memory`/`-limit map`/`-limit time` on unfamiliar inputs, and prefer `-thumbnail` or a `jpeg:size` read hint for batch work.
- **Do not fabricate capability.** If a format is missing from `-list format`, or a delegate is absent, say what is missing and how to install it. Do not silently fall back to another format or tool — and remember ImageMagick will do exactly that on your behalf if you let it, so always confirm `%m` on the output.
- **Licensing:** ImageMagick is separate software under its own license (ImageMagick License, Apache-2.0-style). This skill does not redistribute it.

## Fast recipes

```bash
# Inspect
"$MAGICK" identify -format '%f %m %wx%h %[colorspace] alpha=%A frames=%n\n' -- in.png

# Resize to fit a box, never enlarging
"$MAGICK" in.jpg -resize '1600x1600>' out.jpg

# Resize to a width, height automatic (the plain "make it N wide" case)
"$MAGICK" in.jpg -resize 800x out.jpg

# Square thumbnail, centered crop (only use this when a SQUARE is wanted — it crops)
"$MAGICK" in.jpg -thumbnail 300x300^ -gravity center -extent 300x300 thumb.jpg

# Rotate 90° clockwise (-rotate is clockwise; use -90 or 270 for counter-clockwise)
"$MAGICK" in.png -rotate 90 rotated.png

# Crop a region, then reset the virtual canvas
"$MAGICK" in.png -crop 400x300+50+20 +repage crop.png

# Trim uniform borders
"$MAGICK" in.png -trim +repage trimmed.png

# Web-optimize a photo
"$MAGICK" in.jpg -auto-orient -resize '2000x2000>' -strip -interlace Plane \
  -sampling-factor 4:2:0 -quality 82 out.jpg

# Put a white background behind transparency
"$MAGICK" in.png -background white -alpha remove -alpha off out.jpg

# Watermark bottom-right
"$MAGICK" in.jpg logo.png -gravity southeast -geometry +20+20 -composite out.jpg

# Batch a folder into a NEW directory (never in place; no `--` here, mogrify mis-parses it)
mkdir -p out && "$MAGICK" mogrify -path out -resize '1200x1200>' -quality 85 in/*.jpg

# Resize an animated GIF correctly
"$MAGICK" in.gif -coalesce -resize 320x -layers optimize out.gif

# Are two images identical? (metric goes to stderr; exit 1 means "they differ", not "error")
"$MAGICK" compare -metric AE in1.png in2.png null: 2>&1
```

`compare` has its own exit convention: **`0` identical, `1` images differ, `2` a real error** such as a missing file. Do not treat its exit `1` as a failure. It also **does not refuse mismatched dimensions** — comparing 640×480 against 320×240 returns a bare number with no warning, so check `%wx%h` first.

For more — including EXIF, text and captions, montage, masks, effects, animation, pipelines, and PDF/SVG rasterization — read [natural-language recipes](references/natural-language-recipes.md).

## Common mistakes

| Mistake | Consequence | Fix |
|---|---|---|
| Setting after the thing it modifies | Silently ignored | `-density 300 in.pdf` not `in.pdf -density 300` |
| Forgetting `+repage` after `-crop`/`-trim` | Output keeps a virtual canvas and offset; later composites misplace it | Append `+repage` |
| `-resize` on an animated GIF | Frames corrupt or misalign | `-coalesce -resize … -layers optimize` |
| `mogrify` without `-path` | Originals overwritten | `mogrify -path OUTDIR` |
| Frame selector on the output | Ignored or an error | Put `[0]` on the input filename |
| `-quality` meaning assumed | PNG quality is zlib level × 10 + filter, not a JPEG-style scale | Read the format's rule |
| Trusting `-version` delegates | Missing coder module fails at runtime | Trust `-list format` plus a 1×1 probe |
| Reusing the same path for input and output | File truncated | Always write a new path |
| `-clone` outside `\( \)` on IM7 | `UnableToCloneImage ... CLINoImageOperator` | Clone only inside a parenthesized sub-list |
| Assuming `-negate`/`-evaluate` skip alpha | IM7's default channel set **includes alpha**, so transparency inverts too | Add `-channel RGB` for IM6-style behaviour |
| Writing a multi-frame input to one filename | Silently expands to `out-0.png`, `out-1.png`, … | Select a frame (`in.gif[0]`) or accept the `%d` expansion |
| Passing `--` to `mogrify` | Creates a file named `--`, exit 0 | Omit it; use `./name` for odd filenames |
| Bare `-` as output | Inherits the *input's* coder, not the one you expected | Write `png:-`, `miff:-`, … explicitly |
| Trusting the output extension | Unresolvable coder silently writes the input's format, exit 0 | Use `FORMAT:out.ext` and confirm `%m` |
| `-extent` with an opaque `-background` | Also flattens the image's **existing** interior transparency and drops the alpha channel | `-background none` to pad while keeping alpha |
| `-coalesce` on a multi-page TIFF/PDF/PSD | Pads every page onto page 1's canvas, exit 0 — sizes silently destroyed | `-coalesce` is for *animations* only; omit it for documents |
| Masking with `-compose DstIn` onto an image with no alpha | Masked-out area becomes opaque **black**, not transparent | Add `-alpha set` to the destination first |
| A mask smaller than the destination | Only the mask's bounding box is affected; the rest stays opaque | Add `-define compose:clip-to-self=false` |
| `-dissolve` with `magick` | Unrecognized option (exit 11) — it exists only on `magick composite` | `-compose Dissolve -define compose:args=40 -composite` |
| `-mosaic` on a negative page offset (e.g. after `-shadow`) | Clips the overhang | `-layers merge` expands to fit |
| `PNG32:` to force a coder | Also forces 8-bit RGBA, silently downconverting a 16-bit source | Plain `PNG:` preserves depth |
| `compare -metric AE` on quantized output (GIF/palette) | Near-total mismatch on a correct pair | Use `RMSE`/`PHASH`, or `-fuzz` |
| `-draw 'rectangle …'` with only `-stroke` set | Fills the region **solid black** — destroys what you meant to highlight | Add `-fill none` |
| `-font 'Family Name'` | Warns at exit 0 and silently substitutes a fallback face | Use the hyphenated name from `-list font` |
| Building annotation text with `2>&1` | Burns an ImageMagick warning into the image | Capture stdout only; check stderr separately |

## Completion checklist

- [ ] Re-located ImageMagick with `command -v magick` for this task.
- [ ] Checked `-version` and confirmed needed formats with `-list format` (and a probe if writing).
- [ ] Confirmed input and output paths do not collide, and no `mogrify` runs in place.
- [ ] Ordered settings before the reads/operators they affect.
- [ ] Explained destructive, lossy, or security-relevant effects before running them.
- [ ] Checked exit status and did not treat a warning as success.
- [ ] Validated the specific claim (dimensions, frames, colorspace, alpha, size) on every output.
- [ ] Reported output paths and the evidence behind the claim.
