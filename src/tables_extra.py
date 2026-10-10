# -*- coding: utf-8 -*-
"""추가 문항(Q16~Q20)용 테이블.

기존 4개 테이블(users/events/payments/prices)과 따로 둔다. 이유가 있다.
실제 시험은 처음 보는 테이블 이름과 컬럼 이름을 내놓는다. 늘 같은 스키마로만
연습하면 '어느 테이블에 뭐가 있는지' 를 외워서 푸는 습관이 생기고, 시험장에서
스키마를 읽는 데 시간을 다 쓴다. 그래서 문제에 적힌 이름을 그대로 쓴다.

데이터는 일부러 '틀린 쿼리가 틀리게 나오도록' 심어 둔다.
  · 하루에 여러 건 → DISTINCT 안 쓰면 연속일수가 부풀어 오른다
  · CANCELLED 만 있는 날 → status 필터 안 하면 연속 구간이 이어져 버린다
  · 거래 없는 실험 참가자 → LEFT JOIN + COALESCE 안 하면 유저 수가 깎인다
  · created_at 에 시각이 붙어 있음 → DATE 로 안 자르면 일자 집계가 깨진다
"""
import random
from datetime import date, datetime, timedelta

# ── 스키마 (화면 표시용) ─────────────────────────────────────────────────
SCHEMA_EXTRA = [
    {
        "name": "user_event_logs",
        "cols": [("event_id", "bigint"), ("user_id", "int"),
                 ("event_name", "varchar"), ("created_at", "datetime")],
        "notes": [
            "event_id 가 기본 키입니다.",
            "event_name 은 'app_open', 'item_view', 'add_to_cart', 'purchase' 중 하나입니다.",
            "한 유저가 같은 행동을 여러 번 남깁니다. 유저 수를 셀 때는 중복을 지워야 합니다.",
            "created_at 에는 시각까지 들어 있습니다 (예: 2026-02-03 14:27:11).",
        ],
    },
    {
        "name": "first_trades",
        "cols": [("user_id", "int"), ("first_trade_date", "date")],
        "notes": [
            "user_id 가 기본 키입니다. 유저당 한 행입니다.",
            "first_trade_date 는 2026-01-25 ~ 2026-02-14 범위입니다.",
        ],
    },
    {
        "name": "daily_app_visits",
        "cols": [("user_id", "int"), ("visit_date", "date")],
        "notes": [
            "기본 키가 없습니다. 같은 유저가 같은 날 여러 행을 남길 수 있습니다.",
            "앱을 연 날만 행이 있습니다. 안 연 날은 행이 없습니다.",
        ],
    },
    {
        "name": "stock_orders",
        "cols": [("order_id", "bigint"), ("user_id", "int"),
                 ("order_date", "date"), ("status", "varchar")],
        "notes": [
            "order_id 가 기본 키입니다.",
            "status 는 'COMPLETED' 또는 'CANCELLED' 입니다.",
            "한 유저가 하루에 여러 건 주문할 수 있습니다.",
            "주문이 있어도 전부 CANCELLED 인 날이 있습니다.",
        ],
    },
    {
        "name": "experiment_users",
        "cols": [("user_id", "int"), ("group_name", "varchar")],
        "notes": [
            "user_id 가 기본 키입니다.",
            "group_name 은 'A_Control' 또는 'B_Variant' 입니다.",
            "실험에 참가했지만 거래가 한 건도 없는 유저가 있습니다.",
        ],
    },
    {
        "name": "user_trades_summary",
        "cols": [("user_id", "int"), ("total_trading_amount", "decimal(18,2)")],
        "notes": [
            "user_id 가 기본 키입니다.",
            "실험 기간 동안의 총 거래 금액입니다.",
            "experiment_users 에 있지만 여기 없는 유저가 있습니다.",
        ],
    },
    {
        "name": "stock_daily_prices",
        "cols": [("stock_code", "varchar"), ("trade_date", "date"),
                 ("close_price", "int")],
        "notes": [
            "(stock_code, trade_date) 조합이 유일합니다.",
            "영업일(월~금)만 들어 있습니다. 주말 행은 없습니다.",
            "전 거래일은 '하루 전' 이 아니라 '데이터상 바로 앞 행' 입니다.",
            "종목은 '005930', '000660', '035720' 세 개입니다.",
        ],
    },
]

