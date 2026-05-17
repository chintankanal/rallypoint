# JLRS Foolproof User & Player Workflow

## 1. The Core Philosophy
To prevent confusion and data duplication, we must decouple **Authentication** (User Account) from **League Participation** (Player Profile/Official Role).

*   **Users** "own" accounts (email/password).
*   **Players/Officials** are "roles" within the league.
*   Linking is done via a **Unique Claim Code** rather than matching emails.

---

## 2. Player Workflow: The "Provision & Claim" Model
This removes the risk of email mismatch.

### Step 1: Provisioning (Coach)
1.  The Coach goes to the Dashboard and clicks "Register Player."
2.  The Coach enters the player's name, DOB, and Nationality (required for ranking).
3.  **Key Change:** The system generates a unique 6-character **Claim Code** (e.g., `XY72-Z`) for that player profile.
4.  The Coach gives this code to the parent/athlete.

### Step 2: Account Creation (Player/Parent)
1.  The User (Parent or Player) registers via the common `Login.tsx` form. They can use *any* email/phone they prefer.
2.  Upon first login, the system asks: "Are you a new player or claiming an existing profile?"
3.  The User enters the **Claim Code**.
4.  **Result:** The `users.user_id` is now linked to the `Player.player_id`.

**Note on Sharing:** For players, the Coach typically shares the code in person or via the system's "Send Notification" button, which triggers an automated email to the `contact_email` provided.

---

## 3. Privileged Roles Workflow (Coaches, Umpires & Referees)
To maintain league integrity, privileged roles cannot be self-selected during public registration. They must be provisioned by an **Admin**. Both of the following approaches are supported:

### Approach 1: Direct Account Creation (Pre-authenticated)
1.  The Admin creates the User account directly in the System.
2.  The Admin assigns the specific role (`COACH`, `REFEREE`, or `UMPIRE`) and relevant `academy_id` (for Coaches).
3.  **Automatic Dispatch:** The system automatically sends a "Welcome" email to the user.
4.  **First-Time Login:** The user logs in using **Email OTP**. Upon successful entry, they are prompted to set a permanent password (optional).
5.  **Subsequent Logins:** The user can log in via their password or continue using Email OTP as a fallback/primary method.

**Example (Senior Referee):**
Admin creates a user for *Rajan Kumar* with email `rajan.ref@official.com` and role `REFEREE`. Rajan receives a "Welcome" email, enters his email on the login page, receives a 6-digit code, and immediately sees his assigned events.

### Approach 2: Official Invitation (Claim-based)
1.  The Admin creates an "Official Profile" (Coach/Referee/Umpire) without an associated user account.
2.  The system generates a unique **Claim Code**.
3.  **Automatic Dispatch:** The Admin clicks "Send Invitation," and the system emails the recipient an "Official Invitation." This email contains the **Claim Code** and a link to the registration page.
4.  The recipient registers an account (using any email/phone) and enters the code to "Claim" their verified role.

**Example (New Academy Coach):**
Admin provisions a profile for *Coach Arjun* at *City Academy*. The system generates code `COACH-99-AX`. Arjun receives an invite email, decides to register with his personal Gmail, enters the code during onboarding, and is instantly linked to his academy as a Coach.

### Summary of Sharing Mechanism
| Method | Delivery | Contents |
| :--- | :--- | :--- |
| **Approach 1** | Automated Email | **Authentication:** Instructions to login via Email OTP for first-time setup. |
| **Approach 2** | Automated Email | **Authorization:** Claim Code and Registration Link. |

### Step 2: Event Assignment (Dynamic)
Once a User is linked to a `REFEREE` or `UMPIRE` role, they become part of the global league directory.
1.  **Assigning:** For a specific event, an Admin (or Host Coach) searches the global directory for "Registered Umpires."
2.  They add the Umpire to the event.
3.  **Portability:** The Umpire now sees that event in their dashboard. When the event ends, the link remains in history, but their active write-access to that event's tables expires.

---

## 4. Foolproof Logic Rules

| Scenario | Solution |
| :--- | :--- |
| **Admin Control** | Only Admins can authorize privileged roles. The system blocks `COACH/REFEREE/UMPIRE` roles in public registration. |
| **Auto-Notification** | Any generation of a Claim Code or Account creation triggers an automated system email to the recipient. |
| **Email Mismatch** | Claim Codes ignore emails. Linking is explicit and intentional. |
| **Duplicate Player Profiles** | Coaches can see a "League Directory" search before creating a new profile to see if a player exists in another academy. |
| **Hybrid Auth** | The system supports secure passwords, but uses **Email OTP** for the first login, password resets, and as a passwordless fallback. |
| **Role Security** | The `Role` dropdown is removed from public registration. Default role is always `PLAYER`. `COACH/REFEREE/UMPIRE` roles must be "Claimed" or "Invited." |
| **Multi-Academy Players** | A `Player` record has one `primary_academy_id`. If they move, a "Transfer" is logged. They don't need a new profile. |

---

## 5. Technical Implementation Adjustments

### Schema Update
*   Add `claim_code` (String, Unique) and `is_claimed` (Boolean) to the `Player` table.
*   Add `claim_code` to the `Users` table (temporary storage until link is established).

### UI Changes
*   **Login/Register Form:** Remove the "Role" dropdown. Everyone registers as a standard User.
*   **Onboarding Screen:** A new view for first-time users to either "Start as New Player" or "Enter Claim Code."
*   **Coach Dashboard:** Display the `Claim Code` prominently next to unlinked players in the roster.

---

## 6. Testing Locally (Without a Domain)
If a custom domain is not yet registered, use the **Resend Sandbox**:
1.  **Sign up** at resend.com.
2.  **API Key:** Add `RESEND_API_KEY` to your local `.env`.
3.  **Sender:** Set `FROM_EMAIL` to `onboarding@resend.dev`.
4.  **Recipient Limit:** In sandbox mode, you can **only** send emails to your own registered Resend account email. Use this email when creating test Players or Coaches to verify the delivery flow.

---
*End of Workflow Proposal*