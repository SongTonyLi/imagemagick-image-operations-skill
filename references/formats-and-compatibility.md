# ImageMagick: Formats, Delegates, Security & Version Compatibility

Verified against the local install on 2026-09-10:
`ImageMagick 7.1.1-34 Q16-HDRI aarch64 22301`, Homebrew, macOS arm64, `/opt/homebrew/bin/magick`.

**The one rule that matters: never assume a format, coder, or delegate exists. Run `-list` and check.**
This install proves why — `magick -version` advertises `heic` and `jxl` delegates that **do not actually work**
(see "Local install: known-broken" below).

---

## 1. Enumerate local capability at runtime

Run these before relying on any feature. All are read-only, fast, and safe.

| Command | Answers | Notes for an agent |
|---|---|---|
| `magick -version` | Version, Q-depth, HDRI, feature flags, **claimed** delegates | The delegate list is a *build-time* claim, not proof. Verify with `-list format`. |
| `magick -list format` | Every registered coder + `rw+` mode + backing library version | **Ground truth for "can I read/write X".** Grep it. Absence = unsupported. |
| `magick -list delegate` | External-program conversion rules from `delegates.xml` | Rule exists ≠ binary installed. Also `command -v gs ffmpeg rsvg-convert inkscape`. |
| `magick -list policy` | Active `policy.xml` rules | If output is only `Policy: Undefined / rights: None`, the policy is **open** (nothing restricted). |
| `magick -list configure` | Build config: paths, `QuantumDepth`, `FEATURES`, `DELEGATES`, `CONFIGURE_PATH` | Use `CONFIGURE_PATH` to locate `policy.xml`/`delegates.xml`. |
| `magick -list font` | Fonts usable by `-font` | Never hardcode a font name; `-annotate`/`caption:` fail or silently substitute. |
| `magick identify -list resource` | Current memory/map/disk/area/width/height/time/thread limits | Same as `magick -list resource`. |
| `magick -list module` | Dynamically loadable coder modules | A module can be *listed here* yet fail to load (this install: `heic`, `jxl`). |
| `magick -list *` | Everything (colorspace, filter, kernel, gravity, …) | Use for enumerating valid enum arguments. |

### Reliable capability probes (copy-paste)

```bash
magick -list format | grep -qE '^\s+JXL\*?\s' && echo yes || echo no   # registered?
for b in gs ffmpeg rsvg-convert inkscape dcraw; do                      # binary present?
  printf '%-14s %s\n' "$b" "$(command -v $b || echo MISSING)"; done
magick -size 1x1 xc:red FMT:/tmp/p.fmt && magick identify /tmp/p.fmt    # ONLY real proof
```

**Always use the explicit `FORMAT:file` prefix when probing.** Without it, a bare extension that
ImageMagick doesn't recognize is silently ignored and you get the *input* format written under the
wrong filename (verified — see below). With the prefix you get a hard error instead.

---

## 2. Format table (verified against `magick -list format` on this install)

Mode: `r`=read, `w`=write, `+`=multi-frame/animation. `-` = not supported.
"Local" = status on this specific install.

