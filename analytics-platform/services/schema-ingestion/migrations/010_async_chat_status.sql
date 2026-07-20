-- Add status column to conversation_messages for async chat processing
ALTER TABLE conversation_messages ADD COLUMN status TEXT DEFAULT 'processing' NOT NULL;
