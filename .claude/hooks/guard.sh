#!/usr/bin/env bash
# A Bash command Claude Code is about to run, refused (exit 2, the reason on stderr) when it skips a hook, force-pushes
# main, or writes to the project or deploys without the founder's go, which the command carries as FOUNDER_GO=1.
command=$(jq -r '.tool_input.command // ""')
refuse() { echo "Refused by .claude/hooks/guard.sh: $1" >&2; exit 2; }

[[ $command == *--no-verify* ]] && refuse "--no-verify skips the gates; fix what the hook reports (AGENTS.md, Gates)."
[[ $command =~ git[[:space:]]+push ]] && [[ $command =~ (--force|[[:space:]]-f([[:space:]]|$)|[[:space:]]\+) ]] \
  && [[ $command =~ (^|[[:space:]:+/])main([[:space:]]|$) ]] && refuse "no forced push to main."
if [[ $command != *FOUNDER_GO=1* ]]; then
  [[ $command == *radar* && $command == *--yes* ]] \
    && refuse "a write to the project needs the founder's go; ask, then prefix FOUNDER_GO=1."
  [[ $command == *deploy:local* ]] && refuse "deploying is the founder's; ask, then prefix FOUNDER_GO=1."
fi
exit 0
