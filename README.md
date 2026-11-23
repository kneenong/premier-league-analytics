# Premier League Analytics

An interactive analytics dashboard for the Premier League. Explore league-wide performance, track recent form, and compare any two of the 20 clubs from the completed 2025–26 men's season. Filter by all, home, or away fixtures, then trace the averages back to each club's individual matches.

## Run in VS Code

Open the project folder and run these commands in the VS Code terminal with Python 3.11–3.13:

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

The app loads and validates the season automatically. To keep a local copy, run `python season_data.py --download` or import a file with `python season_data.py --file path/to/E0.csv`. If automatic loading fails, the dashboard lets you retry or upload the [2025–26 Premier League CSV](https://www.football-data.co.uk/mmz4281/2526/E0.csv).

## Deploy on Streamlit Community Cloud

Use the `main` branch and `app.py` as the entry point. Select Python 3.13 in the advanced deployment settings. The deployment installs the dependencies from `requirements.txt` and retrieves the season on first use.

## How the numbers are calculated

Python validates 380 distinct fixtures, with each club hosting every other club exactly once. SQLite creates two perspectives for each fixture so home and away summaries, trends, and match logs use the same results. Only fixture and performance fields are used.

| Display | Definition |
|---|---|
| Points per match | Three points per win and one per draw, divided by matches in the venue filter. |
| Goals for and against | Goals scored and conceded by the selected club. |
| Shots for and against | Shots taken by the selected club and its opponents. |
| Shots on target for and against | On-target shots for the selected club and its opponents. |
| Season trend | Mean of the last five matches in the venue filter, plotted on the date of the fifth match. |
| Score in the match log | The selected club's goals appear first. |

Match data comes from [Football-Data.co.uk](https://www.football-data.co.uk/englandm.php) ([field notes](https://www.football-data.co.uk/notes.txt)). The stadium banner is an original AI-generated illustration of a fictional venue. The dashboard uses club names as identifiers.
