# Problem Statement

The current table tennis competitive structure—driven by official rankings from TTFI, MSTTA, TSTTA—is effective for formal competition but inherently episodic in nature. Rankings are updated primarily during tournament cycles, which means that for large parts of the year, especially between seasons, there is no continuous or reliable mechanism to track a player’s current form or improvement trajectory.

During these gaps, players actively participate in local tournaments organized by academies and sponsors. While these events provide valuable exposure and cross-academy interaction, they are not structured to generate accurate or continuous player rankings. The typical format—group stage followed by knockout—prioritizes progression over comprehensive comparison. As a result, outcomes are often influenced by draw dynamics rather than consistent relative strength. Strong players may not face each other at all, or may meet only once, making it difficult to establish a clear and repeatable hierarchy among top competitors.

Additionally, participation in these tournaments is voluntary and uneven, which further reduces the likelihood of consistent high-quality matchups. The frequency with which strong players compete against each other is low, and when they do, the system does not retain or aggregate these results in a way that contributes to a broader understanding of player strength. Consequently, there is no unified rating framework across academies, and the only available proxy for assessing a player’s level remains official seedings—which are themselves infrequent and lagging indicators.

This leads to a fragmented ecosystem where:

- Player evaluation is time-bound rather than continuous  
- Matchups are draw-dependent rather than systematically designed  
- Cross-academy comparisons are infrequent and unstructured  
- Rankings do not fully reflect current ability or development  

In essence, while the ecosystem provides ample opportunities to compete, it lacks a structured, data-driven mechanism to convert match outcomes into a reliable, real-time measure of player strength. This gap limits accurate benchmarking, slows down talent identification, and reduces the effectiveness of competition as a tool for player development.

---

# Proposed Solution

To address the gap between episodic official rankings and unstructured local competition, we propose introducing a continuous, match-driven rating system that runs alongside existing tournaments and training programs.

At its core, the solution is to systematically capture match outcomes and convert them into a dynamic player rating, enabling a real-time and objective measure of player strength across academies and age groups.

---

## Key Principles of the Solution

### 1. Continuous Rating (Not Event-Based)

Every match—whether played in a league setting, local tournament, or structured session—contributes to a player’s rating.

This ensures:

- Player progress is captured in real time  
- Rankings reflect current form, not past results  

---

### 2. Structured League Layer on Top of Existing Ecosystem

Introduce a league-style match framework within and across academies where:

- Players are matched regularly  
- Matchups are designed, not left to draw probability  
- Strong players are more likely to play each other repeatedly  

This complements tournaments by:

- Increasing frequency of high-quality matches  
- Providing consistent benchmarking opportunities  

---

### 3. Unified Cross-Academy Rating System

All players operate within a single rating pool, regardless of academy.

This enables:

- Direct comparison of players across academies  
- Removal of “local strength bias”  
- Creation of a common performance benchmark  

---

### 4. Elo-Based Rating Engine (With Enhancements)

Each match updates player ratings using a system that considers:

- Expected outcome vs actual result  
- Match importance (league vs tournament vs practice)  
- Player experience (number of matches played)  
- Cross-academy context  
- Age differences (via controlled upset bonus)  
- Margin of victory (set score)  

This ensures:

- Fair reward for upsets  
- Stability for experienced players  
- Faster correction for new players  

---

### 5. Contextual Tiering for Player Development

Players are grouped into universal tiers based on rating alone.

| Tier | Rating Range |
|------|-------------|
| Beginner | < 900 |
| Intermediate | 900–1100 |
| Advanced | 1100–1300 |
| Elite | 1300–1500 |
| National Track | 1500+ |

This provides:

- Clear progression pathways  
- Better match planning  
- Motivation and goal-setting  

---

### 6. Coaching Analytics Layer (Age-Contextual Views)

Age context is valuable for talent identification and developmental tracking, but it belongs in a coaching analytics layer—not in the tier system itself.

The analytics layer provides:

- Age-group leaderboards  
- Percentile rank within age group (e.g., 90th percentile for U-10)  
- Rating velocity (points gained per month)  
- Cross-age comparisons  

---

### 7. Starting Rating and Provisional Period

There are two entry paths into the system: unseeded and seeded.

#### Unseeded Entry (Default)

All new players without prior rankings enter with:

- **Starting rating**: 1000  
- **Virtual matches**: 0  
- **Provisional period**: First 15 rated matches  

During the provisional period:

- K-factor is fixed at 60  
- Ratings are marked with a provisional indicator (P)  
- Results carry reduced weight  
- Players are excluded from ASI calculations  

