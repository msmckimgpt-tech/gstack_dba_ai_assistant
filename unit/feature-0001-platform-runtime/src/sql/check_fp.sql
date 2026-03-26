USE agent_memory;
SELECT 'KV fingerprints' as what, COUNT(*) as cnt FROM AgentMemoryKV WHERE `Key` LIKE 'schema_fp:%' OR `Key` LIKE 'table_fp:%';
SELECT 'KV timestamps' as what, COUNT(*) as cnt FROM AgentMemoryKV WHERE `Key` LIKE '%insight%' OR `Key` LIKE '%scan%';
SELECT 'Fact insights' as what, COUNT(*) as cnt FROM AgentMemoryFactEntries WHERE ConversationId = '__global__' AND (FactKey LIKE 'schema_insight:%' OR FactKey LIKE 'table_insight:%');
