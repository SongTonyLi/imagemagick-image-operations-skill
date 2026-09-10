# ImageMagick Operation Reference (intent → option)

Verified against **ImageMagick 7.1.1-34 Q16-HDRI aarch64** at `/opt/homebrew/bin/magick` (macOS/Homebrew).
Built-in delegates: `bzlib fontconfig freetype gslib heic jng jp2 jpeg jxl lcms lqr ltdl lzma openexr png ps raw tiff webp xml zlib zstd`. Features: `Cipher DPC HDRI Modules OpenMP(5.0)`.
Every option below was executed locally. Discrepancies vs. imagemagick.org are called out in §13.

**Golden rule of IM7 argument order:** the command line is read left→right. *Settings* (`-density`, `-delay`, `-size`, `-font`, `-background`, `-fill`…) affect only images read/created **after** them. *Operators* (`-resize`, `-crop`, `-blur`…) act on images already in the list. When in doubt, put settings before the input filename.

---

## 1. The CLI tools

`magick -list Tool` → `animate compare composite conjure convert display identify import mogrify montage stream`. Invoke as `magick <tool> …` (preferred) or via the legacy shim binaries.

| Tool | Invocation | Use when |
|---|---|---|
| `magick` | `magick [opts] in… [opts] out` | Default. Read → transform → write, N inputs → M outputs. |
| `magick identify` | `magick identify [-verbose|-format …] file` | Inspect only; never writes. |
| `magick mogrify` | `magick mogrify [opts] file…` | Batch, **in-place**. |
| `magick montage` | `magick montage [opts] in… out` | Contact sheet / grid of labeled thumbnails. |
| `magick composite` | `magick composite [opts] src dst [mask] out` | Two-image overlay, simple case. |
| `magick compare` | `magick compare [-metric M] a b diff` | Difference metric + visual diff map. |
| `magick stream` | `magick stream [-map rgb -storage-type char] in raw` | Stream raw pixels of a huge image without full decode. |
| `magick conjure` | `magick conjure [msl:]script.msl` | Run an MSL (XML) script. Use the `msl:` prefix if the extension isn't auto-detected. |
| `magick display` / `animate` / `import` | X11 GUI / screen capture | **On this build they exist but abort with "delegate library support not built-in"** — no X11. Do not use. |
| `magick convert` | legacy | Deprecated in IM7 (prints a warning). Only reason to use it: a few options the native `magick` CLI rejects (see §13). |

> **`mogrify` overwrites the original file in place by default.** `magick mogrify -resize 50% *.jpg` destroys the originals.
> Always either add **`-path DIR`** (writes results into `DIR`, sources untouched — verified: `mogrify -path dst -resize 20x20 src/g.png` left `src/g.png` at 200x100 and produced `dst/g.png` at 20x10) or add **`-format png`** (writes a new extension alongside). Work on a copy when unsure.

---

## 2. Inspect / metadata

| Intent | Command |
|---|---|
| One-line summary | `magick identify f.png` → `f.png PNG 200x100 200x100+0+0 16-bit sRGB 985B` |
| Everything | `magick identify -verbose f.png` |
| Header only, no pixel decode (fast) | `magick identify -ping f.png` |
| Machine-readable | `magick f.png json:-` (also `magick identify -format %[…]`) |
| Custom fields | `magick identify -format "%wx%h %m %[colorspace]\n" f.png` |
| Print mid-pipeline | `magick f.png -print "%wx%h\n" -resize 50% out.png` |
| Introspect the binary | `magick -list <type>` |

`magick -list list` (all list types): Align Alpha AutoThreshold Boolean Cache Channel Class CLI ClipPath Coder Color Colorspace Command Compliance Complex Compose Compress Configure DataType Debug Decoration Delegate Direction Dispose Distort Dither Endian Evaluate FillRule Filter Font Format Function Gradient Gravity Illuminant Intensity Intent Interlace Interpolate Kernel Layers LineCap LineJoin List Locale LogEvent Log Magic Method Metric Mime Mode Module Morphology Noise Orientation Pagesize PixelChannel PixelIntensity PixelMask PixelTrait Policy PolicyDomain PolicyRights Preview Primitive QuantumFormat Resource SparseColor Statistic Storage Stretch Style Threshold Tool Type Units Validate VirtualPixel Weight WordBreak.
`magick -list Command` prints a 458-entry option table (both `-x` and `+x` forms). Useful, but **not a complete inventory** — verified counter-examples: `-canny` and `-mean-shift` both run successfully yet are absent from the list.

The authoritative test for "does this option exist here?" is to run it and read the exit status:

| Exit | Meaning |
|---|---|
| `11` | unrecognized option — the option genuinely does not exist on this build |
| `1` + `option deprecated, unable to execute` | recognized but removed (`-maximum`, `-minimum`) |
| `0` + `option has been replaced` on stderr | still works, auto-translated (`-transform`, `-affine`, `-median`) |
| `0` | supported |

```bash
magick rose: -canny 0x1+10%+30% /tmp/probe.png >/dev/null 2>&1; echo $?   # 0 -> supported
```

**Percent escapes** (verified): `%w %h` px size · `%g` full geometry `WxH+X+Y` · `%W %H` canvas · `%X %Y` page offset · `%m` format · `%f` filename · `%t` basename · `%e` extension · `%d` directory · `%b` human size · `%B` bytes · `%z` depth · `%Q` quality · `%k` unique colors · `%n` #images · `%s` scene index · `%T` delay (ticks) · `%[colorspace] %[type] %[page] %[orientation] %[quality] %[version]`.
**Statistics:** `%[mean] %[standard-deviation] %[min] %[max] %[skewness] %[kurtosis] %[entropy] %[colors]`. Values are in the Q16 quantum range (0–65535).
**Computed:** `%[fx:EXPRESSION]`, e.g. `-format "%[fx:w*h]"`.

**EXIF / IPTC / XMP:** `-format "%[EXIF:*]"` dumps every tag as `exif:Tag=Value`; `%[EXIF:Make]`, `%[EXIF:Orientation]`, `%[EXIF:PixelXDimension]` read one. Case-insensitive (`%[exif:*]` works). Requesting a tag that isn't present emits `unknown image property` to stderr and yields empty — guard with `2>/dev/null`. IPTC via `%[IPTC:2:120]`; profiles listed in `-verbose` output as `Profile-exif`, `Profile-iptc`, `Profile-xmp`, `Profile-icc`.
`-set exif:Make Foo` does **not** synthesize a real EXIF block (verified: unreadable afterwards) — it only sets an artifact.

