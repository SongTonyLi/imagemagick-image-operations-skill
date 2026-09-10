# Natural-language recipes (intent → verified command)

Every command here was executed against ImageMagick 7.1.1-34 Q16-HDRI and its result checked. Replace `in.*`/`out.*` with real paths. `$MAGICK` is written as `magick` throughout.

Quote every geometry string: `!`, `^`, `>`, `<`, `@`, `%` are all shell metacharacters.

---

## Inspect

### "What is this image?"
```bash
magick identify -format '%f %m %wx%h %[colorspace] alpha=%A opaque=%[opaque] depth=%z frames=%n\n' -- in.png
```
Notes: `%m` is the coder detected from **content**, so this answers "what is it really" regardless of the extension. `%A` says an alpha channel exists; `%[opaque]` says whether any pixel actually uses it.

### "List every image in this folder as a table"
```bash
magick identify -format '%f %m %wx%h %[colorspace] %b\n' -- ./*.jpg ./*.png | column -t
```
Notes: `\t` is **not** interpreted inside `-format` — it emits a literal `t` (`a.pngtPNGt300x300`). Use spaces plus `column -t`, or a real tab via `$'...'`. Prints **one line per frame**, so multi-page files contribute several rows.

### "Which image in this folder is the biggest?"
```bash
magick identify -precision 9 -format '%[fx:w*h] %f\n' -- ./*.jpg ./*.png | sort -rn | head -1
```
Notes: `-precision 9` is required — otherwise `%[fx:]` prints `1.92e+06` above 1e6 and `sort -n` mis-orders it. Use `%B` for largest *file* rather than largest pixel count.

### "Put the width and height into shell variables"
```bash
read W H <<< "$(magick identify -format '%w %h' -- in.png)"
```
Notes: verified in bash and zsh. `eval "$(magick identify -format 'W=%w; H=%h' -- in.png)"` sets several at once.

### "Get the dimensions of thousands of files quickly"
```bash
magick identify -ping -format '%f %wx%h\n' -- ./*.jpg
```
Notes: `-ping` reads the header only and skips pixel decoding. `%[mean]` and other pixel statistics are unavailable under `-ping`.

### "How many frames are in this GIF, and how big is each one?"
```bash
magick identify -format 'scene=%s canvas=%g frame=%wx%h delay=%Tcs\n' -- anim.gif
```
Notes: `%n` under a frame selector reports the **selection** size — `anim.gif[0]` gives `1`, not the file's frame count. Optimized GIFs have frames smaller than the canvas; only `%g` shows it. There is no valid `%[dispose]`/`%[disposal]` property (both warn and return empty at exit 0) — read disposal from `-verbose`.

### "What camera took this photo and when?"
```bash
magick identify -format '%[EXIF:Make] %[EXIF:Model] %[EXIF:DateTimeOriginal]\n' -- photo.jpg
magick identify -format '%[exif:*]' -- photo.jpg          # everything
```
Notes: an absent tag warns and returns empty **at exit 0**. Check for an empty value rather than trusting the status.

### "What is the average brightness?"
```bash
magick in.png -format 'quantum=%[mean] normalized=%[fx:mean]\n' info:
```
Notes: `%[mean]` is in quantum units (0–65535 on Q16); `%[fx:mean]` is normalized 0–1. Do not mix the two scales.

### "Dump everything as JSON"
```bash
magick in.png json:
```

### "Is this image blank?"
```bash
magick in.png -format '%[fx:standard_deviation]\n' info:
```
Notes: `0` means every pixel is identical. A legitimately flat image (a trimmed solid, a swatch, a mask) also reads `0`.

### "Where was this photo taken?"
```bash
magick identify -format '%[EXIF:GPSLatitude] %[EXIF:GPSLatitudeRef] / %[EXIF:GPSLongitude] %[EXIF:GPSLongitudeRef]\n' -- photo.jpg
```
Notes: returns DMS rationals (`40/1,44/1,5436/100 N`). Decimal = `d + m/60 + s/3600`, negated for `S`/`W`. EXIF rationals are never pre-divided — `%[EXIF:FNumber]` is `56/10`, not `5.6`.

### "Is this photo going to show up sideways?"
```bash
magick identify -format '%f %wx%h orientation=%[orientation] exif=%[EXIF:Orientation]\n' -- photo.jpg
```
Notes: `RightTop` == EXIF `6` == needs a 90° CW rotation to display upright. `identify` reports **stored** pixel dimensions, so a 600x400 file with orientation 6 actually displays as 400x600.

### "Is this actually greyscale, or just a grey-looking colour image?"
```bash
magick in.jpg -colorspace HSL -channel g -separate +channel -format 'maxSat=%[fx:maxima]\n' info:
```
Notes: authoritative — a truly neutral image gives `0` (verified), any colour gives `> 0`. `%[type]`/`%[colorspace]` only report how the file is *stored*, which is a different question.

### "What's the average colour?"
```bash
magick in.jpg -scale 1x1\! -format '%[pixel:u] #%[hex:u]\n' info:
```
Notes: use `-scale`, **not** `-resize`. `-scale` is a plain box average and matches `%[fx:mean.r]` exactly (verified `#536154`); `-resize 1x1!` applies a windowed filter and gave a different answer (`#525D52`). `%[hex:mean]` is not a valid substitute — it returned `#005858`.

---

## Convert and compress

### "Convert these PNGs to JPEG"
```bash
magick in.png -quality 90 JPG:out.jpg
```
Notes: the explicit `JPG:` prefix makes an unresolvable coder fail loudly instead of silently writing PNG bytes into `out.jpg`. Confirm with `identify -format '%m'`.

### "Make this photo much smaller without it looking obviously worse"
```bash
magick in.jpg -auto-orient -resize '2000x2000>' -strip -interlace Plane \
  -sampling-factor 4:2:0 -quality 82 JPG:out.jpg
```
Notes: `-strip` also drops the ICC profile — colors can shift.

