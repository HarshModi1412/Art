/* Cookie consent, and the analytics it gates.
 *
 * WHY THIS FILE EXISTS AND WHAT IT REFUSES TO DO
 * ----------------------------------------------
 * No Indian law requires a cookie banner. What requires one here is Google
 * Analytics: it sets cookies, and the moment a visitor arrives from the EU or
 * the UK the ePrivacy Directive needs their permission BEFORE the tracker
 * loads, not after. So this script's actual job is to not load something.
 *
 * The rules it follows, each of which is the thing regulators actually fine:
 *
 *   1. Nothing non-essential runs before a choice is made. GA4 is injected by
 *      this file and by nothing else, so "reject" genuinely means no request to
 *      Google rather than a request with a flag on it.
 *   2. Reject is as prominent as Accept. Same size, same weight, side by side,
 *      first layer. An Accept button next to a faint "Manage settings" link is
 *      the single most-penalised pattern in Europe.
 *   3. Nothing is pre-ticked. Consumer Protection (E-commerce) Rule 4(9) bans
 *      pre-ticked consent boxes in India too, so this is not an EU-only point.
 *   4. Withdrawal is as easy as consent. A permanent footer link reopens this,
 *      and rejecting later removes the cookies that were already set.
 *   5. What was consented to is recorded: the choice, when, and which version
 *      of the notice was shown. Article 7(1) requires being able to demonstrate
 *      consent, and "the user must have clicked something" is not a record.
 *   6. Google Consent Mode v2 is signalled, with everything denied by default,
 *      before any Google tag could read it.
 *
 * Deliberately not used: a third-party consent platform. Every one of them is
 * itself a third-party script that loads before consent, which is the problem.
 */