---

## 3. Geometry & resizing

### Geometry argument syntax (all verified on a 200x100 source)

| Form | Meaning | Result |
|---|---|---|
| `WxH` | fit inside box, preserve aspect | `-resize 50x50` → 50x25 |
| `WxH!` | force exact, **ignore** aspect | `-resize '50x50!'` → 50x50 |
| `WxH>` | shrink only if larger than box | `-resize '500x500>'` → 200x100 (unchanged) |
| `WxH<` | enlarge only if smaller than box | `-resize '500x500<'` → 500x250 |
| `WxH^` | fill/cover the box (min dimension meets) | `-resize '50x50^'` → 100x50 |
| `N%` or `WxH%` | percentage scale | `-resize 50%` → 100x50 |
| `A@` | scale so total pixel area ≤ A | `-resize '5000@'` → 100x50 |
| `xH` | height only, aspect kept | `-resize x50` → 100x50 |
| `Wx` | width only, aspect kept | `-resize 100x` → 100x50 |
| `WxH+X+Y` | size plus offset (crop/extent/composite) | |
| `WxH-X-Y` | negative offset (off canvas top/left) | |
| `WxH{+-}X{+-}Y!` | for `-crop`: `!` forces the region to stay inside the image | |
| `WxH@` on `-crop` | tile the image into ≈N equal pieces | `-crop 3x1@` → three 67x100/66x100/67x100 tiles |

**Quote geometry strings** — `!`, `^`, `>`, `<`, `@` are all shell metacharacters.

### Resize-family options

| Option | Syntax | What it does |
|---|---|---|
| `-resize` | `geometry` | Standard high-quality resample (filter from `-filter`, default Lanczos/Mitchell). |
| `-thumbnail` | `geometry` | Resize **and strip all metadata/profiles** (verified: a `-set comment` survives `-resize`, is gone after `-thumbnail`). Fastest good-quality path for batches. |
| `-scale` | `geometry` | Simple pixel averaging, no filter. **Preserves aspect ratio** (docs claim otherwise — see §13). |
| `-sample` | `geometry` | Nearest-neighbour point sampling; blocky, very fast. |
| `-adaptive-resize` | `geometry` | Data-dependent triangulation; sharper on line art. |
| `-interpolative-resize` | `geometry` | Resize using the `-interpolate` method. |
| `-magnify` | *(no arg)* | Double the size. |
| `-liquid-rescale` | `geometry` | Seam-carving / content-aware rescale (needs `lqr`, present here). |
| `-resample` | `H{xV}` | Resize to change DPI, using the image's stored density. |
| `-filter` | `type` | Resampling kernel; `magick -list Filter` → Bartlett Blackman Bohman Box Catrom Cosine Cubic Gaussian Hamming Hann Hermite Jinc Kaiser Lagrange Lanczos Lanczos2 Lanczos2Sharp LanczosRadius LanczosSharp Mitchell Parzen Point Quadratic Robidoux RobidouxSharp Sinc SincFast Spline CubicSpline Triangle Welch. |

### Canvas / cropping options

| Option | Syntax | What it does |
|---|---|---|
| `-crop` | `WxH{+-}X{+-}Y{!}` or `WxH@` | Extract region(s). Multiple regions ⇒ multiple output images. |
| `-extent` | `WxH{+X+Y}` | Set canvas to exactly WxH, padding with `-background`, anchored by `-gravity`. |
| `-trim` | *(no arg)* | Remove uniform border; pair with `-fuzz N%`. |
| `-chop` | `WxH{+X+Y}` | Delete an interior band and close the gap (200x100 `-chop 20x0+0+0` → 180x100). |
| `-splice` | `WxH{+X+Y}` | Insert a band of `-background` (200x100 `-splice 0x30` → 200x130; add `-gravity south` to put the bar at the bottom). |
| `-border` | `WxH` | Add `-bordercolor` border on all sides (200x100 `-border 10x5` → 220x110). |
| `-shave` | `WxH` | Remove W px from each side, H from top and bottom (→ 180x90). |
| `-frame` | `WxH{+outer+inner}` | 3-D decorative frame in `-mattecolor` (`-frame 10x10+3+3` → 220x120). |
| `-repage` | `WxH{+X+Y}` | Set the virtual-canvas page geometry. |
| `+repage` | *(no arg)* | **Erase** the page geometry/offset. |
| `-page` | `geometry` \| `letter`… | Setting: page size/offset for images read after it (`magick -list Pagesize`). |
| `-gravity` | `direction` | Anchor for extent/splice/annotate/composite/crop. `magick -list Gravity` → None Center East Forget NorthEast North NorthWest SouthEast South SouthWest West. |
| `-region` | `geometry` / `+region` | Confine following operators to a rectangle; `+region` releases it. |
| `-roll` | `{+-}X{+-}Y` | Cyclically shift pixels, no size change. |

### The virtual-canvas trap

`-crop` and `-trim` **do not clear the page geometry**. Verified: `magick g.png -crop 50x50+10+10 …` yields `w=50 h=50 page=200x100 X=+10 Y=+10`; after `+repage`, `page=0x0`. Consequences: GIF/PNG writers re-emit the original canvas size, `-append`/`-flatten`/montage misplace the tile, and `identify` shows a mismatched `%g`.
**Always write `-crop … +repage` and `-trim +repage`** unless you deliberately need the offset (e.g. rebuilding an animation).

---

## 4. Rotation, orientation, flipping

| Option | Syntax | What it does |
|---|---|---|
| `-rotate` | `degrees{>}{<}` | Rotate CW, expanding canvas, filling with `-background`. `90>` rotates **only if width > height** (200x100 → 100x200); `90<` only if width < height (200x100 → unchanged). |
| `-flip` | — | Mirror vertically (top↔bottom). |
| `-flop` | — | Mirror horizontally (left↔right). |
| `-transpose` | — | Flip about the top-left→bottom-right diagonal (= flip + rotate 90). |
| `-transverse` | — | Flip about the other diagonal (= flop + rotate 90). |
| `-auto-orient` | — | Rotate/flip pixels per the EXIF orientation tag and reset it to TopLeft. |
| `-orient` | `type` | Set the orientation **metadata only**, no pixel change. `magick -list Orientation` → TopLeft TopRight BottomRight BottomLeft LeftTop RightTop RightBottom LeftBottom. |
| `-deskew` | `threshold{%}` | Straighten scanned text (e.g. `-deskew 40%`); add `-define deskew:auto-crop=<px>` to trim. |
| `-shear` | `Xdeg{xYdeg}` | Skew along axes. |
| `-distort SRT` | see §8 | Arbitrary scale/rotate/translate about a chosen origin, no canvas growth. |

