# QVeris Social Studio

A daily archive for reviewing QVeris market visuals and X post drafts.

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

The pipeline fetches the latest Top 5 gainers, creates a dated image and X
draft, then upserts that market date in `data/posts.json`. Images are archived
under `public/posts/`. Running the same date again updates only that date;
older cards remain intact.

For GitHub Actions, add this repository secret:

```text
ALPHA_VANTAGE_API_KEY
```

The workflow runs every day at 08:30 Asia/Shanghai.
Automatic X publishing is intentionally disabled. When the workflow commits a
new card, a connected Vercel project will rebuild the website automatically.

## Deploy to Vercel

1. Import the `qveris-social-studio` folder into Vercel.
2. Keep the default Next.js build settings.
3. Deploy.

## Publishing roadmap

### Phase 1: Manual publishing

- The website generates and displays the image and post copy.
- A person checks the numbers.
- Use `Copy text` and `Download image`, then publish on X manually.

### Phase 2: One-click publishing

- Create an X developer project and app.
- Add OAuth credentials as Vercel environment variables.
- Add a protected server API route that uploads the image and creates the post.
- Keep a confirmation button before publishing.

### Phase 3: Automatic publishing

- A scheduled job fetches the latest approved data.
- Validation checks freshness, duplicate content, missing images, and numbers.
- The job creates the visual and post copy.
- Low-risk posts publish automatically; sensitive posts remain in review.

Never expose X API secrets in browser code or commit them to the repository.