### "Shrink it but don't let the colours shift"
```bash
magick in.jpg -auto-orient -resize '2000x2000>' +profile '!icc,*' \
  -sampling-factor 4:2:0 -quality 82 JPG:out.jpg
```
Notes: `+profile '!icc,*'` drops every profile **except** ICC — most of `-strip`'s size saving while keeping color management. This matters for wide-gamut sources: a Display P3 photo stripped of its profile is reinterpreted as sRGB and visibly desaturates. Check what a file carries with `identify -format '%[profiles]'`.

### "Get this JPEG under 200 kilobytes"
```bash
magick in.jpg -define jpeg:extent=200kb JPG:out.jpg
```
Notes: ImageMagick binary-searches the quality to hit the budget. Verify with `ls -l`; the result is approximate and can land slightly over.

### "Convert to WebP, lossless"
```bash
magick in.png -define webp:lossless=true WEBP:out.webp
```

### "Shrink this PNG by cutting it to 64 colours"
```bash
magick in.png -colors 64 PNG8:out.png
```
Notes: quantization is irreversible. `PNG8:` forces a palette; `PNG32:` forces 8-bit RGBA and will **silently downconvert a 16-bit source** — use plain `PNG:` to preserve depth.

### "Save this as a progressive JPEG for the web"
```bash
magick in.jpg -interlace Plane -quality 85 JPG:out.jpg
```

### "Combine these scans into a single PDF"
```bash
magick -density 150 -units PixelsPerInch page1.png page2.png PDF:out.pdf
```
Notes: needs a working PDF coder and Ghostscript. Set `-density` **before** the inputs.

### "Turn page 1 of this PDF into a print-quality PNG"
```bash
magick -density 300 -units PixelsPerInch 'in.pdf[0]' \
  -background white -alpha remove -alpha off -units PixelsPerInch PNG:out.png
```
Notes: `-density` must precede the input or the page rasterizes at 72 dpi and `-density` only edits metadata. Frame selector goes on the **input**. Add `-define pdf:use-cropbox=true` to honor the crop box.

`-units PixelsPerInch` matters for anything called "print quality": without it the PNG's `pHYs` chunk is written with `units=0` (`identify` reports `units=Undefined`), so the 300 is stored as a bare aspect ratio and print pipelines fall back to 72 dpi. Verify with:
```bash
magick identify -format '%wx%h units=%U density=%x\n' out.png
```

### "Convert this HEIC from my phone to a JPEG"
```bash
magick -list format | grep -i heic || echo 'no HEIC coder — use the fallback'
magick photo.heic -quality 90 JPG:out.jpg     # only if the grep above printed something
sips -s format jpeg photo.heic --out out.jpg  # macOS fallback, verified working
```
Notes: **on this machine there is no HEIC coder** — `heic.so` ships but is linked against an older libheif and fails to load, so `magick` dies with `no decode delegate for this image format 'HEIC'`. Same story for AVIF/JXL. Always run the `-list format` check first; `brew reinstall imagemagick` fixes it. Related trap: `magick in.jpg out.heic` writes a **JPEG** named `.heic` at exit 0 — always name the coder (`HEIC:out.heic`) so it fails loudly.

### "Convert this PNG to WebP"
```bash
magick in.png -quality 80 WEBP:out.webp
```
Notes: verified 87 KB PNG → 27 KB at q80, 74 KB lossless. WebP keeps alpha either way.

### "Convert this JPEG to PNG"
```bash
magick in.jpg PNG:out.png
```
Notes: always grows the file (74 KB → 271 KB verified) — JPEG artifacts become lossless data. Only worth it when you need alpha or further lossless editing.

### "Convert the whole folder to JPEG"
```bash
mkdir -p out && magick mogrify -path out -format jpg -quality 85 photos/*.png photos/*.jpg
```
Notes: `-path` writes elsewhere; without it `mogrify` overwrites the originals in place. `-format` sets the new extension.

### "Convert it but keep the EXIF" / "…and strip it"
```bash
magick photo.jpg -resize 50% JPG:out.jpg           # profiles are copied by default
magick photo.jpg -strip JPG:out.jpg                # removes EXIF, IPTC, ICC, comments
magick photo.jpg -thumbnail 200x JPG:out.jpg       # -thumbnail resizes AND strips
```
Notes: verified — the plain resize still reports `Canon EOS 5D Mark IV`, `-strip` reports nothing, `-thumbnail` strips too. Caveat: after a resize the retained `exif:PixelXDimension` is **stale** (still the old size), so never use EXIF as a dimensions check.

### "Render this SVG at 800 pixels wide with a transparent background"
```bash
magick -background none -density 300 in.svg -resize 800x PNG:out.png
```
Notes: SVG is rendered by whichever delegate is configured. Check `-list delegate` — the built-in MSVG renderer is much lower quality than librsvg or Inkscape. For fidelity, call `rsvg-convert -w 800 in.svg -o out.png` directly.

---

## Resize and crop

### "Make this fit inside 800×600 without stretching"
```bash
magick in.jpg -resize '800x600' out.jpg
```

### "Just make it 800 wide"
```bash
magick in.jpg -resize 800x out.jpg
```

### "Cap these at 1600px but never enlarge the small ones"
```bash
magick in.jpg -resize '1600x1600>' out.jpg
```

### "Force exactly 800×600 even if it distorts"
```bash
magick in.jpg -resize '800x600!' out.jpg
```

### "Shrink to half size"
```bash
magick in.jpg -resize '50%' out.jpg
```

### "Make a 300×300 square thumbnail cropped from the centre"
```bash
magick in.jpg -resize '300x300^' -gravity center -extent 300x300 +repage JPG:out.jpg
```
Notes: `^` covers the box (overflowing), then `-extent` crops to exactly 300×300. This **crops** — only use it when a square is actually wanted. Swap `-resize` for `-thumbnail` for speed, accepting that `-thumbnail` strips all metadata and profiles.

### "Cut out a 400×300 region starting 50 across and 20 down"
```bash
magick in.png -crop 400x300+50+20 +repage out.png
```
Notes: without `+repage` the output keeps a virtual canvas and offset (`page=800x600 +50+20`), and later composites/appends misplace it.

### "Slice this into a grid of 256px tiles"
```bash
magick in.png -crop 256x256 +repage +adjoin 'tile_%d.png'
```
Notes: edge tiles are smaller unless the dimensions divide evenly. `-crop 3x2@` instead splits into exactly 3×2 equal pieces.