Canonical fix for phone photos: `magick in.jpg -auto-orient -strip out.jpg`.

---

## 5. Color

| Intent | Option | Syntax |
|---|---|---|
| Change working colorspace | `-colorspace` | `sRGB\|RGB\|Gray\|LinearGray\|CMYK\|Lab\|LCH\|HSL\|HSB\|HCL\|OHTA\|YCbCr\|XYZ\|Oklab\|…` (`-list Colorspace`, 40 values) |
| Force image class/type | `-type` | `Bilevel Grayscale GrayscaleAlpha Palette PaletteAlpha TrueColor TrueColorAlpha ColorSeparation Optimize` |
| Bits per channel | `-depth` | `1\|8\|16\|32` |
| Grayscale by a chosen luma | `-grayscale` | `Rec709Luminance` etc. (`-list PixelIntensity`: Average Brightness Lightness Mean MS Rec601Luma Rec601Luminance Rec709Luma Rec709Luminance RMS) |
| Auto contrast | `-normalize` / `-auto-level` / `-contrast-stretch b{xw}{%}` / `-linear-stretch` | `-contrast-stretch 2%x1%` |
| Auto gamma | `-auto-gamma` | — |
| Manual gamma | `-gamma` | `value` (e.g. `2.2`); `+gamma v` sets the metadata only |
| Levels | `-level` / `+level` | `black{xwhite}{+gamma}{%}` e.g. `-level 10%,90%`; `+level` is the inverse |
| Map endpoints to colors | `-level-colors` | `src_color,dst_color` e.g. `-level-colors black,white` |
| HSB tweak | `-modulate` | `brightness{,saturation{,hue}}` — 100 = unchanged, e.g. `110,120,100` |
| Brightness/contrast | `-brightness-contrast` | `b{xc}{%}`, each −100…100 |
| Perceptual contrast | `-sigmoidal-contrast` / `+sigmoidal-contrast` | `contrast{xmidpoint{%}}` e.g. `3x50%`; `+` form decreases |
| Invert | `-negate` / `+negate` | `+negate` inverts grayscale only |
| Histogram equalize | `-equalize` | — |
| Tint with fill color | `-colorize` / `-tint` | `percent` or `r,g,b` percentages |
| Split/merge channels | `-separate` / `-combine` | `magick in.png -separate ch_%d.png`; `magick r.png g.png b.png -combine out.png` |
| Restrict following ops | `-channel` / `+channel` | `R,G,B,A,RGB,RGBA,CMYK,Alpha,All,Sync…` (`-list Channel`); `+channel` resets to default |
| Rearrange channels | `-channel-fx` | `"red=>green"`, `"red;green;blue"` |
| Per-pixel expression | `-fx` | `-fx "1-u"`, `-fx "(u.r+u.g+u.b)/3"` |
| Color matrix | `-color-matrix` | `"1 0 0, 0 1 0, 0 0 1"` (5x5 for RGBA, 6x6 for CMYKA). **`-recolor` is removed — use this.** |
| 1-D / 3-D LUT | `-clut` / `-hald-clut` | `magick img.png lut.png -clut out.png` |
| ICC profile | `-profile` / `+profile` | `-profile sRGB.icc`; `+profile "icc"` strips one; combine with `-intent Perceptual\|Relative\|Saturation\|Absolute` and `-black-point-compensation` |
| Drop all metadata | `-strip` | — |
| Palette reduction | `-colors` + `-quantize` + `-dither` | `-quantize YUV -colors 8 -dither FloydSteinberg` (`-list Dither` → None FloydSteinberg Riemersma; `+dither` disables) |
| Match a fixed palette | `-remap` | `magick in.png -remap palette.png out.png` (`-map` is removed) |
| Recolor / erase a color | `-opaque` / `+opaque` / `-transparent` / `+transparent` | `-fuzz 20% -fill white -opaque red`; `+opaque` recolors everything *not* matching |
| Tolerance for all color matching | `-fuzz` | `distance{%}` — affects `-trim`, `-opaque`, `-transparent`, `-floodfill` |
| Background fill color | `-background` | `-background none\|white\|"#RRGGBB"\|"rgba(…)"` |

### `-alpha <verb>` (all 16 verified)

`Activate/On` enable alpha · `Deactivate/Off` ignore alpha (data kept) · `Set` enable + make fully opaque where undefined · `Opaque` force alpha=opaque · `Transparent` force alpha=transparent (color kept) · `Extract` replace image with the alpha channel as grayscale · `Copy` copy the intensity into alpha · `Shape` like Copy but zeroes the color · `Remove` composite over `-background`, discard alpha · `Background` set transparent pixels' color to `-background` · `Associate`/`Disassociate` premultiply / un-premultiply · `Discrete` treat alpha as an independent channel · `OffIfOpaque` drop a fully-opaque alpha channel.

### Flatten vs mosaic vs layers (verified with a 100x100 base + a 60x60 at `-page +80+80`)

| Option | Result | Rule |
|---|---|---|
| `-flatten` | 100x100 | Canvas = **first image's** page; anything outside is clipped. |
| `-mosaic` | 180x180 | Canvas **grows** to the bounding box of all pages; background filled. |
| `-layers merge` | 100x100 image with `page=180x180` | Like mosaic but keeps the page offset instead of expanding pixels. |
| `-layers flatten` | same as `-flatten` | Alias in the layers family. |

---

## 6. Composition & layering

```
magick base.png overlay.png -gravity center -compose Over -composite out.png
magick composite -gravity center -compose Multiply overlay.png base.png out.png   # note: src dst order
magick base.png overlay.png -geometry +10+20 -compose Over -composite out.png
```

