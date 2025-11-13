# Branch Strategy

This document outlines the Git branch strategy for the FraudGuard AI project.

## Branch Structure

### Main Branches

1. **`main`** (Production)
   - Contains production-ready code
   - Protected branch - no direct pushes allowed
   - Requires pull request with approval
   - All commits must pass CI/CD checks
   - Only merged from `develop` branch

2. **`develop`** (Development)
   - Integration branch for features
   - Contains latest development code
   - Merged from feature branches
   - Used for staging and testing

### Supporting Branches

3. **`feature/*`** (Feature Branches)
   - Created from `develop`
   - Named after feature: `feature/task-31-github-setup`
   - Merged back to `develop` when complete
   - Deleted after merge

4. **`hotfix/*`** (Hotfix Branches)
   - Created from `main` for urgent production fixes
   - Merged to both `main` and `develop`
   - Follow naming: `hotfix/critical-bug-fix`

5. **`release/*`** (Release Branches)
   - Created from `develop` for release preparation
   - Used for final testing and bug fixes
   - Merged to both `main` and `develop`
   - Follow naming: `release/v1.0.0`

## Workflow

### Feature Development

1. Create feature branch from `develop`:
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feature/task-31-github-setup
   ```

2. Work on feature and commit:
   ```bash
   git add .
   git commit -m "feat: implement feature X"
   ```

3. Push feature branch:
   ```bash
   git push origin feature/task-31-github-setup
   ```

4. Create Pull Request to `develop`
5. After review and approval, merge to `develop`
6. Delete feature branch

### Release Process

1. Create release branch from `develop`:
   ```bash
   git checkout develop
   git checkout -b release/v1.0.0
   ```

2. Final testing and bug fixes on release branch
3. Merge to `main` when ready
4. Tag the release:
   ```bash
   git tag -a v1.0.0 -m "Release version 1.0.0"
   git push origin v1.0.0
   ```

5. Merge back to `develop`

### Hotfix Process

1. Create hotfix branch from `main`:
   ```bash
   git checkout main
   git checkout -b hotfix/critical-bug-fix
   ```

2. Fix the issue and commit
3. Merge to `main` and tag
4. Merge to `develop`

## Branch Protection Rules

### Main Branch
- ✅ Require pull request reviews before merging
- ✅ Require status checks to pass before merging
- ✅ Require branches to be up to date before merging
- ✅ Require conversation resolution before merging
- ✅ Do not allow force pushes
- ✅ Do not allow deletions

### Develop Branch
- ✅ Require pull request reviews before merging
- ✅ Require status checks to pass before merging
- ⚠️ Allow force pushes (for rebasing)
- ❌ Do not allow deletions

## Commit Message Convention

Follow conventional commits format:

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `style:` - Code style changes (formatting, etc.)
- `refactor:` - Code refactoring
- `test:` - Adding or updating tests
- `chore:` - Maintenance tasks

Example:
```
feat: add GitHub Actions CI/CD workflow

- Set up automated testing
- Configure deployment pipeline
- Add code quality checks
```

## Best Practices

1. **Keep branches small and focused** - One feature per branch
2. **Regularly sync with develop** - Rebase feature branches on develop
3. **Write clear commit messages** - Follow conventional commits
4. **Delete merged branches** - Keep repository clean
5. **Use pull requests** - Never push directly to main or develop
6. **Review before merging** - All PRs require at least one approval

## Setup Commands

### Initial Setup

```bash
# Create develop branch
git checkout -b develop
git push -u origin develop

# Create feature branch template
git checkout develop
git checkout -b feature/task-31-github-setup
```

### Daily Workflow

```bash
# Start new feature
git checkout develop
git pull origin develop
git checkout -b feature/your-feature-name

# Work and commit
git add .
git commit -m "feat: your feature description"

# Push and create PR
git push origin feature/your-feature-name
```

