# -*- coding: utf-8 -*-
"""문항별 해설 본문.

앱의 /guide 에서 렌더링된다. 내용은 여기 한 곳에서만 관리한다.
"""

# 문제 표현 → 기법 매핑. 해설보다 이걸 먼저 외우는 게 실전에 쓸모 있다.
PATTERNS = [
    ("“직전 / 이전 / 전월 / 전일”", "LAG()",
     "날짜 뺄셈으로 직전 행을 찾지 말 것. 주말·결측에서 깨진다"),
    ("“최근 N개 / N일 이동평균”", "ROWS BETWEEN (N-1) PRECEDING AND CURRENT ROW",
     "RANGE 아님. 날짜 조인 아님. 당일 포함이라 N-1"),
    ("“누적 / 러닝토탈”", "SUM(x) OVER (ORDER BY ...)",
     "ORDER BY 만 붙이면 자동으로 누적"),
    ("“전체 대비 비중”", "SUM(x) OVER ()",
     "괄호를 비우면 전체 합"),
    ("“그룹별 1등 / 최신 1건”", "ROW_NUMBER() = 1 을 서브쿼리 밖에서",
     "WHERE 에서 윈도우 함수 못 씀"),
    ("“공동 순위 / 동점”", "RANK (건너뜀) vs DENSE_RANK (안 건너뜀)",
     "1등만 한 명이면 ROW_NUMBER"),
    ("“연속 N개월 / 끊기지 않고”", "gaps and islands : 일련번호 − ROW_NUMBER()",
     "같은 값이 나오는 구간이 연속 구간"),
    ("“코호트 / 가입 후 N개월”", "TIMESTAMPDIFF(MONTH, 코호트월, 활동월)",
     "분모는 코호트 전체. LEFT JOIN 필수"),
    ("“신규 / 기존 / 복귀”", "MIN() OVER 로 첫 달, LAG 로 직전 달",
     "세 분류가 겹치지도 비지도 않게"),
    ("“중앙값”", "ROW_NUMBER + COUNT, 짝수면 가운데 둘 평균",
     "MySQL 에 MEDIAN 없음"),
    ("“퍼널 / 단계별 전환”", "COUNT(DISTINCT CASE WHEN step THEN user END)",
     "가로로 펼치는 조건부 집계"),
    ("“~가 없는 것도 포함”", "LEFT JOIN + COALESCE",
     "INNER 쓰면 분모가 깎인다"),
    ("“비율 / 전환율 / 퍼센트”", "ROUND(100.0 * A / NULLIF(B,0), 2)",
     "×100, 소수, 0 방어 — 셋 다"),
]

CHECKS = [
    "출력 컬럼 이름과 순서가 문제와 똑같은가",
    "ORDER BY 를 넣었는가 (빠지면 로직이 맞아도 0점)",
    "ROUND 자릿수가 문제와 같은가",
    "LEFT JOIN 인가 INNER 인가 — 빠지는 행이 없는가",
    "나눗셈에 100.0 또는 1.0 을 섞었는가",
    "분모가 0 이 될 수 있으면 NULLIF 를 썼는가",
    "조인으로 행이 불어나 COUNT 가 부풀지 않는가 (DISTINCT)",
    "빈 그룹·NULL·동점에서도 답이 맞는가",
]

