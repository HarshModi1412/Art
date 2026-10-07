# Brand image prompts

Generated from `backend/core/brandkit.py` by `scripts/gen_brand_prompts.py`. Do not edit by hand:
change the library and run the script again.

## How to use this

1. Pick a direction below. Generate each image with ChatGPT (or any image model) by pasting the prompt as it is.
2. ChatGPT makes 1024 × 1024, 1024 × 1536 or 1536 × 1024. Generate at the closest shape, then crop and resize to the size in the table (a free tool such as squoosh.app does both and saves WebP).
3. Save each file as `<name>.webp` (or `.jpg`) in `Smart CafeX/brand-assets/<direction id>/`, for example `Smart CafeX/brand-assets/quiet_luxury/post-bg.webp`. Keep each file under 300 KB.
4. Commit the files. The Brand Management module finds them by name on its next load; anything missing is drawn from the palette instead, so you can add images one at a time.

**The rules every prompt already carries:**

- **No text in any image.** The app sets the seller's name in real type on top. If an image comes back with letters, signs or labels in it, generate it again.
- **No brand names.** The "in the spirit of" names you see in the app are guidance for sellers only.
- **Colours come from the direction's first palette.** The app only shows these photographs while a seller uses that palette; on the other palettes it draws the backgrounds itself, so nothing clashes.
- **`texture` and `pattern` are black and white.** The app tints them to whatever colours the seller picks.
- **`motif` is decoration**, never a logo. Every seller in a direction shares it.

| File | Size | Shape | What the app uses it for |
|---|---|---|---|
| `post-bg` | 1080 × 1350 | 4:5 portrait | Background for feed posts. Text sits in the lower 40%. |
| `story-bg` | 1080 × 1920 | 9:16 portrait | Background for Instagram stories. Name at the top, text at the bottom. |
| `hero` | 2400 × 1350 | 16:9 landscape | Website hero and the direction card. The name sits in the centre. |
| `texture` | 2048 × 2048 | 1:1 square | Tileable surface. Tinted to any palette by the app. |
| `pattern` | 2048 × 2048 | 1:1 square | Seamless repeat for packaging and posts. Tinted by the app. |
| `packaging` | 1600 × 1600 | 1:1 square | Packaging inspiration. Shown as a picture only, never printed on. |
| `motif` | 1024 × 1024 | 1:1 square | Decoration only. Never use it as a logo or monogram. |
| `mood-<category>` | 1200 × 1500 | 4:5 portrait | The photography section of the brand book, one per category the direction supports. |

## Directions

