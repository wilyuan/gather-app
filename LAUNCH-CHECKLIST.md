# Gather — Launch Checklist

## Phase 1: Get It Live (Day 1-2)

### Step 1: Supabase Setup (30 min)
- [ ] Go to https://supabase.com → Sign up → New Project
- [ ] Name: "gather" | Region: EU West (Frankfurt) | Set a database password
- [ ] Wait for project to provision (~2 min)
- [ ] Go to Settings → API → Copy **Project URL** and **anon public key**
- [ ] Go to SQL Editor → Paste entire contents of `supabase-schema.sql` → Run
- [ ] Verify: go to Table Editor → you should see: cities, categories, profiles, activities, participants, saved_activities

### Step 2: Connect the App (5 min)
- [ ] Open `index.html` in a code editor
- [ ] Find `const SUPABASE_URL = 'YOUR_SUPABASE_URL'` (near top of script)
- [ ] Replace with your Project URL
- [ ] Find `const SUPABASE_ANON_KEY = 'YOUR_SUPABASE_ANON_KEY'`
- [ ] Replace with your anon public key
- [ ] Save the file

### Step 3: Deploy to Vercel (10 min)
- [ ] Create a GitHub repo: `gather-app`
- [ ] Push all files (index.html, manifest.json, sw.js, offline.html)
- [ ] Go to https://vercel.com → Import your GitHub repo
- [ ] Deploy (zero config needed, it's just static files)
- [ ] Your app is now live at `gather-app.vercel.app`
- [ ] Optional: connect a custom domain like `gather.city` or `getgather.app`

### Step 4: Seed Data (1-2 hours)
- [ ] Copy `scraper/.env.example` to `scraper/.env`
- [ ] Fill in your Supabase **service role key** (Settings → API → service_role secret)
- [ ] Optional: Add Google Places API key for business venue scraping
- [ ] Run: `cd scraper && pip install -r requirements.txt`
- [ ] Run: `python scrape.py --city krakow --push`
- [ ] Run: `python scrape.py --city warsaw --push`
- [ ] Verify: open your deployed app → you should see real pins on the map

### Step 5: Test Everything
- [ ] Create an account on the live app
- [ ] Create a one-time activity → verify it appears on the map
- [ ] Try creating a recurring activity (should fail — freemium block)
- [ ] Join an activity → verify participant count updates
- [ ] Switch cities → verify map flies to new location
- [ ] Filter by category, language, time → verify results change
- [ ] Open on iPhone Safari → Add to Home Screen → verify it opens fullscreen
- [ ] Test on Android Chrome → verify PWA install prompt appears

## Phase 2: First Users (Week 1-2)

### Community Seeding
- [ ] Identify 20 active Facebook groups for expats/internationals in Kraków
- [ ] Draft a short, genuine post: "I built a free app that puts Kraków activities on a map..."
- [ ] Post in 3-5 groups (don't spam — space them over a few days)
- [ ] Identify 10 recurring activity organizers in Kraków (board game cafés, dance studios, running groups)
- [ ] Message them directly: "I found your [event] and added it to Gather — want to claim your listing?"

### Reddit & Online
- [ ] Post on r/krakow — frame as "I built this for the expat community, feedback wanted"
- [ ] Post on r/poland — same angle
- [ ] Post on r/digitalnomad — "made a free tool for finding activities in Polish cities"
- [ ] Join Kraków expat Telegram/WhatsApp groups and share naturally

### University Channels
- [ ] Contact Jagiellonian University international student office
- [ ] Contact AGH international student office
- [ ] Ask if they can share with incoming Erasmus students
- [ ] Post in university Facebook groups and Discord servers

## Phase 3: Validate & Iterate (Week 3-4)

### Metrics to Watch
- [ ] Set up Supabase dashboard to track: signups, activities created, joins per day
- [ ] Monitor: do users come back after day 1? (retention)
- [ ] Monitor: are users creating their own activities or just browsing?
- [ ] Monitor: which categories get the most engagement?

### Signals That It's Working
- Users creating activities you didn't seed
- Same users coming back multiple times
- People sharing the app link in group chats
- Organizers asking to "claim" their listing
- Anyone asking "when are you adding [city]?"

### Signals to Pivot
- Many signups but no one joins activities (discovery is fine, conversion is broken)
- People browse but never create (too much friction, or they don't trust the platform yet)
- Zero organic sharing after 2 weeks of active community seeding

## Phase 4: Monetization (Month 2-3)

### Premium Feature Launch
- [ ] Add Stripe integration (Stripe Atlas works in Poland)
- [ ] Premium price: 29 PLN/month or 249 PLN/year
- [ ] Premium features: recurring events, analytics (views/joins), promoted placement
- [ ] Add upgrade flow in the app (profile → Upgrade to Premium)
- [ ] Email the organizers who already have recurring events: "upgrade to keep your listing"

### Promoted Listings (Later)
- [ ] Once 5K+ monthly active users
- [ ] Businesses pay 49-99 PLN/month for highlighted pins and search priority
- [ ] Self-serve dashboard for businesses to manage their listing
