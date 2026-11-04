---
name: architecture
description: Scores each pillar's top-level interface and the untyped seams under it, and designs an interface twice. Use at a sprint's start, in its Retrospective, and before an `interface` issue's Design.
---

# architecture

Keeps the repo **interface first** (AGENTS.md, How work happens, 9). Load the codebase-design skill first and use its
words exactly: module, interface, depth, seam, adapter, leverage, locality, and its deletion test.

The six pillars are model, acquisition, review, site, search and insights. Each one's interface is stated by its
`interface` issue: `gh issue list --label interface --state all --json number,title,state,labels`. A pillar whose
interface issue is still open has no stable interface yet.

## Score

1. **Scope.** At a sprint's start, the pillars its milestone says it moves; at its end, all six. Done when they are
   named.
2. **Map.** Start the `Explore` agent with the pillars, the codebase-design words, and one row to fill per pillar:
   - its entry: the one module callers use, its input and output types, how it starts, stops and reports status if
     it runs, and its errors;
   - each caller that reaches past the entry into its internals;
   - each port: its adapters (production and scripted), and whether it only forwards (the deletion test);
   - what crosses the entry untyped: `Any`, a lambda, a `Mapping[str, Any]` record, JSON text, a string kind.

   Done when every pillar has its row, with path:line evidence.
3. **Count.** The architecture guard (`test_untyped_seams_only_fall` in `radar/tests/repo/test_boundaries.py`) pins
   each untyped seam per file and keeps every pin equal to its count, so the pins are the counts. Each kind's total,
   from the repo root:
   `python3 -c "from radar.tests.repo.test_boundaries import UNTYPED; print({k: sum(v.values()) for k, v in UNTYPED.items()})"`

   Done when each total stands beside its value in the last sprint PR's **Architecture** section.
4. **Score.** Two scores out of 10 per pillar:
   - **does the job**, from the measure its `interface` issue names (`research measure`, `quality coverage`,
     `eval run`…); with none named yet, from the evidence, saying so;
   - **design**, from step 2: 8 when it has one entry, is typed in and out, states its lifecycle and errors, has
     tests that cross it, has no caller that reaches past it, and lets nothing untyped cross it; 7 when one of these
     still falls short; 6 when two do; 5 or less when more do, or when it has no single entry or lets untyped values
     cross its entry.

   Polish waits until every pillar has 7 on both. Done when every pillar has both scores, each with one line saying
   why.
5. **Act.** Fix a finding in the sprint when it takes a few lines. Otherwise open an issue with its pillar's label:
   `interface` when it changes an entry, and otherwise naming the interface it deepens. Done when every finding is
   either fixed or an issue.
6. **Report.** Put the scorecard and the counts, before and after, in the sprint PR's **Architecture** section; nothing
   lands in the repo. Done when the PR shows them.

## Design an interface

Before an `interface` issue's Design comment, design the interface twice (the codebase-design skill):

1. Start three or more sub-agents. Each designs the interface under a different constraint: the fewest entry points;
   the most common caller made trivial; ports and adapters at every dependency that crosses a seam.
2. Compare their designs on depth, locality and seam placement, and recommend one, or a hybrid when it is stronger.
3. Take the founder's open decisions through the grilling skill.

Done when the Design comment quotes the chosen interface and says why the others lost.
