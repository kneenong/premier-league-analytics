"""Simulate a Premier League season from completed results and scoring rates."""

import numpy as np

SIMULATIONS = 10_000
PRIOR_MATCHES = 8
LEAGUE_PRIOR_MATCHES = 38


def scoring_totals(matches, club_index):
    """Return goal and appearance totals in home/away order for each club."""
    goals_for = np.zeros((len(club_index), 2))
    goals_against = np.zeros_like(goals_for)
    appearances = np.zeros_like(goals_for)
    for _, home, away, hg, ag, *_ in matches:
        if home in club_index:
            i = club_index[home]
            goals_for[i, 0] += hg
            goals_against[i, 0] += ag
            appearances[i, 0] += 1
        if away in club_index:
            i = club_index[away]
            goals_for[i, 1] += ag
            goals_against[i, 1] += hg
            appearances[i, 1] += 1
    return goals_for, goals_against, appearances


def season_projection(previous, played, clubs, simulations=SIMULATIONS, seed=2026):
    """Keep actual results fixed and project the remaining home-away pairings."""
    clubs = sorted(clubs)
    index = {club: i for i, club in enumerate(clubs)}
    old_gf, old_ga, old_played = scoring_totals(previous, index)
    gf, ga, games = scoring_totals(played, index)

    old_average = np.array([[match[3], match[4]] for match in previous]).mean(axis=0)
    new_goals = np.array([[match[3], match[4]] for match in played]).reshape(-1, 2)
    average = (new_goals.sum(axis=0) + LEAGUE_PRIOR_MATCHES * old_average) / (
        len(played) + LEAGUE_PRIOR_MATCHES
    )
    old_attack = np.divide(old_gf, old_played * old_average, out=np.ones_like(old_gf), where=old_played > 0)
    old_defense = np.divide(old_ga, old_played * old_average[::-1], out=np.ones_like(old_ga), where=old_played > 0)
    attack = (gf / average + PRIOR_MATCHES * old_attack) / (games + PRIOR_MATCHES)
    defense = (ga / average[::-1] + PRIOR_MATCHES * old_defense) / (games + PRIOR_MATCHES)

    points = np.zeros(len(clubs), dtype=int)
    known = set()
    for _, home, away, hg, ag, *_ in played:
        known.add((home, away))
        points[index[home]] += 3 * (hg > ag) + (hg == ag)
        points[index[away]] += 3 * (ag > hg) + (hg == ag)

    rng = np.random.default_rng(seed)
    projected = np.tile(points, (simulations, 1))
    goals = np.tile(gf.sum(axis=1).astype(int), (simulations, 1))
    conceded = np.tile(ga.sum(axis=1).astype(int), (simulations, 1))
    for home, h in index.items():
        for away, a in index.items():
            if h == a or (home, away) in known:
                continue
            hg = rng.poisson(average[0] * attack[h, 0] * defense[a, 1], simulations)
            ag = rng.poisson(average[1] * attack[a, 1] * defense[h, 0], simulations)
            projected[:, h] += 3 * (hg > ag) + (hg == ag)
            projected[:, a] += 3 * (ag > hg) + (hg == ag)
            goals[:, h] += hg
            goals[:, a] += ag
            conceded[:, h] += ag
            conceded[:, a] += hg

    order = np.lexsort((rng.random(projected.shape), -goals, -(goals - conceded), -projected), axis=1)
    ranks = order.argsort(axis=1) + 1
    low, high = np.quantile(projected, [0.1, 0.9], axis=0, method="nearest")
    return [
        {
            "Club": club, "Played": int(games[i].sum()), "Points now": int(points[i]),
            "Projected points": float(projected[:, i].mean()),
            "80% points range": f"{low[i]}–{high[i]}",
            "Average finish": float(ranks[:, i].mean()),
            "Title": float((ranks[:, i] == 1).mean()),
            "Top four": float((ranks[:, i] <= 4).mean()),
            "Bottom three": float((ranks[:, i] > len(clubs) - 3).mean()),
        }
        for i, club in enumerate(clubs)
    ]
