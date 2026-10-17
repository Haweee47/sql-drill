# -*- coding: utf-8 -*-
"""문항별 정적 페이지를 만든다 — 검색 유입용.

드릴(index.html)은 자바스크립트가 돌기 전까지 본문이 비어 있다.
검색 엔진이 가져갈 텍스트가 없으니 아무리 좋은 내용이 있어도 안 잡힌다.

그래서 문항마다 '읽을 수 있는 페이지'를 따로 만든다.
  web/q/5.html   ← 문제 + 쉬운 해설 + 자세한 해설 + 정답 쿼리
  web/q/        ← 20개 목록
각 페이지는 롱테일 검색어("SQL 코호트 리텐션 쿼리" 같은)를 노린다.
"""
import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from guide_data import GUIDE                 # noqa: E402
from guide_easy import EASY_BY_ID            # noqa: E402
from tasks import TASKS                      # noqa: E402

SITE = "https://haweee47.github.io/sql-drill"
OUT = os.path.join(HERE, "web")
QDIR = os.path.join(OUT, "q")

CSS = """
:root{--bg:#F7F7F5;--panel:#fff;--fg:#1B1F23;--muted:#6B7280;--line:#E3E3DF;
      --accent:#1B64DA;--ok:#0F7B4F;--bad:#C0392B;--code:#F3F4F6;--warn:#FFF8E6}
@media(prefers-color-scheme:dark){:root{--bg:#15181B;--panel:#1C2024;--fg:#E8EAEC;
      --muted:#99A1A9;--line:#2C3237;--accent:#6AA3F5;--ok:#4CC38A;--bad:#E57373;
      --code:#23282D;--warn:#2A2416;color-scheme:dark}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
     font:16px/1.78 "Malgun Gothic",system-ui,sans-serif}
.wrap{max-width:760px;margin:0 auto;padding-inline:18px;padding-block:0 70px}
nav.bc{font-size:13px;color:var(--muted);padding-block:16px 0}
nav.bc a{color:var(--accent);text-decoration:none}
nav.bc a:hover{text-decoration:underline}
h1{font-size:25px;line-height:1.4;margin:14px 0 6px;letter-spacing:-.4px;
   word-break:keep-all;text-wrap:balance}
.meta{color:var(--muted);font-size:13px;margin-bottom:20px}
.cta{display:inline-block;background:var(--accent);color:#fff;text-decoration:none;
     border-radius:9px;padding:10px 20px;font-weight:700;font-size:15px;margin:4px 0 22px}
h2{font-size:18px;margin:34px 0 10px;padding-top:14px;border-top:1px solid var(--line);
   letter-spacing:-.2px}
h3{font-size:14px;color:var(--muted);margin:20px 0 7px}
.box{background:var(--panel);border:1px solid var(--line);border-radius:10px;
     padding:14px 16px;white-space:pre-wrap;word-break:keep-all;font-size:14.5px;
     line-height:1.72}
.spec{font-size:13.5px;color:var(--muted);margin-top:10px;word-break:break-all}
code{font-family:Consolas,"D2Coding",monospace;font-size:.9em;background:var(--code);
     padding:1px 5px;border-radius:4px}
pre{background:var(--panel);border:1px solid var(--line);border-radius:10px;
    padding:14px 16px;overflow-x:auto;font-size:13.5px;line-height:1.66}
pre code{background:none;padding:0;font-size:inherit}
ol,ul{padding-left:22px}li{margin-bottom:7px;word-break:keep-all}
.oneline{font-size:17px;line-height:1.7;font-weight:600;word-break:keep-all;margin:0 0 14px}
table.e,table.g{border-collapse:collapse;margin:6px 0 12px;font-size:13.5px}
table.e th,table.e td,table.g th,table.g td{border:1px solid var(--line);padding:4px 11px;
    text-align:left}
table.e th,table.g th{background:var(--code);font-size:12.5px;color:var(--muted)}
table.e td.x{color:var(--bad)}
p.note{font-size:13.5px;color:var(--muted);margin:5px 0 12px;word-break:keep-all}
.trap{background:var(--warn);border-radius:10px;padding:13px 16px 13px 0}
.trap ul{padding-left:34px;margin:0}
.wt{background:var(--warn);border-radius:10px;padding:13px 16px 13px 0}
.wt ul{padding-left:34px;margin:0}
.var{color:var(--muted);font-size:14px;word-break:keep-all}
.pager{display:flex;gap:10px;margin-top:40px;padding-top:18px;
       border-top:1px solid var(--line);font-size:14px;flex-wrap:wrap}
.pager a{color:var(--accent);text-decoration:none}
.pager a:hover{text-decoration:underline}
.pager .r{margin-left:auto}
.list{list-style:none;padding:0}
.list li{margin-bottom:0;border-bottom:1px solid var(--line)}
.list a{display:block;padding:13px 4px;color:var(--fg);text-decoration:none}
.list a:hover{background:var(--panel)}
.list .lv{color:var(--muted);font-size:12.5px}
footer{margin-top:40px;padding-top:16px;border-top:1px solid var(--line);
       color:var(--muted);font-size:13px}
footer a{color:var(--accent)}
"""

