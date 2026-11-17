# Prototype privacy and security

Each demo workspace has an unguessable seven-day token; only its hash is stored in the database. The browser stores the token locally. This is suitable for local demonstrations, not internet deployment: production requires an identity provider, HttpOnly session handling, TLS, rate limiting, key rotation, monitoring and security review.

Coordinates are optional and require consent. Live weather sends the selected coordinates to Open-Meteo only when explicitly selected. District-only farms use a labeled Gazipur illustration in demo weather. Map tiles are requested from OpenStreetMap; comply with its tile usage policy for deployment.

Area search sends the entered place name to Open-Meteo's GeoNames-based geocoding service when Search is pressed. Previewing a map point does not save it. The area-save control explicitly requests consent to store the coordinates and use them for live weather. Manual coordinates remain available when search or map tiles are unavailable.

Photos are private, stripped of original metadata by re-encoding and retained until the owner deletes the case/workspace. Retraining consent defaults off; no automatic retraining exists. Automated retention cleanup, malware scanning and S3 storage are not implemented. Account export excludes private storage paths and device credential hashes. Deletion removes images, sensor readings, records and session credentials.

Device credentials are returned once at registration, stored hashed on the server, and kept in page memory for the virtual-device test. Raw ADC values remain raw. A calibration identifier alone is not proof of calibration. No pump or pesticide automation exists.
