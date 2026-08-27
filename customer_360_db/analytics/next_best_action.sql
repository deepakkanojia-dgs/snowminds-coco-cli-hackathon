create or replace dynamic table CUSTOMER_360_DB.ANALYTICS.NEXT_BEST_ACTION(
	CUSTOMER_ID,
	FULL_NAME,
	CUSTOMER_SEGMENT,
	CHURN_RISK,
	TOTAL_ANNUAL_PREMIUM,
	OVERALL_SENTIMENT_SCORE,
	RECOMMENDED_ACTION,
	GENERATED_AT
) target_lag = '1 hour' refresh_mode = AUTO initialize = ON_CREATE warehouse = COMPUTE_WH
 as
SELECT 
    customer_id,
    full_name,
    customer_segment,
    churn_risk,
    total_annual_premium,
    overall_sentiment_score,
    AI_COMPLETE('llama3.3-70b',
        CONCAT('You are an insurance customer success AI. Based on the following customer profile, recommend ONE specific next best action. Be concise (2-3 sentences max). Include the action category in brackets at the start: [RETAIN], [UPSELL], [RESOLVE], [ENGAGE], or [WIN-BACK].\n\nCustomer: ', full_name, '\nSegment: ', customer_segment, '\nAnnual Premium: Rs ', total_annual_premium::STRING, '\nTenure: ', tenure_months::STRING, ' months\nActive Policies: ', active_policies::STRING, ' (', COALESCE(policy_types, 'None'), ')\nLapsed Policies: ', lapsed_policies::STRING, '\nTotal Claims: ', total_claims::STRING, ' (Rejected: ', rejected_claims::STRING, ', Pending: ', pending_claims::STRING, ')\nAvg Claim Satisfaction: ', COALESCE(avg_claim_satisfaction::STRING, 'N/A'), '/5\nSentiment Score: ', overall_sentiment_score::STRING, ' (scale -1 to +1)\nChurn Risk: ', churn_risk, '\nUnresolved Issues: ', unresolved_issues::STRING, '\nRecent Call History: ', COALESCE(call_history::STRING, 'No calls recorded'))
    ) AS recommended_action,
    CURRENT_TIMESTAMP() AS generated_at
FROM CUSTOMER_360_DB.ANALYTICS.CUSTOMER_360;