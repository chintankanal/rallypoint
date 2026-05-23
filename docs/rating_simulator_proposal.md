# JLRS Rating Simulator Proposal

## Purpose

Build an interactive Rating Simulator to explain to coaches, players, and parents how JLRS rating dynamics work and why joining JLRS benefits player development. The simulator will let users run scenarios, compare programs, visualize trajectories, and produce shareable outcomes to support onboarding and coaching conversations.

## Target audiences

- Coaches: show program impact, progression forecasts, and recruiting signals.
- Players: demonstrate how match frequency, results, and training translate into rating improvements.
- Parents: visualize long-term benefits and expected timelines.
- Administrators: evaluate retention and program ROI.

## High-level goals

- Demystify JLRS rating system with intuitive visuals and examples.
- Quantify projected rating and ranking outcomes for realistic scenarios.
- Show sensitivity to match results, opponent strength, training, and inactivity.
- Provide exportable, shareable reports for recruitment and onboarding.

## Aspects the simulator should cover

1. Rating model overview
   - Explain the core JLRS rating approach at a high level (behavioral description) and uncertainty/confidence without disclosing proprietary algorithms.
   - Show how a single match result changes a player's standing and why opponent strength, event weight and activity matter.

2. Initial conditions
   - Starting rating: JLRS new players begin at the standard starting level used across the system; the simulator will default to this JLRS starting rating.
   - Provisional period: new players remain provisional for a short onboarding window (the simulator will show the "provisional" marker and faster responsiveness during the first set of matches).
   - Seeded entry: players with documented prior performance may be seeded and skip or shorten the provisional window; the simulator supports seeded presets for district/state/national entry paths.
   - Initial uncertainty: the simulator will surface confidence bands tied to the number of real + virtual matches, reflecting how quickly a rating stabilizes.

3. Match outcome variables
   - Win / loss / draw
   - Margin of victory (if JLRS uses margin-aware adjustments)
   - Opponent rating distribution
   - Home/away or event-weight multipliers

4. Participation and activity
   - Number of matches per week/month/season
   - Match importance (league, tournament, friendly) and its effect on responsiveness
   - Inactivity: JLRS models inactivity as a reduction in rating confidence (not an automatic rating decay); the simulator will show confidence decay over extended inactivity and its effect on projected updates

5. Training and development effects
   - Coach-led practice programs modeled as incremental skill gain per month (user-set slider)
   - Academy program vs independent practice comparison

6. Variance & uncertainty
   - Monte Carlo simulation to show probable rating bands (median, 25/75, 5/95 percentiles)
   - Confidence bands will be driven by JLRS's match-count-based confidence model so users can see how provisional status and inactivity change uncertainty
   - Probability of reaching rating thresholds within X months

7. Career scenarios
   - Short-term (3 months), medium (1 year), long-term (3 years) trajectories
   - Switching academies, coaching changes, injury/absence events

8. Competitive outcomes
   - Projected ranking among peers and within academy (shows Academy Strength Index impact)
   - Estimated win probability vs representative opponents

9. Edge cases and verification
   - Player disputes, result reversals, and effect on rating
   - Voided matches and matches vs provisional players
   - Academy normalization effects and how cross-academy matchups are treated differently from intra-academy matches

10. Privacy and data limitations
   - Synthetic data option and anonymized historical examples
   - Explain assumptions and confidence limits

## What the simulator would show (visuals & outputs)

- Interactive time-series charts: rating vs time with confidence bands.
- Scenario comparison: overlay multiple runs (e.g., with vs without academy training).
- Distribution heatmaps: rating density across season cohorts.
- Match-level breakdown: for each simulated match, show rating change, opponent, and updated uncertainty.
- KPI cards: expected rating change/month, time-to-threshold, win-probabilities.
- Exportable report: PDF/PNG of charts + scenario summary and recommended next steps.
- Shareable link: store scenario parameters and results for coaches to share.

## Interaction / UX patterns

- Preset scenarios: "Typical beginner", "Academy program", "Tournaments heavy", "Infrequent player".
- Sliders and inputs:
  - Starting rating and uncertainty
  - Matches per month
  - Average opponent rating
  - Training gain per month
  - Probability of upset (skill variance)
  - Event weight multipliers
- Timeline scrubber: hover or scrub to view match-by-match changes.
- Compare mode: enable up to 3 scenarios side-by-side.
- Export/Share buttons: PDF, PNG, shareable URL.
- Accessibility: keyboard navigation, clear color contrast, and tooltips.

## Formats and distribution

- Web interactive (primary): built as a React page/component embedded in JLRS marketing and coach dashboards.
- Lightweight static explainer: pre-computed scenario pages as static HTML for marketing emails.
- Video/animated GIFs: short animations of rating trajectories for social and onboarding.
- Printable PDF report: one-page coach-friendly summary for meetings.

## How it would work (technical approach)

1. Simulation engine
   - Client-side engine in TypeScript for instant interactivity using a deterministic rating update function and stochastic outcome sampling.
   - Monte Carlo: run N simulations (e.g., 1,000) to produce distribution bands; default N should be tuned for performance (e.g., 200 for quick preview, 2,000 for full report server-side).
   - Option to offload heavy simulations to server (FastAPI endpoint) when user requests export or large Monte Carlo runs.

