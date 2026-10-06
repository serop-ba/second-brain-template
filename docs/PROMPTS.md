# Prompt library

Paste these into Claude Code in this folder. Replace the bracketed parts. Claude loads the brain automatically at session start.

## Set up

- `/init`
- *Start me from the [creator | service | saas | ecommerce] profile, then adapt it to: [one line about your business].*
- *Interview me about my business as if you were my first hire. Then file it.*

## Departments and direction

- *Add a [Support] department: lead [me], [3] hours a week, it owns [...]. Fill its page sections from what I just told you.*
- *Which of my departments get no hours but have bets or goals attached? What does that cost me?*
- *Rewrite my north star so it has a number and a date. Ask me questions until it does.*
- *Challenge my three bets. Which doesn't move the north star? What's the cheapest way to find out I'm wrong?*
- *Brief every department. Then tell me the hand-offs between them.*

## Numbers

- *Look at my metrics. Which are vanity metrics, and what should I track instead?*
- *Add a metric [name] under [department]. Define exactly what's counted, and set bands from this goal: [...]*
- *Set healthy, watch and bad bands for [metric] from my price of [X] and margin of [Y]. Show me your arithmetic.*
- *Log today's values: [mrr 2400, newsletter 1,520, expenses 610].*
- *Which of my metrics haven't been updated in two weeks, and which of those could be automatic?*
- *Explain what moved this month in my numbers, using only the data. Say what you can't conclude.*

## Connect

- `/connect` *pull my MRR from Stripe*
- `/connect` *install the YouTube pack for channel [UC...] and tell me what to put in .env*
- `/connect` *my bank exports a CSV monthly: columns are [...]. Turn it into expenses and income metrics.*
- `/connect` *build an automation that pulls [subscriber count] from [Beehiiv / ConvertKit / Substack / Mailchimp]*
- *Check the number the Stripe automation produced against what I read off the Stripe dashboard: [value].*

## Rhythm

- `/weekly`
- *Plan my week. Three to five outcomes, each tied to a bet. Tell me which one you'd cut first.*
- *Plan my day. At most three priorities. Tell me what you left off.*
- `/record` *I decided to [...]*
- `/record` *I changed [price / landing page / ad budget] from [X] to [Y] today.*
- *Which decisions are past their review date? Walk me through each outcome.*
- *What did I decide in the last 90 days that I was most wrong about? What does that say about how I decide?*

## Knowledge

- `/ingest` *[paste a transcript, article or call notes]*
- `/ingest` *the file at [path]*
- *What do my notes say about [topic]? Cite the documents.*
- *Find contradictions between my notes.* (or `/lint`)
- *Turn my last five log entries into a one-page update I can send my [partner / advisor / team].*

## Working with Claude

- *Update my working rules: [be blunter, never hedge, always end with the one thing I should do next].*
- *Show me everything you changed in the last session.* (Claude runs `history --actor claude`.)
- *Undo your last change.*

## Customise the platform itself

- *Add a field to [bets: a "confidence" percent]. Update the schema, the CLI, the console, CLAUDE.md and the tests.*
- *I'm a [coach]. Replace the demo with a realistic example for my kind of business.* (edit `core/seed.py`)
- *Add a starter profile for [restaurants] to catalog/profiles with the departments and metrics that matter.*

## For consultants delivering this to a client

- *Set up a brain for [client name], a [type of business]. Interview me about them in the first person, then file it. Use the [service] profile.*
- *Connect their Stripe and Meta Ads, and show me the numbers next to what they told me their numbers were.*
- *Write the client a one-page handover: where their data lives, the weekly loop, how to back up, who changed what.*
