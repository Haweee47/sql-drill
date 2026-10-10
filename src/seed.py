# -*- coding: utf-8 -*-
"""토스 사전 쿼리 테스트 대비 — 연습용 데이터 생성.

FP&A 직무이므로 유저 행동과 결제가 함께 있는 구조로 만든다.
실제 테스트에서 자주 나오는 것들이 전부 계산 가능하도록 설계했다.
  · 월별 리텐션 / 코호트
  · 퍼널 전환율
  · 매출 분해(신규·기존·이탈·복귀)
  · 윈도우 함수(누적, 전월 대비, 순위)

규모는 일부러 작게 잡았다(유저 3,000명). 쿼리 결과를 눈으로 검산할 수 있어야
틀린 쿼리를 잡아낼 수 있다.
"""
import os
import random
from datetime import date, timedelta

import duckdb

import tables_extra as TX

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "practice.duckdb")

random.seed(20261007)
START = date(2026, 1, 1)
END = date(2026, 9, 30)

CHANNELS = ["organic", "paid_search", "sns", "referral"]
PLANS = ["free", "basic", "pro"]
PRICE = {"free": 0, "basic": 9900, "pro": 29900}
STEPS = ["view_landing", "signup_start", "signup_done", "kyc_done", "first_payment"]


def daterange(a, b):
    d = a
    while d <= b:
        yield d
        d += timedelta(days=1)


def build():
    if os.path.exists(DB):
        os.remove(DB)
    con = duckdb.connect(DB)

    # ── users ────────────────────────────────────────────────────────────
    users = []
    for uid in range(1, 3001):
        signup = START + timedelta(days=random.randint(0, (END - START).days - 20))
        ch = random.choices(CHANNELS, weights=[40, 25, 25, 10])[0]
        age = random.choices([20, 30, 40, 50], weights=[30, 40, 20, 10])[0] + random.randint(0, 9)
        users.append((uid, signup, ch, age,
                      random.choices(["M", "F"], weights=[52, 48])[0]))
    con.execute("""CREATE TABLE users(
        user_id INTEGER, signup_date DATE, channel VARCHAR, age INTEGER, gender VARCHAR)""")
    con.executemany("INSERT INTO users VALUES (?,?,?,?,?)", users)

    # ── events (퍼널 + 접속 로그) ─────────────────────────────────────────
    events = []
    # 채널별로 퍼널 통과율을 다르게 둔다 → 퍼널 문제에서 차이가 보여야 한다
    pass_rate = {"organic": 0.82, "paid_search": 0.70, "sns": 0.62, "referral": 0.88}
    for uid, signup, ch, age, g in users:
        p = pass_rate[ch]
        reached = 0
        for i, step in enumerate(STEPS):
            if i > 0 and random.random() > p:
                break
            events.append((uid, step, signup + timedelta(days=i // 2), ch))
            reached = i
        # 접속 로그: 리텐션 계산용. 가입 후 이탈 확률이 점점 커진다
        if reached >= 2:
            alive = True
            d = signup
            while alive and d <= END:
                if random.random() < 0.45:
                    events.append((uid, "app_open", d, ch))
                d += timedelta(days=random.randint(1, 6))
                if random.random() < 0.055:
                    alive = False
    con.execute("""CREATE TABLE events(
        user_id INTEGER, event_name VARCHAR, event_date DATE, channel VARCHAR)""")
    con.executemany("INSERT INTO events VALUES (?,?,?,?)", events)

    # ── subscriptions / payments ────────────────────────────────────────
    pays = []
    paid_users = [u for u in users if random.random() < 0.38]
    for uid, signup, ch, age, g in paid_users:
        plan = random.choices(PLANS[1:], weights=[65, 35])[0]
        # 첫 결제까지 걸리는 기간을 넓게 둔다. 좁으면 '30일 이내' 같은 조건이
        # 아무것도 걸러내지 못해 조건을 빼먹은 쿼리도 정답이 되어 버린다.
        d = signup + timedelta(days=random.choice(
            [random.randint(1, 25)] * 6 + [random.randint(26, 90)] * 4))
        churned = False
        while d <= END and not churned:
            # 업그레이드 / 다운그레이드가 섞여 있어야 매출 분해 문제가 성립한다
            r = random.random()
            if r < 0.05 and plan == "basic":
                plan = "pro"
            elif r < 0.08 and plan == "pro":
                plan = "basic"
            pays.append((uid, d, plan, PRICE[plan]))
            if random.random() < 0.09:
                churned = True
                # 일부는 몇 달 뒤 복귀한다 → 복귀 매출 문제용
                if random.random() < 0.35:
                    back = d + timedelta(days=random.randint(60, 120))
                    if back <= END:
                        d, churned = back, False
                        continue
            d += timedelta(days=30)
    con.execute("""CREATE TABLE payments(
        user_id INTEGER, paid_date DATE, plan VARCHAR, amount INTEGER)""")
    con.executemany("INSERT INTO payments VALUES (?,?,?,?)", pays)

    # ── prices (일별 종가) ───────────────────────────────────────────────
    # 이동평균·골든크로스 문제용. 영업일(월~금)만 만든다.
    prices = []
    for code, base, drift, vol in [("005930", 72000, 18, 900),
                                   ("000660", 131000, 55, 2300),
                                   ("035720", 48000, -12, 700)]:
        px = float(base)
        for d in daterange(START, END):
            if d.weekday() >= 5:
                continue
            px = max(1000.0, px + drift + random.gauss(0, vol))
            prices.append((code, d, int(round(px, -1))))
    con.execute("""CREATE TABLE prices(
        stock_code VARCHAR, trade_date DATE, close_price INTEGER)""")
    con.executemany("INSERT INTO prices VALUES (?,?,?)", prices)

    extra = TX.create(con)
    for n in TX.DDL_DUCK:
        print("%-22s %6d" % (n, len(extra.get(n) or [])))

    print("users      %5d" % len(users))
    print("events     %5d" % len(events))
    print("payments   %5d" % len(pays))
    print("prices     %5d" % len(prices))
    print("\n기간 %s ~ %s" % (START, END))
    print("DB: %s" % DB)
    con.close()


if __name__ == "__main__":
    build()