### "Get rid of the white border around this scan"
```bash
magick identify -format 'bbox=%@\n' -- in.png        # preview what will be removed
magick in.png -fuzz 2% -trim +repage out.png
```
Notes: `%@` shows the bounding box `-trim` would keep. `-fuzz` tolerates JPEG noise and off-white; without it a near-white border may not trim at all.

### "Pad this out to a 500×500 square on a black background — don't crop it"
```bash
magick in.png -background black -gravity center -extent 500x500 +repage out.png
```
Notes: **an opaque `-background` also flattens the image's existing interior transparency** and drops the alpha channel. To pad while keeping alpha use `-background none`. With no `-background` at all, transparency silently becomes white.

### "Crop it to a centred square"
```bash
magick in.jpg -set option:sq '%[fx:min(w,h)]' -gravity center -crop '%[sq]x%[sq]+0+0' +repage out.jpg
```
Notes: with `-gravity center` the `+0+0` is measured from the centre, not the corner. The `-set option:` escape makes one command work for any input size (verified 800x600 → 600x600).

### "Resize it to roughly a quarter-megapixel, whatever the shape"
```bash
magick in.jpg -resize '250000@' out.jpg
```
Notes: `@` targets total pixel *area* while preserving aspect (verified 1200x1600 → 433x577 = 249,841 px). Useful for equal-cost thumbnails of mixed-orientation sources.

### "Add a 20px white frame"
```bash
magick in.png -bordercolor white -border 20 out.png
```

---

## Rotate and orient

### "Rotate 90 degrees clockwise"
```bash
magick in.png -rotate 90 out.png
```
Notes: `-rotate` is **clockwise**; use `-90` or `270` for counter-clockwise. Dimensions swap either way, so verify direction with a pixel probe, not geometry:
```bash
magick out.png -format 'TL=%[pixel:p{0,0}]\n' info:
```

### "Tilt this 7 degrees and fill the corners with white"
```bash
magick in.png -background white -rotate 7 out.png
```
Notes: `-background` must come **before** `-rotate`. The canvas grows to contain the rotated image.

### "These phone photos show up sideways"
```bash
magick in.jpg -auto-orient -strip JPG:out.jpg
```
Notes: `-auto-orient` applies the EXIF orientation to the pixels and resets the tag. Strip afterwards so no viewer re-applies it.

### "Straighten this crooked scan"
```bash
magick in.png -deskew 40% +repage out.png
```
Notes: works on high-contrast text scans; on photos it often finds nothing.

### "Mirror this left to right"
```bash
magick in.png -flop out.png      # horizontal;  -flip is vertical
```
Notes: fl**o**p = h**o**rizontal is the mnemonic that sticks.

### "Rotate only the landscape photos to portrait"
```bash
magick in.jpg -rotate '90>' out.jpg
```
Notes: `90>` rotates only if width > height, `90<` only if width < height. Verified: 800x600 → 600x800, while a 1200x1600 input was left untouched. Quote it or the shell sees a redirect.

---

## Color and tone

### "Make this black and white"
```bash
magick in.jpg -colorspace Gray out.jpg           # grayscale (keeps tones)
magick in.jpg -colorspace Gray -monochrome out.png   # true 1-bit bilevel
```
Notes: "black and white" is ambiguous. Grayscale preserves legibility and is the safe default for photos and scans; bilevel is what people mean for line art, fax, or OCR prep. Ask if the distinction matters. Verify the color really went away:
```bash
magick out.jpg -colorspace HSL -channel G -separate -format 'sat=%[fx:mean]\n' info:
```

### "This photo looks washed out"
```bash
magick in.jpg -auto-level out.jpg           # per-channel stretch to full range
magick in.jpg -contrast-stretch 1%x1% out.jpg   # ignore 1% outliers at each end
```

### "Brighten the shadows without blowing out the highlights"
```bash
magick in.jpg -gamma 1.6 out.jpg
```
Notes: use `-gamma`, not `-brightness-contrast`. Gamma is monotonic with fixed endpoints, so white stays white and clipping is structurally impossible; `-brightness-contrast 25` pushes highlight pixels to pure white. On an **HDRI** build `%[fx:maxima]` can exceed 1.0 in memory, so it tests "would clip on write", not "is clipped".

### "Boost the colours ~30%"
```bash
magick in.jpg -modulate 100,130,100 out.jpg
```
Notes: arguments are `brightness,saturation,hue`, each as a percentage of the original.

### "Give this an old-fashioned sepia look"
```bash
magick in.jpg -sepia-tone 80% out.jpg
```
Notes: the argument is a solarize-style **threshold**, not an intensity slider. `80%` is the conventional value; much lower values produce a harsh, wrong-looking image. Confirm the hue landed warm (R > G > B).

### "Invert the colours"
```bash
magick in.png -channel RGB -negate out.png
```
Notes: `-channel RGB` matters — IM7's default channel set **includes alpha**, so a bare `-negate` also inverts transparency.

### "Pull out just the red channel"
```bash
magick in.png -channel R -separate out.png
```

### "Change every red pixel to blue, allowing for slight variation"
```bash
magick in.png -fuzz 15% -fill blue -opaque red out.png
```

### "Give this a warm tint" / "wash it toward a colour"
```bash
magick in.jpg -fill '#ffcc66' -tint 40 out.jpg        # luminance-weighted, highlights stay bright
magick in.jpg -fill '#0066cc' -colorize 35 out.jpg    # flat blend, flattens contrast
```
Notes: `-fill` must precede both. `-tint` is the one you want for "warm it up"; `-colorize` for a poster-style flat wash.

### "Make a duotone out of this"
```bash
magick in.jpg -colorspace gray \
  \( -size 1x256 gradient:'#1a1a4d'-'#ffcc99' -rotate 90 \) -clut out.jpg
```
Notes: `-clut` maps luminance through a 256-entry lookup table; the `-rotate 90` turns the vertical ramp into the 256x1 strip `-clut` expects, shadows on the left.