After 15 matches, the player transitions to the standard rating pipeline.

---

#### Seeded Entry (Players with Prior Rankings)

Players with documented history skip the provisional phase.

| Seeding Level | Starting Rating | Virtual Matches | Initial CR |
|--------------|----------------|----------------|-----------|
| District     | 1200           | 10             | 0.28      |
| State        | 1400           | 20             | 0.49      |
| National     | 1500           | 30             | 0.63      |

Virtual matches influence confidence and K-factor stabilization.

Confidence Ratio (CR):

$$
CR = 1 - e^{-(\text{real\_matches} + \text{virtual\_matches}) / 30}
$$

---

# The Elo Rating (Foundation)

At its core, Elo updates a player’s rating based on performance relative to expectation.

---

## Expected Score

$$
E_A = \frac{1}{1 + 10^{(R_B - R_A)/400}}
$$

$$
E_B = 1 - E_A
$$

---

## Actual Score (Margin of Victory)

After the match, the score reflects dominance, not just outcome.

### Best-of-3 Matches

| Result | S (Winner) | S (Loser) |
|--------|-----------|----------|
| 2–0    | 1.00      | 0.00     |
| 2–1    | 0.90      | 0.10     |

---

### Best-of-5 Matches

| Result | S (Winner) | S (Loser) |
|--------|-----------|----------|
| 3–0    | 1.00      | 0.00     |
| 3–1    | 0.90      | 0.10     |
| 3–2    | 0.80      | 0.20     |

---

### Best-of-7 Matches

| Result | S (Winner) | S (Loser) |
|--------|-----------|----------|
| 4–0    | 1.00      | 0.00     |
| 4–1    | 0.90      | 0.10     |
| 4–2    | 0.80      | 0.20     |
| 4–3    | 0.75      | 0.25     |

---

## Rating Update

$$
\Delta R = K \times (S - E)
$$

---

## K-Factor

| Matches (real + virtual) | Base K | Reason |
|--------------------------|--------|--------|
| < 30                     | 50     | Rapid improvement phase |
| 30–100                   | 32     | Balanced |
| 100+                     | 20     | Stability |

---

## Example (Upset)

- Player A: 1200  
- Player B: 1400  

If A wins 3–0:

$$
\Delta \approx +24
$$

Large gain due to unexpected outcome.

---

# Extending Elo for Real-World Use

Plain Elo assumes:

- Equal match frequency  
- No structural bias  
- Equal reliability  

These assumptions do not hold, so extensions are added.

---

## 1. Confidence Score (CR)

Measures rating reliability.

$$
CR = 1 - e^{-(\text{real\_matches} + \text{virtual\_matches}) / 30}
$$

| Total Matches | CR   | Interpretation |
|--------------|------|---------------|
| 5            | 0.15 | Very uncertain |
| 10           | 0.28 | Low |
| 15           | 0.39 | Provisional threshold |
| 20           | 0.49 | Moderate |
| 30           | 0.63 | Reliable |
| 60           | 0.86 | High |
| 100+         | 0.96 | Very reliable |

---

### K Adjustment

$$
K_{\text{eff}} = K \times (2 - CR)
$$

- New players → faster updates  
- Experienced players → stability  

---

## 2. Inactivity Decay

After 6 weeks of inactivity:

$$
CR_{\text{decayed}} = CR \times e^{-(w_{\text{inactive}} - 6)/16}
$$

| Weeks Inactive | CR Multiplier | Effect |
|---------------|--------------|--------|
| 6             | 1.00         | No change |
| 14            | 0.61         | Moderate decay |
| 22            | 0.37         | Significant decay |
| 38            | 0.13         | Near reset |

**Key design choice:** Rating does not decay—only confidence.

---

## 3. Academy Adjustment

### Match Multiplier

- Same academy → 0.8  
- Cross-academy → 1.2  

$$
K' = K \times W_{\text{academy}}
$$

---

### Academy Strength Index (ASI)

$$
ASI = \text{mean rating of non-provisional active players}
$$

Conditions:

- Non-provisional: 15+ matches  
- Active: at least one match in last 8 weeks  
- Minimum 5 players required  

---

### Cross-Academy Normalization

$$
R_{\text{adj}} = R + (\text{GlobalAvg} - ASI)
$$

---

## 4. Age Bonus (Upset Only)

Applies only when younger player wins.

$$
\text{Bonus} = \min(10, 2 \times \text{age\_diff})
$$

- Younger wins → bonus applied  
- Older wins → no bonus  

---

## 5. Match Importance

| Match Type | Weight |
|-----------|--------|
| League    | 1.0    |
| Tournament| 1.2    |
| Friendly  | 0.5    |

