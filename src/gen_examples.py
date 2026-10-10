# -*- coding: utf-8 -*-
"""예시 입력에 참조 정답을 실제로 돌려 예시 출력을 만든다.

손으로 쓴 예시는 틀리기 쉽고, 틀린 예시는 없느니만 못하다.
결과는 examples.json으로 저장하고 app.py가 읽는다.
"""
import json
import os
import sys

import duckdb

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from schema import EXAMPLES, SCHEMA  # noqa: E402
from tasks import TASKS  # noqa: E402

TYPES = {t["name"]: dict(t["cols"]) for t in SCHEMA}


def build(tables):
    """예시 입력으로 메모리 DB를 만든다. 실제와 같은 컬럼 타입을 쓴다."""
    con = duckdb.connect(":memory:")
    # NULL 정렬 순서를 시험 환경(MySQL·SQLite)에 맞춘다. 이걸 빼면 예시 출력의
    # 행 순서가 채점 결과와 달라져, 예시가 틀린 순서를 가르치게 된다.
    try:
        con.execute("SET default_null_order='nulls_first_on_asc_last_on_desc'")
    except Exception:
        pass
    for name, (cols, rows) in tables.items():
        decl = ", ".join("%s %s" % (c, TYPES[name][c].replace("char(1)", "VARCHAR"))
                         for c in cols)
        con.execute("CREATE TABLE %s (%s)" % (name, decl))
        if rows:
            ph = ",".join(["?"] * len(cols))
            con.executemany("INSERT INTO %s VALUES (%s)" % (name, ph), rows)
    # 문항이 참조하지만 예시에 없는 테이블은 빈 테이블로 만들어 둔다
    for t in SCHEMA:
        if t["name"] not in tables:
            decl = ", ".join("%s %s" % (c, ty.replace("char(1)", "VARCHAR"))
                             for c, ty in t["cols"])
            con.execute("CREATE TABLE %s (%s)" % (t["name"], decl))
    return con


def main():
    out = {}
    for task in TASKS:
        tables = EXAMPLES.get(task["id"])
        if not tables:
            print("  Q%-2d 예시 없음" % task["id"]); continue
        con = build(tables)
        try:
            cur = con.execute(task["ref"])
            cols = [d[0] for d in cur.description]
            rows = [["NULL" if v is None else str(v) for v in r] for r in cur.fetchall()]
        except Exception as e:
            print("  Q%-2d 실행 오류: %s" % (task["id"], str(e)[:120])); con.close(); continue
        con.close()
        out[str(task["id"])] = {
            "input": {n: {"cols": c, "rows": [[str(x) for x in r] for r in rs]}
                      for n, (c, rs) in tables.items()},
            "output": {"cols": cols, "rows": rows},
        }
        print("  Q%-2d 입력 %s → 출력 %d행" %
              (task["id"], "/".join("%s %d" % (n, len(rs)) for n, (c, rs) in tables.items()),
               len(rows)))
    json.dump(out, open(os.path.join(HERE, "examples.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\nexamples.json 저장 — %d문항" % len(out))


if __name__ == "__main__":
    main()
