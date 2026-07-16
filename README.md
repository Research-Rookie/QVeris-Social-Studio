# QVeris Social Studio

A daily archive for reviewing QVeris-powered market visuals and social post drafts.

## Run locally

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

## Daily pipeline

```bash
python scripts/fetch_rankings.py
python scripts/generate_image.py
python scripts/generate_tweet.py
```

The pipeline fetches the latest Top 5 gainers through QVeris, creates a dated
image and social post draft, then upserts that market date in `data/posts.json`. Images are archived
under `public/posts/`. Running the same date again updates only that date;
older cards remain intact.

For GitHub Actions, add this repository secret:

```text
QVERIS_API_KEY
```

The workflow runs every day at 08:30 Asia/Shanghai.
Automatic X publishing has been removed. When the workflow commits a new card,
a connected Vercel project will rebuild the website automatically.

## Prediction Market Pulse

```bash
python scripts/fetch_prediction_markets.py
python scripts/generate_prediction_market_image.py
python scripts/generate_prediction_market_tweet.py
```

This pipeline uses QVeris to discover active prediction-market events, renders a
daily probability pulse card, and archives a social post draft.

## Market Narrative Shift

```bash
python scripts/fetch_financial_news_signal.py
python scripts/build_market_narrative_shift.py
python scripts/generate_market_narrative_shift_image.py
python scripts/generate_market_narrative_shift_tweet.py
```

This pipeline automatically selects a well-covered ticker, compares its latest
news language, themes, and sentiment with the most recent archived baseline,
then generates a 1200x675 visual and a review-ready social post. When no prior
coverage exists, the card says that the baseline is being built instead of
claiming a change that the data cannot support.

## API sources

The current project keeps finance data centralized through QVeris:

```text
QVERIS_API_KEY
```

QVeris is used for:

- Daily U.S. stock movers
- FCF Yield comparisons
- Prediction Market Pulse events and implied probabilities

Optional Typefully draft creation uses:

```text
TYPEFULLY_API_KEY
TYPEFULLY_SOCIAL_SET_ID
```

## Deploy to Vercel

1. Import the `qveris-social-studio` folder into Vercel.
2. Keep the default Next.js build settings.
3. Deploy.

## Publishing workflow

### Manual publishing

- The website generates and displays the image and post copy.
- A person checks the numbers.
- Use `Copy text` and `Download image`, then publish on X manually.

### Optional Typefully draft

- Run the `Send Selected Card to Typefully` workflow.
- Provide the card `post_id`.
- Review the Typefully draft before publishing.

Never expose API secrets in browser code or commit them to the repository.
