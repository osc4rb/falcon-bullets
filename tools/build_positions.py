"""Extract cadet positions from the AFCW Classification Directory into SQL.

Reads every position's title, rank line, and "Duty Summary" and writes a SQL
script that loads them into a Supabase `positions` table readable only by
signed-in academy accounts. The directory is internal to the Cadet Wing, so the
output is NOT committed to this public repo.

Usage:  python build_positions.py <AFCW Classification Directory.pdf> <out.sql>
"""
import re
import sys

import pymupdf

# Words kept upper-case when turning "SQUADRON A1 STAFF" into "Squadron A1 Staff".
KEEP_UPPER = {"NCO", "NCOIC", "IPR", "PEER", "EO", "EOL", "CST", "SPARK", "OIC", "XF", "ML", "SL",
              "AFCW", "CW", "PP", "SEL", "CWOC", "HCX", "AMT", "II", "III", "IV", "BCT", "ACE",
              "AD", "LNO", "SAAC"}
SMALL = {"OF", "AND", "THE", "FOR", "TO", "IN", "ON", "AT", "OR"}
GROUP_ORDER = ["Cadet Squadron Staff", "Special Functions", "Cadet Group Staff", "Cadet Wing Staff",
               "Wing Operational Functions", "Policy, Plans and Programs", "APPENDIX E: Summer Wing Staff"]


def display_title(t):
    words = []
    for i, w in enumerate(t.split()):
        core = re.sub(r"[^A-Za-z0-9]", "", w).upper()
        if "/" in w and not re.search(r"\d", w):
            words.append("/".join(p if p.upper() in KEEP_UPPER else p[:1].upper() + p[1:].lower()
                                  for p in w.split("/")))
        elif re.search(r"\d", w) or core in KEEP_UPPER or w.lower() == "i5":
            words.append(w if w.lower() != "i5" else "i5")
        elif re.fullmatch(r"\(\d+x\)", w, re.I):
            words.append(w.lower())
        elif core in SMALL and i > 0:
            words.append(w.lower())
        else:
            words.append("-".join(p[:1].upper() + p[1:].lower() for p in w.split("-")))
    return " ".join(words)


def chapter_lookup(doc):
    chaps = [(pg, t.strip()) for lvl, t, pg in doc.get_toc()
             if lvl == 1 and not t.upper().startswith("CHAPTER") and pg >= 9]

    def chapter(pg):
        c = ""
        for p, t in chaps:
            if p <= pg:
                c = t
        return c
    return chapter


def extract(pdf_path):
    doc = pymupdf.open(pdf_path)
    chapter = chapter_lookup(doc)
    lines, page_of = [], []
    for i, page in enumerate(doc):
        t = page.get_text()
        for ch in (" ", " ", " "):
            t = t.replace(ch, " ")
        for ln in t.split("\n"):
            lines.append(ln.rstrip())
            page_of.append(i + 1)

    def prev_nonblank(idx):
        idx -= 1
        while idx >= 0 and not lines[idx].strip():
            idx -= 1
        return idx

    out, seen = [], set()
    for i, ln in enumerate(lines):
        m = re.match(r"\s*1\.\s*Duty Summary[.:]?\s*(.*)", ln)
        if not m:
            continue
        # Summary runs until "2. Responsibilities".
        parts, j = [m.group(1)], i + 1
        while j < len(lines) and not re.match(r"\s*2\.\s*Responsibilities", lines[j]):
            if not re.match(r"\s*AFCWCD, 6 Aug 25\s*$", lines[j]) and not re.match(r"\s*\d+\s*$", lines[j]):
                parts.append(lines[j])
            j += 1
        summary = " ".join(" ".join(parts).split())
        ti = prev_nonblank(i)
        hi = prev_nonblank(ti)
        title = " ".join(lines[ti].split())
        header = " ".join(lines[hi].split()) if hi >= 0 else ""
        if not title or not re.match(r"^[A-Zi][A-Z0-9 &/\-\(\)\.,'’x]+$", title):
            continue
        # A rank only counts at the start of a word, so office codes like "SWC/CC" aren't read as ranks.
        rank_re = r"(?:(?<=^)|(?<=[\s,]))C/(?:Lt Col|2d Lt|[A-Za-z0-9]+)"
        ranks = re.findall(rank_re, header)
        additional = bool(re.match(r"additional duty", header, re.I))
        office = "" if additional or not ranks else re.split(r",?\s*" + rank_re, header)[0].strip(" ,")
        key = title.upper()
        if key in seen:
            continue
        seen.add(key)
        out.append({"title": title, "display": display_title(title), "office": office,
                    "rank": ", ".join(r[2:] for r in ranks), "additional": additional,
                    "summary": summary, "grp": chapter(page_of[i]), "page": page_of[i]})
    rank = {g: n for n, g in enumerate(GROUP_ORDER)}
    out.sort(key=lambda p: (rank.get(p["grp"], 99), p["page"]))
    return out


def sql_str(s):
    return "'" + s.replace("'", "''") + "'"


def main(pdf_path, out_sql):
    rows = extract(pdf_path)
    with open(out_sql, "w", encoding="utf-8") as f:
        f.write("-- Falcon Bullets: AFCW Classification Directory positions (Cadet Wing internal).\n")
        f.write("-- Readable only by signed-in accounts with an academy email.\n")
        f.write("create table if not exists public.positions (\n"
                "  id serial primary key, title text not null, display text not null, office text,\n"
                "  rank text, additional boolean default false, summary text, grp text, page int\n);\n")
        f.write("alter table public.positions enable row level security;\n")
        f.write("revoke all on public.positions from anon;\n")
        f.write("grant select on public.positions to authenticated;\n")
        f.write("drop policy if exists \"academy accounts read positions\" on public.positions;\n")
        f.write("create policy \"academy accounts read positions\" on public.positions for select to authenticated\n"
                "  using ((auth.jwt() ->> 'email') ~* '@(.+\\.)?afacademy\\.(af\\.)?edu$');\n")
        f.write("truncate public.positions restart identity;\n")
        f.write("insert into public.positions (title, display, office, rank, additional, summary, grp, page) values\n")
        vals = [f"({sql_str(r['title'])}, {sql_str(r['display'])}, {sql_str(r['office'])}, {sql_str(r['rank'])}, "
                f"{'true' if r['additional'] else 'false'}, {sql_str(r['summary'])}, {sql_str(r['grp'])}, {r['page']})"
                for r in rows]
        f.write(",\n".join(vals) + ";\n")
    print(f"wrote {out_sql}: {len(rows)} positions")
    return rows


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
