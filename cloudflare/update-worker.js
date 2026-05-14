const CACHE_METADATA = "no-cache, no-store, must-revalidate";
const CACHE_ARTIFACT = "public, max-age=31536000, immutable";

const CONTENT_TYPES = {
  ".yml": "text/yaml; charset=utf-8",
  ".yaml": "text/yaml; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".zip": "application/zip",
  ".dmg": "application/x-apple-diskimage",
  ".exe": "application/vnd.microsoft.portable-executable",
  ".blockmap": "application/octet-stream"
};

function contentTypeFor(key) {
  const lower = key.toLowerCase();
  const extension = Object.keys(CONTENT_TYPES).find((ext) => lower.endsWith(ext));
  return extension ? CONTENT_TYPES[extension] : "application/octet-stream";
}

function cacheControlFor(key) {
  return /^latest.*\.ya?ml$/i.test(key) ? CACHE_METADATA : CACHE_ARTIFACT;
}

function isArtifact(key) {
  return /\.(dmg|zip|exe|blockmap)$/i.test(key);
}

function baseHeaders(key) {
  return {
    "Access-Control-Allow-Origin": "*",
    "Cache-Control": key ? cacheControlFor(key) : CACHE_METADATA,
    "X-Content-Type-Options": "nosniff",
    "Accept-Ranges": "bytes"
  };
}

function downloadMetadataKey(platform) {
  return platform === "windows" ? "latest.yml" : "latest-mac.yml";
}

function platformFromRequest(request) {
  const ua = request.headers.get("User-Agent") || "";
  return /Windows/i.test(ua) ? "windows" : "mac";
}

function parseArtifactPath(metadata) {
  const match = metadata.match(/^path:\s*(.+)$/m);
  return match ? match[1].trim().replace(/^["']|["']$/g, "") : "";
}

async function downloadRedirect(request, env, platform) {
  const metadataKey = downloadMetadataKey(platform);
  const metadata = await env.DECKLENS_UPDATES.get(metadataKey);
  if (metadata === null) {
    return new Response(`No ${platform} release is available yet`, {
      status: 404,
      headers: {
        ...baseHeaders(metadataKey),
        "Content-Type": "text/plain; charset=utf-8"
      }
    });
  }

  const artifactPath = parseArtifactPath(await metadata.text());
  if (!artifactPath) {
    return new Response(`Release metadata is missing an artifact path: ${metadataKey}`, {
      status: 502,
      headers: {
        ...baseHeaders(metadataKey),
        "Content-Type": "text/plain; charset=utf-8"
      }
    });
  }

  const url = new URL(request.url);
  url.pathname = `/${artifactPath}`;
  url.search = "";
  return Response.redirect(url.toString(), 302);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const key = decodeURIComponent(url.pathname.replace(/^\/+/, ""));

    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
          "Access-Control-Allow-Headers": "If-None-Match, If-Modified-Since, Range"
        }
      });
    }

    if (!["GET", "HEAD"].includes(request.method)) {
      return new Response("Method not allowed", {
        status: 405,
        headers: baseHeaders(key)
      });
    }

    if (key === "download") {
      return downloadRedirect(request, env, platformFromRequest(request));
    }

    if (key === "download/mac") {
      return downloadRedirect(request, env, "mac");
    }

    if (key === "download/windows") {
      return downloadRedirect(request, env, "windows");
    }

    if (!key) {
      return new Response("DeckLens update feed", {
        status: 200,
        headers: {
          ...baseHeaders(key),
          "Content-Type": "text/plain; charset=utf-8"
        }
      });
    }

    const object = await env.DECKLENS_UPDATES.get(key, {
      onlyIf: request.headers,
      range: request.headers
    });

    if (object === null) {
      return new Response("Not found", {
        status: 404,
        headers: {
          ...baseHeaders(key),
          "Content-Type": "text/plain; charset=utf-8"
        }
      });
    }

    const headers = new Headers(baseHeaders(key));
    object.writeHttpMetadata(headers);
    headers.set("Content-Type", headers.get("Content-Type") || contentTypeFor(key));
    headers.set("ETag", object.httpEtag);
    if (isArtifact(key) && !headers.has("Content-Disposition")) {
      headers.set("Content-Disposition", `attachment; filename="${key.split("/").pop()}"`);
    }

    const hasRange = object.range &&
      Number.isFinite(object.range.offset) &&
      Number.isFinite(object.range.end);

    if (hasRange) {
      headers.set("Content-Range", `bytes ${object.range.offset}-${object.range.end - 1}/${object.size}`);
    }

    return new Response(request.method === "HEAD" ? null : object.body, {
      status: object.body ? (hasRange ? 206 : 200) : 304,
      headers
    });
  }
};
