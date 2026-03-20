-- Run this in Supabase SQL Editor (Dashboard → SQL Editor → New Query)

CREATE TABLE tips (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    handle TEXT NOT NULL,
    competition TEXT,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    match_date DATE,
    result_pick TEXT NOT NULL CHECK (result_pick IN ('H', 'D', 'A')),
    home_goals INTEGER NOT NULL,
    away_goals INTEGER NOT NULL,
    confidence INTEGER NOT NULL CHECK (confidence BETWEEN 1 AND 5),
    reasoning TEXT,
    is_correct BOOLEAN DEFAULT NULL,
    actual_home INTEGER DEFAULT NULL,
    actual_away INTEGER DEFAULT NULL,
    submitted_at TIMESTAMPTZ DEFAULT NOW()
);

-- Allow anyone to insert and read (no login required)
ALTER TABLE tips ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anyone can insert tips"
    ON tips FOR INSERT TO anon WITH CHECK (true);

CREATE POLICY "Anyone can read tips"
    ON tips FOR SELECT TO anon USING (true);

CREATE POLICY "Anyone can update tips"
    ON tips FOR UPDATE TO anon USING (true);
