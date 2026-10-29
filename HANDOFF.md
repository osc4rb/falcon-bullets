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
- Rebuilt `usafa715a-fillable.pdf` (restores the boxes' shaded edges) is built locally but NOT committed:
  needs the user's OK under the government-material rule (keep public / move behind login / remove).
- Job picker: SQL generated locally from the AFCW Classification Directory; not loaded. Needs the user's
  OK before that internal content goes into Supabase.
- User to confirm a real `@afacademy.af.edu` login works and test CAC signing in Acrobat.

## Next steps
- After the user decides on the form PDF: commit it (or host it behind login) and push.
- Delete the throwaway test accounts in Supabase Auth (test.cadet.e2e@..., falcon...).

## Commands
- Rebuild the form: `python tools/build_715a.py <flattened 715A> <official 715A> usafa715a-fillable.pdf`
- Rebuild the font: `python tools/build_font.py <SourceSans3VF-Upright.ttf> 415 fonts/FalconSans-Regular.ttf`