### "Posterize it to a few colour bands"
```bash
magick in.jpg +dither -posterize 4 PNG:out.png
```
Notes: verified 38 colours with `+dither`, 42 with dithering. **Write PNG** — a JPEG round-trip immediately re-introduces thousands of colours (46,617 measured), so the effect looks undone.

### "Swap the red and blue channels"
```bash
magick in.jpg -channel-fx 'red<=>blue' out.png
magick in.jpg -separate -swap 0,2 -combine out.png
```
Notes: both verified identical — `srgb(147,129,171)` → `srgb(171,129,147)`. `magick in.jpg -separate out_%d.png` writes all three channels at once.

### "Convert to CMYK with a proper profile"
```bash
magick in.jpg -profile sRGB.icc -profile CMYK.icc -colorspace CMYK out.tif
```
Notes: a bare `-colorspace CMYK` without profiles does a naive conversion that will not match print.

---

## Transparency

### "Make the white background of this logo transparent"
```bash
magick logo.png -fuzz 10% -transparent white out.png
```
Notes: only removes white **connected to nothing in particular** — every white pixel goes, including white inside the subject. Check the result.

### "Put a white background behind this transparent PNG so it works as a JPEG"
```bash
magick in.png -background white -alpha remove -alpha off JPG:out.jpg
```
Notes: `-alpha off` after `-alpha remove` ensures no alpha channel is carried into the output.

### "Use this shape as a cookie-cutter mask over that photo"
```bash
magick photo.jpg -alpha set mask.png -gravity center -compose DstIn -composite PNG:out.png
```
Notes: **`-alpha set` on the destination is mandatory.** White in the mask = keep, black/transparent = cut away.

Without `-alpha set`, a destination that has no alpha channel has nowhere to record transparency, so the masked-out region is written as **opaque black** at exit 0 — a plausible-looking wrong image, not a visible error. Verified on a solid `rgb(60,120,90)` destination:

| | inside the shape | outside the shape |
|---|---|---|
| no `-alpha set` | `srgb(60,120,90)` | `srgb(0,0,0)` — opaque black |
| `-alpha set` | `srgba(60,120,90,1)` | `srgba(0,0,0,0)` — transparent |

`-define compose:clip-to-self=false` is often recommended for this and is **not needed on IM 7.1.1-34**: with `-alpha set` the results are byte-identical with and without it, for masks both smaller than and the same size as the destination. It only changes anything in the already-broken no-alpha case. Always confirm the result rather than assuming:
```bash
magick out.png -format 'A=%A corner=%[pixel:p{5,5}]\n' info:
```

### "Only remove the background around the subject, not the white inside it"
```bash
magick logo.png -fuzz 5% -fill none -draw 'alpha 0,0 floodfill' PNG:out.png
```
Notes: flood-fills from the top-left corner and stops at edges. Verified on a donut: the outer white went transparent (`graya(0,0)`) while the interior hole stayed opaque (`graya(255,1)`). Plain `-transparent white` kills both.

### "Why does -flatten clip my image but -layers merge doesn't?"
```bash
magick in.png -background white -flatten out.png        # composites onto the FIRST image's canvas
magick layer1.png layer2.png -background none -layers merge out.png    # expands to the bounding box
```
Notes: verified with a 100x100 base and a layer at +80+80 — `-flatten` gave 100x100 (clipped), `-layers merge` gave 180x180. For "put a background behind this one image" you want `-flatten`'s clipping; for shadows and overhanging layers you want `merge`.

---

## Composite and watermark

### "Put my logo in the bottom-right corner with a 30px margin"
```bash
magick in.jpg logo.png -gravity southeast -geometry +30+30 -compose Over -composite JPG:out.jpg
```
Notes: order is base, then overlay. If the logo PNG has transparent padding, the *canvas* sits 30px from the edge but the visible ink sits further in — check `%@` on the logo first.

### "Same, but make the logo 40% opaque"
```bash
magick in.jpg logo.png -gravity southeast -geometry +30+30 \
  -define compose:args=40 -compose Dissolve -composite JPG:out.jpg
```
Notes: **`-dissolve` does not exist on `magick`** (exit 11) — it is a `magick composite` option. Use `-compose Dissolve` with `compose:args`.

### "Stamp a faint diagonal DRAFT across the whole image"
```bash
magick in.jpg \( -size 300x300 xc:none -gravity center -pointsize 48 -fill 'rgba(0,0,0,0.25)' \
  -annotate -30 'DRAFT' -write mpr:wm +delete \) \
  \( -size '%[fx:w]x%[fx:h]' tile:mpr:wm \) -compose Over -composite JPG:out.jpg
```
Notes: **quote `'%[fx:w]x%[fx:h]'`** — unquoted, zsh fails with `no matches found` before `magick` ever runs. The tile is stashed in an `mpr:` register (single-invocation scope), then tiled to the base image's exact size. Pick a colour with contrast: `rgba(255,255,255,0.35)` is invisible on a light photo even though `compare -metric AE` confirms 112,505 pixels changed. If you build the tile with `-rotate` instead of `-annotate -30`, set `-background none` **before** the rotate or the corners come back opaque white and knock out the photo.

### "Show me what changed between these two images, as a picture"
```bash
magick a.png b.png -compose difference -composite out.png
magick a.png b.png -compose difference -composite -auto-level out.png   # amplified
```
Notes: black = identical. Real differences are often too dark to see, so `-auto-level` (or `-evaluate multiply 8`) to bring them up.

### "Put a small version of image B in the corner of image A"
```bash
magick in.jpg \( inset.png -resize 300x -bordercolor white -border 6 \
  -bordercolor '#00000055' -border 2 \) -gravity southeast -geometry +30+30 -composite JPG:out.jpg
```
Notes: two stacked `-border` calls give a white frame plus a soft outer edge. Resize inside the parens so the base image is untouched.

### "Tile this pattern across a canvas"
```bash
magick -size 640x400 tile:logo.png out.png
magick -size 20x20 pattern:checkerboard -scale '400x300!' out.png
```
Notes: verified pattern names — `checkerboard bricks circles crosshatch fishscales gray50 hexagons horizontal vertical octagons left30 right30 hs_diagcross`. There is no `-list pattern` in IM7 (it errors). `-scale 400x300` alone preserves aspect and gives 300x300; add `!`.

