# Selecting a farm area

Open **FloodCrop AI** for the selected plot. Its area picker supports:

1. Search a town, district or village. Results are global; adding a country, such as `Sylhet, Bangladesh`, helps disambiguate names.
2. Select a search result, click a point on the map, or drag the green pin.
3. Alternatively enter latitude/longitude and press **Use coordinates**. Zero coordinates are valid.
4. Tick consent and press **Save area & use live weather**. This updates the existing farm without changing its name or plot IDs. The selected point persists in PostgreSQL and becomes the default weather location on return visits.

The same selector is available when creating farms under **Farms & plots**. A district-only farm can still be created without precise coordinates by clearing the point and entering its district/area name.

Named-place lookup uses Open-Meteo Geocoding / GeoNames through the authenticated `/api/v1/locations/search` proxy. Lookup failures return an unavailable message; the coordinate controls remain usable. The map uses OpenStreetMap tiles and requires WebGL; search and coordinates remain available if the map cannot render.

Saving uses the owner-checked `/api/v1/farms/{id}/location` endpoint and requires explicit location consent. Old cached forecast records are removed for that farm's plots; the weather UI cache includes the coordinates. Live weather is requested for the newly saved point, with no simulated fallback on provider failure. A map point is not a surveyed plot boundary, flood extent or flood-depth prediction.

See https://open-meteo.com/en/docs/geocoding-api for the source API contract and https://www.geonames.org/ for the underlying place-name dataset attribution.
