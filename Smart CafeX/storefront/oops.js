/* The last line of defence: what happens when the JavaScript throws.
 *
 * WHY THIS FILE EXISTS
 * --------------------
 * The backend has had an unhandled-exception handler since the beginning: a
 * 500 is logged, fingerprinted, recorded and mailed, and the seller is told
 * plainly that it was reported. The browser had nothing at all. So a null that
 * reached `x.name` in a render function threw, the stack unwound, and the half
 * drawn screen simply stopped: no message, no record, and nothing for anyone
 * to act on. The seller sees a spinner that never resolves or a button that
 * does nothing, and the operator never finds out it happened.
 *
 * `api()` in smart.js already handles the failures it can see (a dropped
 * connection is retried, a non-JSON body becomes `{}` rather than throwing),
 * and the code is written defensively with `|| {}` and `|| []` throughout.
 * This is for the ones nobody predicted, which by definition is the whole
 * remaining set.
 *
 * WHAT IT DELIBERATELY DOES NOT DO
 * --------------------------------
 *  * It does not swallow the error. The console still gets it, because that is
 *    where it is debugged from.
 *  * It does not show a dialog for every failure. Most uncaught errors leave a
 *    usable screen behind, and a modal over a working app is worse than the
 *    bug. It uses the app's own toast where there is one, and says nothing at
 *    all where there is not.
 *  * It does not report the same fault twice, or more than a handful per page
 *    load. A throw inside a render loop can fire thousands of times a second,
 *    and a reporter without a ceiling turns one bug into an outage of its own.
 */
(function () {
  "use strict";

  var MAX_PER_PAGE = 5;     // a loop must not become a denial of service
  var sent = 0;
  var seen = Object.create(null);

  function short(v, n) {
    v = (v === null || v === undefined) ? "" : String(v);
    return v.length > n ? v.slice(0, n) : v;
  }

  function report(kind, message, source, line, col, stack) {
    // Deduped on the shape of the fault, not the moment it happened, so the
    // same broken line reported from a loop counts once.
    var key = kind + "|" + message + "|" + source + "|" + line;
    if (seen[key] || sent >= MAX_PER_PAGE) return;
    seen[key] = 1;
    sent += 1;
    try {
      var body = JSON.stringify({
        kind: short(kind, 40),
        message: short(message, 400),
        source: short(source, 300),
        line: line || 0,
        col: col || 0,
        stack: short(stack, 2000),
        page: short(location.pathname + location.search, 300),
        ua: short(navigator.userAgent, 200)
      });
      // keepalive so a fault thrown during a navigation still gets out.
      fetch("/api/client-error", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: body,
        keepalive: true
      }).catch(function () { /* reporting must never raise on its own */ });
    } catch (e) { /* ditto */ }

    // Tell the person something, but only through the app's own toast, and
    // only once. A seller who knows it broke will retry or call; one who
    // watched a button do nothing assumes the product is broken generally.
    try {
      if (sent === 1 && typeof window.toast === "function") {
        window.toast("Something on this screen did not load. It has been "
                     + "reported. Reloading usually clears it.", 6000);
      }
    } catch (e) { /* a broken toast must not re-enter this handler */ }
  }

  window.addEventListener("error", function (e) {
    // Two different events share this name. A genuine uncaught exception has
    // .error; a failed <img>/<script>/<link> fires the same event on the
    // element with no .error, and those are not bugs worth reporting.
    if (!e || (!e.error && !e.message)) return;
    if (e.target && e.target !== window) return;
    report("error", e.message || String(e.error),
           e.filename, e.lineno, e.colno,
           e.error && e.error.stack);
  }, true);

  window.addEventListener("unhandledrejection", function (e) {
    var r = e && e.reason;
    if (!r) return;
    // An api() failure that nobody awaited lands here. Those already carry a
    // readable message and a status, so they are reported as what they are.
    report("unhandledrejection",
           (r && r.message) || String(r),
           (r && r.status !== undefined) ? "api status " + r.status : "",
           0, 0, r && r.stack);
  });
})();