### "Fit this photo into a 16:9 frame with a blurred background instead of black bars"
```bash
magick photo.jpg \( -clone 0 -resize '600x400^' -gravity center -extent 600x400 -blur 0x20 -modulate 80 \) \
  \( -clone 0 -resize 600x400 \) -delete 0 -gravity center -composite JPG:out.jpg
```
Notes: clone twice — cover-cropped and blurred for the backdrop, fit-inside for the foreground — then `-delete 0` drops the original so `-composite` sees exactly two images.

### "Put these two side by side"
```bash
magick a.png b.png +append out.png          # horizontal
magick a.png b.png -append out.png          # vertical
```

### "Side by side with a 10px white gap"
```bash
magick a.png b.png -background white -gravity center +smush 10 out.png
```
Notes: `+smush` is horizontal, `-smush` vertical. The gap is filled with `-background` and images are aligned by `-gravity`.

### "Blend these two photos 50/50"
```bash
magick a.png b.png -define compose:args=50 -compose blend -composite out.png
```

### "Give this floating logo a soft drop shadow"
```bash
magick logo.png \( +clone -background black -shadow 60x8+6+6 \) +swap \
  -background none -layers merge +repage out.png
```
Notes: `-shadow` **replaces** the image with its shadow, which is why the clone/swap dance is needed. `-clone`/`+clone` only work inside `\( \)` on IM7. Use `-layers merge`, not `-mosaic`: `-shadow` produces a *negative* page offset and `-mosaic` clips the overhang (332×332 vs 322×322).

### "Build a contact sheet with filenames under each image"
```bash
magick montage -label '%f' './photos/*.png[0]' -tile 4x -geometry '200x200+8+8' \
  -background white -pointsize 12 PNG:out.png
```
Notes: quote the glob so `montage` expands it, and quote `%f` so the shell does not.

**Append `[0]` to the input pattern.** Without it, an animated GIF contributes one tile *per frame* and a multi-page TIFF/PDF one *per page*, so a nine-file folder can silently produce a sixteen-tile sheet. `%f` still prints the clean filename with the selector attached.

---

## Text

### "Add a caption bar under this image"
```bash
magick in.jpg -background '#222' -fill white -pointsize 28 -gravity center \
  label:'My caption' -append JPG:out.jpg
```
Notes: `label:` auto-sizes to the text; `caption:` wraps to a `-size` you set. The output height grows by the bar — verify it did.

### "Write my name across the middle in big red letters"
```bash
magick in.png -fill red -pointsize 72 -gravity center -annotate 0 'Song' out.png
```
Notes: `-annotate 0` means zero rotation; `-annotate -30` rotates. Confirm the text rendered rather than silently producing nothing:
```bash
magick out.png -format 'sd=%[fx:standard_deviation]\n' info:
```

### "What fonts do I have?"
```bash
magick -list font | sed -n 's/^ *Font: //p' | grep -v '^\.' | sort
```
Notes: `-font` wants the **hyphenated** name printed here, not the space-separated `family:` field — `Times-New-Roman` works, `Times New Roman` warns and silently falls back at exit 0. If the list is empty, pass a font file directly (`-font /System/Library/Fonts/Helvetica.ttc`). Being listed does not mean it renders your text: `Zapf-Dingbats` exits 0 with no warning and produces a blank image. Probe before trusting one:

```bash
err=$(magick -size 200x50 xc:white -font "$F" -pointsize 24 -fill black \
      -gravity center -annotate 0 'Hg' /tmp/probe.png 2>&1)
[ -z "$err" ] && [ "$(magick /tmp/probe.png -format '%[fx:standard_deviation]' info:)" != "0" ] \
  && echo "$F usable"
```

### "Burn the capture date into the corner"
```bash
magick in.jpg -gravity southwest -pointsize 24 -fill yellow \
  -annotate +12+12 '%[exif:DateTimeOriginal]' JPG:out.jpg
```
Notes: if the tag is absent this renders an empty string and still exits 0. Check the tag exists first.

### "Fit this text into a 400×200 box, auto-sizing the font"
```bash
magick -background '#222' -fill '#fff' -size 400x200 -gravity center \
  caption:'A considerably longer piece of text that must shrink to fit' PNG:out.png
```
Notes: give `-size` and **no `-pointsize`** and `caption:` picks the largest size that fits, wrapping as needed — verified `Short` rendered at 166pt and a long sentence at ~30pt, both exactly 400x200. Read the chosen size back with `%[caption:pointsize]`.

### "Add a caption under the image without it changing the image width"
```bash
magick in.jpg -background '#111' -fill white -pointsize 24 -size '%[fx:w]x' \
  -gravity center caption:'Sunset over the bay' -append JPG:out.jpg
```
Notes: without `-size '%[fx:w]x'` a long caption renders wider than the photo and `-append` pads the photo to match (verified: a 400px image came out 552px wide).

### "Put a copyright bar at the bottom"
```bash
magick in.jpg \( -size 1200x56 xc:'rgba(0,0,0,0.55)' -fill white -pointsize 26 \
  -gravity center -annotate 0 '© 2026 Example Studio' \) -gravity south -composite JPG:out.jpg
```
Notes: this overlays and keeps the original dimensions. Swap for `-gravity south -background 'rgba(0,0,0,0.55)' -splice 0x56 -annotate +0+14 '...'` if you would rather grow the canvas (1200x1600 → 1200x1656).

### "Give the text a drop shadow"
```bash
magick in.jpg -pointsize 48 -gravity center \
  -fill 'rgba(0,0,0,0.6)' -annotate +3+3 'SHADOWED' \
  -fill white              -annotate +0+0 'SHADOWED' JPG:out.jpg
```
Notes: cheap hard shadow — draw an offset dark copy, then the light copy. For a real blurred shadow use the `label:` + `-shadow` + `+swap` + `-layers merge` idiom from the drop-shadow recipe above.

### "Draw a red rectangle outline to highlight a region"
```bash
magick in.png -stroke red -strokewidth 4 -fill none -draw 'rectangle 100,80 400,300' out.png
```
Notes: `-fill none` is required or the rectangle is filled solid.