- [Quiet Luxury](#quiet-luxury) (`quiet_luxury`)
- [Heritage Maison](#heritage-maison) (`heritage_maison`)
- [Modern Minimal](#modern-minimal) (`modern_minimal`)
- [Everyday Bright](#everyday-bright) (`everyday_bright`)
- [Playful Pop](#playful-pop) (`playful_pop`)
- [Street Edge](#street-edge) (`street_edge`)
- [Soft Romantic](#soft-romantic) (`soft_romantic`)
- [Artisan Earth](#artisan-earth) (`artisan_earth`)
- [Modern Heritage](#modern-heritage) (`modern_heritage`)
- [Apothecary](#apothecary) (`apothecary`)
- [Calm & Airy](#calm-airy) (`calm_airy`)
- [Bold Maximal](#bold-maximal) (`bold_maximal`)
- [Classic Timeless](#classic-timeless) (`classic_timeless`)

<a id="quiet-luxury"></a>
## Quiet Luxury

Folder: `Smart CafeX/brand-assets/quiet_luxury/`  
Restraint as the luxury. Few words, exact details, nothing loud.  
Categories: jewellery, clothing, fragrance, home_decor

| Role | Colour |
|---|---|
| Background | `#F3F0EA` |
| Panels | `#E7E2D9` |
| Deep tone | `#1F1D1A` |
| Accent | `#6E6253` |
| Support | `#A89D8E` |

**`post-bg`**

```text
minimal still life, soft directional daylight, plaster and pale stone surfaces, muted warm neutral tones, generous negative space, calm and restrained mood. Abstract background for a social media post, portrait 4:5, no product. Keep the lower 40% of the frame calm, plain and evenly lit in #F3F0EA with nothing in it; place soft shapes, surfaces and shadows in the upper 60%. Colour palette (Stone): background #F3F0EA, panels #E7E2D9, deep tone #1F1D1A, accent #6E6253, support #A89D8E. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`story-bg`**

```text
minimal still life, soft directional daylight, plaster and pale stone surfaces, muted warm neutral tones, generous negative space, calm and restrained mood. Abstract vertical background, portrait 9:16, no product. Keep the top 15% and the bottom 35% calm and plain in #F3F0EA; put the visual interest in the middle. Colour palette (Stone): background #F3F0EA, panels #E7E2D9, deep tone #1F1D1A, accent #6E6253, support #A89D8E. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`hero`**

```text
minimal still life, soft directional daylight, plaster and pale stone surfaces, muted warm neutral tones, generous negative space, calm and restrained mood. Wide website hero background, landscape 16:9, no product. Leave the centre third calm and empty so a name can sit on it; let surfaces, light and shadow fill the edges. Colour palette (Stone): background #F3F0EA, panels #E7E2D9, deep tone #1F1D1A, accent #6E6253, support #A89D8E. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`texture`**

```text
Seamless tileable texture of fine lime plaster wall, photographed flat and straight on, even shadowless light, black and white only (greyscale), medium contrast, square 1:1, edges that tile without seams. No objects. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`pattern`**

```text
Seamless repeating pattern of very fine, widely spaced pinstripe lines, flat graphic design, black and white only (greyscale), evenly spaced, square 1:1, edges that tile without seams, refined and balanced. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`packaging`**

```text
minimal still life, soft directional daylight, plaster and pale stone surfaces, muted warm neutral tones, generous negative space, calm and restrained mood. Product packaging set shot front-on and centred: a rigid gift box with its lid beside it, a paper shopping bag, folded tissue paper and a small swing tag on a string. Every item is completely blank and unprinted, in tones of #F3F0EA and #6E6253 with #A89D8E details, on a #E7E2D9 surface. Colour palette (Stone): background #F3F0EA, panels #E7E2D9, deep tone #1F1D1A, accent #6E6253, support #A89D8E. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`motif`**

```text
a single thin arch outline, flat vector-style graphic, a single colour #6E6253 on a plain #F3F0EA background, centred with a generous margin, crisp clean edges, square 1:1. Nothing that looks like a letter or a number. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-jewellery`**

```text
minimal still life, soft directional daylight, plaster and pale stone surfaces, muted warm neutral tones, generous negative space, calm and restrained mood. Lifestyle photograph, portrait 4:5: a pair of hands resting on the surface, wearing a simple ring and a fine chain, cropped at the wrists. Plain stone or plaster backgrounds in the ground tone. Colour palette (Stone): background #F3F0EA, panels #E7E2D9, deep tone #1F1D1A, accent #6E6253, support #A89D8E. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-clothing`**

```text
minimal still life, soft directional daylight, plaster and pale stone surfaces, muted warm neutral tones, generous negative space, calm and restrained mood. Lifestyle photograph, portrait 4:5: a softly folded garment and a garment on a plain hanger, no labels or tags visible. Plain stone or plaster backgrounds in the ground tone. Colour palette (Stone): background #F3F0EA, panels #E7E2D9, deep tone #1F1D1A, accent #6E6253, support #A89D8E. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-fragrance`**

```text
minimal still life, soft directional daylight, plaster and pale stone surfaces, muted warm neutral tones, generous negative space, calm and restrained mood. Lifestyle photograph, portrait 4:5: an unlabelled glass perfume bottle with a plain cap, with one or two small props. Plain stone or plaster backgrounds in the ground tone. Colour palette (Stone): background #F3F0EA, panels #E7E2D9, deep tone #1F1D1A, accent #6E6253, support #A89D8E. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-home_decor`**

```text
minimal still life, soft directional daylight, plaster and pale stone surfaces, muted warm neutral tones, generous negative space, calm and restrained mood. Lifestyle photograph, portrait 4:5: a quiet corner of a room with a vase, a few books with blank spines and a draped throw. Plain stone or plaster backgrounds in the ground tone. Colour palette (Stone): background #F3F0EA, panels #E7E2D9, deep tone #1F1D1A, accent #6E6253, support #A89D8E. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

<a id="heritage-maison"></a>
## Heritage Maison

Folder: `Smart CafeX/brand-assets/heritage_maison/`  
Grand, assured and ceremonial. Deep tones, a serif with presence.  
Categories: jewellery, clothing, fragrance, home_decor

| Role | Colour |
|---|---|
| Background | `#F6F1E7` |
| Panels | `#ECE3D1` |
| Deep tone | `#14261E` |
| Accent | `#1F4D3A` |
| Support | `#9C7A45` |

**`post-bg`**

```text
rich still life, warm low-key light with soft golden highlights, deep velvet and dark marble surfaces, emerald and oxblood tones, symmetrical composition, opulent and assured mood. Abstract background for a social media post, portrait 4:5, no product. Keep the lower 40% of the frame calm, plain and evenly lit in #F6F1E7 with nothing in it; place soft shapes, surfaces and shadows in the upper 60%. Colour palette (Emerald): background #F6F1E7, panels #ECE3D1, deep tone #14261E, accent #1F4D3A, support #9C7A45. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`story-bg`**

```text
rich still life, warm low-key light with soft golden highlights, deep velvet and dark marble surfaces, emerald and oxblood tones, symmetrical composition, opulent and assured mood. Abstract vertical background, portrait 9:16, no product. Keep the top 15% and the bottom 35% calm and plain in #F6F1E7; put the visual interest in the middle. Colour palette (Emerald): background #F6F1E7, panels #ECE3D1, deep tone #14261E, accent #1F4D3A, support #9C7A45. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`hero`**

```text
rich still life, warm low-key light with soft golden highlights, deep velvet and dark marble surfaces, emerald and oxblood tones, symmetrical composition, opulent and assured mood. Wide website hero background, landscape 16:9, no product. Leave the centre third calm and empty so a name can sit on it; let surfaces, light and shadow fill the edges. Colour palette (Emerald): background #F6F1E7, panels #ECE3D1, deep tone #14261E, accent #1F4D3A, support #9C7A45. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`texture`**

```text
Seamless tileable texture of silk damask fabric, photographed flat and straight on, even shadowless light, black and white only (greyscale), medium contrast, square 1:1, edges that tile without seams. No objects. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`pattern`**

```text
Seamless repeating pattern of small symmetrical medallion damask, flat graphic design, black and white only (greyscale), evenly spaced, square 1:1, edges that tile without seams, refined and balanced. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`packaging`**

```text
rich still life, warm low-key light with soft golden highlights, deep velvet and dark marble surfaces, emerald and oxblood tones, symmetrical composition, opulent and assured mood. Product packaging set shot front-on and centred: a rigid gift box with its lid beside it, a paper shopping bag, folded tissue paper and a small swing tag on a string. Every item is completely blank and unprinted, in tones of #F6F1E7 and #1F4D3A with #9C7A45 details, on a #ECE3D1 surface. Colour palette (Emerald): background #F6F1E7, panels #ECE3D1, deep tone #14261E, accent #1F4D3A, support #9C7A45. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`motif`**

```text
an ornate symmetrical crest shape without any letters, flat vector-style graphic, a single colour #1F4D3A on a plain #F6F1E7 background, centred with a generous margin, crisp clean edges, square 1:1. Nothing that looks like a letter or a number. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-jewellery`**

```text
rich still life, warm low-key light with soft golden highlights, deep velvet and dark marble surfaces, emerald and oxblood tones, symmetrical composition, opulent and assured mood. Lifestyle photograph, portrait 4:5: a pair of hands resting on the surface, wearing a simple ring and a fine chain, cropped at the wrists. Deep velvet, dark wood or marble surfaces. Colour palette (Emerald): background #F6F1E7, panels #ECE3D1, deep tone #14261E, accent #1F4D3A, support #9C7A45. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-clothing`**

```text
rich still life, warm low-key light with soft golden highlights, deep velvet and dark marble surfaces, emerald and oxblood tones, symmetrical composition, opulent and assured mood. Lifestyle photograph, portrait 4:5: a softly folded garment and a garment on a plain hanger, no labels or tags visible. Deep velvet, dark wood or marble surfaces. Colour palette (Emerald): background #F6F1E7, panels #ECE3D1, deep tone #14261E, accent #1F4D3A, support #9C7A45. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-fragrance`**

```text
rich still life, warm low-key light with soft golden highlights, deep velvet and dark marble surfaces, emerald and oxblood tones, symmetrical composition, opulent and assured mood. Lifestyle photograph, portrait 4:5: an unlabelled glass perfume bottle with a plain cap, with one or two small props. Deep velvet, dark wood or marble surfaces. Colour palette (Emerald): background #F6F1E7, panels #ECE3D1, deep tone #14261E, accent #1F4D3A, support #9C7A45. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-home_decor`**

```text
rich still life, warm low-key light with soft golden highlights, deep velvet and dark marble surfaces, emerald and oxblood tones, symmetrical composition, opulent and assured mood. Lifestyle photograph, portrait 4:5: a quiet corner of a room with a vase, a few books with blank spines and a draped throw. Deep velvet, dark wood or marble surfaces. Colour palette (Emerald): background #F6F1E7, panels #ECE3D1, deep tone #14261E, accent #1F4D3A, support #9C7A45. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

<a id="modern-minimal"></a>
## Modern Minimal

Folder: `Smart CafeX/brand-assets/modern_minimal/`  
Sharp, current and clean. Black, white and one confident line of type.  
Categories: jewellery, clothing, fragrance, home_decor

| Role | Colour |
|---|---|
| Background | `#FFFFFF` |
| Panels | `#F2F2F2` |
| Deep tone | `#111111` |
| Accent | `#111111` |
| Support | `#8A8A8A` |

**`post-bg`**

```text
minimal studio still life, crisp even light, seamless white and pale stone backdrop, monochrome palette, sharp architectural shadows, precise composition. Abstract background for a social media post, portrait 4:5, no product. Keep the lower 40% of the frame calm, plain and evenly lit in #FFFFFF with nothing in it; place soft shapes, surfaces and shadows in the upper 60%. Colour palette (Mono): background #FFFFFF, panels #F2F2F2, deep tone #111111, accent #111111, support #8A8A8A. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`story-bg`**

```text
minimal studio still life, crisp even light, seamless white and pale stone backdrop, monochrome palette, sharp architectural shadows, precise composition. Abstract vertical background, portrait 9:16, no product. Keep the top 15% and the bottom 35% calm and plain in #FFFFFF; put the visual interest in the middle. Colour palette (Mono): background #FFFFFF, panels #F2F2F2, deep tone #111111, accent #111111, support #8A8A8A. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`hero`**

```text
minimal studio still life, crisp even light, seamless white and pale stone backdrop, monochrome palette, sharp architectural shadows, precise composition. Wide website hero background, landscape 16:9, no product. Leave the centre third calm and empty so a name can sit on it; let surfaces, light and shadow fill the edges. Colour palette (Mono): background #FFFFFF, panels #F2F2F2, deep tone #111111, accent #111111, support #8A8A8A. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`texture`**

```text
Seamless tileable texture of smooth heavyweight matte paper, photographed flat and straight on, even shadowless light, black and white only (greyscale), medium contrast, square 1:1, edges that tile without seams. No objects. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`pattern`**

```text
Seamless repeating pattern of thin precise grid lines, flat graphic design, black and white only (greyscale), evenly spaced, square 1:1, edges that tile without seams, refined and balanced. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`packaging`**

```text
minimal studio still life, crisp even light, seamless white and pale stone backdrop, monochrome palette, sharp architectural shadows, precise composition. Product packaging set shot front-on and centred: a rigid gift box with its lid beside it, a paper shopping bag, folded tissue paper and a small swing tag on a string. Every item is completely blank and unprinted, in tones of #FFFFFF and #111111 with #8A8A8A details, on a #F2F2F2 surface. Colour palette (Mono): background #FFFFFF, panels #F2F2F2, deep tone #111111, accent #111111, support #8A8A8A. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`motif`**

```text
a single bold geometric square rotated slightly, flat vector-style graphic, a single colour #111111 on a plain #FFFFFF background, centred with a generous margin, crisp clean edges, square 1:1. Nothing that looks like a letter or a number. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-jewellery`**

```text
minimal studio still life, crisp even light, seamless white and pale stone backdrop, monochrome palette, sharp architectural shadows, precise composition. Lifestyle photograph, portrait 4:5: a pair of hands resting on the surface, wearing a simple ring and a fine chain, cropped at the wrists. Seamless white or stone backdrop. Colour palette (Mono): background #FFFFFF, panels #F2F2F2, deep tone #111111, accent #111111, support #8A8A8A. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-clothing`**

```text
minimal studio still life, crisp even light, seamless white and pale stone backdrop, monochrome palette, sharp architectural shadows, precise composition. Lifestyle photograph, portrait 4:5: a softly folded garment and a garment on a plain hanger, no labels or tags visible. Seamless white or stone backdrop. Colour palette (Mono): background #FFFFFF, panels #F2F2F2, deep tone #111111, accent #111111, support #8A8A8A. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-fragrance`**

```text
minimal studio still life, crisp even light, seamless white and pale stone backdrop, monochrome palette, sharp architectural shadows, precise composition. Lifestyle photograph, portrait 4:5: an unlabelled glass perfume bottle with a plain cap, with one or two small props. Seamless white or stone backdrop. Colour palette (Mono): background #FFFFFF, panels #F2F2F2, deep tone #111111, accent #111111, support #8A8A8A. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-home_decor`**

```text
minimal studio still life, crisp even light, seamless white and pale stone backdrop, monochrome palette, sharp architectural shadows, precise composition. Lifestyle photograph, portrait 4:5: a quiet corner of a room with a vase, a few books with blank spines and a draped throw. Seamless white or stone backdrop. Colour palette (Mono): background #FFFFFF, panels #F2F2F2, deep tone #111111, accent #111111, support #8A8A8A. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

<a id="everyday-bright"></a>
## Everyday Bright

Folder: `Smart CafeX/brand-assets/everyday_bright/`  
Friendly, bright and easy. Bold tones, clear type, a brand for every day.  
Categories: jewellery, clothing, fragrance, home_decor

| Role | Colour |
|---|---|
| Background | `#FFFFFF` |
| Panels | `#F5F3F0` |
| Deep tone | `#161616` |
| Accent | `#C8102E` |
| Support | `#E0A82E` |

**`post-bg`**

```text
bright cheerful still life, clean daylight, saturated primary colour blocks against white, crisp shadows, energetic and friendly mood. Abstract background for a social media post, portrait 4:5, no product. Keep the lower 40% of the frame calm, plain and evenly lit in #FFFFFF with nothing in it; place soft shapes, surfaces and shadows in the upper 60%. Colour palette (Signal red): background #FFFFFF, panels #F5F3F0, deep tone #161616, accent #C8102E, support #E0A82E. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`story-bg`**

```text
bright cheerful still life, clean daylight, saturated primary colour blocks against white, crisp shadows, energetic and friendly mood. Abstract vertical background, portrait 9:16, no product. Keep the top 15% and the bottom 35% calm and plain in #FFFFFF; put the visual interest in the middle. Colour palette (Signal red): background #FFFFFF, panels #F5F3F0, deep tone #161616, accent #C8102E, support #E0A82E. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`hero`**

```text
bright cheerful still life, clean daylight, saturated primary colour blocks against white, crisp shadows, energetic and friendly mood. Wide website hero background, landscape 16:9, no product. Leave the centre third calm and empty so a name can sit on it; let surfaces, light and shadow fill the edges. Colour palette (Signal red): background #FFFFFF, panels #F5F3F0, deep tone #161616, accent #C8102E, support #E0A82E. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`texture`**

```text
Seamless tileable texture of fine cotton canvas, photographed flat and straight on, even shadowless light, black and white only (greyscale), medium contrast, square 1:1, edges that tile without seams. No objects. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`pattern`**

```text
Seamless repeating pattern of simple evenly spaced polka dots, flat graphic design, black and white only (greyscale), evenly spaced, square 1:1, edges that tile without seams, refined and balanced. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`packaging`**

```text
bright cheerful still life, clean daylight, saturated primary colour blocks against white, crisp shadows, energetic and friendly mood. Product packaging set shot front-on and centred: a rigid gift box with its lid beside it, a paper shopping bag, folded tissue paper and a small swing tag on a string. Every item is completely blank and unprinted, in tones of #FFFFFF and #C8102E with #E0A82E details, on a #F5F3F0 surface. Colour palette (Signal red): background #FFFFFF, panels #F5F3F0, deep tone #161616, accent #C8102E, support #E0A82E. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`motif`**

```text
a cheerful rounded star shape, flat vector-style graphic, a single colour #C8102E on a plain #FFFFFF background, centred with a generous margin, crisp clean edges, square 1:1. Nothing that looks like a letter or a number. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-jewellery`**

```text
bright cheerful still life, clean daylight, saturated primary colour blocks against white, crisp shadows, energetic and friendly mood. Lifestyle photograph, portrait 4:5: a pair of hands resting on the surface, wearing a simple ring and a fine chain, cropped at the wrists. White backdrops with blocks of bold tone. Colour palette (Signal red): background #FFFFFF, panels #F5F3F0, deep tone #161616, accent #C8102E, support #E0A82E. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-clothing`**

```text
bright cheerful still life, clean daylight, saturated primary colour blocks against white, crisp shadows, energetic and friendly mood. Lifestyle photograph, portrait 4:5: a softly folded garment and a garment on a plain hanger, no labels or tags visible. White backdrops with blocks of bold tone. Colour palette (Signal red): background #FFFFFF, panels #F5F3F0, deep tone #161616, accent #C8102E, support #E0A82E. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-fragrance`**

```text
bright cheerful still life, clean daylight, saturated primary colour blocks against white, crisp shadows, energetic and friendly mood. Lifestyle photograph, portrait 4:5: an unlabelled glass perfume bottle with a plain cap, with one or two small props. White backdrops with blocks of bold tone. Colour palette (Signal red): background #FFFFFF, panels #F5F3F0, deep tone #161616, accent #C8102E, support #E0A82E. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-home_decor`**

```text
bright cheerful still life, clean daylight, saturated primary colour blocks against white, crisp shadows, energetic and friendly mood. Lifestyle photograph, portrait 4:5: a quiet corner of a room with a vase, a few books with blank spines and a draped throw. White backdrops with blocks of bold tone. Colour palette (Signal red): background #FFFFFF, panels #F5F3F0, deep tone #161616, accent #C8102E, support #E0A82E. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

<a id="playful-pop"></a>
## Playful Pop

Folder: `Smart CafeX/brand-assets/playful_pop/`  
Loud, funny and unmistakable. Chunky type, candy tones, a wink in every line.  
Categories: jewellery, clothing, fragrance, home_decor

| Role | Colour |
|---|---|
| Background | `#FFF4F8` |
| Panels | `#FFE4EE` |
| Deep tone | `#2B0F2E` |
| Accent | `#C2185B` |
| Support | `#F2B705` |

**`post-bg`**

```text
playful pop still life, hard flash light, glossy candy-toned surfaces, chunky geometric shapes, bold colour blocking, joyful and cheeky mood. Abstract background for a social media post, portrait 4:5, no product. Keep the lower 40% of the frame calm, plain and evenly lit in #FFF4F8 with nothing in it; place soft shapes, surfaces and shadows in the upper 60%. Colour palette (Bubblegum): background #FFF4F8, panels #FFE4EE, deep tone #2B0F2E, accent #C2185B, support #F2B705. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`story-bg`**

```text
playful pop still life, hard flash light, glossy candy-toned surfaces, chunky geometric shapes, bold colour blocking, joyful and cheeky mood. Abstract vertical background, portrait 9:16, no product. Keep the top 15% and the bottom 35% calm and plain in #FFF4F8; put the visual interest in the middle. Colour palette (Bubblegum): background #FFF4F8, panels #FFE4EE, deep tone #2B0F2E, accent #C2185B, support #F2B705. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`hero`**

```text
playful pop still life, hard flash light, glossy candy-toned surfaces, chunky geometric shapes, bold colour blocking, joyful and cheeky mood. Wide website hero background, landscape 16:9, no product. Leave the centre third calm and empty so a name can sit on it; let surfaces, light and shadow fill the edges. Colour palette (Bubblegum): background #FFF4F8, panels #FFE4EE, deep tone #2B0F2E, accent #C2185B, support #F2B705. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`texture`**

```text
Seamless tileable texture of glossy terrazzo with large chips, photographed flat and straight on, even shadowless light, black and white only (greyscale), medium contrast, square 1:1, edges that tile without seams. No objects. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`pattern`**

```text
Seamless repeating pattern of playful squiggles and soft blobs, flat graphic design, black and white only (greyscale), evenly spaced, square 1:1, edges that tile without seams, refined and balanced. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`packaging`**

```text
playful pop still life, hard flash light, glossy candy-toned surfaces, chunky geometric shapes, bold colour blocking, joyful and cheeky mood. Product packaging set shot front-on and centred: a rigid gift box with its lid beside it, a paper shopping bag, folded tissue paper and a small swing tag on a string. Every item is completely blank and unprinted, in tones of #FFF4F8 and #C2185B with #F2B705 details, on a #FFE4EE surface. Colour palette (Bubblegum): background #FFF4F8, panels #FFE4EE, deep tone #2B0F2E, accent #C2185B, support #F2B705. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`motif`**

```text
a chunky wavy flower shape, flat vector-style graphic, a single colour #C2185B on a plain #FFF4F8 background, centred with a generous margin, crisp clean edges, square 1:1. Nothing that looks like a letter or a number. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-jewellery`**

```text
playful pop still life, hard flash light, glossy candy-toned surfaces, chunky geometric shapes, bold colour blocking, joyful and cheeky mood. Lifestyle photograph, portrait 4:5: a pair of hands resting on the surface, wearing a simple ring and a fine chain, cropped at the wrists. Candy-toned backdrops and glossy surfaces. Colour palette (Bubblegum): background #FFF4F8, panels #FFE4EE, deep tone #2B0F2E, accent #C2185B, support #F2B705. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-clothing`**

```text
playful pop still life, hard flash light, glossy candy-toned surfaces, chunky geometric shapes, bold colour blocking, joyful and cheeky mood. Lifestyle photograph, portrait 4:5: a softly folded garment and a garment on a plain hanger, no labels or tags visible. Candy-toned backdrops and glossy surfaces. Colour palette (Bubblegum): background #FFF4F8, panels #FFE4EE, deep tone #2B0F2E, accent #C2185B, support #F2B705. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-fragrance`**

```text
playful pop still life, hard flash light, glossy candy-toned surfaces, chunky geometric shapes, bold colour blocking, joyful and cheeky mood. Lifestyle photograph, portrait 4:5: an unlabelled glass perfume bottle with a plain cap, with one or two small props. Candy-toned backdrops and glossy surfaces. Colour palette (Bubblegum): background #FFF4F8, panels #FFE4EE, deep tone #2B0F2E, accent #C2185B, support #F2B705. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-home_decor`**

```text
playful pop still life, hard flash light, glossy candy-toned surfaces, chunky geometric shapes, bold colour blocking, joyful and cheeky mood. Lifestyle photograph, portrait 4:5: a quiet corner of a room with a vase, a few books with blank spines and a draped throw. Candy-toned backdrops and glossy surfaces. Colour palette (Bubblegum): background #FFF4F8, panels #FFE4EE, deep tone #2B0F2E, accent #C2185B, support #F2B705. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

<a id="street-edge"></a>
## Street Edge

Folder: `Smart CafeX/brand-assets/street_edge/`  
Raw, loud and sure of itself. Condensed caps, black and one acid accent.  
Categories: jewellery, clothing

| Role | Colour |
|---|---|
| Background | `#0E0E0E` |
| Panels | `#1A1A1A` |
| Deep tone | `#F2F2F2` |
| Accent | `#D7FF3A` |
| Support | `#FF5A4F` |

**`post-bg`**

```text
gritty urban still life, hard flash, concrete and brushed steel surfaces, near-black tones with a single acid accent, high contrast, raw and defiant mood. Abstract background for a social media post, portrait 4:5, no product. Keep the lower 40% of the frame calm, plain and evenly lit in #0E0E0E with nothing in it; place soft shapes, surfaces and shadows in the upper 60%. Colour palette (Blackout): background #0E0E0E, panels #1A1A1A, deep tone #F2F2F2, accent #D7FF3A, support #FF5A4F. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`story-bg`**

```text
gritty urban still life, hard flash, concrete and brushed steel surfaces, near-black tones with a single acid accent, high contrast, raw and defiant mood. Abstract vertical background, portrait 9:16, no product. Keep the top 15% and the bottom 35% calm and plain in #0E0E0E; put the visual interest in the middle. Colour palette (Blackout): background #0E0E0E, panels #1A1A1A, deep tone #F2F2F2, accent #D7FF3A, support #FF5A4F. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`hero`**

```text
gritty urban still life, hard flash, concrete and brushed steel surfaces, near-black tones with a single acid accent, high contrast, raw and defiant mood. Wide website hero background, landscape 16:9, no product. Leave the centre third calm and empty so a name can sit on it; let surfaces, light and shadow fill the edges. Colour palette (Blackout): background #0E0E0E, panels #1A1A1A, deep tone #F2F2F2, accent #D7FF3A, support #FF5A4F. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`texture`**

```text
Seamless tileable texture of rough poured concrete, photographed flat and straight on, even shadowless light, black and white only (greyscale), medium contrast, square 1:1, edges that tile without seams. No objects. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`pattern`**

```text
Seamless repeating pattern of halftone dots fading into diagonal stripes, flat graphic design, black and white only (greyscale), evenly spaced, square 1:1, edges that tile without seams, refined and balanced. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`packaging`**

```text
gritty urban still life, hard flash, concrete and brushed steel surfaces, near-black tones with a single acid accent, high contrast, raw and defiant mood. Product packaging set shot front-on and centred: a rigid gift box with its lid beside it, a paper shopping bag, folded tissue paper and a small swing tag on a string. Every item is completely blank and unprinted, in tones of #0E0E0E and #D7FF3A with #FF5A4F details, on a #1A1A1A surface. Colour palette (Blackout): background #0E0E0E, panels #1A1A1A, deep tone #F2F2F2, accent #D7FF3A, support #FF5A4F. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`motif`**

```text
a sharp angular lightning bolt shape, flat vector-style graphic, a single colour #D7FF3A on a plain #0E0E0E background, centred with a generous margin, crisp clean edges, square 1:1. Nothing that looks like a letter or a number. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-jewellery`**

```text
gritty urban still life, hard flash, concrete and brushed steel surfaces, near-black tones with a single acid accent, high contrast, raw and defiant mood. Lifestyle photograph, portrait 4:5: a pair of hands resting on the surface, wearing a simple ring and a fine chain, cropped at the wrists. Concrete, steel and asphalt textures. Colour palette (Blackout): background #0E0E0E, panels #1A1A1A, deep tone #F2F2F2, accent #D7FF3A, support #FF5A4F. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-clothing`**

```text
gritty urban still life, hard flash, concrete and brushed steel surfaces, near-black tones with a single acid accent, high contrast, raw and defiant mood. Lifestyle photograph, portrait 4:5: a softly folded garment and a garment on a plain hanger, no labels or tags visible. Concrete, steel and asphalt textures. Colour palette (Blackout): background #0E0E0E, panels #1A1A1A, deep tone #F2F2F2, accent #D7FF3A, support #FF5A4F. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

<a id="soft-romantic"></a>
## Soft Romantic

Folder: `Smart CafeX/brand-assets/soft_romantic/`  
Soft, graceful and personal. Blush tones, fine serifs, a gentle voice.  
Categories: jewellery, clothing, fragrance, home_decor

| Role | Colour |
|---|---|
| Background | `#FBF3F0` |
| Panels | `#F3E3DD` |
| Deep tone | `#3A2328` |
| Accent | `#9A4A5B` |
| Support | `#D2B2A2` |

**`post-bg`**

```text
soft romantic still life, diffused window light, blush and ivory draped fabric, petals and pearl tones, delicate shadows, dreamy and tender mood. Abstract background for a social media post, portrait 4:5, no product. Keep the lower 40% of the frame calm, plain and evenly lit in #FBF3F0 with nothing in it; place soft shapes, surfaces and shadows in the upper 60%. Colour palette (Blush): background #FBF3F0, panels #F3E3DD, deep tone #3A2328, accent #9A4A5B, support #D2B2A2. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`story-bg`**

```text
soft romantic still life, diffused window light, blush and ivory draped fabric, petals and pearl tones, delicate shadows, dreamy and tender mood. Abstract vertical background, portrait 9:16, no product. Keep the top 15% and the bottom 35% calm and plain in #FBF3F0; put the visual interest in the middle. Colour palette (Blush): background #FBF3F0, panels #F3E3DD, deep tone #3A2328, accent #9A4A5B, support #D2B2A2. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`hero`**

```text
soft romantic still life, diffused window light, blush and ivory draped fabric, petals and pearl tones, delicate shadows, dreamy and tender mood. Wide website hero background, landscape 16:9, no product. Leave the centre third calm and empty so a name can sit on it; let surfaces, light and shadow fill the edges. Colour palette (Blush): background #FBF3F0, panels #F3E3DD, deep tone #3A2328, accent #9A4A5B, support #D2B2A2. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`texture`**

```text
Seamless tileable texture of crushed silk, photographed flat and straight on, even shadowless light, black and white only (greyscale), medium contrast, square 1:1, edges that tile without seams. No objects. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`pattern`**

```text
Seamless repeating pattern of tiny scattered flowers and dots, flat graphic design, black and white only (greyscale), evenly spaced, square 1:1, edges that tile without seams, refined and balanced. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`packaging`**

```text
soft romantic still life, diffused window light, blush and ivory draped fabric, petals and pearl tones, delicate shadows, dreamy and tender mood. Product packaging set shot front-on and centred: a rigid gift box with its lid beside it, a paper shopping bag, folded tissue paper and a small swing tag on a string. Every item is completely blank and unprinted, in tones of #FBF3F0 and #9A4A5B with #D2B2A2 details, on a #F3E3DD surface. Colour palette (Blush): background #FBF3F0, panels #F3E3DD, deep tone #3A2328, accent #9A4A5B, support #D2B2A2. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`motif`**

```text
a delicate looping ribbon bow, flat vector-style graphic, a single colour #9A4A5B on a plain #FBF3F0 background, centred with a generous margin, crisp clean edges, square 1:1. Nothing that looks like a letter or a number. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-jewellery`**

```text
soft romantic still life, diffused window light, blush and ivory draped fabric, petals and pearl tones, delicate shadows, dreamy and tender mood. Lifestyle photograph, portrait 4:5: a pair of hands resting on the surface, wearing a simple ring and a fine chain, cropped at the wrists. Blush and ivory fabrics, soft folds. Colour palette (Blush): background #FBF3F0, panels #F3E3DD, deep tone #3A2328, accent #9A4A5B, support #D2B2A2. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-clothing`**

```text
soft romantic still life, diffused window light, blush and ivory draped fabric, petals and pearl tones, delicate shadows, dreamy and tender mood. Lifestyle photograph, portrait 4:5: a softly folded garment and a garment on a plain hanger, no labels or tags visible. Blush and ivory fabrics, soft folds. Colour palette (Blush): background #FBF3F0, panels #F3E3DD, deep tone #3A2328, accent #9A4A5B, support #D2B2A2. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-fragrance`**

```text
soft romantic still life, diffused window light, blush and ivory draped fabric, petals and pearl tones, delicate shadows, dreamy and tender mood. Lifestyle photograph, portrait 4:5: an unlabelled glass perfume bottle with a plain cap, with one or two small props. Blush and ivory fabrics, soft folds. Colour palette (Blush): background #FBF3F0, panels #F3E3DD, deep tone #3A2328, accent #9A4A5B, support #D2B2A2. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-home_decor`**

```text
soft romantic still life, diffused window light, blush and ivory draped fabric, petals and pearl tones, delicate shadows, dreamy and tender mood. Lifestyle photograph, portrait 4:5: a quiet corner of a room with a vase, a few books with blank spines and a draped throw. Blush and ivory fabrics, soft folds. Colour palette (Blush): background #FBF3F0, panels #F3E3DD, deep tone #3A2328, accent #9A4A5B, support #D2B2A2. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

<a id="artisan-earth"></a>
## Artisan Earth

Folder: `Smart CafeX/brand-assets/artisan_earth/`  
Warm, grounded and tactile. Earth tones, a characterful serif, a slower pace.  
Categories: jewellery, clothing, fragrance, home_decor

| Role | Colour |
|---|---|
| Background | `#F2EEE4` |
| Panels | `#E6DFD0` |
| Deep tone | `#2A2620` |
| Accent | `#5E5D33` |
| Support | `#B5653F` |

**`post-bg`**

```text
warm earthy still life, low golden afternoon light, raw linen, unglazed clay and wood surfaces, olive and ochre tones, tactile textures, calm and grounded mood. Abstract background for a social media post, portrait 4:5, no product. Keep the lower 40% of the frame calm, plain and evenly lit in #F2EEE4 with nothing in it; place soft shapes, surfaces and shadows in the upper 60%. Colour palette (Olive and clay): background #F2EEE4, panels #E6DFD0, deep tone #2A2620, accent #5E5D33, support #B5653F. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`story-bg`**

```text
warm earthy still life, low golden afternoon light, raw linen, unglazed clay and wood surfaces, olive and ochre tones, tactile textures, calm and grounded mood. Abstract vertical background, portrait 9:16, no product. Keep the top 15% and the bottom 35% calm and plain in #F2EEE4; put the visual interest in the middle. Colour palette (Olive and clay): background #F2EEE4, panels #E6DFD0, deep tone #2A2620, accent #5E5D33, support #B5653F. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`hero`**

```text
warm earthy still life, low golden afternoon light, raw linen, unglazed clay and wood surfaces, olive and ochre tones, tactile textures, calm and grounded mood. Wide website hero background, landscape 16:9, no product. Leave the centre third calm and empty so a name can sit on it; let surfaces, light and shadow fill the edges. Colour palette (Olive and clay): background #F2EEE4, panels #E6DFD0, deep tone #2A2620, accent #5E5D33, support #B5653F. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`texture`**

```text
Seamless tileable texture of rough rag paper with visible fibres, photographed flat and straight on, even shadowless light, black and white only (greyscale), medium contrast, square 1:1, edges that tile without seams. No objects. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`pattern`**

```text
Seamless repeating pattern of loose drawn leaf and seed shapes, flat graphic design, black and white only (greyscale), evenly spaced, square 1:1, edges that tile without seams, refined and balanced. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`packaging`**

```text
warm earthy still life, low golden afternoon light, raw linen, unglazed clay and wood surfaces, olive and ochre tones, tactile textures, calm and grounded mood. Product packaging set shot front-on and centred: a rigid gift box with its lid beside it, a paper shopping bag, folded tissue paper and a small swing tag on a string. Every item is completely blank and unprinted, in tones of #F2EEE4 and #5E5D33 with #B5653F details, on a #E6DFD0 surface. Colour palette (Olive and clay): background #F2EEE4, panels #E6DFD0, deep tone #2A2620, accent #5E5D33, support #B5653F. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`motif`**

```text
a rounded pebble shape with a soft inner ring, flat vector-style graphic, a single colour #5E5D33 on a plain #F2EEE4 background, centred with a generous margin, crisp clean edges, square 1:1. Nothing that looks like a letter or a number. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-jewellery`**

```text
warm earthy still life, low golden afternoon light, raw linen, unglazed clay and wood surfaces, olive and ochre tones, tactile textures, calm and grounded mood. Lifestyle photograph, portrait 4:5: a pair of hands resting on the surface, wearing a simple ring and a fine chain, cropped at the wrists. Raw fabric, clay and wood surfaces. Colour palette (Olive and clay): background #F2EEE4, panels #E6DFD0, deep tone #2A2620, accent #5E5D33, support #B5653F. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-clothing`**

```text
warm earthy still life, low golden afternoon light, raw linen, unglazed clay and wood surfaces, olive and ochre tones, tactile textures, calm and grounded mood. Lifestyle photograph, portrait 4:5: a softly folded garment and a garment on a plain hanger, no labels or tags visible. Raw fabric, clay and wood surfaces. Colour palette (Olive and clay): background #F2EEE4, panels #E6DFD0, deep tone #2A2620, accent #5E5D33, support #B5653F. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-fragrance`**

```text
warm earthy still life, low golden afternoon light, raw linen, unglazed clay and wood surfaces, olive and ochre tones, tactile textures, calm and grounded mood. Lifestyle photograph, portrait 4:5: an unlabelled glass perfume bottle with a plain cap, with one or two small props. Raw fabric, clay and wood surfaces. Colour palette (Olive and clay): background #F2EEE4, panels #E6DFD0, deep tone #2A2620, accent #5E5D33, support #B5653F. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-home_decor`**

```text
warm earthy still life, low golden afternoon light, raw linen, unglazed clay and wood surfaces, olive and ochre tones, tactile textures, calm and grounded mood. Lifestyle photograph, portrait 4:5: a quiet corner of a room with a vase, a few books with blank spines and a draped throw. Raw fabric, clay and wood surfaces. Colour palette (Olive and clay): background #F2EEE4, panels #E6DFD0, deep tone #2A2620, accent #5E5D33, support #B5653F. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

<a id="modern-heritage"></a>
## Modern Heritage

Folder: `Smart CafeX/brand-assets/modern_heritage/`  
Tradition, made contemporary. Vivid celebration tones in a clean, modern frame.  
Categories: jewellery, clothing, fragrance, home_decor

| Role | Colour |
|---|---|
| Background | `#F6F1E6` |
| Panels | `#EEE4D0` |
| Deep tone | `#1B1F3B` |
| Accent | `#2D3A8C` |
| Support | `#D99A14` |

**`post-bg`**

```text
contemporary festive still life, warm directional light, block printed textile and brass surfaces, indigo marigold and madder red tones, clean modern composition, vivid and rooted mood. Abstract background for a social media post, portrait 4:5, no product. Keep the lower 40% of the frame calm, plain and evenly lit in #F6F1E6 with nothing in it; place soft shapes, surfaces and shadows in the upper 60%. Colour palette (Indigo and marigold): background #F6F1E6, panels #EEE4D0, deep tone #1B1F3B, accent #2D3A8C, support #D99A14. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`story-bg`**

```text
contemporary festive still life, warm directional light, block printed textile and brass surfaces, indigo marigold and madder red tones, clean modern composition, vivid and rooted mood. Abstract vertical background, portrait 9:16, no product. Keep the top 15% and the bottom 35% calm and plain in #F6F1E6; put the visual interest in the middle. Colour palette (Indigo and marigold): background #F6F1E6, panels #EEE4D0, deep tone #1B1F3B, accent #2D3A8C, support #D99A14. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`hero`**

```text
contemporary festive still life, warm directional light, block printed textile and brass surfaces, indigo marigold and madder red tones, clean modern composition, vivid and rooted mood. Wide website hero background, landscape 16:9, no product. Leave the centre third calm and empty so a name can sit on it; let surfaces, light and shadow fill the edges. Colour palette (Indigo and marigold): background #F6F1E6, panels #EEE4D0, deep tone #1B1F3B, accent #2D3A8C, support #D99A14. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`texture`**

```text
Seamless tileable texture of block printed cotton, photographed flat and straight on, even shadowless light, black and white only (greyscale), medium contrast, square 1:1, edges that tile without seams. No objects. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`pattern`**

```text
Seamless repeating pattern of block print paisley and small florals, flat graphic design, black and white only (greyscale), evenly spaced, square 1:1, edges that tile without seams, refined and balanced. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`packaging`**

```text
contemporary festive still life, warm directional light, block printed textile and brass surfaces, indigo marigold and madder red tones, clean modern composition, vivid and rooted mood. Product packaging set shot front-on and centred: a rigid gift box with its lid beside it, a paper shopping bag, folded tissue paper and a small swing tag on a string. Every item is completely blank and unprinted, in tones of #F6F1E6 and #2D3A8C with #D99A14 details, on a #EEE4D0 surface. Colour palette (Indigo and marigold): background #F6F1E6, panels #EEE4D0, deep tone #1B1F3B, accent #2D3A8C, support #D99A14. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`motif`**

```text
a lotus-like symmetrical flower shape, flat vector-style graphic, a single colour #2D3A8C on a plain #F6F1E6 background, centred with a generous margin, crisp clean edges, square 1:1. Nothing that looks like a letter or a number. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-jewellery`**

```text
contemporary festive still life, warm directional light, block printed textile and brass surfaces, indigo marigold and madder red tones, clean modern composition, vivid and rooted mood. Lifestyle photograph, portrait 4:5: a pair of hands resting on the surface, wearing a simple ring and a fine chain, cropped at the wrists. Printed textiles and brass in clean, modern compositions. Colour palette (Indigo and marigold): background #F6F1E6, panels #EEE4D0, deep tone #1B1F3B, accent #2D3A8C, support #D99A14. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-clothing`**

```text
contemporary festive still life, warm directional light, block printed textile and brass surfaces, indigo marigold and madder red tones, clean modern composition, vivid and rooted mood. Lifestyle photograph, portrait 4:5: a softly folded garment and a garment on a plain hanger, no labels or tags visible. Printed textiles and brass in clean, modern compositions. Colour palette (Indigo and marigold): background #F6F1E6, panels #EEE4D0, deep tone #1B1F3B, accent #2D3A8C, support #D99A14. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-fragrance`**

```text
contemporary festive still life, warm directional light, block printed textile and brass surfaces, indigo marigold and madder red tones, clean modern composition, vivid and rooted mood. Lifestyle photograph, portrait 4:5: an unlabelled glass perfume bottle with a plain cap, with one or two small props. Printed textiles and brass in clean, modern compositions. Colour palette (Indigo and marigold): background #F6F1E6, panels #EEE4D0, deep tone #1B1F3B, accent #2D3A8C, support #D99A14. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-home_decor`**

```text
contemporary festive still life, warm directional light, block printed textile and brass surfaces, indigo marigold and madder red tones, clean modern composition, vivid and rooted mood. Lifestyle photograph, portrait 4:5: a quiet corner of a room with a vase, a few books with blank spines and a draped throw. Printed textiles and brass in clean, modern compositions. Colour palette (Indigo and marigold): background #F6F1E6, panels #EEE4D0, deep tone #1B1F3B, accent #2D3A8C, support #D99A14. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

<a id="apothecary"></a>
## Apothecary

Folder: `Smart CafeX/brand-assets/apothecary/`  
Precise, sensory and calm. Plain labels, amber glass, measured words.  
Categories: fragrance, home_decor

| Role | Colour |
|---|---|
| Background | `#EFE8DC` |
| Panels | `#E2D7C4` |
| Deep tone | `#1E1B17` |
| Accent | `#5C4A32` |
| Support | `#9C8463` |

**`post-bg`**

```text
apothecary still life, soft overcast light, amber glass and kraft paper, matte stone and steel surfaces, muted earth tones, orderly precise composition, calm and studied mood. Abstract background for a social media post, portrait 4:5, no product. Keep the lower 40% of the frame calm, plain and evenly lit in #EFE8DC with nothing in it; place soft shapes, surfaces and shadows in the upper 60%. Colour palette (Kraft): background #EFE8DC, panels #E2D7C4, deep tone #1E1B17, accent #5C4A32, support #9C8463. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`story-bg`**

```text
apothecary still life, soft overcast light, amber glass and kraft paper, matte stone and steel surfaces, muted earth tones, orderly precise composition, calm and studied mood. Abstract vertical background, portrait 9:16, no product. Keep the top 15% and the bottom 35% calm and plain in #EFE8DC; put the visual interest in the middle. Colour palette (Kraft): background #EFE8DC, panels #E2D7C4, deep tone #1E1B17, accent #5C4A32, support #9C8463. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`hero`**

```text
apothecary still life, soft overcast light, amber glass and kraft paper, matte stone and steel surfaces, muted earth tones, orderly precise composition, calm and studied mood. Wide website hero background, landscape 16:9, no product. Leave the centre third calm and empty so a name can sit on it; let surfaces, light and shadow fill the edges. Colour palette (Kraft): background #EFE8DC, panels #E2D7C4, deep tone #1E1B17, accent #5C4A32, support #9C8463. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`texture`**

```text
Seamless tileable texture of kraft paper, photographed flat and straight on, even shadowless light, black and white only (greyscale), medium contrast, square 1:1, edges that tile without seams. No objects. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`pattern`**

```text
Seamless repeating pattern of a fine dotted grid like a lab notebook page, flat graphic design, black and white only (greyscale), evenly spaced, square 1:1, edges that tile without seams, refined and balanced. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`packaging`**

```text
apothecary still life, soft overcast light, amber glass and kraft paper, matte stone and steel surfaces, muted earth tones, orderly precise composition, calm and studied mood. Product packaging set shot front-on and centred: a rigid gift box with its lid beside it, a paper shopping bag, folded tissue paper and a small swing tag on a string. Every item is completely blank and unprinted, in tones of #EFE8DC and #5C4A32 with #9C8463 details, on a #E2D7C4 surface. Colour palette (Kraft): background #EFE8DC, panels #E2D7C4, deep tone #1E1B17, accent #5C4A32, support #9C8463. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`motif`**

```text
a simple botanical sprig drawn with a single line, flat vector-style graphic, a single colour #5C4A32 on a plain #EFE8DC background, centred with a generous margin, crisp clean edges, square 1:1. Nothing that looks like a letter or a number. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-fragrance`**

```text
apothecary still life, soft overcast light, amber glass and kraft paper, matte stone and steel surfaces, muted earth tones, orderly precise composition, calm and studied mood. Lifestyle photograph, portrait 4:5: an unlabelled glass perfume bottle with a plain cap, with one or two small props. Amber glass, kraft paper, matte stone and steel. Colour palette (Kraft): background #EFE8DC, panels #E2D7C4, deep tone #1E1B17, accent #5C4A32, support #9C8463. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-home_decor`**

```text
apothecary still life, soft overcast light, amber glass and kraft paper, matte stone and steel surfaces, muted earth tones, orderly precise composition, calm and studied mood. Lifestyle photograph, portrait 4:5: a quiet corner of a room with a vase, a few books with blank spines and a draped throw. Amber glass, kraft paper, matte stone and steel. Colour palette (Kraft): background #EFE8DC, panels #E2D7C4, deep tone #1E1B17, accent #5C4A32, support #9C8463. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

<a id="calm-airy"></a>
## Calm & Airy

Folder: `Smart CafeX/brand-assets/calm_airy/`  
Quiet, airy and balanced. Pale tones, light type, room to breathe.  
Categories: jewellery, clothing, fragrance, home_decor

| Role | Colour |
|---|---|
| Background | `#F4F1EC` |
| Panels | `#E9E4DC` |
| Deep tone | `#2B2926` |
| Accent | `#686055` |
| Support | `#A9A08F` |

**`post-bg`**

```text
serene japandi still life, soft diffused daylight, pale oak, rice paper and stoneware surfaces, warm ivory and ash tones, lots of empty space, airy and balanced mood. Abstract background for a social media post, portrait 4:5, no product. Keep the lower 40% of the frame calm, plain and evenly lit in #F4F1EC with nothing in it; place soft shapes, surfaces and shadows in the upper 60%. Colour palette (Linen): background #F4F1EC, panels #E9E4DC, deep tone #2B2926, accent #686055, support #A9A08F. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`story-bg`**

```text
serene japandi still life, soft diffused daylight, pale oak, rice paper and stoneware surfaces, warm ivory and ash tones, lots of empty space, airy and balanced mood. Abstract vertical background, portrait 9:16, no product. Keep the top 15% and the bottom 35% calm and plain in #F4F1EC; put the visual interest in the middle. Colour palette (Linen): background #F4F1EC, panels #E9E4DC, deep tone #2B2926, accent #686055, support #A9A08F. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`hero`**

```text
serene japandi still life, soft diffused daylight, pale oak, rice paper and stoneware surfaces, warm ivory and ash tones, lots of empty space, airy and balanced mood. Wide website hero background, landscape 16:9, no product. Leave the centre third calm and empty so a name can sit on it; let surfaces, light and shadow fill the edges. Colour palette (Linen): background #F4F1EC, panels #E9E4DC, deep tone #2B2926, accent #686055, support #A9A08F. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`texture`**

```text
Seamless tileable texture of rice paper with long fibres, photographed flat and straight on, even shadowless light, black and white only (greyscale), medium contrast, square 1:1, edges that tile without seams. No objects. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`pattern`**

```text
Seamless repeating pattern of loose brush-stroke circles, flat graphic design, black and white only (greyscale), evenly spaced, square 1:1, edges that tile without seams, refined and balanced. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`packaging`**

```text
serene japandi still life, soft diffused daylight, pale oak, rice paper and stoneware surfaces, warm ivory and ash tones, lots of empty space, airy and balanced mood. Product packaging set shot front-on and centred: a rigid gift box with its lid beside it, a paper shopping bag, folded tissue paper and a small swing tag on a string. Every item is completely blank and unprinted, in tones of #F4F1EC and #686055 with #A9A08F details, on a #E9E4DC surface. Colour palette (Linen): background #F4F1EC, panels #E9E4DC, deep tone #2B2926, accent #686055, support #A9A08F. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`motif`**

```text
a single open brush circle, flat vector-style graphic, a single colour #686055 on a plain #F4F1EC background, centred with a generous margin, crisp clean edges, square 1:1. Nothing that looks like a letter or a number. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-jewellery`**

```text
serene japandi still life, soft diffused daylight, pale oak, rice paper and stoneware surfaces, warm ivory and ash tones, lots of empty space, airy and balanced mood. Lifestyle photograph, portrait 4:5: a pair of hands resting on the surface, wearing a simple ring and a fine chain, cropped at the wrists. Pale oak, paper and stoneware surfaces. Colour palette (Linen): background #F4F1EC, panels #E9E4DC, deep tone #2B2926, accent #686055, support #A9A08F. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-clothing`**

```text
serene japandi still life, soft diffused daylight, pale oak, rice paper and stoneware surfaces, warm ivory and ash tones, lots of empty space, airy and balanced mood. Lifestyle photograph, portrait 4:5: a softly folded garment and a garment on a plain hanger, no labels or tags visible. Pale oak, paper and stoneware surfaces. Colour palette (Linen): background #F4F1EC, panels #E9E4DC, deep tone #2B2926, accent #686055, support #A9A08F. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-fragrance`**

```text
serene japandi still life, soft diffused daylight, pale oak, rice paper and stoneware surfaces, warm ivory and ash tones, lots of empty space, airy and balanced mood. Lifestyle photograph, portrait 4:5: an unlabelled glass perfume bottle with a plain cap, with one or two small props. Pale oak, paper and stoneware surfaces. Colour palette (Linen): background #F4F1EC, panels #E9E4DC, deep tone #2B2926, accent #686055, support #A9A08F. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-home_decor`**

```text
serene japandi still life, soft diffused daylight, pale oak, rice paper and stoneware surfaces, warm ivory and ash tones, lots of empty space, airy and balanced mood. Lifestyle photograph, portrait 4:5: a quiet corner of a room with a vase, a few books with blank spines and a draped throw. Pale oak, paper and stoneware surfaces. Colour palette (Linen): background #F4F1EC, panels #E9E4DC, deep tone #2B2926, accent #686055, support #A9A08F. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

<a id="bold-maximal"></a>
## Bold Maximal

Folder: `Smart CafeX/brand-assets/bold_maximal/`  
More is more. Jewel tones, pattern, drama and a serif with swagger.  
Categories: jewellery, clothing, fragrance, home_decor

| Role | Colour |
|---|---|
| Background | `#FBF6EE` |
| Panels | `#F1E6D6` |
| Deep tone | `#1C1023` |
| Accent | `#0F6B4F` |
| Support | `#B8185A` |

**`post-bg`**

```text
maximalist still life, dramatic warm spotlight, velvet, brocade and gilded surfaces, emerald fuchsia and saffron jewel tones, layered pattern, opulent and theatrical mood. Abstract background for a social media post, portrait 4:5, no product. Keep the lower 40% of the frame calm, plain and evenly lit in #FBF6EE with nothing in it; place soft shapes, surfaces and shadows in the upper 60%. Colour palette (Jewel box): background #FBF6EE, panels #F1E6D6, deep tone #1C1023, accent #0F6B4F, support #B8185A. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`story-bg`**

```text
maximalist still life, dramatic warm spotlight, velvet, brocade and gilded surfaces, emerald fuchsia and saffron jewel tones, layered pattern, opulent and theatrical mood. Abstract vertical background, portrait 9:16, no product. Keep the top 15% and the bottom 35% calm and plain in #FBF6EE; put the visual interest in the middle. Colour palette (Jewel box): background #FBF6EE, panels #F1E6D6, deep tone #1C1023, accent #0F6B4F, support #B8185A. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`hero`**

```text
maximalist still life, dramatic warm spotlight, velvet, brocade and gilded surfaces, emerald fuchsia and saffron jewel tones, layered pattern, opulent and theatrical mood. Wide website hero background, landscape 16:9, no product. Leave the centre third calm and empty so a name can sit on it; let surfaces, light and shadow fill the edges. Colour palette (Jewel box): background #FBF6EE, panels #F1E6D6, deep tone #1C1023, accent #0F6B4F, support #B8185A. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`texture`**

```text
Seamless tileable texture of crushed velvet, photographed flat and straight on, even shadowless light, black and white only (greyscale), medium contrast, square 1:1, edges that tile without seams. No objects. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`pattern`**

```text
Seamless repeating pattern of lush leaves, fruit and birds, flat graphic design, black and white only (greyscale), evenly spaced, square 1:1, edges that tile without seams, refined and balanced. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`packaging`**

```text
maximalist still life, dramatic warm spotlight, velvet, brocade and gilded surfaces, emerald fuchsia and saffron jewel tones, layered pattern, opulent and theatrical mood. Product packaging set shot front-on and centred: a rigid gift box with its lid beside it, a paper shopping bag, folded tissue paper and a small swing tag on a string. Every item is completely blank and unprinted, in tones of #FBF6EE and #0F6B4F with #B8185A details, on a #F1E6D6 surface. Colour palette (Jewel box): background #FBF6EE, panels #F1E6D6, deep tone #1C1023, accent #0F6B4F, support #B8185A. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`motif`**

```text
a dramatic sunburst, flat vector-style graphic, a single colour #0F6B4F on a plain #FBF6EE background, centred with a generous margin, crisp clean edges, square 1:1. Nothing that looks like a letter or a number. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-jewellery`**

```text
maximalist still life, dramatic warm spotlight, velvet, brocade and gilded surfaces, emerald fuchsia and saffron jewel tones, layered pattern, opulent and theatrical mood. Lifestyle photograph, portrait 4:5: a pair of hands resting on the surface, wearing a simple ring and a fine chain, cropped at the wrists. Velvet, brocade and gilded surfaces. Colour palette (Jewel box): background #FBF6EE, panels #F1E6D6, deep tone #1C1023, accent #0F6B4F, support #B8185A. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-clothing`**

```text
maximalist still life, dramatic warm spotlight, velvet, brocade and gilded surfaces, emerald fuchsia and saffron jewel tones, layered pattern, opulent and theatrical mood. Lifestyle photograph, portrait 4:5: a softly folded garment and a garment on a plain hanger, no labels or tags visible. Velvet, brocade and gilded surfaces. Colour palette (Jewel box): background #FBF6EE, panels #F1E6D6, deep tone #1C1023, accent #0F6B4F, support #B8185A. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-fragrance`**

```text
maximalist still life, dramatic warm spotlight, velvet, brocade and gilded surfaces, emerald fuchsia and saffron jewel tones, layered pattern, opulent and theatrical mood. Lifestyle photograph, portrait 4:5: an unlabelled glass perfume bottle with a plain cap, with one or two small props. Velvet, brocade and gilded surfaces. Colour palette (Jewel box): background #FBF6EE, panels #F1E6D6, deep tone #1C1023, accent #0F6B4F, support #B8185A. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-home_decor`**

```text
maximalist still life, dramatic warm spotlight, velvet, brocade and gilded surfaces, emerald fuchsia and saffron jewel tones, layered pattern, opulent and theatrical mood. Lifestyle photograph, portrait 4:5: a quiet corner of a room with a vase, a few books with blank spines and a draped throw. Velvet, brocade and gilded surfaces. Colour palette (Jewel box): background #FBF6EE, panels #F1E6D6, deep tone #1C1023, accent #0F6B4F, support #B8185A. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

<a id="classic-timeless"></a>
## Classic Timeless

Folder: `Smart CafeX/brand-assets/classic_timeless/`  
Polished, trusted and enduring. Navy, cream, a classic serif and good manners.  
Categories: jewellery, clothing, fragrance, home_decor

| Role | Colour |
|---|---|
| Background | `#F7F5F0` |
| Panels | `#ECE8DF` |
| Deep tone | `#141C2E` |
| Accent | `#1F2F55` |
| Support | `#9E2B33` |

**`post-bg`**

```text
classic polished still life, soft warm studio light, navy wool, cream paper and dark polished wood surfaces, navy cream and burgundy tones, balanced traditional composition, refined and composed mood. Abstract background for a social media post, portrait 4:5, no product. Keep the lower 40% of the frame calm, plain and evenly lit in #F7F5F0 with nothing in it; place soft shapes, surfaces and shadows in the upper 60%. Colour palette (Navy): background #F7F5F0, panels #ECE8DF, deep tone #141C2E, accent #1F2F55, support #9E2B33. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`story-bg`**

```text
classic polished still life, soft warm studio light, navy wool, cream paper and dark polished wood surfaces, navy cream and burgundy tones, balanced traditional composition, refined and composed mood. Abstract vertical background, portrait 9:16, no product. Keep the top 15% and the bottom 35% calm and plain in #F7F5F0; put the visual interest in the middle. Colour palette (Navy): background #F7F5F0, panels #ECE8DF, deep tone #141C2E, accent #1F2F55, support #9E2B33. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`hero`**

```text
classic polished still life, soft warm studio light, navy wool, cream paper and dark polished wood surfaces, navy cream and burgundy tones, balanced traditional composition, refined and composed mood. Wide website hero background, landscape 16:9, no product. Leave the centre third calm and empty so a name can sit on it; let surfaces, light and shadow fill the edges. Colour palette (Navy): background #F7F5F0, panels #ECE8DF, deep tone #141C2E, accent #1F2F55, support #9E2B33. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`texture`**

```text
Seamless tileable texture of herringbone wool, photographed flat and straight on, even shadowless light, black and white only (greyscale), medium contrast, square 1:1, edges that tile without seams. No objects. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`pattern`**

```text
Seamless repeating pattern of small regular foulard diamonds, flat graphic design, black and white only (greyscale), evenly spaced, square 1:1, edges that tile without seams, refined and balanced. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`packaging`**

```text
classic polished still life, soft warm studio light, navy wool, cream paper and dark polished wood surfaces, navy cream and burgundy tones, balanced traditional composition, refined and composed mood. Product packaging set shot front-on and centred: a rigid gift box with its lid beside it, a paper shopping bag, folded tissue paper and a small swing tag on a string. Every item is completely blank and unprinted, in tones of #F7F5F0 and #1F2F55 with #9E2B33 details, on a #ECE8DF surface. Colour palette (Navy): background #F7F5F0, panels #ECE8DF, deep tone #141C2E, accent #1F2F55, support #9E2B33. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`motif`**

```text
a laurel wreath without any letters inside, flat vector-style graphic, a single colour #1F2F55 on a plain #F7F5F0 background, centred with a generous margin, crisp clean edges, square 1:1. Nothing that looks like a letter or a number. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-jewellery`**

```text
classic polished still life, soft warm studio light, navy wool, cream paper and dark polished wood surfaces, navy cream and burgundy tones, balanced traditional composition, refined and composed mood. Lifestyle photograph, portrait 4:5: a pair of hands resting on the surface, wearing a simple ring and a fine chain, cropped at the wrists. Navy wool, cream paper and dark polished wood. Colour palette (Navy): background #F7F5F0, panels #ECE8DF, deep tone #141C2E, accent #1F2F55, support #9E2B33. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-clothing`**

```text
classic polished still life, soft warm studio light, navy wool, cream paper and dark polished wood surfaces, navy cream and burgundy tones, balanced traditional composition, refined and composed mood. Lifestyle photograph, portrait 4:5: a softly folded garment and a garment on a plain hanger, no labels or tags visible. Navy wool, cream paper and dark polished wood. Colour palette (Navy): background #F7F5F0, panels #ECE8DF, deep tone #141C2E, accent #1F2F55, support #9E2B33. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-fragrance`**

```text
classic polished still life, soft warm studio light, navy wool, cream paper and dark polished wood surfaces, navy cream and burgundy tones, balanced traditional composition, refined and composed mood. Lifestyle photograph, portrait 4:5: an unlabelled glass perfume bottle with a plain cap, with one or two small props. Navy wool, cream paper and dark polished wood. Colour palette (Navy): background #F7F5F0, panels #ECE8DF, deep tone #141C2E, accent #1F2F55, support #9E2B33. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```

**`mood-home_decor`**

```text
classic polished still life, soft warm studio light, navy wool, cream paper and dark polished wood surfaces, navy cream and burgundy tones, balanced traditional composition, refined and composed mood. Lifestyle photograph, portrait 4:5: a quiet corner of a room with a vase, a few books with blank spines and a draped throw. Navy wool, cream paper and dark polished wood. Colour palette (Navy): background #F7F5F0, panels #ECE8DF, deep tone #141C2E, accent #1F2F55, support #9E2B33. Absolutely no text, letters, numbers, words, logos, labels, signage, watermarks or signatures anywhere in the image. No people's faces.
```
