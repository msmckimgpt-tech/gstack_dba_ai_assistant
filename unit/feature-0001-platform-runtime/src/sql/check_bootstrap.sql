USE agent_memory;
SELECT `Key`, LEFT(`Value`, 80) as val FROM AgentMemoryKV
WHERE `Key` IN ('schema_insights_bootstrap_at', 'schema_instance_scan_at')
   OR `Key` LIKE 'schema_insight_refresh_at:%'
LIMIT 30;
