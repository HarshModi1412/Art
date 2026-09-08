"""
The festival content library — what to post, when, and what not to say.

WHY THIS IS DATA AND NOT A PROMPT
---------------------------------
The obvious build is to ask a language model "write me a Diwali post". That
produces the exact thing this file exists to prevent: a diya, a rangoli, the
words "festival of lights", and a greeting that competes with four hundred
identical greetings in the same feed on the same evening.

What actually separates a post that sells from one that does not is knowledge a
model will not reliably supply on its own: that Navratri's nine day-wise colours
rotate every year and give you nine pre-scheduled posts; that Dhanteras converts
because the purchase is religious rather than promotional, so discounting on it
reads as clearing dead stock on a sacred day; that Karva Chauth intent dies at
moonrise with no tail; that Raksha Bandhan advertising has spent five years
moving away from "brother protects sister" and copy in that register now reads
as dated.

So the festival knowledge is a table. The model's job is to write in the
seller's voice using it, not to remember it.

THE SAFETY FIELD IS NOT OPTIONAL
--------------------------------
Every entry carries `caution`. Indian festival advertising has a real and
asymmetric sentiment risk, and it lands hardest on exactly the three categories
this app serves. Campaigns pulled in recent years include Fabindia's
"Jashn-e-Riwaaz" (an Urdu name for a Diwali collection), Sabyasachi's mangalsutra
campaign, Dabur's same-sex Karva Chauth ad, Tanishq's Ekatvam, and GIVA's Rakhi
ad over Indo-Western styling. Large brands survived those. A seller with 40 SKUs
would not.

TWO GRAMMARS
------------
`buys_for` is the highest-leverage field in the table. On a GIFTING festival the
reader is not the wearer, and the whole caption flips: "she will never take it
off" rather than "you will never want to take it off". Small sellers get this
backwards constantly and it is the most fixable error in the category.
"""
from __future__ import annotations

SELF = "self"          # the reader is the wearer
GIFT = "gift"          # the reader is buying for someone else
BOTH = "both"


# ---------------------------------------------------------------------------
# The library. Weights are 0-10 per category; a festival scoring 0-3 for a
# seller's category is not offered to them at all.
# ---------------------------------------------------------------------------

