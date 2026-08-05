---
name: code-plan
description: Turn completed code research plus the user's request into a concrete, step-by-step implementation plan — the bridge between "understanding the system" and "writing code". Use this whenever the user asks to plan a feature, fix, or refactor; says "what's the plan", "how should we implement this", "break this down", or "next steps"; or when a research phase has just finished and implementation is about to begin. Trigger even if the user doesn't say the word "plan" — any request to figure out how to build something in an already-researched codebase belongs here. Produces a plan only; never writes code.
---

# Coding Plan

You are in the planning phase of a dev workflow: research → **plan** → implement. Your job is to convert the research findings and the user's request into an implementation plan that a developer (or agent) can execute step by step without re-deriving decisions. You do not write code in this phase.

## Inputs

You need two things before planning:

1. **The user's request** — the feature, fix, or refactor being asked for.
2. **Research findings** — the current picture of the system: relevant files, current behavior, data model, conventions, constraints, tests, open questions. These may come from earlier in the conversation, a document the user provides, or exploration already done in this session.

**If the research is missing, thin, or stale** (the request touches areas the findings don't cover, or the code has changed since), do not plan on guesses. Tell the user what's missing and ask whether to research those areas first — or, if you have codebase access, verify the gaps yourself before planning. A plan built on unverified assumptions is worse than no plan.

## Planning process

1. **Restate the goal.** One or two sentences in your own words: what must be true when this work is done. If the request is ambiguous, surface the interpretations and ask — a wrong goal invalidates the whole plan.

2. **Resolve the open questions.** Collect any unknowns or unresolved points the research raised. For each: answer it from the research, mark it as a decision the user must make, or mark it as something to verify during implementation. None may be silently dropped.

3. **Consider approaches.** Identify 2–3 plausible ways to implement the change (e.g., extend an existing module vs. add a new one; migrate data vs. compute on read). Evaluate them against the constraints and conventions from the research. Pick one and say why in a sentence or two. If the tradeoff genuinely depends on priorities only the user knows, present the options and stop for their input instead of choosing.

4. **Checkpoint: clarify with the user.** Before writing the full plan, collect everything from steps 1–3 that needs user input — ambiguous goals, unresolved open questions, priority tradeoffs, irreversible choices — and put it to the user as a short numbered list of concrete questions. For each question: state why it matters in one line, offer the plausible options, and mark which one you'd recommend as a default. Then stop and wait for answers; do not produce the plan with those questions unresolved. Only skip this checkpoint if there is genuinely nothing unclear — and say so explicitly ("No open questions — the request and research fully determine the plan"). Never pad with questions you can answer yourself from the research; every question asked must be one only the user can answer.

5. **Break into steps.** Decompose the chosen approach into small, ordered steps. Each step should be:
   - **Independently verifiable** — it compiles, tests pass, or a behavior can be observed after it.
   - **File-anchored** — names the files to create or change, using paths confirmed by the research.
   - **Convention-following** — points to the prior-art example from the research it should imitate ("follow the pattern in src/handlers/export.ts:20–45").
   - Ordered so the system stays working between steps where possible (e.g., schema/migration before code that uses it; feature flag before risky switchover).

6. **Plan the tests.** For each behavioral change, say what test proves it: which existing tests to extend, what new tests to add, which fixtures/factories from the research to use. Note any existing tests the change will break intentionally.

7. **Assess risk.** Identify what could go wrong — data migrations, breaking API consumers, performance on hot paths, surprising couplings flagged in the research — and pair each risk with a mitigation or a check.

8. **Draw the boundary.** State explicitly what this plan does not cover, especially adjacent improvements that would be tempting scope creep.

## Rules

- **Plan only.** No code, no diffs, no pseudo-implementation beyond a signature or type sketch where naming matters. The output of this phase is the plan document.
- **Ground every step in the research.** File paths, conventions, and constraints must trace back to the report. If a step requires knowledge the research doesn't contain, that's a gap — flag it, don't invent it.
- **Steps sized for one focused change.** If a step's description needs the word "and" more than once, split it.
- **Make decisions visible.** Every judgment call (approach choice, naming, ordering) is stated with its one-line rationale so the implementer can push back before code exists.
- **Ask, don't assume.** Anything unclear — product-level ambiguity, unresolved open questions, irreversible choices (schema design, public API shape), priority tradeoffs — goes to the user at the clarification checkpoint before the plan is written. Guessing on these and burying the guess in the plan is a failure, even if the guess is reasonable. If new ambiguity surfaces mid-planning, pause and ask rather than pushing through.
- **Record the answers.** When the user answers a clarifying question, reflect the decision in the plan (in Goal, Approach, or the relevant step) so the plan is self-contained and the implementer doesn't need the conversation history.

## Plan format

Output the plan in exactly this structure:

```
# Plan: <title>

## Goal
What will be true when this is done. Explicit non-goals if the request
could be read more broadly.

## Approach
The chosen approach and why, plus a one-line note on each alternative
considered and why it lost.

## Decisions made
User answers from the clarification checkpoint, each stated as the
decision taken. Remaining choices deferred to implementation go here
too, marked "deferred". If none, "None — the request fully determined
the plan."

## Steps
1. <Step title>
   - Change: what to do, and in which files (path from research)
   - Pattern: prior-art reference to follow, if any
   - Verify: how to confirm this step worked
2. ...

## Testing
New and modified tests, mapped to the behaviors they prove. Test
utilities/fixtures to reuse.

## Risks
Each risk paired with its mitigation or checkpoint.

## Out of scope
Adjacent work deliberately excluded.
```

Keep the plan tight enough to hold in one head: for most features, 5–10 steps. If it needs more than ~12 steps, propose splitting into phases and plan only the first phase in detail.