---

## Effects

### "Blur this"
```bash
magick in.png -gaussian-blur 0x8 out.png
```
Notes: `0x8` means "let ImageMagick pick the radius for sigma 8". Sigma is the real control.

### "Pixelate this so a face is unrecognisable"
```bash
magick in.png -scale 5% -scale 2000% out.png
```
Notes: scale down then back up. **This is obfuscation, not redaction** — pixelation and blurring can sometimes be reversed, and the underlying pixels are gone only because `-scale` discarded them. For genuine removal, draw an opaque rectangle over the region.

### "Sharpen it a bit"
```bash
magick in.jpg -unsharp 0x1+1+0.02 out.jpg
```

### "Add a dark vignette"
```bash
magick in.jpg -background black -vignette 0x30 out.jpg
```

### "Oil-paint effect"
```bash
magick in.jpg -paint 4 out.jpg
```
Notes: the option is `-paint`. There is no `-oil-paint` (exit 11). Likewise `-radial-blur` is now `-rotational-blur`.

### "Blur (or pixelate) just one region — a face, a licence plate"
```bash
magick in.jpg \( -clone 0 -crop 150x100+120+80 +repage -blur 0x10 \) \
  -geometry +120+80 -compose over -composite JPG:out.jpg
magick in.jpg \( -clone 0 -crop 150x100+120+80 +repage -scale 8x -scale '150x100!' \) \
  -geometry +120+80 -composite JPG:out.jpg
```
Notes: clone → crop the region → effect → composite back at the same offset. Verified only the named rectangle changed. The pixelate form **must** use `-scale` both ways; `-resize` interpolates on the way back up and you get a blur, not blocks.

### "Find the edges"
```bash
magick in.png -canny 0x1+10%+30% out.png
magick in.png -colorspace gray -edge 2 -negate out.png
```
Notes: `-canny radius x sigma + lower% + upper%` gives clean single-pixel edges. `-edge` is a crude morphological gradient — thick and noisy.

### "Emboss it / add motion blur / add film grain"
```bash
magick in.jpg -emboss 2 out.jpg
magick in.jpg -motion-blur 0x18+45 out.jpg          # radius x sigma + angle (degrees, clockwise from up)
magick in.jpg -attenuate 0.4 +noise Gaussian out.jpg
```
Notes: `-attenuate` scales the noise amount and must come first. `+noise` **adds** noise; `-noise N` is a denoising median filter — easy to mix up.

### "Make it look like a polaroid"
```bash
magick in.jpg -set caption 'Summer 2023' -bordercolor white -background black \
  -density 96 -pointsize 12 -polaroid 6 PNG:out.png
```
Notes: `-polaroid <angle>` does the frame, the caption strip (from `-set caption`), the rotation and the shadow in one operator. `-background` here is the **shadow** colour, not the frame.

### "Make it look like a tiny model (tilt-shift)"
```bash
magick in.png \
  \( -clone 0 -blur 0x8 \
     \( -size 640x170 gradient:white-black -size 640x140 xc:black -size 640x170 gradient:black-white -append \) \
     -alpha off -compose CopyOpacity -composite \) \
  -compose over -composite PNG:out.png
```
Notes: build a mask that is white where you want blur and black in the sharp band, apply it as the *blurred copy's* alpha, then lay that over the sharp original. The three `-size` heights must sum to the image height. Verified by edge energy: top band 0.452 → 0.214, middle unchanged at 0.433, bottom 0.194 → 0.096. The three-image `-composite` mask shorthand does **not** work for this.

### "Round the corners of this thumbnail"
```bash
magick in.png \( +clone -alpha extract -draw 'fill black polygon 0,0 0,15 15,0 fill white circle 15,15 15,0' \
  \( +clone -flip \) -compose Multiply -composite \( +clone -flop \) -compose Multiply -composite \) \
  -alpha off -compose CopyOpacity -composite PNG:out.png
```

---

## Animation

### "Shrink this animated GIF to 120px wide"
```bash
magick in.gif -coalesce -resize 120x -layers optimize -loop 0 out.gif
```
Notes: **always `-coalesce` first**. A naive `-resize` on an optimized GIF corrupts frames because each stored frame is a partial tile. Verify every frame, not just the first:
```bash
magick identify -format '%s %wx%h\n' out.gif
```

### "Save every frame as a separate PNG"
```bash
magick in.gif -coalesce +adjoin 'frame_%d.png'
```

### "Extract the pages of this multi-page TIFF/PDF/PSD"
```bash
magick in.tif +adjoin 'page_%d.png'
```
Notes: **do not `-coalesce` a document.** `-coalesce` is for animations; on a multi-page file with differing page sizes it pads every page onto page 1's canvas and exits 0, silently destroying the real dimensions.

### "Build a GIF from these frames, looping forever at ~8fps"
```bash
magick -delay 1x8 -loop 0 frame*.png out.gif
```
Notes: `-delay` is a **setting** and must precede the inputs — after them it is silently ignored. `-delay 1x8` means "1/8 second"; GIF stores centiseconds so this becomes 12cs ≈ 8.33fps. To change already-loaded frames use `-set delay`. `-loop` works in either position.

### "Make this animation play backwards"
```bash
magick in.gif -coalesce -reverse -layers optimize -loop 0 out.gif
```

### "This GIF is far too big"
```bash
magick in.gif -coalesce -layers OptimizeTransparency -colors 128 -layers optimize out.gif
```

### "Turn this GIF into an animated WebP or APNG"
```bash
magick in.gif -coalesce -loop 0 WEBP:out.webp
magick in.gif -coalesce -define webp:lossless=true -loop 0 WEBP:out.webp
magick in.gif -coalesce APNG:out.png
```
Notes: WebP verified — 10 frames kept, 6555 B → 3234 B lossless. APNG needs the explicit `APNG:` prefix, and `identify` then reports `1` frame because IM's PNG reader ignores `acTL`; verify with `grep -c acTL out.png` or a browser. **APNG timing is unreliable**: IM re-times into 1/25 s ticks and only `-delay 4` round-trips exactly (verified `-delay 20` on 3 frames gave 0.84 s instead of 0.60 s). Prefer WebP.