| Format | Mode | Local | Lossy? | Alpha | Anim | Gotchas |
|---|---|---|---|---|---|---|
| PNG | `rw-` | OK | lossless | yes | no (use APNG) | Default write may be 16-bit here (Q16 build). Use `-depth 8` to force 8-bit. |
| PNG8 | `rw-` | OK | lossless | binary only | no | 8-bit indexed, ≤256 colors. Transparency is on/off, no partial alpha. |
| PNG24 | `rw-` | OK | lossless | **none/binary** | no | Opaque 24-bit RGB. Drops partial alpha — use PNG32 if you need it. |
| PNG32 | `rw-` | OK | lossless | full 8-bit | no | Safest "PNG with alpha" choice. |
| PNG00 | `rw-` | OK | lossless | inherits | no | Inherits bit-depth/color-type from the source image. |
| APNG | `rw+` | OK | lossless | yes | yes | Animated PNG. Distinct coder from PNG. |
| JPEG / JPG | `rw-` | OK | **lossy** | **no** | no | Alpha silently flattened (usually to black). Use `-background white -flatten` first. `-quality` 1-100. Re-encoding always degrades. |
| JXL | `rw+`* | **BROKEN** | both | yes | yes | Advertised in `-version`, **not registered** locally. Writing `out.jxl` silently produces a PNG. |
| WEBP | `rw+` | OK (libwebp 1.5.0) | both | yes | yes | `-define webp:lossless=true` for lossless. Animated WebP needs mux support. |
| HEIC / HEIF | `rw+`* | **BROKEN** | lossy | yes | yes | Advertised in `-version`, **not registered** locally. Same silent-PNG failure. |
| AVIF | `rw+`* | **BROKEN** | lossy | yes | yes | Handled by the `heic` coder; broken for the same reason. |
| GIF | `rw+` | OK | lossless-ish | binary only | **yes** | Max 256 colors/frame; heavy quantization. `-layers Optimize` to shrink. Use `-loop 0` for infinite. `-dispose` matters for transparency. |
| TIFF | `rw+` | OK (libtiff 4.7.1) | both | yes | yes (pages) | Compression: `-compress LZW\|ZIP\|JPEG\|Group4\|ZSTD\|WEBP\|LZMA\|LERC`. Multi-page via `file.tif[n]`. |
| BMP / BMP2 / BMP3 | `rw-` | OK | lossless | limited | no | BMP3/BMP2 for legacy consumers. Alpha support is unreliable across readers. |
| ICO | `rw+` | OK | lossless | yes | multi-size | Write several sizes: `magick in.png -define icon:auto-resize=256,128,64,48,32,16 out.ico`. |
| CUR | `rw-` | OK | lossless | yes | no | Windows cursor; same ICON module. |
| ICNS | `rw+` | OK | lossless | yes | multi-size | macOS icon. Only specific sizes are legal (16,32,128,256,512,1024). |
| SVG / SVGZ | `rw+` | **internal MSVG only** | vector | yes | no | See §2a — this is the biggest quality trap. |
| MSVG | `rw+` | OK | vector | yes | no | ImageMagick's own crude SVG renderer. |
| MVG | `rw-` | OK | vector | yes | no | Magick Vector Graphics — IM's internal drawing language. **Security-sensitive on read.** |
| PDF | `rw+` | **OK (gslib built in)** | raster on read | yes | yes (pages) | See §4. `-density` BEFORE the filename. |
| EPS / EPSF / EPI | `rw-` | OK | raster on read | yes | no | Ghostscript path. `EPS2`/`EPS3` are write-only. |
| PS | `rw+` | OK | raster on read | yes | yes | `PS2`/`PS3` are write-only (`-w+`). |
| PSD / PSB | `rw+` | OK | lossless | yes | layers | `file.psd[0]` = **flattened composite**, `[1]`,`[2]`… = individual layers. Verified locally. |
| DNG/CR2/CR3/NEF/ARW/RAF/ORF/RW2 | `r--` | OK (libraw 0.21.2) | lossless | no | no | **Read-only.** Built-in `raw` delegate (libraw), NOT the external `dcraw` binary. Slow. Use `-define dng:use-camera-wb=true`. |
| MIFF | `rw+` | OK | lossless | yes | yes | IM's native lossless interchange format. Good for pipelines. |
| MPC | `rw+` | OK | lossless | yes | yes | Memory-mapped cache. **Writes TWO files** (`base.mpc` + `base.cache`) — verified. Fast re-reads; not portable across builds/arch. |
| XCF | `r--` | OK | lossless | yes | layers | **Read-only.** GIMP native. |
| DDS | `rw+` | OK | both | yes | mipmaps | `-define dds:compression=dxt1\|dxt5\|none`. |
| EXR | `rw+` | OK (OpenEXR 3.2.4) | lossless | yes | no | True HDR float. **Pairs with the Q16-HDRI build** — preserves out-of-range values. |
| HDR | `rw+` | OK | lossless | no | no | Radiance RGBE. HDR luminance, shared-exponent encoding. |
| PBM/PGM/PPM/PNM/PAM | `rw+` | OK | lossless | PAM only | no | Trivially parseable. `-compress none` forces ASCII. PAM is the only one with alpha. |
| TXT | `rw+` | OK | lossless | yes | no | Human-readable pixel enumeration: `# ImageMagick pixel enumeration: W,H,0,65535,srgb`. Great for exact pixel assertions in tests. |
| JSON | `-w+` | OK | n/a | n/a | n/a | **Write-only metadata.** `magick in.png json:-` dumps full image info. Prefer over parsing `identify -verbose`. |
| RGB/RGBA/RGBO/BGR/GRAY/CMYK | `rw+` | OK | lossless | RGBA yes | yes | Headerless raw. **You MUST supply `-size WxH -depth N`** on read or it fails/garbles. |
| MP4/MOV/AVI/MKV/WEBM/MPEG/M2V/WMV | `rw+` | **write OK, read BROKEN** | lossy | no | yes | Requires the external `ffmpeg` binary. See §2b. |
| FITS | `rw+` | OK | lossless | no | yes | Astronomy; often float data — HDRI build handles it properly. |
| JP2/J2K/JPC/JPT/JPM | `rw-` | OK (openjpeg 2.5.3) | both | yes | no | `-define jp2:rate=` for compression ratio. |
| TGA, PCX, XPM, XBM, SGI, SUN/RAS, PICT, PALM, VIFF, QOI, FARBFELD, VIPS, MAT, DPX, CIN, SIXEL | varies | OK | varies | varies | varies | Present. Check `-list format` for the exact mode before use. |
| DCM (DICOM) | `r--` | OK | varies | no | frames | Read-only. Medical imaging. |
| XPS | `r--` | OK | raster | yes | pages | Read-only, Ghostscript-backed. **Security-sensitive.** |
| HTTP/HTTPS/FTP/FILE | `r--` | **OK, live network** | n/a | n/a | n/a | **`magick https://host/x.png out.png` performs a real network fetch — verified working.** Major SSRF surface. |
| MSL | `rw+` | **OK** | n/a | n/a | n/a | Magick Scripting Language. **Executes a script.** Primary ImageTragick vector. Disable for untrusted input. |
| EPHEMERAL / SHOW / WIN | — | **not registered** | n/a | n/a | n/a | Absent on this build. One less attack surface. |

