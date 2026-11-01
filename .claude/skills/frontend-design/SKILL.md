---
name: frontend-design
description: Design and build production-ready pages, components and styles for Spendly's server-rendered frontend (Flask + Jinja2 templates, plain CSS with variables, vanilla JS, INR currency). Use this skill whenever the user asks to create, redesign, restyle or polish any Spendly page or UI piece — profile, dashboard, expense list, add/edit/delete expense forms, filters, tables, cards, badges, charts, navbar, empty states, responsive or mobile layout, accessibility or "make it look better" — even if they never say "frontend" or "design". Also use it before writing any new template under templates/ or any CSS under static/css/.
---

# Spendly frontend design

Spendly is a small, server-rendered app: Flask returns Jinja2 templates, styled with hand-written CSS and (rarely) vanilla JS. There is no build step, no npm, no CSS framework and no JS framework. That is deliberate — it keeps the project teachable and fast — so good design here means working *within* those constraints rather than reaching for new tooling. The goal is UI a real user could rely on: consistent with the existing pages, responsive, accessible, and handling every state (empty, error, long text, big numbers).

## Before you write anything

1. Read `static/css/style.css` (tokens, navbar, buttons, auth/form styles, footer) and the page CSS closest to what you are building (`profile.css`, `landing.css`). Reuse an existing class before inventing one; two near-identical classes are how a design system rots.
2. Read `templates/base.html` for the blocks you can fill: `title`, `head`, `content`, `scripts`.
3. Read `CLAUDE.md` for conventions that override your instincts (INR, commit prefixes, step numbering).

## Stack rules

- **Templates:** every page `{% extends "base.html" %}`. Page CSS goes in `{% block head %}` as `<link rel="stylesheet" href="{{ url_for('static', filename='css/<page>.css') }}">`. Page JS goes in `{% block scripts %}`. Link with `url_for('<view_function>')`, never hardcoded paths in anchors (form `action="/login"` is the one legacy exception; prefer `url_for` in new code). Renaming a view function breaks templates, so don't.
- **CSS:** shared styles live in `style.css`; page-only styles in `static/css/<page>.css`. Use the variables in `:root` and never write hex, `rgb()` or named colours in templates or page CSS — this is what keeps theming and contrast fixable in one place. If you need a colour that does not exist, add a variable to `:root` in `style.css` (hex is allowed only there), then use it.
- **No inline styles** (`style="..."`) and no `<style>` blocks. Data-driven widths (bars, progress) use `<progress>`/`<meter>` or a small set of utility classes, not `style="width: 40%"`.
- **JS:** vanilla only, progressive enhancement. The page must work with JS off (forms POST, links navigate). Put shared behaviour in `static/js/main.js`, page behaviour in the template's `scripts` block.
- **Jinja:** autoescape is on — never use `|safe` on user-supplied text (names, descriptions). Format money with the `inr` filter from `app.py` (`{{ amount|inr }}`), never by hand.
- **No new dependencies** (CDN CSS/JS libraries, icon fonts, chart libraries) unless the user explicitly approves; Google Fonts for DM Serif Display and DM Sans are already loaded in `base.html`.

## Design language

Spendly looks calm, editorial and trustworthy — warm paper background, white cards with a thin border, deep green accent, serif display headings.

| Need | Use |
|---|---|
| Page background / card surface | `--paper` / `--paper-card` with `1px solid var(--border)` |
| Text hierarchy | `--ink` (primary), `--ink-soft`, `--ink-muted` (labels, meta), `--ink-faint` (placeholders only) |
| Primary action / positive emphasis | `--accent` on `--accent-light` |
| Secondary highlight | `--accent-2` on `--accent-2-light` |
| Errors / destructive actions | `--danger` on `--danger-light` |
| Headings, big numbers | `--font-display`; everything else `--font-body` |
| Corners | `--radius-sm` inputs/badges, `--radius-md` cards, `--radius-lg` hero panels |
| Content width | `max-width: var(--max-width)`, centred, side padding `2rem` (`1rem` on phones) |

