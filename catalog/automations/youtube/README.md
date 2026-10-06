# YouTube channel

Pulls subscribers, lifetime views and video count each day, so the dashboard shows the trend.

1. Google Cloud Console: create a project, enable **YouTube Data API v3**, create an **API key**.
2. Find your channel id (starts with `UC`): YouTube Studio, Settings, Channel, Advanced settings.
3. Put both in `automations/.env`:
   ```
   YOUTUBE_API_KEY=...
   YOUTUBE_CHANNEL_ID=UC...
   ```
4. `python3 brain.py refresh youtube`

Limits: the Data API has no impressions or click-through rate (those need the Analytics API with OAuth). Log them by hand with `metric set` if you want them.
