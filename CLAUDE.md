# Working rules for agents

## Agent-written code must run before it is done

- Write or update tests that exercise the change, and run them before committing. Passing lint or type checks is not proof the code works.
- Run agent-executed code in a container or sandbox with no production secrets and limited network access.
- Never run unreviewed code against production credentials or data.
