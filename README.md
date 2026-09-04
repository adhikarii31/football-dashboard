# ⚽ Advanced Football Match Analytics Dashboard

An interactive web application built with **Python**, **Streamlit**, and **mplsoccer** that dynamically fetches match event data from StatsBomb Open Data to visualize team performance, pass networks, defensive pressure heatmaps, and xG flow timelines.

---

## 🌟 Key Features

* **Dynamic Match Selection:** Choose from various competitions, seasons, and individual fixtures.
* **xG Flow Timeline:** Step-chart tracking cumulative Expected Goals ($xG$) across 90 minutes.
* **Tactical Networks & Shot Maps:** Visualizes team pass networks and shot locations scaled by $xG$.
* **Defensive Pressure Heatmaps:** Spatial 2D Kernel Density Estimation (KDE) plots showing high-press zones.
* **Key Pass Creators Table:** Granular player-level data highlighting shot assist creators.

---

## 🛠️ Tech Stack & Libraries

* **Language:** Python 3.10+
* **Framework:** [Streamlit](https://streamlit.io/)
* **Data Sources:** [StatsBombPy](https://github.com/statsbomb/statsbombpy)
* **Visualizations:** [mplsoccer](https://mplsoccer.readthedocs.io/), Matplotlib, Pandas, NumPy

---
   ```bash
   git clone [https://github.com/YOUR_GITHUB_USERNAME/football-match-analytics.git](https://github.com/YOUR_GITHUB_USERNAME/football-match-analytics.git)
   cd football-match-analytics
