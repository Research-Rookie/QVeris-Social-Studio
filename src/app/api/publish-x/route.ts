import { NextRequest, NextResponse } from "next/server";
import { TwitterApi } from "twitter-api-v2";
import fs from "node:fs";
import path from "node:path";
import postsData from "../../../../data/posts.json";

export const runtime = "nodejs";

type Post = {
  id: string;
  tweet: string;
  image: string;
  xPostId?: string | null;
};

const posts = postsData as Post[];

function requireEnv(name: string) {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing server environment variable: ${name}`);
  }
  return value;
}

function verifyPublishToken(token: unknown) {
  const expected = process.env.X_PUBLISH_TOKEN;
  if (!expected) {
    throw new Error("Missing server environment variable: X_PUBLISH_TOKEN");
  }
  if (typeof token !== "string" || token !== expected) {
    throw new Error("Invalid publish token");
  }
}

function resolvePublicImage(image: string) {
  const normalized = image.replace(/^\/+/, "");
  const imagePath = path.join(process.cwd(), "public", normalized);
  const publicRoot = path.join(process.cwd(), "public");
  if (!imagePath.startsWith(publicRoot) || !fs.existsSync(imagePath)) {
    throw new Error(`Image not found: ${image}`);
  }
  return imagePath;
}

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as {
      postId?: string;
      tweet?: string;
      publishToken?: string;
    };

    verifyPublishToken(body.publishToken);

    const post = posts.find((item) => item.id === body.postId);
    if (!post) {
      return NextResponse.json({ error: "Post not found" }, { status: 404 });
    }
    if (post.xPostId) {
      return NextResponse.json(
        { error: "Post already has an xPostId", xPostId: post.xPostId },
        { status: 409 },
      );
    }

    const tweet = (body.tweet || post.tweet || "").trim();
    if (!tweet) {
      return NextResponse.json({ error: "Tweet text is empty" }, { status: 400 });
    }
    if (tweet.length > 280) {
      return NextResponse.json(
        { error: `Tweet is ${tweet.length} characters; limit is 280` },
        { status: 400 },
      );
    }

    const client = new TwitterApi({
      appKey: requireEnv("X_API_KEY"),
      appSecret: requireEnv("X_API_SECRET"),
      accessToken: requireEnv("X_ACCESS_TOKEN"),
      accessSecret: requireEnv("X_ACCESS_SECRET"),
    });

    const mediaId = await client.v1.uploadMedia(resolvePublicImage(post.image));
    const response = await client.v2.tweet({
      text: tweet,
      media: { media_ids: [mediaId] },
    });

    return NextResponse.json({
      ok: true,
      postId: post.id,
      xPostId: response.data.id,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown publish error";
    const status = message.includes("Invalid publish token") ? 401 : 500;
    return NextResponse.json({ error: message }, { status });
  }
}
