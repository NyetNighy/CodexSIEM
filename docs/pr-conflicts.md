# Resolving Pull Request Conflicts

If your PR shows conflicts, use this workflow from your feature branch.

## Option A (recommended): Rebase onto main

```bash
git fetch origin
git checkout <your-branch>
git rebase origin/main
```

If conflicts appear:

1. Open conflicted files and resolve `<<<<<<<`, `=======`, `>>>>>>>` blocks.
2. Mark resolved files:

```bash
git add <file1> <file2>
```

3. Continue rebase:

```bash
git rebase --continue
```

Repeat until complete, then push:

```bash
git push --force-with-lease
```

## Option B: Merge main into your branch

```bash
git fetch origin
git checkout <your-branch>
git merge origin/main
```

Resolve conflicts, then:

```bash
git add <resolved-files>
git commit

git push
```

## Tips to reduce future conflicts

- Rebase/merge `origin/main` before opening PR and before final review.
- Keep PRs smaller and focused.
- Avoid broad formatting-only changes across many files.
