# CLAUDE.md

Materials for HX Construtora (construction company in João Pessoa, Brazil). The users are the company team, not developers: answer in Brazilian Portuguese, explain in plain language, and open the result in the browser after each change.

## app-gestao/

Single-file visual prototype (`index.html` + `assets/`) of a management system meant to replace Excel spreadsheets. Hash routing: Painel, Obras, Obra HUR, Financeiro, Contratos, Diário de obra, RH & Ponto. All data is mocked in the script; the audio diary and AI report are simulated.

Visual identity (from hxconstrutora.com.br): black header, light blue `#92C0EB`, navy `#131C2B`, logo gray `#D7D9DB`, Numans uppercase titles, Inter for numbers, square corners. Keep it when adding screens.

Run: open `app-gestao/index.html`, or `cd app-gestao && python3 -m http.server 5260`.

## tour-3d/

three.js tour of the Hayah tower generated from the legal DWG. `web/index.html` (three.js via CDN) loads `web/model.js`, produced by `tools/extract.py`. See `tour-3d/README.md` for regenerating from a DWG. DWG/DXF files are git-ignored: they are client project files and must not be pushed to this public repo.

Run: `cd tour-3d/web && python3 -m http.server 5391`. Deploy: only `tour-3d/web/` goes to Vercel.

## Rules

- Never commit `.env*` files, passwords or API keys. This repository is public.
- Turning the prototype into a real system: plan first and get approval (suggested stack: Vite + React + Supabase).