GUIDE = [
 dict(id=1, title="월별 신규 가입자와 결제 전환율", level="쉬움",
   asks="‘전체’가 분모인 비율을 구할 줄 아는가. 그리고 조건부 집계.",
   steps=[
     "유저별 <b>첫</b> 결제일을 먼저 만든다 (MIN). payments 를 바로 조인하면 한 유저가 여러 행이 된다.",
     "users 를 기준으로 <b>LEFT JOIN</b>. 결제 없는 유저가 분모에 남아야 한다.",
     "converted 는 조건부 집계로 센다.",
     "비율은 converted / signups × 100.",
   ],
   sql="""WITH first_pay AS (
  SELECT user_id, MIN(paid_date) AS fp FROM payments GROUP BY user_id
)
SELECT DATE_FORMAT(u.signup_date, '%Y-%m') AS signup_month,
       COUNT(*) AS signups,
       SUM(CASE WHEN f.fp <= DATE_ADD(u.signup_date, INTERVAL 30 DAY)
                THEN 1 ELSE 0 END) AS converted,
       ROUND(100.0 * SUM(CASE WHEN f.fp <= DATE_ADD(u.signup_date, INTERVAL 30 DAY)
                THEN 1 ELSE 0 END) / COUNT(*), 2) AS conversion_rate
FROM users u
LEFT JOIN first_pay f ON f.user_id = u.user_id
GROUP BY signup_month
ORDER BY signup_month;""",
   traps=[
     "<b>INNER JOIN</b> 을 쓰면 결제 없는 유저가 사라져 전환율이 부풀려진다. 이 문제의 핵심 함정.",
     "분자를 <b>전체 결제자</b>로 쓰기 쉽다. 30일 조건이 붙은 쪽이어야 한다.",
     "<code>×100</code> 누락. <code>*1.0</code> 만으로는 비율(0.23)이지 퍼센트가 아니다.",
     "<code>f.fp IS NOT NULL</code> 은 안 써도 된다. NULL 과의 비교는 NULL 이라 CASE 가 거짓으로 떨어진다.",
   ],
   variants="“가입 후 7일 이내 재방문율”, “첫 구매까지 N일 이내 비율” — 날짜 기준만 바뀐다."),

 dict(id=2, title="채널별 퍼널 전환율", level="쉬움",
   asks="세로로 쌓인 이벤트를 가로 단계로 펼칠 줄 아는가.",
   steps=[
     "단계별로 <code>COUNT(DISTINCT CASE WHEN ... THEN user_id END)</code>.",
     "같은 유저가 같은 이벤트를 여러 번 남길 수 있으므로 DISTINCT 필수.",
     "최종 전환율은 마지막 단계 ÷ 첫 단계.",
   ],
   sql="""SELECT channel,
       COUNT(DISTINCT CASE WHEN event_name='view_landing'  THEN user_id END) AS landing_users,
       COUNT(DISTINCT CASE WHEN event_name='signup_done'   THEN user_id END) AS signup_users,
       COUNT(DISTINCT CASE WHEN event_name='first_payment' THEN user_id END) AS paid_users,
       ROUND(100.0 * COUNT(DISTINCT CASE WHEN event_name='first_payment' THEN user_id END)
             / NULLIF(COUNT(DISTINCT CASE WHEN event_name='view_landing' THEN user_id END), 0), 2)
         AS final_cvr
FROM events
GROUP BY channel
ORDER BY final_cvr DESC;""",
   traps=[
     "<b>DISTINCT 누락</b> — 중복 이벤트가 있으면 단계 인원이 부풀려진다.",
     "<code>COUNT(CASE WHEN ...)</code> 는 <b>0 이 아니라 NULL 을 세지 않는 것</b>이다. ELSE 를 쓰지 말 것. <code>ELSE 0</code> 을 넣으면 전부 세어진다.",
     "첫 단계가 0 인 채널이 있으면 0 나누기. NULLIF 로 막는다.",
   ],
   variants="“단계 간 전환율”(2→3, 3→4)로 바뀌면 분모를 직전 단계로 바꾸면 된다."),

 dict(id=3, title="월별 매출 · 누적 · 전월 대비", level="보통",
   asks="윈도우 함수 기본기. 누적과 LAG.",
   steps=[
     "월 단위로 먼저 집계해 한 달 = 한 행으로 만든다.",
     "그 위에서 <code>SUM() OVER (ORDER BY)</code> 로 누적.",
     "<code>LAG()</code> 로 전월 값을 끌어와 증감률.",
   ],
   sql="""WITH m AS (
  SELECT DATE_FORMAT(paid_date, '%Y-%m-01') AS mm, SUM(amount) AS rev
  FROM payments GROUP BY mm
)
SELECT DATE_FORMAT(mm, '%Y-%m') AS month,
       rev AS revenue,
       SUM(rev) OVER (ORDER BY mm) AS cumulative_revenue,
       ROUND(100.0 * (rev - LAG(rev) OVER (ORDER BY mm))
             / LAG(rev) OVER (ORDER BY mm), 2) AS mom_growth
FROM m
ORDER BY mm;""",
   traps=[
     "집계 전에 윈도우를 쓰려 하면 안 된다. <b>GROUP BY 로 월별 한 행을 먼저</b> 만들고 그 위에서 윈도우.",
     "정렬용으로 <code>'%Y-%m-01'</code>(월 첫날)을 쓰고 출력은 <code>'%Y-%m'</code>. 문자열 <code>'2026-1'</code> 로 정렬하면 10월이 1월 뒤에 온다.",
     "첫 달 증감률은 NULL 이 맞다. 0 으로 채우지 말 것.",
     "MySQL 은 <code>LAG(rev)</code> 를 별칭으로 재사용할 수 없다. 두 번 풀어 쓴다.",
   ],
   variants="“전년 동월 대비”면 <code>LAG(rev, 12)</code>."),

 dict(id=4, title="가입 코호트별 월간 리텐션", level="어려움",
   asks="코호트 분석의 뼈대. 분모 고정 + 경과 개월.",
   steps=[
     "코호트 = 가입 월. 유저마다 하나.",
     "활동 = app_open 이 있는 월. 유저×월 중복 제거.",
     "<code>TIMESTAMPDIFF(MONTH, 코호트, 활동월)</code> 로 경과 개월 M+1, M+2…",
     "분모는 <b>코호트 전체 인원</b>. 활동 안 한 사람도 포함.",
   ],
   sql="""WITH base AS (
  SELECT user_id, DATE_FORMAT(signup_date, '%Y-%m-01') AS cohort FROM users
),
act AS (
  SELECT DISTINCT user_id, DATE_FORMAT(event_date, '%Y-%m-01') AS m
  FROM events WHERE event_name = 'app_open'
)
SELECT DATE_FORMAT(b.cohort, '%Y-%m') AS cohort_month,
       COUNT(DISTINCT b.user_id) AS cohort_size,
       ROUND(100.0 * COUNT(DISTINCT CASE WHEN TIMESTAMPDIFF(MONTH, b.cohort, a.m)=1
             THEN b.user_id END) / COUNT(DISTINCT b.user_id), 1) AS m1_retention,
       ROUND(100.0 * COUNT(DISTINCT CASE WHEN TIMESTAMPDIFF(MONTH, b.cohort, a.m)=2
             THEN b.user_id END) / COUNT(DISTINCT b.user_id), 1) AS m2_retention,
       ROUND(100.0 * COUNT(DISTINCT CASE WHEN TIMESTAMPDIFF(MONTH, b.cohort, a.m)=3
             THEN b.user_id END) / COUNT(DISTINCT b.user_id), 1) AS m3_retention
FROM base b
LEFT JOIN act a ON a.user_id = b.user_id
GROUP BY cohort_month
ORDER BY cohort_month;""",
   traps=[
     "<b>INNER JOIN 금지.</b> 한 번도 활동 안 한 유저가 분모에서 빠지면 리텐션이 과대평가된다.",
     "분모를 <code>COUNT(*)</code> 로 쓰면 안 된다. 조인으로 행이 불어나 있다. <code>COUNT(DISTINCT user_id)</code>.",
     "활동 테이블에서 유저×월 <b>중복 제거를 먼저</b> 해야 한다. 안 하면 한 유저가 여러 번 세어질 수 있다 — DISTINCT 를 써서 막는다.",
     "아직 기간이 안 지난 코호트는 0 이 나온다. 정상이다.",
   ],
   variants="주 단위면 <code>TIMESTAMPDIFF(WEEK, ...)</code>. “결제 리텐션”이면 활동 테이블을 payments 로 바꾼다."),

 dict(id=5, title="월별 매출 분해 (신규/기존/복귀)", level="어려움",
   asks="FP&A 의 핵심. 배타적 분류를 만들 줄 아는가.",
   steps=[
     "<b>유저 × 월</b> 단위로 먼저 집계한다. 이걸 안 하면 아래가 전부 꼬인다.",
     "<code>MIN(m) OVER (PARTITION BY user_id)</code> → 그 유저의 첫 결제 월.",
     "<code>LAG(m) OVER (PARTITION BY user_id ORDER BY m)</code> → 직전 결제 월.",
     "첫 달이면 신규. 아니면 직전 달이 바로 전월인지로 기존/복귀를 가른다.",
   ],
   sql="""WITH mu AS (
  SELECT user_id, DATE_FORMAT(paid_date, '%Y-%m-01') AS m, SUM(amount) AS amt
  FROM payments GROUP BY user_id, m
),
l AS (
  SELECT user_id, m, amt,
         LAG(m) OVER (PARTITION BY user_id ORDER BY m) AS prev_m,
         MIN(m) OVER (PARTITION BY user_id)            AS first_m
  FROM mu
)
SELECT DATE_FORMAT(m, '%Y-%m') AS month,
       SUM(CASE WHEN m = first_m THEN amt ELSE 0 END) AS new_revenue,
       SUM(CASE WHEN m <> first_m AND prev_m = DATE_SUB(m, INTERVAL 1 MONTH)
                THEN amt ELSE 0 END) AS existing_revenue,
       SUM(CASE WHEN m <> first_m AND (prev_m IS NULL OR prev_m < DATE_SUB(m, INTERVAL 1 MONTH))
                THEN amt ELSE 0 END) AS returning_revenue,
       SUM(amt) AS total_revenue
FROM l
GROUP BY month
ORDER BY month;""",
   traps=[
     "<b>분류 순서가 핵심.</b> 첫 달(new)을 먼저 떼어내고, 나머지를 ‘직전 달 있음/없음’으로 가른다. 순서를 바꾸면 겹치거나 빈다.",
     "세 항목 합 = total 인지 <b>반드시 검산</b>한다. 틀리면 분류가 겹치거나 빈 것이다.",
     "유저×월 집계를 건너뛰고 payments 에 바로 LAG 를 걸면, 같은 달 두 번 결제한 유저에서 깨진다.",
     "날짜 문자열끼리 비교하므로 <code>'%Y-%m-01'</code> 형식을 일관되게 쓴다.",
   ],
   variants="이탈(churn) 매출까지 요구하면, 직전 달에는 있었는데 이번 달에 없는 유저를 따로 만들어 음수로 붙인다."),

 dict(id=6, title="채널별 첫 결제까지 일수의 중앙값", level="어려움",
   asks="MySQL 에 MEDIAN 이 없을 때 직접 만들 줄 아는가.",
   steps=[
     "유저별 첫 결제일 → 가입일과의 차이(일수).",
     "채널 안에서 일수 오름차순으로 <code>ROW_NUMBER()</code>, 동시에 <code>COUNT() OVER</code> 로 인원수.",
     "가운데 위치만 남긴다. 홀수면 1개, 짝수면 2개.",
     "남은 값을 AVG 하면 짝수 평균까지 한 번에 처리된다.",
   ],
   sql="""WITH f AS (
  SELECT p.user_id, u.channel,
         DATEDIFF(MIN(p.paid_date), u.signup_date) AS d
  FROM payments p JOIN users u ON u.user_id = p.user_id
  GROUP BY p.user_id, u.channel, u.signup_date
),
r AS (
  SELECT channel, d,
         ROW_NUMBER() OVER (PARTITION BY channel ORDER BY d) AS rn,
         COUNT(*)     OVER (PARTITION BY channel)            AS cnt
  FROM f
)
SELECT channel, MAX(cnt) AS payers, AVG(d) AS median_days
FROM r
WHERE rn IN (FLOOR((cnt + 1) / 2), FLOOR((cnt + 2) / 2))
GROUP BY channel
ORDER BY median_days, channel;""",
   traps=[
     "<code>DATEDIFF(끝, 시작)</code> — MySQL 은 인자 순서가 <b>끝이 먼저</b>다. TIMESTAMPDIFF 와 반대라 헷갈린다.",
     "짝수 처리를 빼먹으면 값이 한쪽으로 치우친다. <code>FLOOR((cnt+1)/2)</code> 와 <code>FLOOR((cnt+2)/2)</code> 두 자리를 잡는 게 정석.",
     "홀수면 두 식이 같은 값이 되어 자동으로 1개만 남는다. 분기할 필요 없다.",
     "payers 는 <code>COUNT(*)</code> 가 아니라 <code>MAX(cnt)</code>. WHERE 로 이미 2행만 남았기 때문.",
   ],
   variants="“상위 25% 지점”이면 <code>PERCENT_RANK() <= 0.25</code> 또는 <code>NTILE(4)=1</code>."),

 dict(id=7, title="월별 플랜 업그레이드 / 다운그레이드", level="보통",
   asks="직전 행과 비교할 줄 아는가.",
   steps=[
     "유저별 결제 순서로 <code>LAG(plan)</code>.",
     "직전 플랜과 현재 플랜을 비교해 방향을 판정.",
     "첫 결제는 직전이 NULL 이므로 제외.",
   ],
   sql="""WITH l AS (
  SELECT user_id, paid_date, plan,
         LAG(plan) OVER (PARTITION BY user_id ORDER BY paid_date) AS prev_plan
  FROM payments
)
SELECT DATE_FORMAT(paid_date, '%Y-%m') AS month,
       SUM(CASE WHEN prev_plan='basic' AND plan='pro'   THEN 1 ELSE 0 END) AS upgrades,
       SUM(CASE WHEN prev_plan='pro'   AND plan='basic' THEN 1 ELSE 0 END) AS downgrades
FROM l
WHERE prev_plan IS NOT NULL
GROUP BY month
HAVING upgrades + downgrades > 0
ORDER BY month;""",
   traps=[
     "<code>PARTITION BY user_id</code> 누락 — 다른 유저의 플랜과 비교하게 된다.",
     "첫 결제를 변경으로 세지 않도록 <code>prev_plan IS NOT NULL</code>.",
     "MySQL 은 <b>HAVING 에서 SELECT 별칭을 쓸 수 있다</b>. 표준 SQL 은 안 된다.",
   ],
   variants="“상태가 바뀐 시점”, “가격이 인상된 건” 전부 같은 구조."),

 dict(id=8, title="3개월 이상 연속 결제한 유저", level="어려움",
   asks="gaps and islands. 알면 1분, 모르면 못 푼다.",
   steps=[
     "유저별 결제한 <b>월</b> 목록을 중복 없이 만든다.",
     "월을 일련번호로 바꾼다 (기준월로부터 몇 개월째인가).",
     "<code>일련번호 − ROW_NUMBER()</code> → 연속 구간마다 같은 값이 나온다.",
     "그 값으로 묶어 개수를 세고 3 이상만 남긴다.",
   ],
   sql="""WITH mu AS (
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
FROM runs WHERE run_len >= 3;""",
   traps=[
     "<b>왜 되는지</b>를 알아야 응용된다. 연속이면 일련번호와 행번호가 같은 보폭으로 증가해 차이가 고정된다. 끊기면 차이가 점프한다.<br>"
     "<code>2,3,4월 → 1,2,3 − 1,2,3 = 0,0,0</code> (같은 그룹)<br>"
     "<code>2월, 5월 → 1,4 − 1,2 = 0,2</code> (다른 그룹)",
     "월 중복 제거(<code>DISTINCT</code>)를 안 하면 같은 달 두 번 결제한 유저가 연속으로 잘못 잡힌다.",
     "마지막에 <code>COUNT(DISTINCT user_id)</code> — 한 유저가 연속 구간을 두 개 가질 수 있다.",
   ],
   variants="“연속 출석 일수”, “N일 연속 접속” 전부 동일. 일 단위면 DATEDIFF 를 일련번호로."),

 dict(id=9, title="채널별 결제 전환과 LTV", level="보통",
   asks="분모가 다른 지표 두 개를 한 쿼리에서 만들 줄 아는가.",
   steps=[
     "유저별 누적 결제액을 먼저 만든다.",
     "users 에 LEFT JOIN.",
     "<code>COUNT(*)</code> 는 전체 유저, <code>COUNT(결제컬럼)</code> 은 결제 유저. NULL 을 세지 않는 성질을 이용한다.",
     "AVG 도 NULL 을 무시하므로 결제 유저 기준 평균이 자동으로 나온다.",
   ],
   sql="""WITH pu AS (
  SELECT user_id, SUM(amount) AS amt FROM payments GROUP BY user_id
)
SELECT u.channel,
       COUNT(*)                                       AS total_users,
       COUNT(pu.user_id)                              AS paying_users,
       ROUND(100.0 * COUNT(pu.user_id) / COUNT(*), 2) AS paying_ratio,
       ROUND(AVG(pu.amt), 2)                          AS ltv
FROM users u
LEFT JOIN pu ON pu.user_id = u.user_id
GROUP BY u.channel
ORDER BY ltv DESC;""",
   traps=[
     "<b>이 문제의 핵심은 <code>COUNT(*)</code> 와 <code>COUNT(컬럼)</code> 의 차이</b>다. 분모 두 개를 CASE 없이 만들 수 있다.",
     "LTV 분모를 전체 유저로 착각하기 쉽다. 문제를 다시 읽을 것.",
     "<code>AVG(COALESCE(amt,0))</code> 로 쓰면 결제 안 한 유저가 0 으로 들어가 LTV 가 내려간다. 의도가 다르다.",
   ],
   variants="“ARPU vs ARPPU” 가 정확히 이 차이다. ARPU 는 전체 유저, ARPPU 는 결제 유저 기준."),

 dict(id=10, title="채널별 ARPPU와 순위 변동", level="어려움",
   asks="윈도우를 두 단계로 겹쳐 쓸 줄 아는가.",
   steps=[
     "월×채널 ARPPU 를 먼저 집계.",
     "월 안에서 <code>RANK()</code> → 파티션은 <b>월</b>.",
     "채널 기준으로 <code>LAG(rnk)</code> → 파티션은 <b>채널</b>. 파티션 기준이 다르다.",
     "윈도우 결과를 다시 윈도우에 넣으려면 한 단계 감싸야 한다.",
   ],
   sql="""WITH a AS (
  SELECT DATE_FORMAT(p.paid_date, '%Y-%m-01') AS mm, u.channel,
         ROUND(SUM(p.amount) / COUNT(DISTINCT p.user_id), 2) AS arppu
  FROM payments p JOIN users u ON u.user_id = p.user_id
  GROUP BY mm, u.channel
),
r AS (
  SELECT mm, channel, arppu,
         RANK() OVER (PARTITION BY mm ORDER BY arppu DESC) AS rnk
  FROM a
)
SELECT DATE_FORMAT(mm, '%Y-%m') AS month, channel, arppu, rnk,
       LAG(rnk) OVER (PARTITION BY channel ORDER BY mm)       AS prev_rnk,
       LAG(rnk) OVER (PARTITION BY channel ORDER BY mm) - rnk AS rank_change
FROM r
ORDER BY mm, rnk;""",
   traps=[
     "<b>같은 SELECT 안에서 RANK 를 LAG 에 넣을 수 없다.</b> CTE 로 한 단계 감싼다. 이 문제가 묻는 게 바로 이것.",
     "순위는 <b>월</b>로 파티션, 변동은 <b>채널</b>로 파티션. 둘을 같게 쓰면 전부 틀린다.",
     "<code>rank_change</code> 부호 방향을 문제대로. 여기서는 ‘전월 − 이번달’이라 오르면 양수.",
     "ARPPU 분모는 <code>COUNT(DISTINCT user_id)</code>. 결제 건수가 아니다.",
   ],
   variants="“전월 대비 매출 순위 변동”, “주간 랭킹 변화” 전부 같은 2단 구조."),

 dict(id=11, title="전 유저 결제 요약 (NULL 처리)", level="보통",
   asks="LEFT JOIN 후 NULL 을 어떻게 다루는가. 그리고 NULL 정렬.",
   steps=[
     "users 기준 LEFT JOIN.",
     "건수는 <code>COUNT(p.user_id)</code> — NULL 을 안 세므로 0 이 된다.",
     "합계는 <code>COALESCE(SUM(...), 0)</code> — SUM 은 대상이 없으면 NULL 을 반환한다.",
     "마지막 결제일은 NULL 그대로 두되, 정렬에서 뒤로 보낸다.",
   ],
   sql="""SELECT u.user_id, u.channel,
       COUNT(p.user_id)           AS pay_count,
       COALESCE(SUM(p.amount), 0) AS total_amount,
       MAX(p.paid_date)           AS last_paid
FROM users u
LEFT JOIN payments p ON p.user_id = u.user_id
GROUP BY u.user_id, u.channel
ORDER BY (MAX(p.paid_date) IS NULL), COALESCE(SUM(p.amount),0) DESC, u.user_id
LIMIT 20;""",
   traps=[
     "<code>COUNT(*)</code> 를 쓰면 결제 없는 유저도 <b>1</b> 이 된다. LEFT JOIN 으로 행은 하나 생기기 때문. <code>COUNT(p.user_id)</code> 여야 0.",
     "<code>SUM</code> 은 대상 행이 없으면 0 이 아니라 <b>NULL</b>. COALESCE 로 감싼다.",
     "MySQL 에 <code>NULLS LAST</code> 가 없다. <code>ORDER BY (컬럼 IS NULL), 컬럼</code> 로 쓴다. 조건식이 0/1 이 되어 NULL 이 뒤로 간다.",
     "<code>COALESCE(total, '없음')</code> 처럼 <b>문자 기본값을 넣으면 컬럼 전체가 문자열</b>이 되어 정렬이 사전순으로 깨진다.",
   ],
   variants="“주문 없는 고객 포함 요약”, “미거래 종목 포함” 전부 동일."),

 dict(id=12, title="채널별 pro 비중 (0 나누기)", level="보통",
   asks="분모가 0 이 될 수 있는 상황을 아는가.",
   steps=[
     "결제 유저 수와 pro 유저 수를 조건부 DISTINCT 집계로.",
     "비율 계산에서 분모를 <code>NULLIF(분모, 0)</code> 로 감싼다.",
   ],
   sql="""SELECT u.channel,
       COUNT(DISTINCT p.user_id) AS paying_users,
       COUNT(DISTINCT CASE WHEN p.plan='pro' THEN p.user_id END) AS pro_users,
       ROUND(100.0 * COUNT(DISTINCT CASE WHEN p.plan='pro' THEN p.user_id END)
             / NULLIF(COUNT(DISTINCT p.user_id), 0), 2) AS pro_ratio
FROM users u
LEFT JOIN payments p ON p.user_id = u.user_id
GROUP BY u.channel
ORDER BY pro_ratio DESC, u.channel;""",
   traps=[
     "<b><code>IFNULL(분모, 0)</code> 은 정반대다.</b> 0 나누기를 막는 게 아니라 만든다. 방어는 <code>NULLIF(분모, 0)</code>.",
     "결제 유저가 0 명인 채널도 결과에 나와야 하므로 LEFT JOIN.",
     "<code>CASE WHEN ... THEN user_id END</code> 에 <b>ELSE 를 쓰지 않는다</b>. ELSE 0 을 넣으면 0 도 값이라 DISTINCT 집계에 섞인다.",
     "이 데이터로는 ‘분모 0’ 이 드물다. <b>안 걸린다고 맞는 게 아니다</b> — 여러 데이터셋으로 채점되면 그때 터진다.",
   ],
   variants="“환불률”, “쿠폰 사용률” 처럼 모집단이 비어 있을 수 있는 비율 전부."),
]

