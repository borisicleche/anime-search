# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository layout

Monorepo. JS projects form a pnpm workspace (`pnpm-workspace.yaml` at the root covers `apps/*` and `packages/*`, with a single root `pnpm-lock.yaml`); the Python service is outside it and managed by uv.

- `apps/web` (`@anime-search/web`) — Next.js frontend.
- `packages/shared` (`@anime-search/shared`) — TypeScript types generated from the AI service's OpenAPI schema.
- `services/ai` — Python service (uv, Python 3.13 per `.python-version`).

Run `pnpm install` once at the repo root (never inside a package; that would create a stray lockfile). Root scripts proxy to packages: `pnpm dev`, `pnpm build`, `pnpm check` (all packages), `pnpm gen:types`. Package-specific commands can be run from inside the package directory or via `pnpm --filter <name> <script>`.

## packages/shared (generated API types)

`pnpm gen:types` runs `openapi-typescript` against the running AI service (`http://localhost:8080/openapi.json`) and writes `src/ai-service.d.ts`. With `--root-types --root-types-no-schema-prefix`, every Pydantic model is exported by name, so the web app imports `import type { Anime } from "@anime-search/shared/ai-service"`. The file is generated: never edit it by hand; regenerate after changing Pydantic models and commit the result. Pydantic model names must be unique across the service, since they become top-level type names.

## apps/web (Next.js)

```bash
cd apps/web
pnpm dev      # dev server on http://localhost:3000
pnpm build
pnpm lint          # eslint (lint:fix to auto-fix)
pnpm format        # prettier --write .   (format:check to verify)
pnpm check         # lint + format:check, for CI
```

ESLint (`eslint.config.mjs`): next core-web-vitals + typescript, `simple-import-sort` for import order, and `eslint-config-prettier` last so ESLint never fights Prettier. Prettier (`prettier.config.mjs`) uses `prettier-plugin-tailwindcss` to sort class names; with Tailwind v4 it reads `tailwindStylesheet: ./src/app/globals.css`.

No test runner is configured yet.

**Read `apps/web/AGENTS.md` before writing Next.js code.** This is Next.js 16.4 with React 19.3, and APIs differ from older versions. Consult the bundled docs in `apps/web/node_modules/next/dist/docs/`. `next dev` re-adds that AGENTS.md block automatically, so keep it committed.

Non-default settings in `next.config.ts` that affect how code must be written:

- `cacheComponents: true` and `partialPrefetching: true` enable the newer caching/prefetch model.
- `reactCompiler: true` means manual `useMemo`/`useCallback` is usually unnecessary.
- Tailwind v4 runs through a Turbopack CSS loader rule (`@tailwindcss/turbopack`), not PostCSS.

All source lives under `apps/web/src/`, with App Router routes in `src/app/`. The `@/*` alias maps to `src/*`. Route types (e.g. `LayoutProps<"/">`) are generated into `.next/types`; if typecheck complains after moving routes, delete `.next` and run `pnpm exec next typegen`.

## services/ai (Python)

```bash
cd services/ai
uv sync               # create .venv and install deps
uv run python hello.py
uv add <package>      # add a dependency (updates pyproject.toml + uv.lock)
uv add --dev <pkg>    # add a dev-only tool
uv run poe            # list tasks (defined in [tool.poe.tasks] in pyproject.toml)
uv run poe lint       # ruff check .   (lint:fix to auto-fix)
uv run poe format     # ruff format .
uv run poe check      # lint + format:check, for CI
uv run poe test       # pytest (run one test: uv run pytest tests/test_health.py::test_health_returns_ok)
uv run poe dev        # FastAPI dev server with reload on http://localhost:8080
```

Linting/formatting is Ruff (config in `[tool.ruff]`); task aliases use poethepoet because uv has no built-in script runner. Add new aliases to `[tool.poe.tasks]`, not `[project.scripts]` (that defines package entry points).

The service is a FastAPI app: `app/main.py` creates `app` and defines `/health`, routers live in `app/routers/`, Pydantic models in `app/models.py`. `bench.py` and `bench_cache.py` are standalone LLM experiments, not part of the app.

Tests use pytest and live in `tests/`, named `test_*.py`. They call the app in-process through FastAPI's `TestClient` (needs `httpx`, already a dev dependency), so no server has to be running. `[tool.pytest.ini_options]` sets `pythonpath = ["."]` so tests can `from app.main import app`.
