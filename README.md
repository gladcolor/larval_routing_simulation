# CDC Ethiopia — *Anopheles stephensi* larval survey webmaps

Interactive visualizations of larval-site surveys in **Jigjiga, Logiya, and Semera, Ethiopia**
(campaigns: Dry24 → Rainy24 → Malaria24 → Dry25).

## How to use
1. **Unzip** this folder, keeping all files together.
2. Open **`dashboard.html`** in a web browser (Chrome, Edge, or Firefox — just double-click).
3. Use the tabs at the top to switch views.

> **Internet connection required.** The basemap tiles and the mapping library (Leaflet)
> load from the web. All of the *survey data* is embedded in the HTML files, so no
> database or server is needed.

## The tabs
- **🛰 Survey Trajectory** — animated path of the surveys over time. Choose how to colour
  each habitat (Anopheles presence, campaign, sector, quadrant, or larval count) and the
  symbol (dots / spikes / bars, where height = larval count). Includes a cumulative
  larvae-by-campaign chart with LOESS smoothing.
- **🔥 Spatial Hotspots** — Getis-Ord Gi\* hot/cold spots and Local Moran's I (LISA) clusters
  per city × campaign, with global Moran's I and plain-English interpretation.
- **🌡 Heatmap** — kernel-density heatmap of larval abundance / survey density.
- **🗂 Sector density** — small-multiples grid (3 cities × 4 campaigns) of mean larvae per
  habitat by sector.
- **🎲 Monte Carlo** — a survey-order simulation. For each campaign, habitats are visited in
  *random* order many times (you choose how many — default 2 000); each panel shows the
  cumulative larval proportion vs habitats surveyed as a 5–95% / 25–75% band around the even-spread
  diagonal, with the **actual** field survey order overlaid in white. Pick a city, toggle the x-axis
  between % and # of habitats, and click a panel title to enlarge it (click again or press *Esc* to
  restore). *This tab shuffles habitats freely (no spatial constraint); the road-network version is the next tab.*
- **🚐 Route planning** — treatment routing on the **real OSM road network**. Teams drive between
  habitats (road travel times) and spend 20 min/site within an 8 h day. Pick a city, campaign,
  routing algorithm, number of teams (1–3) and working days; **▶ Drive route** animates a car per
  team along the actual streets, treating habitats as it passes, with a **cumulative larvae-treated
  curve**. Compares scenarios (e.g. 2 teams × 5 days vs 1 team × 10 days). Algorithms:
  - **Sector sweep** (default) — clear every habitat in one administrative sector before driving to
    the next (sectors ordered by larvae). Realistic and efficient (~3× less driving; routes don't backtrack).
  - **Greedy hotspot** — chase the richest *individual* sites: most larvae earliest, but it zig-zags
    across town (prize-collecting / orienteering). **Key finding:** because larvae are highly
    concentrated, this treats far more larvae per day than nearest-neighbour "shortest-route" logic.
  - **Cluster + greedy**, **Nearest-neighbour**, **Random** (baseline) for comparison.

## Files
| File | What it is |
|------|------------|
| `dashboard.html` | **Open this** — tabbed wrapper for the four maps |
| `survey_trajectory_animation.html` | Survey-trajectory animation |
| `spatial_analysis_hotspots.html` | Gi\* / LISA spatial analysis |
| `larval_heatmap.html` | Density heatmap |
| `sector_density_maps.html` | Sector × campaign density grid |
| `monte_carlo_simulation.html` | Monte Carlo survey-order simulation (uses `mc_data.js`) |
| `mc_data.js` | Larval counts per habitat (survey order), by city × campaign — data for the Monte Carlo tab |

*Source: An. stephensi larval surveillance, Ethiopia.*
