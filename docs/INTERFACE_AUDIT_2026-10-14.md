# Interface recovery withdrawal — 2026-10-14

## Outcome

The owner rejected the interface recovery after Windows testing and authorized its removal. All implementation, translation, test and workflow changes introduced by `gpt/recupera-interface` through `eacfc7a` are withdrawn together. Those paths are restored byte-for-byte to `0eb6775`; only the withdrawal documentation differs from that base. Original icons and their rendering are restored, without another redesign.

This is a rollback of an unsuccessful implementation, not completion of the interface requirements. The original development history remains available. No merge or history rewrite is performed.

## Evidence and limits

- The supplied recovery conversation reports a visually worse interface and renewed door gaps when replacing TEST-406 with the interface package. It explicitly acknowledges the icon redesign and that the branches were not integrated.
- Git confirms changes to `icons.py`, including the silhouettes in `a9d0a46`. Git also confirms that this branch and the door recovery branch diverged at `0eb6775`.
- The door engine files were not changed by this interface branch. The old door behavior came from distributing a separate branch without the door fixes; it was not a reversal of the fixes inside the door branch.
- The previous implementation report is superseded by this withdrawal. CI and offscreen screenshots did not establish visual acceptance.
- Conversations with the other two agents were not supplied. This cleanup does not infer their instructions or discard their independent branches.
- No new Windows validation or visual fidelity is claimed. No code is being newly implemented.

## Preserved references

| Purpose | Reference | Status |
|---|---|---|
| Official development | `claude/b1-curved-wall-perf` at `0eb6775` | Unchanged |
| Door recovery / TEST-406 line | `gpt/recupera-portas-f01` at `671f444` | Unchanged; not merged here |
| Real-host visual investigation | `gpt/investiga-visual` at `4e5a0f8` | Unchanged; infrastructure available |
| Rejected recovery history | `gpt/recupera-interface` through `eacfc7a` | Retained in Git history; withdrawn from branch tip |
| Design and functional requirements | `DECISIONS.md`, `DESIGN.md`, `PORTAS.md`, approved mockup PDF | Not revoked or rewritten |

TEST-340 and TEST-385 must not be recommended as upgrades of TEST-406. Any CI package generated for this rollback is likewise not an integrated replacement. `NEXT.md` now points to the preserved lines of work and marks recovery as suspended. Stop here until the owner defines a new interface attempt.
