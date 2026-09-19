"""
The Story Engine — a narrative layer that sits ON TOP of the weekly arc.

WHAT PROBLEM THIS SOLVES
------------------------
social.py already builds a week as an ARC (tease -> reveal -> prove -> place ->
close) and refuses to put two identical archetypes back to back. That machinery
decides HOW each post is shot and paced. It does not decide WHAT STORY the week
is telling — every week came out as the same arc with a different product name.

A brand whose feed reads as designed runs one deliberate STORY a week — a
Problem->Solution, a Social-Proof stack, a Transformation, a Seasonal build-up —
chosen from what the business is trying to do right now, not picked at random.
This module is that chooser. It does NOT replace the arc; it names the story the
arc is telling, and folds that name and its through-line into the week's theme
note, which social.py already threads into every caption, reel script and the
paste-ready video prompt (build_video_prompt's STORY line).

HOW IT DECIDES
--------------
Six inputs describe the week (objective, audience_state, product_behavior,
proof_level, campaign_context, emotional_driver). `derive_inputs()` reads them
off what the planner already knows — the seller's category, whether a festival
is live this week, and the sales signals. `select_story()` runs the machine
rules (Rule Sets A–H) over those inputs and returns a ranked list of story
archetypes; `pick()` wraps that into the chosen story plus its alternates.

FESTIVE OR NOT, THE SAME ENGINE
-------------------------------
A festival in the week sets campaign_context = "seasonal" and the engine leads
with the Seasonal/Occasion story; an ordinary week is "evergreen" and the
engine leads with the objective-driven story. Both go through the same rules —
that is the whole point of building it as an engine rather than a festive-only
special case.

WHY IT ONLY ENRICHES, NEVER OVERRIDES
-------------------------------------
The arc's beat/format/archetype choices are tuned against the research social.py
is built on (informational content sells; carousels earn saves; reels carry
reach; the offer pillar is capped). The story sets the week's NARRATIVE FRAME
and the ROLE each beat plays (tension / demonstration / proof / product /
resolution — the roles rule #29 of the design already asks a week to cover). It
does not reorder beats or change formats, so the proven execution layer is
untouched and the planner's tests stay green.
"""
from __future__ import annotations

# --------------------------------------------------------------- 1. the six inputs
OBJECTIVES = ["awareness", "education", "trust", "consideration",
              "conversion", "launch", "retention", "community"]
AUDIENCE_STATES = ["unaware", "problem_aware", "solution_aware",
                   "product_aware", "ready_to_buy"]
PRODUCT_BEHAVIORS = ["visual", "demonstrable", "experiential",
                     "technical", "transformational", "repeat_use"]
PROOF_LEVELS = ["none", "claims", "reviews", "ugc", "quantitative", "case_studies"]
# Ordered weakest -> strongest, so a rule can say "proof_level >= reviews".
PROOF_RANK = {name: i for i, name in enumerate(PROOF_LEVELS)}
CAMPAIGN_CONTEXTS = ["evergreen", "launch", "drop", "sale", "seasonal",
                     "new_feature", "repositioning"]
EMOTIONAL_DRIVERS = ["curiosity", "aspiration", "fomo", "relief", "identity",
                     "surprise", "belonging", "achievement"]

# --------------------------------------------------------------- 2. narrative roles
#
# The five jobs a whole week must cover (design rule #29). The arc's beats map
# onto them one-to-one, so a full 5-beat week covers every role; a shorter
# cadence covers the ones its beats reach. This is what lets the engine report
# "this week has tension + product + demonstration + proof, no resolution".
ROLES = ["tension", "demonstration", "proof", "product", "resolution"]

BEAT_TO_ROLE = {
    "tease":  "tension",
    "reveal": "product",
    "prove":  "demonstration",
    "place":  "proof",
    "close":  "resolution",
}


def role_for_beat(beat: str) -> str:
    return BEAT_TO_ROLE.get(beat, "product")


def roles_covered(beats: list[str]) -> dict:
    """Which of the five narrative roles this set of beats reaches, and which it
    misses. Informational — surfaced on the brief so a thin cadence is honest
    about the roles it cannot fit, never used to block a plan."""
    present = {BEAT_TO_ROLE.get(b) for b in beats if b in BEAT_TO_ROLE}
    return {"present": [r for r in ROLES if r in present],
            "missing": [r for r in ROLES if r not in present]}


