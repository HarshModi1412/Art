/*
 * Renders the real storefront views in Node with a minimal DOM.
 *
 * Why this exists: the guest-checkout crash ("cannot read null 'name'") was in
 * the browser bundle, so every server-side test passed while the page was
 * broken for exactly the shopper guest checkout was built for. This runs the
 * actual store.js against the states that matter — signed in, and not.
 *
 *   node scripts/test_storefront_render.js
 */
const fs = require("fs");
const path = require("path");

const STORE = path.join(__dirname, "..", "Smart CafeX", "storefront", "store.js");

const stubEl = () => new Proxy(
  { style: {}, classList: { add() {}, remove() {}, toggle() {} },
    querySelectorAll: () => [], querySelector: () => null, addEventListener() {},
    appendChild() {}, removeAttribute() {}, setAttribute() {}, focus() {},
    closest: () => null, remove() {} },
  { get: (t, k) => (k in t ? t[k] : (typeof k === "string" ? "" : undefined)),
    set: () => true });

Object.assign(global, {
  location: { pathname: "/s/demo", search: "", href: "http://x/s/demo", hash: "" },
  history: { pushState() {}, replaceState() {} },
  localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
  document: { getElementById: stubEl, querySelectorAll: () => [], querySelector: () => null,
              createElement: stubEl, addEventListener() {},
              documentElement: stubEl(), body: stubEl() },
  window: { addEventListener() {} },
  requestAnimationFrame: (f) => f(),
  addEventListener: () => {}, removeEventListener: () => {},
  matchMedia: () => ({ matches: false, addEventListener() {}, addListener() {} }),
  getComputedStyle: () => ({ getPropertyValue: () => "" }),
  scrollY: 0, innerWidth: 1200, innerHeight: 800,
  fetch: () => Promise.reject(new Error("no network in this harness")),
  IntersectionObserver: class { observe() {} unobserve() {} disconnect() {} },
});

let src = fs.readFileSync(STORE, "utf8")
  .replace(/^\(async function boot\(\)[\s\S]*$/m, "");   // skip the boot IIFE
src += "\nmodule.exports = { viewCheckout, viewProduct, viewHome, viewShop, S };\n";
const tmp = path.join(require("os").tmpdir(), "store_harness_" + process.pid + ".js");
fs.writeFileSync(tmp, src);
const M = require(tmp);

M.S.site = {
  brand: "Aureva",
  commerce: { cod_enabled: true, currency: "INR", shipping_fee: 49, free_shipping_above: 2000,
              gst_percent: 18, gst_inclusive: true, order_note: "" },
  policies: { returns: "7 days" },
  trust: { show: true, business_name: "Aureva Labs", gstin: "29ABCDE1234F1Z5",
           address: "Bengaluru", support_phone: "9876543210",
           returns_days: 7, dispatch_days: 2 },
  sections: {}, copy: {}, hero: {}, story: {}, highlights: [], stats: [], gallery: [],
};
M.S.data = { categories: [], products: [], icons: {} };
M.S.icons = {};
M.S.products = [{
  id: "p1", name: "Field Shirt", price: 1499, in_stock: true, available: 4,
  images: [], image_url: "", highlights: [],
  options: [{ name: "Size", values: ["S", "M"] }, { name: "Colour", values: ["Black", "Blue"] }],
  variants: [
    { id: "v1", label: "S / Black", options: { Size: "S", Colour: "Black" }, price: 1499, in_stock: true, available: 2, image_url: "" },
    { id: "v2", label: "S / Blue", options: { Size: "S", Colour: "Blue" }, price: 1499, in_stock: false, available: 0, image_url: "" },
    { id: "v3", label: "M / Black", options: { Size: "M", Colour: "Black" }, price: 1699, in_stock: true, available: 2, image_url: "" },
    { id: "v4", label: "M / Blue", options: { Size: "M", Colour: "Blue" }, price: 1499, in_stock: false, available: 0, image_url: "" },
  ],
}];
M.S.priced = {
  items: [{ product_id: "p1", name: "Field Shirt", display_name: "Field Shirt — M / Black",
            qty: 1, line_total: 1699, image_url: "" }],
  subtotal: 1699, shipping: 49, tax: 259, gst_percent: 18, gst_inclusive: true,
  total: 1748, min_order: 0, cod_enabled: true,
};
M.S.route = { name: "product", id: "p1" };

let pass = 0, fail = 0;
function must(cond, name, extra) {
  if (cond) { console.log("  ✓ " + name); pass++; }
  else { console.log("  ✗ " + name + (extra ? "  " + extra : "")); fail++; }
}
function render(fn) {
  try { return fn(); } catch (e) { return { __error: e.message }; }
}

console.log("== storefront renders for a GUEST (no customer record) ==");
M.S.customer = null;
let h = render(() => M.viewCheckout());
must(typeof h === "string", "checkout renders instead of throwing",
     h && h.__error ? "-> " + h.__error : "");
if (typeof h === "string") {
  must(h.includes("No account needed"), "it says an account is not needed");
  must(h.includes('id="coName" value=""'), "name and phone start empty, not undefined");
  must(h.includes('id="coEmail"'), "an optional email field is offered");
  must(h.includes("Aureva Labs") && h.includes("trust-legal"), "the trust block renders");
  must(!h.includes("undefined"), "nothing renders the string 'undefined'");
}

console.log("\n== and for a SIGNED-IN shopper ==");
M.S.customer = { id: "c1", email: "riya@example.com", name: "Riya", phone: "9876543210",
                 address: { line1: "12 MG Road", city: "Bengaluru", state: "KA", pincode: "560001" } };
h = render(() => M.viewCheckout());
must(typeof h === "string", "checkout renders",
     h && h.__error ? "-> " + h.__error : "");
if (typeof h === "string") {
  must(h.includes("Signed in as riya@example.com"), "it says who you are");
  must(h.includes("12 MG Road"), "the saved address is prefilled");
}

console.log("\n== the product page with a variant matrix ==");
M.S.customer = null;
h = render(() => M.viewProduct("p1"));
must(typeof h === "string", "product page renders",
     h && h.__error ? "-> " + h.__error : "");
if (typeof h === "string") {
  must(h.includes("Choose size &amp; colour") || h.includes("Choose size & colour"),
       "it asks for a choice before it will sell");
  must(h.includes("opt-v"), "the option chips render");
  must(h.includes("gone"), "sold-out combinations are struck through, not hidden");
  must(h.includes("from ₹1,499"), "an unchosen matrix shows a 'from' price");
}
M.S.chosen = { p1: { Size: "M", Colour: "Black" } };
h = render(() => M.viewProduct("p1"));
if (typeof h === "string") {
  must(h.includes("₹1,699"), "choosing a variant shows that variant's price");
  must(h.includes("Add to bag"), "and enables the buy button");
}

fs.unlinkSync(tmp);
console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
