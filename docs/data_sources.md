# Sources and permitted-use records

Checked 2026-11-16. Initial prices and rainfall values are authored synthetic fixtures and not historical evidence.

- PlantVillage: https://huggingface.co/datasets/mohanty/PlantVillage and https://github.com/spMohanty/PlantVillage-Dataset. Dataset card declares CC BY-SA 3.0. The preparation script retains the card, official leaf map, split manifests, commit hashes, image URLs/checksums and attribution under data/plantvillage. This is a small controlled-image research subset, not a representative Bangladesh field sample.
- Open-Meteo: https://open-meteo.com/en/docs. Live adapter retrieves hourly precipitation with UTC timestamps. CC BY 4.0 attribution is displayed. Check commercial service terms before commercial deployment. Provider does not expose original model issuance time in this response; that field stays null.
- FFWC: https://ww2.ffwc.gov.bd/. Original official reference only; no machine feed, bulletin freshness claims, invented river alerts or farm flood polygons.
- DAM: https://market.dam.gov.bd/. Original report reference. Private CSV imports require declared source, permission confirmation, date, type, unit and grade. No assumed public API or unauthorized scraping.
- Maps: https://www.openstreetmap.org/copyright; raster tiles use the standard service and attribution. Production traffic must comply with https://operations.osmfoundation.org/policies/tiles/ or use a contracted tile provider.
- Area lookup (added 2026-11-17): https://open-meteo.com/en/docs/geocoding-api, using the GeoNames-based worldwide place-name service through an authenticated backend proxy. Queries are only submitted when Search is pressed. Results identify named places and do not establish surveyed farm boundaries. Original coordinates and country/admin labels are retained in the selection UI; saving a point remains farmer-reported location data.

Dataset license declarations are not an independent legal review. Preserve attribution and applicable share-alike terms when redistributing source images or derived artifacts.
