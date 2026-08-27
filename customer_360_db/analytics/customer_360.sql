create or replace dynamic table CUSTOMER_360_DB.ANALYTICS.CUSTOMER_360(
	CUSTOMER_ID,
	FULL_NAME,
	EMAIL,
	PHONE,
	CITY,
	STATE,
	CUSTOMER_SEGMENT,
	TENURE_MONTHS,
	ANNUAL_INCOME,
	CREDIT_SCORE,
	PREFERRED_CHANNEL,
	IS_ACTIVE,
	TOTAL_POLICIES,
	ACTIVE_POLICIES,
	LAPSED_POLICIES,
	TOTAL_ANNUAL_PREMIUM,
	POLICY_TYPES,
	TOTAL_CLAIMS,
	SETTLED_CLAIMS,
	PENDING_CLAIMS,
	REJECTED_CLAIMS,
	TOTAL_AMOUNT_CLAIMED,
	TOTAL_AMOUNT_APPROVED,
	AVG_RESOLUTION_DAYS,
	AVG_CLAIM_SATISFACTION,
	TOTAL_CALLS,
	AVG_CALL_SENTIMENT,
	WORST_CALL_SENTIMENT,
	LAST_CALL_DATE,
	TOTAL_INTERACTIONS,
	AVG_INTERACTION_SENTIMENT,
	UNRESOLVED_ISSUES,
	CHANNELS_USED,
	OVERALL_SENTIMENT_SCORE,
	CHURN_RISK,
	CALL_HISTORY
) target_lag = '1 hour' refresh_mode = AUTO initialize = ON_CREATE warehouse = COMPUTE_WH
 as
WITH policy_summary AS (
    SELECT 
        customer_id,
        COUNT(*) AS total_policies,
        SUM(CASE WHEN status = 'Active' THEN 1 ELSE 0 END) AS active_policies,
        SUM(CASE WHEN status = 'Lapsed' THEN 1 ELSE 0 END) AS lapsed_policies,
        SUM(premium_amount) AS total_premium,
        LISTAGG(DISTINCT policy_type, ', ') AS policy_types
    FROM CUSTOMER_360_DB.RAW.RAW_POLICIES
    GROUP BY customer_id
),
claims_summary AS (
    SELECT 
        customer_id,
        COUNT(*) AS total_claims,
        SUM(CASE WHEN status = 'Settled' THEN 1 ELSE 0 END) AS settled_claims,
        SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END) AS pending_claims,
        SUM(CASE WHEN status = 'Rejected' THEN 1 ELSE 0 END) AS rejected_claims,
        SUM(claim_amount) AS total_claimed,
        SUM(approved_amount) AS total_approved,
        AVG(resolution_days) AS avg_resolution_days,
        AVG(satisfaction_score) AS avg_claim_satisfaction
    FROM CUSTOMER_360_DB.RAW.RAW_CLAIMS
    GROUP BY customer_id
),
transcript_summary AS (
    SELECT 
        customer_id,
        COUNT(*) AS total_calls,
        AVG(
            CASE LOWER(sentiment_score:categories[0]:sentiment::STRING)
                WHEN 'positive' THEN 1.0
                WHEN 'neutral' THEN 0.0
                WHEN 'negative' THEN -1.0
                ELSE 0.0
            END
        ) AS avg_call_sentiment,
        MIN(
            CASE LOWER(sentiment_score:categories[0]:sentiment::STRING)
                WHEN 'positive' THEN 1.0
                WHEN 'neutral' THEN 0.0
                WHEN 'negative' THEN -1.0
                ELSE 0.0
            END
        ) AS worst_call_sentiment,
        MAX(call_date) AS last_call_date,
        ARRAY_AGG(OBJECT_CONSTRUCT(
            'date', call_date::STRING,
            'reason', call_reason,
            'sentiment', sentiment_score:categories[0]:sentiment::STRING,
            'summary', call_summary
        )) AS call_history
    FROM CUSTOMER_360_DB.CURATED.CALL_TRANSCRIPTS_ENRICHED
    GROUP BY customer_id
),
interaction_summary AS (
    SELECT 
        customer_id,
        COUNT(*) AS total_interactions,
        AVG(
            CASE LOWER(sentiment_score:categories[0]:sentiment::STRING)
                WHEN 'positive' THEN 1.0
                WHEN 'neutral' THEN 0.0
                WHEN 'negative' THEN -1.0
                ELSE 0.0
            END
        ) AS avg_interaction_sentiment,
        SUM(CASE WHEN resolved = FALSE THEN 1 ELSE 0 END) AS unresolved_issues,
        LISTAGG(DISTINCT channel, ', ') AS channels_used
    FROM CUSTOMER_360_DB.CURATED.INTERACTIONS_ENRICHED
    GROUP BY customer_id
)
SELECT 
    c.customer_id,
    c.first_name || ' ' || c.last_name AS full_name,
    c.email,
    c.phone,
    c.city,
    c.state,
    c.customer_segment,
    c.tenure_months,
    c.annual_income,
    c.credit_score,
    c.preferred_channel,
    c.is_active,
    
    COALESCE(p.total_policies, 0) AS total_policies,
    COALESCE(p.active_policies, 0) AS active_policies,
    COALESCE(p.lapsed_policies, 0) AS lapsed_policies,
    COALESCE(p.total_premium, 0) AS total_annual_premium,
    p.policy_types,
    
    COALESCE(cl.total_claims, 0) AS total_claims,
    COALESCE(cl.settled_claims, 0) AS settled_claims,
    COALESCE(cl.pending_claims, 0) AS pending_claims,
    COALESCE(cl.rejected_claims, 0) AS rejected_claims,
    COALESCE(cl.total_claimed, 0) AS total_amount_claimed,
    COALESCE(cl.total_approved, 0) AS total_amount_approved,
    cl.avg_resolution_days,
    cl.avg_claim_satisfaction,
    
    COALESCE(t.total_calls, 0) AS total_calls,
    t.avg_call_sentiment,
    t.worst_call_sentiment,
    t.last_call_date,
    COALESCE(i.total_interactions, 0) AS total_interactions,
    i.avg_interaction_sentiment,
    COALESCE(i.unresolved_issues, 0) AS unresolved_issues,
    i.channels_used,
    
    ROUND(COALESCE(
        (COALESCE(t.avg_call_sentiment,0) * COALESCE(t.total_calls,0) + 
         COALESCE(i.avg_interaction_sentiment,0) * COALESCE(i.total_interactions,0)) /
        NULLIF(COALESCE(t.total_calls,0) + COALESCE(i.total_interactions,0), 0)
    , 0), 3) AS overall_sentiment_score,
    
    CASE 
        WHEN p.lapsed_policies > 0 THEN 'High'
        WHEN COALESCE(t.avg_call_sentiment, 0) < -0.5 THEN 'High'
        WHEN COALESCE(i.unresolved_issues, 0) >= 2 THEN 'High'
        WHEN COALESCE(t.avg_call_sentiment, 0) < -0.2 THEN 'Medium'
        WHEN COALESCE(i.unresolved_issues, 0) = 1 THEN 'Medium'
        ELSE 'Low'
    END AS churn_risk,
    
    t.call_history

FROM CUSTOMER_360_DB.RAW.RAW_CUSTOMERS c
LEFT JOIN policy_summary p ON c.customer_id = p.customer_id
LEFT JOIN claims_summary cl ON c.customer_id = cl.customer_id
LEFT JOIN transcript_summary t ON c.customer_id = t.customer_id
LEFT JOIN interaction_summary i ON c.customer_id = i.customer_id;