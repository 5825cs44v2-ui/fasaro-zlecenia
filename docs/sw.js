/* Service worker — aplikacja działa też przy słabym internecie. */
"use strict";

var VERSION = "fasaro-zlecenia-v2";
var SHELL = [
  "./",
  "./index.html",
  "./style.css",
  "./app.js",
  "./manifest.webmanifest",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./icons/icon-maskable-512.png",
  "./icons/apple-touch-icon.png",
  "./icons/favicon-32.png",
];

self.addEventListener("install", function (event) {
  event.waitUntil(
    caches
      .open(VERSION)
      .then(function (cache) {
        return cache.addAll(SHELL);
      })
      .then(function () {
        return self.skipWaiting();
      })
  );
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches
      .keys()
      .then(function (keys) {
        return Promise.all(
          keys.map(function (key) {
            if (key !== VERSION) return caches.delete(key);
            return null;
          })
        );
      })
      .then(function () {
        return self.clients.claim();
      })
  );
});

self.addEventListener("fetch", function (event) {
  var request = event.request;
  if (request.method !== "GET") return;

  var url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (url.pathname.indexOf("/data/") !== -1) {
    event.respondWith(networkFirst(request));
    return;
  }

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(function () {
        return caches.match("./index.html");
      })
    );
    return;
  }

  event.respondWith(cacheFirst(request));
});

function networkFirst(request) {
  return caches.open(VERSION).then(function (cache) {
    return fetch(request, { cache: "no-store" })
      .then(function (response) {
        if (response && response.ok) cache.put(request, response.clone());
        return response;
      })
      .catch(function () {
        return cache.match(request, { ignoreSearch: true }).then(function (cached) {
          return cached || new Response("{}", { headers: { "Content-Type": "application/json" } });
        });
      });
  });
}

function cacheFirst(request) {
  return caches.open(VERSION).then(function (cache) {
    return cache.match(request).then(function (cached) {
      if (cached) return cached;
      return fetch(request).then(function (response) {
        if (response && response.ok) cache.put(request, response.clone());
        return response;
      });
    });
  });
}
