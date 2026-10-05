// Example transcript offered on the upload form for quick demos.

export const SAMPLE_TRANSCRIPT_TITLE = 'Project Alpha – Launch Planning';

export const SAMPLE_TRANSCRIPT = `[00:00:05] Alice: Morning everyone. Today we need to finalise the launch plan for Project Alpha and review the payment integration status.
[00:00:21] Mike: The payment integration is about 80 percent done. The remaining work is the refund flow and the webhook retries.
[00:00:40] Alice: Is that going to be ready for the original launch date on the 12th?
[00:00:52] Mike: Honestly no. The refund flow touches the ledger service and we found a bug in the reconciliation job last week.
[00:01:15] Priya: QA also needs at least three days for regression testing once payments are complete.
[00:01:34] Alice: Then I think we should move the launch. Does Friday the 19th work for everyone?
[00:01:45] Mike: Friday the 19th works if I can finish payments by the 15th.
[00:01:58] Priya: That gives QA enough time.
[00:02:06] Alice: Okay, we have decided to postpone the launch to Friday the 19th.
[00:02:20] Alice: Next, marketing. Daniel, where are we with the announcement?
[00:02:31] Daniel: The blog post and email campaign are drafted. I need final screenshots of the checkout page.
[00:02:47] Mike: I will send Daniel the updated checkout screenshots by Wednesday.
[00:03:02] Daniel: Great. I'll also update the launch date in the press kit by Thursday.
[00:03:15] Priya: One risk: the mobile app still points to the old pricing API. If we launch without fixing that, mobile users will see the wrong prices.
[00:03:36] Alice: Good catch. We agreed last month that pricing comes from a single API, so the mobile app has to switch before launch.
[00:03:52] Mike: Our team can take that, but we will need an extra engineer for two days.
[00:04:05] Alice: I'll ask Sarah to lend us one engineer from the platform team. Let's go with that plan.
[00:04:20] Priya: I will prepare the regression test plan and share it with the team by Monday.
[00:04:38] Alice: Last item, the budget. We are slightly over on cloud costs because of the load testing environment.
[00:04:55] Mike: We can shut down the load testing cluster after the launch. That should save around two thousand dollars a month.
[00:05:10] Alice: Agreed. The decision is to decommission the load testing cluster one week after launch.
[00:05:24] Daniel: Should we also run a post-launch survey?
[00:05:31] Alice: Yes, Daniel will draft the survey questions by next Friday.
[00:05:43] Alice: Thanks everyone. To recap: launch moves to the 19th, Mike finishes payments by the 15th, and Priya owns the regression plan.
`;