$$
K'' = K \times W_{\text{match}}
$$

---

# Final Combined Formula

### 1. Academy Normalization

$$
R_{\text{adj}} = R + (\text{GlobalAvg} - ASI)
$$

---

### 2. Expected Score

$$
E_A = \frac{1}{1 + 10^{(R_{B,\text{adj}} - R_{A,\text{adj}})/400}}
$$

---

### 3. Actual Score

Derived from margin-of-victory tables.

---

### 4. Effective K (per player)

$$
K_{\text{eff}} = \min(K_{\text{base}} \times W_{\text{match}} \times W_{\text{academy}} \times (2 - CR), 60)
$$

---

### 5. Shared K (Zero-Sum Enforcement)

$$
K_{\text{shared}} = \frac{K_{\text{eff},A} + K_{\text{eff},B}}{2}
$$

## 6. Rating Delta

$$
\Delta = K_{\text{shared}} \times (S_A - E_A)
$$

---

## 7. Rating Update

$$
R_A' = R_A + \Delta, \quad R_B' = R_B - \Delta
$$

---

## 8. Age Bonus (if younger player won)

$$
\text{Bonus} = \min(10, 2 \times \text{age\_diff})
$$

$$
R_{\text{younger}}' = R_{\text{younger}}' + \text{Bonus}, \quad
R_{\text{older}}' = R_{\text{older}}' - \text{Bonus}
$$

---

# Full Example — Step-by-Step Walkthrough

## Scenario Setup

| Attribute        | Player A | Player B |
|------------------|----------|----------|
| Age              | 11       | 13       |
| Rating (R)       | 1350     | 1250     |
| Matches Played   | 20       | 60       |
| Academy          | X        | Y        |
| Match Type       | Tournament (cross-academy) |
| Result           | Player A wins 3–0 |

---

## Academy Context

| Parameter | Value |
|----------|------|
| Global Average Rating | 1100 |
| ASI (Academy X) | 1200 |
| ASI (Academy Y) | 1150 |

---

## Step 1: Academy Normalization

$$
R_{A,\text{adj}} = 1350 + (1100 - 1200) = 1250
$$

$$
R_{B,\text{adj}} = 1250 + (1100 - 1150) = 1200
$$

Academy X is stronger overall, so A is adjusted downward more.

---

## Step 2: Expected Score

$$
E_A = \frac{1}{1 + 10^{(1200 - 1250)/400}} \approx 0.57
$$

$$
E_B = 1 - 0.57 = 0.43
$$

Player A is slightly favored (~57%).

---

## Step 3: Actual Score

Player A wins 3–0:

$$
S_A = 1.00, \quad S_B = 0.00
$$

Dominant victory → maximum signal.

---

## Step 4: Base K-Factor

| Player | Matches | Base K |
|--------|--------|--------|
| A      | 20     | 50     |
| B      | 60     | 32     |

A is still evolving → higher K.  
B is more stable → lower K.

---

## Step 5: Confidence Score (CR)

$$
CR_A = 1 - e^{-20/30} \approx 0.49
$$

$$
CR_B = 1 - e^{-60/30} \approx 0.86
$$

- A: Moderate confidence  
- B: High confidence  

---

## Step 6: Effective K and Shared K

### Per-player Effective K

$$
K_{\text{eff},A} = \min(50 \times 1.2 \times 1.2 \times (2 - 0.49), 60)
$$

$$
= \min(108.9, 60) = 60
$$

$$
K_{\text{eff},B} = \min(32 \times 1.2 \times 1.2 \times (2 - 0.86), 60)
$$

$$
= \min(52.3, 60) = 52.3
$$

### Shared K

$$
K_{\text{shared}} = \frac{60 + 52.3}{2} = 56.15
$$

---

The shared K averages both players’ effective K-factors. This ensures:

- The match’s importance is determined before the result (not influenced by who wins)  
- Both players’ experience levels contribute proportionally  
- Zero-sum is maintained: total rating points in the system are conserved  

---

## Step 7: Rating Delta

$$
\Delta = 56.15 \times (1.00 - 0.57)
$$

$$
= 56.15 \times 0.43 \approx 24.1
$$

---

## Step 8: Apply Zero-Sum Update

$$
R_A' = 1350 + 24.1 = 1374.1
$$

$$
R_B' = 1250 - 24.1 = 1225.9
$$

---

## Step 9: Age Bonus

Younger player (A, age 11) beat older player (B, age 13).

$$
\text{Bonus} = \min(10, 2 \times 2) = 4
$$

