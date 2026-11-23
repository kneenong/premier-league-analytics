"""Streamlit dashboard for the 2025–26 men's Premier League."""

from base64 import b64encode
from html import escape
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from season_data import ARCHIVE, LOCAL_CSV, SEASON, VENUES, download_season, parse_season, query_season

ROOT = Path(__file__).parent
COLORS = ["#c7f45c", "#7cd7fd"]
METRICS = {
    "ppg": "Points / match",
    "gf": "Goals for / match",
    "ga": "Goals against / match",
    "shots": "Shots for / match",
    "shots_against": "Shots against / match",
    "target": "Shots on target for / match",
    "target_against": "Shots on target against / match",
}
TREND_METRICS = {"Goals scored": "gf", "Goals conceded": "ga", "Shots on target": "target"}
SUMMARY_COLUMNS = {
    "club": "Club", "played": "Played", "wins": "W", "draws": "D", "losses": "L",
    "points": "Points", **METRICS,
}
LOG_COLUMNS = {
    "date": "Date", "opponent": "Opponent", "venue": "Venue", "score": "Score",
    "result": "Result", "shots": "Shots for", "shots_against": "Shots against",
    "target": "On target for", "target_against": "On target against",
}


@st.cache_data(show_spinner=False)
def load_season(raw):
    return query_season(parse_season(raw))


@st.cache_data(ttl="1d", show_spinner="Loading the 2025–26 season…")
def load_online_season():
    return load_season(download_season())


def dashboard_data():
    if LOCAL_CSV.is_file():
        return load_season(LOCAL_CSV.read_bytes())

    if not st.session_state.get("season_source_unavailable"):
        try:
            return load_online_season()
        except (OSError, ValueError):
            st.session_state["season_source_unavailable"] = True

    st.warning("The season data source is temporarily unavailable. Try again or upload the season CSV.")
    if st.button("Retry download"):
        st.session_state.pop("season_source_unavailable", None)
        st.rerun()
    st.link_button("Open the season archive", ARCHIVE)
    upload = st.file_uploader(f"Upload the {SEASON} Premier League CSV", type=["csv"])
    return load_season(upload.getvalue()) if upload is not None else None


def masthead():
    st.html(f"""
        <div class="masthead">
          <div class="wordmark"><span class="mark" aria-hidden="true">PL</span> League Analytics</div>
          <span class="season-label">{SEASON} · Men's Premier League</span>
        </div>
    """)


def hero():
    image_path = ROOT / "stadium.jpg"
    encoded = b64encode(image_path.read_bytes()).decode("ascii")
    st.html(f"""
        <section class="hero">
          <div class="hero-copy">
            <h1>Premier League<br>by the numbers.</h1>
            <p>Explore all 20 clubs. Compare how they performed at home and away.</p>
          </div>
          <div class="hero-image">
            <img src="data:image/jpeg;base64,{encoded}" alt="Illustration of a floodlit football stadium at dusk">
          </div>
        </section>
    """)


def venue_control():
    return st.radio("Venue", VENUES, horizontal=True, key="venue")


def overview(rows, venue):
    st.header("League overview")
    search_area, sort_area, direction_area = st.columns([2, 2, 1])
    with search_area:
        search = st.text_input("Find a club", placeholder="Search club name").strip().casefold()
    with sort_area:
        sort_by = st.selectbox("Sort by", ["ppg", "club", "points", "wins", *list(METRICS)[1:]],
                               format_func=SUMMARY_COLUMNS.__getitem__)
    with direction_area:
        direction = st.selectbox("Order", ["Highest first", "Lowest first"], index=0)

    table = pd.DataFrame(rows).loc[:, list(SUMMARY_COLUMNS)]
    if search:
        table = table[table["club"].str.casefold().str.contains(search, regex=False)]
    table = table.sort_values(sort_by, ascending=direction == "Lowest first", kind="stable")
    st.caption(f"{len(table)} of 20 clubs · {venue} · {rows[0]['played']} matches per club")
    if table.empty:
        st.info("No clubs match that search.")
        return
    st.dataframe(table.rename(columns=SUMMARY_COLUMNS), hide_index=True, width="stretch",
                 height=min(760, 36 + 36 * len(table)),
                 column_config={name: st.column_config.NumberColumn(name, format="%.2f")
                                for name in METRICS.values()},
                 key="league_table")


def club_panel(row, side):
    st.html(f"""
        <section class="team-panel {side}">
          <h3>{escape(row['club'])}</h3>
          <p>{row['played']} played · {row['wins']}W / {row['draws']}D / {row['losses']}L</p>
          <dl>
            <div><dt>Points / match</dt><dd>{row['ppg']:.2f}</dd></div>
            <div><dt>Goals for / match</dt><dd>{row['gf']:.2f}</dd></div>
            <div><dt>Goals against / match</dt><dd>{row['ga']:.2f}</dd></div>
          </dl>
        </section>
    """)