| Option | Syntax | Role |
|---|---|---|
| `-composite` | — | Composite the last two (or three: src, dst, mask) images in the list. |
| `-compose` | `operator` | Setting: which blend math `-composite`, `-layers composite`, `-draw image`, `-flatten`, montage use. |
| `-geometry` | `{+-}X{+-}Y` (+ optional `WxH`) | Offset (and optional resize) of the overlay. |
| `-gravity` | `direction` | Anchor for the overlay; combines with `-geometry`. |
| `-tile` / `+tile` | filename or `WxH` | Use an image as a repeating fill; `-draw`/montage use it too. |
| `-draw "image OP X,Y W,H file"` | see §7 | Composite inside a draw sequence. |
| `-flatten` / `-mosaic` | — | See §5 table. |
| `-append` / `+append` | — | Stack **vertically** (60x60+60x60 → 60x120) / **horizontally** (→ 120x60). |
| `-smush` / `+smush` | `offset` | Like append but with a gap: `-smush 10` → 60x130; `+smush 10` → 130x60. Negative offsets overlap. |
| `-layers` | `verb` | Multi-image operations, below. |

**Compose operators** (`magick -list Compose`, 60+; every name below accepted locally):

| Operator | Effect |
|---|---|
| `Over` (default) / `SrcOver` | Normal alpha blend: src on top of dst. |
| `Multiply` | Darkens: `s*d`. Shadows, ink. |
| `Screen` | Lightens: inverse-multiply. Glows. |
| `Overlay` / `HardLight` / `SoftLight` / `PinLight` / `LinearLight` / `VividLight` | Contrast blends (multiply where dark, screen where light). |
| `Darken` / `Lighten` | Per-channel min / max. |
| `DarkenIntensity` / `LightenIntensity` | Pick the whole pixel with lower/higher intensity. |
| `Difference` / `Exclusion` | `|s−d|` — the visual-diff workhorse. |
| `DstOver` | Put src *under* dst. |
| `SrcIn` / `In` | Keep src only where dst is opaque (cookie-cut). |
| `SrcOut` / `Out` | Keep src only where dst is transparent. |
| `DstIn` | Keep dst only where src is opaque → **the standard "apply a mask"**. |
| `DstOut` | Keep dst only where src is transparent → punch a hole. |
| `Atop` / `DstAtop` | src over dst, clipped to dst's shape (and the mirror). |
| `CopyAlpha` (`CopyOpacity` accepted as alias) | Copy src intensity/alpha into dst's alpha channel. |
| `Copy`, `CopyRed/Green/Blue/Black/Cyan/Magenta/Yellow` | Overwrite the whole image / one channel. |
| `Blend` | Weighted average; `-define compose:args=SRC_PCT,DST_PCT`. |
| `Dissolve` | Blend using src alpha; `-define compose:args=SRC{,DST}`. |
| `Modulate` | Adjust dst brightness/saturation by src; `compose:args=B,S`. |
| `ChangeMask` | Make dst pixels transparent where they equal src — used by GIF optimizers. |
| `Mathematics` | `compose:args=A,B,C,D` → `A*s*d + B*s + C*d + D`. |
| `Plus` / `MinusSrc` / `MinusDst` / `DivideSrc` / `DivideDst` / `ModulusAdd` / `ModulusSubtract` | Arithmetic. |
| `Hue`, `Saturate`, `Luminize`, `Colorize` | HSL channel transplants. |
| `Displace`, `Distort`, `Bumpmap`, `Blur`, `Threshold`, `Freeze`, `Negate`, `Xor`, `Clear`, `None` | Specialty. |

Useful modifiers: `-define compose:args=…`, `-define compose:clip-to-self=false` (let the src draw outside dst bounds), `-define compose:clamp=off`.

**`-layers <verb>`** (`magick -list Layers`; all verified against a 3-frame GIF):

| Verb | Does |
|---|---|
| `Coalesce` | Rebuild every frame as a full, standalone image (undo GIF optimization). **Do this before editing any animation.** |
| `Optimize` | `OptimizeFrame` + `OptimizeTransparency` — the normal re-optimize step after editing. |
| `OptimizeFrame` | Crop each frame to its changed region and set page offsets. |
| `OptimizePlus` | Like Optimize but may insert extra zero-delay frames for a smaller file. |
| `OptimizeTransparency` | Replace unchanged pixels with transparency. |
| `Dispose` | Show what each frame looks like after its GIF dispose method is applied. |
| `Flatten` | Merge all layers onto the first image's canvas. |
| `Merge` | Merge onto a canvas covering all pages (keeps the page offset). |
| `Mosaic` | Merge and expand the canvas to the bounding box. |
| `Composite` | Composite one image list over another; the two lists are separated by `null:`. |
| `RemoveDups` | Delete frames identical to the previous one (delays are merged). |
| `RemoveZero` | Delete zero-delay frames. |
| `TrimBounds` | Set every frame's page to the common bounding box without changing pixels. |
| `CompareAny` / `CompareClear` / `CompareOverlay` | Difference-region analysis. `-deconstruct` is removed → use `-layers CompareAny`. |

**montage** essentials: `-tile COLSxROWS` · `-geometry WxH{+-}X{+-}Y` (tile size + padding) · `-label '%f'` · `-title 'text'` · `-background color` · `-frame geom` · `-shadow` · `-mode Concatenate|Frame|Unframe` (`-list Mode`) · `-pointsize`/`-font` for labels. `-mode Concatenate` gives a zero-gap grid.

---

## 7. Text & drawing

| Option | Syntax | Notes |
|---|---|---|
| `-annotate` | `{+-}X{+-}Y text` or `DEG {+-}X{+-}Y text` or `XDEGxYDEG{+-}X{+-}Y text` | Draws text. With `-gravity` set, X/Y become offsets *from that anchor* (`-gravity center -annotate 0x0+0+0 "Hi"`). `XDEGxYDEG` shears/rotates: `-annotate 15x15+20+60 "Rot"`. Without gravity, `+X+Y` is the text **baseline** origin, not the top-left. |
| `-draw` | `'primitive args …'` | Full MVG vector language, below. |
| `-font` | font name or file | `-font Helvetica`, `-font Helvetica-Bold`, `-font /path/to.ttf`. `magick -list font` lists 2668 entries here (name, family, style, stretch, weight, glyph file). |
| `-family` / `-weight` / `-style` | `Helvetica` / `Normal Bold Thin Light Medium SemiBold ExtraBold Heavy` or a number / `Any Italic Normal Oblique` | Font selection by attributes. `-list Weight`, `-list Style`. |
| `-stretch` | `Normal Condensed Expanded …` (`-list Stretch`) | **Broken in the native `magick` CLI on this build** (`unrecognized option '-stretch'`); works under `magick convert` / `magick mogrify`. See §13. |
| `-pointsize` | `value` | Font size in points (scaled by `-density` for vector formats). |
| `-fill` / `-stroke` / `-strokewidth` | color / color / number | Glyph interior, outline, outline width. `-stroke none` is the default. |
| `-undercolor` | color | Opaque box painted behind `-annotate` text. |
| `-kerning` | `value` | Extra px between glyphs. |
| `-interline-spacing` | `value` | Extra px between lines. |
| `-interword-spacing` | `value` | Extra px between words. |
| `-direction` | `right-to-left` \| `left-to-right` | Bidi rendering. |
| `-word-break` | `normal` \| `break-word` | Wrapping policy for `caption:`. |
| `-gravity` | direction | Anchors both `-annotate` and `-draw text`. |
| `-antialias` / `+antialias` | — | `+antialias` for crisp pixel text. |

