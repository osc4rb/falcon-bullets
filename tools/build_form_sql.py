"""Write SQL that stores the fillable 715A in Supabase, readable only by academy accounts.

The form artwork is government material, so it is not published in this public repo.
Paste the output into the Supabase SQL editor; the site fetches it after sign-in.

Usage:  python build_form_sql.py <usafa715a-fillable.pdf> <out.sql>
"""
import base64
import sys

ACADEMY = r"'@(.+\.)?afacademy\.(af\.)?edu$'"


def main(pdf_path, out_sql):
    data = base64.b64encode(open(pdf_path, "rb").read()).decode("ascii")
    with open(out_sql, "w", encoding="utf-8") as f:
        f.write("-- Falcon Bullets: fillable USAFA Form 715A, readable only by signed-in academy accounts.\n")
        f.write("create table if not exists public.forms (\n"
                "  name text primary key, data text not null, updated_at timestamptz default now()\n);\n")
        f.write("alter table public.forms enable row level security;\n")
        f.write("revoke all on public.forms from anon;\n")
        f.write("grant select on public.forms to authenticated;\n")
        f.write("drop policy if exists \"academy accounts read forms\" on public.forms;\n")
        f.write("create policy \"academy accounts read forms\" on public.forms for select to authenticated\n"
                f"  using ((auth.jwt() ->> 'email') ~* {ACADEMY});\n")
        f.write("insert into public.forms (name, data) values ('usafa715a', '" + data + "')\n"
                "  on conflict (name) do update set data = excluded.data, updated_at = now();\n")
    print(f"wrote {out_sql} ({len(data):,} base64 chars)")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
