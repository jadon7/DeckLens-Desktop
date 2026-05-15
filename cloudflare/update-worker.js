const CACHE_METADATA = "no-cache, no-store, must-revalidate";
const CACHE_ARTIFACT = "public, max-age=31536000, immutable";
const RATE_LIMIT_WINDOW_MS = 60 * 1000;
const RATE_LIMIT_REDIRECTS_PER_MINUTE = 30;
const RATE_LIMIT_ARTIFACTS_PER_MINUTE = 120;

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

function clientIp(request) {
  return request.headers.get("CF-Connecting-IP") ||
    request.headers.get("X-Forwarded-For")?.split(",")[0]?.trim() ||
    "unknown";
}

async function checkRateLimit(request, store, scope, limit) {
  if (!store) return null;

  const now = Date.now();
  const bucket = Math.floor(now / RATE_LIMIT_WINDOW_MS);
  const key = `${scope}:${clientIp(request)}:${bucket}`;
  const current = Number(await store.get(key)) || 0;

  if (current >= limit) {
    return new Response("Too many download requests. Please retry later.", {
      status: 429,
      headers: {
        ...baseHeaders(""),
        "Content-Type": "text/plain; charset=utf-8",
        "Retry-After": String(Math.ceil(RATE_LIMIT_WINDOW_MS / 1000))
      }
    });
  }

  await store.put(key, String(current + 1), {
    expirationTtl: Math.ceil(RATE_LIMIT_WINDOW_MS / 1000) + 30
  });

  return null;
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

function parsePreferredArtifactPath(metadata, extension) {
  const escapedExtension = extension.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const pattern = new RegExp(`^\\s*-\\s*url:\\s*(.+${escapedExtension})\\s*$`, "im");
  const match = metadata.match(pattern);
  return match ? match[1].trim().replace(/^["']|["']$/g, "") : "";
}

function parseArtifactDigest(metadata, artifactPath) {
  if (artifactPath) {
    const escapedPath = artifactPath.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const artifactPattern = new RegExp(
      `^\\s*-\\s*url:\\s*${escapedPath}\\s*\\n\\s*sha512:\\s*(.+)$`,
      "im"
    );
    const artifactMatch = metadata.match(artifactPattern);
    if (artifactMatch) {
      return artifactMatch[1].trim().replace(/^["']|["']$/g, "").slice(0, 24);
    }
  }

  const match = metadata.match(/^sha512:\s*(.+)$/m);
  return match ? match[1].trim().replace(/^["']|["']$/g, "").slice(0, 24) : "";
}

function parseRangeHeader(rangeHeader, size) {
  if (!rangeHeader) return null;

  const match = rangeHeader.match(/^bytes=(\d*)-(\d*)$/);
  if (!match) return { error: "Invalid range" };

  const [, rawStart, rawEnd] = match;
  if (!rawStart && !rawEnd) return { error: "Invalid range" };

  if (!rawStart) {
    const suffixLength = Number(rawEnd);
    if (!Number.isInteger(suffixLength) || suffixLength <= 0) return { error: "Invalid range" };
    const offset = Math.max(size - suffixLength, 0);
    return { offset, length: size - offset };
  }

  const offset = Number(rawStart);
  const requestedEnd = rawEnd ? Number(rawEnd) : size - 1;
  if (!Number.isInteger(offset) || !Number.isInteger(requestedEnd) || offset < 0 || requestedEnd < offset) {
    return { error: "Invalid range" };
  }

  if (offset >= size) return { error: "Range not satisfiable" };

  const end = Math.min(requestedEnd, size - 1);
  return { offset, length: end - offset + 1 };
}

async function downloadRedirect(request, env, platform) {
  const limited = await checkRateLimit(
    request,
    env.DECKLENS_RATE_LIMITS,
    "download-redirect",
    RATE_LIMIT_REDIRECTS_PER_MINUTE
  );
  if (limited) return limited;

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

  const metadataText = await metadata.text();
  const artifactPath = platform === "mac"
    ? parsePreferredArtifactPath(metadataText, ".dmg") || parseArtifactPath(metadataText)
    : parseArtifactPath(metadataText);
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
  const digest = parseArtifactDigest(metadataText, artifactPath);
  url.search = digest ? `?v=${encodeURIComponent(digest)}` : "";
  return new Response(null, {
    status: 302,
    headers: {
      ...baseHeaders(metadataKey),
      Location: url.toString()
    }
  });
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

    if (isArtifact(key)) {
      const limited = await checkRateLimit(
        request,
        env.DECKLENS_RATE_LIMITS,
        "download-artifact",
        RATE_LIMIT_ARTIFACTS_PER_MINUTE
      );
      if (limited) return limited;
    }

    const rangeHeader = request.headers.get("Range");
    let requestedRange = null;
    if (rangeHeader) {
      const head = await env.DECKLENS_UPDATES.head(key);
      if (head === null) {
        return new Response("Not found", {
          status: 404,
          headers: {
            ...baseHeaders(key),
            "Content-Type": "text/plain; charset=utf-8"
          }
        });
      }

      requestedRange = parseRangeHeader(rangeHeader, head.size);
      if (requestedRange?.error) {
        return new Response(requestedRange.error, {
          status: requestedRange.error === "Range not satisfiable" ? 416 : 400,
          headers: {
            ...baseHeaders(key),
            "Content-Range": `bytes */${head.size}`,
            "Content-Type": "text/plain; charset=utf-8"
          }
        });
      }
    }

    const object = await env.DECKLENS_UPDATES.get(key, {
      onlyIf: request.headers,
      range: requestedRange || undefined
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

    const hasRange = requestedRange &&
      Number.isFinite(requestedRange.offset) &&
      Number.isFinite(requestedRange.length);

    if (hasRange) {
      const end = requestedRange.offset + requestedRange.length - 1;
      headers.set("Content-Range", `bytes ${requestedRange.offset}-${end}/${object.size}`);
      headers.set("Content-Length", String(requestedRange.length));
    } else {
      headers.set("Content-Length", String(object.size));
    }

    return new Response(request.method === "HEAD" ? null : object.body, {
      status: object.body ? (hasRange ? 206 : 200) : 304,
      headers
    });
  }
};