### 2a. SVG — verify the renderer, quality differs enormously

Three possible SVG backends, in descending fidelity: **Inkscape** > **librsvg (RSVG)** > **internal MSVG**.
The internal MSVG renderer handles only a small subset of SVG — it commonly drops gradients, filters,
clip paths, CSS, and web fonts, producing silently wrong output rather than an error.

**On this install, SVG renders with the INTERNAL MSVG renderer.** Verified: `-list format` shows
`SVG* SVG rw+ Scalable Vector Graphics (XML 2.9.13)` — the "(XML …)" tag means libxml, i.e. **no RSVG
linked in** (`--with-rsvg=no`), and `svg:` vs `msvg:` produced **byte-identical output**
(`compare -metric AE` = 0). `rsvg-convert 2.60.0` *is* installed and `delegates.xml` has a
`svg => rsvg-convert` rule, but the built-in SVG coder claims the format first so the rule never fires.

```bash
magick -list format | grep -iE '^\s+(SVG|MSVG)'   # "(RSVG x.y)" => librsvg; "(XML x.y)" => internal
magick svg:in.svg a.png; magick msvg:in.svg b.png
magick compare -metric AE a.png b.png null:       # 0 => internal renderer in use
```

**Recommendation for good SVG output on this machine: bypass ImageMagick.**
```bash
rsvg-convert -w 1024 -o out.png in.svg          # then post-process with magick if needed
```

### 2b. Video — write works, read is broken locally

`ffmpeg 8.1.1` is installed at `/opt/homebrew/bin/ffmpeg` and `delegates.xml` defines
`video:decode => ffmpeg -nostdin -loglevel error -i '%s' -an -f rawvideo -y %s '%s'`.

- **Writing** works: `magick anim.gif out.mp4` produced a valid `ISO Media, MP4 Base Media v1` file.
- **Reading fails**: `magick identify out.mp4` → `Unknown encoder 'webp' / Error selecting an encoder`.
  This build's video path asks ffmpeg for a `webp` encoder, and the local ffmpeg has **none**
  (`ffmpeg -encoders | grep -c ' webp'` → `0`).

**Workaround: use ffmpeg directly for frame extraction**, then hand PNGs to ImageMagick.
```bash
ffmpeg -i in.mp4 -vsync 0 /tmp/f_%04d.png && magick /tmp/f_*.png out.gif
```

### 2c. Local install: known-broken coders (HEIC / HEIF / AVIF / JXL)

