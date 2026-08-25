-- Add missing processing_status column to domain_documents
ALTER TABLE domain_documents ADD COLUMN IF NOT EXISTS processing_status TEXT DEFAULT 'pending' NOT NULL;
