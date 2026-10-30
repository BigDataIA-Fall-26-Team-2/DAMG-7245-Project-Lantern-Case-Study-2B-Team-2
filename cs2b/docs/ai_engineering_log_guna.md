# AI Engineering Log: Guna (Part 0, Part 4, the app, issue drafts)

I used Claude (Anthropic) as a pair programmer for my parts. This log says what I asked it to do, what I decided and checked myself, and where the AI was wrong and how I caught it. Every number below comes from my own terminal output or from filings I opened myself.

## How I worked with the AI

I discussed the approach first and only ran something after I understood it. The AI wrote drafts of scripts, app code and documents. I ran everything on my laptop, read the outputs, pasted them back, and decided what to keep. When something did not look right I made it prove the claim with a command before I acted on it.

## Part 0: setup, acquisition and provenance

What I did:
- Decided to use all three monthly ZIPs (2026_04, 2026_05, 2026_06) as our quarter, because Canvas gives Team 2 the quarter 2026q2 and in 2026 the SEC publishes monthly. I asked the TA, who said the kit can take a list or the months can be combined.
- Set up the new private team repo with the starter kit in cs2b/, after the TA said CS2 must be in a new repo. I checked that no lab leftovers went in by comparing with the kit's own git history.
- Ran the download for all three ZIPs, wrote one manifest with a SHA-256 per file, tracked data/raw with DVC (33 files, 664 MB) and pushed to the team bucket with my own access key.
- Ran the fresh-clone test myself: dvc pull fetched 30 files and added 33, and verify_manifest returned no mismatches.

Where the AI helped: the download script, the DVC commands, the manifest check.

What I decided against the AI's first idea: when three checker tests failed with real data, the first suggestion was to turn use_fixture back on. I refused, because that would make tests pass by running on fake data. We changed only the test's own temporary copy instead, and our real settings stayed on real data.

What the AI got wrong: it suggested allow_anonymous_login = true in the DVC config. With that, DVC ignored my key and every push failed with 403. I tested the key directly with a small script (it could list, write and delete in the bucket), which showed the key was fine and the setting was the problem. We switched it off in the local config and the push worked.

## Part 4: verify your dependency

What I did:
- Checked every sampled holding by hand in the filings: 20 in the first sample, then 9 new ones after the panel changed to 101 admitted filings. Result: 19 of 20 match fair value and principal.
- Found the things the AI could not see without the filings: BlackRock and Onex report in plain dollars, not thousands; for Bluefin and IMB Midco the first search hit was the December schedule, and the March line was the right one; the IMB Midco revolver was on the next page; the Smarsh identifier ending in "Two" pointed to the third line, not the second.
- Found that a sampled "holding" (T Series, Cerity Partners revolver) was a row from the unfunded commitments table. Dhruvi turned this into rule_commitment_rows.
- Found row 14: Great Elm's CLO Formation JV common equity, where the filing column is "Par Amount / Quantity" and 166 is a unit count stored as principal. I took the screenshot of the column header that proved it.

Where the AI helped: the sampler script, the comparison commands, and drafting dependency_check.md from my notes.

What the AI got wrong: the first sampler overwrote reviewed results on every run. A teammate's review caught it, and we changed it to write a separate file and refuse to overwrite completed reviews.

## The app (frontend, backend)

The TA said the case study needs a full application with a frontend, backend and deployment. I set the requirements from our code review comments: more options for the user, less static, and configurable from Streamlit.

What I did:
- Decided the direction of the UI: follow the pipeline in order, show one step at a time and unfold the rest as the user clicks, plain words instead of jargon, fewer columns, and the hand checks as one table where the same row lines up for our values and the filing's values.
- Tested every version locally and reported each error back: the missing __init__.py, a JSON error when the backend failed, a pandas dtype error on triage categories, the Refresh button crash, June showing nothing (it has no reports with a schedule).
- Showed the app to a teammate, collected what confused them, and asked for the changes.
- Merged my app branch with Lokesh's app changes, ran the tests (53/53) and checked the app again before pushing.

Where the AI helped: most of the code in app/api.py, app/engine.py and app/ui.py, and the Swagger documentation.

What the AI got wrong and I caught: it sent commit commands without a branch check, so I asked that every commit start with git branch --show-current; it twice said files were attached when they were not; a dollar sign in the UI text was shown as a maths formula.

## Reviews I did

- Lokesh's Part 3 PR #37 and triage PR #42: ran the tests, the self-check, checked .dvc/config did not change, and tested the app on his branch before approving.
- Shravya's PR #38 (agreement report): checked her three gaps against coverage.csv.
- Shravya's PR #40 (pipeline): found that on Windows every stage reruns once because Git turns line endings into CRLF, with identical results.

## Checking claims before acting on them

Near the deadline the AI listed three risks: the self-check at 9/10, the tag name, and no video link. I asked it to prove each one on main before I sent anything to the team. We checked with git ls-remote, the README on origin/main, the triage file on origin/main and the self-check, and all three were confirmed. One detail changed: the 9/10 comes from our team's stricter check (it only accepts reviewed triage notes), not from missing categories.

## What I take from this

The AI was fast at writing code and documents, but it could not open the filings or see my screen, and it was confidently wrong a few times. The parts that mattered most, reading the filings, deciding what not to do, and checking every claim, were mine.
