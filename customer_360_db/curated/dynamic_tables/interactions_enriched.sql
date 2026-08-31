create or replace dynamic table CUSTOMER_360_DB.CURATED.INTERACTIONS_ENRICHED(
	INTERACTION_ID,
	CUSTOMER_ID,
	INTERACTION_DATE,
	CHANNEL,
	INTERACTION_TYPE,
	SUBJECT,
	CONTENT,
	SENTIMENT_SCORE,
	RESOLVED,
	AGENT_ID
) target_lag = '1 hour' refresh_mode = AUTO initialize = ON_CREATE warehouse = COMPUTE_WH
 as
SELECT 
    i.interaction_id,
    i.customer_id,
    i.interaction_date,
    i.channel,
    i.interaction_type,
    i.subject,
    i.content,
    AI_SENTIMENT(i.content) AS sentiment_score,
    i.resolved,
    i.agent_id
FROM CUSTOMER_360_DB.RAW.RAW_INTERACTIONS i;