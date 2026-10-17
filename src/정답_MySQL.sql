-- ════════════════════════════════════════════════════════════════════
--  정답 (MySQL 8 문법)  —  먼저 직접 풀고 나서 보세요
-- ════════════════════════════════════════════════════════════════════
--
--  DuckDB ↔ MySQL 차이 (drill.py는 DuckDB로 돌아갑니다)
--    date_trunc('month', d)        →  DATE_FORMAT(d, '%Y-%m-01')
--    strftime(d, '%Y-%m')          →  DATE_FORMAT(d, '%Y-%m')
--    date_diff('day', a, b)        →  DATEDIFF(b, a)        ← 인자 순서 반대
--    date_diff('month', a, b)      →  TIMESTAMPDIFF(MONTH, a, b)
--    d + INTERVAL 30 DAY           →  DATE_ADD(d, INTERVAL 30 DAY)  (둘 다 가능)
--    median(x)                     →  없음. 직접 구현
--    FILTER (WHERE ...)            →  없음. SUM(CASE WHEN ... END)
--    QUALIFY                       →  없음. 서브쿼리로 한 번 더 감싸기
--
--  테스트돔 주의
--    · 실행해 보고 고칠 수 없습니다. 제출 전에 머리로 검산하세요
--    · 컬럼 별칭과 순서를 문제에 적힌 그대로 쓰세요
--    · ORDER BY를 빼먹으면 틀립니다
-- ════════════════════════════════════════════════════════════════════


-- ── Q1. 월별 신규 가입자와 결제 전환율 ─────────────────────────────────
WITH first_pay AS (
  SELECT user_id, MIN(paid_date) AS fp FROM payments GROUP BY user_id
)
SELECT DATE_FORMAT(u.signup_date, '%Y-%m')                         AS signup_month,
       COUNT(*)                                                     AS signups,
       SUM(CASE WHEN f.fp IS NOT NULL
                 AND f.fp <= DATE_ADD(u.signup_date, INTERVAL 30 DAY)
                THEN 1 ELSE 0 END)                                  AS converted,
       ROUND(100.0 * SUM(CASE WHEN f.fp IS NOT NULL
                 AND f.fp <= DATE_ADD(u.signup_date, INTERVAL 30 DAY)
                THEN 1 ELSE 0 END) / COUNT(*), 2)                   AS conversion_rate
FROM users u
LEFT JOIN first_pay f ON f.user_id = u.user_id
GROUP BY signup_month
ORDER BY signup_month;
-- 함정: INNER JOIN을 쓰면 결제 없는 유저가 분모에서 빠져 전환율이 부풀려집니다.


-- ── Q2. 채널별 퍼널 전환율 ────────────────────────────────────────────
SELECT channel,
       COUNT(DISTINCT CASE WHEN event_name = 'view_landing'  THEN user_id END) AS landing_users,
       COUNT(DISTINCT CASE WHEN event_name = 'signup_done'   THEN user_id END) AS signup_users,
       COUNT(DISTINCT CASE WHEN event_name = 'first_payment' THEN user_id END) AS paid_users,
       ROUND(100.0 * COUNT(DISTINCT CASE WHEN event_name = 'first_payment' THEN user_id END)
             / NULLIF(COUNT(DISTINCT CASE WHEN event_name = 'view_landing' THEN user_id END), 0), 2) AS final_cvr
FROM events
GROUP BY channel
ORDER BY final_cvr DESC;
-- 함정: COUNT(DISTINCT ...)를 안 쓰면 중복 이벤트가 있을 때 틀립니다. NULLIF로 0 나누기 방어.


-- ── Q3. 월별 매출 · 누적 매출 · 전월 대비 증감률 ───────────────────────
WITH m AS (
  SELECT DATE_FORMAT(paid_date, '%Y-%m-01') AS mm, SUM(amount) AS rev
  FROM payments GROUP BY mm
)
SELECT DATE_FORMAT(mm, '%Y-%m')                                     AS month,
       rev                                                           AS revenue,
       SUM(rev) OVER (ORDER BY mm)                                   AS cumulative_revenue,
       ROUND(100.0 * (rev - LAG(rev) OVER (ORDER BY mm))
             / LAG(rev) OVER (ORDER BY mm), 2)                       AS mom_growth
