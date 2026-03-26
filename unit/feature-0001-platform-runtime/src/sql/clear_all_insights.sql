USE agent_memory;

-- Clear all fingerprints and timestamps
DELETE FROM AgentMemoryKV WHERE `Key` LIKE 'schema_fp:%'
   OR `Key` LIKE 'table_fp:%'
   OR `Key` = 'schema_insights_bootstrap_at'
   OR `Key` = 'schema_instance_scan_at'
   OR `Key` LIKE 'schema_insight_refresh_at:%'
   OR `Key` LIKE 'table_insight_refresh_at:%'
   OR `Key` LIKE 'schema_instance_scan_offset:%'
   OR `Key` = 'schema_instance_scan_schema_offset';

-- Clear all insight fact entries
DELETE FROM AgentMemoryFactEntries WHERE ConversationId = '__global__'
   AND (FactKey LIKE 'schema_insight:%' OR FactKey LIKE 'table_insight:%');

-- Also clear from insight worker conversation
DELETE FROM AgentMemoryFactEntries WHERE ConversationId = '__insight_worker__'
   AND (FactKey LIKE 'schema_insight:%' OR FactKey LIKE 'table_insight:%');
