---
name: slice
description: Use when the founder starts a slice with /slice <issue>. Walks How work happens from the issue to the merged PR, one step at a time, each with its done-when.
disable-model-invocation: true
argument-hint: "<issue number>"
---

# slice

One session, one slice. AGENTS.md (How work happens) is the law; this is its order.

1. **Fetch the issue once.** `gh issue view $ARGUMENTS --json title,body,comments,milestone --jq '.title, .milestone.title,
   .body, (.comments[].body)'`; keep it, never fetch it again in this session. Done when you know its sprint, the
   acceptance criteria, the Design comment if any, and the decisions.
2. **Is it in the current sprint?** It is when its milestone is the open sprint with the lowest number. Done when it
   is; if not, say so and stop.
3. **Design.** Without a Design comment, write one (domain objects and ports, data shape, tests, what it leaves
   out) and wait for the founder's go. Done when the issue holds a Design comment the founder accepted.
4. **Branch.** `git switch -c <name> origin/main`, named after the slice in plain words. Done when on it, clean.
5. **Build.** Each criterion in turn, its test first: red, fix, green, fix reverted red (the verify skill's red
   check). Read the system's guide (`app/`, `radar/` or `contracts/AGENTS.md`) before its first file. Anything
   outside the criteria becomes an issue, not code. Done when every criterion has code and a test that fails
   without it.
6. **Review.** The standards-review skill on the staged diff. Done when every finding is fixed or rebutted.
7. **Commit.** One issue per commit: `type(scope): subject`, a body that ends with `Refs #N`, the `Lines: +A/-D`
   trailer from `git diff --cached --numstat`. Done when the pre-commit hook passes.
8. **Gate.** `npm run check` on the clean tree, in the foreground under its limit; read its last block, never poll.
   Done when it prints the clean `GATES: PASS` line.
9. **PR.** With the sprint built: push, open the PR with the issues, decisions, line count and GATES line; screenshots
   in `../MVRadar-screenshots/pr-<n>/`, shown to the founder. Done when the PR is open and green.
10. **Close.** After the merge: tick the criteria, comment the Retrospective on the PR. Done when the issues are closed.