# --------------------------------------------------------------- 3. story database
#
# The 20 story archetypes, machine-readable. Each row is what a story IS for and
# when to reach for it — the fields the machine rules match against — plus the
# `frame`, the one line woven into the week's theme note so every caption, reel
# script and video prompt carries the same through-line. `roles` names the arc
# roles the story leans on (used only to explain the pick; the arc still decides
# the actual beats). `{product}` and `{occasion}` in a frame are filled in.
STORIES: dict[str, dict] = {
    "PROBLEM_SOLUTION": {
        "name": "Problem → Solution",
        "objectives": ["awareness", "consideration", "conversion"],
        "audience_states": ["problem_aware", "solution_aware"],
        "product_behaviors": ["demonstrable", "technical", "transformational"],
        "campaign_contexts": ["evergreen", "sale", "repositioning"],
        "emotional_drivers": ["relief", "curiosity"],
        "roles": ["tension", "demonstration", "proof", "resolution"],
        "proof_required": False,
        "cta": ["Learn more", "Shop now", "DM to order"],
        "frame": ("The week names a real problem, shows why it happens, then puts "
                  "{product} forward as the better way — pain first, product as the answer."),
    },
    "DIDNT_KNOW_I_NEEDED": {
        "name": "I didn't know I needed this",
        "objectives": ["awareness", "consideration"],
        "audience_states": ["unaware", "problem_aware"],
        "product_behaviors": ["demonstrable", "repeat_use", "experiential"],
        "campaign_contexts": ["evergreen", "new_feature"],
        "emotional_drivers": ["surprise", "curiosity"],
        "roles": ["tension", "demonstration", "proof"],
        "proof_required": False,
        "cta": ["Learn more", "Shop now"],
        "frame": ("The week starts from how people do it now, then reveals the better "
                  "way {product} makes possible — the small upgrade you can't go back from."),
    },
    "TRANSFORMATION": {
        "name": "Transformation (before → after)",
        "objectives": ["awareness", "trust", "conversion"],
        "audience_states": ["problem_aware", "solution_aware", "product_aware"],
        "product_behaviors": ["visual", "transformational", "experiential"],
        "campaign_contexts": ["evergreen", "seasonal"],
        "emotional_drivers": ["aspiration", "achievement"],
        "roles": ["tension", "demonstration", "proof", "resolution"],
        "proof_required": False,
        "cta": ["Shop now", "See the difference"],
        "frame": ("The week is a before-and-after: where you start, what {product} "
                  "changes, and the visible result — the difference carries the story."),
    },
    "FOUNDER_JOURNEY": {
        "name": "Founder / hero journey",
        "objectives": ["awareness", "trust", "community"],
        "audience_states": ["unaware", "problem_aware"],
        "product_behaviors": ["experiential", "visual"],
        "campaign_contexts": ["launch", "repositioning", "evergreen"],
        "emotional_drivers": ["belonging", "aspiration"],
        "roles": ["tension", "product", "proof", "resolution"],
        "proof_required": False,
        "cta": ["Follow the story", "Shop now"],
        "frame": ("The week is the maker's own story — why {product} exists, what it "
                  "took to make it — so the brand, not just the piece, earns trust."),
    },
    "PRODUCT_REVEAL": {
        "name": "Product reveal",
        "objectives": ["awareness", "launch", "conversion"],
        "audience_states": ["unaware", "problem_aware", "product_aware"],
        "product_behaviors": ["visual", "experiential"],
        "campaign_contexts": ["launch", "drop", "new_feature", "seasonal"],
        "emotional_drivers": ["curiosity", "fomo", "surprise"],
        "roles": ["tension", "product", "demonstration", "resolution"],
        "proof_required": False,
        "cta": ["Shop the drop", "Get yours"],
        "frame": ("The week builds anticipation, reveals {product}, then explores it — "
                  "something is coming, here it is, here's what makes it worth having."),
    },
    "SOCIAL_PROOF_STACK": {
        "name": "Social proof stack",
        "objectives": ["trust", "conversion"],
        "audience_states": ["solution_aware", "product_aware", "ready_to_buy"],
        "product_behaviors": ["visual", "demonstrable", "repeat_use"],
        "campaign_contexts": ["evergreen", "sale", "seasonal"],
        "emotional_drivers": ["belonging", "relief"],
        "roles": ["proof", "product", "resolution"],
        "proof_required": True,
        "cta": ["Shop now", "DM to order"],
        "frame": ("The week stacks proof for {product}: one person said it, another "
                  "lived it, several agree — claim, person, experience, then act."),
    },
    "OBJECTION_DESTROYER": {
        "name": "Objection destroyer",
        "objectives": ["consideration", "conversion"],
        "audience_states": ["product_aware", "ready_to_buy"],
        "product_behaviors": ["demonstrable", "technical", "transformational"],
        "campaign_contexts": ["evergreen", "sale"],
        "emotional_drivers": ["relief", "achievement"],
        "roles": ["tension", "demonstration", "proof", "resolution"],
        "proof_required": False,
        "cta": ["Shop now", "DM your question"],
        "frame": ("The week takes the real reason people hesitate over {product} — "
                  "price, care, fit, doubt — and dismantles it, doubt then answer."),
    },
    "HOW_IT_WORKS": {
        "name": "How it actually works",
        "objectives": ["education", "consideration"],
        "audience_states": ["problem_aware", "solution_aware"],
        "product_behaviors": ["technical", "demonstrable"],
        "campaign_contexts": ["evergreen", "new_feature"],
        "emotional_drivers": ["curiosity", "relief"],
        "roles": ["demonstration", "product", "proof"],
        "proof_required": False,
        "cta": ["Learn more", "Shop now"],
        "frame": ("The week opens up {product} — behind the magic, here's what actually "
                  "happens — so the thing that felt unfamiliar becomes understood."),
    },
    "DAY_IN_THE_LIFE": {
        "name": "Day in the life",
        "objectives": ["awareness", "consideration", "retention"],
        "audience_states": ["problem_aware", "solution_aware", "product_aware"],
        "product_behaviors": ["repeat_use", "experiential", "visual"],
        "campaign_contexts": ["evergreen", "seasonal"],
        "emotional_drivers": ["belonging", "aspiration"],
        "roles": ["product", "demonstration", "proof"],
        "proof_required": False,
        "cta": ["Shop now", "Save for later"],
        "frame": ("The week follows a normal day and lets {product} appear naturally in "
                  "it — useful in a routine, not an advert dropped into one."),
    },
    "THE_SWITCH": {
        "name": "The switch",
        "objectives": ["consideration", "conversion"],
        "audience_states": ["solution_aware", "product_aware", "ready_to_buy"],
        "product_behaviors": ["demonstrable", "transformational"],
        "campaign_contexts": ["evergreen", "repositioning", "sale"],
        "emotional_drivers": ["relief", "achievement"],
        "roles": ["tension", "demonstration", "proof", "resolution"],
        "proof_required": False,
        "cta": ["Make the switch", "Shop now"],
        "frame": ("The week is a switch story: what people used, the problem it left, "
                  "and what changed once they moved to {product} — behaviour, not features."),
    },
    "EDUCATION_TO_PRODUCT": {
        "name": "Education → product",
        "objectives": ["education", "awareness", "trust"],
        "audience_states": ["unaware", "problem_aware", "solution_aware"],
        "product_behaviors": ["technical", "demonstrable", "experiential"],
        "campaign_contexts": ["evergreen", "repositioning"],
        "emotional_drivers": ["curiosity", "achievement"],
        "roles": ["demonstration", "product", "proof"],
        "proof_required": False,
        "cta": ["Learn more", "Shop now"],
        "frame": ("The week teaches something genuinely useful, builds a new way of "
                  "seeing it, and shows {product} fitting that understanding — authority, then sell."),
    },
    "MYSTERY_REVEAL": {
        "name": "Mystery → reveal",
        "objectives": ["awareness", "launch"],
        "audience_states": ["unaware", "problem_aware", "product_aware"],
        "product_behaviors": ["visual", "experiential"],
        "campaign_contexts": ["launch", "drop", "seasonal"],
        "emotional_drivers": ["curiosity", "surprise", "fomo"],
        "roles": ["tension", "product", "resolution"],
        "proof_required": False,
        "cta": ["Shop the drop", "Get yours"],
        "frame": ("The week withholds and hints — something unusual, clues, curiosity — "
                  "then reveals {product}. Premium by restraint, not by shouting."),
    },
    "LIMITED_DROP": {
        "name": "Limited drop / scarcity",
        "objectives": ["conversion", "launch"],
        "audience_states": ["product_aware", "ready_to_buy"],
        "product_behaviors": ["visual", "experiential"],
        "campaign_contexts": ["drop", "sale", "launch", "seasonal"],
        "emotional_drivers": ["fomo", "achievement"],
        "roles": ["tension", "product", "proof", "resolution"],
        "proof_required": False,
        "cta": ["Shop before it's gone", "Get yours"],
        "frame": ("The week runs on real scarcity around {product} — attention, desire, "
                  "availability, urgency, act. Only when the scarcity is genuine."),
    },
    "CUSTOMER_REACTION": {
        "name": "Customer reaction",
        "objectives": ["trust", "awareness", "conversion"],
        "audience_states": ["solution_aware", "product_aware"],
        "product_behaviors": ["visual", "experiential"],
        "campaign_contexts": ["evergreen", "seasonal"],
        "emotional_drivers": ["surprise", "belonging"],
        "roles": ["proof", "product", "resolution"],
        "proof_required": True,
        "cta": ["Shop now", "DM to order"],
        "frame": ("The week is built on the reaction {product} gets — the surprise and "
                  "delight of a real person — because the reaction sells better than the claim."),
    },
    "BEHIND_THE_PRODUCT": {
        "name": "Behind the product",
        "objectives": ["trust", "awareness", "community"],
        "audience_states": ["unaware", "problem_aware", "solution_aware"],
        "product_behaviors": ["experiential", "visual", "demonstrable"],
        "campaign_contexts": ["evergreen", "repositioning"],
        "emotional_drivers": ["belonging", "aspiration"],
        "roles": ["demonstration", "product", "proof"],
        "proof_required": False,
        "cta": ["Shop now", "Follow the making"],
        "frame": ("The week shows what customers don't see about {product} — the craft, "
                  "the process, the people — because that is what a competitor cannot copy."),
    },
    "ONE_CUSTOMER_ONE_PROBLEM": {
        "name": "One customer, one problem",
        "objectives": ["education", "trust", "conversion"],
        "audience_states": ["problem_aware", "solution_aware", "product_aware"],
        "product_behaviors": ["technical", "demonstrable", "transformational"],
        "campaign_contexts": ["evergreen"],
        "emotional_drivers": ["relief", "achievement"],
        "roles": ["tension", "demonstration", "proof", "resolution"],
        "proof_required": True,
        "cta": ["Read the story", "Shop now"],
        "frame": ("The week is one customer's specific story with {product} — what they "
                  "struggled with, exactly what changed — a case study, not a testimonial."),
    },
    "BELIEF_CHANGE": {
        "name": "Belief change",
        "objectives": ["awareness", "education", "repositioning"],
        "audience_states": ["unaware", "problem_aware", "solution_aware"],
        "product_behaviors": ["technical", "transformational", "demonstrable"],
        "campaign_contexts": ["repositioning", "evergreen"],
        "emotional_drivers": ["curiosity", "identity"],
        "roles": ["tension", "demonstration", "product"],
        "proof_required": False,
        "cta": ["Rethink it", "Shop now"],
        "frame": ("The week changes a belief about the category — everyone assumes X, "
                  "actually Y — and lands {product} inside the new way of seeing it."),
    },
    "COMMUNITY": {
        "name": "Community / participation",
        "objectives": ["community", "retention", "awareness"],
        "audience_states": ["product_aware", "ready_to_buy", "solution_aware"],
        "product_behaviors": ["experiential", "visual", "repeat_use"],
        "campaign_contexts": ["evergreen", "seasonal"],
        "emotional_drivers": ["belonging", "identity"],
        "roles": ["tension", "proof", "resolution"],
        "proof_required": False,
        "cta": ["Join in", "Tag a friend"],
        "frame": ("The week asks the audience in around {product} — a prompt, their "
                  "submissions, a response — turning a broadcast into a loop."),
    },
    "SEASONAL_OCCASION": {
        "name": "Seasonal / occasion",
        "objectives": ["awareness", "conversion", "consideration"],
        "audience_states": ["problem_aware", "solution_aware", "product_aware", "ready_to_buy"],
        "product_behaviors": ["visual", "experiential", "transformational"],
        "campaign_contexts": ["seasonal", "sale", "drop"],
        "emotional_drivers": ["belonging", "aspiration", "fomo"],
        "roles": ["tension", "product", "proof", "resolution"],
        "proof_required": False,
        "cta": ["Shop for {occasion}", "Order in time"],
        "frame": ("The week ties {product} to {occasion} — the moment people are already "
                  "shopping for — so the piece feels like the answer to the occasion, not an ad inside it."),
    },
    "PRODUCT_AS_IDENTITY": {
        "name": "Product as identity",
        "objectives": ["awareness", "conversion", "community"],
        "audience_states": ["solution_aware", "product_aware", "ready_to_buy"],
        "product_behaviors": ["visual", "experiential"],
        "campaign_contexts": ["evergreen", "launch", "seasonal", "repositioning"],
        "emotional_drivers": ["identity", "aspiration", "belonging"],
        "roles": ["tension", "product", "proof", "resolution"],
        "proof_required": False,
        "cta": ["Shop now", "Make it yours"],
        "frame": ("The week is about who {product} says you are — what you value, how it "
                  "reflects that — so buying it is an act of identity, not just a purchase."),
    },
}

