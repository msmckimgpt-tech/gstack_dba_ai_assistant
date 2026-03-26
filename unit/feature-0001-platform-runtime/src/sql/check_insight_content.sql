USE agent_memory;
SELECT e.FactKey, LEFT(t.TextContent, 200) as content
FROM AgentMemoryFactEntries e
JOIN AgentMemoryTexts t ON e.TextHash = t.TextHash
WHERE e.ConversationId = '__global__'
  AND (e.FactKey LIKE 'schema_insight:%' OR e.FactKey LIKE 'table_insight:%')
ORDER BY e.UpdatedAt DESC
LIMIT 10;