`magick -version` lists `heic` and `jxl` among built-in delegates, but **neither format is registered**
and both fail at runtime:
```
magick: unable to load module '.../coders/heic.la': file not found @ error/module.c/OpenModule/1293
```
Root cause: this is a `--with-modules` build. `heic.la` hardcodes
`-L/opt/homebrew/Cellar/libheif/1.17.6_1/lib` and `heic.so` links `libheif.1.dylib` at build version
1.17.6, but Homebrew has since upgraded libheif to **1.19.8** — the old Cellar path is gone and libltdl
cannot resolve the module. Same story for `jxl`. **Fix: `brew reinstall imagemagick`.**

**The dangerous part is the failure mode.** Verified:
```bash
magick base.png out.heic     # exit 0, NO error, 501-byte file created
magick identify out.heic     # -> out.heic PNG 64x64 ...   <-- it is a PNG!
```
An unregistered extension is silently ignored and the **input** format is written under the requested
filename. Same for `.avif` and `.jxl`. With the explicit prefix you get a proper error instead:
```bash
magick base.png heic:out.heic   # -> unable to load module '.../heic.la'
```
**Rule: always write `FORMAT:path` for any format you have not verified, and `identify` the result.**

---

## 3. Quantum depth & HDRI (this build: **Q16-HDRI**)

| Term | Meaning | Check |
|---|---|---|
| `Q8` / `Q16` / `Q32` | Bits per channel sample in the pixel cache. Q16 → `QuantumRange` = 65535. | `magick -list configure \| grep QuantumDepth` |
| `HDRI` | Samples are **floating point**; values outside `[0, QuantumRange]` are preserved instead of clipped. | `magick -version \| grep -o HDRI` |
| Combined | `magick -version` → `Q16-HDRI`; `magick -list configure \| grep FEATURES` → includes `HDRI`. | |

```bash
magick -format '%[fx:quantumrange]\n' -size 1x1 xc: info:   # -> 65535   (verified)
magick -version | grep -qi hdri && echo HDRI || echo non-HDRI
```

### When HDRI actually matters (all verified locally)

| Operation | Non-HDRI (clipped) | Q16-HDRI (this build) |
|---|---|---|
| `-evaluate multiply 4` on 50% gray | `1.0` | **`2.0`** — over-range survives |
| `-evaluate subtract 30%` on 20% gray | `0` | **`-0.100005`** — negative survives |
| after adding `-clamp` | `1.0` / `0` | `1.0` / `0` — clamped back |
| writing to PNG | `1.0` | `1.0` — **implicitly clamped on write to integer formats** |

**Practical consequences:**
- Range-expanding math (`-evaluate`, `-fx`, `-function`, `-compose Plus/Minus`, convolution with
  negative kernel weights) can leave pixels outside `[0,1]`. They look fine after a PNG write (clamped)
  but propagate wrongly through further operations. **Insert `-clamp` before writing, or before any
  operation that assumes normalized input.**
- HDRI is what makes EXR/HDR/FITS round-trips meaningful; on a non-HDRI build those are lossy.
- Q16 makes intermediate files ~2× larger — `magick in.png out.png` here produced a **16-bit** PNG.
  Add `-depth 8` when you want a normal 8-bit file.
- `-fx` / `%[fx:...]` return normalized `0.0–1.0` floats regardless of Q depth, but on HDRI they can
  legitimately exceed that range.

---

## 4. Ghostscript / PDF / EPS / PS

### Detection

```bash
magick -list format | grep -E '^\s+(PDF|EPS|PS)\s'   # coder registered?
magick -list delegate | grep -iE 'ps|pdf|eps'         # gs-based rules
command -v gs && gs --version                          # external binary
magick -version | grep -o gslib                        # gs linked IN as a library
```

**Local finding: PDF/PS/EPS all work.** This build has **`gslib` compiled in**, so Ghostscript is a
*linked library* — it does not shell out to `gs`. A separate `gs 10.00.0` also exists at
`/usr/local/bin/gs`, and `delegates.xml` has six `gs` rules (`eps<=>ps`, `eps<=>pdf`, `pdf<=>ps`,
`pdf<=>eps`, `ps<=>eps`, `ps<=>pdf`), all invoked with `-dSAFER`.

### Rules