COLS = {
    "user_event_logs": ["event_id", "user_id", "event_name", "created_at"],
    "first_trades": ["user_id", "first_trade_date"],
    "daily_app_visits": ["user_id", "visit_date"],
    "stock_orders": ["order_id", "user_id", "order_date", "status"],
    "experiment_users": ["user_id", "group_name"],
    "user_trades_summary": ["user_id", "total_trading_amount"],
    "stock_daily_prices": ["stock_code", "trade_date", "close_price"],
}

DDL_DUCK = {
    "user_event_logs": "event_id BIGINT, user_id INTEGER, event_name VARCHAR, created_at TIMESTAMP",
    "first_trades": "user_id INTEGER, first_trade_date DATE",
    "daily_app_visits": "user_id INTEGER, visit_date DATE",
    "stock_orders": "order_id BIGINT, user_id INTEGER, order_date DATE, status VARCHAR",
    "experiment_users": "user_id INTEGER, group_name VARCHAR",
    "user_trades_summary": "user_id INTEGER, total_trading_amount DECIMAL(18,2)",
    "stock_daily_prices": "stock_code VARCHAR, trade_date DATE, close_price INTEGER",
}

DDL_SQLITE = {
    "user_event_logs": "event_id INTEGER, user_id INTEGER, event_name TEXT, created_at TEXT",
    "first_trades": "user_id INTEGER, first_trade_date TEXT",
    "daily_app_visits": "user_id INTEGER, visit_date TEXT",
    "stock_orders": "order_id INTEGER, user_id INTEGER, order_date TEXT, status TEXT",
    "experiment_users": "user_id INTEGER, group_name TEXT",
    "user_trades_summary": "user_id INTEGER, total_trading_amount REAL",
    "stock_daily_prices": "stock_code TEXT, trade_date TEXT, close_price INTEGER",
}


# ── 데이터 생성 ────────────────────────────────────────────────────────
def _biz(a, b):
    d = a
    while d <= b:
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


