Run a pre-PR review of my current changes.

Steps:
1. Run `git diff main...HEAD --stat` and read every changed file.
2. Launch the code-reviewer agent on the diff.
3. If connectors, profiling, or auth changed, also launch the security-auditor agent.
4. Summarize blockers/concerns and fix the blockers with me before I open the PR.
