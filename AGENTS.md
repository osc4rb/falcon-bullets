# Falcon Bullets

A private accomplishment log for USAFA cadets that fills out USAFA Form 715A (Cadet Performance
Brief) for strats. Live at https://osc4rb.github.io/falcon-bullets/ (GitHub Pages, repo osc4rb/falcon-bullets).

## Architecture
- `index.html` — the whole app (vanilla JS, no build step). Loads from CDN: supabase-js v2,
  pdf-lib 1.17.1, @pdf-lib/fontkit 1.1.1.
- Supabase (project ref in `index.html`; the publishable key there is public by design):
  email/password auth, `bullets` table with row-level security (each user reads/writes only their rows).
  The 715A draft (Section I edits + section sentences) is stored in the user's auth `user_metadata`.
- `usafa715a-fillable.pdf` — the real 715A artwork (from an Acrobat-flattened copy) with old entries
  removed and AcroForm fields added at the exact XFA-template coordinates. Built by `tools/build_715a.py`.
- `fonts/FalconSans-Regular.ttf` — Source Sans 3 tuned to match the form's Myriad Pro (see `fonts/README.md`).
- `tools/build_positions.py` — turns the AFCW Classification Directory into SQL for a `positions` table
  (job picker). Its output is NOT committed (Cadet-Wing internal).

## Run / deploy
- No build. Edit `index.html`, `git push` to `main`, GitHub Pages redeploys in ~1 minute.
- Test the fill locally with Node + pdf-lib (same code path as the browser `download715()`).

## Conventions
- Field names in the PDF: `name, class_rank, unit, semester, duty_title, duty_desc, s1..s4`,
  checkboxes `s{n}_{needs_improvement|developing|proficient|highly_proficient|exceptionally_skilled}`,
  signature fields `rater_sig, cc_sig, pp_sig, ratee_sig`.
- App areas = the form's Section II boxes: Executing the Mission, Leading People, Managing Resources,
  Improving the Unit.

## Decisions
- The official 715A is an encrypted Adobe XFA form; nothing outside Acrobat can fill it, so the app
  fills a rebuilt copy on the real artwork instead. The page is the real form; the file is a new PDF.
- Old entries are removed with line-art redaction and `fill=False` (painting white hid the boxes'
  recessed edges). Verified: zero pixel differences outside entry boxes vs. the original.
- Text is drawn with a custom appearance (left 0.7pt, right 2.5pt, first baseline 1.155x size,
  1.2x line spacing, weight 415) measured against Acrobat's render of a real filled 715A:
  baselines within 0.25pt, same line breaks, ink ratio 0.998.
- Name and class come from the login email (`c29first.last@afacademy.af.edu` -> "Last, First", 2029 -> C3C).
  Cadet emails are `@afacademy.af.edu`.
- Supabase email confirmation must stay OFF (free-tier mail is rate-limited and the confirm link breaks).
- Government material: the user's global rule forbids committing government-owned files without approval.
  The 715A artwork and the AFCW directory are treated as needing the user's sign-off before being published.