| Rule | Why | Verified |
|---|---|---|
| **`-density` goes BEFORE the input filename** | It's a *setting* that controls rasterization resolution. After the filename it only relabels metadata. | `magick -density 300 t.pdf o.png` → **267×267**; `magick t.pdf -density 300 o.png` → **64×64** |
| Page select with `file.pdf[0]` | 0-based. Quote it — the shell will glob `[0]`. | `magick 't.pdf[0]' p0.png` → OK |
| Rasterizing a PDF is **lossy and irreversible** | Vector text/paths become pixels at a fixed DPI. Never round-trip PDF→PNG→PDF if the original is available. | — |
| `-define pdf:use-cropbox=true` | Use CropBox instead of MediaBox — avoids printer margins/bleed showing up as whitespace. | — |
| Also useful | `-define pdf:fit-page=WxH`, `-alpha remove -background white` (PDFs rasterize with transparency), `-colorspace sRGB` (CMYK PDFs). | — |
| Default density is only 72 DPI | Output looks blurry unless you raise it. 150 for screen, 300 for print. | — |

### The security-policy trap (most common PDF failure in the wild)

Many distros (Debian/Ubuntu/RHEL, most Docker images) ship a `policy.xml` that **disables PDF/PS/EPS**
after CVE-2018-16509 and friends:
```xml
<policy domain="coder" rights="none" pattern="PDF" />
<policy domain="coder" rights="none" pattern="{PS,PS2,PS3,EPS,PDF,XPS}" />
```
The error:
```
convert: attempt to perform an operation not allowed by the security policy `PDF' @ error/constitute.c/ReadImage/412
convert: no images defined `out.png' @ error/convert.c/ConvertImageCommand/3300
```
**Detect it, don't guess:** `magick -list policy | grep -iE 'coder|pattern|rights'`.
Fixes: comment out the rule, point `MAGICK_CONFIGURE_PATH` at a permissive `policy.xml`, or bypass IM
entirely: `gs -sDEVICE=png16m -r300 -o out.png in.pdf`.

**On THIS machine there is no such restriction — PDF read and write both work.**

---

## 5. `policy.xml` — location and semantics

**Local path (verified):** `/opt/homebrew/Cellar/imagemagick/7.1.1-34/etc/ImageMagick-7/policy.xml`
Found via `magick -list configure | grep CONFIGURE_PATH`; also printed by `magick -list policy`.
No per-user override exists (`~/.config/ImageMagick/` and `~/.magick/` are both absent) and no
`MAGICK_*` env vars are set.
Search order: `MAGICK_CONFIGURE_PATH` → `~/.config/ImageMagick/` → build `CONFIGURE_PATH` → built-in.

**Local finding: this is the "open" policy — it restricts NOTHING.** The entire `<policymap>` is
commented out except `<policy domain="Undefined" rights="none"/>`, and
`magick -list configure | grep SECURITY_POLICY` reports `open`. So `magick -list policy` shows only
`Policy: Undefined / rights: None`. **All coders (MSL, MVG, SVG, PDF, HTTPS, URL) and all delegates are
permitted** — confirmed empirically by a live `https://` fetch.

### Domains

| Domain | Controls | Example |
|---|---|---|
| `resource` | Memory/disk/size/time ceilings (see §8) | `<policy domain="resource" name="memory" value="256MiB"/>` |
| `coder` | Per-format read/write rights | `<policy domain="coder" rights="none" pattern="{PS,EPS,PDF,XPS}"/>` |
| `module` | Whether a coder module may load at all | `<policy domain="module" rights="write" pattern="{MSL,MVG,PS,SVG,URL,XPS}"/>` |
| `delegate` | External program execution | `<policy domain="delegate" rights="none" pattern="*"/>` |
| `filter` | Loadable image filters (`-process`) | `<policy domain="filter" rights="none" pattern="*"/>` |
| `path` | Filesystem access by glob | `<policy domain="path" rights="none" pattern="@*"/>` (blocks indirect reads) |
| `cache` | Pixel cache behavior | `<policy domain="cache" name="memory-map" value="anonymous"/>` |
| `system` | `shred`, `memory-map`, `max-memory-request`, `precision`, default `font` | `<policy domain="system" name="max-memory-request" value="256MiB"/>` |

