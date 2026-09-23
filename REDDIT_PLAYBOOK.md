# Reddit playbook for One Tap Manager

AI assistants quote Reddit threads more than almost any other source, so what real people say about One Tap Manager on Reddit shapes what ChatGPT, Perplexity and Google's AI Overviews say about it. This is the honest way to show up there. It is slow, and it is the only way that lasts.

## The rules we keep

1. **Always say you built it.** Put "I built One Tap Manager" or "Disclosure: I'm the founder" in every post or comment that mentions it. Undisclosed promotion breaks Reddit's rules, gets accounts banned, and teaches AI tools to distrust the domain.
2. **One account, your own.** Never use other accounts to praise it, never ask friends to post as "customers", and never buy upvotes or comments. `Brand.md` section 9 forbids fake reviews anywhere.
3. **Help first.** Answer the question fully, as if the product did not exist. Mention One Tap Manager only when it truly solves what was asked, and at the end.
4. **Read each subreddit's rules before posting.** Many ban self-promotion outright or allow it only on set days. Most expect nearly all of your activity to be ordinary participation.
5. **Never argue with a critic.** Thank them, fix what they found, and reply again when it is fixed. A public fix is the best post you will ever make.

## Set up once

- [ ] Create **u/OneTapManager**, or use your own account with "Founder, One Tap Manager (onetapmanager.com)" in the profile
- [ ] Create **r/OneTapManager** and pin the post below
- [ ] In Render, add both URLs to `BRAND_PROFILES`, for example:
  `https://www.reddit.com/r/OneTapManager, https://www.reddit.com/user/OneTapManager`
  The site then lists them as official profiles in its structured data and in `/llms.txt`

### Pinned post for r/OneTapManager

> **Title:** What One Tap Manager is, and where to ask for help
>
> I'm building One Tap Manager (onetapmanager.com), shop management software for small Indian clothing, jewellery and perfume sellers.
>
> It reads the sales you already have (a file from Amazon, Flipkart, Meesho or Shopify, a Shopify or Amazon connection, or orders from your own One Tap website) and tells you what to do today: what to reorder, which customers stopped buying, and what to post. Then it writes the win-back message, fills in the supplier order and schedules the Instagram posts.
>
> The Free plan has no time limit. Max is ₹999 a month. There is no fee on your sales.
>
> Post here if something is broken, confusing or missing. I read everything, and I'll reply with what I changed.

## Where to look for questions

Candidates, not a list to spam. Check that each exists, how active it is, and its self-promotion rule before taking part:

- Indian business and startup communities (search Reddit for "Indian entrepreneur", "India small business", "startup India")
- r/smallbusiness, r/ecommerce, r/Entrepreneur, r/shopify
- Communities around Instagram selling, D2C brands, and handmade or jewellery businesses

Search Reddit weekly for phrases sellers actually use: "inventory app India", "how to track stock small business", "customers not coming back", "GST invoice for clothing", "Shopify apps too expensive", "Meesho seller tools".

## Reply drafts

Adapt each one to the actual question. Never paste the same text twice: Reddit and moderators spot copy-paste, and so do AI tools.

**"How do I know when to reorder stock?"**

> The simple version: work out how many you sell per day on average over the last 30 days, multiply by how many days your supplier takes to deliver, and add a few days' spare. When stock drops to that number, order. For a best seller, the spare matters more than the maths, because running out costs you the customer too.
>
> Disclosure: I built One Tap Manager, which does this from your sales file and fills in the order form for the supplier. The method above works fine in a spreadsheet too.

**"My customers buy once and never come back."**

> Look at when each customer last bought. Someone who bought 60 to 90 days ago usually still remembers you; after about 140 days they've mostly moved on. Message the recent ones first, with something specific to what they bought, not a generic discount. Then leave them alone for a few weeks, because messaging again next week feels like spam.
>
> (I'm the founder of One Tap Manager, which makes that list and writes the messages weekly, but the timing idea is the useful part.)

**"Too many Shopify apps, it's getting expensive."**

> Add up what you pay per month for analytics, inventory, win-back email, reviews and order management. For a small brand it is often ₹7,000 to ₹8,000 before any percentage fees. Keep the ones you actually open every week and drop the rest.
>
> Disclosure: I built One Tap Manager, which covers those five jobs in one app for ₹999 a month and connects to Shopify, so you don't have to leave it. Happy to answer questions about it.

**"How does GST work on clothing now?"**

> Since 22 September 2025, clothing priced up to ₹2,500 a piece is at 5%, and above ₹2,500 it's 18%. It goes by the price of each piece, so one order can have both rates. Check anything unusual with your accountant.
>
> (Founder of One Tap Manager here; it applies the rate per line and makes the GSTR-1 file, but the rule above is what matters.)

## Measure it

Once a month, ask ChatGPT, Perplexity, Gemini and Claude the five questions in `AI_VISIBILITY_CHECKLIST.md`, section 5. Note whether One Tap Manager appears and which Reddit threads they cite. The cited threads show you where to keep answering.