**Text pseudo-images** (each auto-sizes; verified): `label:"text"` → single line sized to the text (`-pointsize 20 label:"LabelText"` → 86x25). `caption:"text"` → word-wrapped into the width given by `-size 150x` (→ 150x40); with `-size WxH` the pointsize auto-fits. `text:file.txt` → renders a text file as pages. `pango:"<markup>"` if the delegate is present.

**Caption bar recipe:** `magick in.png -background '#222' -fill white -pointsize 20 -gravity south -splice 0x40 -annotate +0+8 "My caption" out.png` (splice makes the bar, annotate writes into it).

**`-draw` primitives** (all verified): `point X,Y` · `line X1,Y1 X2,Y2` · `rectangle X1,Y1 X2,Y2` · `roundrectangle X1,Y1 X2,Y2 RW,RH` · `arc X1,Y1 X2,Y2 START,END` · `ellipse CX,CY RX,RY START,END` · `circle CX,CY PX,PY` (second point is *on* the circle) · `polyline X,Y …` · `polygon X,Y …` · `bezier X,Y …` · `path 'M 5,5 L 30,30 Z'` (SVG path syntax) · `text X,Y 'string'` · `image OPERATOR X,Y W,H 'file'` (W,H = 0,0 keeps native size) · `color X,Y method` · `matte X,Y method`.
**Transforms inside `-draw`:** `translate X,Y` · `rotate DEG` · `scale SX,SY` · `skewX DEG` · `skewY DEG` · `affine sx,rx,ry,sy,tx,ty` · `push graphic-context` / `pop graphic-context` to scope them.
**Settings inside `-draw`:** `fill COLOR` · `stroke COLOR` · `stroke-width N` · `stroke-dasharray a,b` · `stroke-linecap butt|round|square` · `stroke-linejoin miter|round|bevel` · `fill-opacity N` · `stroke-opacity N` · `fill-rule evenodd|nonzero` · `font NAME` · `font-size N` · `text-align left|center|right` · `gravity DIR`.

---

## 8. Effects & filters

| Option | Syntax | Effect |
|---|---|---|
| `-blur` | `radiusxsigma` (`0xN` = auto radius) | Gaussian-ish blur, fast. |
| `-gaussian-blur` | `radiusxsigma` | True Gaussian; slower, stronger. |
| `-motion-blur` | `radiusxsigma{+angle}` | Directional streak, e.g. `0x12+45`. |
| `-rotational-blur` | `angle` | Spin blur around the center. **`-radial-blur` does not exist here** — this is its replacement. |
| `-bilateral-blur` | `WxH{+int-sigma}{+space-sigma}` | Edge-preserving smoothing. |
| `-selective-blur` | `radiusxsigma+threshold` | Blur only where local contrast < threshold. |
| `-adaptive-blur` | `radiusxsigma` | Blurs less near edges. |
| `-sharpen` | `radiusxsigma` | Gaussian sharpen. |
| `-unsharp` | `radiusxsigma{+amount}{+threshold}` | Unsharp mask, e.g. `0x1+1+0.05`. Best general sharpener. |
| `-adaptive-sharpen` | `radiusxsigma` | Sharpens more near edges. |
| `-despeckle` | — | Remove speckle while keeping edges. |
| `-statistic` | `type WxH` | `-list Statistic`: Contrast Gradient Maximum Mean Median Minimum Mode NonPeak RootMeanSquare StandardDeviation. **`-median R` and `-mode R` are removed → `-statistic Median 3x3`, `-statistic Mode 3x3`; `-noise R` (the filter) → `-statistic NonPeak R`.** |
| `+noise` | `type` | **Add** noise. `-list Noise`: Gaussian Impulse Laplacian Multiplicative Poisson Random Uniform. Scale with `-attenuate`. |
| `-kuwahara` | `radius` | Edge-preserving painterly smoothing. |
| `-wavelet-denoise` | `threshold{%}` | Wavelet noise removal. |
| `-local-contrast` | `radiusx{strength%}` | Local-contrast / clarity boost. |
| `-clahe` | `WxH{%}+bins+clip` | Contrast-limited adaptive histogram equalization, e.g. `25x25%+128+3`. |
| `-mean-shift` | `WxH+distance{%}` | Colour clustering / cartoon flattening. |
| `-kmeans` | `colors{xiterations}{%}` | K-means colour clustering. |
| `-morphology` | `method kernel` | See below. |
| `-edge` | `radius` | Edge detection. |
| `-canny` | `radiusxsigma{+lower%}{+upper%}` | Multi-stage Canny edge detector, e.g. `0x1+10%+30%`. |
| `-hough-lines` | `WxH{+threshold}` | Line detection, e.g. `9x9+150`. |
| `-connected-components` | `4` \| `8` | Label connected regions; add `-define connected-components:verbose=true`. |
| `-emboss` / `-charcoal` / `-sketch` / `-paint` | `radius` / `factor` / `radiusxangle+amp` / `radius` | Artistic. **`-oil-paint` does not exist — it is `-paint`.** |
| `-swirl` / `-wave` / `-implode` / `-spread` | `deg` / `ampxwavelen` / `amount` / `radius` | Warps. |
| `-vignette` | `radiusxsigma{+x}{+y}` | Soft darkened corners (uses `-background`). |
| `-shadow` | `opacityxsigma{+x}{+y}` | Turn the image into a drop shadow (`60x4+3+3` on 200x100 → 216x116). |
| `-raise` / `+raise` | `WxH` | 3-D raised / sunken bevel. |
| `-polaroid` | `angle` | Polaroid-frame effect (200x100 → 242x148). |
| `-sepia-tone` | `threshold{%}` | Sepia. |
| `-solarize` | `threshold{%}` | Invert above threshold. |
| `-posterize` | `levels` | Reduce levels per channel. |
| `-segment` | `cluster,smooth` | Fuzzy c-means colour segmentation, e.g. `1x1.5`. |
| `-shade` | `azimuthxelevation` | Grayscale relief lighting; `+shade` keeps colour. |
| `-sort-pixels` | — | Pixel-sorting glitch effect. |
| `-white-balance` | — | Auto white point. |
| `-sparse-color` | `method 'x,y color …'` | Gradient from control points. `-list SparseColor`: Barycentric Bilinear Inverse Shepards Voronoi Manhattan. |