### "Make a crossfade animation between these two images"
```bash
magick a.png b.png -morph 12 -set delay 6 -loop 0 out.gif
magick a.png b.png -morph 12 \( -clone -2-1 \) -set delay 6 -loop 0 -layers optimize out.gif
```
Notes: `-morph N` inserts N interpolated frames, so you end up with N+2 (verified 14). The inputs must be the same size — `-resize '300x300!'` first or IM pads them. The second form adds the reverse pass for a seamless loop.

### "Make it ping-pong instead of jumping back to the start"
```bash
magick in.gif -coalesce \( -clone -2-1 \) -layers optimize -loop 0 out.gif
```
Notes: `-clone -2-1` clones from the second-to-last frame down to frame 1, so 10 frames become 18 with no duplicated endpoints (verified frame 10 == frame 8, frame 17 == frame 1).

**Verifying an optimized animation:** after `-layers optimize`, reading `out.gif[1]` gives the *stored partial tile*, where unchanged pixels are transparent — comparing that against a source frame looks like corruption. Always coalesce before verifying:
```bash
magick out.gif -coalesce +adjoin 'check_%d.png'
```

---

## Batch

### "Resize every image in this folder"
```bash
mkdir -p out
magick mogrify -path out -resize '1200x1200>' -quality 85 in/*.jpg
```
Notes: **`mogrify` overwrites its inputs in place without `-path`.** Never pass `--` to `mogrify` — it writes a file literally named `--` and exits 0. Confirm the originals survived:
```bash
shasum in/* > /tmp/before.sha   # ... run ... then
shasum -c /tmp/before.sha
```

### "Convert every PNG under this tree to WebP, keeping the folder structure"
```bash
find in -name '*.png' -print0 | while IFS= read -r -d '' f; do
  out="${f%.png}.webp"
  magick "$f" -quality 85 "WEBP:$out"
done
```
Notes: `mogrify -path` flattens the tree into one directory, so build each output path explicitly instead.

### "I have ten thousand photos to thumbnail — make it fast"
```bash
mkdir -p out
find in -name '*.jpg' -print0 | xargs -0 -P 8 -I{} sh -c \
  'magick -define jpeg:size=400x400 "$1" -thumbnail 200x200 -strip "out/$(basename "$1")"' _ {}
```
Notes: `-I{}` substitutes the **whole path**, so `out/{}.jpg` would resolve to `out/in/photo.jpg.jpg` and fail — wrap in `sh -c` and use `basename`. `jpeg:size` lets libjpeg decode at reduced scale, roughly 4× faster; it makes the result slightly softer and the derived dimension can land a pixel off, so avoid it when an exact output size is contractual.

---

## Compare

### "Are these two files the same image?"
```bash
magick identify -format '%f %wx%h %#\n' -- a.png b.png     # check sizes AND signature first
magick compare -metric AE a.png b.png null: 2>&1
```
Notes: **`compare` exits `0` identical, `1` images differ, `2` real error.** Exit 1 is not a failure. The metric goes to **stderr**. On quantized output (GIF/palette) bare `AE` reports near-total mismatch for a correct pair — use `RMSE` or `PHASH`, or add `-fuzz`.

**`compare` does not refuse mismatched dimensions.** A 640×480 against a 320×240 returns a bare `307200` with no warning at exit 1 — indistinguishable from "these differ a lot". Always compare `%wx%h` first. `%#` is the fastest identical-or-not test and is size-aware.

### "How different are they, perceptually?"
```bash
magick compare -metric RMSE a.jpg b.jpg null: 2>&1     # 1621.4 (0.0247)  lower is better
magick compare -metric PSNR a.jpg b.jpg null: 2>&1     # 32.13 dB         higher is better
magick compare -metric SSIM a.jpg b.jpg null: 2>&1     # 0.733            1.0 is identical
magick compare -metric PHASH a.jpg b.jpg null: 2>&1    # 0.557            0 is identical
```
Notes: those numbers are a real measurement of a q40 re-encode vs. its original. Rules of thumb: PSNR > 40 dB or SSIM > 0.98 is visually indistinguishable. **`PHASH` is the only one that survives resizing and re-cropping**, so use it for "is this the same picture", not "is this the same file". Also available: `DSSIM NCC MAE MSE FUZZ`.

### "Show me what changed between these two screenshots"
```bash
magick compare -metric RMSE -highlight-color red a.png b.png diff.png 2>&1
```

### "Find where this icon appears in the screenshot"
```bash
magick compare -subimage-search -metric RMSE screenshot.png icon.png null: 2>&1 | tail -1
# -> "0 (0) @ 220,140"   score, normalised score, then the top-left match coordinates
```
Notes: verified an exact hit at 220,140. Brute force and **slow** — 8.9 s for an 80×60 needle in a 640×480 haystack, and it scales with the product of the areas. Downscale both 4× to find the neighbourhood, then re-search a crop at full size. Writing to a file produces **two** outputs, `match-0.png` (difference) and `match-1.png` (similarity map).

### "Find duplicate images in this folder"
```bash
magick identify -format '%# %f\n' -- ./*.png | sort
```
Notes: `%#` is a content signature — identical pixels give identical signatures regardless of filename or format.

---

## Pipelines and generation

### "Do several steps without temporary files"
```bash
magick in.png -resize 50% miff:- | magick - -colorspace Gray PNG:out.png
```
Notes: pipe `miff:-`, not PNG/JPEG — MIFF is lossless and preserves depth, alpha, and multiple frames. A bare `-` output inherits the **input's** coder, so always name it (`png:-`).

### "Save an intermediate mid-pipeline"
```bash
magick in.png -resize 50% -write half.png -resize 50% quarter.png
```
Notes: `-write` emits the current image and keeps going. Each step works on the **previous result**, so rounding compounds — verified `1200x1600 -resize 800x -resize 400x` gives 400x534, whereas resizing the original straight to 400x gives 400x533. Re-clone from an `mpr:` per size if exactness matters.

