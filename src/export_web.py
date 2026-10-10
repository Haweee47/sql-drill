# -*- coding: utf-8 -*-
"""정적 사이트용 데이터를 뽑는다.

서버가 하던 일을 브라우저로 옮기기 위한 준비다.
  · 쿼리 실행   → 브라우저의 sql.js (SQLite WASM) 가 한다
  · 정답 계산   → 여기서 미리 돌려서 JSON 으로 박아 둔다
  · 추가 데이터셋 → 명세를 JSON 으로 넘겨 브라우저가 임시 DB 를 만든다

결과물은 web/ 아래에 떨어지고, 그대로 어디든 올리면 된다.
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import app                                  # noqa: E402
import engines as ENG                       # noqa: E402
import tables_extra as TX                   # noqa: E402
from datasets import DATASETS               # noqa: E402
from schema import SCHEMA                   # noqa: E402
from tasks import TASKS                     # noqa: E402

OUT = os.path.join(HERE, "web")
DATA = os.path.join(OUT, "data")


def jdump(name, obj):
    p = os.path.join(DATA, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    return os.path.getsize(p)


def main():
    os.makedirs(DATA, exist_ok=True)

    # ── 1. 문제 ──────────────────────────────────────────────────────
    tasks = []
    for t in TASKS:
        tasks.append({
            "id": t["id"], "title": t["title"], "level": t["level"],
            "minutes": t["minutes"], "prompt": t["prompt"],
            "columns": t["columns"], "order_note": t["order_note"],
            "tables": app.used_tables(t),
        })
    n = jdump("tasks.json", tasks)
    print("  tasks.json       %2d문항  %6.1f KB" % (len(tasks), n / 1024))

    # ── 2. 스키마 ────────────────────────────────────────────────────
    schema = [{"name": s["name"],
               "cols": [[c, ty] for c, ty in s["cols"]],
               "notes": s["notes"]} for s in SCHEMA]
    n = jdump("schema.json", schema)
    print("  schema.json      %2d테이블 %6.1f KB" % (len(schema), n / 1024))

    # ── 3. 예시 ──────────────────────────────────────────────────────
    ex = json.load(open(os.path.join(HERE, "examples.json"), encoding="utf-8"))
    n = jdump("examples.json", ex)
    print("  examples.json    %2d개     %6.1f KB" % (len(ex), n / 1024))

    # ── 4. 추가 데이터셋 명세 (브라우저가 임시 DB 를 만든다) ───────────
    ddl = dict(ENG._SQLITE_DDL)
    specs = []
    for name, spec in DATASETS:
        tbls = {}
        for tname, (cols, rows) in spec.items():
            tbls[tname] = {
                "cols": cols,
                "rows": [[(v.isoformat() if hasattr(v, "isoformat") else v)
                          for v in r] for r in rows],
            }
        specs.append({"name": name, "tables": tbls})
    n = jdump("datasets.json", {"ddl": ddl, "sets": specs})
    print("  datasets.json    %2d개     %6.1f KB" % (len(specs), n / 1024))

    # ── 5. 정답 (본 데이터 + 데이터셋별) ──────────────────────────────
    expected = {}
    for t in TASKS:
        rec = {}
        cols, rows = ENG.run(t["ref"], "duckdb")
        rec["main"] = {"cols": cols, "rows": rows}
        for name, spec in DATASETS:
            run, close = ENG.dataset_runner(spec, "duckdb")
            try:
                c, r = run(t["ref"])
                rec[name] = {"cols": c, "rows": r}
            except Exception as e:
                rec[name] = {"error": str(e)[:200]}
            close()
        expected[str(t["id"])] = rec
        print("    Q%-2d 본 %4d행" % (t["id"], len(rows)), end="")
        print("  " + "  ".join("%s %d" % (nm, len(expected[str(t["id"])][nm].get("rows", [])))
                               for nm, _ in DATASETS))
    n = jdump("expected.json", expected)
    print("  expected.json             %6.1f KB" % (n / 1024))

    # ── 6. DB 파일 ───────────────────────────────────────────────────
    src = os.path.join(HERE, "practice.sqlite")
    if not os.path.exists(src):
        sys.exit("practice.sqlite 가 없습니다. python make_sqlite.py 를 먼저 실행하세요.")
    dst = os.path.join(DATA, "practice.sqlite")
    shutil.copyfile(src, dst)
    print("  practice.sqlite           %6.1f KB" % (os.path.getsize(dst) / 1024))

    # ── 7. 해설 페이지 (서버 없이 그대로 쓸 수 있는 정적 HTML) ─────────
    guide = app.guide_html().replace('href="/"', 'href="./index.html"')
    with open(os.path.join(OUT, "guide.html"), "w", encoding="utf-8") as f:
        f.write(guide)
    print("  guide.html                %6.1f KB"
          % (os.path.getsize(os.path.join(OUT, "guide.html")) / 1024))

    print("\n  web/ 준비 완료 — 이 폴더를 통째로 올리면 됩니다.")


if __name__ == "__main__":
    main()