def generate(seed=20261010):
    """7개 테이블의 행을 만들어 돌려준다. {테이블: [행...]}"""
    rnd = random.Random(seed)
    out = {}

    # 1) user_event_logs — 퍼널. 단계마다 줄어든다
    logs = []
    eid = 1
    feb = date(2026, 2, 1)
    for uid in range(1, 3001):
        if rnd.random() > 0.95:
            continue
        def stamp():
            d = feb + timedelta(days=rnd.randint(0, 27))
            return datetime(d.year, d.month, d.day,
                            rnd.randint(0, 23), rnd.randint(0, 59), rnd.randint(0, 59))
        for _ in range(rnd.randint(1, 4)):
            logs.append((eid, uid, "app_open", stamp())); eid += 1
        if rnd.random() > 0.66:
            continue
        for _ in range(rnd.randint(1, 6)):
            logs.append((eid, uid, "item_view", stamp())); eid += 1
        if rnd.random() > 0.45:
            continue
        for _ in range(rnd.randint(1, 3)):
            logs.append((eid, uid, "add_to_cart", stamp())); eid += 1
        if rnd.random() > 0.38:
            continue
        for _ in range(rnd.randint(1, 2)):
            logs.append((eid, uid, "purchase", stamp())); eid += 1
    out["user_event_logs"] = logs

    # 2) first_trades / daily_app_visits — D7 리텐션
    # 코호트 범위(2/1~2/7) 밖의 날짜도 넣는다. 범위 필터를 빼먹으면 틀리게 나온다.
    ft, visits = [], []
    uid = 1
    for d in [date(2026, 1, 25) + timedelta(days=k) for k in range(21)]:
        n = rnd.randint(55, 130) if date(2026, 2, 1) <= d <= date(2026, 2, 7) else rnd.randint(20, 60)
        # 코호트 날짜마다 D7 재방문율을 다르게 둔다 → 날짜별 차이가 보여야 한다
        d7 = 0.22 + 0.05 * (d.day % 7)
        for _ in range(n):
            ft.append((uid, d))
            # 평소 방문 (D7 과 무관한 잡음)
            for _ in range(rnd.randint(0, 5)):
                visits.append((uid, d + timedelta(days=rnd.randint(0, 20))))
            if rnd.random() < d7:
                # 같은 날 중복 방문 → DISTINCT 안 쓰면 100% 를 넘는 비율이 나온다
                for _ in range(rnd.randint(1, 3)):
                    visits.append((uid, d + timedelta(days=7)))
            uid += 1
    out["first_trades"] = ft
    out["daily_app_visits"] = visits

    # 3) stock_orders — 연속 거래일수
    orders, oid = [], 1
    for u in range(1, 1201):
        d = date(2026, 3, 2) + timedelta(days=rnd.randint(0, 40))
        for _ in range(rnd.randint(1, 4)):                 # 구간 몇 개
            run = rnd.choice([1, 1, 2, 2, 3, 3, 4, 5, 6])
            for k in range(run):
                day = d + timedelta(days=k)
                # 10% 는 그 날 주문이 전부 취소된다 → 연속이 끊겨야 한다
                all_cancel = rnd.random() < 0.10
                for _ in range(rnd.randint(1, 3)):
                    st = "CANCELLED" if all_cancel or rnd.random() < 0.12 else "COMPLETED"
                    orders.append((oid, u, day, st)); oid += 1
            d += timedelta(days=run + rnd.randint(2, 9))   # 구간 사이는 비운다
    out["stock_orders"] = orders

    # 4) experiment_users / user_trades_summary — A/B
    eu, uts = [], []
    for u in range(1, 2001):
        eu.append((u, "A_Control" if u % 2 == 0 else "B_Variant"))
        if rnd.random() < 0.12:
            continue                                      # 거래 없는 참가자
        amt = round(rnd.lognormvariate(11.4, 0.85), 2)
        if rnd.random() < 0.012:
            amt = round(amt * rnd.uniform(25, 90), 2)     # 극단 이상치
        uts.append((u, amt))
    out["experiment_users"] = eu
    out["user_trades_summary"] = uts

    # 5) stock_daily_prices — 3일 이상 연속 상승 구간
    px_rows = []
    for code, base, drift, vol in [("005930", 72000, 25, 700),
                                   ("000660", 131000, 60, 1800),
                                   ("035720", 48000, -10, 600)]:
        px = float(base)
        for d in _biz(date(2026, 1, 1), date(2026, 6, 30)):
            px = max(1000.0, px + drift + rnd.gauss(0, vol))
            px_rows.append((code, d, int(round(px, -1))))
    out["stock_daily_prices"] = px_rows
    return out


def create(con, rows=None, ddl=None, as_text=False):
    """duckdb/sqlite 연결에 테이블을 만들고 행을 넣는다."""
    ddl = ddl or (DDL_SQLITE if as_text else DDL_DUCK)
    rows = rows if rows is not None else generate()
    # 한 행씩 커밋하면 파일 DB 에서 몇 분이 걸린다. 한 트랜잭션으로 묶는다.
    try:
        con.execute("BEGIN TRANSACTION")
    except Exception:
        pass
    for name, decl in ddl.items():
        con.execute("CREATE TABLE %s (%s)" % (name, decl))
        data = rows.get(name) or []
        if not data:
            continue
        if as_text:
            data = [tuple(v.isoformat(sep=" ") if isinstance(v, datetime)
                          else (v.isoformat() if hasattr(v, "isoformat") else v)
                          for v in r) for r in data]
        con.executemany("INSERT INTO %s VALUES (%s)"
                        % (name, ",".join(["?"] * len(COLS[name]))), data)
    try:
        con.execute("COMMIT")
    except Exception:
        pass
    return rows
