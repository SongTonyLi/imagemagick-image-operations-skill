# ImageMagick Command-Line Processing (anatomy of the command line)

Reference for agents. All non-trivial claims below were verified against **ImageMagick 7.1.1-34 Q16-HDRI
aarch64** (`/opt/homebrew/bin/magick`). Source: <https://imagemagick.org/command-line-processing/>
(`/script/command-line-processing.php` 301-redirects there).

---

## 1. Anatomy

```
magick [tool] [setting|operator|sequence-op|stack|input-file]... output-file
```

`magick -help` prints exactly:

```
Usage: magick tool [ {option} | {image} ... ] {output_image}
Usage: magick [ {option} | {image} ... ] {output_image}
       magick [ {option} | {image} ... ] -script {filename} [ {script_args} ...]
       magick -help | -version | -usage | -list {option}
```

The command line is a **strictly left-to-right pipeline** over a mutable *image list*. Arguments are
evaluated in the order written ("do-it-as-you-see-it"). An output filename is required (except for
`-help/-version/-list` and tools like `identify`/`mogrify`/`stream`).

Six ordered components per the docs: input filename(s), image settings, image operators, image
sequence operators, image stacks, output filename.

**Verified:** an operator before any image is a hard error —
`magick -resize 50% rose.png r.png` → `magick: no images found for operation '-resize' at CLI arg 1`.

---

## 2. The three argument kinds

Authoritative per-build classification: **`magick -list CLI`**. (`magick -list Command` dumps all 458
accepted `-x`/`+x` token spellings; `magick -list list` shows every `-list` topic.)

| Kind | Semantics | When it acts |
|---|---|---|
| **Setting** | State stored in the image-info / current image; persists until reset, unset (`+opt`), scope-exited, or command end. | Consumed *later* — at the next read, operator, or write. |
| **Operator** | Applied immediately to **every image currently in the list**, then forgotten. | At the point it appears. |
| **Sequence operator** | Applied immediately to the **image list as a whole** (may change list length). | At the point it appears. |
| **Stack op** | `-clone -delete -insert -swap` — manipulate list membership/order. | Immediately; `-clone` requires a `\( \)` stack (see §5). |

### Settings (`magick -list CLI` → Setting, 76 entries)

```
adjoin affine alpha antialias authenticate background bias bilateral-blur
black-point-compensation blue-primary bordercolor caption channel comment compress debug
define delay density depth direction display dispose dither encoding endian extract family
fill filter font format fuzz geometry gravity green-primary interlace intent interpolate
label limit linewidth log loop mattecolor monitor orient page pointsize preview quality
quiet read-mask red-primary region render repage sampling-factor scene seed size stretch
stroke strokewidth style texture tile transparent-color treedepth type undercolor units
verbose virtual-pixel weight write-mask
```

### Operators (act on each image in the list)

```
annotate black-threshold blur border charcoal chop clip clip-path clip-mask colors colorize
colorspace color-threshold compose contrast convolve crop cycle despeckle draw edge emboss
enhance equalize evaluate extent flip flop floodfill frame gamma gaussian-blur grayscale
implode integral kmeans lat level map median modulate monochrome negate noise normalize
opaque ordered-dither paint posterize raise profile radial-blur random-threshold
range-threshold resample reshape resize roll rotate sample scale sepia-tone segment shade
shadow sharpen shave shear sigmoidal-contrast solarize splice spread strip swirl threshold
transparent thumbnail tint transform trim unsharp version wave white-point white-threshold
```
Channel operators (own category): `channel-fx`, `separate`.

### Sequence operators (act on the whole list)

```
append affinity average clut coalesce combine compare complex composite copy crop debug
deconstruct delete evaluate-sequence fft flatten fx hald-clut ift identify insert layers
limit map maximum minimum morph mosaic optimize print process quiet swap write
```

> Overlap is real: `crop`, `debug`, `evaluate`, `fx`, `limit`, `map`, `quiet` appear in more than one
> category — their meaning depends on list context. Also note `-mosaic`/`-flatten`/`-layers` are
> sequence ops, and `-duplicate`/`-reverse` behave as list ops even though not printed in that group.

### Verified behaviour contrast

