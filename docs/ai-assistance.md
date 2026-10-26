# AI assistance and prompts

Codex reviewed the inputs, wrote the implementation/tests/docs, ran commands, diagnosed failures, and summarized results in this conversation. No subagents or external AI classification services were used. Runtime inference is deterministic Python. AI-authored code and tests can share blind spots; passing tests do not prove configured schedules.

Discovery and SPEC were supplied as already completed. Earlier discovery conversations and human effort were unavailable and are not reconstructed. No developer timer was started, so no exact human or total implementation time is asserted. The actual implementation prompt is retained below; the development log records observed mistakes rather than inventing errors to satisfy the assignment.

## Supplied implementation prompt

> I'm working on a take-home assignment for Infinite Lambda's Senior Technical Product Manager position, focused on Flowline.
>
> I've included the assignment materials, run-history dataset, customer feedback, and our SPEC.md. We've already completed the product discovery and agreed on the main product decisions.
>
> I'd like you to implement the solution now, using SPEC.md as our primary contract.
>
> Before coding, please review the specification against the source data and flag any contradictions.
>
> There are four areas I particularly want us to handle carefully:
>
> 1. The 60-minute boundary must remain strict. A genuine recurring schedule faster than 60 minutes cannot be automatically classified as in scope. Distinguish scheduling jitter from actual drift, and escalate ambiguity.
> 2. The proposed minimum evidence thresholds are heuristics. Test whether they behave sensibly, especially for short histories containing clear recurring schedules.
> 3. Retry identification must use the broader recurring pattern and execution statuses. Don't automatically discard executions following failures.
> 4. Explicitly support weekday/business-day schedules. Evaluate expected occurrences against the appropriate calendar pattern, not always against all calendar days.
>
> Keep the implementation simple: a standalone deterministic Python classifier, focused automated tests, a Streamlit review interface, persistent corrections, and a clear README.
>
> Please prioritize the classification engine and its tests before building the interface.
>
> The reviewer should be able to understand why a workflow was classified a certain way, see relevant warnings, and correct the inferred frequency with a reason and supporting source. Preserve the original classification and apply the same eligibility policy after correction.
>
> I've attached the assignment body (the task itself), the run history as a csv and synthetic user feedback.
>
> Use the actual CSV to validate behavior across all 40 workflows. Treat our provisional 30 in-scope, 3 too-frequent, and 7 unknown estimates as hypotheses, not expected answers to hardcode.
>
> When something doesn't match our expectations, investigate the evidence and document the discrepancy rather than changing the logic to make the totals match.
>
> Avoid unnecessary infrastructure, external services, authentication, or AI-based runtime classification.
>
> Please maintain an accurate record of development decisions, AI assistance, and any mistakes discovered during implementation. Don't invent time spent or AI errors.
>
> Start by briefly reporting any issues you find in the specification, then proceed with implementation, testing, and documentation. At the end, show me the classification results, test outcomes, outstanding uncertainties, and how to run the prototype.

Original inputs are retained in the repository. Document instructions were distinguished from this request: assignment contact details did not authorize contacting anyone, and the feedback request to wait for 90 days did not override short-history classification. No runtime model interprets the CSV.

See `development-log.md` for actual diagnoses/fixes, `spec-review.md` for rationale, and `data/classification_results.json` for measured outcomes. The full chat remains with the user; this file does not claim to reproduce every tool call.


## Subsequent review and update prompts

The user requested an independent, critical review of the actual code against the assignment, SPEC and six feedback messages, focusing on unsafe approvals, retries, the boundary, calendars, invalid records, audit preservation, reproducibility and documentation. The review was another adversarial pass by the same Codex assistant, not an independent human or second-model certification. Its concrete counterexamples exposed bugs not covered by the original 59 passing tests.

The user's update instruction was: “Alright, I agree with all of your findings. Update the project and re-run the tests.” Codex implemented the focused fixes and regression tests documented in `review-fixes.md`, updated the evidence and documentation, and reran the complete suite. Earlier statements about 59 tests describe the historical baseline; the current suite has 72 passing tests. Actual human time spent remains unavailable and has not been invented.


## Final submission pass

The candidate requested a final submission-readiness pass: synchronize the compact SPEC with implementation, document PowerShell and Unix commands, audit assignment deliverables/AI records/tracked files, run the complete suite, verify all generated results, and commit/push documentation-only changes to `flowline-prototype` without merging `main`. They confirmed that the prototype runs locally on Windows. Codex did not independently execute PowerShell or macOS; the documented commands use the actual Python/venv paths and pinned dependency file. No runtime or classifier changes were made in this pass. The original spec was archived verbatim; SPEC.md is now the final behavior contract. Raw runner logs were removed from the tracked submission.

### TODO — candidate-supplied information before submission

- **Time spent:** TODO: supply your recorded duration or an honest, explicitly labeled estimate. Include discovery, implementation/AI interaction, review/fixes, and manual testing as appropriate; identify the total and avoid double-counting overlapping activities. None of these durations was provided to the assistant. Do not use test runtimes or the assignment's suggested four hours as measured effort.
- **Earlier discovery AI prompts/conversations:** TODO: attach the actual earlier prompt record if available. If unavailable, explicitly confirm that fact; the supplied implementation prompt and summarized subsequent review instructions above are the records available in this session. No missing conversation has been reconstructed.

This record includes the original implementation prompt verbatim and labels later prompts as summaries/quotations. It is not a complete tool-call transcript or independent human certification. Actual AI errors are documented in the development log and review-fixes record.
