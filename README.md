# Premier League Analytics

Explore Premier League results from 2022–23 through 2026–27. Choose a season in League overview or Compare clubs, filter by all, home, or away fixtures, and trace the averages back to match results. The ongoing season shows completed fixtures as supplied by the data provider.

Open **Season forecast** for projected 2026–27 points, an 80% points range, average finish, and the probability of each club winning the title, finishing in the top four, or finishing in the bottom three.

## Run in VS Code

Open the project folder and run these commands in the VS Code terminal with Python 3.11–3.13:

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

The app loads the selected season automatically. To keep a local copy, run `python season_data.py --season 2024 --download` or import a file with `python season_data.py --season 2024 --file path/to/E0.csv`. Use the starting year of the season. A local copy takes priority over online results, so refresh it manually where you need up-to-date results. If automatic loading fails, you can retry or upload the relevant CSV from the [season archive](https://www.football-data.co.uk/englandm.php).

## Deploy on Streamlit Community Cloud

Use the `main` branch and `app.py` as the entry point. Select Python 3.13 in the advanced deployment settings. The deployment installs the dependencies from `requirements.txt` and retrieves the season on first use.

## How the numbers are calculated

For a completed season, Python requires all 380 distinct fixtures across 20 clubs. For the season in progress, it validates completed fixture pairs against the current club roster. SQLite creates two perspectives for each fixture so home and away summaries, trends, and match logs use the same results. Only fixture and performance fields are used.

| Display | Definition |
|---|---|
| Points per match | Three points per win and one per draw, divided by matches in the venue filter. |
| Goals for and against | Goals scored and conceded by the selected club. |
| Shots for and against | Shots taken by the selected club and its opponents. |
| Shots on target for and against | On-target shots for the selected club and its opponents. |
| Season trend | Mean of the last five matches in the venue filter, plotted on the date of the fifth match. |
| Score in the match log | The selected club's goals appear first. |

Match data comes from [Football-Data.co.uk](https://www.football-data.co.uk/englandm.php) ([field notes](https://www.football-data.co.uk/notes.txt)). The stadium banner is an original AI-generated illustration of a fictional venue. The dashboard uses club names as identifiers.

## How the forecast works

Actual results are fixed. For each remaining home and away pairing, the model draws both clubs' scores independently from Poisson distributions. Each scoring rate combines league-wide home advantage with the home and away goals scored and conceded by the two clubs. Last season's relative rates count as eight prior matches per venue. Promoted clubs start at the league-average rate. The model repeats the remaining season 10,000 times using a fixed random seed so identical inputs reproduce the same forecast.

The 80% points range uses the 10th and 90th percentiles of simulated points. Clubs are ranked by points, goal difference, then goals scored. Exact simulated ties are resolved at random. Forecasts omit transfers, injuries, and points deductions. To roll the dashboard into a new season, update `CURRENT_SEASON` and the club roster in `season_data.py`. The URL and prior season are derived from that year.