# Names the machine rules use that are aliases of a canonical story above.
_ALIASES = {
    "IDENTITY": "PRODUCT_AS_IDENTITY",
    "BEFORE_AFTER": "TRANSFORMATION",
    "CUSTOMER_STORY": "ONE_CUSTOMER_ONE_PROBLEM",
}


def _canon(story_id: str) -> str:
    return _ALIASES.get(story_id, story_id)


# --------------------------------------------------------------- 3b. story -> post kind
#
# "What kind of post for that story." Each story leans on particular KINDS of
# photograph/clip — a Social-Proof week wants customer shots and reviews, a
# Reveal week wants the hero and the half-open box, a How-it-works week wants the
# process and the one detail. These are the arc's own archetypes (social.py's
# ARCHETYPES), so the story can bias which archetype each beat becomes WITHOUT
# inventing a parallel vocabulary. slate_shape treats this as a preference, not a
# command: it still refuses two identical posts in a row, still keeps the week a
# mix of reels and carousels, and still favours what the seller can actually
# shoot — the story only breaks ties, so the KIND of post follows the story while
# the proven balance rules hold. Each list is deliberately format-mixed (reels:
# tease, unbox, in_use, process, festival; carousels/stills: hero, detail,
# styling, proof, answer) so a story can never force an all-one-format week.
PREFERRED_ARCHETYPES: dict[str, list[str]] = {
    "PROBLEM_SOLUTION":       ["answer", "detail", "in_use", "proof"],
    "DIDNT_KNOW_I_NEEDED":    ["in_use", "detail", "styling"],
    "TRANSFORMATION":         ["in_use", "detail", "styling", "proof"],
    "FOUNDER_JOURNEY":        ["process", "hero", "proof"],
    "PRODUCT_REVEAL":         ["hero", "unbox", "detail"],
    "SOCIAL_PROOF_STACK":     ["proof", "in_use", "styling"],
    "OBJECTION_DESTROYER":    ["answer", "detail", "proof"],
    "HOW_IT_WORKS":           ["process", "detail", "answer"],
    "DAY_IN_THE_LIFE":        ["in_use", "styling", "hero"],
    "THE_SWITCH":             ["answer", "in_use", "proof"],
    "EDUCATION_TO_PRODUCT":   ["detail", "process", "answer"],
    "MYSTERY_REVEAL":         ["tease", "hero", "unbox"],
    "LIMITED_DROP":           ["unbox", "hero", "festival"],
    "CUSTOMER_REACTION":      ["proof", "unbox", "in_use"],
    "BEHIND_THE_PRODUCT":     ["process", "detail", "hero"],
    "ONE_CUSTOMER_ONE_PROBLEM": ["proof", "answer", "in_use"],
    "BELIEF_CHANGE":          ["answer", "detail", "process"],
    "COMMUNITY":              ["proof", "in_use", "styling"],
    "SEASONAL_OCCASION":      ["festival", "hero", "in_use", "styling"],
    "PRODUCT_AS_IDENTITY":    ["hero", "in_use", "styling"],
}