| Command | Result |
|---|---|
| `magick -size 10x10 xc:white -negate -size 10x10 xc:white +append c.png` | left half black, right half white → operator hit only images already read |
| `magick -size 20x20 xc:none -background red -flatten f.png` | pixel = `srgb(255,0,0)` |
| `magick -size 20x20 xc:none -flatten -background red f.png` | pixel = `srgb(255,255,255)` — setting arrived too late |

---

## 3. The image list

* 0-based indexing. Negative indices count from the end (`-1` = last). `0--1` = the whole list.
* Reads append to the end of the list, in command-line order.
* `-format ... info:` prints once **per image** in the list.
* FX/percent context: `%[fx:n]` = list length, `%[fx:t]` = index of the image being evaluated,
  `%[fx:i]`/`%[fx:j]` = pixel coords, `u` = current image, `v` = second image.

Verified list-op semantics on `red green blue`:

| Op | Result |
|---|---|
| `-reverse` | blue green red |
| `-swap 0,2` | blue green red |
| `-delete 1` | red blue |
| `+delete` | deletes the **last** image |
| `-insert 0` | moves last image to index 0 → blue red green |
| `-duplicate 2` | list length 3 (works at top level, unlike `+clone`) |

### `-option` vs `+option`

The `+` form generally means *unset / off / apply individually / use the default*. There is no single
universal rule — check the specific option. Verified:

| Pair | Verified difference |
|---|---|
| `-append` / `+append` | vertical (40x20+40x20 → 40x40) / horizontal (→ 80x20) |
| `-gravity center` / `+gravity` | `%[gravity]` = `center` / `none` |
| `-repage` / `+repage` | keeps page geometry / resets it to `0x0+0+0` |
| `-delete N` / `+delete` | delete index N / delete last |
| `-clone N` / `+clone` | clone index N / clone the last image of the parent list |
| `-adjoin` / `+adjoin` | one multi-frame output file / one file per frame |
| `-quiet` / `+quiet` | suppress warnings / restore warnings |

---

## 4. Percent escapes (format specifiers)

Valid in: `-format`, `identify -format`, `info:`, `-annotate`, `-label`, `-caption`, `-comment`,
`-set`, `-draw text`, and in **output filenames** via `%[filename:...]` properties.

| Escape | Meaning (verified on `rose:`) |
|---|---|
| `%w %h` | current width / height (`70` `46`) |
| `%W %H` | page (canvas) width / height |
| `%g` | page geometry, e.g. `70x46+0+0` |
| `%X %Y` | page x/y offset **including sign** (`+5`) |
| `%f %e %t %d` | filename / extension / basename-no-ext / directory (empty for `rose:`) |
| `%m` | file format — **`PNM`** for `rose:`, not `ROSE` |
| `%z %Q` | depth (`8`) / compression quality (`92`) |
| `%b` | file size (`9673B`) |
| `%n %p %s` | number of images / index in list / scene number |
| `%r` | class+colorspace, e.g. `DirectClass sRGB` |
| `%c %l %M` | comment / label / original filename (`rose:`) |
| `%A` | alpha channel state (`Blend`, `Undefined`, …) |
| `%[mean] %[standard-deviation] %[minima] %[maxima]` | **quantum units** (Q16 → 0..65535): `27022.8 15154.8 5654 65535` |
| `%[fx:mean]` | **normalized 0..1**: `0.412341` — differs from `%[mean]`! |
| `%[fx:...]` | runs the full FX expression engine (`%[fx:w*h]` → `3220`) |
| `%[colorspace] %[depth] %[type] %[opaque] %[entropy]` | `sRGB 8 TrueColor True 0.89247` |
| `%[orientation]` | symbolic (`RightTop`) |
| `%[EXIF:Orientation]` | raw EXIF value (`6`); `%[exif:...]` lowercase works identically |
| `%[EXIF:*]` | dumps all EXIF as `exif:Key=Value` lines |
| `%[option:foo]` | value of `-define foo=...`; warns "unknown image property" if unset |
| `%[myprop]` | value set by `-set myprop ...` |

`-precision N` controls float digits (`-precision 3` → `0.412`).
Unknown properties emit a **warning** (exit 0) unless `-regard-warnings`.

---

## 5. Parentheses: image stacks