**`-morphology METHOD KERNEL`** — `-list Morphology`: Correlate Convolve Dilate Erode Close Open DilateIntensity ErodeIntensity CloseIntensity OpenIntensity (and the `…I` short forms) Smooth EdgeOut EdgeIn Edge TopHat BottomHat Hmt HitNMiss HitAndMiss Thinning Thicken Distance IterativeDistance. **There is no `Gradient` method** (docs list one). Prefix with `N:` to iterate (`-morphology Dilate:3 Disk`).
**Kernels** (`-list Kernel`): Unity Gaussian DoG LoG Blur Comet Binomial Laplacian Sobel FreiChen Roberts Prewitt Compass Kirsch Diamond Square Rectangle Disk Octagon Plus Cross Ring Peaks Edges Corners Diagonals LineEnds LineJunctions Ridges ConvexHull ThinSe Skeleton Chebyshev Manhattan Octagonal Euclidean. Parameterize with `Name:args` (`Gaussian:0x2`, `Square:1`, `Disk:3.5`). Inspect one with `-define showkernel=1`.

**`-distort METHOD 'ARGS'`** — `-list Distort`: Affine RigidAffine AffineProjection ScaleRotateTranslate SRT Perspective PerspectiveProjection BilinearForward BilinearReverse Polynomial Arc Polar DePolar Barrel BarrelInverse Shepards Resize.

> **Critical syntax point (verified):** the whole coordinate list is ONE argument. `-distort Perspective "0,0 0,0 200,0 200,0 0,100 20,100 200,100 180,100"` works; leaving it unquoted so the shell splits it fails with `require at least 1 CPs`.

| Method | Args | Use |
|---|---|---|
| `SRT` | `angle` \| `scale,angle` \| `x,y scale angle` \| `x,y scale angle newx,newy` | Scale-rotate-translate about a chosen origin (rotation without canvas growth). |
| `Perspective` | 4+ pairs `sx,sy dx,dy` | Keystone correction / place an image on a plane. |
| `Affine` | 3 pairs `sx,sy dx,dy` | General affine from control points. |
| `AffineProjection` | `sx,rx,ry,sy,tx,ty` | Affine from a matrix (`-transform` was removed → `+distort AffineProjection`). |
| `Barrel` / `BarrelInverse` | `A,B,C{,D{,cx,cy}}` | Lens distortion correction. |
| `Arc` | `arc_angle{ rotate{ top_radius{ bottom_radius}}}` | Bend the image into an arc/ring. |
| `Polar` / `DePolar` | `0` or `Rmax,Rmin cx,cy sa,ea` | Rectangular ↔ polar (panorama ↔ "little planet"). |
| `Resize` | `geometry` | Resize using the distortion engine (`-filter`-driven, EWA). |
| `Shepards`, `Polynomial`, `BilinearForward/Reverse`, `RigidAffine` | control points | Warping from point pairs. |

Distortion helpers: `-virtual-pixel` (`-list VirtualPixel`: Background Black CheckerTile Dither Edge Gray HorizontalTile HorizontalTileEdge Mirror None Random Tile Transparent VerticalTile VerticalTileEdge White), `+distort` (auto-expand the canvas to fit the result), `-define distort:viewport=WxH+X+Y`, `-define distort:scale=N`.

---

## 9. Format & output control

| Option | Syntax | Meaning |
|---|---|---|
| `-quality` | `0..100` | **JPEG:** 0–100, higher = better/bigger (verified 10→513 B, 50→685 B, 95→2205 B). Default 92. **WEBP:** 0–100 lossy quality (100 ≠ lossless; use `-define webp:lossless=true`). **PNG: the value is `zlib_level*10 + filter_type`, not a quality.** Verified: `-quality 95` and `-quality 90` produce byte-identical 939-byte files (both zlib 9), `-quality 00` → 985 B (special "best guess"), `-quality 10` → 1411 B (zlib 1). Use `-quality 95` (zlib 9 + adaptive filter 5) for photos-as-PNG and `-quality 90` for flat graphics. |
| `-compress` | `type` / `+compress` | `-list Compress`: None RLE/RunlengthEncoded Zip ZipS LZW LZMA Zstd BZip JPEG JPEG2000 LosslessJPEG Lossless WebP Fax Group4 JBIG1 JBIG2 B44 B44A DWAA DWAB Piz Pxr24 DXT1 DXT3 DXT5 BC7 LERC. `+compress` = store uncompressed. |
| `-interlace` | `type` | `-list Interlace`: None Line Plane Partition GIF JPEG PNG. `-interlace Plane` = progressive JPEG (verified: `Interlace: JPEG` in `-verbose`); `-interlace PNG` = Adam7. |
| `-sampling-factor` | `WxH` or `4:2:0` | Chroma subsampling. Verified: `4:2:0` → `jpeg:sampling-factor: 2x2,1x1,1x1`; `4:4:4` → `1x1,1x1,1x1` (no chroma loss, bigger). |
| `-strip` | — | Drop all profiles, comments, EXIF. Big win on small JPEGs. |
| `-density` | `H{xV}` | Setting: resolution for rasterizing vector input (PDF/SVG/PS) — put it **before** the input file. |
| `-units` | `PixelsPerInch` \| `PixelsPerCentimeter` \| `Undefined` | Verified quirk: PNG stores density in pixels/cm, so `-density 300 -units PixelsPerInch out.png` reads back as `118.11 PixelsPerCentimeter` (the same physical DPI). JPEG stores 300 PPI correctly. |
| `-page` | `geometry` \| `A4`/`Letter` | Canvas size/offset for images read after it. |
| `-adjoin` / `+adjoin` | — | `-adjoin` (default) writes one multi-frame file; `+adjoin` forces one file per frame — requires a `%d` in the name: `magick anim.gif +adjoin frame_%d.png`. |
| `-delay` | `ticks{xticks-per-second}` | Frame delay in 1/100 s. |
| `-loop` | `count` | GIF loop count; `0` = forever. |
| `-dispose` | `Undefined\|None\|Background\|Previous` or `0..3` (`-list Dispose`) | GIF frame disposal. |
| `-write` / `+write` | `filename` | Write an intermediate result and keep processing (verified: `-write w1.png -resize 50% w2.png` produced 200x100 and 100x50). `+write` writes without removing the image from the list. |
| `-set` / `+set` | `key value` | Set a property/artifact on images already loaded: `-set comment "x"`, `-set delay 10`, `-set option:foo bar`. `+set key` removes it. |
| `-define` / `+define` | `key=value` | Coder/operator options (below). |
| `-scene` / `-scenes` | `N` / `N-M` | Starting scene number / range for `%d` output naming. |

