# Research Analysis: EloR vs. JLRS

This document compares the Joint League Rating System (JLRS) with the research paper [**"Elo-based Rating Systems for Large-Scale Matchmaking"** (Liu et al., WWW '21)](https://cs.stanford.edu/people/paulliu/files/www-2021-elor.pdf).

## Part 1: What the "EloR" Paper Does
The paper addresses a fundamental weakness in traditional Elo: it is often too slow to converge and struggles with "cold start" problems in large-scale networks where players only play a tiny fraction of the total pool.

1. **Statistical Foundation (Maximum Likelihood):** Instead of just doing incremental updates (like Elo), the paper treats matchmaking as a statistical estimation problem. It uses a Log-Linear Model to estimate the probability of a match outcome based on player ratings.

2. **Handling Team Games:** A major portion of the paper focuses on how to decompose a team's performance into individual ratings. It proposes a way to aggregate individual skill into a team "strength" and then distribute the win/loss delta back to individuals in a way that is mathematically sound.

3. **Computational Efficiency:** For systems with millions of players, calculating the "perfect" rating for everyone simultaneously is computationally impossible. The paper introduces an online approximation algorithm that provides the accuracy of a "full-system" recalculation but with the speed of a simple Elo update.

4. **Performance over Time:** It incorporates a "temporal" component, recognizing that a player's skill isn't a static point but a moving target. It uses a weighting system to ensure recent matches carry more "signal" than matches from a year ago.

## Part 2: JLRS vs. EloR (Comparison)
While both systems are rooted in the Elo formula, they are designed for very different environments.

| Feature | EloR (Stanford/WWW '21) | JLRS (Your System) |
| :--- | :--- | :--- |
| **Primary Goal** | Accuracy at Scale. Finding the "true" skill of millions of players as quickly as possible. | Developmental Tracking. Providing a fair, context-aware growth metric for league participants. |
| **Match Outcome** | Typically binary (Win/Loss) or probability-based. | Granular (Margin of Victory). Specifically maps set scores (3-0 vs 3-2) to the rating delta. |
| **Handling Bias** | Focuses on Network Sparsity (players not playing enough diverse opponents). | Focuses on Local Strength Bias (Academy Strength Index - ASI). |
| **Incentives** | Designed for "fair matches" (Matchmaking). | Designed for "developmental leaps" (Age Bonus and Tiering). |
| **Zero-Sum** | Usually enforced, but secondary to likelihood estimation. | Strictly Enforced. Uses the K_shared mechanism to ensure the system is economically closed. |
| **Uncertainty** | Uses Bayesian inference to determine confidence. | Uses an Exponential Saturation Model (Confidence Ratio - CR). |

## Part 3: Engineering Insights
If you were to apply some of the "EloR" paper's logic to JLRS, here are a few improvements that would make your code (like `rating_engine.py` described in your implementation plan) even more robust:

1. **The "Temporal Decay" of ASI:** The paper emphasizes that skill changes over time. Your current `asi_service.py` logic (per the docs) recalculates ASI based on active players. You might consider adding a "time-weight" to the ASI calculation, where matches played by players in the last 2 weeks influence the Academy Strength more than matches from 2 months ago.

2. **Moving from Mapping Tables to Logistic Functions:** Currently, JLRS uses a lookup table for $S$ (e.g., 3-0 = 1.0). The EloR paper suggests that using a continuous logistic function for the "Margin of Victory" provides better convergence. In your `rating_math.py`, you could experiment with a sigmoid function that maps the point/set differential to a value between 0 and 1.

3. **Batch-Wise Integrity:** The paper discusses the risk of "order-dependence" in updates. In your `jlrs_impl_plan.md`, you correctly identified that matches must be processed in `match_timestamp ASC`. The paper validates this approach, noting that for small-scale leagues, chronological serial processing is the most accurate way to prevent "rating jumping" during a single event day.

## Summary
The EloR paper is an "industrial strength" version of Elo meant for massive, anonymous networks. JLRS is a "bespoke" version of Elo meant for a high-trust, high-touch sports environment.

The paper's most relevant takeaway for you is the handling of uncertainty. While your $CR$ (Confidence Ratio) is great, the paper's data suggests that as a player moves tiers (e.g., from Advanced to Elite), you should temporarily reset their $CR$ because they are now entering a "new pool" of competition where their old history is a less reliable predictor.