**Rights:** `none`, `read`, `write`, `execute`, `all`; combine with `|` (e.g. `read | write`).
**Rules are processed in order** — the deny-all-then-allowlist idiom depends on it:
```xml
<policy domain="delegate" rights="none" pattern="*" />
<policy domain="filter"   rights="none" pattern="*" />
<policy domain="coder"    rights="none" pattern="*" />
<policy domain="coder"    rights="read|write" pattern="{GIF,JPEG,PNG,WEBP}" />
```
Resource policies are **maximums**: if policy says 1GB and you pass `-limit memory 2GB`, you get 1GB.
Patterns must be **UPPER-CASE** before 7.1.1-16 (`EPS` not `eps`); use `[Pp][Nn][Gg]` to be safe.
A policy with `stealth="true"` (e.g. `shared-secret`) is hidden from `-list policy`.

**How a denial manifests** — an operation-level error, not a file-not-found:
```
attempt to perform an operation not allowed by the security policy `PDF'
```
If you see that string, it is a **policy problem, not a missing delegate**. Do not try to install
Ghostscript; inspect `magick -list policy`.

Validate a hand-written policy at <https://imagemagick-secevaluator.doyensec.com/>.

---

## 6. IM6 → IM7 porting (CLI-visible only)

| Concern | IM6 idiom | IM7 idiom | Verified locally |
|---|---|---|---|
| Entry point | `convert in.png out.jpg` | **`magick in.png out.jpg`** | `convert` still exists but prints `WARNING: The convert command is deprecated in IMv7, use "magick"` |
| Sub-tools | `identify`, `mogrify`, `composite`, `montage`, `compare` | `magick identify`, `magick mogrify`, … (legacy names are symlinks) | symlinks confirmed |
| **Alpha in default channel set** | `-negate` leaves alpha alone | `-negate` **also negates alpha**; use `-channel RGB -negate` | `xc:rgba(255,0,0,0.25) -negate` → **a=0.75**; with `-channel RGB` → a=0.25 |
| Alpha on/off | `-matte` / `+matte` | `-alpha set` / `-alpha off` | `-matte` → `option has been replaced '-matte', use "-alpha Set"` |
| Alpha modes | — | `-alpha activate\|deactivate\|set\|off\|remove\|discrete\|copy\|extract` | |
| Alpha in blurs/convolve | excluded | **included**; add `-alpha discrete` to process alpha independently | |
| Masks | `-mask`, `-clip-mask` | `-read-mask` (protect from update) / `-write-mask` (protect from write); `-mask` kept for compat | |
| Channel surgery | `-separate` + `-combine` juggling | `-channel-fx '\| gray=>alpha'` | |
| `+combine` | `+combine` | **`+combine <colorspace>`** — argument now required | bare `+combine` → `MissingArgument '+combine'` |
| Grayscale | `-colorspace Rec709Luma` | `-intensity Rec709Luminance -colorspace gray` (`Rec*Luma` colorspaces removed) | |
| Grayscale storage | 4 channels (RGBA) | **1 channel**; `-colorspace sRGB` to expand back before adding color | |
| `-gamma` multi-arg | `-gamma 1,2,3` | not supported → `-channel blue -gamma 2` | |
| `-region` | cloned + composited a sub-image | sets a **write mask**; transforms are relative to image origin, not region origin | |
| `-draw` alpha | `-draw 'matte 0,0 floodfill'` | `-draw 'alpha 0,0 floodfill'` | |
| `-composite` order | `composite fg.png bg.png out.png` (overlay FIRST) | **`magick bg.png fg.png -composite out.png`** (background FIRST) | center pixel = red ⇒ fg over bg ✓ |
| Averaging | `-average` | `-evaluate-sequence Mean` | warns with the replacement |
| Min/max/median | `-maximum` / `-minimum` / `-median` | `-evaluate-sequence Max\|Min\|Median` | |
| Blur | `-gaussian 0x2` | `-gaussian-blur 0x2` | warns with the replacement |
| Colour matrix | `-recolor` | `-color-matrix` | warns with the replacement |
| Remap | `-map` / `-affinity` | `-remap` | |
| Transform | `-transform` | `-distort Affine "..."` | |
| Affine | `-affine` | `-draw "affine ..."` | |
| Under-colour | `-box` | `-undercolor` | |
| Deconstruct | `-deconstruct` | `-layers CompareAny` | |
| Convolve bias | `-bias` | `-define convolve:bias=value` | |
| Show kernel | `-define showKernel=1` | `-define morphology:showKernel=1` | |
| **Removed outright** | `-interpolate` (as an operator), `-origin`, `-passphrase` | hard error | `unrecognized option '-origin' / '-passphrase'` |
| Option ordering | loosely grouped, order-insensitive | **strictly sequential**: an operator only affects images already read | |
| Settings scoping | global | use `\( ... \)` to scope settings/images, `{ ... }` to save/restore settings | |
| Filename vs option | ambiguous | `-read <file>` for filenames starting with `-`; `--` ends options | |
| Arg length cap | 4,096 chars | 131,072 chars | |
| `%Z` escape | supported | removed | |

**The three that bite an agent most often:** (1) `magick` not `convert`; (2) **alpha is now in the
default channel set** — add `-channel RGB` to reproduce IM6 output; (3) **`-composite` takes background
first**, the opposite of the old standalone `composite` tool.

---

## 7. Untrusted-input safety

ImageMagick's CVE history (ImageTragick CVE-2016-3714 and successors) centers on **coders that execute
things**: MSL scripts, MVG/SVG parsers, the `EPHEMERAL`/`URL`/`HTTPS` coders, `|`-prefixed filenames,
and delegate command injection through crafted filenames.

### Rules

1. **Never interpolate an unquoted user string into a shell command.** Prefer an exec-style API
   (`subprocess.run([...], shell=False)`) over a shell string. `delegates.xml` templates like
   `'gs' ... '-sOutputFile=%o' '-f%i'` are quoted, but a filename containing `'` can still break out.