**Important `-define` keys** (all accepted locally):

| Key | Effect |
|---|---|
| `jpeg:size=WxH` | **Read hint** — decodes the JPEG at the smallest DCT scale ≥ WxH. Verified: 4000x3000 → 200x200 took 0.38 s plain, **0.05 s** with `-define jpeg:size=400x300`. |
| `jpeg:extent=250kb` | Auto-tune quality to hit a target file size. |
| `png:color-type=0\|2\|3\|4\|6` | Force gray / RGB / palette / gray+α / RGBA. |
| `png:compression-level=0..9`, `png:compression-filter=0..5`, `png:compression-strategy` | Explicit PNG encoder control (clearer than `-quality`). |
| `png:bit-depth=1\|2\|4\|8\|16` | Force PNG bit depth. |
| `webp:lossless=true`, `webp:method=0..6`, `webp:alpha-quality=0..100`, `webp:exact=true` | WebP encoder. Higher `method` = slower/smaller. |
| `heic:speed=…`, `heic:preserve-orientation=true` | HEIC/AVIF encoder. |
| `tiff:rows-per-strip=N`, `tiff:tile-geometry=WxH`, `tiff:alpha=unassociated` | TIFF layout. |
| `pdf:use-cropbox=true`, `pdf:fit-page=WxH` | Use the PDF CropBox (not MediaBox) when rasterizing. |
| `showkernel=1` | Print the resolved `-morphology` kernel to stderr. |
| `registry:temporary-path=/path` | Where the pixel cache spills to disk. |
| `connected-components:verbose=true`, `deskew:auto-crop=N`, `distort:viewport=…`, `compose:args=…`, `compose:clip-to-self=false` | Operator tuning. |

---

## 10. Animation & multi-frame

**The workflow: `-coalesce` → edit → `-layers optimize`.** An optimized GIF's frames are partial tiles with page offsets; editing them directly corrupts the animation.

```
magick in.gif -coalesce -resize 50% -layers optimize -loop 0 out.gif
magick in.gif -coalesce -set delay 10 -layers OptimizePlus -loop 0 out.gif
```

| Task | Command |
|---|---|
| Build from stills | `magick -delay 20 -loop 0 f*.png out.gif` |
| Extract every frame | `magick anim.gif -coalesce +adjoin frame_%d.png` (verified: produced `frame_0/1/2.png`) |
| Extract one frame | `magick 'anim.gif[2]' f2.png` |
| Frame count / delays | `magick identify -format "%s %wx%h %T\n" anim.gif` |
| Reverse | `magick anim.gif -coalesce -reverse out.gif` |
| Tween between frames | `magick a.png b.png -morph 10 out.gif` |
| Change speed | `magick anim.gif -coalesce -set delay 5 -layers optimize out.gif` |
| APNG | `magick anim.gif -coalesce apng:out.apng` (verified) |
| Animated WebP | `magick anim.gif -coalesce out.webp` (verified: 3 frames) |
| Diff-region analysis | `magick anim.gif -layers CompareAny out.gif` (replaces `-deconstruct`) |
| Video | `magick in.mp4 f_%03d.png` / `magick f_*.png out.mp4` — routed through the **ffmpeg delegate** (`magick -list delegate | grep ffmpeg`); requires `ffmpeg` on `$PATH`. For real encoding control, call `ffmpeg` directly. |

> **`-delay` placement gotcha (verified).** `-delay` is a *setting*: `magick anim.gif -delay 10 out.gif` leaves the delay at the original 20; `magick -delay 10 anim.gif out.gif` gives 10; and to change already-loaded frames use `-set delay 10`. The same rule applies to `-dispose`.
>
> **`-loop` is the exception** — it is written to the output container, so **either position works** (verified: `-loop 3` before *and* after the input both yield `Iterations: 3`).

---

## 11. Comparison & analysis

```
magick compare -metric RMSE a.png b.png diff.png      # metric goes to STDERR
magick compare -metric AE -fuzz 2% a.png b.png null:  # count differing pixels only
```

`-list Metric` → **AE DSSIM Fuzz MAE MEPP MSE NCC PAE PHASH PSNR RMSE SSIM**. Real output for a 200x100 image vs. its `-blur 0x2` version:

| Metric | Value | Reading |
|---|---|---|
| `AE` | `2400` | Absolute count of differing pixels (integer). Use with `-fuzz`. |
| `MAE` | `12.4533 (0.000190026)` | Mean absolute error, quantum (normalized). |
| `MSE` | `0.0714004 (1.0895e-06)` | Mean squared error. |
| `RMSE` | `68.4049 (0.00104379)` | Root MSE — the general-purpose "how different" number. |
| `PAE` | `522 (0.00796521)` | Peak (worst single pixel) absolute error. |
| `PSNR` | `59.6277` | dB; **higher is better**, `inf` = identical, >40 ≈ visually identical. |
| `SSIM` | `0.998505` | Structural similarity, 1.0 = identical. |
| `DSSIM` | `0.000747685` | `(1−SSIM)/2`-style distance, 0 = identical. |
| `NCC` | `0.666661` | Normalized cross-correlation, 1.0 = identical. |
| `PHASH` | `4.58096e-06` | Perceptual hash distance — robust to resize/format; best for "is this the same picture?". |
| `FUZZ` | `68.4049 (0.00104379)` | RMSE that respects `-fuzz`. |
| `MEPP` | `747200 (1.0895e-06, 0.00796521)` | Mean error per pixel: total, normalized MSE, normalized PAE. |