```
magick wand.gif \( wizard.gif -rotate 30 \) +append out.gif
```

* Parens must be **separate shell words**: `magick red.png \(-size 8x8 xc:blue\)` fails with
  `unable to open image '(-size'`. Use `\( ... \)` (sh/bash/zsh/fish) or `"(" ... ")"`.
  On Windows cmd no escaping is needed.
* Inside `\( \)` a **new child image list** is created; on `\)` its contents are appended to the parent.
* **Nesting works**, verified: `magick -size 8x8 xc:red \( -size 8x8 xc:blue \( -size 8x8 xc:green \) +append \) -append` → 16x16.
* **IM7 gotcha (verified):** `-clone`/`+clone` only work *inside* a stack. At top level:
  `magick rose: +clone -append t.png` → `magick: UnableToCloneImage '+clone' ... CLINoImageOperator`.
  The IM6 shim tolerates it: `magick convert rose: +clone -append t.png` → 70x92 (works).
  Top-level alternative in IM7: `-duplicate`.
* IM7 also supports `{ ... }` to **scope settings**. Verified:
  `magick -size 20x20 xc:white { -fill red } -draw "rectangle 5,5 15,15"` draws **black** (fill
  discarded at `}`), while the same without braces draws red.

---

## 6. Filename references and read modifiers

### Format prefix (`CODER:file`) — overrides extension sniffing
`PNG:x`, `png32:x`, `JPG:x`, `RGB:raw`, `magick:rose` (verified 70x46). Also valid for output:
`magick image.jpg rgb:image`.

### Frame / scene selection — `file[...]` (verified on a 4-frame GIF)
| Syntax | Result |
|---|---|
| `seq.gif[0]` | scene 0 only |
| `seq.gif[1-2]` | scenes 1,2 |
| `seq.gif[2,0]` | scenes 2 then 0 — **order is preserved** |
| `-define frames:step=2` | every other frame |

### Geometry-on-read
| Syntax | Verified |
|---|---|
| `rose.png[20x20]` | resize on read → `20x13` (aspect preserved, like `-resize`) |
| `rose.png[20x20+5+5]` | crop on read → `20x20`, page `70x46+5+5` |
| `-extract 20x20+5+5 rose.png` | setting form of crop-on-read → `20x20` |

Much cheaper than reading full-size then resizing. For a real file whose name contains brackets, use
`-define filename:literal=true`.
`-size WxH` is **ignored for real image files** (verified) — it only sizes generators (`xc:`, `gradient:`, …).

### Built-in generators / pseudo-formats (verified)
| Read | Notes |
|---|---|
| `xc:red`, `canvas:khaki` | uniform color (same coder XC); needs `-size` |
| `gradient:red-blue`, `radial-gradient:white-black` | `magick -list gradient` → Linear, Radial |
| `plasma:fractal`, `pattern:checkerboard` | `pattern:` names via `magick -list ...` docs |
| `rose:` 70x46 PNM, `logo:` 640x480 GIF, `wizard:` 480x640 GIF, `granite:` 128x128, `netscape:` 216x144 | fixed-size built-ins |
| `label:'Hi'`, `caption:'...'`, `text:file.txt` | rendered text; `-size 100x` auto-heights a label |
| `tile:src.png` | tile a texture over `-size` |
| `hald:` | 512x512 identity HALD CLUT |
| `null:` | **1x1 opaque white image in IM7** (`n=1`), not "no image" |
| `stegano:`, `inline:` (base64), `vid:` | misc |

### Write-only / dual pseudo-formats
`info:` (text, `-w+`), `json:` (`-w+`), `txt:` (rw+, pixel enumeration), `sparse-color:` (write),
`histogram:` (write), `null:` (write = discard), `miff:` (rw+), `mpc:` (rw+), `mpr:` (in-memory register).
`info:file.txt` writes the formatted text to a file; `info:-` / `info:` goes to stdout.

### stdin / stdout / fds
* `-` = stdin on read, stdout on write. **Verified gotcha:** a bare `-` output inherits the *input's*
  format — `magick rose: - > f` produced a **PPM**, not PNG. Always write `png:-`, `miff:-`, `gif:-`.
