# QVeris Social Studio

A lightweight content workspace for reviewing QVeris data visuals and X post
copy before publishing.

## Run locally

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

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