FROM m
ORDER BY mm;
-- 누적합은 ORDER BY만 주면 기본 프레임이 RANGE UNBOUNDED PRECEDING ~ CURRENT ROW 입니다.


-- ── Q4. 가입 코호트별 월간 리텐션 ─────────────────────────────────────
WITH base AS (
  SELECT user_id, DATE_FORMAT(signup_date, '%Y-%m-01') AS cohort FROM users
),
act AS (
  SELECT DISTINCT user_id, DATE_FORMAT(event_date, '%Y-%m-01') AS m
  FROM events WHERE event_name = 'app_open'
)
SELECT DATE_FORMAT(b.cohort, '%Y-%m')          AS cohort_month,
       COUNT(DISTINCT b.user_id)               AS cohort_size,
       ROUND(100.0 * COUNT(DISTINCT CASE WHEN TIMESTAMPDIFF(MONTH, b.cohort, a.m) = 1
             THEN b.user_id END) / COUNT(DISTINCT b.user_id), 1) AS m1_retention,
       ROUND(100.0 * COUNT(DISTINCT CASE WHEN TIMESTAMPDIFF(MONTH, b.cohort, a.m) = 2
             THEN b.user_id END) / COUNT(DISTINCT b.user_id), 1) AS m2_retention,
       ROUND(100.0 * COUNT(DISTINCT CASE WHEN TIMESTAMPDIFF(MONTH, b.cohort, a.m) = 3
             THEN b.user_id END) / COUNT(DISTINCT b.user_id), 1) AS m3_retention
FROM base b
LEFT JOIN act a ON a.user_id = b.user_id
GROUP BY cohort_month
ORDER BY cohort_month;
-- 함정 둘.
--   1) LEFT JOIN이어야 합니다. INNER면 한 번도 활동 안 한 유저가 분모에서 빠집니다.
--   2) 분모는 COUNT(DISTINCT b.user_id). 조인으로 행이 불어나므로 DISTINCT 필수.


-- ── Q5. 월별 매출 분해 (신규/기존/복귀) ───────────────────────────────
WITH mu AS (
  SELECT user_id, DATE_FORMAT(paid_date, '%Y-%m-01') AS m, SUM(amount) AS amt
  FROM payments GROUP BY user_id, m
),
l AS (
  SELECT user_id, m, amt,
         LAG(m) OVER (PARTITION BY user_id ORDER BY m) AS prev_m,
         MIN(m) OVER (PARTITION BY user_id)            AS first_m
  FROM mu
)
SELECT DATE_FORMAT(m, '%Y-%m')                                              AS month,
       SUM(CASE WHEN m = first_m THEN amt ELSE 0 END)                       AS new_revenue,
       SUM(CASE WHEN m <> first_m
                 AND prev_m = DATE_SUB(m, INTERVAL 1 MONTH)
                THEN amt ELSE 0 END)                                        AS existing_revenue,
       SUM(CASE WHEN m <> first_m
                 AND (prev_m IS NULL OR prev_m < DATE_SUB(m, INTERVAL 1 MONTH))
                THEN amt ELSE 0 END)                                        AS returning_revenue,
       SUM(amt)                                                             AS total_revenue
FROM l
GROUP BY month
ORDER BY month;
-- 세 분류가 겹치지도 비지도 않아야 합계와 맞습니다.
-- 첫 결제월(new)을 먼저 떼어내고, 나머지를 '직전달 있음/없음'으로 가르는 순서가 핵심.


-- ── Q6. 채널별 첫 결제까지 걸린 일수의 중앙값 ─────────────────────────
WITH f AS (
  SELECT p.user_id, u.channel,
         DATEDIFF(MIN(p.paid_date), u.signup_date) AS d
  FROM payments p
  JOIN users u ON u.user_id = p.user_id
  GROUP BY p.user_id, u.channel, u.signup_date
),
r AS (
  SELECT channel, d,
         ROW_NUMBER() OVER (PARTITION BY channel ORDER BY d) AS rn,
         COUNT(*)    OVER (PARTITION BY channel)             AS cnt
  FROM f
)
SELECT channel,
       MAX(cnt)          AS payers,
       AVG(d)            AS median_days
