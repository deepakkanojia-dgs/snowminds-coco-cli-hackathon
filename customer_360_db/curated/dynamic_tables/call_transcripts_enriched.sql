create or replace dynamic table CUSTOMER_360_DB.CURATED.CALL_TRANSCRIPTS_ENRICHED(
	TRANSCRIPT_ID,
	CUSTOMER_ID,
	CALL_DATE,
	AGENT_ID,
	CALL_DURATION_SECONDS,
	CALL_TYPE,
	CALL_REASON,
	TRANSCRIPT_TEXT,
	SENTIMENT_SCORE,
	CALL_SUMMARY,
	EXTRACTED_COMPLAINT,
	EXTRACTED_RESOLUTION,
	CHURN_INDICATOR,
	RAW_JSON
) target_lag = '1 hour' refresh_mode = FULL initialize = ON_CREATE warehouse = COMPUTE_WH
 as
SELECT 
    t.transcript_id,
    t.customer_id,
    t.call_date,
    t.agent_id,
    t.call_duration_seconds,
    t.call_type,
    t.call_reason,
    t.transcript_text,
    AI_SENTIMENT(t.transcript_text) AS sentiment_score,
    AI_SUMMARIZE(t.transcript_text) AS call_summary,
    SNOWFLAKE.CORTEX.EXTRACT_ANSWER(t.transcript_text, 'What is the customer complaint or issue?')[0]:answer::STRING AS extracted_complaint,
    SNOWFLAKE.CORTEX.EXTRACT_ANSWER(t.transcript_text, 'What action or resolution did the agent offer?')[0]:answer::STRING AS extracted_resolution,
    SNOWFLAKE.CORTEX.EXTRACT_ANSWER(t.transcript_text, 'Is the customer likely to cancel or leave?')[0]:answer::STRING AS churn_indicator,
    t.raw_json
FROM CUSTOMER_360_DB.RAW.RAW_CALL_TRANSCRIPTS t;