2. Rating model
   - Implement the JLRS proprietary rating model as a self-contained library. The implementation will not disclose internal formulas; instead it will expose behavior, inputs, and effects in plain language (for example: how opponent strength, event weight, margin, and activity influence updates).
   - Key JLRS behaviors the simulator will model (described at a high level):
     - Provisional period responsiveness and a visible provisional indicator during early matches.
     - Seeded entry paths (district/state/national presets) that shorten provisional behavior and increase initial confidence.
     - Confidence score tied to the count of real + virtual matches; confidence affects how responsive the rating is to new results.
     - Inactivity reduces confidence (not rating), and the simulator will show how prolonged inactivity increases uncertainty and slows convergence.
     - Academy adjustments: intra-academy matches are weighted differently than cross-academy matches; the simulator will let users toggle and visualize the Academy Strength Index (ASI) normalization effect.
     - Match importance multipliers (league vs tournament vs friendly) and margin-of-victory sensitivity will be represented behaviorally so users can see why certain results move ratings more.
     - Age-contextual bonuses for certain upset scenarios (younger player wins) will be shown as a behavioral modifier without disclosing the internal rule implementation.
   - Model must expose a deterministic single-match update and a batch simulation API with parameters that can be tuned internally (parameters are JLRS-confidential but the simulator UI exposes high-level sliders like "training impact", "match importance", and "average opponent strength").

3. Data & presets
   - Use historical JLRS anonymized data to seed realistic opponent distributions and presets; presets will reflect JLRS tiers, seeded-entry profiles, and academy ASI baselines.
   - Provide synthetic data generator for privacy-safe demos and a "demo" mode that uses representative JLRS cohorts (Beginner → National Track) without any PII.

4. Frontend
   - React + TypeScript component using D3 or charting library (Recharts, Chart.js, or Visx) for time-series and heatmaps.
   - Controls panel for inputs and scenario manager component for saving/comparing scenarios.

5. Backend (optional for heavy workloads)
   - FastAPI endpoint to run large Monte Carlo simulations, cache results, and return shareable scenario IDs.
   - Authentication: optional for coach/admin features like saving team-wide scenarios.

6. Storage & sharing
   - Short-lived shareable URLs containing encoded scenario parameters (for small payloads).
   - For persistent shares: save scenario to DB and return a short ID.

7. Performance
   - Use Web Worker to run simulations without blocking UI.
   - Use WASM or optimized numeric libs only if profiling indicates bottlenecks.

## Validation & testing

- Backtest against historical JLRS match data to ensure simulated distributions match real progression patterns.
- Sensitivity analysis: vary inputs and verify monotonic behavior (more training -> better outcome on average).
- Unit tests for rating updates, match sampling, and scenario serialization.
- UX tests with coaches for clarity and understandability.

## Educational materials & onboarding content

- Quick tour: step-by-step modal explaining sliders and outputs.
- Glossary: plain-language terms such as "confidence band" (uncertainty range), "event weight" (how important a match is), and "activity impact" (how match frequency affects standing).
 - JLRS glossary entries: "provisional" status, "Academy Strength Index (ASI)", "seeded entry" and "confidence score" will be explained in coach-friendly language.
- Scenario library: curated examples with coach commentary.
- One-page explainer for parents: what to expect and how JLRS supports development.

## Privacy & compliance

- Allow demo mode with no PII and synthetic opponents.
- If using real historical data: anonymize player IDs and obey data retention policies.

## Timeline & milestones (suggested)

- Week 1: Requirements & model selection; basic single-match update prototype.
- Week 2: Client-side simulator UI + single-run charting; presets.
- Week 3: Monte Carlo runs with Web Worker; compare mode UI.
- Week 4: Export, shareable links, and server-side batch endpoint (optional).
- Week 5: Backtesting with historical data and UX reviews with coaches.
- Week 6: Polish, accessibility, and rollout to marketing/coach dashboards.

## Success metrics

- Time-on-page for simulator > 2 minutes (engagement).
- Conversion lift: increased onboarding rate for users who interact with simulator.
- Number of shared reports generated by coaches.
- Positive coach feedback in usability testing.

## Deliverables

- Interactive web simulator component (`/web/src/components/RatingSimulator/`).
- Server-side simulation endpoint (`/app/routers/simulator.py`) for heavy runs and sharing.
- Scenario presets and training program templates.
- Documentation: README, user guide, coach playbook, and one-page parent explainer.

## Risks & mitigation

- Misleading predictions: always surface uncertainty and explain assumptions.
- Performance: mitigate with Web Workers and server-side heavy-lifting option.
- Data privacy: provide synthetic demo mode and strict anonymization.

## Next steps (recommended)

- Finalize JLRS proprietary model configuration and confirm explainability language (no public disclosure of formulas).
- Identify sample historical data to seed presets.
- Wireframe UI and run a quick prototype usability session with 3-5 coaches.
- Decide on client-only vs hybrid client-server simulation approach.

---

Author: JLRS Product
Date: 2026-05-18