FROM r
WHERE rn IN (FLOOR((cnt + 1) / 2), FLOOR((cnt + 2) / 2))   -- 홀수면 1개, 짝수면 2개
GROUP BY channel
ORDER BY median_days, channel;
-- DATEDIFF는 MySQL에서 DATEDIFF(끝, 시작) 순서입니다. DuckDB와 인자 순서가 반대입니다.
-- 짝수 개일 때 가운데 두 값을 AVG로 평균 내는 게 표준 처리입니다.


-- ── Q7. 월별 플랜 업그레이드 / 다운그레이드 ───────────────────────────
WITH l AS (
  SELECT user_id, paid_date, plan,
         LAG(plan) OVER (PARTITION BY user_id ORDER BY paid_date) AS prev_plan
  FROM payments
)
SELECT DATE_FORMAT(paid_date, '%Y-%m')                                      AS month,
       SUM(CASE WHEN prev_plan = 'basic' AND plan = 'pro'   THEN 1 ELSE 0 END) AS upgrades,
       SUM(CASE WHEN prev_plan = 'pro'   AND plan = 'basic' THEN 1 ELSE 0 END) AS downgrades
FROM l
WHERE prev_plan IS NOT NULL
GROUP BY month
HAVING upgrades + downgrades > 0
ORDER BY month;
-- MySQL은 HAVING에서 SELECT 별칭을 쓸 수 있습니다. (표준 SQL은 안 됩니다)


-- ── Q8. 3개월 이상 연속 결제한 유저 수 ────────────────────────────────
WITH mu AS (
  SELECT DISTINCT user_id, DATE_FORMAT(paid_date, '%Y-%m-01') AS m FROM payments
),
g AS (
  SELECT user_id, m,
         TIMESTAMPDIFF(MONTH, '2026-01-01', m)
         - ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY m) AS grp
  FROM mu
),
runs AS (
  SELECT user_id, grp, COUNT(*) AS run_len FROM g GROUP BY user_id, grp
)
SELECT COUNT(DISTINCT user_id) AS users_with_3plus_streak
FROM runs
WHERE run_len >= 3;
-- gaps and islands. 월 일련번호에서 행번호를 빼면 연속 구간마다 같은 값이 나옵니다.
--   2,3,4월 → 1,2,3 - 1,2,3 = 0,0,0  (같은 그룹)
--   2월,  5월 → 1,4 - 1,2 = 0,2        (다른 그룹)


-- ── Q9. 채널별 결제 전환과 LTV ────────────────────────────────────────
WITH pu AS (
  SELECT user_id, SUM(amount) AS amt FROM payments GROUP BY user_id
)
SELECT u.channel,
       COUNT(*)                                        AS total_users,
       COUNT(pu.user_id)                               AS paying_users,
       ROUND(100.0 * COUNT(pu.user_id) / COUNT(*), 2)  AS paying_ratio,
       ROUND(AVG(pu.amt), 2)                           AS ltv
FROM users u
LEFT JOIN pu ON pu.user_id = u.user_id
GROUP BY u.channel
ORDER BY ltv DESC;
-- COUNT(*)는 전체 행, COUNT(컬럼)은 NULL을 빼고 셉니다. 이 차이로 분모 둘을 한 번에 만듭니다.
-- AVG도 NULL을 무시하므로 결제 유저 기준 평균이 자동으로 나옵니다.


-- ── Q10. 채널별 ARPPU와 전월 대비 순위 변동 ───────────────────────────
WITH a AS (
  SELECT DATE_FORMAT(p.paid_date, '%Y-%m-01') AS mm, u.channel,
         ROUND(SUM(p.amount) * 1.0 / COUNT(DISTINCT p.user_id), 2) AS arppu
  FROM payments p
  JOIN users u ON u.user_id = p.user_id
  GROUP BY mm, u.channel
),
r AS (
  SELECT mm, channel, arppu,
         RANK() OVER (PARTITION BY mm ORDER BY arppu DESC) AS rnk
  FROM a
)
SELECT DATE_FORMAT(mm, '%Y-%m')                                   AS month,
       channel,
       arppu,
       rnk,
       LAG(rnk) OVER (PARTITION BY channel ORDER BY mm)           AS prev_rnk,
       LAG(rnk) OVER (PARTITION BY channel ORDER BY mm) - rnk     AS rank_change
