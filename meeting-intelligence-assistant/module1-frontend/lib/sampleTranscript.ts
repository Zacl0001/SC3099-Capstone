// Example transcript offered on the upload form for quick demos.
// Uses module2's required format: every line is "Speaker: text".

export const SAMPLE_TRANSCRIPT_TITLE = 'Project Alpha – Launch Planning';

export const SAMPLE_TRANSCRIPT = `Alice: Morning everyone. Today we need to finalise the launch plan for Project Alpha and review the payment integration status.
Mike: The payment integration is about 80 percent done. The remaining work is the refund flow and the webhook retries.
Alice: Is that going to be ready for the original launch date on the 12th?
Mike: Honestly no. The refund flow touches the ledger service and we found a bug in the reconciliation job last week.
Priya: QA also needs at least three days for regression testing once payments are complete.
Alice: Then I think we should move the launch. Does Friday the 19th work for everyone?
Mike: Friday the 19th works if I can finish payments by the 15th.
Priya: That gives QA enough time.
Alice: Okay, we have decided to postpone the launch to Friday the 19th.
Alice: Next, marketing. Daniel, where are we with the announcement?
Daniel: The blog post and email campaign are drafted. I need final screenshots of the checkout page.
Mike: I will send Daniel the updated checkout screenshots by Wednesday.
Daniel: Great. I'll also update the launch date in the press kit by Thursday.
Priya: One risk: the mobile app still points to the old pricing API. If we launch without fixing that, mobile users will see the wrong prices.
Alice: Good catch. We agreed last month that pricing comes from a single API, so the mobile app has to switch before launch.
Mike: Our team can take that, but we will need an extra engineer for two days.
Alice: I'll ask Sarah to lend us one engineer from the platform team. Let's go with that plan.
Priya: I will prepare the regression test plan and share it with the team by Monday.
Alice: Last item, the budget. We are slightly over on cloud costs because of the load testing environment.
Mike: We can shut down the load testing cluster after the launch. That should save around two thousand dollars a month.
Alice: Agreed. The decision is to decommission the load testing cluster one week after launch.
Daniel: Should we also run a post-launch survey?
Alice: Yes, Daniel will draft the survey questions by next Friday.
Alice: Thanks everyone. To recap: launch moves to the 19th, Mike finishes payments by the 15th, and Priya owns the regression plan.
`;
