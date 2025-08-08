# Global Weather Dashboard (Streamlit)

A ready-to-deploy **Streamlit** app that shows **real-time and historical weather** for **any location worldwide**, with a selectable **date range** and **variables**. Uses the free **Open‑Meteo** Forecast & Archive APIs (no API key required).

## Features
- Search any place (Open‑Meteo Geocoding)
- Pick **hourly** or **daily** data
- Select variables: temperature, humidity, precipitation, wind, gusts, pressure, cloud cover
- Plots (Plotly) and an interactive data table
- Download the raw CSV
- Smartly pulls from **archive** for older dates and **forecast** for recent dates, so you get a continuous range

## Local Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open the URL shown in your terminal.

## One‑Click Online Deploy (Free)

1. Push these files to a new **public GitHub** repo.
2. Go to **Streamlit Community Cloud** and click **Deploy an app**.
3. Point it at your repo (`main` branch), set the **entrypoint** to `app.py`, and deploy.
4. Share your app URL.

> Tip: If you run into geocoding limits, try a more specific place name, or host the app on Community Cloud which has generous limits.

## Notes
- Data source: https://open-meteo.com/
- Archive coverage varies by variable and region. If you select a very long range, the app will split requests across archive and forecast and merge them.
- Time zone is set to `auto` so times will be localized to the chosen location.