# Proposal: JLRS Landing Page Redesign

## 1. Executive Summary
The Junior League Rating System (JLRS) currently defaults to a leaderboard view. While functional for returning users, it lacks context for new visitors. This proposal outlines the transition from a "Data-First" approach to a "Value-First" approach by implementing a professional landing page that explains the rating system, benefits, and call-to-actions (CTAs) before diving into the statistics.

## 2. Target Audience
*   **Junior Athletes:** Looking to track their progress and see where they stand.
*   **Parents:** Seeking a fair, transparent way to understand their child's competitive level.
*   **Coaches/Academies:** Using the system to seed tournaments and evaluate training effectiveness.
*   **Organizers:** Looking for a reliable tool to manage league fairness.

## 3. Key Objectives
*   **Provide Context:** Explain the Elo-based math and tier system (Beginner to National Track).
*   **Encourage Participation:** Clear CTAs for registration and match reporting.
*   **Build Trust:** Highlight the "Active Status Index" (ASI) and inactivity logic to show the rankings are live and accurate.
*   **Improve UX:** Create a logical flow from "What is this?" to "How do I join?" to "Where is the data?".

## 4. Proposed Content Architecture

### Section 1: Hero Section (The Hook)
*   **Headline:** "Elevate Your Game. Track Your Progress. Join the League."
*   **Sub-headline:** "A sophisticated, data-driven rating system designed specifically for the next generation of athletes."
*   **Primary CTA:** [View Live Leaderboards]
*   **Secondary CTA:** [Register for JLRS]
*   **Background:** High-quality action shot of junior sports (badminton/tennis) with a dark overlay.

### Section 2: How It Works (The Logic)
A three-column layout explaining the core mechanics found in our configuration:
1.  **Dynamic Rating:** Explain that ratings change based on match results, opponent strength, and match type (Tournament vs. Friendly).
2.  **Tiered Progression:** Show the progression from *Beginner* (0-899) through *Elite* and *National Track*.
3.  **Accuracy & Fairness:** Mention the ASI (Active Status Index) which ensures that only active, proven players stay at the top.

### Section 3: Live Ecosystem Stats (Social Proof)
A "ribbon" style bar showing real-time numbers:
*   **[X]** Registered Players
*   **[Y]** Matches Processed
*   **[Z]** Participating Academies

### Section 4: Player Profiles & Analytics
Highlight what a player gets once they log in:
*   Rating history charts.
*   Head-to-head statistics.
*   Match breakdown by weightage (League vs. Friendly).

### Section 5: Academy Integration
Briefly explain how academies can use the system for cross-academy matches and internal seeding, utilizing the `w_cross_academy` and `w_same_academy` multipliers.

### Section 6: Footer
*   Links to FAQ (Math breakdown).
*   Contact support.
*   Privacy Policy & Terms.

## 5. Visual Guidelines
*   **Color Palette:**
    *   Primary: Deep Navy (Professionalism/Trust).
    *   Accent: Electric Blue or Vibrant Orange (Energy/Youth).
    *   Success: Green (for rating gains).
*   **Typography:** Clean, sans-serif fonts (e.g., Inter or Montserrat) for high readability.
*   **Mobile-First:** The majority of users will check rankings on their phones at tournament venues. The landing page must be lightweight and responsive.

## 6. User Flow Transition

**Current Flow:**
1. User enters URL -> Leaderboard Table.

**Proposed Flow:**
1. User enters URL -> Landing Page (Value Proposition).
2. User clicks "View Leaderboard" -> Filterable Ranking View.
3. User clicks "Player Name" -> Authenticated/Public Profile.

## 7. Technical Implementation Notes
*   **Route Handling:** Update the FastAPI/Frontend router to serve the Landing Page at `/` and move the leaderboard to `/leaderboard`.
*   **SEO:** Implement Meta tags (OpenGraph) so when the link is shared on WhatsApp/Social Media, it shows a preview of the JLRS mission rather than just a raw table.
*   **Caching:** Since the landing page is mostly static, it should be cached aggressively, while the "Live Stats" ribbon can be updated via a lightweight API call to the `/api/v1/config` and stats endpoints.

## 8. Success Metrics
*   **Reduced Bounce Rate:** Fewer users leaving immediately because they didn't understand the table.
*   **Increased Registrations:** Higher conversion from "Visitor" to "Registered User".
*   **Engagement Time:** More time spent on the site reading the "How it Works" section.

---
*End of Proposal*