def preferred_archetypes(story_id: str) -> list[str]:
    """The arc archetypes this story leans on, best first. Empty for an unknown
    story, which slate_shape reads as 'no preference'."""
    return list(PREFERRED_ARCHETYPES.get(_canon(story_id), []))


# --------------------------------------------------------------- 4. content taxonomy
#
# Reference only — the arc's FORMAT_FOR_ARCHETYPE still decides a post's actual
# format. These name the execution options a story CAN reach for, so a strategist
# (or a later, richer selector) can pick a specific treatment inside a beat.
REEL_TYPES = [
    "UGC", "Unboxing", "Try-on", "HyperMotion", "Cinematic TVC", "Tutorial",
    "Product review", "Shopping", "At-home UGC", "Delivery", "Review",
    "Before-after", "2D product motion", "Typographics", "Dark minimalism",
    "Colour pop", "Mixed media", "SaaS demo", "Talking head", "Founder story",
    "Day in the life", "POV", "Street interview", "Customer interview",
    "Reaction", "Challenge", "BTS", "ASMR", "Screen recording",
    "Product montage", "Stop motion", "Meme / trend adaptation",
    "Green screen explainer", "FAQ reel", "Myth vs fact", "Case study",
    "Comparison", "Listicle", "POV testimonial", "Live cutdown",
]
IMAGE_TYPES = [
    "Product hero", "Product lifestyle", "UGC still", "Founder portrait",
    "Customer portrait", "Testimonial quote", "Review screenshot",
    "Product detail", "Price / offer", "Announcement", "Launch teaser",
    "Editorial photography", "Typographic statement", "Data / statistic card",
    "Before-after", "Comparison graphic", "Product collection", "Flat lay",
    "Moodboard", "Meme", "Illustration", "Infographic", "Screenshot / UI",
    "Social proof wall", "BTS photography", "Process image",
    "Event / occasion graphic", "Quote from founder", "FAQ card", "Countdown",
    "Availability / stock", "CTA graphic",
]
CAROUSEL_TYPES = [
    "Educational", "How-to", "Step-by-step", "Problem breakdown", "Before-after",
    "Product breakdown", "Feature deep dive", "Comparison", "FAQ",
    "Myth vs fact", "Customer story", "Case study", "Testimonial compilation",
    "Checklist", "Framework", "Data / statistics", "Timeline", "Process / BTS",
    "Lookbook", "Collection", "Gift guide", "Buying guide", "Use cases",
    "Product specifications", "Ingredients / materials", "Social proof",
    "Objection handling", "Story sequence", "Screenshots / UI walkthrough",
    "Founder journey",
]
VISUAL_STYLES = [
    "Clean minimal", "Dark minimalism", "Colour pop", "Editorial", "Luxury",
    "Brutalist", "Mixed media", "Collage", "Scrapbook", "Magazine",
    "Handwritten", "Data-driven", "Corporate / consulting", "Lifestyle",
    "UGC native", "High contrast", "3D product render", "Illustration-led",
    "Photo + type", "Screenshot-led",
]


