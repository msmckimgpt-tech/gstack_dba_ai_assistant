USE agent_memory;
SELECT 'AgentMemoryFacts (insight keys)' as what, COUNT(*) as cnt
FROM AgentMemoryFacts
WHERE FactKey LIKE 'schema_insight:%' OR FactKey LIKE 'table_insight:%';

SELECT 'AgentMemoryFactEntries (insight content)' as what, COUNT(*) as cnt
FROM AgentMemoryFactEntries
WHERE ConversationId = '__global__'
AND (FactKey LIKE 'schema_insight:%' OR FactKey LIKE 'table_insight:%');

SELECT FactKey, Weight FROM AgentMemoryFacts
WHERE FactKey LIKE 'schema_insight:%' LIMIT 20;
