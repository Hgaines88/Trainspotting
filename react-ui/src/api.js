const API_ROOT = "/api";
let archiveVersionRequest = null;

function isPublicArchiveRead(path, options) {
  const method = String(options.method || "GET").toUpperCase();
  return (
    method === "GET" &&
    (path === "/designers" ||
      path.startsWith("/designers?") ||
      path.startsWith("/designers/") ||
      path === "/collections" ||
      path.startsWith("/collections?") ||
      path.startsWith("/collections/") ||
      path.startsWith("/archive-options/"))
  );
}

function currentArchiveVersion() {
  if (!archiveVersionRequest) {
    archiveVersionRequest = fetch(`${API_ROOT}/archive-version`, { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error("The archive version is unavailable.");
        const payload = await response.json();
        if (!Number.isInteger(payload.version) || payload.version < 1) {
          throw new Error("The archive version is invalid.");
        }
        return payload.version;
      })
      .finally(() => { archiveVersionRequest = null; });
  }
  return archiveVersionRequest;
}

async function versionedPath(path) {
  const version = await currentArchiveVersion();
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}archive_version=${version}`;
}

function describeApiError(detail, fallback) {
  if (typeof detail === "string" && detail) return detail;

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => String(item?.msg || "").replace(/^Value error,\s*/, ""))
      .filter(Boolean);
    if (messages.length) return messages.join(" ");
  }

  return fallback;
}

export async function apiRequest(path, options = {}) {
  const requestPath = isPublicArchiveRead(path, options)
    ? await versionedPath(path)
    : path;
  const response = await fetch(`${API_ROOT}${requestPath}`, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });

  if (response.status === 204) return null;

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    throw new Error(
      payload
        ? describeApiError(payload.detail, "The request could not be completed.")
        : `The request failed (HTTP ${response.status}).`
    );
  }

  return payload;
}
