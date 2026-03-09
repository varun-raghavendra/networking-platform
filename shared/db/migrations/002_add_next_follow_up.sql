ALTER TABLE contacts ADD COLUMN IF NOT EXISTS next_follow_up_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS idx_contacts_next_follow_up ON contacts(next_follow_up_at) WHERE next_follow_up_at IS NOT NULL;
