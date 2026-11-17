# Hardware contract

1. Authenticate as a farmer and create/select a plot.
2. `POST /api/v1/devices` with `{name,plot_id}` returns `{id,key,plot_id}`. Save the key securely on the future device.
3. `POST /api/v1/device/readings` using `X-Device-Key: <key>` accepts the example below. The same endpoint handles virtual and physical devices.

```json
{"schema_version":"1.0","event_id":"device-event-1","device_id":"registration-id","plot_id":"owned-plot-id","timestamp":"2026-11-16T12:00:00Z","source_type":"simulator","measurements":{"soil_moisture_adc":2150,"air_temperature_c":29.1,"relative_humidity_pct":76.2,"rainfall_mm_interval":null},"calibration_id":null}
```

Switch `source_type` to `esp32` without changing the UI or business logic. Credentials must match the registered plot. Event IDs are unique per device; retries return duplicate=true. Out-of-range measurements and timestamps more than five minutes in the future are rejected. Missing readings display NO_LIVE_DEVICE_DATA; simulated readings display SIMULATED_DATA. There is no conversion from ADC to moisture percent.

Before real deployment: physical wiring, secure provisioning, firmware, soil-specific calibration, calibrated measurement schema extension, HTTPS/TLS termination, rate limits, offline buffering, power/enclosure, clock sync and independent field validation. No actual device is connected or field-validated.
