def calculate_risk_score(
    withdrawal_rate,
    avg_wait_days,
    upgrade_cost,
    capacity_mw,
    active_projects
):
    """
    Returns a score between 0 and 100

    100 = Lowest Risk
    0 = Highest Risk
    """

    withdrawal_score = (
        1 - withdrawal_rate
    ) * 100

    wait_score = max(
        0,
        100 - (avg_wait_days / 25)
    )

    cost_per_mw = (
        upgrade_cost / capacity_mw
    )

    cost_score = max(
        0,
        100 - (cost_per_mw / 10000)
    )

    congestion_score = max(
        0,
        100 - active_projects
    )

    final_score = (
        withdrawal_score * 0.40 +
        wait_score * 0.25 +
        cost_score * 0.20 +
        congestion_score * 0.15
    )

    return round(final_score, 2)
