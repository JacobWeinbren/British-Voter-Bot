/**
 * The hourly trigger for the British Voter Bot.
 *
 * GitHub's own cron used to run the posting workflow and stopped delivering: every tick landed on
 * 23-25 August, then 7 of 8 on the 26th, none on the 27th, and 3 of the ~96 asked for over the 28th
 * and 29th. Nothing in the repo explained it, and asking for more ticks made it worse. So the clock
 * lives here instead, and .github/workflows/post.yml has no `schedule:` block at all.
 *
 * This Worker does not decide whether a card goes out. It only asks GitHub to run the workflow; the
 * workflow's own `python -m voterbot due` weighs the posting ledger and the Bluesky feed and posts
 * at most one card per slot. That is what makes the trigger safe to fire bluntly: a run that fires
 * twice, fires late, or fires when the slot is already filled costs a few seconds and does nothing.
 */

const GITHUB_API = "https://api.github.com";

async function dispatch(env) {
	const response = await fetch(`${GITHUB_API}/repos/${env.REPO}/actions/workflows/${env.WORKFLOW}/dispatches`, {
		method: "POST",
		headers: {
			Authorization: `Bearer ${env.GITHUB_TOKEN}`,
			Accept: "application/vnd.github+json",
			"X-GitHub-Api-Version": "2022-11-28",
			"User-Agent": "british-voter-bot-trigger", // GitHub rejects an API call with no User-Agent
			"Content-Type": "application/json",
		},
		// No `inputs`: the workflow's `force` input defaults to false, so the run checks the slot
		// rather than posting on sight. Forcing a card out is a job for the Actions tab, by hand.
		body: JSON.stringify({ ref: env.BRANCH }),
	});

	// A dispatch that works returns 204 with no body. Throwing on anything else marks the scheduled
	// invocation failed, which is visible in the Worker's logs; a swallowed 401 would not be.
	if (response.status !== 204) {
		const body = await response.text();
		throw new Error(`dispatch failed: ${response.status} ${response.statusText} ${body.slice(0, 300)}`);
	}
}

export default {
	async scheduled(event, env) {
		await dispatch(env);
		console.log(`asked ${env.REPO} to run ${env.WORKFLOW} on ${env.BRANCH}`);
	},
};