# ── Q13~Q17 해설 ─────────────────────────────────────────────────────
GUIDE_EXTRA = [
    {
        "id": 13,
        "title": "퍼널 단계별 유저 수와 단계 전환율",
        "level": "쉬움",
        "asks": "한 테이블을 한 번만 읽어 네 숫자를 뽑고, 그 숫자끼리 나눈다. "
                "JOIN 도 GROUP BY 도 필요 없다. 여기서 시간을 쓰면 안 되는 문제다.",
        "steps": [
            "<code>COUNT(DISTINCT CASE WHEN ... THEN user_id END)</code> 로 단계별 순 유저 수를 "
            "한 줄씩 만든다. 테이블을 네 번 읽을 필요가 없다.",
            "그 네 숫자를 <b>서브쿼리로 감싸서</b> 바깥에서 이름으로 다시 쓴다. "
            "그러지 않으면 전환율 식에 COUNT(DISTINCT CASE...) 를 또 써야 해서 길이가 네 배가 된다.",
            "전환율은 <code>100.0 *</code> 을 앞에 붙이고 <code>ROUND(..., 1)</code>.",
            "분모에 <code>NULLIF(분모, 0)</code> 을 씌운다.",
        ],
        "sql": """SELECT a AS app_open_users,
       v AS item_view_users,
       k AS cart_users,
       p AS purchase_users,
       ROUND(100.0 * v / NULLIF(a, 0), 1) AS view_conversion_rate,
       ROUND(100.0 * k / NULLIF(v, 0), 1) AS cart_conversion_rate,
       ROUND(100.0 * p / NULLIF(k, 0), 1) AS purchase_conversion_rate
FROM (
  SELECT COUNT(DISTINCT CASE WHEN event_name = 'app_open'    THEN user_id END) AS a,
         COUNT(DISTINCT CASE WHEN event_name = 'item_view'   THEN user_id END) AS v,
         COUNT(DISTINCT CASE WHEN event_name = 'add_to_cart' THEN user_id END) AS k,
         COUNT(DISTINCT CASE WHEN event_name = 'purchase'    THEN user_id END) AS p
  FROM user_event_logs
) c;""",
        "traps": [
            "<b>DISTINCT 를 빼면 틀린다.</b> 한 유저가 app_open 을 네 번 남기면 "
            "<code>COUNT(CASE ...)</code> 는 4 를 센다. 묻는 건 유저 수이지 이벤트 수가 아니다.",
            "<b>CASE 에 ELSE 를 쓰지 마라.</b> <code>ELSE 0</code> 을 붙이면 0 도 값이라서 "
            "<code>COUNT(DISTINCT ...)</code> 가 0 을 하나의 유저로 센다. "
            "ELSE 를 안 쓰면 NULL 이 되고 COUNT 는 NULL 을 세지 않는다.",
            "<b>100.0 의 소수점이 핵심이다.</b> <code>100 * v / a</code> 는 정수 나눗셈이 되는 "
            "엔진에서 0 이 나온다. 토스 테스트돔에서 실제로 이걸로 틀린 적이 있다.",
            "<b>이 문제의 NULLIF 는 채점으로 확인할 수 없다.</b> MySQL·SQLite 는 0 으로 나누면 "
            "오류 없이 NULL 을 준다. PostgreSQL·MS SQL 은 오류가 난다. "
            "즉 여기서는 있어도 없어도 같은 답이 나오지만, 습관을 안 들이면 다른 엔진에서 터진다.",
            "<b>이 문제의 '퍼널' 은 진짜 퍼널이 아니다.</b> 단계 순서를 안 따지므로, "
            "장바구니를 안 거치고 구매한 유저가 있으면 뒤 단계가 앞 단계보다 많아져 "
            "전환율이 100% 를 넘을 수 있다. 면접에서 이걸 물으면 "
            "'순서를 강제하려면 단계별 첫 시각을 비교해야 한다' 고 답하면 된다.",
        ],
        "variants": "“단계별 이탈률”은 <code>100 − 전환율</code>. "
                    "“채널별 퍼널”이면 <code>GROUP BY channel</code> 만 추가되고 구조는 그대로다. "
                    "순서를 강제하는 진짜 퍼널은 단계별 <code>MIN(created_at)</code> 을 구해 "
                    "<code>MIN(cart) &gt; MIN(view)</code> 처럼 비교한다.",
    },
    {
        "id": 14,
        "title": "코호트별 D7 리텐션율",
        "level": "보통",
        "asks": "코호트 테이블을 왼쪽에 두고 활동 로그를 LEFT JOIN 한다. "
                "코호트 문제의 90% 가 이 모양이다.",
        "steps": [
            "코호트 테이블(<code>first_trades</code>)을 <b>왼쪽</b>에 둔다. 분모가 여기서 나온다.",
            "활동 로그를 <code>LEFT JOIN</code> 하고, 조인 조건에 "
            "<code>visit_date = first_trade_date + 7일</code> 을 넣는다.",
            "분모는 <code>COUNT(DISTINCT f.user_id)</code>, 분자는 "
            "<code>COUNT(DISTINCT v.user_id)</code>. 둘 다 DISTINCT 다.",
            "범위 조건은 <code>WHERE</code> 에 쓴다 (왼쪽 테이블 조건이므로 안전하다).",
        ],
        "sql": """SELECT f.first_trade_date,
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
ORDER BY f.first_trade_date;""",
        "traps": [
            "<b>JOIN 조건을 WHERE 로 옮기면 LEFT JOIN 이 INNER JOIN 이 된다.</b> "
            "<code>WHERE v.visit_date = ...</code> 로 쓰면 재방문 안 한 유저의 NULL 행이 "
            "조건에 걸려 사라지고, 분모까지 같이 깎인다. "
            "<b>오른쪽 테이블 조건은 반드시 ON 에</b> — 이 한 줄이 리텐션 문제의 핵심이다.",
            "<b>'정확히 7일' 과 '7일 이내' 는 다른 문제다.</b> <code>=</code> 로 쓸 자리에 "
            "<code>&lt;=</code> 를 쓰면 숫자가 크게 부풀어 오른다. 문제를 다시 읽어라.",
            "<b>분자에 DISTINCT 를 빼면 100% 를 넘는다.</b> 방문 로그는 같은 유저가 같은 날 "
            "여러 행을 남길 수 있다. 리텐션율이 100 을 넘으면 거의 항상 이 실수다.",
            "<b>분모를 COUNT(*) 로 쓰면 안 된다.</b> LEFT JOIN 후의 <code>COUNT(*)</code> 는 "
            "조인으로 불어난 행 수다. 코호트 크기가 아니다.",
            "<b>재방문자 0 명인 날도 한 행 나와야 한다.</b> LEFT JOIN 이면 자동으로 0 이 된다. "
            "<code>COUNT</code> 는 빈 입력에서 0 을 돌려주기 때문이다 "
            "(<code>SUM</code> 은 NULL 이 된다 — 다른 문제에서 자주 나오는 함정).",
        ],
        "variants": "“D1/D7/D30 을 한 번에”면 조인 조건을 "
                    "<code>visit_date IN (+1일, +7일, +30일)</code> 로 바꾸고 "
                    "<code>COUNT(DISTINCT CASE WHEN ... END)</code> 를 세 개 만든다. "
                    "“월 코호트 매트릭스”면 <code>TIMESTAMPDIFF(MONTH, 코호트월, 활동월)</code> 을 "
                    "경과 개월로 쓰고 그걸로 피벗한다.",
    },
    {
        "id": 15,
        "title": "유저별 최장 연속 거래일수",
        "level": "어려움",
        "asks": "gaps and islands. 알면 2분, 모르면 못 푼다. 반드시 외워 둘 패턴.",
        "steps": [
            "먼저 <b>조건을 걸고 하루 단위로 중복을 지운다</b>: "
            "<code>SELECT DISTINCT user_id, order_date ... WHERE status='COMPLETED'</code>. "
            "이 한 줄에 문제의 조건 두 개가 다 들어 있다.",
            "날짜를 일련번호로 바꾼다: <code>DATEDIFF(order_date, '기준일')</code>.",
            "<code>일련번호 − ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY order_date)</code> "
            "→ 연속 구간마다 같은 값이 나온다.",
            "그 값으로 묶어 <code>COUNT(*)</code> → 구간 길이. "
            "유저별 <code>MAX()</code> → 최장 길이. <code>HAVING</code> 으로 3 이상만.",
        ],
        "sql": """WITH d AS (
  SELECT DISTINCT user_id, order_date
  FROM stock_orders
  WHERE status = 'COMPLETED'
),
g AS (
  SELECT user_id, order_date,
         DATEDIFF(order_date, '2026-01-01')
         - ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY order_date) AS grp
  FROM d
),
runs AS (
  SELECT user_id, grp, COUNT(*) AS run_len
  FROM g GROUP BY user_id, grp
)
SELECT user_id, MAX(run_len) AS max_streak_days
FROM runs
GROUP BY user_id
HAVING MAX(run_len) >= 3
ORDER BY max_streak_days DESC, user_id ASC;""",
        "traps": [
            "<b>왜 되는가.</b> 연속이면 날짜 일련번호와 행 번호가 같은 보폭으로 늘어나 차이가 "
            "고정된다. 끊기면 차이가 점프한다.<br>"
            "<code>3/2,3/3,3/4 → 60,61,62 − 1,2,3 = 59,59,59</code> (한 구간)<br>"
            "<code>3/2, 3/6 → 60,64 − 1,2 = 59,62</code> (다른 구간)",
            "<b>DISTINCT 를 빼면 연속일수가 부풀어 오른다.</b> 하루에 3건 거래했으면 "
            "ROW_NUMBER 가 세 칸 가는데 날짜는 그대로라 차이가 틀어진다.",
            "<b>status 필터를 빼면 끊겨야 할 구간이 이어진다.</b> 그 날 주문이 전부 CANCELLED 면 "
            "거래하지 않은 날이다. 「끊김복귀」 데이터셋이 이걸 잡는다.",
            "<b>HAVING 에 MAX(run_len) 을 그대로 쓴다.</b> <code>WHERE run_len &gt;= 3</code> 으로 "
            "미리 걸러도 같은 답이 나오지만, 그러면 '최장 구간이 3 미만인 유저' 와 "
            "'3 이상 구간만 남긴 유저' 의 MAX 가 달라질 수 있는 변형 문제에서 틀린다.",
            "<b>정렬 두 개를 다 쓴다.</b> 동점이 많은 문제다. "
            "<code>max_streak_days DESC</code> 만 쓰면 같은 값들 사이 순서가 실행마다 바뀐다.",
        ],
        "variants": "“연속 출석일수”, “N일 연속 접속”, “연속 결제 개월수” 전부 같은 패턴이다. "
                    "월 단위면 일련번호를 <code>TIMESTAMPDIFF(MONTH, 기준월, 그달)</code> 로 바꾼다. "
                    "“현재 진행 중인 연속일수”면 마지막 구간만 "
                    "(<code>MAX(order_date) = 오늘</code> 인 구간) 남긴다.",
    },
    {
        "id": 16,
        "title": "A/B 테스트 그룹 집계 (상위 1% 제외)",
        "level": "보통",
        "asks": "순서가 생명인 문제. ①0 채우기 → ②순위 매기기 → ③자르기 → ④집계. "
                "이 순서를 바꾸면 답이 달라진다.",
        "steps": [
            "<b>실험 참가자 테이블을 왼쪽에 두고</b> 거래 요약을 LEFT JOIN, "
            "<code>COALESCE(금액, 0)</code> 으로 0 을 채운다. 분모는 참가자 수여야 한다.",
            "그 결과 위에서 <code>PERCENT_RANK() OVER (PARTITION BY group_name ORDER BY amt)</code>. "
            "0 을 채운 <b>뒤에</b> 순위를 매기는 것이 중요하다 — 0 인 유저도 모집단의 일부다.",
            "<code>WHERE pr &lt;= 0.99</code> 로 이상치를 떨어뜨린다. "
            "윈도우 함수는 WHERE 에서 못 쓰므로 반드시 서브쿼리/CTE 로 한 단 감싸야 한다.",
            "남은 행으로 <code>COUNT(*)</code>, <code>SUM(amt)</code>, "
            "그리고 <code>ROUND(SUM(amt)/COUNT(*), 0)</code>.",
        ],
        "sql": """WITH j AS (
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
ORDER BY group_name;""",
        "traps": [
            "<b>윈도우 함수는 WHERE 에 못 쓴다.</b> "
            "<code>WHERE PERCENT_RANK() OVER (...) &lt;= 0.99</code> 는 문법 오류다. "
            "실행 순서가 WHERE → 윈도우 함수이기 때문이다. 한 단 감싸는 것 외에 방법이 없다.",
            "<b>LEFT JOIN 을 INNER JOIN 으로 쓰면 유저 수가 깎인다.</b> 거래가 없는 참가자도 "
            "실험 참가자다. A/B 테스트에서 분모를 임의로 줄이면 그 결과는 못 쓴다. "
            "「결제없음」 데이터셋이 이걸 잡는다.",
            "<b>0 을 채우기 전에 순위를 매기면 다른 답이 나온다.</b> 거래 없는 유저를 빼고 "
            "순위를 매기면 모집단이 달라지고 잘려 나가는 사람도 달라진다. 문제가 지정한 순서를 따르라.",
            "<b>PERCENT_RANK 의 정의를 알고 써라.</b> "
            "<code>(순위 − 1) / (전체 − 1)</code> 이므로 <b>최솟값은 항상 0, 최댓값은 항상 1</b> 이다. "
            "그래서 <code>&gt; 0.99</code> 는 '상위 1%' 가 아니라 거의 항상 "
            "<b>최댓값 행만</b> 떨어뜨린다. 그룹에 2명뿐이면 1명이 날아간다. "
            "면접에서 물으면 '진짜 상위 1% 는 "
            "<code>NTILE(100)</code> 이나 <code>PERCENTILE_CONT</code> 로 임계값을 구해 자른다' 고 답하라.",
            "<b>최댓값이 동점이면 둘 다 빠진다.</b> PERCENT_RANK 는 동점에 같은 값을 주므로 "
            "공동 1위가 둘이면 둘 다 1.0 이다. 「동점」 데이터셋이 이걸 잡는다.",
            "<b>ROUND(..., 0) 은 정수가 아니라 소수 0자리다.</b> 엔진에 따라 "
            "<code>150</code> 또는 <code>150.0</code> 으로 보인다. 정수형으로 받아야 하면 "
            "<code>CAST(ROUND(...) AS SIGNED)</code> 까지 써라.",
        ],
        "variants": "“상·하위 1% 양쪽 제거”면 <code>pr BETWEEN 0.01 AND 0.99</code>. "
                    "“중앙값 비교”면 <code>ROW_NUMBER</code> + <code>COUNT() OVER</code> 패턴. "
                    "“전환율 비교”면 <code>COUNT(DISTINCT 전환유저)/COUNT(DISTINCT 참가자)</code> 로 "
                    "분모를 참가자 전체로 둔다 (intention-to-treat).",
    },
    {
        "id": 17,
        "title": "3일 이상 연속 상승 구간 모두 찾기",
        "level": "어려움",
        "asks": "LAG 로 상승일을 가리고, 그 위에 gaps and islands 를 한 번 더 얹는다. "
                "두 패턴을 포개는 문제. 이게 풀리면 시계열 문제는 거의 다 풀린다.",
        "steps": [
            "먼저 <b>모든 행에 행 번호</b>를 매긴다: "
            "<code>ROW_NUMBER() OVER (PARTITION BY stock_code ORDER BY trade_date) AS rn</code>. "
            "이게 '몇 번째 거래일인가' 다. 날짜가 아니라 이 번호가 기준이 된다.",
            "같은 단에서 <code>LAG(close_price) OVER (PARTITION BY stock_code ORDER BY trade_date)</code> "
            "로 전 거래일 종가를 끌어온다.",
            "<code>WHERE prev IS NOT NULL AND close_price &gt; prev</code> 로 상승일만 남긴다.",
            "남은 상승일에 <b>새로 행 번호를 매기고</b> "
            "<code>rn − 새 행번호</code> → 연속 상승 구간마다 같은 값.",
            "그 값으로 묶어 <code>MIN/MAX/COUNT</code>, <code>HAVING COUNT(*) &gt;= 3</code>.",
        ],
        "sql": """WITH p AS (
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
ORDER BY stock_code, streak_start_date;""",
        "traps": [
            "<b>날짜 차이로 구간을 묶으면 틀린다.</b> 주말이 비어 있어서 금요일과 월요일은 "
            "날짜로는 3일 차이지만 거래일로는 연속이다. "
            "<code>DATEDIFF</code> 대신 <b>행 번호</b>를 일련번호로 써야 한다. "
            "「끊김복귀」·「동점」 데이터셋이 이걸 잡는다.",
            "<b>rn 은 상승일만 걸러낸 뒤에 매기면 안 된다.</b> 전체 행에 먼저 매겨 둬야 "
            "'거래일 순서' 가 보존된다. 걸러낸 뒤 매기면 하락일이 사라진 자리가 메워져 "
            "끊긴 구간이 붙어 버린다.",
            "<b>&gt; 와 &gt;= 는 다른 문제다.</b> 전일과 같은 가격은 상승이 아니다. "
            "「경계값」 데이터셋에 같은 가격이 들어 있다.",
            "<b>prev IS NOT NULL 을 빼면 첫 행이 섞인다.</b> 각 종목의 첫 거래일은 전일이 없어서 "
            "LAG 가 NULL 이다. <code>close_price &gt; NULL</code> 은 NULL(거짓 취급)이라 "
            "대부분 자동으로 빠지지만, 명시하는 편이 안전하고 읽기도 낫다.",
            "<b>streak_days 는 상승일의 개수다.</b> 상승이 시작되기 전 날(기준이 된 날)은 세지 "
            "않는다. 세어야 하는 문제면 <code>COUNT(*) + 1</code> 이고 시작일도 하루 앞이 된다. "
            "문제를 다시 읽어라 — 출제자가 어느 쪽을 묻는지가 갈린다.",
            "<b>PARTITION BY stock_code 를 LAG 와 ROW_NUMBER 양쪽에 다 써라.</b> "
            "하나라도 빠지면 종목이 넘어가는 지점에서 앞 종목의 마지막 가격과 비교해 버린다.",
        ],
        "variants": "“N일 연속 하락”이면 부등호만 뒤집는다. "
                    "“최장 구간 하나만”이면 마지막에 "
                    "<code>ROW_NUMBER() OVER (PARTITION BY stock_code ORDER BY COUNT(*) DESC)</code> "
                    "로 1등만. “연속 상승률”이면 구간 양 끝 종가가 필요하므로 "
                    "<code>FIRST_VALUE/LAST_VALUE</code> 를 쓰거나 시작일 하루 전 종가를 따로 끌어온다.",
    },
]

