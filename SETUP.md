# Gather App — Setup Guide

## Quick Start (Demo Mode)
Just open `index.html` in your browser. The app works immediately with 48 real activities across Warsaw and Kraków — no backend needed. This is perfect for testing, demoing, and validating the concept.

## Connecting Supabase (Production Mode)

### 1. Create a Supabase Project
- Go to https://supabase.com and sign up (free tier is fine)
- Click "New Project", name it "gather", choose a region close to Poland (EU West)
- Save your **Project URL** and **anon/public key** from Settings → API

### 2. Run the Database Schema
- In your Supabase dashboard, go to **SQL Editor**
- Paste the entire contents of `supabase-schema.sql` and click **Run**
- This creates all tables, indexes, RLS policies, the freemium trigger, and seeds categories + cities

### 3. Configure the App
Open `index.html` and find these two lines near the top of the `<script>`:
```
const SUPABASE_URL = 'YOUR_SUPABASE_URL';
const SUPABASE_ANON_KEY = 'YOUR_SUPABASE_ANON_KEY';
```
Replace with your actual values from step 1.

### 4. Enable Auth
- In Supabase dashboard → Authentication → Providers
- Email auth is enabled by default
- Optional: enable Google, Apple, or Facebook OAuth for social login

### 5. Seed Real Activities
Once connected, you can seed activities by inserting rows into the `activities` table via the Supabase Table Editor or SQL. The demo data in the HTML gives you the exact format.

## Architecture

```
index.html          — Complete single-page app (PWA-ready)
manifest.json       — PWA manifest for "Add to Home Screen"
supabase-schema.sql — Full database schema + RLS + seed data
```

### Database Tables
- **cities** — Launch cities (Warsaw, Kraków)
- **profiles** — User profiles (auto-created on signup)
- **categories** — 15 activity categories
- **activities** — Core table with location, timing, frequency, language
- **participants** — Join/leave tracking
- **saved_activities** — Bookmarks

### Key Features
- **Freemium model**: One-time events are always free. Recurring (weekly/biweekly/monthly) events require Premium — enforced at the database level via trigger.
- **Language labels**: Every activity tagged EN, PL, or EN/PL with color-coded badges.
- **City switching**: Fly between cities with animated map transitions.
- **PostGIS**: Spatial indexing for fast map queries at scale.
- **RLS (Row Level Security)**: Users can only edit/delete their own content.

## What's Next
1. **Deploy**: Host on Vercel, Netlify, or GitHub Pages (it's just static files)
2. **Scraper**: Build a Python script to pull events from Google Maps, Facebook, Meetup, Eventbrite
3. **Premium/Stripe**: Add Stripe checkout for Premium subscriptions
4. **Push notifications**: Use Supabase Edge Functions + web push
5. **Native app**: Wrap in React Native or Capacitor for App Store