HEAD = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="SQL 드릴">
<meta property="og:title" content="{ogtitle}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{url}">
<meta property="og:locale" content="ko_KR">
<meta name="twitter:card" content="summary">
<style>{css}</style>
</head><body><div class="wrap">
"""

FOOT = """
<footer>
  <a href="{site}/">SQL 드릴</a> — 브라우저에서 바로 돌아가는 SQL 쿼리 테스트 연습.
  서버도 회원가입도 없습니다. ·
  <a href="https://github.com/Haweee47/sql-drill">소스</a>
</footer>
</div></body></html>
"""


def e(s):
    return html.escape(str(s), quote=True)


def plain(s, n=155):
    """HTML 태그를 떼고 메타 설명용으로 줄인다."""
    import re
    t = re.sub(r"<[^>]+>", "", str(s))
    t = " ".join(t.split())
    return (t[:n - 1] + "…") if len(t) > n else t


def q_page(g, task, prev_g, next_g):
    ez = EASY_BY_ID.get(g["id"])
    url = "%s/q/%d.html" % (SITE, g["id"])
    title = "%s — SQL 문제 풀이와 함정 | SQL 드릴" % g["title"]
    desc = plain(ez["oneline"] if ez else g["asks"])

    h = HEAD.format(title=e(title), desc=e(desc), url=e(url),
                    ogtitle=e(g["title"] + " — SQL 풀이"), css=CSS)
    h += '<nav class="bc"><a href="%s/">SQL 드릴</a> › <a href="./">문항 해설</a> › Q%d</nav>' \
         % (SITE, g["id"])
    h += "<h1>%s</h1>" % e(g["title"])
    h += '<div class="meta">난이도 %s · 권장 %d분 · 출력 컬럼 <code>%s</code></div>' \
         % (e(g["level"]), task["minutes"], e(task["columns"]))
    h += '<a class="cta" href="%s/#q%d">이 문제 직접 풀어보기 →</a>' % (SITE, g["id"])

    h += "<h2>문제</h2>"
    h += '<div class="box">%s</div>' % e(task["prompt"])
    h += '<div class="spec">정렬 <code>%s</code></div>' % e(task["order_note"])

    if ez:
        h += "<h2>쉽게 설명하면</h2>"
        h += '<p class="oneline">%s</p>' % ez["oneline"]
        h += ez.get("idea", "")
        h += "<h3>이렇게 푼다</h3><ol>%s</ol>" % "".join("<li>%s</li>" % x for x in ez["how"])
        h += '<h3>이것만 피하면 된다</h3><div class="wt"><ul>%s</ul></div>' \
             % "".join("<li>%s</li>" % x for x in ez["watch"])

    h += "<h2>자세히</h2>"
    h += "<p><b>묻는 것</b> · %s</p>" % g["asks"]
    h += "<h3>풀이 순서</h3><ol>%s</ol>" % "".join("<li>%s</li>" % x for x in g["steps"])
    h += "<h3>정답 (MySQL)</h3><pre><code>%s</code></pre>" % e(g["sql"])
    h += '<h3>함정</h3><div class="trap"><ul>%s</ul></div>' \
         % "".join("<li>%s</li>" % x for x in g["traps"])
    h += '<h3>이렇게 변형된다</h3><p class="var">%s</p>' % g["variants"]

    h += '<div class="pager">'
    if prev_g:
        h += '<a href="./%d.html">← Q%d. %s</a>' % (prev_g["id"], prev_g["id"], e(prev_g["title"]))
    if next_g:
        h += '<a class="r" href="./%d.html">Q%d. %s →</a>' % (next_g["id"], next_g["id"], e(next_g["title"]))
    h += "</div>"
    h += FOOT.format(site=SITE)
    return h


def index_page():
    url = SITE + "/q/"
    desc = ("SQL 쿼리 테스트에 나오는 20개 유형의 문제와 풀이. 퍼널, 코호트 리텐션, "
            "윈도우 함수, gaps and islands, NULL 처리까지 함정과 함께 정리했습니다.")
    h = HEAD.format(title="SQL 문항 해설 20선 — 쿼리 테스트 유형 정리 | SQL 드릴",
                    desc=e(desc), url=e(url),
                    ogtitle="SQL 문항 해설 20선", css=CSS)
    h += '<nav class="bc"><a href="%s/">SQL 드릴</a> › 문항 해설</nav>' % SITE
    h += "<h1>SQL 문항 해설 20선</h1>"
    h += '<p class="meta">데이터 분석 채용 전형의 쿼리 테스트에 실제로 나오는 유형들입니다. '
    h += '각 문항마다 <b>쉬운 설명</b>과 <b>자세한 설명</b>을 함께 적었습니다.</p>'
    h += '<a class="cta" href="%s/">직접 풀어보기 →</a>' % SITE

    for lv in ("쉬움", "보통", "어려움"):
        items = [g for g in GUIDE if g["level"] == lv]
        if not items:
            continue
        h += "<h2>%s (%d문항)</h2><ul class=\"list\">" % (lv, len(items))
        for g in items:
            ez = EASY_BY_ID.get(g["id"])
            h += '<li><a href="./%d.html"><b>Q%d. %s</b><br>' % (g["id"], g["id"], e(g["title"]))
            h += '<span class="lv">%s</span></a></li>' % e(plain(ez["oneline"] if ez else g["asks"], 90))
        h += "</ul>"
    h += FOOT.format(site=SITE)
    return h


def main():
    os.makedirs(QDIR, exist_ok=True)
    tmap = {t["id"]: t for t in TASKS}
    order = sorted(GUIDE, key=lambda g: g["id"])

    for i, g in enumerate(order):
        t = tmap.get(g["id"])
        if not t:
            continue
        prev_g = order[i - 1] if i > 0 else None
        next_g = order[i + 1] if i + 1 < len(order) else None
        p = os.path.join(QDIR, "%d.html" % g["id"])
        with open(p, "w", encoding="utf-8") as f:
            f.write(q_page(g, t, prev_g, next_g))
    with open(os.path.join(QDIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_page())
    print("  q/ 페이지 %d개 + 목록 1개" % len(order))

    # ── sitemap.xml ──────────────────────────────────────────────────
    urls = [SITE + "/", SITE + "/q/", SITE + "/guide.html"]
    urls += ["%s/q/%d.html" % (SITE, g["id"]) for g in order]
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        pri = "1.0" if u.endswith("/sql-drill/") else ("0.9" if u.endswith("/q/") else "0.7")
        sm.append("  <url><loc>%s</loc><priority>%s</priority></url>" % (u, pri))
    sm.append("</urlset>")
    with open(os.path.join(OUT, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write("\n".join(sm))
    print("  sitemap.xml  %d개 URL" % len(urls))

    # ── robots.txt ───────────────────────────────────────────────────
    with open(os.path.join(OUT, "robots.txt"), "w", encoding="utf-8") as f:
        f.write("User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n" % SITE)
    print("  robots.txt")


if __name__ == "__main__":
    main()