Existing building blocks to reuse: `.btn-primary`, `.btn-ghost`, `.btn-submit`, `.form-group`, `.form-input`, `.auth-card`, `.auth-error`, `.nav-cta`, and the card/stat/table/badge/progress patterns in `profile.css`. Lift a pattern into `style.css` when a second page needs it.

## Production-ready checklist

Work through these for every page. They are the difference between a mock-up and something shippable.

**Responsive.** Design mobile-first or verify at 375px, 768px and 1200px. Existing breakpoints are around 900px, 720px and 600–640px; follow them rather than adding new ones. Grids use `repeat(auto-fit, minmax(...))` or collapse to one column; wide tables sit in an `overflow-x: auto` wrapper so the page itself never scrolls sideways. Tap targets are at least 44×44px on touch.

**Accessible.** Use real elements: `<button>` for actions, `<a>` for navigation, `<table>` with `<th scope>` for tabular data, one `<h1>` per page and headings in order. Every input has a visible `<label for>`; errors are text (not colour alone) near the field and in `role="alert"` or the existing `.auth-error` block. Keep a visible focus ring (`:focus-visible` with `--accent`) — never `outline: none` without a replacement. Text contrast is at least 4.5:1, so `--ink-faint` is for placeholders and decoration only. Decorative glyphs get `aria-hidden="true"`; meaningful non-text (progress bars) get a text equivalent.

**Every state.** Design the empty state ("No expenses yet" with a call to action), the error state, the long-content state (long descriptions wrap or truncate with `text-overflow`, never break the layout), and the big-number state (`₹12,34,567.00` must fit its card). Check with zero rows, one row and fifty rows.

**Money and dates.** INR only: `₹` with Indian grouping via the `inr` filter, tabular numerals (`font-variant-numeric: tabular-nums`) and right alignment in columns, never `$`. Show dates in one consistent human format, and keep ISO `YYYY-MM-DD` for `<input type="date">` values and `<time datetime>`.

**Forms.** `method="POST"`, correct `type` (`email`, `number` with `step="0.01"` and `min`, `date`), `autocomplete` hints, `required`, and repopulate fields after a server-side error (never the password). Server validation is the source of truth; HTML attributes are a convenience. Destructive actions need a confirmation step. There is no CSRF protection yet — don't invent a half-measure, but mention it when you add a state-changing form.

**Performance and polish.** No render-blocking additions beyond the one page stylesheet; no images without `width`/`height` and `alt`; avoid layout shift. Transitions are short (150–250ms) and limited to colour/opacity/transform; wrap anything larger in `@media (prefers-reduced-motion: no-preference)`. Add a `<title>` per page and keep the footer/nav from `base.html` intact.

**Security-minded markup.** Escape everything user-supplied, build links with `url_for`, and add `rel="noopener"` to any `target="_blank"` link.

## Workflow

1. Restate what the page must let the user do, and what data it receives from the view (names and shapes). If the view does not exist yet, define the context variables first so template and route agree.
2. Sketch the structure as semantic HTML with the existing classes; add only the new classes you need, named `block-element` style like the rest (`stat-card`, `cat-row`).
3. Write the page CSS using variables only, then run the checklist above.
4. Verify: run `venv/bin/python -m pytest`, then `grep -nE '#[0-9a-fA-F]{3,8}\b|style=' templates/<page>.html static/css/<page>.css` (expect no output), start `venv/bin/python app.py` (check port 5001 is free first) and look at the page logged in and logged out at phone and desktop widths. If you cannot view it in a browser, say so rather than claiming it looks right.
5. Add or extend tests in `tests/` for what the page promises: status codes and redirects, key content present, no `$`, no inline styles/hex.

## Things to flag rather than silently decide

- A feature needs a colour, font or pattern the system lacks.
- A page would need JS to work at all.
- The spec and these conventions disagree (for example, a spec that lists no CSS file but forbids inline styles): pick the convention-compliant option and say so.
- Existing code that breaks these rules (for instance `.auth-error` in `style.css` has a hardcoded border hex). Note it; fix it only if asked or if it is in the file you are already changing.
