# -*- coding: utf-8 -*-
"""테스트돔 형식 문제 정의.

실제 테스트돔 SQL 문항의 조건을 그대로 흉내 낸다.
  · 문항마다 제한시간이 있다 (쉬움 3~7분 / 어려움 10~30분)
  · 실행해 보고 고칠 수 없다. 한 번 쓰고 제출한다
  · 자동 채점이므로 컬럼명·컬럼순서·행 정렬이 정확히 맞아야 한다

그래서 drill.py는 기본적으로 '제출 전 미리보기'를 막는다(--peek로 해제).
"""

TASKS = [
    dict(
        id=1, title="월별 신규 가입자와 결제 전환율", level="쉬움", minutes=6,
        prompt="""가입 월별로 아래 세 가지를 구하세요.

  signups          그 달의 신규 가입자 수
  converted        그중 가입 후 30일 이내에 첫 결제를 한 사람 수
  conversion_rate  converted / signups × 100

· 분모는 그 달의 전체 가입자입니다. 결제 이력이 없는 유저도 포함합니다.
· 가입 후 31일째 이후에 첫 결제한 사람은 converted 에서 제외합니다.
· 전환율은 소수점 둘째 자리까지 반올림합니다.
· 월 오름차순으로 정렬하세요.""",
        columns="signup_month, signups, converted, conversion_rate",
        order_note="signup_month ASC",
        ref="""
WITH f AS (SELECT user_id, MIN(paid_date) AS fp FROM payments GROUP BY user_id)
SELECT strftime(u.signup_date,'%Y-%m') AS signup_month,
       COUNT(*) AS signups,
       SUM(CASE WHEN f.fp IS NOT NULL AND f.fp <= u.signup_date + INTERVAL 30 DAY
                THEN 1 ELSE 0 END) AS converted,
       ROUND(100.0*SUM(CASE WHEN f.fp IS NOT NULL AND f.fp <= u.signup_date + INTERVAL 30 DAY
                THEN 1 ELSE 0 END)/COUNT(*), 2) AS conversion_rate
FROM users u LEFT JOIN f ON f.user_id = u.user_id
GROUP BY 1 ORDER BY 1"""),

    dict(
        id=2, title="채널별 퍼널 전환율", level="쉬움", minutes=7,
        prompt="""채널별로 아래 세 단계의 순 유저 수와 최종 전환율(%)을 구하세요.
  view_landing / signup_done / first_payment

· 최종 전환율 = first_payment 유저 수 / view_landing 유저 수 × 100
· 소수점 둘째 자리까지 반올림합니다.
· 최종 전환율 내림차순으로 정렬하세요.""",
        columns="channel, landing_users, signup_users, paid_users, final_cvr",
        order_note="final_cvr DESC",
        ref="""
SELECT channel,
  COUNT(DISTINCT CASE WHEN event_name='view_landing'  THEN user_id END) AS landing_users,
  COUNT(DISTINCT CASE WHEN event_name='signup_done'   THEN user_id END) AS signup_users,
  COUNT(DISTINCT CASE WHEN event_name='first_payment' THEN user_id END) AS paid_users,
  ROUND(100.0*COUNT(DISTINCT CASE WHEN event_name='first_payment' THEN user_id END)
       /NULLIF(COUNT(DISTINCT CASE WHEN event_name='view_landing' THEN user_id END),0),2) AS final_cvr
FROM events GROUP BY channel ORDER BY final_cvr DESC"""),

    dict(
        id=3, title="월별 매출 · 누적 매출 · 전월 대비 증감률", level="보통", minutes=8,
        prompt="""월별 결제 금액 합계와 누적 매출, 전월 대비 증감률(%)을 구하세요.

· 증감률 = (이번달 - 전달) / 전달 × 100, 소수점 둘째 자리 반올림
· 첫 달의 증감률은 NULL 입니다.
· 월 오름차순으로 정렬하세요.""",
        columns="month, revenue, cumulative_revenue, mom_growth",
        order_note="month ASC",
        ref="""
WITH m AS (SELECT date_trunc('month',paid_date) AS mm, SUM(amount) AS rev
           FROM payments GROUP BY 1)
SELECT strftime(mm,'%Y-%m') AS month, rev AS revenue,
       SUM(rev) OVER (ORDER BY mm) AS cumulative_revenue,
       ROUND(100.0*(rev - LAG(rev) OVER (ORDER BY mm))/LAG(rev) OVER (ORDER BY mm),2) AS mom_growth
FROM m ORDER BY mm"""),

    dict(
        id=4, title="가입 코호트별 월간 리텐션", level="어려움", minutes=18,
        prompt="""가입 월을 코호트로 삼아 M+1, M+2, M+3 리텐션(%)을 구하세요.

· 잔존 기준: 해당 월에 app_open 이벤트가 1건 이상 있으면 잔존으로 봅니다.
· 리텐션 = 그 달에 활동한 코호트 인원 / 코호트 전체 인원 × 100
· 소수점 첫째 자리까지 반올림합니다.
· 코호트 오름차순으로 정렬하세요.""",
        columns="cohort_month, cohort_size, m1_retention, m2_retention, m3_retention",
        order_note="cohort_month ASC",
        ref="""
WITH b AS (SELECT user_id, date_trunc('month',signup_date) AS c FROM users),
act AS (SELECT DISTINCT user_id, date_trunc('month',event_date) AS m
        FROM events WHERE event_name='app_open')
SELECT strftime(b.c,'%Y-%m') AS cohort_month,
  COUNT(DISTINCT b.user_id) AS cohort_size,
  ROUND(100.0*COUNT(DISTINCT CASE WHEN date_diff('month',b.c,a.m)=1 THEN b.user_id END)
       /COUNT(DISTINCT b.user_id),1) AS m1_retention,
  ROUND(100.0*COUNT(DISTINCT CASE WHEN date_diff('month',b.c,a.m)=2 THEN b.user_id END)
       /COUNT(DISTINCT b.user_id),1) AS m2_retention,
  ROUND(100.0*COUNT(DISTINCT CASE WHEN date_diff('month',b.c,a.m)=3 THEN b.user_id END)
       /COUNT(DISTINCT b.user_id),1) AS m3_retention
FROM b LEFT JOIN act a ON a.user_id=b.user_id
GROUP BY 1 ORDER BY 1"""),

    dict(
        id=5, title="월별 매출 분해 (신규/기존/복귀)", level="어려움", minutes=25,
        prompt="""월 매출을 세 갈래로 나누세요.

  new       그 유저의 생애 첫 결제가 일어난 달
  existing  직전 달에도 결제한 유저
  returning 과거에 결제한 적은 있으나 직전 달에는 결제가 없던 유저

· 세 항목의 합이 total_revenue와 정확히 같아야 합니다.
· 월 오름차순으로 정렬하세요.""",
        columns="month, new_revenue, existing_revenue, returning_revenue, total_revenue",
        order_note="month ASC",
        ref="""
WITH mu AS (SELECT user_id, date_trunc('month',paid_date) AS m, SUM(amount) AS amt
            FROM payments GROUP BY 1,2),
l AS (SELECT user_id, m, amt,
             LAG(m) OVER (PARTITION BY user_id ORDER BY m) AS pm,
             MIN(m) OVER (PARTITION BY user_id) AS fm FROM mu)
SELECT strftime(m,'%Y-%m') AS month,
  SUM(CASE WHEN m=fm THEN amt ELSE 0 END) AS new_revenue,
  SUM(CASE WHEN m<>fm AND pm = m - INTERVAL 1 MONTH THEN amt ELSE 0 END) AS existing_revenue,
  SUM(CASE WHEN m<>fm AND (pm IS NULL OR pm < m - INTERVAL 1 MONTH) THEN amt ELSE 0 END) AS returning_revenue,
  SUM(amt) AS total_revenue
FROM l GROUP BY 1 ORDER BY 1"""),

    dict(
        id=6, title="채널별 첫 결제까지 걸린 일수의 중앙값", level="어려움", minutes=15,
        prompt="""결제 경험이 있는 유저만 대상으로, 가입일부터 첫 결제일까지 걸린 일수의
채널별 중앙값을 구하세요.

· MySQL 8에는 MEDIAN 함수가 없습니다.
· 대상 인원이 짝수면 가운데 두 값의 평균입니다.
· 중앙값 오름차순, 같으면 channel 오름차순으로 정렬하세요.""",
        columns="channel, payers, median_days",
        order_note="median_days ASC, channel ASC",
        ref="""
WITH f AS (SELECT p.user_id, u.channel,
                  date_diff('day', u.signup_date, MIN(p.paid_date)) AS d
           FROM payments p JOIN users u ON u.user_id=p.user_id
           GROUP BY 1,2, u.signup_date)
SELECT channel, COUNT(*) AS payers,
       CAST(median(d) AS DOUBLE) AS median_days
FROM f GROUP BY channel ORDER BY median_days, channel"""),

    dict(
        id=7, title="월별 플랜 업그레이드 / 다운그레이드", level="보통", minutes=10,
        prompt="""결제 이력에서 직전 결제와 플랜이 달라진 건을 찾아, 월별 업그레이드
(basic→pro)와 다운그레이드(pro→basic) 건수를 구하세요.

· 유저의 첫 결제는 변경이 아니므로 제외합니다.
· 변경이 한 건도 없는 달은 결과에서 제외합니다.
· 월 오름차순으로 정렬하세요.""",
        columns="month, upgrades, downgrades",
        order_note="month ASC",
        ref="""
WITH l AS (SELECT user_id, paid_date, plan,
             LAG(plan) OVER (PARTITION BY user_id ORDER BY paid_date) AS pp
           FROM payments)
SELECT strftime(paid_date,'%Y-%m') AS month,
  SUM(CASE WHEN pp='basic' AND plan='pro' THEN 1 ELSE 0 END) AS upgrades,
  SUM(CASE WHEN pp='pro' AND plan='basic' THEN 1 ELSE 0 END) AS downgrades
FROM l WHERE pp IS NOT NULL
GROUP BY 1
HAVING SUM(CASE WHEN pp<>plan THEN 1 ELSE 0 END) > 0
ORDER BY 1"""),

    dict(
        id=8, title="3개월 이상 연속 결제한 유저 수", level="어려움", minutes=20,
        prompt="""결제한 '월'이 3개월 이상 끊김 없이 이어진 적이 있는 유저가 몇 명인지
구하세요.

· 한 유저가 여러 연속 구간을 가질 수 있으나 유저 수는 중복 없이 셉니다.
· 결과는 한 행입니다.""",
        columns="users_with_3plus_streak",
        order_note="(단일 행)",
        ref="""
WITH mu AS (SELECT DISTINCT user_id, date_trunc('month',paid_date) AS m FROM payments),
g AS (SELECT user_id, m,
        date_diff('month', DATE '2026-01-01', m)
        - ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY m) AS grp
      FROM mu),
r AS (SELECT user_id, grp, COUNT(*) AS run FROM g GROUP BY 1,2)
SELECT COUNT(DISTINCT user_id) AS users_with_3plus_streak
FROM r WHERE run >= 3"""),

    dict(
        id=9, title="채널별 결제 전환과 LTV", level="보통", minutes=9,
        prompt="""채널별로 아래 네 가지를 구하세요.

  total_users   그 채널의 전체 유저 수
  paying_users  그중 결제 이력이 1건 이상 있는 유저 수
  paying_ratio  paying_users / total_users × 100
  ltv           결제 유저 1인당 누적 결제액 평균
                (분모는 전체 유저가 아니라 paying_users 입니다)

· 비중과 LTV는 소수점 둘째 자리까지 반올림합니다.
· LTV 내림차순으로 정렬하세요.""",
        columns="channel, total_users, paying_users, paying_ratio, ltv",
        order_note="ltv DESC",
        ref="""
WITH pu AS (SELECT user_id, SUM(amount) AS amt FROM payments GROUP BY 1)
SELECT u.channel,
       COUNT(*) AS total_users,
       COUNT(pu.user_id) AS paying_users,
       ROUND(100.0*COUNT(pu.user_id)/COUNT(*),2) AS paying_ratio,
       ROUND(AVG(pu.amt),2) AS ltv
FROM users u LEFT JOIN pu ON pu.user_id=u.user_id
GROUP BY u.channel ORDER BY ltv DESC"""),

    dict(
        id=10, title="채널별 ARPPU와 전월 대비 순위 변동", level="어려움", minutes=20,
        prompt="""월별·채널별 ARPPU(결제 유저 1인당 평균 결제액)를 구하고, 각 월 안에서
ARPPU 순위를 매긴 뒤 전월 대비 순위 변동을 구하세요.

· ARPPU = 그 달 결제액 합계 / 그 달 결제한 순 유저 수, 소수점 둘째 자리 반올림
· 순위는 ARPPU 내림차순, 동점이면 같은 순위(RANK)
· rank_change = 전월 순위 - 이번달 순위 (오르면 양수). 첫 달은 NULL
· 월 오름차순, 순위 오름차순으로 정렬하세요.""",
        columns="month, channel, arppu, rnk, prev_rnk, rank_change",
        order_note="month ASC, rnk ASC",
        ref="""
WITH a AS (
  SELECT date_trunc('month',p.paid_date) AS mm, u.channel,
         ROUND(SUM(p.amount)*1.0/COUNT(DISTINCT p.user_id),2) AS arppu
  FROM payments p JOIN users u ON u.user_id=p.user_id
  GROUP BY 1,2),
r AS (SELECT *, RANK() OVER (PARTITION BY mm ORDER BY arppu DESC) AS rnk FROM a)
SELECT strftime(mm,'%Y-%m') AS month, channel, arppu, rnk,
       LAG(rnk) OVER (PARTITION BY channel ORDER BY mm) AS prev_rnk,
       LAG(rnk) OVER (PARTITION BY channel ORDER BY mm) - rnk AS rank_change
FROM r ORDER BY mm, rnk"""),

    dict(
        id=11, title="5일 이동평균 (부분 구간 포함)", level="보통", minutes=8,
        prompt="""종목코드 '005930'의 일별 종가에 대해 5일 이동평균을 구하세요.

· 직전 5거래일이 아직 쌓이지 않은 날은, 그날까지 있는 데이터만으로 평균을 냅니다.
  (1일차는 1개, 2일차는 2개 ... 5일차부터 5개)
· 이동평균은 소수점 둘째 자리까지 반올림합니다.
· 날짜 오름차순으로 정렬하세요.""",
        columns="trade_date, close_price, ma5",
        order_note="trade_date ASC",
        ref="""
SELECT trade_date, close_price,
       ROUND(AVG(close_price) OVER (ORDER BY trade_date
             ROWS BETWEEN 4 PRECEDING AND CURRENT ROW), 2) AS ma5
FROM prices
WHERE stock_code = '005930'
ORDER BY trade_date"""),

    dict(
        id=12, title="종목별 5일·20일 이동평균", level="보통", minutes=10,
        prompt="""모든 종목에 대해 5일 이동평균과 20일 이동평균을 함께 구하세요.

· 각 종목의 이동평균은 그 종목 안에서만 계산합니다.
· 구간이 모자라는 날은 있는 만큼만 평균을 냅니다.
· 소수점 둘째 자리까지 반올림합니다.
· 종목코드 오름차순, 그 안에서 날짜 오름차순으로 정렬하세요.""",
        columns="stock_code, trade_date, close_price, ma5, ma20",
        order_note="stock_code ASC, trade_date ASC",
        ref="""
SELECT stock_code, trade_date, close_price,
       ROUND(AVG(close_price) OVER (PARTITION BY stock_code ORDER BY trade_date
             ROWS BETWEEN 4 PRECEDING AND CURRENT ROW), 2) AS ma5,
       ROUND(AVG(close_price) OVER (PARTITION BY stock_code ORDER BY trade_date
             ROWS BETWEEN 19 PRECEDING AND CURRENT ROW), 2) AS ma20
FROM prices
ORDER BY stock_code, trade_date"""),

    dict(
        id=13, title="골든크로스 발생일 찾기", level="어려움", minutes=18,
        prompt="""종목별로 5일 이동평균이 20일 이동평균을 아래에서 위로 뚫고 올라간 날
(골든크로스)을 모두 찾으세요.

· 골든크로스 = 전일에는 ma5 <= ma20 이었는데 당일 ma5 > ma20 이 된 날
· 이동평균은 구간이 모자라면 있는 만큼만 계산합니다.
· 출력하는 ma5, ma20 은 소수점 둘째 자리까지 반올림합니다.
  (교차 여부 판정은 반올림 전 값으로 합니다)
· 비교할 전일이 없는 첫 거래일은 제외합니다.
· 종목코드 오름차순, 날짜 오름차순으로 정렬하세요.""",
        columns="stock_code, trade_date, ma5, ma20",
        order_note="stock_code ASC, trade_date ASC",
        ref="""
WITH m AS (
  SELECT stock_code, trade_date,
         AVG(close_price) OVER (PARTITION BY stock_code ORDER BY trade_date
               ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) AS ma5,
         AVG(close_price) OVER (PARTITION BY stock_code ORDER BY trade_date
               ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS ma20
  FROM prices),
d AS (
  SELECT *, LAG(ma5) OVER (PARTITION BY stock_code ORDER BY trade_date) AS p5,
            LAG(ma20) OVER (PARTITION BY stock_code ORDER BY trade_date) AS p20
  FROM m)
SELECT stock_code, trade_date, ROUND(ma5,2) AS ma5, ROUND(ma20,2) AS ma20
FROM d
WHERE p5 IS NOT NULL AND p5 <= p20 AND ma5 > ma20
ORDER BY stock_code, trade_date"""),

    dict(
        id=14, title="전 유저 결제 요약 (NULL 처리)", level="보통", minutes=10,
        prompt="""모든 유저에 대해 결제 요약을 만드세요. 결제 이력이 없는 유저도
빠짐없이 포함해야 합니다.

  user_id       유저 ID
  channel       유입 채널
  pay_count     결제 건수 (없으면 0)
  total_amount  결제 금액 합계 (없으면 0)
  last_paid     마지막 결제일 (없으면 NULL 그대로 둘 것)

· total_amount 는 숫자여야 합니다. 문자로 바꾸지 마세요.
· 결제가 있는 유저를 먼저, 없는 유저를 뒤로 보내세요.
· 그 안에서는 total_amount 내림차순, 같으면 user_id 오름차순입니다.
· 상위 20행만 출력하세요.""",
        columns="user_id, channel, pay_count, total_amount, last_paid",
        order_note="결제없음 뒤로, total_amount DESC, user_id ASC / LIMIT 20",
        ref="""
SELECT u.user_id, u.channel,
       COUNT(p.user_id)                AS pay_count,
       COALESCE(SUM(p.amount), 0)      AS total_amount,
       MAX(p.paid_date)                AS last_paid
FROM users u
LEFT JOIN payments p ON p.user_id = u.user_id
GROUP BY u.user_id, u.channel
ORDER BY (MAX(p.paid_date) IS NULL), COALESCE(SUM(p.amount),0) DESC, u.user_id
LIMIT 20"""),

    dict(
        id=15, title="채널별 pro 비중 (0 나누기 방어)", level="보통", minutes=9,
        prompt="""채널별로 결제 유저 가운데 pro 플랜을 쓴 적 있는 유저의 비중을
구하세요.

  channel      채널
  paying_users 그 채널에서 결제 이력이 1건 이상인 유저 수
  pro_users    그중 pro 플랜 결제가 1건 이상인 유저 수
  pro_ratio    pro_users / paying_users × 100 (소수점 둘째 자리 반올림)

· 모든 채널이 결과에 나와야 합니다. 결제 유저가 한 명도 없는 채널도 포함합니다.
· 결제 유저가 0 명인 채널의 pro_ratio 는 NULL 이어야 합니다. 0 이나 에러가 아닙니다.
· pro_ratio 내림차순, 같으면 channel 오름차순으로 정렬하세요.""",
        columns="channel, paying_users, pro_users, pro_ratio",
        order_note="pro_ratio DESC, channel ASC",
        ref="""
SELECT u.channel,
       COUNT(DISTINCT p.user_id) AS paying_users,
       COUNT(DISTINCT CASE WHEN p.plan = 'pro' THEN p.user_id END) AS pro_users,
       ROUND(100.0 * COUNT(DISTINCT CASE WHEN p.plan = 'pro' THEN p.user_id END)
             / NULLIF(COUNT(DISTINCT p.user_id), 0), 2) AS pro_ratio
FROM users u
LEFT JOIN payments p ON p.user_id = u.user_id
GROUP BY u.channel
ORDER BY pro_ratio DESC, u.channel"""),

    # ── Gemini 출제 5문항 (Q16~Q20) ──────────────────────────────────
    # 테이블 이름을 문제에 적힌 그대로 쓴다. 낯선 스키마를 읽는 연습이 필요하다.
    dict(
        id=16, title="퍼널 단계별 유저 수와 단계 전환율", level="쉬움", minutes=8,
        prompt="""user_event_logs 로 아래를 한 행으로 구하세요.

  app_open_users           app_open 을 남긴 순 유저 수
  item_view_users          item_view 를 남긴 순 유저 수
  cart_users               add_to_cart 를 남긴 순 유저 수
  purchase_users           purchase 를 남긴 순 유저 수
  view_conversion_rate     item_view_users / app_open_users x 100
  cart_conversion_rate     cart_users / item_view_users x 100
  purchase_conversion_rate purchase_users / cart_users x 100

· 유저 수는 전부 중복을 지운 수입니다 (한 유저가 같은 행동을 여러 번 남깁니다).
· 단계 순서를 따지지 않습니다. 그 행동을 남겼으면 그 단계에 셉니다.
· 전환율은 소수점 첫째 자리까지 반올림합니다.
· 분모가 0 이면 전환율은 NULL 이어야 합니다.
  MySQL·SQLite 는 0 으로 나누면 그냥 NULL 을 주지만, 다른 DB 는 오류가 납니다.
  NULLIF(분모, 0) 를 쓰는 습관을 들이세요.
· 결과는 한 행입니다.""",
        columns="app_open_users, item_view_users, cart_users, purchase_users, "
                "view_conversion_rate, cart_conversion_rate, purchase_conversion_rate",
        order_note="(한 행)",
        ref="""
WITH c AS (
  SELECT COUNT(DISTINCT CASE WHEN event_name='app_open'    THEN user_id END) AS a,
         COUNT(DISTINCT CASE WHEN event_name='item_view'   THEN user_id END) AS v,
         COUNT(DISTINCT CASE WHEN event_name='add_to_cart' THEN user_id END) AS k,
         COUNT(DISTINCT CASE WHEN event_name='purchase'    THEN user_id END) AS p
  FROM user_event_logs)
SELECT a AS app_open_users, v AS item_view_users, k AS cart_users, p AS purchase_users,
       ROUND(100.0*v/NULLIF(a,0), 1) AS view_conversion_rate,
       ROUND(100.0*k/NULLIF(v,0), 1) AS cart_conversion_rate,
       ROUND(100.0*p/NULLIF(k,0), 1) AS purchase_conversion_rate
FROM c"""),

    dict(
        id=17, title="코호트별 D7 리텐션율", level="보통", minutes=12,
        prompt="""first_trade_date 가 2026-02-01 ~ 2026-02-07 인 유저를 코호트로 봅니다.
첫 거래일자별로 아래를 구하세요.

  cohort_size         그 날 첫 거래한 유저 수
  d7_active_users     그 유저 중 '첫 거래일 + 정확히 7일' 에 앱을 연 유저 수
  d7_retention_rate   d7_active_users / cohort_size x 100

· +7일 '이내' 가 아니라 '정확히 그 날' 입니다.
· daily_app_visits 는 같은 유저가 같은 날 여러 행을 남길 수 있습니다.
· 재방문자가 0 명인 날도 0 으로 한 행 나와야 합니다.
· 리텐션율은 소수점 첫째 자리까지 반올림합니다.
· first_trade_date 오름차순으로 정렬하세요.""",
        columns="first_trade_date, cohort_size, d7_active_users, d7_retention_rate",
        order_note="first_trade_date ASC",
        ref="""
SELECT f.first_trade_date,
       COUNT(DISTINCT f.user_id) AS cohort_size,
       COUNT(DISTINCT v.user_id) AS d7_active_users,
       ROUND(100.0*COUNT(DISTINCT v.user_id)/NULLIF(COUNT(DISTINCT f.user_id),0), 1)
         AS d7_retention_rate
FROM first_trades f
LEFT JOIN daily_app_visits v
       ON v.user_id = f.user_id
      AND v.visit_date = f.first_trade_date + INTERVAL 7 DAY
WHERE f.first_trade_date BETWEEN DATE '2026-02-01' AND DATE '2026-02-07'
GROUP BY f.first_trade_date
ORDER BY f.first_trade_date"""),

    dict(
        id=18, title="유저별 최장 연속 거래일수", level="어려움", minutes=18,
        prompt="""stock_orders 에서 유저별 '가장 길게 연속으로 거래한 일수' 를 구하고,
그 값이 3 이상인 유저만 뽑으세요.

  user_id
  max_streak_days   최장 연속 거래일수

· status = 'COMPLETED' 인 주문만 셉니다.
· 하루에 여러 번 거래했어도 그 날은 1일입니다.
· 그 날 주문이 전부 CANCELLED 면 거래하지 않은 날입니다 (연속이 끊깁니다).
· 날짜가 하루씩 이어진 구간만 연속입니다. 주말·공휴일은 따지지 않습니다.
· max_streak_days 내림차순, 같으면 user_id 오름차순으로 정렬하세요.""",
        columns="user_id, max_streak_days",
        order_note="max_streak_days DESC, user_id ASC",
        ref="""
WITH d AS (SELECT DISTINCT user_id, order_date
           FROM stock_orders WHERE status='COMPLETED'),
g AS (SELECT user_id, order_date,
             date_diff('day', DATE '2026-01-01', order_date)
             - ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY order_date) AS grp
      FROM d),
r AS (SELECT user_id, grp, COUNT(*) AS run FROM g GROUP BY 1,2)
SELECT user_id, MAX(run) AS max_streak_days
FROM r GROUP BY user_id
HAVING MAX(run) >= 3
ORDER BY max_streak_days DESC, user_id ASC"""),

    dict(
        id=19, title="A/B 테스트 그룹 집계 (상위 1% 제외)", level="보통", minutes=14,
        prompt="""experiment_users 의 모든 참가자를 대상으로 그룹별 지표를 구하세요.

  group_name
  user_count          이상치를 뺀 유저 수
  group_total_amount  이상치를 뺀 총 거래 금액 합계
  arpu                group_total_amount / user_count, 소수점 없이 반올림

· user_trades_summary 에 행이 없는 참가자는 거래 금액 0 으로 봅니다.
· 이상치 판정은 '거래 금액 0 처리까지 끝낸 뒤' 그룹별로 합니다.
  PERCENT_RANK() OVER (PARTITION BY group_name ORDER BY 금액) > 0.99 인 유저를 뺍니다.
· group_name 오름차순으로 정렬하세요.""",
        columns="group_name, user_count, group_total_amount, arpu",
        order_note="group_name ASC",
        ref="""
WITH j AS (
  SELECT e.user_id, e.group_name,
         COALESCE(s.total_trading_amount, 0) AS amt
  FROM experiment_users e
  LEFT JOIN user_trades_summary s ON s.user_id = e.user_id),
p AS (
  SELECT group_name, amt,
         PERCENT_RANK() OVER (PARTITION BY group_name ORDER BY amt) AS pr
  FROM j)
SELECT group_name,
       COUNT(*) AS user_count,
       SUM(amt) AS group_total_amount,
       ROUND(SUM(amt)/COUNT(*), 0) AS arpu
FROM p WHERE pr <= 0.99
GROUP BY group_name ORDER BY group_name"""),

    dict(
        id=20, title="3일 이상 연속 상승 구간 모두 찾기", level="어려움", minutes=22,
        prompt="""stock_daily_prices 에서 종목별로 '3일 이상 연속 상승한 구간' 을
모두 찾으세요.

  stock_code
  streak_start_date  그 구간의 첫 상승일
  streak_end_date    그 구간의 마지막 상승일
  streak_days        그 구간의 연속 상승 일수

· 상승일 = 전 거래일 종가보다 당일 종가가 '더 높은' 날 (같으면 상승이 아닙니다).
· 전 거래일은 하루 전이 아니라 그 종목의 데이터상 바로 앞 행입니다.
· streak_days 는 상승일의 개수입니다. 상승이 시작되기 전 날은 세지 않습니다.
· 구간이 3일 미만이면 출력하지 않습니다.
· stock_code 오름차순, 같으면 streak_start_date 오름차순으로 정렬하세요.""",
        columns="stock_code, streak_start_date, streak_end_date, streak_days",
        order_note="stock_code ASC, streak_start_date ASC",
        ref="""
WITH p AS (
  SELECT stock_code, trade_date,
         ROW_NUMBER() OVER (PARTITION BY stock_code ORDER BY trade_date) AS rn,
         LAG(close_price) OVER (PARTITION BY stock_code ORDER BY trade_date) AS prev,
         close_price
  FROM stock_daily_prices),
u AS (
  SELECT stock_code, trade_date, rn,
         rn - ROW_NUMBER() OVER (PARTITION BY stock_code ORDER BY trade_date) AS grp
  FROM p WHERE prev IS NOT NULL AND close_price > prev)
SELECT stock_code,
       MIN(trade_date) AS streak_start_date,
       MAX(trade_date) AS streak_end_date,
       COUNT(*) AS streak_days
FROM u GROUP BY stock_code, grp
HAVING COUNT(*) >= 3
ORDER BY stock_code, streak_start_date"""),

    # ── NULL·COALESCE 집중 문항 (Q21~Q23) ───────────────────────────
    # 토스 쿼리 테스트에 '데이터 타입과 NULL' 유형이 실제로 나왔다.
    dict(
        id=21, title="채널별 ARPU 와 ARPPU", level="보통", minutes=11,
        prompt="""채널별로 아래 네 가지를 구하세요.

  users   그 채널의 전체 가입자 수
  payers  그중 결제를 한 번이라도 한 유저 수
  arpu    결제액 합계 / 전체 가입자 수   (결제 안 한 유저도 분모에 넣습니다)
  arppu   결제액 합계 / 결제한 유저 수   (결제한 유저만 분모에 넣습니다)

· 결제가 한 건도 없는 채널은 arpu, arppu 를 모두 0 으로 출력하세요.
· arpu, arppu 는 소수점 둘째 자리까지 반올림합니다.
· arpu 내림차순, 같으면 channel 오름차순으로 정렬하세요.""",
        columns="channel, users, payers, arpu, arppu",
        order_note="arpu DESC, channel ASC",
        ref="""
SELECT u.channel,
       COUNT(DISTINCT u.user_id) AS users,
       COUNT(DISTINCT p.user_id) AS payers,
       ROUND(COALESCE(SUM(p.amount), 0) * 1.0
             / NULLIF(COUNT(DISTINCT u.user_id), 0), 2) AS arpu,
       COALESCE(ROUND(SUM(p.amount) * 1.0
             / NULLIF(COUNT(DISTINCT p.user_id), 0), 2), 0) AS arppu
FROM users u
LEFT JOIN payments p ON p.user_id = u.user_id
GROUP BY u.channel
ORDER BY arpu DESC, u.channel ASC"""),

    dict(
        id=22, title="한 번도 결제하지 않은 유저 수", level="쉬움", minutes=7,
        prompt="""채널별로 '결제 이력이 한 건도 없는 유저 수' 를 구하세요.

  channel
  never_paid   그 채널에서 결제 이력이 없는 유저 수

· payments 테이블에는 user_id 가 비어 있는(NULL) 행이 섞여 있을 수 있습니다.
  그 행은 '누구의 결제인지 알 수 없는 행' 이므로 결제 이력으로 치지 않습니다.
· 결제 이력이 없는 유저가 0 명인 채널도 0 으로 한 행 나와야 합니다.
· never_paid 내림차순, 같으면 channel 오름차순으로 정렬하세요.""",
        columns="channel, never_paid",
        order_note="never_paid DESC, channel ASC",
        ref="""
SELECT u.channel,
       SUM(CASE WHEN p.user_id IS NULL THEN 1 ELSE 0 END) AS never_paid
FROM users u
LEFT JOIN (SELECT DISTINCT user_id FROM payments WHERE user_id IS NOT NULL) p
       ON p.user_id = u.user_id
GROUP BY u.channel
ORDER BY never_paid DESC, u.channel ASC"""),

    dict(
        id=23, title="유저별 결제 요약 (NULL 표시와 정렬 분리)", level="보통", minutes=12,
        prompt="""유저별 결제 요약을 상위 20명만 출력하세요.

  user_id
  total_amount   결제액 합계. 결제 이력이 없으면 0
  first_paid     첫 결제일. 결제 이력이 없으면 NULL 그대로 둡니다
  plan_label     마지막 결제 plan. 결제 이력이 없으면 문자열 '없음'

· total_amount 내림차순 → first_paid 오름차순 → user_id 오름차순으로 정렬합니다.
· first_paid 오름차순에서 NULL 은 '가장 작은 값' 으로 봅니다 (앞에 옵니다).
  MySQL·SQLite 의 기본 동작입니다.
· 정렬한 뒤 상위 20행만 남기세요.""",
        columns="user_id, total_amount, first_paid, plan_label",
        order_note="total_amount DESC, first_paid ASC(NULL 먼저), user_id ASC / LIMIT 20",
        ref="""
WITH s AS (
  SELECT u.user_id,
         COALESCE(SUM(p.amount), 0) AS total_amount,
         MIN(p.paid_date) AS first_paid,
         MAX(p.paid_date) AS last_paid
  FROM users u
  LEFT JOIN payments p ON p.user_id = u.user_id
  GROUP BY u.user_id)
SELECT s.user_id, s.total_amount, s.first_paid,
       COALESCE(MAX(lp.plan), '없음') AS plan_label
FROM s
LEFT JOIN payments lp
       ON lp.user_id = s.user_id AND lp.paid_date = s.last_paid
GROUP BY s.user_id, s.total_amount, s.first_paid
ORDER BY s.total_amount DESC, s.first_paid ASC, s.user_id ASC
LIMIT 20"""),
]
