# America, One Road at a Time

A standalone, responsive travelogue for the September–October 2026 US trip. This directory is designed to deploy as a separate Railway service without changing the existing JLRS/Rallypoint app.

## Railway setup

1. Create a **new service** in your Railway project and connect it to this same GitHub repository.
2. In the new service's Settings, set **Root Directory** to `/travelogue`.
3. Set the service's **Config-as-code file path** to `/travelogue/railway.toml` so Railway loads the deployment settings from this subdirectory. The Dockerfile is at `/travelogue/Dockerfile`.
4. Deploy, then open Settings → Networking and generate a domain. This produces a separate URL from JLRS.
5. Optional: attach a custom domain later.

The page is static and does not need database credentials or Rallypoint environment variables. External photo URLs and Leaflet/OpenStreetMap are used for the initial version. Replace the editorial image URLs with your own travel photos when ready.
