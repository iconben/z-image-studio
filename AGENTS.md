

## Frontend assets update
- Static assets are now split under `src/zimage/static/css`, `js`, and `i18n` (relative URLs in `index.html`).
- Translations are loaded via `js/i18n-loader.js` into `window.translations` and consumed by `js/main.js`; add new locales by dropping JSON files in `i18n/`.
- Theme/helpers live in `js/theme.js` and `js/utils.js`; main app logic is in `js/main.js`.

## Development Guidelines

### Repository, Issues, and Merge Requests
The remote repository not only hosts source code, but also provides features such as issue tracking, merge requests/pull requests management etc. You should use mcp server to access issues, managing merge requests/pull requests.

### Development

Use context7 for the most up-to-date documentation of the specific version of related frameworks and libraries.  

Add necessary docs in comments, for classes and methods please use comment blocks.

## Commit Message Policy

All contributors **must** use [semantic commit messages](https://www.conventionalcommits.org/) for every commit. This helps ensure clarity, traceability, and automation in our development workflow.

### Semantic Commit Format

```
<type>(<scope>): <short summary>

[optional body]

[optional footer(s)]
```

#### Examples

- `feat(ledger): add validation for legalEntityCode`
- `fix(accounting): correct rounding error in calculations`
- `docs(readme): update usage instructions`

**Types:** feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert
