"""Build data/sample_transactions.csv: the shop a new seller sees on "Load sample data".

WHY THIS FILE EXISTS
--------------------
The sample used to be a cafe: croissants, cold coffee, sandwiches. The people
One Tap Manager is for sell clothes, jewellery and perfume (the landing page
says so in Hindi), so a kurta seller's first look at the product told them
their biggest earner was "Sandwiches". The sample is the activation moment for
anyone who does not have a sales file to hand, so it has to look like their
kind of shop.

WHAT IT MODELS, AND WHY
  * A small D2C brand: kurtas and sarees, oxidised and kundan jewellery, attars.
    Real Indian price points, whole rupees.
  * Fewer, bigger orders than a cafe: most orders are one item, some two or
    three, so the average basket is around a thousand rupees, not two hundred.
  * Most customers buy once; a loyal minority come back. Some of the regulars
    stop partway through, so "customers slipping away" and the win-back list
    have real people in them.
  * Weekends and evenings are busier, and there is a festive lift in the last
    three weeks, which is when sellers stock up. That gives the forecast and
    the weekday advice something true to say.
  * Same nine columns as before, so nothing that reads the sample changes.

Deterministic: seeded, so re-running it produces the same file and the tests
that read it do not flicker.

Run: python scripts/make_sample_data.py
"""
from __future__ import annotations

import csv
import os
import random
from datetime import date, datetime, timedelta

SEED = 20260923
END = date(2026, 9, 21)          # the last day of sales in the sample
DAYS = 90
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "data", "sample_transactions.csv")

# (product, category, subcategory, price in rupees, relative popularity)
CATALOGUE = [
    ("Cotton Kurta, Indigo", "Clothing", "Kurtas", 1299, 9),
    ("Block Print Kurta, Rust", "Clothing", "Kurtas", 1499, 8),
    ("Chikankari Kurta, White", "Clothing", "Kurtas", 1899, 6),
    ("Handloom Saree, Maroon", "Clothing", "Sarees", 3499, 3),
    ("Linen Saree, Olive", "Clothing", "Sarees", 2799, 3),
    ("Bandhani Dupatta, Pink", "Clothing", "Dupattas", 699, 6),
    ("Phulkari Dupatta, Mustard", "Clothing", "Dupattas", 899, 4),
    ("Linen Co-ord Set, Sage", "Clothing", "Co-ord sets", 2199, 4),
    ("Oxidised Jhumkas", "Jewellery", "Earrings", 449, 12),
    ("Pearl Drop Earrings", "Jewellery", "Earrings", 599, 8),
    ("Kundan Studs", "Jewellery", "Earrings", 399, 7),
    ("Temple Necklace, Gold-tone", "Jewellery", "Necklaces", 1299, 4),
    ("Silver Choker", "Jewellery", "Necklaces", 899, 4),
    ("Glass Bangle Set", "Jewellery", "Bangles", 349, 7),
    ("Brass Kada", "Jewellery", "Bangles", 549, 5),
    ("Adjustable Silver Ring", "Jewellery", "Rings", 299, 6),
    ("Rose Attar, 6 ml", "Fragrance", "Attars", 499, 7),
    ("Mogra Attar, 6 ml", "Fragrance", "Attars", 549, 6),
    ("Oud Attar, 6 ml", "Fragrance", "Attars", 899, 4),
    ("Sandalwood Eau de Parfum, 50 ml", "Fragrance", "Perfumes", 1299, 3),
    ("Jasmine Body Mist, 100 ml", "Fragrance", "Perfumes", 799, 4),
    ("Attar Discovery Set", "Fragrance", "Gift sets", 1199, 3),
]

FIRST_NAMES = [
    "Aarav", "Aditi", "Ananya", "Anjali", "Arjun", "Avni", "Diya", "Farah", "Gauri",
    "Isha", "Ishaan", "Kavya", "Kiara", "Meera", "Mehak", "Naina", "Neha", "Nikhil",
    "Pooja", "Priya", "Rahul", "Riya", "Rohan", "Saanvi", "Sameer", "Sana", "Shreya",
    "Simran", "Sneha", "Tanvi", "Tara", "Vanya", "Vihaan", "Zoya", "Aisha", "Divya",
    "Ira", "Jiya", "Lavanya", "Manya", "Nidhi", "Pari", "Radhika", "Rhea", "Sakshi",
    "Suhana", "Trisha", "Uma", "Vidya", "Yashika",
]
LAST_INITIALS = "ABCDGJKMNPRSTV"


def build() -> list[dict]:
    rng = random.Random(SEED)
    start = END - timedelta(days=DAYS - 1)
    weights = [c[4] for c in CATALOGUE]

    next_id = [1001]

    def new_customer(regular: bool) -> dict:
        cid = f"C{next_id[0]}"
        next_id[0] += 1
        # Regulars have a rate; about a third stop coming partway through the
        # window, which is exactly who the win-back list is for.
        stops = regular and rng.random() < 0.33
        return {"id": cid, "name": f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_INITIALS)}.",
                "regular": regular, "rate": rng.uniform(0.05, 0.12) if regular else 0.0,
                "last_day": (start + timedelta(days=rng.randint(30, 62))) if stops else END}

    # A small loyal core, plus a pool of occasional buyers that grows as new
    # people find the shop. Most walk-ins are someone new, which is what makes
    # "most customers buy once" true, as it is for a real D2C shop.
    customers = [new_customer(True) for _ in range(45)]
    occasional: list[dict] = []
    rows, order_no = [], 5001
    day = start
    while day <= END:
        weekend = day.weekday() >= 5
        festive = (END - day).days < 21
        # Regulars who are still active come back at their own rate.
        todays = [c for c in customers if c["regular"] and day <= c["last_day"]
                  and rng.random() < c["rate"] * (1.35 if weekend else 1.0)]
        # New and occasional buyers arrive on top of that.
        walk_ins = rng.randint(2, 5) + (2 if weekend else 0) + (3 if festive else 0)
        for _ in range(walk_ins):
            if occasional and rng.random() < 0.22:
                todays.append(rng.choice(occasional))
            else:
                c = new_customer(False)
                occasional.append(c)
                todays.append(c)
        for cust in todays:
            hour = rng.choices([10, 12, 14, 17, 19, 20, 21, 22],
                               weights=[1, 2, 2, 3, 5, 6, 5, 3])[0]
            when = datetime(day.year, day.month, day.day, hour, rng.randint(0, 59))
            lines = rng.choices([1, 2, 3], weights=[64, 28, 8])[0]
            picked = set()
            for _ in range(lines):
                prod = rng.choices(CATALOGUE, weights=weights)[0]
                if prod[0] in picked:
                    continue
                picked.add(prod[0])
                qty = 1 if prod[3] >= 900 else rng.choices([1, 2, 3], weights=[78, 18, 4])[0]
                rows.append({
                    "date": when.strftime("%Y-%m-%d %H:%M"),
                    "order_id": f"ORD{order_no}",
                    "customer_id": cust["id"],
                    "customer_name": cust["name"],
                    "product": prod[0],
                    "category": prod[1],
                    "subcategory": prod[2],
                    "quantity": qty,
                    "amount": prod[3] * qty,
                })
            order_no += 1
        day += timedelta(days=1)
    rows.sort(key=lambda r: (r["date"], r["order_id"]))
    return rows


def main() -> None:
    rows = build()
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["date", "order_id", "customer_id", "customer_name",
                                           "product", "category", "subcategory",
                                           "quantity", "amount"])
        w.writeheader()
        w.writerows(rows)
    orders = len({r["order_id"] for r in rows})
    revenue = sum(r["amount"] for r in rows)
    print(f"wrote {len(rows)} lines, {orders} orders, "
          f"{len({r['customer_id'] for r in rows})} customers, "
          f"Rs {revenue:,} to {OUT}")


if __name__ == "__main__":
    main()
