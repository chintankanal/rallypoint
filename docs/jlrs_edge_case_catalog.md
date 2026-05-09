# JLRS Edge Case Catalog

This document defines system behavior for edge cases not covered by the core rating spec. Each entry includes the scenario, the decision, and the rationale. Implementation must handle every case listed here; any scenario not listed should be escalated to the rating committee before coding.

---

# 1. Match Completion Edge Cases

## 1.1 Walkover / Forfeit

**Scenario:**  
A player wins because the opponent fails to appear or is disqualified before play begins.

**Decision:**  
Walkovers are **not rated**. No rating update for either player.

**Rationale:**  
No competitive information was generated. Rating a walkover would reward the winner and punish the absent player based on logistics, not skill.

---

## 1.2 Retirement Mid-Match

**Scenario:**  
A player retires during a match (e.g., injury at 1–2 down in a best-of-5).

**Decision:**  

- If at least one full set has been completed → match **is rated**  
- Use score at time of retirement  
- Remaining sets awarded to opponent  

If no full set completed → match **not rated**

---

### Retirement Scoring Rules

| Sets Completed | Rated? | Recorded Score |
|---------------|--------|----------------|
| 0 | No | Not recorded |
| 1+ (Bo3) | Yes | Opponent awarded remaining sets (e.g., 1–0 → 1–2 loss) |
| 1+ (Bo5) | Yes | Opponent awarded remaining sets (e.g., 1–2 → 1–3 loss) |
| 1+ (Bo7) | Yes | Opponent awarded remaining sets (e.g., 2–3 → 2–4 loss) |

---

**Rationale:**  
Partial matches still contain competitive signal. Discarding them wastes valid information.

---

## 1.3 Disputed Set Score

**Scenario:**  
Players or coaches disagree on the set score of a completed match.

**Decision:**  

- Match enters dispute queue  
- Rating update is **deferred** (not applied, not reversed)  
- If unresolved within 72 hours → match **voided**  

---

**Rationale:**  
Applying and then reversing ratings complicates audit trails. Deferral is cleaner.

---

## 1.4 Match Voided After Ratings Applied

**Scenario:**  
A match is voided after ratings have already been applied.

**Decision:**  

- System performs a **rating rollback** for that match  
- Ratings revert to exact previous values  
- Subsequent matches are **not recalculated**  

---

**Rationale:**  
Full cascade recalculation is complex and confusing. Reversing only the affected delta is predictable and auditable.

---

# 2. Player Identity Edge Cases

## 2.1 Player Registered at Multiple Academies

**Scenario:**  
A player trains at two academies.

**Decision:**  

- Each player has **one primary academy**  
- Determines:
  - ASI normalization  
  - Match classification (intra vs cross)  

- Primary academy can be changed once per quarter  
- Change effective next calendar month  

---

**Rationale:**  
Dynamic academy switching creates gaming opportunities. Fixed primary with periodic change is auditable.

---

## 2.2 Player Transfers Between Academies

**Scenario:**  
Player permanently moves to a new academy.

**Decision:**  

- Rating carries over unchanged  
- Primary academy updated (next month)  
- Historical matches retain original academy  
- No rating adjustment  

---

**Rationale:**  
Rating reflects player skill. ASI normalization already accounts for academy differences.

---

## 2.3 Age Cutoff Timing

**Scenario:**  
Player turns a new age mid-season.

**Decision:**  

- Age = age as of **January 1**  
- Fixed for entire calendar year  

---

**Rationale:**  
Prevents rating inconsistencies due to mid-season age changes.

---

## 2.4 Incorrect Profile Data

**Scenario:**  
Age or academy entered incorrectly.

**Decision:**  

- Correct going forward  
- Past matches **not recalculated**  
- Exception: major errors → manual adjustment allowed  

---

**Rationale:**  
Recalculation is costly and confusing. Most errors have minimal impact.

---

# 3. Match Context Edge Cases

## 3.1 Provisional vs Provisional

**Scenario:**  
Two provisional players (<15 matches) face each other.

**Decision:**  

- Both use **K = 60**  
- \( K_{\text{shared}} = 60 \)  
- Match rated normally  

---

**Rationale:**  
Both ratings uncertain → high K accelerates convergence.

---

## 3.2 Seeded vs Provisional

**Scenario:**  
Seeded player vs provisional player.

**Decision:**  

- Seeded: standard K  
- Provisional: K = 60  
- Shared K = average  

---

**Rationale:**  
Standard pipeline handles this naturally.

---

## 3.3 Extremely Lopsided Matches

**Scenario:**  
Rating gap > 500 points.

**Decision:**  

- Match **not rated**

---

**Rationale:**  
Expected score ~0.97 → near-zero signal. Prevents noise-driven swings.

---

## 3.4 Same Opponent Repeated

**Scenario:**  
Players face each other multiple times in a week.

**Decision:**  

- First 2 matches → normal  
- Subsequent matches → **downweighted to Friendly**  

---

**Rationale:**  
Prevents rating manipulation via repetition.

---

## 3.5 Mixed Match Formats

**Scenario:**  
Event uses Bo3 and Bo5.

**Decision:**  

- Margin-of-victory tables handle format  
- Event weight applied uniformly  

---

**Rationale:**  
Match format is per-match property.

---

## 3.6 Match During Event Transition

**Scenario:**  
Match played before event officially starts.

**Decision:**  

- Only matches within event window count  
- Others default to Friendly  

---

**Rationale:**  
Prevents classification ambiguity.

---

# 4. Academy and Pool Edge Cases

## 4.1 Academy with <5 Players

**Scenario:**  
Small academy.

**Decision:**  

- ASI defaults to global average  

---

**Rationale:**  
Small sample size unreliable.

---

## 4.2 New Academy Mid-Season

**Scenario:**  
New academy joins.

**Decision:**  

- Standard entry  
- ASI defaults until 15 matches  
- No special handling  

---

**Rationale:**  
System supports continuous onboarding.

---

## 4.3 Academy Becomes Inactive

**Scenario:**  
No matches >8 weeks.

**Decision:**  

- ASI **frozen** at last value  

---

**Rationale:**  
Preserves last known state.

---

# 5. Inactivity and Re-entry

## 5.1 Player Inactive 12+ Months

**Decision:**  

- Rating unchanged  
- CR decays to ~0  
- No re-provisional  

---

**Rationale:**  
CR decay already handles recalibration.

---

## 5.2 Seasonal Inactivity

**Decision:**  

- Standard 6-week decay  
- ASI retains active players for 8 weeks  

---

**Rationale:**  
Balances stability vs responsiveness.

---

# 6. Data Integrity Edge Cases

## 6.1 Duplicate Submission

**Decision:**  

- Deduplicate on (Player A, Player B, Event, Date)  
- First accepted  
- Others discarded  

---

## 6.2 Invalid Event ID

**Decision:**  

- Submission rejected  

---

## 6.3 Concurrent Submissions

**Decision:**  

- Process in **chronological order (event timestamp)**  

---

**Rationale:**  
Ensures deterministic rating evolution.

---

# Summary

| Edge Case | Decision | Impact |
|----------|----------|--------|
| Walkover | Not rated | Zero impact |
| Retirement | Rated if ≥1 set | Uses margin |
| Multi-academy | One primary | Prevents gaming |
| Provisional match | High K | Fast convergence |
| Gap >500 | Not rated | Noise protection |
| Duplicate | Deduped | Clean data |