(function () {
  "use strict";

  var KEY = "cx_consent";
  // Bumping this re-asks everybody. Do it when the categories or the third
  // parties change, because consent to an older notice is not consent to this
  // one.
  var NOTICE_VERSION = 1;

  // Consent Mode v2 defaults, set before anything Google-shaped could look.
  // Denied until told otherwise; this is what makes the default state lawful.
  window.dataLayer = window.dataLayer || [];
  function gtag() { window.dataLayer.push(arguments); }
  window.gtag = window.gtag || gtag;
  gtag("consent", "default", {
    ad_storage: "denied",
    ad_user_data: "denied",
    ad_personalization: "denied",
    analytics_storage: "denied",
    functionality_storage: "granted",  // keeps you signed in; strictly necessary
    security_storage: "granted",
    wait_for_update: 500
  });

  function read() {
    try {
      var raw = localStorage.getItem(KEY);
      if (!raw) return null;
      var v = JSON.parse(raw);
      // A record from an older notice is not a decision about this one.
      if (!v || v.version !== NOTICE_VERSION) return null;
      return v;
    } catch (e) { return null; }
  }

  function write(analytics) {
    var record = {
      version: NOTICE_VERSION,
      analytics: !!analytics,
      at: new Date().toISOString(),
      // Recorded so a later question of "what did they agree to" has an answer
      // that does not depend on remembering what the banner said that month.
      categories: { necessary: true, analytics: !!analytics }
    };
    try { localStorage.setItem(KEY, JSON.stringify(record)); } catch (e) {}
    return record;
  }

  /* Analytics is injected here and nowhere else. That is the whole mechanism:
     if this function is not called, no request reaches Google. */
  var loaded = false;
  function loadAnalytics(id) {
    if (loaded || !id) return;
    loaded = true;
    gtag("consent", "update", { analytics_storage: "granted" });
    var s = document.createElement("script");
    s.async = true;
    s.src = "https://www.googletagmanager.com/gtag/js?id=" + encodeURIComponent(id);
    document.head.appendChild(s);
    gtag("js", new Date());
    // IP anonymisation on, no ad signals, and no cross-site joining. None of
    // that is required of us, and all of it reduces what we are responsible for.
    gtag("config", id, {
      anonymize_ip: true,
      allow_google_signals: false,
      allow_ad_personalization_signals: false
    });
  }

  /* Rejecting after having accepted has to actually remove what was set, or
     "withdraw" means nothing. GA4's cookies are first-party, so we can. */
  function clearAnalyticsCookies() {
    gtag("consent", "update", { analytics_storage: "denied" });
    var host = location.hostname;
    var domains = ["", host, "." + host];
    var parts = host.split(".");
    if (parts.length > 2) domains.push("." + parts.slice(-2).join("."));
    document.cookie.split(";").forEach(function (c) {
      var name = c.split("=")[0].trim();
      if (!/^_ga/.test(name) && !/^_gid$/.test(name)) return;
      domains.forEach(function (d) {
        document.cookie = name + "=; Max-Age=0; path=/" + (d ? "; domain=" + d : "");
      });
    });
  }

  function styles() {
    if (document.getElementById("cxConsentCss")) return;
    var css = document.createElement("style");
    css.id = "cxConsentCss";
    css.textContent = [
      ".cxc{position:fixed;left:0;right:0;bottom:0;z-index:2147483000;",
      "background:#fff;color:#16181d;border-top:1px solid #d9d6cf;",
      "box-shadow:0 -6px 24px rgba(0,0,0,.10);font:14px/1.6 -apple-system,",
      "BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif}",
      "@media(prefers-color-scheme:dark){.cxc{background:#191d26;color:#e8eaef;",
      "border-top-color:#333b4a}}",
      ".cxc-in{max-width:960px;margin:0 auto;padding:16px 20px;display:flex;",
      "gap:18px;align-items:flex-start;flex-wrap:wrap}",
      ".cxc-t{flex:1 1 380px;min-width:260px}",
      ".cxc h2{font-size:15px;margin:0 0 4px}",
      ".cxc p{margin:0;color:#4a4f5a}",
      "@media(prefers-color-scheme:dark){.cxc p{color:#adb6c4}}",
      ".cxc a{color:#3f4a6b}",
      "@media(prefers-color-scheme:dark){.cxc a{color:#9ba6ee}}",
      ".cxc-b{display:flex;gap:10px;flex-wrap:wrap;align-items:center}",
      /* Equal prominence is a legal requirement, so it is expressed as one rule
         that both buttons share rather than two that happen to look similar. */
      ".cxc-b button{font:inherit;font-weight:600;padding:10px 18px;border-radius:8px;",
      "cursor:pointer;border:1px solid #2f3a57;min-width:132px}",
      ".cxc-y{background:#2f3a57;color:#fff}",
      ".cxc-n{background:transparent;color:inherit}",
      ".cxc-b button:focus-visible{outline:2px solid #2f3a57;outline-offset:2px}",
      "@media(prefers-color-scheme:dark){.cxc-b button{border-color:#9ba6ee}",
      ".cxc-y{background:#4e5fc0;color:#fff}.cxc-b button:focus-visible{outline-color:#9ba6ee}}",
      ".cxc-link{position:fixed;left:12px;bottom:12px;z-index:2147482000;",
      "font:12px/1 inherit;background:transparent;border:0;color:#6b7280;",
      "text-decoration:underline;cursor:pointer;padding:6px}",
      "@media(prefers-color-scheme:dark){.cxc-link{color:#909bad}}",
      /* The slotted form. It inherits the colour of whatever footer or
         settings panel it was placed in, so it does not need to know
         anything about that page's theme. 44px tall on a touch screen for
         the same reason every other control here is. */
      ".cxc-inline{font:inherit;background:transparent;border:0;color:inherit;",
      "text-decoration:underline;cursor:pointer;padding:0;line-height:inherit}",
      "@media(pointer:coarse){.cxc-inline{min-height:44px}}"
    ].join("");
    document.head.appendChild(css);
  }

  var bar = null;

  function close() {
    if (bar) { bar.remove(); bar = null; }
    showWithdrawLink();
  }

  function show(id, policyUrl) {
    styles();
    if (bar) return;
    bar = document.createElement("div");
    bar.className = "cxc";
    bar.setAttribute("role", "dialog");
    bar.setAttribute("aria-modal", "false");
    bar.setAttribute("aria-labelledby", "cxcH");
    bar.innerHTML =
      '<div class="cxc-in">' +
      '<div class="cxc-t"><h2 id="cxcH">Can we count your visit?</h2>' +
      '<p>We would like to use Google Analytics to see which pages get used. ' +
      'It sets cookies. Nothing has loaded yet, and saying no changes nothing ' +
      'about how the site works for you. ' +
      '<a href="' + policyUrl + '">What we store</a></p></div>' +
      '<div class="cxc-b">' +
      '<button type="button" class="cxc-n" id="cxcNo">No thanks</button>' +
      '<button type="button" class="cxc-y" id="cxcYes">Yes, that is fine</button>' +
      '</div></div>';
    document.body.appendChild(bar);
    document.getElementById("cxcYes").onclick = function () {
      write(true); loadAnalytics(id); close();
    };
    document.getElementById("cxcNo").onclick = function () {
      write(false); clearAnalyticsCookies(); close();
    };
    // Keyboard first: focus lands on the decline button, so the least
    // consequential choice is the one a keyboard user reaches by default.
    document.getElementById("cxcNo").focus();
  }

  /* WHERE THE WITHDRAW CONTROL LIVES.
   *
   * It used to be one fixed button pinned to the bottom-left of every screen.
   * On a phone that is not a footer, it is an overlay: it sat on top of the
   * app's own tab bar, covering "Home". A permanent control that covers a
   * navigation control is a bug, not compliance.
   *
   * So a page may now declare where it wants the control, with
   * `data-cookie-settings` on any element, and it is rendered inline there:
   * the landing page footer, the login card, and Account settings all do.
   * A page that declares nothing still gets the floating button, because the
   * one thing that must never happen is a surface where consent can be given
   * and not taken back. Article 7(3): withdrawal has to be as easy as consent,
   * which is why this is never behind the login alone.
   */
  function findSlot() {
    var all = document.querySelectorAll("[data-cookie-settings]");
    if (!all.length) return null;
    for (var i = 0; i < all.length; i++) {
      // The one actually on screen wins, so the app can declare several
      // (login card, Account pane) and the right one is always used.
      if (all[i].getClientRects().length) return all[i];
    }
    return all[0];  // declared but on a screen that is not open yet
  }

  function showWithdrawLink() {
    var slot = findSlot();
    var existing = document.getElementById("cxcLink");
    if (existing) {
      var parked = slot ? existing.parentNode === slot
                        : existing.parentNode === document.body;
      if (parked) return;      // already in the right place
      existing.remove();       // the screen changed; re-home it
    }
    styles();
    var b = document.createElement("button");
    b.id = "cxcLink";
    b.type = "button";
    b.textContent = "Cookie settings";
    b.onclick = function () {
      try { localStorage.removeItem(KEY); } catch (e) {}
      clearAnalyticsCookies();
      b.remove();
      start();
    };
    if (slot) {
      b.className = "cxc-inline";
      slot.appendChild(b);
    } else {
      b.className = "cxc-link";
      document.body.appendChild(b);
    }
  }

  /* The app rebuilds Account settings from scratch every time it is opened,
     which throws this control away with it. It calls this to put it back. */
  window.cxCookieSettings = showWithdrawLink;

  function start() {
    fetch("/api/legal/config")
      .then(function (r) { return r.json(); })
      .then(function (cfg) {
        var c = (cfg && cfg.consent) || {};
        // No tracker configured means nothing to consent to. A banner asking
        // permission for nothing trains people to click through banners that
        // matter, so there is deliberately none.
        if (!c.required || !c.analytics_id) return;
        var existing = read();
        if (existing === null) {
          show(c.analytics_id, "/legal/cookies");
          return;
        }
        if (existing.analytics) loadAnalytics(c.analytics_id);
        showWithdrawLink();
      })
      .catch(function () { /* no config, no tracker, no banner */ });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