FROM r
ORDER BY mm, rnk;
-- 윈도우 함수 결과를 다시 윈도우 함수에 넣으려면 서브쿼리/CTE로 한 단계 감싸야 합니다.
-- 같은 SELECT 안에서 rnk를 바로 LAG에 넣을 수 없습니다.
-- 순위는 월로 파티션, 순위 변동은 채널로 파티션 — 파티션 기준이 서로 다른 게 핵심입니다.


-- ====================================================================
-- Q13 ~ Q17  (추가 출제분 · 새 테이블)
-- ====================================================================

-- ------------------------------------------------------------------
-- Q13. 퍼널 단계별 유저 수와 단계 전환율
-- ------------------------------------------------------------------
SELECT a AS app_open_users, v AS item_view_users, k AS cart_users, p AS purchase_users,
       ROUND(100.0 * v / NULLIF(a, 0), 1) AS view_conversion_rate,
       ROUND(100.0 * k / NULLIF(v, 0), 1) AS cart_conversion_rate,
       ROUND(100.0 * p / NULLIF(k, 0), 1) AS purchase_conversion_rate
FROM (
  SELECT COUNT(DISTINCT CASE WHEN event_name = 'app_open'    THEN user_id END) AS a,
         COUNT(DISTINCT CASE WHEN event_name = 'item_view'   THEN user_id END) AS v,
         COUNT(DISTINCT CASE WHEN event_name = 'add_to_cart' THEN user_id END) AS k,
         COUNT(DISTINCT CASE WHEN event_name = 'purchase'    THEN user_id END) AS p
  FROM user_event_logs
) c;

-- ------------------------------------------------------------------
-- Q14. 코호트별 D7 리텐션율
-- ------------------------------------------------------------------
SELECT f.first_trade_date,
       COUNT(DISTINCT f.user_id) AS cohort_size,
       COUNT(DISTINCT v.user_id) AS d7_active_users,
       ROUND(100.0 * COUNT(DISTINCT v.user_id)
             / NULLIF(COUNT(DISTINCT f.user_id), 0), 1) AS d7_retention_rate
FROM first_trades f
LEFT JOIN daily_app_visits v
       ON v.user_id = f.user_id
      AND v.visit_date = DATE_ADD(f.first_trade_date, INTERVAL 7 DAY)
WHERE f.first_trade_date BETWEEN '2026-02-01' AND '2026-02-07'
GROUP BY f.first_trade_date
ORDER BY f.first_trade_date;

-- ------------------------------------------------------------------
-- Q15. 유저별 최장 연속 거래일수
-- ------------------------------------------------------------------
WITH d AS (
  SELECT DISTINCT user_id, order_date
  FROM stock_orders WHERE status = 'COMPLETED'
),
g AS (
  SELECT user_id, order_date,
         DATEDIFF(order_date, '2026-01-01')
         - ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY order_date) AS grp
  FROM d
),
r AS (
  SELECT user_id, grp, COUNT(*) AS run_len FROM g GROUP BY user_id, grp
)
SELECT user_id, MAX(run_len) AS max_streak_days
FROM r GROUP BY user_id
HAVING MAX(run_len) >= 3
ORDER BY max_streak_days DESC, user_id ASC;

-- ------------------------------------------------------------------
-- Q16. A/B 테스트 그룹 집계 (상위 1% 제외)
-- ------------------------------------------------------------------
WITH j AS (
  SELECT e.user_id, e.group_name,
         COALESCE(s.total_trading_amount, 0) AS amt
  FROM experiment_users e
  LEFT JOIN user_trades_summary s ON s.user_id = e.user_id
),
p AS (
  SELECT group_name, amt,
         PERCENT_RANK() OVER (PARTITION BY group_name ORDER BY amt) AS pr
  FROM j
)
SELECT group_name,
       COUNT(*) AS user_count,
       SUM(amt) AS group_total_amount,
       ROUND(SUM(amt) / COUNT(*), 0) AS arpu