* `fd:N` (N > 2) for explicit descriptors; `fd:1` verified equivalent to stdout.

### `@filename` — read a list of filenames
```
$ printf 'rose.png\nrose.png\n' > list.txt
$ magick @list.txt -append out.png     # verified: 70x92
```
Works on this build. It is commonly **disabled by `policy.xml`**
(`<policy domain="path" rights="none" pattern="@*"/>`), which is the upstream/distro-hardened default.
Check with `magick -list policy` (policy file here:
`/opt/homebrew/Cellar/imagemagick/7.1.1-34/etc/ImageMagick-7/policy.xml`).

### Output filename numbering
| Command | Files produced (verified) |
|---|---|
| `magick ... a b c "out-%d.png"` | `out-0.png out-1.png out-2.png` |
| `magick -scene 5 ... a b "sc-%d.png"` | `sc-5.png sc-6.png` |
| `magick a b -scene 10 "w-%03d.png"` | `w-010.png w-011.png` (scene read at write time) |
| `magick seq.gif +adjoin "pg-%02d.png"` | `pg-00 … pg-03` |
| `magick seq.gif oneshot.png` | **auto-splits** to `oneshot-0.png … oneshot-3.png` because PNG is single-frame |
| `magick rose: -set filename:area '%wx%h' 'rose-%[filename:area].png'` | `rose-70x46.png` |

---

## 7. Ordering rules (the top gotchas)

| Rule | Verified evidence |
|---|---|
| `-density` must precede the **vector read** | `magick -density 300 box.eps o.png` → 300x300 px. `magick box.eps -density 300 o.png` → **72x72 px** (only metadata changed). Same for PDF/SVG. |
| `-quality` must precede the **write** | `magick rose: -quality 20 q.jpg` → `%Q`=20; default JPEG write → 92. |
| `-background` must precede `-flatten`/`-extent`/`-rotate`/`-mosaic` | see §2 table |
| `-gravity` must precede the op it steers | `-gravity center -extent 100x100` centers; `-extent 100x100 -gravity center` puts image top-left |
| `-size` must precede the **generator** | `-size 500x500 rose.png` is ignored |
| Any operator must follow at least one image | `magick -resize 50% in.png out.png` → error "no images found for operation" |
| `-strip` destroys EXIF | after `-strip`, `%[EXIF:Orientation]` warns "unknown image property" |
| `-write f.png` mid-pipeline | `magick rose: -resize 50% -write half.png -resize 50% quarter.png` → 35x23 and 18x12 |

---

## 8. IM7 vs IM6

| Topic | IM6 | IM7 (this build) |
|---|---|---|
| Primary command | `convert` | **`magick`**; `magick -version` → 7.1.1-34 |
| `convert` | primary | Deprecated shim. `convert -version` prints `WARNING: The convert command is deprecated in IMv7, use "magick" instead of "convert" or "magick convert"` — **on stderr, exit 0** |
| Sub-tools | separate binaries | `magick identify`, `magick mogrify`, `magick montage`, `magick composite`, `magick compare`, `magick stream`, `magick conjure`, `magick display`, `magick animate`, `magick import`. `magick -list Tool` lists all 11 (incl. `convert`). Standalone binaries still exist as shims. |
| Default `-channel` | RGB (alpha untouched) | **includes alpha**. Verified on `xc:rgba(255,0,0,0.25)`: bare `-negate` → alpha 0.75; `-channel RGB -negate` → alpha 0.25. Same for `-evaluate multiply 0.5` (alpha 0.8→0.4 by default). Add `-channel RGB` to reproduce IM6. |
| `-alpha off` | reversible | permanently removes alpha |
| `+clone` at top level | allowed | **error** unless inside `\( \)`; works under `magick convert` |
| Settings scoping | none | `{ ... }` scopes settings |
| Argument length limit | 4096 | 131072 |
| Renamed/removed | `-gaussian`, `-deconstruct`, `-affinity`, Bessel filter | use `-gaussian-blur`, `-layers CompareAny`, `-remap`, `-filter Jinc` |

`identify` output of a multi-frame file shows the `file[N]` index form:
`seq.gif[0] GIF 8x8 8x8+0+0 8-bit sRGB 2c ...`.

---

## 9. Exit codes and error handling