GUIDE = GUIDE + GUIDE_EXTRA

# ── Q18~Q20 해설 (NULL·COALESCE 집중) ────────────────────────────────
GUIDE_NULL = [
    {
        "id": 18, "title": "채널별 ARPU 와 ARPPU", "level": "보통",
        "asks": "분모가 다른 두 평균을 한 쿼리에서 만든다. "
                "실무에서 가장 자주 틀리는 지표 쌍이고, 면접에서도 묻는다.",
        "steps": [
            "<b>ARPU 와 ARPPU 는 분자가 같고 분모만 다르다.</b> "
            "분자는 둘 다 결제액 합계, 분모는 ARPU 는 전체 가입자, ARPPU 는 결제 유저.",
            "<code>users LEFT JOIN payments</code> 로 결제 안 한 유저까지 붙인다.",
            "분모 두 개를 <code>COUNT(DISTINCT u.user_id)</code> 와 "
            "<code>COUNT(DISTINCT p.user_id)</code> 로 따로 센다. "
            "LEFT JOIN 이라 결제 없는 유저의 <code>p.user_id</code> 는 NULL 이고, "
            "<code>COUNT(DISTINCT)</code> 는 NULL 을 안 세므로 자동으로 결제 유저 수가 된다.",
            "<code>* 1.0</code> 을 붙이고 <code>ROUND(..., 2)</code>.",
        ],
        "sql": """SELECT u.channel,
       COUNT(DISTINCT u.user_id) AS users,
       COUNT(DISTINCT p.user_id) AS payers,
       ROUND(COALESCE(SUM(p.amount), 0) * 1.0
             / NULLIF(COUNT(DISTINCT u.user_id), 0), 2)     AS arpu,
       COALESCE(ROUND(SUM(p.amount) * 1.0
             / NULLIF(COUNT(DISTINCT p.user_id), 0), 2), 0) AS arppu
FROM users u
LEFT JOIN payments p ON p.user_id = u.user_id
GROUP BY u.channel
ORDER BY arpu DESC, u.channel ASC;""",
        "traps": [
            "<b><code>AVG(p.amount)</code> 는 ARPU 도 ARPPU 도 아니다.</b> "
            "결제 <b>건당</b> 평균이다. 한 유저가 5번 결제하면 그 유저가 5번 반영된다. "
            "'유저당' 을 물었으면 분모를 유저 수로 직접 써야 한다. "
            "이 한 줄 차이로 숫자가 두 배 넘게 벌어진다.",
            "<b>AVG 는 NULL 을 분모에서도 뺀다.</b> 결제 안 한 유저의 amount 는 "
            "LEFT JOIN 뒤 NULL 이고, <code>AVG</code> 는 그 행을 분모에서 제외한다. "
            "그래서 <code>AVG(p.amount)</code> 로는 ARPU 가 절대 안 나온다. "
            "값이 10, NULL, 20 이면 AVG 는 15 지 10 이 아니다.",
            "<b>COALESCE 위치가 두 컬럼에서 다르다.</b><br>"
            "arpu — 분모(가입자 수)는 항상 1 이상이므로 <b>분자</b>를 0 으로 채운다: "
            "<code>COALESCE(SUM(...), 0) / 가입자수</code><br>"
            "arppu — 분모(결제 유저 수)가 0 일 수 있어 나눗셈 자체가 NULL 이 된다. "
            "<b>결과 전체</b>를 0 으로 채운다: <code>COALESCE(ROUND(...), 0)</code><br>"
            "arppu 를 arpu 처럼 쓰면 결제 없는 채널에서 0 대신 NULL 이 나온다.",
            "<b><code>* 1.0</code> 을 빼면 안 된다.</b> amount 와 COUNT 가 둘 다 정수라 "
            "정수 나눗셈이 된다. 실제 토스 테스트에서 이걸로 틀린 적이 있다.",
            "<b>정렬을 두 개 다 쓴다.</b> <code>arpu DESC</code> 만 쓰면 동점에서 순서가 흔들린다.",
        ],
        "variants": "“ARPPU 대신 중앙값”이면 <code>ROW_NUMBER</code> + "
                    "<code>COUNT() OVER</code> 패턴. "
                    "“월별 ARPU 추이”면 <code>GROUP BY 월, 채널</code> 로 바꾸되 "
                    "<b>분모를 그 달의 활성 유저로 둘지 전체 가입자로 둘지</b>를 "
                    "문제에서 확인하라 — 여기서 정의가 갈린다.",
    },
    {
        "id": 19, "title": "한 번도 결제하지 않은 유저 수", "level": "쉬움",
        "asks": "'존재하지 않는 것 찾기'. 쉬워 보이지만 <code>NOT IN</code> 을 쓰면 "
                "데이터에 NULL 이 하나 섞인 순간 <b>결과가 0행</b>이 된다. "
                "이 함정 하나만 아는지 보는 문제다.",
        "steps": [
            "결제한 유저 목록을 만든다. <b>user_id 가 NULL 인 행은 뺀다</b> "
            "(누구의 결제인지 모르는 행이므로).",
            "<code>users LEFT JOIN 그 목록</code> → 붙지 않은 유저가 '결제 없음' 이다.",
            "<code>SUM(CASE WHEN p.user_id IS NULL THEN 1 ELSE 0 END)</code> 으로 센다. "
            "<code>COUNT(*)</code> 로 세면 전체 유저 수가 나온다.",
            "0 명인 채널도 한 행 나와야 하므로 <code>WHERE</code> 로 걸러내지 말고 "
            "<code>CASE</code> 로 센다.",
        ],
        "sql": """-- 방법 1. LEFT JOIN ... IS NULL (0명인 채널도 행이 남는다)
SELECT u.channel,
       SUM(CASE WHEN p.user_id IS NULL THEN 1 ELSE 0 END) AS never_paid
FROM users u
LEFT JOIN (SELECT DISTINCT user_id FROM payments WHERE user_id IS NOT NULL) p
       ON p.user_id = u.user_id
GROUP BY u.channel
ORDER BY never_paid DESC, u.channel ASC;

-- 방법 2. NOT EXISTS — NULL 에 면역이라 IS NOT NULL 을 안 써도 된다
SELECT u.channel,
       SUM(CASE WHEN NOT EXISTS (SELECT 1 FROM payments p
                                  WHERE p.user_id = u.user_id)
                THEN 1 ELSE 0 END) AS never_paid
FROM users u
GROUP BY u.channel
ORDER BY never_paid DESC, u.channel ASC;""",
        "traps": [
            "<b><code>NOT IN</code> + NULL = 결과 전멸.</b> 이게 이 문제의 핵심이다.<br>"
            "<code>WHERE u.user_id NOT IN (SELECT user_id FROM payments)</code> 는 "
            "payments 에 NULL 이 <b>한 행이라도</b> 있으면 <b>0행</b>을 돌려준다.<br>"
            "<code>5 NOT IN (1, 2, NULL)</code> 은 "
            "<code>5&lt;&gt;1 AND 5&lt;&gt;2 AND 5&lt;&gt;NULL</code> 이고, "
            "마지막 항이 NULL 이라 전체가 NULL → WHERE 에서 거짓 취급 → 전부 탈락.<br>"
            "본 데이터에는 NULL 이 없어서 통과하고, 「NULL섞임」 데이터셋에서 터진다. "
            "실제 시험이 여러 데이터셋으로 채점하는 이유가 바로 이것이다.",
            "<b><code>NOT EXISTS</code> 는 NULL 에 면역이다.</b> "
            "<code>p.user_id = u.user_id</code> 가 NULL 이면 매칭 실패로 처리되어 "
            "그 행은 조용히 무시된다. '존재하지 않는 것 찾기' 는 "
            "<b>NOT EXISTS 를 기본값</b>으로 삼으면 이 사고가 안 난다.",
            "<b><code>IN</code> 은 멀쩡하다.</b> 하나만 맞으면 참이므로 NULL 이 섞여도 된다. "
            "문제는 부정형(<code>NOT IN</code>)뿐이다.",
            "<b><code>COUNT(*)</code> 로 세면 안 된다.</b> LEFT JOIN 후 "
            "<code>COUNT(*)</code> 는 그 채널의 전체 유저 수다. "
            "<code>SUM(CASE WHEN ... IS NULL THEN 1 ELSE 0 END)</code> 이 정확하다.",
            "<b>서브쿼리에 <code>DISTINCT</code> 를 넣어라.</b> 안 넣으면 한 유저의 결제가 "
            "여러 건일 때 LEFT JOIN 으로 행이 불어난다. "
            "여기서는 IS NULL 만 세니 결과가 같지만, 금액을 같이 구하는 변형에서 바로 깨진다.",
        ],
        "variants": "“이탈 유저 찾기”, “한 번도 로그인 안 한 유저”, “재구매 없는 유저” "
                    "전부 같은 패턴. 반대로 “결제한 유저만”이면 <code>EXISTS</code> 또는 "
                    "<code>INNER JOIN + DISTINCT</code>.",
    },
    {
        "id": 20, "title": "유저별 결제 요약 (NULL 표시와 정렬 분리)", "level": "보통",
        "asks": "토스 쿼리 테스트에 나온 '데이터 타입 문제' 가 정확히 이 유형이다. "
                "<b>보여 줄 값</b>과 <b>정렬할 값</b>을 분리할 수 있는지를 본다.",
        "steps": [
            "<code>users LEFT JOIN payments</code> + <code>GROUP BY user_id</code> 로 "
            "유저별 합계·첫 결제일·마지막 결제일을 만든다.",
            "금액은 <code>COALESCE(SUM(p.amount), 0)</code> — <b>SUM 밖에</b> 씌운다.",
            "첫 결제일은 <b>NULL 을 그대로 둔다</b>. 문자열로 바꾸면 정렬이 깨진다.",
            "마지막 plan 은 <code>paid_date = MAX(paid_date)</code> 로 다시 조인해 가져오고 "
            "<code>COALESCE(..., '없음')</code> — 이 컬럼은 원래 문자열이라 안전하다.",
            "정렬은 원본 컬럼으로 한다: "
            "<code>ORDER BY total_amount DESC, first_paid ASC, user_id ASC</code>.",
        ],
        "sql": """WITH s AS (
  SELECT u.user_id,
         COALESCE(SUM(p.amount), 0) AS total_amount,
         MIN(p.paid_date)           AS first_paid,
         MAX(p.paid_date)           AS last_paid
  FROM users u
  LEFT JOIN payments p ON p.user_id = u.user_id
  GROUP BY u.user_id
)
SELECT s.user_id, s.total_amount, s.first_paid,
       COALESCE(MAX(lp.plan), '없음') AS plan_label
FROM s
LEFT JOIN payments lp
       ON lp.user_id = s.user_id AND lp.paid_date = s.last_paid
GROUP BY s.user_id, s.total_amount, s.first_paid
ORDER BY s.total_amount DESC, s.first_paid ASC, s.user_id ASC
LIMIT 20;""",
        "traps": [
            "<b>날짜에 COALESCE 로 문자열을 넣으면 컬럼 전체가 문자열이 된다.</b> "
            "<code>COALESCE(first_paid, '없음')</code> 을 쓰면 반환 타입이 공통 타입인 "
            "<b>문자열</b>로 승격되고, 그걸로 정렬하면 사전순이 된다. "
            "MySQL·SQLite 는 이 변환을 <b>오류 없이 조용히</b> 하므로 "
            "에러도 안 나고 결과만 틀린다. (PostgreSQL·DuckDB 는 오류를 낸다.)<br>"
            "<b>해법: 표시와 정렬을 분리한다.</b> 표시용 문자열 컬럼을 따로 만들고 "
            "<code>ORDER BY</code> 에는 <b>원본 컬럼</b>을 쓴다.",
            "<b>정렬에서 NULL 의 위치는 엔진마다 다르다.</b> 실제로 돌려 본 결과:<br>"
            "<code>MySQL·SQLite</code> → NULL 을 가장 작은 값으로 본다 "
            "(ASC 면 맨 앞, DESC 면 맨 뒤)<br>"
            "<code>PostgreSQL·DuckDB</code> → 기본이 NULLS LAST (ASC 에서도 맨 뒤)<br>"
            "확실하게 하려면 <code>ORDER BY (first_paid IS NULL), first_paid</code> 처럼 "
            "<code>IS NULL</code>(0/1)을 첫 키로 써서 직접 정한다. "
            "MySQL 에는 <code>NULLS LAST</code> 문법이 없다.",
            "<b>COALESCE 를 SUM 안에 넣을지 밖에 씌울지.</b> "
            "<code>LEFT JOIN + GROUP BY 왼쪽테이블</code> 이면 그룹마다 NULL 행이 한 개 남아 "
            "<code>SUM(COALESCE(amount,0))</code> 도 0 이 나온다. 하지만 "
            "<b>그룹 자체가 비는 경우</b>(상관 서브쿼리, INNER JOIN 뒤)는 SUM 이 NULL 이고 "
            "안쪽 COALESCE 는 실행될 기회가 없다. "
            "<b>밖에 씌우는 쪽이 항상 안전하다.</b>",
            "<b>마지막 plan 을 <code>MAX(plan)</code> 로 바로 뽑으면 틀린다.</b> "
            "그건 '알파벳 순으로 가장 큰 plan' 이다 ('pro' &gt; 'basic'). "
            "'마지막 결제의 plan' 은 날짜로 찾아야 한다 — "
            "<code>paid_date = MAX(paid_date)</code> 로 재조인하거나 "
            "<code>ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY paid_date DESC)</code> "
            "로 1 번만 남긴다.",
            "<b><code>LIMIT</code> 은 정렬 뒤에 걸린다.</b> ORDER BY 를 빼고 LIMIT 만 쓰면 "
            "아무 20행이 나온다. 20번째와 21번째가 완전 동점이면 어느 쪽이 들어올지 "
            "정해지지 않으므로, 문제가 준 정렬 키를 <b>전부</b> 써야 한다.",
        ],
        "variants": "“결제 없는 유저를 맨 뒤로”면 "
                    "<code>ORDER BY (first_paid IS NULL), first_paid</code>. "
                    "“마지막 결제 금액까지”면 재조인에서 <code>MAX(lp.amount)</code> 를 "
                    "같이 가져온다. “N일 이상 결제 없는 유저”면 "
                    "<code>DATEDIFF(기준일, MAX(paid_date)) &gt;= N</code> 에 "
                    "<code>MAX(paid_date) IS NULL</code> 케이스를 따로 처리한다.",
    },
]

GUIDE = GUIDE + GUIDE_NULL