FESTIVALS = {
    "navratri": {
        "name": "Navratri",
        "core": "Nine nights of worship of the Goddess — lived as the year's "
                "biggest dressing-up occasion. The only festival where you are "
                "expected to wear something different nine nights running and be "
                "photographed dancing in each one.",
        "weight": {"clothing": 10, "jewellery": 8, "perfume": 5},
        "buys_for": SELF,
        "buys": ["chaniya choli", "lehenga choli", "kediyu", "oxidised silver "
                 "jhumkas and chokers", "kamarbandh", "maang tikka", "mirror work",
                 "bandhani and gota patti dupattas", "juttis", "potli bags"],
        "colours": ["orange", "white", "red", "royal blue", "yellow", "green",
                    "grey", "purple", "peacock green"],
        "motifs": ["mirror work (abhla)", "bandhani", "gota patti", "dandiya sticks",
                   "garba circles", "kalash / garbo", "red chunri", "marigold"],
        "angles": [
            "Nine nights, nine colours — the outfit for each one, one slide per day",
            "One chaniya choli, nine ways — different dupatta and jewellery each "
            "night, for the buyer who cannot afford nine outfits",
            "Oxidised jewellery that survives three hours of garba — durability "
            "as the hook, not beauty",
            "What to wear going straight from office to garba",
            "Day seven is grey. Nobody knows what to wear on grey day",
            "Mom's old chaniya choli, restyled",
            "First Navratri in a new city — what to buy",
        ],
        "taglines": [
            "Nau raatein, nau look. Ready ho jao.",
            "Garba khelna hai ya dekhna hai? Outfit dono ke liye ready hai.",
            "Ghagra ready, jhumke ready. Energy aap laao.",
            "Go in circles only for garba.",
        ],
        "hashtags": ["#Navratri", "#Garba", "#ChaniyaCholi", "#NavratriLook",
                     "#DandiyaNight", "#OxidisedJewellery"],
        "caution": [
            "Never put Durga's image on a discount creative. Commercialising the "
            "deity is the exact trigger that has had campaigns pulled.",
            "No non-vegetarian food, alcohol or leather in the creative — a large "
            "share of your audience is fasting for nine days.",
            "Do not run Navratri creative to a Bengali audience. In Kolkata this "
            "is Durga Puja and the visual language is completely different.",
        ],
        "note": "The nine day-wise colours are the most usable mechanic in the "
                "Indian calendar — nine posts with a built-in reason to post. The "
                "sequence rotates each year with the weekday Day 1 falls on, so it "
                "must be refreshed annually, never carried forward.",
    },

    "dussehra": {
        "name": "Dussehra",
        "core": "Good defeats evil — and one of the three muhurat days of the "
                "year, when starting or buying something is auspicious.",
        "weight": {"clothing": 5, "jewellery": 6, "perfume": 2},
        "buys_for": SELF,
        "buys": ["new clothes for Ravan Dahan", "gold coins on muhurat",
                 "small gold jewellery"],
        "colours": ["marigold orange", "red", "gold"],
        "motifs": ["bow and arrow", "shami leaves", "burning effigy", "marigold"],
        "angles": [
            "Bought on muhurat — the pieces people buy on an auspicious day",
            "What to wear to Ravan Dahan",
            "The bridge into Diwali — what to buy now that you will wear then",
        ],
        "taglines": ["Shubh muhurat, shubh shuruaat.",
                     "Naya kuch shuru karne ka din."],
        "hashtags": ["#Dussehra", "#Vijayadashami", "#FestiveSeason",
                     "#BijoyaDashami", "#Dussehra2026", "#ShubhMuhurat"],
        "caution": [
            "Do not build a discount around burning things. 'Burn these prices' "
            "lands as cheap.",
            "Do not use Ravana as a metaphor for a competitor.",
        ],
        "note": "A very short window, two or three days. Treat it as a bridge "
                "post into the Diwali run-up, not a campaign of its own.",
    },

    "karva_chauth": {
        "name": "Karva Chauth",
        "core": "A married woman fasts until moonrise. The only evening of the "
                "year when she dresses at wedding intensity. For the buyer the "
                "feeling is not sacrifice, it is getting to feel like a bride "
                "again for one night.",
        "weight": {"clothing": 8, "jewellery": 10, "perfume": 6},
        "buys_for": BOTH,
        "buys": ["kundan / polki / AD statement necklace", "jhumkas or chandbalis",
                 "maang tikka or mathapatti", "stacked bangles and chooda",
                 "solitaire ring or pendant", "red or maroon saree or lehenga"],
        "colours": ["red", "maroon", "oxblood", "fuchsia", "gold", "emerald"],
        "motifs": ["full moon", "the sieve (chalni)", "mehendi", "karva pot",
                   "sindoor", "chooda", "the thali"],
        "angles": [
            "Three pieces, not sixteen — what modern buyers actually wear",
            "The sieve shot: how to get the moon photograph right",
            "First Karva Chauth — what the newly married actually need",
            "Under Rs 2,000 and it still photographs like heirloom",
            "Getting ready in 40 minutes after a work day",
        ],
        "taglines": [
            "Chand se pehle, taiyaar.",
            "Under the same moon.",
            "Ek raat ke liye, dulhan wali feeling.",
        ],
        "hashtags": ["#KarwaChauth", "#KarwaChauthLook", "#FirstKarwaChauth",
                     "#RedSaree", "#KarvaChauth"],
        "caution": [
            "The highest-risk festival on this list. Dabur withdrew a Karva Chauth "
            "ad with an unconditional apology after political backlash.",
            "Do not write 'she starves for him'. The sacrifice framing reads badly "
            "to the younger half of your audience.",
            "Do not use a crescent moon. It is a full moon night, and a crescent "
            "reads as an Islamic symbol — wrong on two counts.",
            "Do not discount aggressively on the day itself; it reads as cheapening "
            "a religious observance.",
        ],
        "note": "A hard-stop festival. Intent dies at moonrise and there is no "
                "tail at all. Same-day delivery messaging matters enormously in "
                "the final 72 hours.",
    },

    "dhanteras": {
        "name": "Dhanteras",
        "core": "The day it is auspicious to buy metal, because Lakshmi enters a "
                "home that has acquired something new and precious. Not a gifting "
                "day and not a fashion day.",
        "weight": {"clothing": 3, "jewellery": 10, "perfume": 1},
        "buys_for": SELF,
        "buys": ["gold and silver coins", "silver utensils",
                 "lakshmi-ganesh coins", "light-weight gold jewellery",
                 "silver payal and bichhua"],
        "colours": ["gold", "deep red", "marigold"],
        "motifs": ["Lakshmi footprints (charan)", "kalash", "coins", "diyas"],
        "angles": [
            "The muhurat window, printed on the creative — free, accurate, and it "
            "signals you understand the customer",
            "Even a Rs 500 silver coin counts — the ritual needs something metal",
            "What people actually buy on Dhanteras, by budget",
            "Hallmark and purity, explained plainly",
        ],
        "taglines": ["Shubh Dhanteras.", "Ghar mein kuch naya, kuch shubh.",
                     "Dhan barse."],
        "hashtags": ["#Dhanteras", "#ShubhDhanteras", "#SilverJewellery",
                     "#GoldJewellery", "#Dhanteras2026", "#SilverCoin"],
        "caution": [
            "Do not run a blowout discount. People are buying BECAUSE the day is "
            "auspicious; heavy discounting signals you are clearing dead stock on "
            "a sacred day.",
            "Never put Lakshmi's image on a price tile.",
            "Never use black in the creative.",
        ],
        "note": "The highest-conversion purchase day of the Indian year for "
                "jewellery, and the reason is religious rather than promotional. "
                "Real intent lives in the final 48 hours.",
    },

    "diwali": {
        "name": "Diwali",
        "core": "Homecoming, and being seen by your people. The year's one "
                "guaranteed family gathering, where you are photographed with "
                "relatives you see once a year and quietly appraised. That "
                "appraisal is what drives the clothing purchase.",
        "weight": {"clothing": 10, "jewellery": 9, "perfume": 8},
        "buys_for": BOTH,
        "buys": ["festive kurta sets and sarees", "lehengas for the party night",
                 "gold and diamond jewellery", "perfume gift sets",
                 "gifting boxes for staff and family"],
        "colours": ["gold", "deep red", "emerald", "royal blue", "ivory",
                    "marigold"],
        "motifs": ["diyas", "rangoli", "marigold torans", "lanterns", "brass"],
        "angles": [
            "The outfit for your in-laws' Diwali lunch, styled three ways",
            "Five gifts under Rs 1,500 that do not look like they cost that",
            "What to wear to a Diwali party that is not a lehenga",
            "Packed and shipped today — the last-safe-order-date post",
            "The workshop at midnight, packing your orders",
            "Repeat-wear maths: what you will wear again after Diwali",
        ],
        "taglines": [
            "Is Diwali, kuch apna sa.",
            "Ghar wapas aane wale sab ke liye.",
            "Roshni aapki, outfit humara.",
            "Not just another festive sale.",
        ],
        "hashtags": ["#Diwali", "#FestiveWear", "#DiwaliGifting", "#EthnicWear",
                     "#Diwali2026"],
        "caution": [
            "The generic 'Happy Diwali from our family to yours' tile with a stock "
            "diya is the single most wasted post in Indian D2C. If you must greet, "
            "shoot your own hands lighting your own diya in your own workshop.",
            "Do not name a Diwali collection in Urdu or in a way that reads as "
            "de-Hinduising the festival — Fabindia's was pulled for exactly this.",
            "Do not discount so hard from Dhanteras to Diwali that you train "
            "customers to buy only on sale.",
        ],
        "note": "The biggest perfume gifting window in India. Ad costs climb hard "
                "from mid-September, so audience-building has to happen in August.",
    },

    "bhai_dooj": {
        "name": "Bhai Dooj",
        "core": "Two days after Diwali a sister applies tilak and prays for her "
                "brother; he gives her a gift. Raksha Bandhan's quieter twin — the "
                "gift is the point and everyone knows it.",
        "weight": {"clothing": 4, "jewellery": 7, "perfume": 7},
        "buys_for": GIFT,
        "buys": ["light jewellery", "perfume", "small gifting sets"],
        "colours": ["red", "gold", "yellow"],
        "motifs": ["tilak", "thali", "sweets"],
        "angles": [
            "The Diwali budget is gone — gifts that still feel like gifts",
            "Delivered by Bhai Dooj if you order today",
            "For the sister who says do not get me anything",
        ],
        "taglines": ["Tilak ke saath, kuch aur bhi.",
                     "Behen ke liye, thoda sa zyada."],
        "hashtags": ["#BhaiDooj", "#SiblingLove", "#Gifting", "#BhaiDooj2026",
                     "#BhaiBehen", "#FestiveGifting"],
        "caution": [
            "Do not recycle your Rakhi creative with the word swapped. The rituals "
            "look different — thread versus tilak — and people notice.",
            "Do not lead with a big-ticket item. The Diwali budget is spent.",
        ],
        "note": "Few brands campaign here, which is the opportunity. Do not post "
                "it on Diwali itself; you will be ignored.",
    },

    "raksha_bandhan": {
        "name": "Raksha Bandhan",
        "core": "A sister ties a thread; he owes her protection. But the last five "
                "years of Indian advertising have renegotiated that — the "
                "protection is now mutual, and 'brother protects sister' copy "
                "reads as dated.",
        "weight": {"clothing": 5, "jewellery": 9, "perfume": 8},
        "buys_for": GIFT,
        "buys": ["rakhi and gift sets", "light jewellery for sisters",
                 "perfume for brothers", "kurta sets"],
        "colours": ["red", "gold", "saffron", "pastel pinks"],
        "motifs": ["rakhi thread", "tilak", "thali", "hands and wrists"],
        "angles": [
            "The gift for the sibling you argue with constantly",
            "Shipping cut-off: order by this date and it lands in time",
            "What she actually wants versus what you were going to buy",
            "The sister who ties the rakhi on her own brother — role reversal",
        ],
        "taglines": [
            "Gehna to your behna.",
            "Let's call it a tie.",
            "Iss baar mera number hai.",
            "Door ho ya paas.",
        ],
        "hashtags": ["#RakshaBandhan", "#Rakhi", "#SiblingLove", "#RakhiGifts",
                     "#Rakhi2026"],
        "caution": [
            "Do not write 'protect your sister' — the whole category has moved on.",
            "Never make a rakhi joke involving a romantic partner. It reads as "
            "incest humour in the Indian context and has burned brands.",
            "Indo-Western styling on Rakhi creative carries real risk — GIVA "
            "withdrew a Rakhi campaign from all media over exactly this.",
        ],
        "note": "The rakhi is the loss leader; the gift is the margin. Do not sell "
                "a rakhi with no gift attached.",
    },

    "ganesh_chaturthi": {
        "name": "Ganesh Chaturthi",
        "core": "Ganpati comes home for ten days and then you walk him to the sea. "
                "A hosting festival — the deity is a houseguest — so it is about "
                "home, food and welcome rather than self-presentation.",
        "weight": {"clothing": 6, "jewellery": 4, "perfume": 3},
        "buys_for": SELF,
        "buys": ["traditional Maharashtrian wear", "nauvari sarees", "kurta sets",
                 "puja essentials"],
        "colours": ["saffron", "red", "yellow", "green"],
        "motifs": ["modak", "Ganpati silhouette", "durva grass", "dhol tasha"],
        "angles": [
            "What to wear for aarti at home versus at the pandal",
            "Ten days, and you are hosting for most of them",
            "The nauvari, explained for people who have never draped one",
        ],
        "taglines": ["Bappa ghar aaye hain.", "Ganpati Bappa Morya."],
        "hashtags": ["#GaneshChaturthi", "#GanpatiBappaMorya", "#Ganeshotsav",
                     "#EcoFriendlyGanpati", "#Ganpati2026", "#Nauvari"],
        "caution": [
            "Do not run a discount on visarjan day. It is a farewell and it is "
            "genuinely emotional.",
            "Do not use 'Bappa' casually in a hard-sell line.",
            "Do not run Marathi-specific creative nationally — outside "
            "Maharashtra, Goa and Karnataka it will confuse.",
        ],
        "note": "Regionally concentrated but intense. Use the chant as the payoff "
                "line and build the setup around a small everyday problem.",
    },

    "eid": {
        "name": "Eid-ul-Fitr",
        "core": "The end of a month of fasting. Relief, gratitude, and being "
                "dressed at your absolute best to visit and be visited. Chand Raat "
                "— the night the crescent is sighted — is an all-night shopping "
                "event in itself.",
        "weight": {"clothing": 9, "jewellery": 6, "perfume": 10},
        "buys_for": BOTH,
        "buys": ["attar and oud", "sharara and gharara sets", "kurta pyjama",
                 "embroidered dupattas", "gifting sets for the family"],
        "colours": ["white", "ivory", "sage", "gold", "pastel green", "black"],
        "motifs": ["crescent moon", "lanterns", "geometric jaali", "dates"],
        "angles": [
            "Attar, explained — why oud lasts and eau de parfum does not",
            "The Chand Raat order: shipped tonight, worn tomorrow",
            "What to wear when you are the one hosting",
            "Eid gifting for the family you see once a year",
        ],
        "taglines": ["Eid Mubarak, khoobsurti ke saath.",
                     "Chand raat ki taiyaari.", "Attar jo shaam bhar rehta hai."],
        "hashtags": ["#EidMubarak", "#EidCollection", "#Attar", "#EidOutfit",
                     "#ChandRaat"],
        "caution": [
            "Do not confuse Eid-ul-Fitr with Eid-ul-Adha. Different tone entirely; "
            "the copy is not interchangeable.",
            "Do not post food imagery at 6pm on a fasting day.",
            "Do not use 'festival of lights' language — wrong festival.",
            "Do not run generic 'ethnic' creative with a crescent pasted on. The "
            "failure here mirrors the Fabindia one in reverse.",
        ],
        "note": "The single strongest perfume festival in India. Attar is embedded "
                "in Eid in a way no other Indian festival matches.",
    },

    "holi": {
        "name": "Holi",
        "core": "Colour, licence and levelling. For one morning hierarchy "
                "dissolves. The one festival where the product being ruined is "
                "part of the fun.",
        "weight": {"clothing": 7, "jewellery": 2, "perfume": 4},
        "buys_for": SELF,
        "buys": ["white kurtas people expect to destroy", "cotton co-ords",
                 "post-Holi body and hair care"],
        "colours": ["white", "and then every colour"],
        "motifs": ["gulal", "pichkari", "thandai", "wet colour on white cotton"],
        "angles": [
            "The Rs 399 white kurta you are supposed to ruin",
            "Post-Holi: wash it all off and smell good again",
            "How to get the colour out of cotton — actually useful, gets saved",
        ],
        "taglines": ["Rang lag jaane do.", "Safed pehno, rang aa hi jayega."],
        "hashtags": ["#Holi", "#HoliOutfit", "#FestivalOfColours", "#Holi2027",
                     "#RangBarse", "#WhiteKurta"],
        "caution": [
            "Do not sell expensive clothing for Holi day. Category error.",
            "Avoid the harassment topic entirely.",
        ],
        "note": "Low price point, high volume. Post-Holi fragrance is a real and "
                "underused angle.",
    },

    "christmas_ny": {
        "name": "Christmas & New Year",
        "core": "Two festivals in one window. Christmas in India is gifting and "
                "warmth; New Year's Eve is the only night of the year when Western "
                "eveningwear outsells ethnic outright.",
        "weight": {"clothing": 8, "jewellery": 6, "perfume": 8},
        "buys_for": BOTH,
        "buys": ["sequins and slip dresses", "blazers and co-ords",
                 "statement costume jewellery", "perfume gift sets"],
        "colours": ["black", "silver", "deep green", "burgundy", "gold"],
        "motifs": ["sequins", "fairy lights", "confetti", "champagne"],
        "angles": [
            "31st night, and you have nothing to wear",
            "One dress, two parties — Christmas lunch to NYE",
            "Gift sets that arrive before the 24th",
        ],
        "taglines": ["31st ki taiyaari.", "New year, same you, better outfit."],
        "hashtags": ["#NewYearOutfit", "#PartyWear", "#31stNight", "#Christmas",
                     "#NYE2026", "#SequinDress"],
        "caution": [
            "Do not post snow.",
            "Do not run ethnic-wear creative for NYE — wrong occasion.",
            "Do not discount on 31 December. It is the least price-sensitive night "
            "of the year.",
        ],
        "note": "The one window where Western outsells ethnic.",
    },

    "valentines": {
        "name": "Valentine's Day",
        "core": "A real gifting spike. Indian brands have moved decisively away "
                "from grand-gesture romance towards everyday, unglamorous, "
                "long-term intimacy — and the campaigns that still do grand "
                "gestures now read as dated.",
        "weight": {"clothing": 4, "jewellery": 9, "perfume": 9},
        "buys_for": GIFT,
        "buys": ["pendants and solitaires", "everyday-wear jewellery",
                 "perfume", "personalised pieces"],
        "colours": ["red", "blush", "rose gold", "ivory"],
        "motifs": ["hearts used sparingly", "hands", "everyday moments"],
        "angles": [
            "The gift she will actually wear on a Tuesday",
            "Everyday intimacy, not the grand gesture",
            "Under Rs 3,000, and it does not look it",
            "Engraving cut-off is today",
        ],
        "taglines": ["Kyunki pyaar jatana zaroori hai.", "Precious, every day."],
        "hashtags": ["#ValentinesDay", "#GiftingIdeas", "#EverydayJewellery",
                     "#ValentinesGift", "#GiftForHer", "#Personalised"],
        "caution": [
            "Valentine's is culturally contested in India and protests are an "
            "annual news event. Keep the creative about the couple, not the day.",
        ],
        "note": "Jewellery and fragrance dominate; clothing is a distant third.",
    },

    "wedding_season": {
        "name": "Wedding season",
        "core": "Not a festival — a demand window that runs on muhurat dates and "
                "moves independently of the festival calendar. Peaks Nov-Dec and "
                "Feb-Jun, with no auspicious dates at all in Aug-Oct or January.",
        "weight": {"clothing": 10, "jewellery": 10, "perfume": 6},
        "buys_for": BOTH,
        "buys": ["lehengas and sharara sets", "sarees for the family",
                 "bridal and bridesmaid jewellery", "sangeet and mehendi outfits"],
        "colours": ["red", "gold", "emerald", "royal blue", "pastels for day"],
        "motifs": ["zari", "kundan", "mehendi", "phoolon ki chaadar"],
        "angles": [
            "Wedding guest, not the bride — what to wear when you are neither",
            "The same lehenga at three functions, styled differently",
            "What the bride's sister wears",
            "Alteration and delivery timelines, stated honestly",
        ],
        "taglines": ["Shaadi ka season, aur aapke paas kuch nahi.",
                     "Guest list mein aap bhi ho."],
        "hashtags": ["#WeddingSeason", "#WeddingGuest", "#Lehenga",
                     "#BridalJewellery", "#ShaadiSeason"],
        "caution": [
            "Do not style guest wear as bridal. The guest is trying NOT to "
            "outshine the bride, and creative that ignores that misses the buyer.",
        ],
        "note": "January is the one genuinely slack month in the whole year — no "
                "festivals, no muhurat dates. The right month for evergreen "
                "catalogue work and collecting reviews.",
    },
}


# ---------------------------------------------------------------------------
# Campaign shape
#
# The research describes a ten-phase model. That is built for a brand with a
# marketing team, and handing a ten-phase plan to a seller with twenty minutes a
# week produces a plan they cannot execute — which is worse than no plan,
# because an unexecuted plan is a guilt generator.
#
# So this is compressed to six beats a solo seller can actually hit, keeping the
# properties that make it a campaign rather than a queue: each beat has ONE job,
# no job repeats, and the cadence rises toward the day.
# ---------------------------------------------------------------------------

BEATS = [
    {"key": "tease", "label": "Tease", "offset_frac": 1.00,
     "job": "Make them curious. Show a detail, not the product.",
     "format": "reel", "cta": "poll",
     "why": "Opening with an announcement wastes the only post nobody is "
            "expecting. A detail earns the second look."},
    {"key": "reveal", "label": "Reveal", "offset_frac": 0.72,
     "job": "Show the pieces properly, with the occasion named.",
     "format": "carousel", "cta": "save",
     "why": "The save-and-return asset. Carousels get roughly nine times the "
            "saves of a single image, and a save before a festival is intent."},
    {"key": "useful", "label": "Be useful", "offset_frac": 0.50,
     "job": "Answer the question they actually have — sizing, styling, care, "
            "what goes with what.",
     "format": "carousel", "cta": "save",
     "why": "Informational content has the strongest measured link to sales of "
            "any content type. This is the post that does the selling."},
    {"key": "proof", "label": "Proof", "offset_frac": 0.32,
     "job": "Show someone else already bought or wore it.",
     "format": "reel", "cta": "dm",
     "why": "Social proof does the convincing you cannot do about yourself."},
    {"key": "deadline", "label": "The deadline", "offset_frac": 0.15,
     "job": "State the last date it can arrive in time. Nothing else.",
     "format": "story", "cta": "dm",
     "why": "The highest-converting festive post there is, and the one small "
            "sellers most often forget. It is not a discount — it is a fact."},
    {"key": "day", "label": "On the day", "offset_frac": 0.0,
     "job": "Be present without selling. Your own hands, your own workshop.",
     "format": "story", "cta": "none",
     "why": "The generic greeting tile competes with four hundred identical "
            "ones. A real photograph of your own does not."},
]

CTA_COPY = {
    "poll": "Which one first? Vote on the story.",
    "save": "Save this for {occasion}.",
    "dm": "DM us to order — we will confirm the delivery date before you pay.",
    "none": "",
}


def for_category(category: str, min_weight: int = 4) -> list[dict]:
    """Festivals worth a seller's time, best first.

    A perfume seller is not offered Dhanteras and a jewellery seller is not
    offered Holi — a festival scoring below the threshold is not a weak
    opportunity, it is the wrong lane, and offering it teaches the seller the
    suggestions are not thought through."""
    cat = (category or "clothing").lower()
    out = []
    for key, f in FESTIVALS.items():
        w = f["weight"].get(cat, 0)
        if w >= min_weight:
            out.append({**f, "key": key, "weight_for": w})
    return sorted(out, key=lambda f: -f["weight_for"])


def get(key: str) -> dict | None:
    f = FESTIVALS.get(key)
    return {**f, "key": key} if f else None


def brief(key: str, category: str, brand: dict | None = None) -> dict:
    """Everything a caption writer needs for this festival, for this seller."""
    f = get(key)
    if not f:
        return {}
    b = brand or {}
    gifting = f["buys_for"] in (GIFT, BOTH)
    return {
        "festival": f["name"], "key": key,
        "core": f["core"],
        "weight": f["weight"].get((category or "clothing").lower(), 0),
        "buys_for": f["buys_for"],
        "reader_is_wearer": f["buys_for"] != GIFT,
        "grammar": ("Write to the GIFTER. The reader is not the wearer — "
                    "'she will never take it off', not 'you will never want to "
                    "take it off'."
                    if f["buys_for"] == GIFT else
                    "Write to the WEARER. The reader is buying for themselves."
                    if f["buys_for"] == SELF else
                    "Some buyers are gifting and some are buying for themselves. "
                    "Pick one per post and be consistent inside it."),
        "buys": f["buys"], "colours": f["colours"], "motifs": f["motifs"],
        "angles": f["angles"], "taglines": f["taglines"],
        "hashtags": f["hashtags"][:5],
        "caution": f["caution"], "note": f.get("note", ""),
        "gifting": gifting,
        "brand_avoid": b.get("avoid") or "",
    }
