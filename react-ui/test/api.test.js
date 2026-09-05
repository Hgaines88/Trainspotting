import assert from "node:assert/strict";
import { afterEach, test } from "node:test";

import { apiRequest } from "../src/api.js";

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
});

test("public archive reads use the current archive version", async () => {
  const requests = [];
  globalThis.fetch = async (url, options = {}) => {
    requests.push({ url, options });
    if (url === "/api/archive-version") {
      return new Response(JSON.stringify({ version: 7 }), { status: 200 });
    }
    return new Response(JSON.stringify([]), { status: 200 });
  };

  assert.deepEqual(await apiRequest("/designers"), []);
  assert.deepEqual(
    requests.map(({ url }) => url),
    ["/api/archive-version", "/api/designers?archive_version=7"]
  );
  assert.equal(requests[0].options.cache, "no-store");
});

test("the public collection list uses the current archive version", async () => {
  const requests = [];
  globalThis.fetch = async (url) => {
    requests.push(url);
    if (url === "/api/archive-version") {
      return new Response(JSON.stringify({ version: 8 }), { status: 200 });
    }
    return new Response(JSON.stringify([]), { status: 200 });
  };

  assert.deepEqual(await apiRequest("/collections"), []);
  assert.deepEqual(requests, [
    "/api/archive-version",
    "/api/collections?archive_version=8",
  ]);
});

test("parallel public reads share one in-flight archive version lookup", async () => {
  const requests = [];
  globalThis.fetch = async (url) => {
    requests.push(url);
    if (url === "/api/archive-version") {
      return new Response(JSON.stringify({ version: 11 }), { status: 200 });
    }
    return new Response(JSON.stringify({ items: [] }), { status: 200 });
  };

  await Promise.all([
    apiRequest("/designers?page=1"),
    apiRequest("/collections?sort=newest"),
  ]);

  assert.equal(requests.filter((url) => url === "/api/archive-version").length, 1);
  assert.ok(requests.includes("/api/designers?page=1&archive_version=11"));
  assert.ok(requests.includes("/api/collections?sort=newest&archive_version=11"));
});

test("later public reads refresh the archive version", async () => {
  let version = 20;
  const versionRequests = [];
  globalThis.fetch = async (url) => {
    if (url === "/api/archive-version") {
      versionRequests.push(url);
      return new Response(JSON.stringify({ version: version++ }), { status: 200 });
    }
    return new Response(JSON.stringify([]), { status: 200 });
  };

  await apiRequest("/designers");
  await apiRequest("/designers");

  assert.equal(versionRequests.length, 2);
});

test("archive selector searches use the current archive version", async () => {
  const requests = [];
  globalThis.fetch = async (url) => {
    requests.push(url);
    if (url === "/api/archive-version") {
      return new Response(JSON.stringify({ version: 9 }), { status: 200 });
    }
    return new Response(JSON.stringify([]), { status: 200 });
  };

  await apiRequest("/archive-options/designers?search=grace&limit=20");

  assert.deepEqual(requests, [
    "/api/archive-version",
    "/api/archive-options/designers?search=grace&limit=20&archive_version=9",
  ]);
});

test("archive discovery queries retain filters and use the current version", async () => {
  const requests = [];
  globalThis.fetch = async (url) => {
    requests.push(url);
    if (url === "/api/archive-version") {
      return new Response(JSON.stringify({ version: 10 }), { status: 200 });
    }
    return new Response(JSON.stringify({ items: [], pagination: {} }), {
      status: 200,
    });
  };

  await apiRequest("/designers?search=McQueen&page=2&page_size=12");

  assert.deepEqual(requests, [
    "/api/archive-version",
    "/api/designers?search=McQueen&page=2&page_size=12&archive_version=10",
  ]);
});

test("mutation requests do not fetch or append an archive version", async () => {
  const requests = [];
  globalThis.fetch = async (url, options = {}) => {
    requests.push({ url, options });
    return new Response(JSON.stringify({ id: 4 }), { status: 201 });
  };

  await apiRequest("/designers", {
    method: "POST",
    body: JSON.stringify({ full_name: "Test Designer" }),
  });

  assert.equal(requests.length, 1);
  assert.equal(requests[0].url, "/api/designers");
});

test("an invalid archive version stops the public request", async () => {
  globalThis.fetch = async () =>
    new Response(JSON.stringify({ version: "invalid" }), { status: 200 });

  await assert.rejects(
    apiRequest("/designers"),
    /The archive version is invalid\./
  );
});
