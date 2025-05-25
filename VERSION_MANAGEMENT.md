# Version Management Guidelines

This document summarizes the version management requirements for DocVault and all projects following the global CLAUDE.md rules.

## Key Requirements

### 1. Version Bumping

- **MUST** follow [Semantic Versioning](https://semver.org/)
  - MAJOR: Incompatible API changes (1.0.0+)
  - MINOR: Backwards-compatible new features
  - PATCH: Backwards-compatible bug fixes
- Update version in `docvault/version.py`
- Update CHANGELOG.md before committing

### 2. CHANGELOG.md Format

Following [Keep a Changelog](https://keepachangelog.com/):

```markdown
## [Unreleased]
### Added
### Changed
### Deprecated
### Removed
### Fixed
### Security

## [X.Y.Z] - YYYY-MM-DD
### Added
- New features...
### Changed
- BREAKING: Changes that break compatibility...
```

### 3. Breaking Changes

- Mark with `BREAKING:` prefix in CHANGELOG.md
- Use `!` suffix in commit messages (e.g., `feat!:`)
- Or include `BREAKING CHANGE:` in commit footer

### 4. Alpha Software Notice

For pre-1.0 versions, include prominent warning:

```markdown
> ⚠️ **Alpha Software**: This project is currently in alpha stage (v0.x.x).
> The API is unstable and may change significantly before v1.0 release.
```

## Files Updated

1. **Global CLAUDE.md** (`~/.claude/CLAUDE.md`)
   - Added Version Management section (Section 2)
   - Renumbered AI-Agent Core Conventions to Section 3

2. **Project CLAUDE.md** (`docvault/CLAUDE.md`)
   - Added Version and Quality Notice section
   - Added Versioning Directives section
   - Added CHANGELOG.md Tracking section
   - Added Contributing and Version Updates section

3. **README.md**
   - Already had alpha warning at top
   - Already had Version Management section
   - Already had contributing instructions

4. **CHANGELOG.md**
   - Added proper header with Keep a Changelog reference
   - Added [Unreleased] section template
   - Added smart depth detection feature to Unreleased

## Workflow Summary

1. Make changes to code
2. Update version in `docvault/version.py` if needed
3. Add changes to CHANGELOG.md under [Unreleased]
4. Commit with conventional commit format
5. On release, move Unreleased items to new version section

## Example Commit Messages

```bash
# Feature with breaking change
feat!: change scrape_url signature to accept depth strategies

# Fix with no breaking change  
fix: handle empty document content in summarizer

# With breaking change footer
feat: add new authentication system

BREAKING CHANGE: auth tokens now require 'Bearer' prefix
```
