# Handoff

**Last updated:** 2026-10-29, government laptop (C29Oscar.Basaula), Claude Code.

## Objective
Get the squad filling their 715As with Falcon Bullets before strats are due (Nov 2 COB).

## Done
- Login + per-user bullets in Supabase; 715A draft syncs across devices via user metadata.
- "Fill my 715a": Section I from the email (name, class year, class-role duty text, semester), four
  Section II sentences, one-click download of the filled form as `LAST_FIRST_USAFA715A.pdf`.
- Form copy pixel-identical to the original outside the entry boxes; filled text matched to Acrobat
  (Falcon Sans 415, measured layout).

## In progress / waiting on the user
- Form moved behind login: user pastes `~/Downloads/falcon-bullets-form.sql` into the Supabase SQL editor;
  then verify the site reads table `forms`, push the site change, and untrack `usafa715a-fillable.pdf`.
- Optional: rewrite git history to purge the earlier public copies of the form (needs force-push; ask first).
- Job picker SQL (AFCW directory) generated locally; not loaded — user wants it later and must approve.
- User to confirm a real `@afacademy.af.edu` login works and test CAC signing in Acrobat.

## Next steps
- Delete the throwaway test accounts in Supabase Auth (test.cadet.e2e@..., falcon...).

## Commands
- Re-publish the form to Supabase: `python tools/build_form_sql.py usafa715a-fillable.pdf form.sql`, paste in SQL editor
- Rebuild the form: `python tools/build_715a.py <flattened 715A> <official 715A> usafa715a-fillable.pdf`
- Rebuild the font: `python tools/build_font.py <SourceSans3VF-Upright.ttf> 415 fonts/FalconSans-Regular.ttf`