# --------------------------------------------------------------- 5. the machine rules
#
# Rule Sets A–H from the design, in order. Each returns story ids to PRIORITIZE
# for the matching condition. select_story concatenates the ones that fire, in
# rule order, dedupes keeping the first mention, then appends every remaining
# story that the six inputs are otherwise compatible with — so the result is
# always a full ranked list, never empty, and deterministic for a given input.
def _rule_seasonal(inp: dict) -> list[str]:               # H — festive/occasion first
    if inp.get("campaign_context") == "seasonal":
        return ["SEASONAL_OCCASION", "PRODUCT_AS_IDENTITY",
                "SOCIAL_PROOF_STACK", "LIMITED_DROP"]
    return []


def _rule_launch(inp: dict) -> list[str]:                 # E
    if inp.get("campaign_context") in ("launch", "drop"):
        return ["MYSTERY_REVEAL", "PRODUCT_REVEAL", "FOUNDER_JOURNEY",
                "SOCIAL_PROOF_STACK"]
    return []


def _rule_technical(inp: dict) -> list[str]:              # F
    if inp.get("product_behavior") == "technical":
        return ["HOW_IT_WORKS", "PROBLEM_SOLUTION", "ONE_CUSTOMER_ONE_PROBLEM",
                "EDUCATION_TO_PRODUCT", "OBJECTION_DESTROYER"]
    return []


