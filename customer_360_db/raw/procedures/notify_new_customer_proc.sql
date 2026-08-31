CREATE OR REPLACE PROCEDURE CUSTOMER_360_DB.RAW.NOTIFY_NEW_CUSTOMER_PROC()
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS CALLER
AS 'BEGIN
  -- Consume stream into a temp table
  CREATE OR REPLACE TEMPORARY TABLE CUSTOMER_360_DB.RAW.TMP_NEW_CUSTOMERS AS
    SELECT CUSTOMER_ID
    FROM CUSTOMER_360_DB.RAW.LOAD_COMPLETE_STREAM
    WHERE METADATA$ACTION = ''INSERT'';

  -- Refresh the dynamic table
  ALTER DYNAMIC TABLE CUSTOMER_360_DB.ANALYTICS.NEXT_BEST_ACTION REFRESH;

  -- Send one email per new customer
  LET c1 CURSOR FOR
    SELECT n.FULL_NAME, n.RECOMMENDED_ACTION, n.OVERALL_SENTIMENT_SCORE, n.CHURN_RISK
    FROM CUSTOMER_360_DB.RAW.TMP_NEW_CUSTOMERS t
    JOIN CUSTOMER_360_DB.ANALYTICS.NEXT_BEST_ACTION n
      ON n.CUSTOMER_ID = t.CUSTOMER_ID;

  LET email_count INTEGER := 0;

  FOR rec IN c1 DO
    LET subj VARCHAR := ''Next Best Action for '' || rec.FULL_NAME;
    LET body VARCHAR := ''Customer: '' || rec.FULL_NAME || ''\\n\\n'' ||
      ''Sentiment Score: '' || rec.OVERALL_SENTIMENT_SCORE::STRING || ''\\n\\n'' ||
      ''Churn Risk: '' || rec.CHURN_RISK || ''\\n\\n'' ||
      ''Recommended Action: '' || rec.RECOMMENDED_ACTION;
    CALL SYSTEM$SEND_EMAIL(''NBA_EMAIL_INT'', ''adil.khan@merkle.com'', :subj, :body);
    email_count := email_count + 1;
  END FOR;

  RETURN ''Emails sent: '' || :email_count::STRING;
END';