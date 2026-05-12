-- Phase 1: Auth + Roles + RLS Foundation
-- Created: 2026-05-12

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create roles enum
CREATE TYPE user_role AS ENUM (
  'graves_ops_super',
  'days_ops_super',
  'swings_ops_super',
  'utility_ops_super',
  'ops_super',
  'ops_manager',
  'ops_director',
  'admin',
  'sudo_admin'
);

-- Create users table
CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  email TEXT UNIQUE NOT NULL,
  full_name TEXT NOT NULL,
  role user_role NOT NULL DEFAULT 'ops_super',
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS on users table
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- Update view_edit_log (Trail) table to include user fields
ALTER TABLE view_edit_log 
  ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id),
  ADD COLUMN IF NOT EXISTS full_name TEXT,
  ADD COLUMN IF NOT EXISTS user_role user_role;

-- Enable RLS on view_edit_log
ALTER TABLE view_edit_log ENABLE ROW LEVEL SECURITY;

-- Enable RLS on placements table
ALTER TABLE placements ENABLE ROW LEVEL SECURITY;

-- Basic RLS Policies (will be refined in later phases)

-- Users can read their own profile
CREATE POLICY "Users can read own profile" ON users
  FOR SELECT USING (auth.uid() = id);

-- Ops Manager+ can read all users
CREATE POLICY "Ops Manager+ can read all users" ON users
  FOR SELECT USING (
    (SELECT role FROM users WHERE id = auth.uid()) IN ('ops_manager', 'ops_director', 'admin', 'sudo_admin')
  );

-- Trail entries are insert-only by authenticated users
CREATE POLICY "Authenticated users can insert trail entries" ON view_edit_log
  FOR INSERT WITH CHECK (auth.uid() IS NOT NULL);

-- Users can read their own trail entries + relevant entries
CREATE POLICY "Users can read relevant trail entries" ON view_edit_log
  FOR SELECT USING (
    user_id = auth.uid() OR 
    (SELECT role FROM users WHERE id = auth.uid()) IN ('ops_manager', 'ops_director', 'admin', 'sudo_admin')
  );

-- Note: placements RLS will be refined based on shift and role in Phase 2
COMMENT ON TABLE users IS 'Phase 1: Core users table with roles for ZDS Forge';
COMMENT ON TABLE view_edit_log IS 'Phase 1: Updated with user attribution for Trail logging';