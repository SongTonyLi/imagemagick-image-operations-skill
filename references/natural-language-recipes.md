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
magick photo.png -alpha set mask.png -gravity center \
  -compose DstIn -define compose:clip-to-self=false -composite PNG:out.png
```
Notes: two non-obvious prerequisites. **`-alpha set` on the destination** — without it, a destination with no alpha channel comes out with the masked area opaque **black** instead of transparent, at exit 0. **`compose:clip-to-self=false`** — without it, only the mask's own bounding box is affected and the surrounding area stays fully opaque.

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
magick in.jpg \( -size 300x300 xc:none -gravity center -pointsize 48 -fill 'rgba(255,255,255,0.35)' \
  -annotate -30 'DRAFT' -write mpr:wm +delete \) \
  \( -size %[fx:w]x%[fx:h] tile:mpr:wm \) -compose Over -composite JPG:out.jpg
```
Notes: simpler alternative — build the tile, then `-tile` it with `composite`. Check the result is not blank (`%[fx:standard_deviation] > 0`).

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

### "Show me what changed between these two screenshots"
```bash
magick compare -metric RMSE -highlight-color red a.png b.png diff.png 2>&1
```

### "Find where this icon appears in the screenshot"
```bash
magick compare -metric RMSE -subimage-search screenshot.png icon.png match.png 2>&1
```
Notes: slow on large images. The best offset is printed after the metric.

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