### "Read from stdin / write to stdout"
```bash
magick - -resize 200x PNG:out.png < in.jpg
magick in.jpg -resize 200x jpg:- > out.jpg
curl -s https://example.com/x.png | magick - -resize 100x PNG:out.png   # needs network
```
Notes: on **output** you must name the coder (`jpg:-`, `png:-`) — a bare `-` inherits the input's format. On input a bare `-` is fine because IM sniffs the magic bytes.

### "Reuse the same image several times in one command"
```bash
magick in.png -write mpr:orig +delete \( mpr:orig -resize 200% \) \( mpr:orig -negate \) +append out.png
```
Notes: `mpr:` is an in-memory register scoped to a **single** `magick` invocation — it does not survive into the next command. `-write mpr:name +delete` stores and drops the original.

### "Work on a copy inside the same command"
```bash
magick in.jpg \( +clone -unsharp 0x3+2+0 \) -compose blend -define compose:args=40 -composite out.jpg
```
Notes: `\( ... \)` is a sub-stack — operators inside affect only what is inside. `+clone` copies the last image, `-clone 0` by index, `-clone -2-1` a range. **`-clone` fails outside `\( \)`** (`UnableToCloneImage`), and the parens must be escaped or quoted so the shell does not eat them.

### "Compute a number from the image and use it"
```bash
magick in.jpg -format 'aspect=%[fx:w/h] mp=%[fx:w*h/1e6] landscape=%[fx:w>h?1:0] half=%[fx:int(w/2)]x%[fx:int(h/2)]\n' info:
magick in.jpg -fx '(r+g+b)/3' out.jpg
```
Notes: `%[fx:...]` computes a **value** at format time and is cheap; `-fx '...'` runs per pixel and is very slow — reach for `-colorspace`, `-evaluate` or `-function` when one exists. Values are 0..1 normalised. Add `-precision 9` for large integers.

### "Create a placeholder gradient"
```bash
magick -size 1920x1080 gradient:navy-skyblue out.png
```
Notes: `-size` must come **before** the generator. Other generators: `xc:red`, `plasma:`, `radial-gradient:`, `pattern:checkerboard`, `label:text`.

---

## Verification cheat sheet

| Claim | Check |
|---|---|
| right format | `identify -format '%m'` — never trust the extension or exit 0 |
| right size | `identify -format '%wx%h'` |
| canvas reset | `identify -format '%[page] %X%Y'` → `+0+0` |
| right direction (rotate/flip) | `-format '%[pixel:p{0,0}]'` — geometry cannot catch this |
| alpha state | `-format '%A %[opaque]'` |
| every frame correct | `identify -format '%s %wx%h\n'` (coalesce optimized GIFs first) |
| not blank | `-format '%[fx:standard_deviation]'` > 0 (flat images legitimately read 0) |
| unchanged pixels | `compare -metric AE a b null:` → 0 |
| originals survived batch | `shasum` before and after |
| size budget | `ls -l` / `%b` |
| metadata gone / kept | `-format '%[profiles]'`, `-format 'exif=[%[EXIF:*]]'` |
| file not truncated | `magick identify -regard-warnings f` → exit 1 if corrupt |
| colour landed right | `-format '%[pixel:p{x,y}]'`, alpha via `%[fx:p{x,y}.a]` |
| perceptually close enough | `compare -metric PSNR` > 40 dB, or `SSIM` > 0.98 |

**Integrity is the one check with a real gotcha.** Verified on a JPEG truncated to 3000 bytes: plain
`magick identify`, and `magick f null:`, both exit **0**. Only `magick identify -regard-warnings f`
exits 1. Use that as the gate in scripts.

**Probe alpha with `%[fx:p{x,y}.a]`, not `a.p{x,y}`** — the latter is a syntax error
(`Expected operator`). Sampling a corner and the centre in one line catches both "the background is
transparent when it should be white" and "the watermark knocked the image out".

**Metrics do not catch composition errors.** For anything with masks, compositing, text placement or
watermarks, render a small preview (`magick out.jpg -resize 400x /tmp/preview.png`) and look at it.
Several recipes here passed every numeric check while being visibly wrong — the tiled watermark
rendered the photo as fragments on white, and the montage silently dropped its labels. Only the
preview exposed those.

---

## Known-broken on this machine

These are environment faults, not usage errors. Check before blaming the command.

- **HEIC / AVIF / JXL have no working coder.** `magick -list format | grep -i heic` prints nothing;
  the modules ship but are linked against an older libheif and fail to load. Worse, a *write* to a
  bare `.heic`/`.avif` extension silently produces the input's format at **exit 0** — always use an
  explicit `HEIC:` prefix (which correctly exits 1) or a `-list format` guard. `brew reinstall
  imagemagick` fixes it; `sips` is the macOS fallback.
- **`mogrify` mis-parses `--`.** `magick mogrify -path out -resize 50% -- a.jpg` writes a file
  literally named `--` into `out/` and skips `a.jpg`, at exit 0. (`magick identify -- f` is fine.)
- **`-clone` outside `\( \)`** fails with `UnableToCloneImage`.
- **`-oil-paint` and `-radial-blur` do not exist** — they are `-paint` and `-rotational-blur`.
  `-dissolve` does not exist on `magick` either; use `-compose Dissolve -define compose:args=N`.
- **`compare` exits 1 for "images differ"**, which is a normal result, not an error. Exit 2 is a real
  error. It also does not refuse mismatched dimensions.
- **`\t` is not an escape in `-format`** — it emits a literal `t`.
- **`%[fx:]` prints scientific notation above 1e6** unless you pass `-precision 9`.

---

## Not yet covered

Intents that are deliberately absent, so nothing here looks more complete than it is:

- Colour: `-level`/`+level` explicit black/white points, `-clahe`, LUT (`.cube`) application.
- Text: RTL/CJK shaping, `-kerning`/`-interline-spacing`, text on a path.
- Composite: seam carving (`-liquid-rescale`), perspective `-distort` beyond `SRT`.
- Animation: per-frame variable delays, GIF → MP4 (needs ffmpeg, not ImageMagick).
- Raw formats (CR2/NEF/DNG) — the `raw` coder is present but untested here.
- `-limit`/`-define registry:` resource tuning for very large images is mentioned only in passing.