Verified exit statuses:

| Situation | Exit |
|---|---|
| success | `0` |
| missing input file | `1` |
| corrupt/undecodable input | `1` |
| bad option argument (`-resize badgeom`) | `1` |
| unknown output coder (`bogusfmt:out`) | `1` |
| **unrecognized option** (`-bogus`) | `11` (fatal, `ProcessCommandOptions`) |
| no arguments | `1` |
| `-help`, `-version` | `0` |
| warning only (e.g. unknown property) | `0` |
| same warning + `-regard-warnings` | `1` |

Scripting rules:
* Test `$?` — do **not** parse stderr; the `convert` deprecation notice goes to stderr with exit 0.
* `-quiet` suppresses **warnings only** (verified: still prints
  `magick: insufficient image data in file 'bad.jpg'` for a real error). `+quiet` restores them.
* `-regard-warnings` promotes warnings to errors → non-zero exit. Use it in CI when EXIF/profile
  problems must fail the build.
* An output file may be partially written before failure; write to a temp name then rename.

---

## 10. Pipelines and intermediates

```bash
magick rose: miff:- | magick - -resize 50% png:- | magick identify -
```
Verified end-to-end (`35x23 PNG`).

| Intermediate | Use |
|---|---|
| `miff:-` | **Preferred pipe format.** Lossless, keeps depth/alpha/metadata/multi-frame. Verified `-depth 16` survives the pipe (`%z`=16). |
| `foo.mpc` (+ sidecar `foo.cache`) | On-disk raw pixel cache: fastest re-read when one source feeds many outputs. Writes **two** files; not portable across IM versions/quantum depths. |
| `mpr:NAME` | In-memory register within **one** command. `magick -size 8x8 xc:red -write mpr:A +delete -size 8x8 xc:blue -write mpr:B +delete mpr:A mpr:B +append out.png` → 16x8, red then blue. Also `-size WxH tile:mpr:tile` to tile a stored image. |
| `-write null:` | run the pipeline for side effects, discard output |
| `png:-`, `gif:-`, `jpg:-` | when the consumer is a non-IM tool |

---

## Common mistakes

| Mistake | Why it breaks | Fix |
|---|---|---|
| `magick in.pdf -density 300 out.png` | PDF already rasterized at 72 dpi before `-density` is seen | `magick -density 300 in.pdf out.png` |
| `magick in.png out.jpg -quality 85` | `-quality` after the output filename never reaches the encoder | `magick in.png -quality 85 out.jpg` |
| `magick a.png b.png -flatten -background white o.png` | background applied after flatten | `-background white` **before** `-flatten` |
| `magick -resize 50% in.png out.png` | operator before any image | put `-resize` after the input |
| `magick rose: +clone -append o.png` | IM7 forbids `-clone` outside a stack | `magick rose: \( +clone \) -append o.png` or `-duplicate 1` |
| `magick a.png (b.png -rotate 5) +append o.png` | shell eats/mis-splits parens | `\( ... \)` with spaces, or `"(" ... ")"` |
| `magick in.png - > out.png` | bare `-` inherits the input coder, not the target extension | `magick in.png png:- > out.png` |
| `magick anim.gif frame.png` | PNG can't hold 4 frames; IM silently writes `frame-0.png…` | `+adjoin frame-%02d.png`, or read `anim.gif[0]` |
| `magick in.png -crop 100x100+0+0 out.png` then compositing looks offset | crop keeps the virtual canvas/page offset | add `+repage` after `-crop` |
| `magick in.png -negate out.png` on RGBA | IM7 negates alpha too | `-channel RGB -negate` |
| Comparing `%[mean]` to `%[fx:mean]` | quantum (0..65535) vs normalized (0..1) | pick one scale |
| `magick @list.txt out.png` fails in prod | `policy.xml` blocks `@*` paths | inline the filenames or relax policy deliberately |
| Relying on `convert` in scripts | deprecated, prints a stderr warning | use `magick` (and `magick identify`, `magick mogrify`) |
| Treating any stderr output as failure | deprecation/warnings exit 0 | check `$?`; add `-regard-warnings` if warnings must fail |
| Piping through PNG/JPEG between steps | re-encode loss / metadata loss | pipe `miff:-` |