2. **Beware the coder prefix.** `magick "$USER_FILE" out.png` lets the *name* pick the coder:
   `msl:evil.png` runs a script, `https://…` performs a network fetch. Both verified live on this box —
   `msl:base.png` loaded the MSL coder, and an `https://` URL was fetched over the network.
3. **Always use an explicit `FORMAT:` prefix for untrusted input**, and strip/reject any user-supplied
   `:` prefix and leading `-`, `@`, `|`:
   ```bash
   magick "png:$(realpath -- "$user")[0]" -strip out.png
   ```
   This also prevents the silent-wrong-format failure from §2c.
4. **Filenames starting with `|`**: historically piped to a shell. **Not exploitable on this build**
   (`magick -size 8x8 xc:red '|touch /tmp/PWNED'` did not create the file), but still sanitize.
5. **`@file` indirect reads are a live risk vector here.** `magick '@list.txt' out.png` **worked**
   (read the filenames listed inside), as did `caption:@cap.txt`. An attacker-controlled `@` argument
   reads arbitrary local files. Block with `<policy domain="path" rights="none" pattern="@*"/>`.
6. **Disable dangerous coders for untrusted work.** Minimum set: `MSL`, `MVG`, `SVG`, `EPHEMERAL`,
   `URL`, `HTTPS`, `HTTP`, `FTP`, `FILE`, `TEXT`, `SHOW`, `WIN`, `PS`, `PS2`, `PS3`, `EPS`, `PDF`, `XPS`.
   Or invert it — allowlist only what you need.
7. **Use `--` to terminate option parsing on `magick` and `magick identify` only.** **Never on `mogrify`** — it treats `--` as a filename, writes a file literally named `--`, and exits 0. Note also that `--` does *not* neutralize a `coder:` prefix; only a `./` path prefix (relative paths) or an explicit `FORMAT:` prefix does.
8. **Always set `-limit`s** (§8) — decompression bombs are the easiest DoS.
9. **Validate the output**, don't trust exit codes. `magick` returned **0** while writing a PNG named
   `.heic`. Always `magick identify out.x` and check the reported format and dimensions.
10. **Strip metadata** with `-strip` — EXIF/XMP/ICC can carry payloads and PII.
11. **Prefer a hardened profile**: run under a restrictive `policy.xml` via `MAGICK_CONFIGURE_PATH`, in a
    container, as an unprivileged user, with a private `temporary-path`.

### Minimal hardened policy for untrusted input

