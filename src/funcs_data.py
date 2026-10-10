# -*- coding: utf-8 -*-
"""함수 상세 레퍼런스.

demo 쿼리는 gen_funcs.py 가 실제로 실행해서 결과를 채운다.
손으로 쓴 예시 결과는 틀리기 쉬워서 쓰지 않는다.
"""

# key 는 패턴 지도에서 앵커로 연결된다
FUNCS = [

dict(key="over", name="OVER 절", group="기본",
  sig="함수(인자) OVER ( [PARTITION BY ...] [ORDER BY ...] [프레임] )",
  args=[
    ("PARTITION BY", "그룹을 나눈다. 그룹이 바뀌면 계산이 초기화된다.",
     "생략 → 전체가 한 덩어리"),
    ("ORDER BY", "그룹 안에서의 순서. 순위·LAG·누적에는 필수.",
     "생략 → 순서 없음. 순위 함수는 에러"),
    ("프레임", "ORDER BY 가 있을 때 계산 범위.",
     "생략 → 아래 '기본 프레임' 참고"),
  ],
  demo="""SELECT v,
  SUM(v) OVER ()                       AS 전체합,
  SUM(v) OVER (ORDER BY v)             AS 누적합,
  SUM(v) OVER (PARTITION BY g)         AS 그룹합
FROM (SELECT 'A' g, 10 v UNION ALL SELECT 'A',20
      UNION ALL SELECT 'B',30 UNION ALL SELECT 'B',40) t
ORDER BY v""",
  notes=[
    "<b>기본 프레임이 핵심이다.</b> ORDER BY 가 없으면 파티션 전체, "
    "있으면 <code>RANGE UNBOUNDED PRECEDING ~ CURRENT ROW</code>(누적)가 된다.",
    "전체 합을 원하면 <b>ORDER BY 를 빼야</b> 한다. 붙이는 순간 누적이 된다.",
    "<code>OVER ()</code> 처럼 괄호를 비우면 테이블 전체 기준.",
    "같은 OVER 를 여러 번 쓰면 <code>WINDOW w AS (...)</code> 로 이름을 붙일 수 있다.",
  ]),

dict(key="lag", name="LAG / LEAD", group="값 접근",
  sig="LAG(expr [, offset [, default]]) OVER ( [PARTITION BY ...] ORDER BY ... )",
  args=[
    ("expr", "가져올 값. 컬럼, 식, 집계 결과 모두 가능.", "필수"),
    ("offset", "몇 행 떨어진 값인가. <b>상수여야 한다</b>(컬럼 불가).", "생략 → <b>1</b>"),
    ("default", "범위를 벗어났을 때 돌려줄 값.", "생략 → <b>NULL</b>"),
    ("PARTITION BY", "그룹별로 따로 본다. 그룹 첫 행의 LAG 는 NULL.",
     "생략 → <b>전체를 한 줄로 이어 본다</b>(그룹 경계를 넘어감)"),
    ("ORDER BY", "'직전'을 정의하는 기준.", "<b>사실상 필수</b>. 없으면 결과가 들쭉날쭉"),
  ],
  demo="""SELECT u, d, v,
  LAG(v) OVER (PARTITION BY u ORDER BY d)    AS 전행_정상,
  LAG(v) OVER (ORDER BY u, d)                AS 전행_파티션없음,
  LAG(v, 2)    OVER (PARTITION BY u ORDER BY d) AS 두행전,
  LAG(v, 1, 0) OVER (PARTITION BY u ORDER BY d) AS 없으면0,
  LEAD(v)      OVER (PARTITION BY u ORDER BY d) AS 다음행
FROM (SELECT 'A' AS u, 1 AS d, 100 AS v UNION ALL SELECT 'A',2,130
      UNION ALL SELECT 'B',1,500 UNION ALL SELECT 'B',2,520) t
ORDER BY u, d""",
  notes=[
    "<b>ORDER BY 가 없으면 의미가 없다.</b> MySQL 은 에러를 내지 않고 "
    "아무 순서나 쓰므로 결과가 들쭉날쭉해진다. 반드시 넣는다.",
    "<b>PARTITION BY 를 빼먹으면 다른 그룹의 마지막 행을 끌어온다.</b> "
    "위 결과에서 B그룹 첫 행을 보라. 정상은 NULL 인데, 파티션이 없으면 "
    "A그룹의 130 이 넘어온다. 유저별·종목별 비교에서 가장 흔한 버그.",
    "<code>default</code> 를 0 으로 주면 증감 계산에서 첫 행이 "
    "<b>전체 증가</b>로 잡힌다. 보통은 NULL 로 두는 게 맞다.",
    "날짜 간격이 불규칙해도 LAG 는 <b>'직전 행'</b>을 준다. "
    "'직전 날짜'가 아니다. 주말·휴일이 있는 데이터에서는 이게 장점이다.",
    "offset 에 컬럼을 넣을 수 없다. 상수만 된다.",
  ]),

dict(key="rownum", name="ROW_NUMBER / RANK / DENSE_RANK", group="순위",
  sig="ROW_NUMBER() OVER ( [PARTITION BY ...] ORDER BY ... )   -- 괄호 안 인자 없음",
  args=[
    ("(인자 없음)", "세 함수 모두 괄호 안이 비어 있다.", "—"),
    ("ORDER BY", "순위의 기준.", "<b>필수</b>. 없으면 에러"),
    ("PARTITION BY", "그룹별로 순위를 다시 매긴다.", "생략 → 전체 통합 순위"),
  ],
  demo="""SELECT nm, score,
  ROW_NUMBER() OVER (ORDER BY score DESC) AS row_num,
  RANK()       OVER (ORDER BY score DESC) AS rnk,
  DENSE_RANK() OVER (ORDER BY score DESC) AS dense,
  NTILE(2)     OVER (ORDER BY score DESC) AS 절반,
  ROUND(PERCENT_RANK() OVER (ORDER BY score DESC),2) AS pct,
  ROUND(CUME_DIST()    OVER (ORDER BY score DESC),2) AS cume
FROM (SELECT 'A' AS nm, 90 AS score UNION ALL SELECT 'B',80
      UNION ALL SELECT 'C',80 UNION ALL SELECT 'D',70) t
ORDER BY score DESC, nm""",
  notes=[
    "<b>동점 처리가 전부 다르다.</b> ROW_NUMBER 1,2,3,4 / RANK 1,2,2,4 / DENSE_RANK 1,2,2,3.",
    "“1등 <b>한 명만</b>” → ROW_NUMBER = 1. “공동 1등 <b>전부</b>” → RANK = 1.",
    "ROW_NUMBER 는 동점일 때 <b>누가 먼저일지 보장되지 않는다.</b> "
    "재현성이 필요하면 <code>ORDER BY score DESC, id</code> 처럼 타이브레이커를 넣는다.",
    "<b>WHERE 에서 쓸 수 없다.</b> 서브쿼리로 감싸고 바깥 WHERE 에서 거른다.",
    "<code>NTILE(n)</code> 의 n 은 상수. 행이 n 으로 안 나뉘면 앞쪽 묶음이 1개씩 더 가진다.",
    "<code>PERCENT_RANK</code> = (rank−1)/(행수−1), 0 부터 시작. "
    "<code>CUME_DIST</code> = 나 이하 비율, 0 보다 크고 1 이하.",
  ]),

dict(key="aggover", name="SUM / AVG / COUNT + OVER", group="집계",
  sig="SUM(expr) OVER ( [PARTITION BY ...] [ORDER BY ...] [프레임] )",
  args=[
    ("expr", "집계 대상. <code>COUNT(*)</code> 는 행 수, <code>COUNT(컬럼)</code> 은 NULL 제외.", "필수"),
    ("ORDER BY", "붙이면 <b>누적</b>이 된다.", "생략 → 파티션 전체 합"),
    ("프레임", "범위를 직접 지정.", "아래 frame 항목 참고"),
  ],
  demo="""SELECT d, v,
  SUM(v)   OVER ()                                               AS 전체,
  SUM(v)   OVER (ORDER BY d)                                     AS 누적,
  AVG(v)   OVER (ORDER BY d ROWS BETWEEN 1 PRECEDING AND CURRENT ROW) AS 최근2평균,
  COUNT(*) OVER (ORDER BY d)                                     AS 누적행수,
  ROUND(100.0*v/SUM(v) OVER (),1)                                AS 비중
FROM (SELECT 1 d, 10 v UNION ALL SELECT 2,20
      UNION ALL SELECT 3,30 UNION ALL SELECT 4,40) t
ORDER BY d""",
  notes=[
    "<b>AVG 는 정수 컬럼이어도 소수를 돌려준다.</b> "
    "MySQL 은 원본 스케일+4자리 DECIMAL. 그래서 ROUND 를 따로 해야 한다.",
    "<code>SUM(x)/COUNT(*)</code> 로 평균을 직접 만들면 "
    "<b>엔진에 따라 정수 나눗셈</b>이 된다. AVG 를 쓰거나 <code>*1.0</code>.",
    "집계 함수는 <b>NULL 을 무시</b>한다. AVG 의 분모에서도 빠진다.",
    "<code>SUM</code> 은 대상 행이 없으면 0 이 아니라 <b>NULL</b> 을 반환한다. "
    "LEFT JOIN 뒤에는 COALESCE 로 감싼다.",
    "<b>집계 위에 윈도우를 겹칠 수 있다.</b> "
    "<code>MAX(SUM(x)) OVER (PARTITION BY a)</code> — GROUP BY 가 먼저 적용된다.",
  ]),

dict(key="frame", name="프레임 (ROWS / RANGE)", group="기본",
  sig="ROWS BETWEEN <시작> AND <끝>     /     RANGE BETWEEN <시작> AND <끝>",
  args=[
    ("UNBOUNDED PRECEDING", "파티션 맨 처음", ""),
    ("n PRECEDING", "ROWS: n행 앞 / RANGE: 값이 n 작은 지점", ""),
    ("CURRENT ROW", "현재 행(ROWS) 또는 현재 값(RANGE)", ""),
    ("n FOLLOWING", "n행 뒤", ""),
    ("UNBOUNDED FOLLOWING", "파티션 맨 끝", ""),
  ],
  demo="""SELECT v,
  COUNT(*) OVER (ORDER BY v ROWS  BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS rows_누적,
  COUNT(*) OVER (ORDER BY v RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS range_누적,
  AVG(v)   OVER (ORDER BY v ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)          AS 최근3평균
FROM (SELECT 10 v UNION ALL SELECT 20 UNION ALL
      SELECT 20 UNION ALL SELECT 30) t
ORDER BY v""",
  notes=[
    "<b>ROWS 는 행을 세고, RANGE 는 값을 센다.</b> 동점이 있으면 결과가 갈린다. "
    "위 예제에서 20 이 두 개라 rows_누적과 range_누적이 달라진다.",
    "<b>개수가 중요한 계산(이동평균, 최근 N건)은 반드시 ROWS.</b>",
    "<b>N일 이동평균의 프레임은 (N−1) PRECEDING</b> 이다. 당일이 포함되기 때문. "
    "5일 → 4 PRECEDING, 20일 → 19 PRECEDING.",
    "앞 행이 모자라면 <b>윈도우가 알아서 줄어든다.</b> "
    "부분 구간을 CASE 로 처리하려 하면 오히려 틀린다.",
    "<code>GROUPS</code> 프레임과 <code>EXCLUDE</code> 절은 <b>MySQL 8 이 지원하지 않는다</b>.",
  ]),

dict(key="firstval", name="FIRST_VALUE / LAST_VALUE / NTH_VALUE", group="값 접근",
  sig="FIRST_VALUE(expr) OVER ( [PARTITION BY ...] ORDER BY ... [프레임] )      NTH_VALUE(expr, n) OVER ( ... )",
  args=[
    ("expr", "가져올 값", "필수"),
    ("n", "<code>NTH_VALUE</code> 전용. 프레임 시작에서 n 번째. 상수.", "필수"),
    ("프레임", "<b>이 함수들은 프레임의 영향을 크게 받는다.</b>", "기본값 주의"),
  ],
  demo="""SELECT d, v,
  FIRST_VALUE(v) OVER (ORDER BY d) AS 첫값,
  LAST_VALUE(v)  OVER (ORDER BY d) AS 마지막값_함정,
  LAST_VALUE(v)  OVER (ORDER BY d
     ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS 마지막값_정답,
  FIRST_VALUE(v) OVER (ORDER BY d DESC) AS 마지막값_쉬운법
FROM (SELECT 1 d, 10 v UNION ALL SELECT 2,20
      UNION ALL SELECT 3,30) t
ORDER BY d""",
  notes=[
    "<b>LAST_VALUE 함정.</b> ORDER BY 만 쓰면 프레임이 '처음~현재'라서 "
    "LAST_VALUE 가 <b>항상 현재 행</b>이 된다. 위 예제의 '마지막값_함정' 열을 보라.",
    "제대로 쓰려면 프레임을 <code>UNBOUNDED FOLLOWING</code> 까지 열어야 한다.",
    "<b>더 쉬운 방법은 ORDER BY 를 뒤집고 FIRST_VALUE 를 쓰는 것.</b> "
    "FIRST_VALUE 는 프레임 시작이 늘 맨 앞이라 이 문제가 없다.",
    "MySQL 8 은 <code>IGNORE NULLS</code> 를 지원하지 않는다. "
    "NULL 을 건너뛰려면 서브쿼리에서 미리 걸러야 한다.",
  ]),

dict(key="countcase", name="COUNT / 조건부 집계", group="집계",
  sig="COUNT(*)   COUNT(expr)   COUNT(DISTINCT expr)   COUNT(CASE WHEN ... THEN x END)",
  args=[
    ("COUNT(*)", "모든 행. NULL 도 센다.", ""),
    ("COUNT(expr)", "<b>NULL 을 제외</b>하고 센다.", ""),
    ("COUNT(DISTINCT expr)", "중복 제거 후 센다. 조인으로 행이 불어났을 때 필수.", ""),
  ],
  demo="""SELECT
  COUNT(*)                                   AS 전체행,
  COUNT(v)                                   AS NULL제외,
  COUNT(DISTINCT v)                          AS 중복제거,
  SUM(CASE WHEN v >= 20 THEN 1 ELSE 0 END)   AS 조건건수_SUM,
  COUNT(CASE WHEN v >= 20 THEN 1 END)        AS 조건건수_COUNT,
  COUNT(CASE WHEN v >= 20 THEN 1 ELSE 0 END) AS 잘못된_ELSE0
FROM (SELECT 10 v UNION ALL SELECT 20 UNION ALL
      SELECT 20 UNION ALL SELECT NULL) t""",
  notes=[
    "<b>COUNT(*) 와 COUNT(컬럼) 의 차이로 분모 두 개를 만들 수 있다.</b> "
    "LEFT JOIN 후 <code>COUNT(*)</code>=전체, <code>COUNT(상대컬럼)</code>=매칭된 것.",
    "<b><code>COUNT(CASE ... ELSE 0 END)</code> 는 틀린다.</b> "
    "0 도 값이라 전부 세어진다. COUNT 와 쓸 때는 <b>ELSE 를 아예 쓰지 않는다</b>.",
    "<code>SUM(CASE ... THEN 1 ELSE 0 END)</code> 는 ELSE 0 이 <b>맞다</b>. "
    "COUNT 냐 SUM 이냐에 따라 ELSE 유무가 반대다.",
    "조인으로 행이 불어난 상태에서 <code>COUNT(DISTINCT user_id)</code> 를 안 쓰면 인원이 부풀려진다.",
  ]),

dict(key="nullfn", name="COALESCE / NULLIF / IFNULL", group="NULL",
  sig="COALESCE(a, b, c, ...)      NULLIF(a, b)      IFNULL(a, b)",
  args=[
    ("COALESCE", "첫 번째 비-NULL 을 반환. 인자 수 제한 없음. <b>표준 SQL</b>.", ""),
    ("NULLIF(a,b)", "a = b 이면 NULL, 아니면 a. <b>0 나누기 방어용</b>.", ""),
    ("IFNULL(a,b)", "COALESCE 의 2인자 버전. <b>MySQL 전용</b>.", ""),
  ],
  demo="""SELECT
  COALESCE(NULL, NULL, 3, 4) AS 첫비NULL,
  NULLIF(10, 10)             AS 같으면NULL,
  NULLIF(10, 5)              AS 다르면그대로,
  100 / NULLIF(0, 0)         AS 안전한나눗셈,
  COALESCE(NULL, 0)          AS NULL을0으로""",
  notes=[
    "<b>0 나누기 방어는 <code>NULLIF(분모, 0)</code>.</b> "
    "<code>IFNULL(분모, 0)</code> 은 정반대로 0 나누기를 <b>만든다</b>.",
    "<b>타입 함정.</b> COALESCE 의 반환 타입은 인자들의 공통 타입이다. "
    "숫자 컬럼에 <code>'없음'</code> 같은 문자를 넣으면 "
    "<b>컬럼 전체가 문자열</b>이 되어 정렬이 사전순으로 깨진다 ('9' &gt; '20').",
    "MySQL 은 이 변환을 <b>조용히</b> 한다. 에러가 안 나서 결과만 틀린다.",
    "표시만 문자로 하고 <b>정렬은 원본 컬럼</b>으로 하면 된다.",
    "<code>NULL = NULL</code> 은 TRUE 가 아니라 NULL. 판정은 <code>IS NULL</code>.",
    "MySQL 에 NVL 은 없다(Oracle 전용).",
  ]),

dict(key="datefn", name="날짜 함수", group="날짜",
  sig="DATE_FORMAT(d, fmt)   DATEDIFF(끝, 시작)   TIMESTAMPDIFF(단위, 시작, 끝)",
  args=[
    ("DATE_FORMAT(d, fmt)", "<code>%Y</code>4자리년 <code>%m</code>월 <code>%d</code>일 "
     "<code>%H</code>시 <code>%i</code>분 <code>%s</code>초", "문자열을 반환"),
    ("DATEDIFF(a, b)", "a − b 를 <b>일수</b>로. <b>끝이 먼저</b>.", ""),
    ("TIMESTAMPDIFF(u, a, b)", "b − a 를 단위 u 로. <b>시작이 먼저</b>. "
     "u = SECOND/MINUTE/HOUR/DAY/WEEK/MONTH/YEAR", ""),
    ("PERIOD_DIFF(p1, p2)", "YYYYMM 형식 두 개의 개월 차.", ""),
  ],
  demo="""SELECT
  DATE_FORMAT(DATE '2026-03-15','%Y-%m')      AS 연월,
  DATE_FORMAT(DATE '2026-03-15','%Y-%m-01')   AS 월첫날,
  DATEDIFF(DATE '2026-03-15', DATE '2026-03-01')        AS 일수_끝먼저,
  TIMESTAMPDIFF(DAY, DATE '2026-03-01', DATE '2026-03-15') AS 일수_시작먼저,
  TIMESTAMPDIFF(MONTH, DATE '2026-01-15', DATE '2026-03-15') AS 개월수,
  DATE_ADD(DATE '2026-03-15', INTERVAL 30 DAY) AS 더하기,
  LAST_DAY(DATE '2026-02-10')                  AS 그달마지막날""",
  notes=[
    "<b>DATEDIFF 와 TIMESTAMPDIFF 는 인자 순서가 반대다.</b> "
    "시험장에서 가장 많이 헷갈리는 지점. 외우지 말고 적어 두라.",
    "<code>INTERVAL</code> 뒤에는 <b>따옴표가 없다</b>. "
    "<code>INTERVAL 30 DAY</code> 이지 <code>INTERVAL '30' DAY</code> 가 아니다.",
    "<b>월 단위로 묶을 때는 <code>'%Y-%m-01'</code>(월 첫날)로 만들어 정렬</b>하고, "
    "출력만 <code>'%Y-%m'</code> 으로 한다. 문자열 정렬은 10월이 1월 뒤로 가기도 한다.",
    "<b>'직전 거래일'을 날짜 뺄셈으로 찾으면 안 된다.</b> "
    "주말·공휴일이 비어 있으면 매칭이 통째로 실패한다. LAG 를 쓴다.",
  ]),

dict(key="median", name="중앙값 만들기 (MEDIAN 대체)", group="응용",
  sig="ROW_NUMBER() + COUNT() OVER 조합",
  args=[
    ("왜 필요한가", "MySQL 8 에는 MEDIAN 도 PERCENTILE_CONT 도 없다.", ""),
  ],
  demo="""WITH r AS (
  SELECT g, v,
         ROW_NUMBER() OVER (PARTITION BY g ORDER BY v) AS rn,
         COUNT(*)     OVER (PARTITION BY g)            AS cnt
  FROM (SELECT 'A' g, 10 v UNION ALL SELECT 'A',20 UNION ALL
        SELECT 'A',30 UNION ALL SELECT 'A',40 UNION ALL
        SELECT 'B',5  UNION ALL SELECT 'B',7 UNION ALL SELECT 'B',100) t
)
SELECT g, MAX(cnt) AS n, AVG(v) AS median
FROM r
WHERE rn IN (FLOOR((cnt+1)/2), FLOOR((cnt+2)/2))
GROUP BY g ORDER BY g""",
  notes=[
    "<b>두 자리를 잡는 게 핵심.</b> <code>FLOOR((cnt+1)/2)</code> 와 "
    "<code>FLOOR((cnt+2)/2)</code> 는 홀수면 같은 값, 짝수면 가운데 두 개가 된다.",
    "그래서 <b>AVG 로 감싸면 홀짝을 분기할 필요가 없다.</b>",
    "A 그룹(4개, 짝수)은 20·30 의 평균 25, B 그룹(3개, 홀수)은 7 이 나온다.",
    "인원수는 <code>COUNT(*)</code> 가 아니라 <code>MAX(cnt)</code>. "
    "WHERE 로 이미 1~2행만 남았기 때문.",
  ]),

dict(key="islands", name="연속 구간 (gaps and islands)", group="응용",
  sig="일련번호 − ROW_NUMBER() → 같은 값이 연속 구간",
  args=[
    ("일련번호", "날짜·월을 정수로 바꾼 값. "
     "<code>TIMESTAMPDIFF(MONTH, 기준일, m)</code> 또는 <code>DATEDIFF</code>", ""),
    ("ROW_NUMBER()", "그룹 안에서 순서대로 1,2,3…", ""),
  ],
  demo="""WITH s AS (
  SELECT u, m, m - ROW_NUMBER() OVER (PARTITION BY u ORDER BY m) AS grp
  FROM (SELECT 1 u, 1 m UNION ALL SELECT 1,2 UNION ALL SELECT 1,3
        UNION ALL SELECT 1,6 UNION ALL
        SELECT 2,1 UNION ALL SELECT 2,3) t
)
SELECT u, grp, MIN(m) AS 시작, MAX(m) AS 끝, COUNT(*) AS 연속길이
FROM s GROUP BY u, grp ORDER BY u, 시작""",
  notes=[
    "<b>원리.</b> 연속이면 일련번호와 행번호가 같은 보폭으로 늘어 차이가 고정된다. "
    "끊기면 차이가 점프한다.<br>"
    "<code>1,2,3 → 1,2,3 빼면 0,0,0</code> (같은 구간)<br>"
    "<code>1,3 → 1,2 빼면 0,1</code> (다른 구간)",
    "<b>중복 제거를 먼저</b> 해야 한다. 같은 달에 두 번 결제한 행이 남아 있으면 깨진다.",
    "마지막에 유저 수를 셀 때 <code>COUNT(DISTINCT user_id)</code>. "
    "한 유저가 연속 구간을 여러 개 가질 수 있다.",
    "일 단위면 <code>DATEDIFF(d, '기준일')</code> 을 일련번호로 쓴다.",
  ]),

dict(key="dedupe", name="그룹별 1건만 남기기", group="응용",
  sig="ROW_NUMBER() OVER (PARTITION BY 키 ORDER BY 정렬) = 1",
  args=[
    ("PARTITION BY", "무엇 기준으로 1건인가 (유저별, 종목별...)", ""),
    ("ORDER BY", "어느 것을 남길 것인가 (최신이면 DESC)", ""),
  ],
  demo="""SELECT u, d, v FROM (
  SELECT u, d, v, ROW_NUMBER() OVER (PARTITION BY u ORDER BY d DESC) AS rn
  FROM (SELECT 1 u, 1 d, 'old' v UNION ALL SELECT 1,3,'new'
        UNION ALL SELECT 2,2,'only') t
) x WHERE rn = 1 ORDER BY u""",
  notes=[
    "<b>WHERE 에서 윈도우 함수를 쓸 수 없으므로</b> 반드시 서브쿼리나 CTE 로 감싼다. "
    "MySQL 에는 QUALIFY 가 없다.",
    "동점이 있으면 어느 행이 남을지 보장되지 않는다. "
    "<code>ORDER BY d DESC, id</code> 처럼 타이브레이커를 넣으면 결과가 고정된다.",
    "“공동 1등 모두”가 필요하면 ROW_NUMBER 대신 <code>RANK() = 1</code>.",
  ]),
]