def _rule_visual(inp: dict) -> list[str]:                 # G
    if inp.get("product_behavior") in ("visual", "transformational"):
        return ["TRANSFORMATION", "PRODUCT_REVEAL", "MYSTERY_REVEAL",
                "DAY_IN_THE_LIFE", "PRODUCT_AS_IDENTITY"]
    return []


def _rule_awareness(inp: dict) -> list[str]:              # A
    if inp.get("objective") == "awareness" and \
            inp.get("audience_state") in ("unaware", "problem_aware"):
        return ["PROBLEM_SOLUTION", "BELIEF_CHANGE", "MYSTERY_REVEAL",
                "FOUNDER_JOURNEY", "PRODUCT_AS_IDENTITY"]
    return []


def _rule_education(inp: dict) -> list[str]:              # B
    if inp.get("objective") == "education":
        return ["EDUCATION_TO_PRODUCT", "HOW_IT_WORKS", "ONE_CUSTOMER_ONE_PROBLEM"]
    return []


def _rule_trust(inp: dict) -> list[str]:                  # C
    if inp.get("objective") == "trust" and \
            PROOF_RANK.get(inp.get("proof_level"), 0) >= PROOF_RANK["reviews"]:
        return ["SOCIAL_PROOF_STACK", "CUSTOMER_REACTION",
                "ONE_CUSTOMER_ONE_PROBLEM", "TRANSFORMATION"]
    return []


