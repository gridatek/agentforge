-- Enable pgvector. The pgvector/pgvector image ships the extension; this turns
-- it on for the agentforge database. langchain-postgres creates its own tables.
CREATE EXTENSION IF NOT EXISTS vector;