# ── NULL 함수 심화 (실제로 두 엔진에서 돌려 확인한 값만 적었다) ──────────
NULL_DEEP = {
    "key": "nulldeep",
    "name": "NULL 심화 — 집계·정렬·IN·타입",
    "group": "NULL",
    "sig": "COALESCE(a,b,...)  ·  NULLIF(a,b)  ·  IFNULL(a,b)  ·  x IS [NOT] NULL",
    "args": [
        ("COALESCE(a,b,c,…)",
         "앞에서부터 처음 만나는 <b>NULL 아닌</b> 값. 인자 수 제한 없음. "
         "<b>표준 SQL — 어느 DB 에서나 된다.</b> 이것만 쓰면 된다.", ""),
        ("NULLIF(a,b)",
         "a 와 b 가 <b>같으면 NULL</b>, 다르면 a. 이름이 헷갈리지만 "
         "'a 가 b 면 NULL 로 만들어라' 는 뜻이다. 0 나누기 방어 전용.", ""),
        ("IFNULL(a,b)",
         "COALESCE 의 2인자 버전. <b>MySQL·SQLite 전용.</b> "
         "PostgreSQL·MS SQL 에 없다. 쓸 이유가 없다.", ""),
        ("NVL / ISNULL",
         "NVL 은 Oracle 전용. ISNULL 은 <b>MS SQL 에서는 ISNULL(a,b) 2인자 대체</b>, "
         "<b>MySQL 에서는 ISNULL(x) 1인자 참/거짓</b> — 이름만 같고 다른 함수다. "
         "둘 다 쓰지 마라.", ""),
        ("x IS NULL / IS NOT NULL",
         "NULL 판정은 <b>이것뿐이다.</b> <code>x = NULL</code> 은 참이 아니라 NULL 이라 "
         "WHERE 에서 항상 걸러진다.", ""),
    ],
    "demo": """-- 1) 집계 함수의 빈 입력 반환값 (틀리면 Q14 처럼 행 수가 어긋난다)
SELECT COUNT(*)  AS cnt_star,   -- 0
       COUNT(x)  AS cnt_col,    -- 0
       SUM(x)    AS sum_x,      -- NULL  ← 0 이 아니다
       AVG(x)    AS avg_x,      -- NULL
       MAX(x)    AS max_x       -- NULL
FROM (SELECT 1 AS x) WHERE 1 = 0;

-- 2) AVG 의 분모는 '행 수' 가 아니라 'NULL 아닌 값의 수' 다
--    x = 10, NULL, 20  →  AVG = 15,  SUM/COUNT(*) = 10
SELECT AVG(x)                  AS avg_x,
       SUM(x) * 1.0 / COUNT(*) AS sum_over_rows,
       COUNT(x)                AS non_null_cnt
FROM t;

-- 3) NOT IN 에 NULL 이 하나라도 있으면 결과가 전부 사라진다
SELECT 5 WHERE 5 NOT IN (1, 2, NULL);   -- 0행
SELECT 5 WHERE 5 IN (5, NULL);          -- 1행 (IN 은 괜찮다)

-- 4) 0 나누기 방어
SELECT 100.0 / NULLIF(0, 0);            -- NULL (안전)""",
    "notes": [
        "<b>철자를 틀리면 그냥 문법 오류다.</b> C-O-A-L-E-S-C-E. "
        "COALECSE, COALEASE, COALSCE 다 틀린 철자다. "
        "시험장에서 빨간 줄이 안 뜨니 눈으로 확인해야 한다.",

        "<b>집계 함수의 빈 입력 반환값 — 이게 가장 자주 틀리는 부분이다.</b><br>"
        "<code>COUNT</code> 는 <b>0</b>, <code>SUM·AVG·MAX·MIN</code> 은 <b>NULL</b>. "
        "그래서 LEFT JOIN 뒤에 금액을 0 으로 보이고 싶으면 "
        "<code>COALESCE(SUM(amount), 0)</code> 이 필요하다. "
        "<b>COALESCE 를 SUM 안에 넣을지 밖에 씌울지는 '그룹이 빌 수 있는가' 로 갈린다.</b><br>"
        "<code>LEFT JOIN + GROUP BY 왼쪽테이블</code> 이면 그룹마다 최소 한 행(NULL 행)이 "
        "남으므로 <code>SUM(COALESCE(amount,0))</code> 도 0 이 나온다.<br>"
        "하지만 <b>그룹 자체가 비는 경우</b> — 상관 서브쿼리 "
        "<code>(SELECT SUM(amount) FROM payments WHERE user_id=u.user_id)</code> 나 "
        "INNER JOIN 뒤 — 는 행이 0개라 <b>SUM 이 NULL</b> 이고 안쪽 COALESCE 는 "
        "실행될 기회조차 없다.<br>"
        "<b>밖에 씌우는 쪽이 항상 안전하다</b>: <code>COALESCE(SUM(amount), 0)</code>.",

        "<b>AVG 는 NULL 을 분모에서도 뺀다.</b> 값이 10, NULL, 20 이면 AVG 는 "
        "(10+20)/2 = <b>15</b> 이지 (10+20)/3 = 10 이 아니다. "
        "'결제 안 한 사람을 0 으로 치고 평균' 을 원하면 "
        "<code>AVG(COALESCE(amount, 0))</code> 처럼 <b>먼저 채워야</b> 한다. "
        "ARPU 와 ARPPU 가 갈리는 지점이 정확히 여기다.",

        "<b>NOT IN + NULL = 전멸.</b> 서브쿼리 결과에 NULL 이 하나라도 섞이면 "
        "<code>WHERE id NOT IN (SELECT ...)</code> 가 <b>0행</b>을 돌려준다. "
        "<code>5 NOT IN (1,2,NULL)</code> 은 '5≠1 AND 5≠2 AND 5≠NULL' 이고 "
        "마지막이 NULL 이라 전체가 NULL(거짓 취급)이 된다. "
        "<b>NOT IN 대신 NOT EXISTS 나 LEFT JOIN … IS NULL 을 써라.</b> "
        "<code>IN</code> 은 반대로 멀쩡하다 (하나만 맞으면 참).<br>"
        "<b>NOT EXISTS 는 NULL 에 면역이다.</b> "
        "<code>NOT EXISTS (SELECT 1 FROM p WHERE p.user_id = u.user_id)</code> 에서 "
        "p.user_id 가 NULL 인 행은 비교가 NULL → 매칭 실패 → 자동으로 무시된다. "
        "<code>IS NOT NULL</code> 을 따로 안 써도 맞는 답이 나온다. "
        "그래서 '존재하지 않는 것 찾기' 는 NOT EXISTS 를 기본값으로 삼아라.",

        "<b>정렬에서 NULL 의 위치 — 엔진마다 다르다.</b> 실제로 돌려 본 결과:<br>"
        "<code>MySQL·SQLite</code> : NULL 을 가장 작은 값으로 본다 → "
        "<b>ASC 면 맨 앞, DESC 면 맨 뒤</b><br>"
        "<code>PostgreSQL·DuckDB</code> : 기본이 NULLS LAST → <b>ASC 에서도 맨 뒤</b><br>"
        "그래서 <b>정렬 컬럼에 NULL 이 있을 수 있으면 직접 정해 줘라</b>: "
        "<code>ORDER BY (금액 IS NULL), 금액 DESC</code> — "
        "<code>IS NULL</code> 은 0/1 이라 이걸 첫 키로 쓰면 NULL 을 뒤로 밀 수 있다. "
        "MySQL 의 <code>ORDER BY 금액 IS NULL, 금액</code> 도 같은 뜻이다 "
        "(<code>NULLS LAST</code> 문법은 MySQL 에 없다).",

        "<b>타입 승격 함정 — 형님이 말한 '데이터 타입 문제' 가 이것이다.</b> "
        "COALESCE 의 반환 타입은 <b>인자들의 공통 타입</b>이다. "
        "<code>COALESCE(금액, '없음')</code> 처럼 숫자에 문자를 섞으면 "
        "<b>컬럼 전체가 문자열</b>이 되고, 그 뒤 정렬이 사전순으로 깨진다 "
        "(<code>'9' &gt; '20'</code>). MySQL·SQLite 는 이 변환을 "
        "<b>오류 없이 조용히</b> 하고, PostgreSQL·DuckDB 는 오류를 낸다. "
        "해결: <b>보여 주는 값과 정렬하는 값을 분리</b>해서 "
        "<code>SELECT COALESCE(CAST(금액 AS CHAR), '없음') … ORDER BY (금액 IS NULL), 금액</code>.",

        "<b>0 과 NULL 은 다른 뜻이다.</b> 0 은 '거래했고 금액이 0', "
        "NULL 은 '거래 기록이 없음' 이다. LEFT JOIN 뒤에 어느 쪽으로 채울지는 "
        "비즈니스 판단이고, 문제에 명시돼 있다. "
        "A/B 테스트의 분모처럼 <b>'참가했지만 행동 안 함' 을 0 으로 세야 하는 경우</b>가 "
        "많으니 문제를 다시 읽어라.",

        "<b>0 으로 나눈 결과도 엔진마다 다르다.</b> 실측: "
        "<code>SQLite·MySQL → NULL</code>, <code>DuckDB → inf</code>, "
        "<code>PostgreSQL·MS SQL → 오류</code>. "
        "즉 시험 환경에서는 <code>NULLIF</code> 없이도 NULL 이 나와 통과할 수 있지만, "
        "습관을 안 들이면 다른 환경에서 쿼리가 터진다.",

        "<b>NULL 은 GROUP BY 에서 하나의 그룹이 되고, COUNT(DISTINCT) 에서는 안 세어진다.</b> "
        "<code>GROUP BY channel</code> 에 channel 이 NULL 인 행들은 "
        "모여서 NULL 그룹 한 줄이 된다. 반면 "
        "<code>COUNT(DISTINCT x)</code> 는 NULL 을 빼고 센다 "
        "(NULL, NULL, 1 → <b>1</b>).",

        "<b>문자열 연결에 NULL 이 끼면 전체가 NULL 이다.</b> "
        "<code>'a' || NULL</code> → NULL. MySQL <code>CONCAT</code> 도 같다. "
        "<code>CONCAT_WS</code> 는 NULL 을 건너뛴다. "
        "이름 조합 같은 걸 만들 때 <code>COALESCE(미들네임, '')</code> 로 먼저 채워라.",

        "<b>NULLIF 와 IFNULL 을 바꿔 쓰면 정반대가 된다.</b> "
        "<code>NULLIF(분모, 0)</code> 은 0 을 NULL 로 만들어 나눗셈을 방어하고, "
        "<code>IFNULL(분모, 0)</code> 은 NULL 을 0 으로 만들어 <b>0 나누기를 일부러 만든다.</b>",
    ],
}

FUNCS = FUNCS + [NULL_DEEP] if isinstance(FUNCS, list) else FUNCS
