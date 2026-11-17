# Marketplace illustrative crop photographs

Listings prefer the seller's usable uploaded photograph. If a listing has no photo, its upload cannot be loaded, or either decoded image dimension is below 32 pixels, the marketplace uses a locally bundled crop photograph only when the listing name identifies a supported crop unambiguously. Tiny pixel/test images do not provide useful produce detail; their original upload bytes remain untouched. These are **illustrative crop images, not photographs of the seller's goods**, and do not establish variety, grade, ripeness, origin, safety or condition. Unknown and mixed crop names use the neutral produce placeholder.

The visible label is `Illustrative crop image` / `ফসলের উদাহরণ ছবি`. The credit line identifies the photographer and license. The public [photo credits page](/crops/credits.html) supplies the original file and license links; its offline copy and machine-readable record are bundled under `apps/web/public/crops/`. No remote photograph requests are needed after deployment.

## Matching and upload behavior

- `apps/web/src/lib/crop-images.ts` uses normalized, case-insensitive whole Unicode tokens (letters, combining marks and digits), rather than JavaScript `\b` or substring matching. Both English and Bangla aliases are supported.
- Supported crops: tomato, potato, rice/paddy, maize/corn, onion, carrot, eggplant/brinjal/aubergine, cucumber, chilli, bell pepper/capsicum, banana, mango, pumpkin, butternut squash, apple, strawberry, grape, orange, peach and cherry.
- Longer phrases take precedence when they overlap (`cherry tomato`, `chilli pepper`). Multiple distinct crops stay generic. Unsupported compounds (`sweet potato`, `custard apple`, `black pepper`, `চাল কুমড়া`) and processed products/seeds stay generic. The broad marketplace category and free-text description never override the product name.
- Public uploads use their original image source. Private uploads retain authenticated fetch-to-blob loading and revoke their object URLs on replacement or unmount. The image instance is keyed to product, image, source, visibility and account, preventing an old loaded/error state from appearing after a change. Aborted fetches cannot publish a late blob or error.
- A broken stock image falls back once to the neutral placeholder. A still-loading private seller image shows loading text rather than implying that the stock photo is the seller's image.
- Decoded seller images smaller than 32 pixels on either side use the labelled crop fallback, including existing 1×1 black/transparent test uploads. An image with both dimensions at least 32 pixels retains upload priority. This is display handling only: no upload or listing data is overwritten.

## Source and license record

All 20 photos were downloaded from Wikimedia Commons on **17 November 2026**. Per-file source pages and `imageinfo` license/author metadata were checked through the Commons API. Licenses are Creative Commons BY (2.0, 4.0), BY-SA (2.0, 3.0, 4.0), or public-domain releases. The precise license belongs to each photograph, not to this whole application. Preserve attribution and the applicable photo license when redistributing the assets or adaptations. The downloaded Commons thumbnails are displayed using CSS `object-fit: cover`; no photo retouching or generation was performed.

The authoritative bundled inventory is `apps/web/public/crops/credits.json`, including original filename, author, source URL, license URL, download URL, retrieval date and SHA-256. `apps/web/public/crops/credits.html` provides the same information in a readable public page. See also [Wikimedia's reuse guidance](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia).

## Visual and functional verification

A contact sheet of every downloaded photo was visually inspected against its assigned crop. A candidate labelled as peach by Commons metadata actually showed a wood cross-section; it was rejected and replaced with **Autumn Red peaches**, photographed by Jack Dykinga/USDA (public domain). The final peach photo was inspected individually. The retained images show the named produce; some depict several varieties, and none are evidence about an individual listing.

`tests/crop-images.test.ts` checks English/Bangla aliases, Unicode boundaries, compound exclusions, mixed/unknown crops and bundled attribution/asset availability. `e2e/crop-images.spec.ts` checks visible bilingual stock labels, seller-image priority, failed upload and stock-photo fallbacks, tiny black/transparent/narrow/short uploads, the 32-pixel boundary, thumbnail/source changes, authenticated private blobs, late responses and object-URL revocation. Valid seller-image fixtures use full-size bundled JPEG photos. API routes in these focused browser tests use controlled listing fixtures; they do not prove backend image access control.

Verified on 17 November 2026:

- `npm test`: **4 files, 74 tests passed**, including **56 crop-image tests**.
- `npx playwright test e2e/crop-images.spec.ts --project=chromium`: **5 passed** against the existing local test app on port 3300 (Microsoft Edge Chromium).
- `npm run typecheck`: passed.
- Scoped ESLint of the matcher, shared image component and new test files: passed.

The existing Vite CommonJS-configuration notice and Playwright terminal-color notice remain non-failing tooling warnings. Full app build, API and integrated browser results belong in the main status report.