```xml
<policymap>
  <policy domain="resource" name="memory"      value="256MiB"/>
  <policy domain="resource" name="map"         value="512MiB"/>
  <policy domain="resource" name="disk"        value="1GiB"/>
  <policy domain="resource" name="area"        value="128MP"/>
  <policy domain="resource" name="width"       value="16KP"/>
  <policy domain="resource" name="height"      value="16KP"/>
  <policy domain="resource" name="time"        value="60"/>
  <policy domain="resource" name="list-length" value="32"/>
  <policy domain="delegate" rights="none" pattern="*"/>
  <policy domain="filter"   rights="none" pattern="*"/>
  <policy domain="path"     rights="none" pattern="@*"/>
  <policy domain="coder"    rights="none" pattern="*"/>
  <policy domain="coder"    rights="read|write" pattern="{GIF,JPEG,PNG,WEBP,TIFF,BMP}"/>
  <policy domain="system"   name="shred" value="1"/>
  <policy domain="system"   name="max-memory-request" value="256MiB"/>
</policymap>
```

---

## 8. Resource limits

Set with `-limit <resource> <value>`, or a `resource` policy, or a `MAGICK_*` env var.
Policy is a hard ceiling that `-limit` cannot exceed. Inspect with `magick identify -list resource`.

| Resource | Limits | On exceed | Env var | **Local value** |
|---|---|---|---|---|
| `memory` | Pixel-cache bytes from the heap | Falls back to memory-mapped disk | `MAGICK_MEMORY_LIMIT` | 32GiB |
| `map` | Bytes of memory-mapped pixel cache | Falls back to on-disk cache | `MAGICK_MAP_LIMIT` | 64GiB |
| `disk` | Bytes of disk for the pixel cache | **Exception thrown**, cache not created | `MAGICK_DISK_LIMIT` | unlimited |
| `area` | `width × height` that may live in memory | Cached to disk (not fatal) | `MAGICK_AREA_LIMIT` | 137.439GP |
| `width` | Max image width in pixels | **Exception**: `width or height exceeds limit` | `MAGICK_WIDTH_LIMIT` | 36.0288PP |
| `height` | Max image height in pixels | **Exception**: `width or height exceeds limit` | `MAGICK_HEIGHT_LIMIT` | 36.0288PP |
| `file` | Max open pixel-cache files | Files closed/reopened on demand | `MAGICK_FILE_LIMIT` | 786432 |
| `thread` | Max parallel OpenMP threads | Capped silently | `MAGICK_THREAD_LIMIT` | 11 |
| `throttle` | Ms to yield the CPU periodically | Slows down (cooperative) | `MAGICK_THROTTLE_LIMIT` | 0 |
| `time` | Max wall-clock seconds | **Exception**: `time limit exceeded` | `MAGICK_TIME_LIMIT` | unlimited |
| `list-length` | Max images in a sequence | **Exception** | `MAGICK_LIST_LENGTH_LIMIT` | unlimited |

Also: `MAGICK_TEMPORARY_PATH` (temp file location; locally
`/var/folders/tz/.../T`), `MAGICK_CONFIGURE_PATH` (config/policy search path),
`MAGICK_TMPDIR`, `MAGICK_DEBUG`, `MAGICK_FONT_PATH`, `OMP_NUM_THREADS`.

**Units.** Bytes take SI/IEC prefixes (`100MB`, `256MiB`, `2GiB`). Pixel counts take pixel suffixes:
`P` = pixel, `KP` = 10³, `MP` = 10⁶ (megapixels), `GP` = 10⁹, `PP` = 10¹⁵. So `8KP` width = 8000 px and
the local `36.0288PP` is effectively "no limit".

**Verified enforcement:**
```bash
magick -limit width 32 -size 64x64 xc:red o.png
# -> magick: width or height exceeds limit `red' @ error/cache.c/OpenPixelCache/3696

magick -limit time 1 -size 4000x4000 xc:red -blur 0x20 o.png
# -> magick: time limit exceeded `red' @ error/cache.c/GetImagePixelCache/1703
```

**Pixel cache fallback chain:** heap (`memory`) → anonymous memory map (`map`) → disk (`disk`).
Each step is slower; if you see unexplained slowness on big images, raise `memory`/`map`.

**Sane defaults for untrusted input:**
```bash
magick -limit memory 256MiB -limit map 512MiB -limit disk 1GiB \
       -limit area 128MP -limit width 16KP -limit height 16KP \
       -limit time 60 -limit list-length 32 \
       png:in.png -strip -resize 1024x1024\> png:out.png
```
