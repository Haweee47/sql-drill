# -*- coding: utf-8 -*-
"""회귀 테스트 — 정답_MySQL.sql 의 모범답안을 전부 채점해 본다.

    python regress.py

데이터셋이나 참조 정답을 건드린 뒤에는 반드시 이걸 돌린다.
'문제를 하나 고쳤더니 다른 문항이 조용히 깨지는' 사고를 막는 유일한 방법이다.

종료 코드 0 = 전부 통과.
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import app                                    # noqa: E402
import dialects as DIA                         # noqa: E402

ANSWERS = os.path.join(HERE, "정답_MySQL.sql")


def load():
    """'-- ── Qn. 제목 ───' 뒤에 오는 첫 쿼리를 문항별 모범답안으로 읽는다."""
    s = io.open(ANSWERS, encoding="utf-8").read()
    out = {}
    marks = [(m.start(), int(m.group(1)))
             for m in re.finditer(r"^--\s*[─\-]*\s*Q(\d+)\.", s, re.M)]
    for k, (pos, qid) in enumerate(marks):
        end = marks[k + 1][0] if k + 1 < len(marks) else len(s)
        body = s[pos:end]
        body = body[body.index("\n") + 1:]                 # 제목 줄 버리기
        body = "\n".join(l for l in body.splitlines()
                         if not l.strip().startswith("--"))
        body = body.strip()
        if ";" in body:
            body = body[:body.index(";")]
        if body.strip():
            out[qid] = body.strip()
    return out


def main():
    answers = load()
    ids = [t["id"] for t in app.TASKS]
    missing = [i for i in ids if i not in answers]
    print("모범답안 %d개 / 문항 %d개" % (len(answers), len(ids)))
    if missing:
        print("답안 없음: %s" % ", ".join("Q%d" % i for i in missing))
    print("-" * 74)

    bad = 0
    for qid in sorted(answers):
        task = next((t for t in app.TASKS if t["id"] == qid), None)
        if task is None:
            continue
        try:
            cols, rows = DIA.run(answers[qid], "mysql")
        except Exception as e:
            print("Q%-2d  실행 실패 — %s" % (qid, str(e).splitlines()[0][:60]))
            bad += 1
            continue
        res = app.grade(task, cols, rows)
        fails = []
        if not res["passed"]:
            fails.append("본데이터: " + (res["messages"] or ["?"])[0][:60])
        for d in app.check_datasets(task, answers[qid], "mysql"):
            if not d["ok"]:
                fails.append("%s: %s" % (d["name"], d["why"][:60]))
        if fails:
            bad += 1
            print("Q%-2d  실패" % qid)
            for f in fails:
                print("       - %s" % f)
        else:
            print("Q%-2d  통과 (본데이터 + 데이터셋 %d개)" % (qid, len(app.DATASETS)))

    print("-" * 74)
    print("실패 %d개" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
