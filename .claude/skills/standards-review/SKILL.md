---
name: standards-review
description: Use before every commit, on the staged diff. Runs the read-only reviewer agent against AGENTS.md's Standards and the slice issue's acceptance criteria; every finding is fixed or rebutted.
---

# standards-review

1. **Diff.** Stage the change. Done when `git diff --cached --stat` shows exactly the slice's files.
2. **Review.** Start the `reviewer` agent with the slice issue's number and its acceptance criteria and Design
   comment, quoted from the one fetch you already made. Done when it returns its findings, or "no findings".
3. **Answer.** Fix each finding, or rebut it with the rule it misreads; an unrebutted SEVERE finding blocks the
   commit. Done when every finding is fixed or rebutted, the rebuttals in the slice issue's thread.

The reviewer reviews; it never rewrites the code.
