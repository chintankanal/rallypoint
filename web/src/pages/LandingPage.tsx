import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Layout, Spinner, ErrorMsg } from '../components/Layout'
import { overviewApi } from '../api/client'

function formatCount(value: number | undefined) {
  return value === undefined ? '—' : new Intl.NumberFormat('en-US').format(value)
}

export default function LandingPage() {
  const overviewQuery = useQuery({
    queryKey: ['overview'],
    queryFn: overviewApi.get,
    staleTime: 60_000,
  })

  const overview = overviewQuery.data

  return (
    <Layout>
      <section className="relative overflow-hidden rounded-3xl border border-gray-800 bg-slate-950 shadow-2xl shadow-black/30 px-6 py-16 sm:px-10 lg:px-16">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(56,189,248,0.16),_transparent_36%),radial-gradient(circle_at_30%_50%,_rgba(59,130,246,0.14),_transparent_28%)]" />
        <div className="relative mx-auto max-w-6xl">
          <div className="grid gap-12 lg:grid-cols-[1.4fr_1fr] items-center">
            <div className="space-y-8">
              <div className="inline-flex rounded-full bg-blue-500/10 px-4 py-1 text-sm font-semibold text-blue-300 ring-1 ring-blue-400/20">
                League ranking for the next generation
              </div>
              <div>
                <h1 className="text-4xl font-bold tracking-tight text-white sm:text-5xl">
                  Elevate Your Game. Track Your Progress. Join the League.
                </h1>
                <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-300">
                  A sophisticated, data-driven rating system built for junior athletes, coaches, and academies. JLRS brings Elo-based ratings, tiered progression, and live analytics together in a single ranking experience.
                </p>
              </div>

              <div className="flex flex-wrap gap-3">
                <Link
                  to="/leaderboard"
                  className="inline-flex items-center justify-center rounded-full bg-blue-500 px-6 py-3 text-sm font-semibold text-white transition hover:bg-blue-400"
                >
                  View Live Leaderboards
                </Link>
                <Link
                  to="/login"
                  className="inline-flex items-center justify-center rounded-full border border-blue-500/40 bg-white/5 px-6 py-3 text-sm font-semibold text-blue-200 transition hover:bg-white/10"
                >
                  Register for JLRS
                </Link>
              </div>
            </div>

            <div className="rounded-3xl border border-white/10 bg-white/5 p-8 shadow-xl shadow-slate-950/20 backdrop-blur">
              <div className="grid gap-6">
                <div className="rounded-3xl border border-blue-500/10 bg-slate-950/80 p-6">
                  <p className="text-xs font-semibold uppercase tracking-[0.24em] text-blue-300">Live ecosystem snapshot</p>
                  <p className="mt-3 text-3xl font-semibold text-white">JLRS in motion</p>
                </div>
                <div className="grid gap-4">
                  <div className="rounded-2xl bg-slate-900/80 p-5 ring-1 ring-white/5">
                    <p className="text-sm text-slate-400">Player progress, ratings, and match weightings are updated continuously as results are confirmed.</p>
                  </div>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="rounded-2xl bg-slate-900/90 p-4">
                      <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Registered Players</p>
                      <p className="mt-3 text-3xl font-semibold text-white">{formatCount(overview?.total_players)}</p>
                    </div>
                    <div className="rounded-2xl bg-slate-900/90 p-4">
                      <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Matches Processed</p>
                      <p className="mt-3 text-3xl font-semibold text-white">{formatCount(overview?.matches_processed)}</p>
                    </div>
                    <div className="rounded-2xl bg-slate-900/90 p-4 sm:col-span-2">
                      <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Participating Academies</p>
                      <p className="mt-3 text-3xl font-semibold text-white">{formatCount(overview?.participating_academies)}</p>
                    </div>
                  </div>
                  {overviewQuery.isLoading && <Spinner />}
                  {overviewQuery.error && <ErrorMsg message={(overviewQuery.error as Error).message} />}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="mt-12 space-y-10">
        <div className="grid gap-6 md:grid-cols-3">
          <Card title="Dynamic Rating" accent="text-blue-400">
            Ratings shift after every confirmed result, accounting for opponent strength, match category, and whether the event is tournament-level, league play, or friendly competition.
          </Card>
          <Card title="Tiered Progression" accent="text-orange-400">
            Players progress naturally through Beginner, Intermediate, Advanced, Elite, and National Track tiers as they earn wins and continue competing.
          </Card>
          <Card title="Accuracy & Fairness" accent="text-green-400">
            The Active Status Index keeps the leaderboard honest by favoring active competitors and gradually pausing inactive profiles until they return to play.
          </Card>
        </div>

        <div className="rounded-3xl border border-gray-800 bg-gray-900/80 p-8">
          <div className="flex flex-col gap-8 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-sm uppercase tracking-[0.24em] text-blue-400">Tier System</p>
              <h2 className="mt-3 text-3xl font-bold text-white">From Beginner to National Track</h2>
              <p className="mt-4 max-w-2xl text-slate-400">
                JLRS uses tier thresholds to help coaches, parents, and players see progress at a glance while still honoring the nuance of Elo-based rating movement.
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {[
                ['Beginner', '0–899'],
                ['Intermediate', '900–1099'],
                ['Advanced', '1100–1299'],
                ['Elite', '1300–1499'],
                ['National Track', '1500+'],
              ].map(([label, range]) => (
                <div key={label} className="rounded-3xl bg-slate-950/80 p-4 ring-1 ring-white/5">
                  <p className="text-sm text-slate-400">{label}</p>
                  <p className="mt-2 text-xl font-semibold text-white">{range}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="grid gap-8 lg:grid-cols-2">
          <section className="rounded-3xl border border-gray-800 bg-slate-950/80 p-8">
            <p className="text-sm uppercase tracking-[0.24em] text-blue-400">Player Profiles</p>
            <h2 className="mt-3 text-3xl font-bold text-white">Your progress, visualized.</h2>
            <p className="mt-4 text-slate-400">
              Every player profile includes rating history, head-to-head comparison, and match breakdown by category so athletes can understand how wins, losses, and strong opponents shape their trajectory.
            </p>
            <div className="mt-8 space-y-4 text-sm text-slate-300">
              <p>• Rating history charts to monitor momentum.</p>
              <p>• Head-to-head snapshots for key rivalries.</p>
              <p>• Match weightings that separate league, tournament, and friendly results.</p>
            </div>
          </section>

          <section className="rounded-3xl border border-gray-800 bg-slate-950/80 p-8">
            <p className="text-sm uppercase tracking-[0.24em] text-blue-400">Academy integration</p>
            <h2 className="mt-3 text-3xl font-bold text-white">Built for cross-academy competition.</h2>
            <p className="mt-4 text-slate-400">
              Academies can rely on JLRS for fair seeding across internal and inter-academy matches. Match multipliers make cross-academy results meaningful while preserving local development goals.
            </p>
            <div className="mt-8 space-y-4 text-sm text-slate-300">
              <p>• `w_same_academy` rewards local match stability.</p>
              <p>• `w_cross_academy` gives extra weight to competitive inter-academy play.</p>
              <p>• Live ASI tracking helps coaches identify active talent and keep leaderboards current.</p>
            </div>
          </section>
        </div>
      </section>

      <section id="faq" className="mt-12 rounded-3xl border border-gray-800 bg-slate-950/80 p-8">
        <div className="grid gap-8 lg:grid-cols-[1.2fr_0.8fr]">
          <div>
            <p className="text-sm uppercase tracking-[0.24em] text-blue-400">FAQ</p>
            <h2 className="mt-3 text-3xl font-bold text-white">How does JLRS create a fair ranking?</h2>
            <p className="mt-4 text-slate-400 leading-7">
              JLRS combines Elo-style math with configurable match weights and an Active Status Index. This keeps top positions reserved for players who are consistently competing and winning against strong opponents.
            </p>
          </div>
          <div className="space-y-4 rounded-3xl bg-slate-900/80 p-6 ring-1 ring-white/5">
            <div>
              <h3 className="text-lg font-semibold text-white">What is ASI?</h3>
              <p className="mt-2 text-slate-400">
                The Active Status Index rewards only regularly active players, so stale ratings don't dominate the leaderboard.
              </p>
            </div>
            <div>
              <h3 className="text-lg font-semibold text-white">Why are match types weighted?</h3>
              <p className="mt-2 text-slate-400">
                Tournament and league games carry more impact than friendly practice matches, reflecting the competitive context of each result.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section id="privacy" className="mt-12 rounded-3xl border border-gray-800 bg-gray-900/95 p-8">
        <div className="grid gap-6 lg:grid-cols-3">
          <div>
            <p className="text-sm uppercase tracking-[0.24em] text-blue-400">Resources</p>
            <ul className="mt-4 space-y-3 text-sm text-slate-300">
              <li>
                <a href="#faq" className="text-slate-200 hover:text-white">FAQ</a>
              </li>
              <li>
                <Link to="/leaderboard" className="text-slate-200 hover:text-white">Live Leaderboards</Link>
              </li>
              <li>
                <a href="mailto:support@jlrs.example.com" className="text-slate-200 hover:text-white">Contact support</a>
              </li>
            </ul>
          </div>
          <div className="lg:col-span-2">
            <p className="text-sm uppercase tracking-[0.24em] text-blue-400">Privacy</p>
            <p className="mt-3 text-slate-400 leading-7">
              JLRS keeps athlete and academy data secure. Ratings, match results, and academy relationships are only visible to authorized users through the platform, while public leaderboards remain focused on performance and progression.
            </p>
            <p className="mt-4 text-sm text-slate-500">Privacy Policy & Terms apply to all users and participants of the JLRS platform.</p>
          </div>
        </div>
      </section>
    </Layout>
  )
}

function Card({ title, accent, children }: { title: string; accent: string; children: React.ReactNode }) {
  return (
    <div className="rounded-3xl border border-gray-800 bg-slate-950/80 p-6 shadow-sm shadow-black/10">
      <p className={`text-sm font-semibold uppercase tracking-[0.24em] ${accent}`}>{title}</p>
      <p className="mt-4 text-slate-300 leading-7">{children}</p>
    </div>
  )
}