def trend_data(logs, clubs, metric):
    series = []
    for club in clubs:
        frame = pd.DataFrame(logs[club])
        frame["date"] = pd.to_datetime(frame["date"])
        frame["average"] = frame[metric].rolling(5, min_periods=5).mean()
        frame["value"] = frame[metric]
        series.append(frame.dropna(subset=["average"]))
    return pd.concat(series, ignore_index=True)


def season_trend(logs, clubs):
    st.header("Season trends")
    metric = st.selectbox("Trend metric", TREND_METRICS)
    st.caption("Each point averages the previous five selected fixtures, including the fixture on that date.")
    chart = alt.Chart(trend_data(logs, clubs, TREND_METRICS[metric])).mark_line(
        point=alt.OverlayMarkDef(size=37, filled=True), strokeWidth=2.4
    ).encode(
        x=alt.X("date:T", title=None, axis=alt.Axis(format="%b", tickCount=7)),
        y=alt.Y("average:Q", title=f"{metric} / match", scale=alt.Scale(zero=True)),
        color=alt.Color("club:N", title=None, scale=alt.Scale(domain=clubs, range=COLORS),
                        legend=alt.Legend(orient="top")),
        tooltip=[alt.Tooltip("club:N", title="Club"),
                 alt.Tooltip("date:T", title="Date", format="%d %b %Y"),
                 alt.Tooltip("opponent:N", title="Opponent"),
                 alt.Tooltip("value:Q", title=metric),
                 alt.Tooltip("average:Q", title="Five-match average", format=".2f")],
    ).properties(height=270)
    st.altair_chart(chart, width="stretch")


def match_log(logs, clubs):
    st.header("Match logs")
    for tab, club in zip(st.tabs(clubs), clubs):
        with tab:
            frame = pd.DataFrame(logs[club]).sort_values("date", ascending=False)
            frame["date"] = pd.to_datetime(frame["date"]).dt.date
            frame["score"] = frame["gf"].astype(str) + "–" + frame["ga"].astype(str)
            st.dataframe(frame[list(LOG_COLUMNS)].rename(columns=LOG_COLUMNS),
                         hide_index=True, height=370, width="stretch",
                         key=f"match_log_{club}")


def compare(rows, logs):
    st.header("Compare clubs")
    clubs = {row["club"]: row for row in rows}
    left, right = st.columns(2)
    with left:
        first = st.selectbox("First club", sorted(clubs), index=0, key="first_club")
    opponents = sorted(clubs.keys() - {first})
    with right:
        second = st.selectbox("Second club", opponents, index=opponents.index("Liverpool")
                              if "Liverpool" in opponents else 0, key="second_club")
    with left:
        club_panel(clubs[first], "side-a")
    with right:
        club_panel(clubs[second], "side-b")

    st.subheader("Attack and defense")
    table = pd.DataFrame({
        "Metric": list(METRICS.values()),
        first: [clubs[first][key] for key in METRICS],
        second: [clubs[second][key] for key in METRICS],
    })
    st.dataframe(table, hide_index=True, width="stretch",
                 column_config={club: st.column_config.NumberColumn(club, format="%.2f")
                                for club in [first, second]})
    season_trend(logs, [first, second])
    match_log(logs, [first, second])


def methodology():
    with st.expander("Metric definitions and sources"):
        st.markdown(f"""
- **Points per match** divides points earned from results by matches played. Wins earn 3 points,
  draws earn 1, and losses earn 0. League position and disciplinary adjustments are outside this calculation.
- **For and against per match** divide goals, total shots, or shots on target by matches played in the selected venue.
- **Five-match average** uses the latest five fixtures in the current venue filter. The first four fixtures have no plotted average.
- **Match log scores** put the selected club first, even for away matches.
- **Data source** [Football-Data.co.uk]({ARCHIVE}) · [Field definitions](https://football-data.co.uk/notes.txt)
""")


def main():
    st.set_page_config(page_title="Premier League Analytics", layout="wide")
    st.html(f"<style>{(ROOT / 'dashboard.css').read_text(encoding='utf-8')}</style>")
    masthead()
    try:
        data = dashboard_data()
    except (OSError, ValueError) as exc:
        st.error(str(exc))
        return
    if data is None:
        hero()
        return
    league, logs = data
    page = st.radio("Dashboard view", ["League overview", "Compare clubs"],
                    horizontal=True, label_visibility="collapsed", key="page")
    if page == "League overview":
        hero()
    venue = venue_control()
    if page == "Compare clubs":
        compare(league[venue], logs[venue])
    else:
        overview(league[venue], venue)
    methodology()


if __name__ == "__main__":
    main()