def _rule_conversion(inp: dict) -> list[str]:             # D
    if inp.get("objective") == "conversion" and \
            inp.get("audience_state") in ("product_aware", "ready_to_buy"):
        return ["OBJECTION_DESTROYER", "SOCIAL_PROOF_STACK", "THE_SWITCH",
                "PRODUCT_AS_IDENTITY", "LIMITED_DROP"]
    return []


# Order matters: seasonal leads on festive weeks, then launch, then the
# product-behaviour rules, then the objective rules.
_RULE_SETS = [_rule_seasonal, _rule_launch, _rule_technical, _rule_visual,
              _rule_awareness, _rule_education, _rule_trust, _rule_conversion]


def _compatible(story: dict, inp: dict) -> bool:
    """A story the six inputs do not actively rule out. A proof-required story
    with no proof to show is ruled out; otherwise a story stays eligible if it
    matches the objective OR the campaign_context (a loose gate, so the tail of
    the ranking is still sensible rather than random)."""
    if story.get("proof_required") and \
            PROOF_RANK.get(inp.get("proof_level"), 0) < PROOF_RANK["reviews"]:
        return False
    obj_ok = inp.get("objective") in story["objectives"]
    ctx_ok = inp.get("campaign_context") in story["campaign_contexts"]
    return obj_ok or ctx_ok


def select_story(inputs: dict) -> list[str]:
    """Ranked story ids for these inputs, most relevant first. Never empty."""
    inp = normalize_inputs(inputs)
    ranked: list[str] = []
    for rule in _RULE_SETS:
        for sid in rule(inp):
            sid = _canon(sid)
            if sid in STORIES and sid not in ranked and _compatible(STORIES[sid], inp):
                ranked.append(sid)
    # Fill the tail with any other compatible story, in the database's own order,
    # so the caller always has alternates to offer.
    for sid, story in STORIES.items():
        if sid not in ranked and _compatible(story, inp):
            ranked.append(sid)
    # Absolute fallback: an input so unusual nothing matched. Problem->Solution
    # is the safe universal story, so the engine never returns nothing.
    if not ranked:
        ranked = ["PROBLEM_SOLUTION"]
    return ranked


# --------------------------------------------------------------- 6. deriving the inputs
#
# The seller never fills in six dropdowns. The planner already knows enough to
# infer them: the category says how the product behaves, a live festival sets the
# campaign context and pulls the objective towards conversion, and the sales
# signals say how much proof exists and how warm the audience is. A future
# settings screen can override any of these; anything the seller has pinned in
# settings wins over what is inferred here.
_BEHAVIOR_BY_CATEGORY = {
    "clothing": "visual", "apparel": "visual", "fashion": "visual",
    "jewellery": "visual", "jewelry": "visual", "accessories": "visual",
    "perfume": "experiential", "fragrance": "experiential",
    "beauty": "transformational", "skincare": "transformational",
    "cosmetics": "transformational", "food": "experiential",
    "home": "visual", "decor": "visual", "software": "technical",
    "saas": "technical", "app": "technical", "service": "demonstrable",
}


def _behavior_for(category: str) -> str:
    cat = (category or "").strip().lower()
    for key, beh in _BEHAVIOR_BY_CATEGORY.items():
        if key in cat:
            return beh
    return "demonstrable"


def derive_inputs(category: str = "", occasion: dict | None = None,
                  signals: dict | None = None, settings: dict | None = None) -> dict:
    """Infer the six inputs from what the planner already knows.

    - campaign_context: a live festival this week => seasonal, else evergreen.
    - objective: a festival is a buying moment (conversion); otherwise proven
      winners mean trust is worth building, and a cold shop is about awareness.
    - audience_state: festive shoppers are product-aware; otherwise problem-aware.
    - product_behavior: from the seller's category.
    - proof_level: real sales in the data are the proxy for proof to show.
    - emotional_driver: the tone the week leans on, festive vs evergreen.
    """
    settings = settings or {}
    signals = signals or {}
    has_winners = bool(signals.get("winners"))
    has_data = bool(signals.get("has_data"))

    festive = bool(occasion)
    campaign_context = "seasonal" if festive else "evergreen"

    if festive:
        objective = "conversion"
        audience_state = "product_aware"
        emotional = "belonging"
    elif has_winners:
        objective = "trust"
        audience_state = "solution_aware"
        emotional = "aspiration"
    elif has_data:
        objective = "consideration"
        audience_state = "problem_aware"
        emotional = "relief"
    else:
        objective = "awareness"
        audience_state = "problem_aware"
        emotional = "curiosity"

    # Proof to show: winners with real revenue read as social proof exists;
    # any sales data at all is at least a claim; a shop with none has none.
    if has_winners:
        proof_level = "reviews"
    elif has_data:
        proof_level = "claims"
    else:
        proof_level = "none"

    inp = {
        "objective": objective,
        "audience_state": audience_state,
        "product_behavior": _behavior_for(category),
        "proof_level": proof_level,
        "campaign_context": campaign_context,
        "emotional_driver": emotional,
    }
    # A seller who has pinned any of these in settings overrides the inference.
    for key in inp:
        pinned = settings.get(f"story_{key}")
        if pinned:
            inp[key] = pinned
    return normalize_inputs(inp)


