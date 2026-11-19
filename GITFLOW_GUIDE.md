# Gitflow guide

Use `main` for production releases and `develop` for integration. Work in short lived feature and release branches, review pull requests, and merge feature branches into `develop` with a merge commit or squash according to team policy.

## Initialize the repository

```bash
git init
git add .
git commit -m "chore: initial project"
git branch -M main
git remote add origin https://github.com/ORG/REPOSITORY.git
git push -u origin main
git switch -c develop
git push -u origin develop
```

## Start a feature

```bash
git switch develop
git pull --ff-only origin develop
git switch -c feature/delivery-live-map
# make focused changes
git add backend frontend
git commit -m "feat: add live delivery tracking"
git push -u origin feature/delivery-live-map
```

Open a pull request from `feature/delivery-live-map` to `develop`. Address review feedback with additional commits, wait for CI, then merge and delete the feature branch.

## Prepare a release

```bash
git switch develop
git pull --ff-only origin develop
git switch -c release/1.0.0
# update version and release notes; commit only release fixes
git add .
git commit -m "chore: prepare release 1.0.0"
git push -u origin release/1.0.0
```

After review and CI, merge the release branch into `main`, tag it, and merge the same release branch back into `develop` so release fixes are retained:

```bash
git switch main
git pull --ff-only origin main
git merge --no-ff release/1.0.0
git tag -a v1.0.0 -m "AI Foodie 1.0.0"
git push origin main --follow-tags
git switch develop
git pull --ff-only origin develop
git merge --no-ff release/1.0.0
git push origin develop
git branch -d release/1.0.0
git push origin --delete release/1.0.0
```

## Hotfixes

Branch `hotfix/<short-name>` from `main`; apply and review the smallest production correction, merge into `main`, tag a patch release, then merge into `develop`.

```bash
git switch main
git pull --ff-only origin main
git switch -c hotfix/fix-payment-timeout
git commit -am "fix: handle payment gateway timeout"
git push -u origin hotfix/fix-payment-timeout
```

Protect `main` and `develop`: require pull requests, passing `CI and Docker delivery`, and at least one reviewer. Keep secrets in GitHub Actions secrets, never in branch commits.