$$
R_A' = 1374.1 + 4 = 1378
$$

$$
R_B' = 1225.9 - 4 = 1222
$$

---

## Final Ratings

| Player | Before | After | Change |
|--------|--------|--------|--------|
| A      | 1350   | 1378   | +28    |
| B      | 1250   | 1222   | -28    |

**Net change = 0 (zero-sum preserved).**

---

## Why Did A Gain This Much?

1. Cross-academy match (1.2× multiplier)  
2. Tournament match (1.2× weight)  
3. A has lower confidence → faster updates  
4. B has high confidence → reliable benchmark  
5. Dominant 3–0 win → maximum signal  
6. Younger player → age bonus applied  

---

## What If A Had Won 3–2 Instead?

$$
S_A = 0.80
$$

$$
\Delta = 56.15 \times (0.80 - 0.57) \approx 12.9
$$

| Player | Before | After | Change |
|--------|--------|--------|--------|
| A      | 1350   | 1367   | +17    |
| B      | 1250   | 1233   | -17    |

Narrow win → smaller rating change.

---

## What If B Had Won (3–0)?

$$
S_A = 0.00
$$

$$
\Delta = 56.15 \times (0.00 - 0.57) \approx -32.0
$$

| Player | Before | After | Change |
|--------|--------|--------|--------|
| A      | 1350   | 1318   | -32    |
| B      | 1250   | 1282   | +32    |

No age bonus (older player won).

---

## What This Example Demonstrates

1. **Shared K system** → match weight determined before result  
2. **Handles uncertainty** → fewer matches → faster updates  
3. **Rewards signal strength** → dominant wins matter more  
4. **Rewards meaningful upsets** → age bonus redistribution  
5. **Zero-sum system** → no rating inflation  

---

# What This System Achieves

- **Continuous evaluation** → real-time strength tracking  
- **High-quality match signal** → margin + context included  
- **Fast learning + stability** → adapts by experience  
- **Fair cross-academy comparison** → ASI normalization  
- **No rating inflation** → zero-sum preserved  
- **Inactivity handling** → confidence decay  
- **Development-focused design** → tiering + analytics  

---

# Operational Design

The rating formula alone is insufficient. Operational mechanisms are required.

---

## 1. Data Collection

Match results must flow into the system with minimal friction.

- **Primary input**: Mobile app match entry  
- **Minimum fields required**:
  - Both players  
  - Match type (auto-filled)  
  - Event reference  
  - Set score  

- **Dual confirmation**:
  - Both players (or coaches) confirm within 48 hours  
  - Unconfirmed results are excluded  

- **Fallback**:
  - Coach can submit on behalf of players  

---

## 2. Match Type Classification

Determines match weight.

- **League**: Scheduled fixtures  
- **Tournament**: Registered events  
- **Friendly**: Practice sessions  

Rules:

- Match type locked at creation  
- Cannot be player-declared after match  

---

## 3. Result Verification and Dispute Resolution

- **Standard flow**:  
  Player A submits → Player B confirms → Rating update  

- **Dispute flow**:  
  If rejected → enters dispute queue  
  Reviewed within 72 hours  

- **No-show handling**:  
  If no confirmation within 48 hours → auto-accepted  

- **Admin override**:  
  League admin can void results  

---

## 4. Anti-Sandbagging

To prevent rating manipulation:

- Friendly cap: max 4 rated friendlies/week  
- Loss pattern detection (e.g., repeated losses to weaker players)  
- Coach visibility into player history  
- Admin review triggers  

---

## 5. Cold Start and Bootstrapping

### Phase 1: Calibration
- Unseeded players: rating = 1000  
- Seeded players: virtual matches applied  
- Ratings not public  

### Phase 2: Convergence
- Once ≥80% players are stable → ratings published  
- Tiers activated  

### Phase 3: Steady State
- System runs normally  

---

## 6. Communication and Transparency

- **Public visibility**: tiers visible to all  
- **Private ratings**: visible to player + coach  
- **Update cadence**: within 24 hours  
- **Explainability**: rating breakdown shown  
- **Quarterly reports**:
  - Player progression  
  - Match frequency  
  - Cross-academy activity  

---

# Summary

JLRS introduces a continuous, league-driven rating system that converts regular match play into a reliable, real-time measure of player strength across academies and age groups.

Every match:

1. Normalizes for academy strength  
2. Computes expected outcome  
3. Compares with actual result (with margin)  
4. Adjusts for experience  
5. Applies age bonus if applicable  
6. Preserves zero-sum integrity  

This system complements—not replaces—official rankings, acting as a continuous benchmarking layer for player development.

---