def normalize_inputs(inputs: dict) -> dict:
    """Coerce to known values; anything unrecognised falls back to a safe default
    so a bad or partial input can never raise inside the rules."""
    inp = dict(inputs or {})
    defaults = {"objective": "awareness", "audience_state": "problem_aware",
                "product_behavior": "demonstrable", "proof_level": "none",
                "campaign_context": "evergreen", "emotional_driver": "curiosity"}
    valid = {"objective": OBJECTIVES, "audience_state": AUDIENCE_STATES,
             "product_behavior": PRODUCT_BEHAVIORS, "proof_level": PROOF_LEVELS,
             "campaign_context": CAMPAIGN_CONTEXTS, "emotional_driver": EMOTIONAL_DRIVERS}
    for key, allowed in valid.items():
        v = str(inp.get(key) or "").strip().lower()
        inp[key] = v if v in allowed else defaults[key]
    return inp


# --------------------------------------------------------------- 7. the pick
def _fill(text: str, product_name: str, occasion: dict | None) -> str:
    occ = (occasion or {}).get("name", "the occasion")
    return (text or "").replace("{product}", product_name or "this piece") \
                       .replace("{occasion}", occ)


def narrative_frame(story_id: str, product_name: str = "",
                    occasion: dict | None = None) -> str:
    """The story's one-line through-line, filled in for this product and
    occasion. This is what gets folded into the week's theme note."""
    story = STORIES.get(_canon(story_id))
    if not story:
        return ""
    return _fill(story["frame"], product_name, occasion)


def pick(inputs: dict | None = None, *, category: str = "", occasion: dict | None = None,
         signals: dict | None = None, settings: dict | None = None,
         product_name: str = "") -> dict:
    """Choose the week's story. Pass explicit `inputs`, or let it derive them
    from the planner's context. Returns the chosen story, its filled-in frame,
    the ranked alternates and the inputs it decided on — everything the brief
    needs to explain WHY this week tells this story."""
    inp = normalize_inputs(inputs) if inputs else \
        derive_inputs(category=category, occasion=occasion, signals=signals, settings=settings)
    ranked = select_story(inp)
    top = ranked[0]
    story = STORIES[top]
    cta = [_fill(c, product_name, occasion) for c in story["cta"]]
    return {
        "id": top,
        "name": story["name"],
        "inputs": inp,
        "frame": _fill(story["frame"], product_name, occasion),
        "roles": story["roles"],
        "proof_required": story["proof_required"],
        "cta": cta,
        # The KINDS of post this story leans on — slate_shape uses this to steer
        # each beat's archetype toward the story.
        "prefer": preferred_archetypes(top),
        "why": _why(top, inp, occasion),
        "alternates": [{"id": sid, "name": STORIES[sid]["name"]} for sid in ranked[1:4]],
    }


def _why(story_id: str, inp: dict, occasion: dict | None) -> str:
    """One plain sentence the seller can read on the brief."""
    name = STORIES[story_id]["name"]
    if inp["campaign_context"] == "seasonal" and occasion:
        return (f"{occasion['name']} is live this week, so the plan tells a "
                f"{name} story — the piece as the answer to the occasion.")
    obj = inp["objective"]
    reason = {
        "awareness": "the shop is still building reach",
        "trust": "there are proven sellers worth building trust around",
        "consideration": "there is sales data but no clear winner yet",
        "conversion": "the audience is warm enough to move on a sale",
        "education": "the plan is leading with authority, not a hard sell",
        "community": "the week is built to bring the audience in",
    }.get(obj, "of what the week is trying to do")
    return f"An ordinary week and {reason}, so the plan tells a {name} story."