| Option | Syntax | Notes |
|---|---|---|
| `-subimage-search` / `+subimage-search` | — | Locate a small image inside a larger one. Verified: it writes **two numbered outputs** (`diff-0.png` = best-match difference, `diff-1.png` = similarity heat map) and prints `score @ x,y`. O(n·m) — crop the search area first. |
| `-similarity-threshold` | `value` | Stop the subimage search once similarity is this good. |
| `-dissimilarity-threshold` | `value` | Max RMSE before `compare` aborts with `images too dissimilar`. Raise it (e.g. `-dissimilarity-threshold 1.0`) if the search errors out. |
| `-highlight-color` / `-lowlight-color` | color | Colors of the difference map. |
| `-metric` | type | As above; result on stderr. |
| `-identify` | — | In `magick`/`stream`, print the identify line mid-pipeline. |
| `-moments` / `+moments` | — | Report image moments / perceptual hash channels. |
| `-features` | `distance` | Haralick texture features. |
| `-format "%[mean]"` etc. | — | See §2 statistics. Combine with `-colorspace Gray` for a single luma number. |

---

## 12. Performance & limits

`magick -list resource` on this machine: `Width/Height 36.0288PP · Area 137.439GP · List length unlimited · Memory 32GiB · Map 64GiB · Disk unlimited · File 786432 · Thread 11 · Throttle 0 · Time unlimited`.

| Control | Syntax | Notes |
|---|---|---|
| `-limit` | `-limit memory 256MB -limit map 512MB -limit disk 1GB -limit area 100MB -limit thread 2 -limit time 30` | Resources: `memory map disk area file thread throttle time width height list-length`. Must appear **before** the input. Exceeding `memory`→`map`→`disk` degrades gracefully; exceeding `disk` errors. |
| `MAGICK_*` env vars | `MAGICK_THREAD_LIMIT`, `MAGICK_MEMORY_LIMIT`, `MAGICK_MAP_LIMIT`, `MAGICK_DISK_LIMIT`, `MAGICK_AREA_LIMIT`, `MAGICK_TIME_LIMIT`, `MAGICK_TEMPORARY_PATH`, `MAGICK_HOME`, `MAGICK_CONFIGURE_PATH` | Verified: `MAGICK_THREAD_LIMIT=2 magick -list resource` reports `Thread: 2`. Same effect as `-limit`, but applies to every invocation. |
| Temp spill location | `-define registry:temporary-path=/fast/ssd/tmp` or `MAGICK_TEMPORARY_PATH` | Keeps the pixel cache off a slow/full volume. |
| Threads | OpenMP 5.0 is compiled in; `-limit thread N` or `OMP_NUM_THREADS`. | Single-threading (`-limit thread 1`) is often **faster** for many small images, and it lets you parallelize with `xargs -P` instead. |
| `-bench` | `-bench 10 in.png -resize 50% null:` | Repeats the command N times and reports iterations/sec and elapsed time. |
| Policy | `magick -list policy` | `/opt/homebrew/Cellar/imagemagick/7.1.1-34/etc/ImageMagick-7/policy.xml` — no restrictive rules on this install (all `rights: None`, Undefined domain). |
| MPC / MIFF cache | `magick big.jpg big.mpc` then reuse `big.mpc` | MPC is a raw memory-mappable dump (`big.mpc` header + `big.cache` pixels — 240 KB for a 200x100 Q16 image). Near-zero decode cost when the same source is processed many times; **not portable** across machines/versions. MIFF is the portable, compressible sibling. |

**Speed recipes (measured on a 4000x3000 JPEG → 200x200):**

| Command | Time |
|---|---|
| `magick big.jpg -resize 200x200 out.jpg` | 0.38 s |
| `magick big.jpg -thumbnail 200x200 out.jpg` | **0.08 s** |
| `magick -define jpeg:size=400x300 big.jpg -resize 200x200 out.jpg` | **0.05 s** |

`-thumbnail` beats `-resize` because it samples down to ~5x the target before filtering **and** strips metadata (output was 13017 B vs 13074 B for `-resize`, with equal visual quality at thumbnail sizes). `jpeg:size` is even better: it never fully decodes the JPEG. Combine both for batch pipelines, and use `-ping` whenever you only need dimensions.

---

## 13. Docs-vs-binary discrepancies (trust the binary)

**Documented online but MISSING from `magick` 7.1.1-34 (hard error `unrecognized option`):**

| Option | Status / replacement |
|---|---|
| `-radial-blur` | Gone. Use `-rotational-blur angle`. |
| `-perceptible` | Not present in this build at all. |
| `-oil-paint` | Never existed as spelled; the option is `-paint radius`. |
| `-respect-parentheses` | The `magick` CLI only accepts the **singular** `-respect-parenthesis`. (The plural *does* work in `magick stream`.) |
| `-storage-type` | Not in the `magick` CLI; only in `magick stream`. |
| `-map` (as `stream -map rgb`) | Exists in `stream`, but as a `magick` operator it is replaced by `-remap`. |
| `-morphology Gradient` | Not a valid method here. `-list Morphology` offers `Edge`, `EdgeIn`, `EdgeOut`. |
| `-stretch` | Listed by `-list Command` and `-list Stretch` works, but the native `magick` CLI rejects it (`unrecognized option '-stretch' … CLISimpleOperatorImage/3529`). **Works under `magick convert` / `magick mogrify`.** Looks like an IM 7.1.1-34 bug. |

**Present but deprecated — emit a warning and are auto-translated:**
`-deconstruct` → `-layers CompareAny` · `-recolor` → `-color-matrix` · `-map` → `-remap` · `-median R` → `-statistic Median` · `-mode R` → `-statistic Mode` · `-transform` → `+distort AffineProjection` · `-noise R` (filter form) → `-statistic NonPeak` · `-cache` → `-limit` · `convert` → `magick`.

**Wrong descriptions on imagemagick.org:**
- `-scale` is documented as "ignoring aspect ratio". **It preserves aspect ratio** (200x100 `-scale 50x50` → 50x25, identical to `-resize`). Only `!` forces exact dimensions.
- `-quality` for PNG is documented as "0–9 compression level". It is actually **`zlib_level*10 + filter_type`** (0–100); verified that 90 and 95 both map to zlib 9 and that 10 (zlib 1) produces a *larger* file than 95.
- The docs' `-layers` verb list omits `OptimizeFrame`, `OptimizePlus`, `OptimizeTransparency`, `TrimBounds`, `CompareClear`, `CompareOverlay`, all of which exist locally.
- `display`, `animate`, and `import` are documented as working tools; on this Homebrew build they exist but abort with *"delegate library support not built-in"* (no X11).