FROM p
WHERE pr <= 0.99
GROUP BY group_name
ORDER BY group_name;

-- ------------------------------------------------------------------
-- Q17. 3일 이상 연속 상승 구간 모두 찾기
-- ------------------------------------------------------------------
WITH p AS (
  SELECT stock_code, trade_date, close_price,
         ROW_NUMBER() OVER (PARTITION BY stock_code ORDER BY trade_date) AS rn,
         LAG(close_price) OVER (PARTITION BY stock_code ORDER BY trade_date) AS prev
  FROM stock_daily_prices
),
u AS (
  SELECT stock_code, trade_date,
         rn - ROW_NUMBER() OVER (PARTITION BY stock_code ORDER BY trade_date) AS grp
  FROM p
  WHERE prev IS NOT NULL AND close_price > prev
)
SELECT stock_code,
       MIN(trade_date) AS streak_start_date,
       MAX(trade_date) AS streak_end_date,
       COUNT(*) AS streak_days
FROM u
GROUP BY stock_code, grp
HAVING COUNT(*) >= 3
ORDER BY stock_code, streak_start_date;

-- ────────────────────────────────────────────────────────────────────
-- Q18. 채널별 ARPU 와 ARPPU
-- ────────────────────────────────────────────────────────────────────
SELECT u.channel,
       COUNT(DISTINCT u.user_id)                                   AS users,
       COUNT(DISTINCT p.user_id)                                   AS payers,
       ROUND(COALESCE(SUM(p.amount), 0) * 1.0
             / NULLIF(COUNT(DISTINCT u.user_id), 0), 2)            AS arpu,
       COALESCE(ROUND(SUM(p.amount) * 1.0
             / NULLIF(COUNT(DISTINCT p.user_id), 0), 2), 0)        AS arppu
FROM users u
LEFT JOIN payments p ON p.user_id = u.user_id
GROUP BY u.channel
ORDER BY arpu DESC, u.channel ASC;
-- 함정: AVG(p.amount) 는 ARPU 도 ARPPU 도 아니다. '결제 건당' 평균이다.
--       ARPU 는 COALESCE 를 SUM 밖에, ARPPU 는 ROUND 밖에 씌운다.

-- ────────────────────────────────────────────────────────────────────
-- Q19. 한 번도 결제하지 않은 유저 수
-- ────────────────────────────────────────────────────────────────────
SELECT u.channel,
       SUM(CASE WHEN p.user_id IS NULL THEN 1 ELSE 0 END)          AS never_paid
FROM users u
LEFT JOIN (SELECT DISTINCT user_id FROM payments WHERE user_id IS NOT NULL) p
       ON p.user_id = u.user_id
GROUP BY u.channel
ORDER BY never_paid DESC, u.channel ASC;
-- 함정: NOT IN (SELECT user_id FROM payments) 는 payments 에 NULL 이 하나라도
--       있으면 0행을 돌려준다. NOT EXISTS 나 LEFT JOIN ... IS NULL 을 써라.

-- ────────────────────────────────────────────────────────────────────
-- Q20. 유저별 결제 요약 (NULL 표시와 정렬 분리)
-- ────────────────────────────────────────────────────────────────────
WITH s AS (
  SELECT u.user_id,
         COALESCE(SUM(p.amount), 0)                                AS total_amount,
         MIN(p.paid_date)                                          AS first_paid,
         MAX(p.paid_date)                                          AS last_paid
  FROM users u
  LEFT JOIN payments p ON p.user_id = u.user_id
  GROUP BY u.user_id
)
SELECT s.user_id, s.total_amount, s.first_paid,
       COALESCE(MAX(lp.plan), '없음')                              AS plan_label
FROM s
LEFT JOIN payments lp
       ON lp.user_id = s.user_id AND lp.paid_date = s.last_paid
GROUP BY s.user_id, s.total_amount, s.first_paid
ORDER BY s.total_amount DESC, s.first_paid ASC, s.user_id ASC
LIMIT 20;
-- 함정: COALESCE(first_paid, '없음') 으로 표시하면 날짜 컬럼이 문자열로 승격돼
--       정렬이 사전순으로 깨진다. 표시와 정렬을 분리해야 한다.
