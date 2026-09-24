/* =========================================================================
   THE FIRST-RUN JOURNEY: "Set up your shop in 3 parts"
   =========================================================================
   Design: docs/designs/first-run-journey.md. Backend: backend/core/onboarding.py.

   One question per screen, big buttons, words in English or Hindi. The journey
   has its own simple screens, but every save writes the same data the modules
   own, and a step only counts as done when that data says so. So a seller who
   adds products in Product Management instead is still "done" here, and one
   who deletes them is not.

   Skipping is allowed, never silent: "Skip for now" asks first, and a skipped
   step goes on the task list, where it ticks itself once really done.

   Loaded BEFORE smart.js so the home screen's first paint can draw the journey
   card. Nothing here runs at load time; it only uses smart.js's globals (api,
   apiUpload, esc, sic, toast, $, openModule...) when a seller acts.
   ========================================================================= */

/* ------------------------------------------------------------- words ---- */
const JT = {
  en: {
    part1_create: "Your shop online", part1_connect: "Connect your website",
    part2: "Your Instagram posts", part3: "Your stock",
    part_of: "Part {n} of 3",
    finish_later: "Finish later", back: "Back", next: "Next", save: "Save",
    skip: "Skip for now", saving: "Saving…", start: "Start",
    skip_q: "Skip this for now?", skip_sub: "It goes on your task list.",
    skip_no: "No, let's do it", skip_yes: "Yes, skip",
    skip_done: "Added to your task list.",
    welcome_t: "Let's set up your shop",
    welcome_s: "About 10 minutes. One small step at a time.",
    welcome_q: "Do you already have a website?",
    have_site: "Yes, I have one", have_site_s: "Shopify, WooCommerce, Wix or Amazon",
    make_site: "No, make me one", make_site_s: "Free. We never take a cut of your sales.",
    shop_name_t: "What is your shop called?", shop_name_ph: "Priya Kurtis",
    shop_name_err: "Type your shop's name.",
    shop_type_t: "What do you sell?",
    type_clothes: "Clothes", type_jewellery: "Jewellery", type_perfumes: "Perfume",
    type_generic: "Something else", type_own: "In your own words", type_own_ph: "Soy wax candles",
    products_t: "Add your products", products_s: "Add at least 3. Buyers want to see a photo.",
    products_count: "{n} of 3 added", products_more: "{n} added",
    add_photo: "Add a photo", change_photo: "Change photo",
    p_name: "Product name", p_name_ph: "Cotton kurta, blue",
    p_price: "Price (₹)", p_price_ph: "799",
    add_product: "Add this product", need_3: "Add {n} more to continue",
    p_name_err: "Type the product's name.", p_price_err: "Type the price in rupees.",
    removed: "Removed.",
    look_t: "Pick a look for your shop", look_s: "You can change it any time.",
    look_rec: "Suggested",
    gate_t: "Your shop needs a name and one product first",
    gate_name: "Name your shop", gate_products: "Add a product",
    address_t: "Your shop's web address", address_s: "Customers type this to find you.",
    address_hint: "Only a to z, 0 to 9 and -",
    address_ok: "Available", address_taken: "Taken. Try one of these:",
    address_short: "Use at least 3 letters or numbers.",
    wa_t: "Your WhatsApp number", wa_s: "Customers use it to reach you.",
    wa_err: "Enter 10 digits.",
    about_t: "Who runs the shop?", about_s: "The law asks every shop to show this.",
    about_name: "Your full name", about_addr: "Your address",
    about_addr_ph: "House, street, city, PIN code",
    about_email: "Customer emails go to {email}.",
    delivery_t: "Do you charge for delivery?",
    delivery_free: "Free delivery", delivery_free_s: "Customers pay only for the product",
    delivery_paid: "Yes, per order", delivery_paid_s: "Set one fee for every order",
    delivery_fee: "Delivery fee (₹)", fee_err: "Type the fee in rupees.",
    preview_t: "This is your shop", preview_s: "Only you can see it until you put it online.",
    list_all: "Show all {n} of my products in the shop",
    go_live: "Put my shop online", change_look: "Change the look",
    full_builder: "Open the full Website Builder",
    pay_t: "How do customers pay you?",
    pay_s: "They pay to your UPI ID. The money comes straight to you.",
    upi: "Your UPI ID", upi_ph: "name@okaxis",
    upi_where: "Where do I find my UPI ID?",
    upi_gpay: "Google Pay: tap your photo. Your UPI ID is under your name.",
    upi_phonepe: "PhonePe: tap your photo. Look for UPI ID.",
    upi_paytm: "Paytm: tap your photo. Look for UPI ID.",
    cod_on: "Cash on delivery is on too.", cod_off: "Cash on delivery is off.",
    not_inr: "UPI works only for shops in rupees.", to_inr: "Switch my shop to rupees",
    razorpay: "Use Razorpay instead",
    p1_done_t: "Your shop is online!", p1_done_s: "Share it where your customers already are.",
    share_wa: "Share on WhatsApp", copy_bio: "Copy for Instagram bio",
    bio_how: "Instagram: Edit profile, then Links, then paste.",
    copied: "Link copied.",
    p1_notlive_t: "Your shop is not online yet", p1_notlive_s: "It is on your task list.",
    put_online: "Put it online now",
    more_parts: "Two more parts",
    more_p2: "Let us make your Instagram posts", more_p2_s: "about 10 minutes",
    more_p3: "Never run out of stock", more_p3_s: "about 5 minutes",
    start_p2: "Start Part 2", later: "Later (it's on your task list)",
    wa_share_text: "My shop is online! Order here: {url}",
    connect_t: "Where is your website?",
    connect_other: "Something else", connect_other_s: "Upload a sales file (Excel or CSV)",
    make_instead: "I don't have a website. Make me one.",
    connect_btn: "Connect", connecting: "Connecting…", pulling: "Bringing in your orders…",
    connect_how: "How to get these",
    upload_t: "Upload a sales file", upload_s: "Export your orders as Excel or CSV from wherever you sell.",
    choose_file: "Choose file",
    catalogue_t: "We found {n} products in your sales",
    catalogue_s: "Add them to your list, so every sale is counted.",
    catalogue_add: "Add them to my list",
    catalogue_none_t: "Add your products", catalogue_none_s: "We did not find products in your sales yet.",
    c_done_t: "Your sales are in", c_orders: "orders", c_customers: "customers",
    c_top: "Top sellers",
    c_want_shop: "Want a free One Tap shop too?", c_want_shop_s: "Your own website, no cut of your sales.",
    c_make_shop: "Yes, make my shop",
    p2_intro_t: "Let us make your Instagram posts",
    p2_i1: "You add photos", p2_i2: "We learn your look", p2_i3: "We make posts, you tap yes",
    brand_t: "Tell us about your brand",
    brand_make: "What do you make?", brand_make_ph: "Hand-block printed cotton kurtas from Jaipur.",
    brand_who: "Who buys it?", brand_who_ph: "Women who want everyday cotton that feels special.",
    brand_err: "Write one line about what you make.",
    style_t: "Add 3 photos of your style",
    style_s: "Pictures whose look you love: your packaging, your shop, photos you admire.",
    style_count: "{n} of 3 added", add_photos: "Add photos",
    photos_t: "Add photos of your products", photos_s: "One clear photo each. A phone near a window is enough.",
    photos_none: "Add a product first.",
    ig_t: "Connect Instagram", ig_s: "So your posts go out on their own.",
    ig_need: "Your Instagram must be a Business or Creator account. It is free.",
    ig_how: "How to switch",
    ig_how_1: "Open Instagram and go to your profile.",
    ig_how_2: "Tap the menu, then Account type and tools.",
    ig_how_3: "Tap Switch to professional account.",
    ig_btn: "Connect Instagram", ig_done: "Instagram is connected.",
    p2_done_t: "Your Social Media Manager is ready",
    p2_done_s: "It plans a week of posts from your photos. Nothing goes out until you say yes.",
    p2_ai: "Planning uses AI, and every AI picture is labelled.",
    plan_week: "Plan my first week", next_p3: "Next: Part 3",
    p3_intro_t: "Never run out of stock",
    p3_i1: "Tell us who you buy from", p3_i2: "We watch what sells", p3_i3: "We warn you before it runs out",
    sup_t: "Who do you buy from?", sup_name: "Supplier's name", sup_name_ph: "Sharma Textiles",
    sup_phone: "Their WhatsApp (optional)", sup_days: "How many days to deliver?",
    sup_err: "Type your supplier's name.", days_err: "Delivery days must be 1 to 120.",
    skip_both: "Stock needs a supplier, so this skips both.",
    stock_t: "How many do you have?", stock_s: "Count what is on your shelf now.",
    search: "Search", stock_more: "Showing 20. Search for the rest.",
    p3_done_t: "You will know before it runs out",
    p3_example: "Example", p3_ex_1: "{name} sells about 2 a day.",
    p3_ex_2: "Supplier takes {d} days.", p3_ex_3: "We will warn you at {n}.",
    p3_ex_why: "2 × {d} = {base}, plus a little extra for safety.",
    all_done_t: "Your shop is all set", all_done_s: "Everything is ready. Well done.",
    left_t: "Almost there", left_s: "You skipped these. Do them whenever you are ready.",
    done: "Done", go_home: "Go to my shop",
    card_title: "Set up your shop in 3 parts",
    card_sub: "Your shop online, your posts, your stock. One small step at a time.",
    card_next: "Next: {step}", card_continue: "Continue", card_hide: "Hide this",
    card_skipped: "{n} skipped step{s} left", card_finish: "Finish them",
    setup_guide: "Setup guide",
    step_shop: "Name your shop", step_products: "Add 3 products", step_site: "Put your shop online",
    step_payment: "Add your UPI ID", step_connect: "Connect your website",
    step_catalogue: "Add your products", step_brand: "Tell us about your brand",
    step_style: "Add 3 style photos", step_photos: "Add product photos",
    step_instagram: "Connect Instagram", step_suppliers: "Add your supplier",
    step_stock: "Count your stock",
    uploading: "Uploading…", upload_failed: "That photo did not upload.", retry: "Try again",
    open: "Open",
  },
  hi: {
    part1_create: "आपकी दुकान ऑनलाइन", part1_connect: "अपनी वेबसाइट जोड़ें",
    part2: "आपकी Instagram पोस्ट", part3: "आपका स्टॉक",
    part_of: "भाग {n} / 3",
    finish_later: "बाद में पूरा करें", back: "पीछे", next: "आगे", save: "सेव करें",
    skip: "अभी छोड़ें", saving: "सेव हो रहा है…", start: "शुरू करें",
    skip_q: "इसे अभी छोड़ें?", skip_sub: "यह आपकी टास्क लिस्ट में जुड़ जाएगा।",
    skip_no: "नहीं, इसे करते हैं", skip_yes: "हाँ, छोड़ें",
    skip_done: "टास्क लिस्ट में जुड़ गया।",
    welcome_t: "चलिए आपकी दुकान तैयार करें",
    welcome_s: "लगभग 10 मिनट। एक-एक छोटा कदम।",
    welcome_q: "क्या आपकी पहले से कोई वेबसाइट है?",
    have_site: "हाँ, है", have_site_s: "Shopify, WooCommerce, Wix या Amazon",
    make_site: "नहीं, मेरे लिए बनाइए", make_site_s: "मुफ़्त। आपकी बिक्री पर कोई कमीशन नहीं।",
    shop_name_t: "आपकी दुकान का नाम क्या है?", shop_name_ph: "प्रिया कुर्तीज़",
    shop_name_err: "अपनी दुकान का नाम लिखें।",
    shop_type_t: "आप क्या बेचते हैं?",
    type_clothes: "कपड़े", type_jewellery: "गहने", type_perfumes: "परफ़्यूम",
    type_generic: "कुछ और", type_own: "अपने शब्दों में", type_own_ph: "मोमबत्तियाँ",
    products_t: "अपने प्रोडक्ट जोड़ें", products_s: "कम से कम 3 जोड़ें। ग्राहक फ़ोटो देखना चाहते हैं।",
    products_count: "3 में से {n} जुड़े", products_more: "{n} जुड़े",
    add_photo: "फ़ोटो जोड़ें", change_photo: "फ़ोटो बदलें",
    p_name: "प्रोडक्ट का नाम", p_name_ph: "कॉटन कुर्ता, नीला",
    p_price: "कीमत (₹)", p_price_ph: "799",
    add_product: "यह प्रोडक्ट जोड़ें", need_3: "आगे बढ़ने के लिए {n} और जोड़ें",
    p_name_err: "प्रोडक्ट का नाम लिखें।", p_price_err: "कीमत रुपये में लिखें।",
    removed: "हटा दिया।",
    look_t: "अपनी दुकान का लुक चुनें", look_s: "इसे कभी भी बदल सकते हैं।",
    look_rec: "सुझाया गया",
    gate_t: "पहले दुकान का नाम और एक प्रोडक्ट चाहिए",
    gate_name: "दुकान का नाम रखें", gate_products: "प्रोडक्ट जोड़ें",
    address_t: "आपकी दुकान का वेब पता", address_s: "ग्राहक इसे लिखकर आपको ढूँढेंगे।",
    address_hint: "सिर्फ़ a से z, 0 से 9 और -",
    address_ok: "उपलब्ध है", address_taken: "यह पता लिया जा चुका है। इनमें से कोई चुनें:",
    address_short: "कम से कम 3 अक्षर या अंक लिखें।",
    wa_t: "आपका WhatsApp नंबर", wa_s: "ग्राहक इसी पर आपसे बात करेंगे।",
    wa_err: "10 अंक लिखें।",
    about_t: "दुकान कौन चलाता है?", about_s: "कानून के अनुसार हर दुकान को यह दिखाना होता है।",
    about_name: "आपका पूरा नाम", about_addr: "आपका पता",
    about_addr_ph: "मकान, गली, शहर, पिन कोड",
    about_email: "ग्राहकों के ईमेल {email} पर आएँगे।",
    delivery_t: "क्या आप डिलीवरी का पैसा लेते हैं?",
    delivery_free: "मुफ़्त डिलीवरी", delivery_free_s: "ग्राहक सिर्फ़ प्रोडक्ट का पैसा देंगे",
    delivery_paid: "हाँ, हर ऑर्डर पर", delivery_paid_s: "हर ऑर्डर पर एक तय फ़ीस",
    delivery_fee: "डिलीवरी फ़ीस (₹)", fee_err: "फ़ीस रुपये में लिखें।",
    preview_t: "यह है आपकी दुकान", preview_s: "ऑनलाइन करने तक इसे सिर्फ़ आप देख सकते हैं।",
    list_all: "मेरे सभी {n} प्रोडक्ट दुकान में दिखाएँ",
    go_live: "मेरी दुकान ऑनलाइन करें", change_look: "लुक बदलें",
    full_builder: "पूरा वेबसाइट बिल्डर खोलें",
    pay_t: "ग्राहक आपको पैसे कैसे देंगे?",
    pay_s: "वे आपकी UPI ID पर पैसे भेजेंगे। पैसा सीधे आपके पास आएगा।",
    upi: "आपकी UPI ID", upi_ph: "name@okaxis",
    upi_where: "मेरी UPI ID कहाँ मिलेगी?",
    upi_gpay: "Google Pay: अपनी फ़ोटो पर टैप करें। नाम के नीचे UPI ID है।",
    upi_phonepe: "PhonePe: अपनी फ़ोटो पर टैप करें। UPI ID देखें।",
    upi_paytm: "Paytm: अपनी फ़ोटो पर टैप करें। UPI ID देखें।",
    cod_on: "कैश ऑन डिलीवरी भी चालू है।", cod_off: "कैश ऑन डिलीवरी बंद है।",
    not_inr: "UPI सिर्फ़ रुपये वाली दुकानों में चलता है।", to_inr: "मेरी दुकान रुपये में करें",
    razorpay: "इसके बजाय Razorpay इस्तेमाल करें",
    p1_done_t: "आपकी दुकान ऑनलाइन है!", p1_done_s: "इसे वहाँ शेयर करें जहाँ आपके ग्राहक हैं।",
    share_wa: "WhatsApp पर शेयर करें", copy_bio: "Instagram बायो के लिए कॉपी करें",
    bio_how: "Instagram: Edit profile, फिर Links, फिर पेस्ट करें।",
    copied: "लिंक कॉपी हो गया।",
    p1_notlive_t: "आपकी दुकान अभी ऑनलाइन नहीं है", p1_notlive_s: "यह आपकी टास्क लिस्ट में है।",
    put_online: "अभी ऑनलाइन करें",
    more_parts: "दो भाग और",
    more_p2: "हम आपकी Instagram पोस्ट बनाएँ", more_p2_s: "लगभग 10 मिनट",
    more_p3: "स्टॉक कभी खत्म न हो", more_p3_s: "लगभग 5 मिनट",
    start_p2: "भाग 2 शुरू करें", later: "बाद में (टास्क लिस्ट में है)",
    wa_share_text: "मेरी दुकान ऑनलाइन है! यहाँ ऑर्डर करें: {url}",
    connect_t: "आपकी वेबसाइट कहाँ है?",
    connect_other: "कुछ और", connect_other_s: "बिक्री की फ़ाइल डालें (Excel या CSV)",
    make_instead: "मेरी वेबसाइट नहीं है। मेरे लिए बनाइए।",
    connect_btn: "जोड़ें", connecting: "जोड़ रहे हैं…", pulling: "आपके ऑर्डर ला रहे हैं…",
    connect_how: "ये कहाँ मिलेंगे",
    upload_t: "बिक्री की फ़ाइल डालें", upload_s: "जहाँ भी आप बेचते हैं, वहाँ से ऑर्डर Excel या CSV में निकालें।",
    choose_file: "फ़ाइल चुनें",
    catalogue_t: "आपकी बिक्री में {n} प्रोडक्ट मिले",
    catalogue_s: "इन्हें अपनी सूची में जोड़ें ताकि हर बिक्री गिनी जाए।",
    catalogue_add: "इन्हें मेरी सूची में जोड़ें",
    catalogue_none_t: "अपने प्रोडक्ट जोड़ें", catalogue_none_s: "आपकी बिक्री में अभी प्रोडक्ट नहीं मिले।",
    c_done_t: "आपकी बिक्री आ गई", c_orders: "ऑर्डर", c_customers: "ग्राहक",
    c_top: "सबसे ज़्यादा बिकने वाले",
    c_want_shop: "एक मुफ़्त One Tap दुकान भी चाहिए?", c_want_shop_s: "आपकी अपनी वेबसाइट, बिक्री पर कोई कमीशन नहीं।",
    c_make_shop: "हाँ, मेरी दुकान बनाइए",
    p2_intro_t: "हम आपकी Instagram पोस्ट बनाएँ",
    p2_i1: "आप फ़ोटो डालें", p2_i2: "हम आपका लुक समझें", p2_i3: "हम पोस्ट बनाएँ, आप हाँ कहें",
    brand_t: "अपने ब्रांड के बारे में बताएँ",
    brand_make: "आप क्या बनाते हैं?", brand_make_ph: "जयपुर के हाथ-छपाई वाले कॉटन कुर्ते।",
    brand_who: "इसे कौन खरीदता है?", brand_who_ph: "वे महिलाएँ जो रोज़ के लिए खास कॉटन चाहती हैं।",
    brand_err: "एक लाइन लिखें कि आप क्या बनाते हैं।",
    style_t: "अपने स्टाइल की 3 फ़ोटो जोड़ें",
    style_s: "ऐसी तस्वीरें जिनका लुक आपको पसंद है: पैकेजिंग, दुकान, या पसंदीदा फ़ोटो।",
    style_count: "3 में से {n} जुड़ीं", add_photos: "फ़ोटो जोड़ें",
    photos_t: "प्रोडक्ट की फ़ोटो जोड़ें", photos_s: "हर प्रोडक्ट की एक साफ़ फ़ोटो। खिड़की के पास फ़ोन काफ़ी है।",
    photos_none: "पहले एक प्रोडक्ट जोड़ें।",
    ig_t: "Instagram जोड़ें", ig_s: "ताकि आपकी पोस्ट अपने आप जाएँ।",
    ig_need: "आपका Instagram बिज़नेस या क्रिएटर अकाउंट होना चाहिए। यह मुफ़्त है।",
    ig_how: "कैसे बदलें",
    ig_how_1: "Instagram खोलें और अपनी प्रोफ़ाइल पर जाएँ।",
    ig_how_2: "मेन्यू पर टैप करें, फिर Account type and tools।",
    ig_how_3: "Switch to professional account पर टैप करें।",
    ig_btn: "Instagram जोड़ें", ig_done: "Instagram जुड़ गया।",
    p2_done_t: "आपका सोशल मीडिया मैनेजर तैयार है",
    p2_done_s: "यह आपकी फ़ोटो से हफ़्ते भर की पोस्ट बनाता है। आपकी हाँ के बिना कुछ नहीं जाता।",
    p2_ai: "पोस्ट बनाने में AI लगता है, और हर AI तस्वीर पर लेबल होता है।",
    plan_week: "मेरा पहला हफ़्ता बनाएँ", next_p3: "आगे: भाग 3",
    p3_intro_t: "स्टॉक कभी खत्म न हो",
    p3_i1: "बताएँ आप किससे खरीदते हैं", p3_i2: "हम देखें क्या बिकता है", p3_i3: "खत्म होने से पहले हम बताएँ",
    sup_t: "आप माल किससे खरीदते हैं?", sup_name: "सप्लायर का नाम", sup_name_ph: "शर्मा टेक्सटाइल्स",
    sup_phone: "उनका WhatsApp (ज़रूरी नहीं)", sup_days: "माल आने में कितने दिन लगते हैं?",
    sup_err: "सप्लायर का नाम लिखें।", days_err: "दिन 1 से 120 के बीच हों।",
    skip_both: "स्टॉक के लिए सप्लायर चाहिए, इसलिए दोनों छूट जाएँगे।",
    stock_t: "आपके पास कितने हैं?", stock_s: "अभी शेल्फ़ पर जितना है, वह गिनें।",
    search: "ढूँढें", stock_more: "20 दिख रहे हैं। बाकी के लिए ढूँढें।",
    p3_done_t: "खत्म होने से पहले आपको पता चल जाएगा",
    p3_example: "उदाहरण", p3_ex_1: "{name} रोज़ लगभग 2 बिकता है।",
    p3_ex_2: "सप्लायर {d} दिन लेता है।", p3_ex_3: "{n} बचने पर हम बताएँगे।",
    p3_ex_why: "2 × {d} = {base}, और थोड़ा सुरक्षा के लिए।",
    all_done_t: "आपकी दुकान पूरी तैयार है", all_done_s: "सब तैयार है। बहुत बढ़िया।",
    left_t: "बस थोड़ा बाकी", left_s: "आपने ये छोड़े थे। जब चाहें तब कर लें।",
    done: "हो गया", go_home: "मेरी दुकान पर जाएँ",
    card_title: "3 भागों में अपनी दुकान तैयार करें",
    card_sub: "दुकान ऑनलाइन, आपकी पोस्ट, आपका स्टॉक। एक-एक छोटा कदम।",
    card_next: "अगला: {step}", card_continue: "जारी रखें", card_hide: "छिपाएँ",
    card_skipped: "{n} छोड़े गए कदम बाकी", card_finish: "पूरे करें",
    setup_guide: "सेटअप गाइड",
    step_shop: "दुकान का नाम रखें", step_products: "3 प्रोडक्ट जोड़ें", step_site: "दुकान ऑनलाइन करें",
    step_payment: "UPI ID जोड़ें", step_connect: "अपनी वेबसाइट जोड़ें",
    step_catalogue: "अपने प्रोडक्ट जोड़ें", step_brand: "अपने ब्रांड के बारे में बताएँ",
    step_style: "स्टाइल की 3 फ़ोटो जोड़ें", step_photos: "प्रोडक्ट की फ़ोटो जोड़ें",
    step_instagram: "Instagram जोड़ें", step_suppliers: "सप्लायर जोड़ें",
    step_stock: "स्टॉक गिनें",
    uploading: "अपलोड हो रहा है…", upload_failed: "फ़ोटो अपलोड नहीं हुई।", retry: "फिर से कोशिश करें",
    open: "खोलें",
  },
};

/* ------------------------------------------------------------- state ---- */
let J = null;              // the last /api/onboarding payload
let _jScreen = null;       // the screen on show
let _jHist = [];           // back stack of screen ids
let _jDraft = {};          // what the seller typed, kept across errors and Back
let _jBusy = false;
let _jThemes = null;       // theme catalogue, fetched once
let _jReturnFocus = null;

const JLANG = () => ((J && J.lang) === "hi" ? "hi" : "en");
function jt(key, vars) {
  let s = (JT[JLANG()] && JT[JLANG()][key]) || JT.en[key] || key;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.split(`{${k}}`).join(String(v));
  return s;
}

/* The first screen for each step. */
const STEP_SCREEN = {
  shop: "shop_name", products: "products", site: "site_look", payment: "payment",
  connect: "connect_pick", catalogue: "catalogue",
  brand: "brand", style: "style", photos: "photos", instagram: "instagram",
  suppliers: "supplier", stock: "supplier",
};
/* Which step each screen belongs to (for Skip and the progress dots). */
const SCREEN_STEP = {
  shop_name: "shop", shop_type: "shop", products: "products",
  site_look: "site", site_address: "site", site_wa: "site", site_about: "site",
  site_delivery: "site", site_preview: "site", payment: "payment",
  connect_pick: "connect", connect_form: "connect", connect_upload: "connect",
  catalogue: "catalogue", brand: "brand", style: "style", photos: "photos",
  instagram: "instagram", supplier: "suppliers", stock: "stock",
};
/* Screens that belong to a part but not to one step. */
const SCREEN_PART = { part1_done: 1, p2_intro: 2, part2_done: 2, p3_intro: 3, part3_done: 3 };
const THEME_FOR = { jewellery: "jewellery", clothes: "fashion", perfumes: "beauty", generic: "basic" };

/* ------------------------------------------------------------ server ---- */
async function jLoad() { J = await api("/api/onboarding"); return J; }
async function jAct(action, extra) {
  J = await api("/api/onboarding", { method: "POST", json: { action, ...(extra || {}) } });
  jTasks();
  return J;
}
async function jSave(what, body) {
  J = await api(`/api/onboarding/save/${what}`, { method: "POST", json: body || {} });
  jTasks();
  return J;
}
function jTasks() {
  if (J && J.tasks && typeof refreshTaskList === "function" && document.getElementById("taskList")) {
    try { refreshTaskList(J.tasks); } catch (e) { /* home not on screen */ }
  }
}
const jStep = (id) => {
  for (const p of (J && J.parts) || []) for (const s of p.steps) if (s.id === id) return s;
  return null;
};
const jDone = (id) => !!(jStep(id) || {}).done;
const jPartOf = (step) => { for (const p of (J && J.parts) || []) if (p.steps.some((s) => s.id === step)) return p.n; return 1; };

/* ----------------------------------------------------------- the sheet --- */
async function openJourney(opts) {
  opts = opts || {};
  _jReturnFocus = document.activeElement;
  jShell();
  jBody(`<div class="jr-loading" role="status">${esc(jt("saving").replace("…", ""))}…</div>`);
  try {
    await jLoad();
    if (!J.has_record) await jAct("start");
    if (J.dismissed) await jAct("undismiss");
    if (J.new_account) jAct("welcomed").catch(() => {});
  } catch (e) { jBody(`<div class="jr-err">${esc(e.message)}</div>`); return; }
  _jHist = [];
  let first = null;
  if (opts.step && STEP_SCREEN[opts.step]) first = STEP_SCREEN[opts.step];
  else if (opts.part) first = jPartEntry(opts.part);
  else first = jWhereNow();
  jGo(first, true);
}
window.openJourney = openJourney;

function jWhereNow() {
  if (!J.path) return "welcome";
  if ((J.unseen_done || []).length) return `part${J.unseen_done[0]}_done`;
  if (!J.next) return "all_done";
  const part = J.next.part;
  const p = J.parts[part - 1];
  if (part > 1 && !p.opened) return `p${part}_intro`;
  return STEP_SCREEN[J.next.step];
}

function jPartEntry(n) {
  if (n === 1) {
    if (!J.path) return "welcome";
    const s = J.parts[0].steps.find((x) => !x.done);
    return s ? STEP_SCREEN[s.id] : "part1_done";
  }
  const p = J.parts[n - 1];
  if (!p.opened) return `p${n}_intro`;
  const s = p.steps.find((x) => !x.done);
  return s ? STEP_SCREEN[s.id] : `part${n}_done`;
}

/* Where to go after a step's last screen: the first unfinished step in this
   part, or the part's finish screen. Done steps are passed with a tick. */
async function jAdvance() {
  const cur = SCREEN_STEP[_jScreen];
  const part = cur ? jPartOf(cur) : (J.next && J.next.part) || 1;
  const p = J.parts[part - 1];
  if (p && p.finished) return jGo(`part${part}_done`);
  const s = p && p.steps.find((x) => !x.done && !x.skipped);
  if (s) return jGo(STEP_SCREEN[s.id]);
  return jGo(jWhereNow());
}

function jShell() {
  if (document.getElementById("jrBack")) return;
  const back = document.createElement("div");
  back.id = "jrBack";
  back.className = "jr-back";
  back.innerHTML = `
    <div class="jr" role="dialog" aria-modal="true" aria-labelledby="jrTitle" id="jr">
      <div class="jr-head">
        <button class="jr-icon" id="jrPrev" type="button" aria-label="${esc(jt("back"))}">${sic("arrow-left")}</button>
        <div class="jr-where"><span id="jrPart"></span><div class="jr-dots" id="jrDots" aria-hidden="true"></div></div>
        <div class="jr-lang" role="group" aria-label="Language">
          <button type="button" data-jlang="en">English</button><button type="button" data-jlang="hi" lang="hi">हिंदी</button>
        </div>
        <button class="jr-icon" id="jrClose" type="button" aria-label="${esc(jt("finish_later"))}" title="${esc(jt("finish_later"))}">${sic("close")}</button>
      </div>
      <div class="jr-body" id="jrBody"></div>
      <div class="jr-foot" id="jrFoot"></div>
      <div class="jr-confirm" id="jrConfirm" hidden></div>
    </div>`;
  document.body.appendChild(back);
  document.body.classList.add("jr-open");
  $("jrClose").onclick = closeJourney;
  $("jrPrev").onclick = jBackStep;
  back.addEventListener("keydown", jKeys);
  back.querySelectorAll("[data-jlang]").forEach((b) => b.onclick = async () => {
    if (_jBusy || b.dataset.jlang === JLANG()) return;
    try { await jAct("set_lang", { lang: b.dataset.jlang }); jGo(_jScreen, true, true); }
    catch (e) { toast(e.message); }
  });
}

function closeJourney() {
  const back = document.getElementById("jrBack");
  if (back) back.remove();
  document.body.classList.remove("jr-open");
  window.removeEventListener("focus", jOnFocus);
  if (_jReturnFocus && _jReturnFocus.focus) { try { _jReturnFocus.focus(); } catch (e) { /* gone */ } }
  // The home card and task list reflect what just happened.
  if (typeof _currentModule !== "undefined" && _currentModule === null && typeof goHome === "function") goHome();
}
window.closeJourney = closeJourney;

function jKeys(e) {
  if (e.key === "Escape") {
    e.preventDefault();
    const c = $("jrConfirm");
    if (c && !c.hidden) { jHideConfirm(); return; }
    closeJourney();
    return;
  }
  if (e.key !== "Tab") return;
  // Keep focus inside the sheet while it is open.
  const root = $("jr");
  const f = Array.from(root.querySelectorAll('button:not([disabled]),a[href],input:not([disabled]),textarea,select,[tabindex="0"]'))
    .filter((el) => el.offsetParent !== null && !el.closest("[hidden]"));
  if (!f.length) return;
  const first = f[0], last = f[f.length - 1];
  if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
}

function jBackStep() {
  if (_jBusy) return;
  const prev = _jHist.pop();
  if (prev) jGo(prev, true);
}

function jBody(html) { const b = $("jrBody"); if (b) b.innerHTML = html; }

function jHeader(step, screen) {
  const part = step ? jPartOf(step) : SCREEN_PART[screen] || (J.next && J.next.part) || 1;
  const name = part === 1 ? (J.path === "connect" ? jt("part1_connect") : jt("part1_create"))
    : part === 2 ? jt("part2") : jt("part3");
  $("jrPart").textContent = `${jt("part_of", { n: part })} · ${name}`;
  const p = J.parts[part - 1] || { steps: [] };
  $("jrDots").innerHTML = p.steps.map((s) =>
    `<i class="${s.done ? "done" : s.skipped ? "skipped" : ""} ${s.id === step ? "on" : ""}"></i>`).join("");
  document.querySelectorAll("[data-jlang]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.jlang === JLANG())));
  $("jrPrev").style.visibility = _jHist.length ? "visible" : "hidden";
  $("jrClose").setAttribute("aria-label", jt("finish_later"));
  $("jrPrev").setAttribute("aria-label", jt("back"));
}

/* Paint a screen. `replace` does not push history (Back, reloads). */
function jGo(id, replace, keepFocus) {
  if (!id) id = "all_done";
  if (!replace && _jScreen && _jScreen !== id) _jHist.push(_jScreen);
  _jScreen = id;
  jHideConfirm();
  const fn = SCREENS[id] || SCREENS.all_done;
  const step = SCREEN_STEP[id];
  jHeader(step, id);
  const out = fn();
  const lang = JLANG();
  $("jr").setAttribute("lang", lang === "hi" ? "hi" : "en");
  jBody(`<h2 class="jr-title" id="jrTitle" tabindex="-1">${esc(out.title)}</h2>
    ${out.sub ? `<p class="jr-sub">${esc(out.sub)}</p>` : ""}
    <div class="jr-content">${out.body || ""}</div>
    <div class="jr-err" id="jrErr" role="alert" hidden></div>`);
  const foot = [];
  if (out.primary) foot.push(`<button class="btn primary jr-main" id="jrMain" type="button"${out.primary.disabled ? " disabled" : ""}>${esc(out.primary.label)}</button>`);
  if (out.secondary) foot.push(`<button class="btn ghost jr-second" id="jrSecond" type="button">${esc(out.secondary.label)}</button>`);
  if (out.skip) foot.push(`<button class="jr-skip" id="jrSkip" type="button">${esc(jt("skip"))}</button>`);
  $("jrFoot").innerHTML = foot.join("");
  $("jrFoot").hidden = !foot.length;
  if (out.primary) $("jrMain").onclick = () => jRun($("jrMain"), out.primary.run);
  if (out.secondary) $("jrSecond").onclick = () => jRun($("jrSecond"), out.secondary.run);
  if (out.skip) $("jrSkip").onclick = () => jAskSkip(out.skip);
  if (out.wire) out.wire();
  if (step && jStep(step) && !jDone(step)) jAct("seen_step", { step }).catch(() => {});
  if (!keepFocus) requestAnimationFrame(() => {
    const auto = document.querySelector("#jrBody [data-autofocus]");
    (auto || $("jrTitle")).focus({ preventScroll: false });
  });
  const body = $("jrBody"); if (body) body.scrollTop = 0;
}

/* Every button that saves: busy while it runs, errors shown next to the form,
   what was typed is never lost. */
async function jRun(btn, fn) {
  if (_jBusy || !fn) return;
  _jBusy = true;
  const label = btn ? btn.innerHTML : "";
  if (btn) { btn.disabled = true; btn.innerHTML = esc(jt("saving")); }
  jErr("");
  try { await fn(); }
  catch (e) { jErr(e.message || String(e)); }
  finally {
    _jBusy = false;
    if (btn && btn.isConnected) { btn.disabled = false; btn.innerHTML = label; }
  }
}
function jErr(msg) {
  const el = $("jrErr"); if (!el) return;
  el.textContent = msg || ""; el.hidden = !msg;
}
const jErrorOf = (key) => { throw new Error(jt(key)); };

/* ------------------------------------------------------------- skip ---- */
function jAskSkip(steps) {
  const list = Array.isArray(steps) ? steps : [steps];
  const box = $("jrConfirm");
  box.innerHTML = `
    <div class="jr-confirm-card" role="alertdialog" aria-modal="true" aria-labelledby="jrSkipQ" aria-describedby="jrSkipS">
      <h3 id="jrSkipQ">${esc(jt("skip_q"))}</h3>
      <p id="jrSkipS">${esc(jt("skip_sub"))}${list.length > 1 ? " " + esc(jt("skip_both")) : ""}</p>
      <button class="btn primary jr-main" id="jrSkipNo" type="button">${esc(jt("skip_no"))}</button>
      <button class="btn ghost jr-second" id="jrSkipYes" type="button">${esc(jt("skip_yes"))}</button>
    </div>`;
  box.hidden = false;
  $("jrSkipNo").onclick = jHideConfirm;
  $("jrSkipYes").onclick = () => jRun($("jrSkipYes"), async () => {
    for (const s of list) await jAct("skip", { step: s });
    jHideConfirm();
    toast(jt("skip_done"));
    await jAdvance();
  });
  requestAnimationFrame(() => $("jrSkipNo").focus());
}
function jHideConfirm() {
  const box = $("jrConfirm");
  if (box && !box.hidden) {
    box.hidden = true; box.innerHTML = "";
    const m = $("jrSkip"); if (m) m.focus();
  }
}

/* ----------------------------------------------------------- helpers --- */
function jChoice(id, icon, title, sub, on) {
  return `<button type="button" class="jr-choice${on ? " on" : ""}" data-choice="${esc(id)}" aria-pressed="${on ? "true" : "false"}">
      <span class="jr-choice-i" aria-hidden="true">${sic(icon)}</span>
      <span class="jr-choice-t"><b>${esc(title)}</b>${sub ? `<span>${esc(sub)}</span>` : ""}</span>
    </button>`;
}
function jField(id, label, attrs, hint) {
  return `<label class="jr-field" for="${id}"><span>${esc(label)}</span>
      <input id="${id}" ${attrs || ""} />${hint ? `<small>${esc(hint)}</small>` : ""}</label>`;
}
const jVal = (id) => ((document.getElementById(id) || {}).value || "").trim();
const F = () => (J && J.facts) || {};
function jSteps3(a, b, c, icons) {
  return `<ol class="jr-how">${[a, b, c].map((txt, i) =>
    `<li><span class="jr-how-i" aria-hidden="true">${sic(icons[i])}</span><b>${esc(txt)}</b></li>`).join("")}</ol>`;
}

/* Phone photos are several MB; the server has 512MB and the seller may be on
   slow mobile data. Resized here to 1600px JPEG before it leaves the phone. */
async function jShrink(file) {
  try {
    if (!/^image\/(jpeg|png|webp)$/i.test(file.type)) return file;
    const bmp = await createImageBitmap(file, { imageOrientation: "from-image" });
    const scale = Math.min(1, 1600 / Math.max(bmp.width, bmp.height));
    if (scale === 1 && file.size < 900 * 1024) return file;
    const cv = document.createElement("canvas");
    cv.width = Math.round(bmp.width * scale); cv.height = Math.round(bmp.height * scale);
    cv.getContext("2d").drawImage(bmp, 0, 0, cv.width, cv.height);
    const blob = await new Promise((res) => cv.toBlob(res, "image/jpeg", 0.85));
    if (!blob) return file;
    return new File([blob], (file.name || "photo").replace(/\.\w+$/, "") + ".jpg", { type: "image/jpeg" });
  } catch (e) { return file; }
}
function jPickPhotos(multiple) {
  return new Promise((resolve) => {
    const inp = document.createElement("input");
    inp.type = "file"; inp.accept = "image/*"; inp.multiple = !!multiple;
    inp.style.display = "none";
    inp.onchange = () => { resolve(Array.from(inp.files || [])); inp.remove(); };
    document.body.appendChild(inp);
    inp.click();
  });
}
async function jUpload(file, onFrac) {
  const small = await jShrink(file);
  const fd = new FormData(); fd.append("files", small);
  const r = await apiUpload("/api/site/image", fd, onFrac);
  if (!r.image_url) throw new Error(jt("upload_failed"));
  return r.image_url;
}
function jPublicUrl() { return F().public_path ? location.origin + F().public_path : ""; }
async function jCopy(text) {
  try { await navigator.clipboard.writeText(text); toast(jt("copied")); }
  catch (e) { window.prompt("", text); }
}
function jThumb(url) {
  return `<span class="jr-thumb" style="${url ? `background-image:url('${esc(url)}')` : ""}">${url ? "" : sic("image")}</span>`;
}

/* ============================================================ SCREENS ==== */
const SCREENS = {
  /* ---------------------------------------------------------- welcome */
  welcome() {
    return {
      title: jt("welcome_t"), sub: jt("welcome_s"),
      body: `<p class="jr-q">${esc(jt("welcome_q"))}</p>
        <div class="jr-choices">
          ${jChoice("connect", "globe", jt("have_site"), jt("have_site_s"))}
          ${jChoice("create", "bag", jt("make_site"), jt("make_site_s"))}
        </div>`,
      wire() {
        document.querySelectorAll("#jrBody [data-choice]").forEach((b) => b.onclick = () => jRun(b, async () => {
          await jAct("choose_path", { path: b.dataset.choice });
          await jAct("open_part", { part: 1 });
          jGo(b.dataset.choice === "connect" ? "connect_pick" : jPartEntry(1));
        }));
      },
    };
  },

  /* ------------------------------------------------------------- shop */
  shop_name() {
    const v = _jDraft.shop_name != null ? _jDraft.shop_name : (F().shop_name || "");
    return {
      title: jt("shop_name_t"),
      body: jField("jrShopName", jt("shop_name_t"),
        `value="${esc(v)}" maxlength="60" autocomplete="organization" placeholder="${esc(jt("shop_name_ph"))}" data-autofocus class="jr-big"`),
      primary: { label: jt("next"), run: async () => {
        const name = jVal("jrShopName");
        if (name.length < 2) jErrorOf("shop_name_err");
        _jDraft.shop_name = name;
        jGo("shop_type");
      } },
      skip: "shop",
      wire() {
        const i = $("jrShopName");
        i.oninput = () => { _jDraft.shop_name = i.value; };
        i.onkeydown = (e) => { if (e.key === "Enter") $("jrMain").click(); };
        // The field has a visible heading already; the label is for readers.
        i.previousElementSibling.classList.add("jr-sr");
      },
    };
  },
  shop_type() {
    // Only an answer the seller gave counts; the app's own default does not.
    const cur = _jDraft.product_type
      || (F().product_type_chosen && typeof state !== "undefined" && state.productType) || "";
    if (cur) _jDraft.product_type = cur;
    const types = [["clothes", "scissors"], ["jewellery", "spark"], ["perfumes", "droplet"], ["generic", "bag"]];
    return {
      title: jt("shop_type_t"),
      body: `<div class="jr-choices two">${types.map(([id, ic]) => jChoice(id, ic, jt("type_" + id), "", cur === id)).join("")}</div>
        <div id="jrOwnBox"${cur === "generic" ? "" : " hidden"}>${jField("jrOwn", jt("type_own"),
          `maxlength="40" value="${esc(_jDraft.label || "")}" placeholder="${esc(jt("type_own_ph"))}"`)}</div>`,
      primary: { label: jt("next"), disabled: !cur, run: async () => {
        const pt = _jDraft.product_type;
        if (!pt) return;
        await jSave("shop", { name: _jDraft.shop_name || F().shop_name || "", product_type: pt,
                              label: pt === "generic" ? jVal("jrOwn") : "" });
        if (typeof state !== "undefined") state.productType = pt;
        await jAdvance();
      } },
      skip: "shop",
      wire() {
        document.querySelectorAll("#jrBody [data-choice]").forEach((b) => b.onclick = () => {
          _jDraft.product_type = b.dataset.choice;
          document.querySelectorAll("#jrBody [data-choice]").forEach((x) => {
            x.classList.toggle("on", x === b); x.setAttribute("aria-pressed", String(x === b));
          });
          $("jrOwnBox").hidden = b.dataset.choice !== "generic";
          $("jrMain").disabled = false;
        });
      },
    };
  },

  /* --------------------------------------------------------- products */
  products() {
    const prods = F().products || [];
    const n = prods.length;
    const photo = _jDraft.p_photo || "";
    const list = prods.slice(0, 12).map((p) => `
      <li class="jr-prod">${jThumb(p.image_url)}<span><b>${esc(p.name)}</b>
        <small>${p.price != null ? "₹" + esc(fmt(p.price)) : ""}</small></span>
        <button class="jr-icon sm" type="button" data-pdel="${esc(p.id)}" aria-label="Remove ${esc(p.name)}">${sic("close")}</button></li>`).join("");
    return {
      title: jt("products_t"), sub: jt("products_s"),
      body: `
        <div class="jr-count"><b>${esc(n >= 3 ? jt("products_more", { n }) : jt("products_count", { n }))}</b>
          <span class="jr-bar"><i style="width:${Math.min(100, n / 3 * 100)}%"></i></span></div>
        ${n ? `<ul class="jr-prods">${list}</ul>` : ""}
        <div class="jr-card">
          <button type="button" class="jr-photo" id="jrPhoto" aria-label="${esc(photo ? jt("change_photo") : jt("add_photo"))}">
            ${photo ? `<img src="${esc(photo)}" alt="" />` : `${sic("camera")}<span>${esc(jt("add_photo"))}</span>`}
          </button>
          <div class="jr-card-fields">
            ${jField("jrPName", jt("p_name"), `maxlength="160" value="${esc(_jDraft.p_name || "")}" placeholder="${esc(jt("p_name_ph"))}"${n < 3 ? " data-autofocus" : ""}`)}
            ${jField("jrPPrice", jt("p_price"), `inputmode="decimal" maxlength="9" value="${esc(_jDraft.p_price || "")}" placeholder="${esc(jt("p_price_ph"))}"`)}
            <button class="btn ${n < 3 ? "primary" : "ghost"} jr-add" id="jrPAdd" type="button">${sic("plus")}${esc(jt("add_product"))}</button>
          </div>
          <div class="jr-up" id="jrPUp" hidden></div>
        </div>`,
      primary: { label: n >= 3 ? jt("next") : jt("need_3", { n: 3 - n }), disabled: n < 3, run: jAdvance },
      skip: "products",
      wire() {
        $("jrPName").oninput = (e) => { _jDraft.p_name = e.target.value; };
        $("jrPPrice").oninput = (e) => { _jDraft.p_price = e.target.value; };
        $("jrPhoto").onclick = async () => {
          const files = await jPickPhotos(false);
          if (!files.length) return;
          const up = $("jrPUp"); up.hidden = false; up.textContent = jt("uploading");
          try {
            _jDraft.p_photo = await jUpload(files[0], (f) => { if (f != null) up.textContent = `${jt("uploading")} ${Math.round(f * 100)}%`; });
            jGo("products", true, true);
          } catch (e) { up.textContent = `${jt("upload_failed")} ${e.message || ""}`; }
        };
        $("jrPAdd").onclick = () => jRun($("jrPAdd"), async () => {
          const name = jVal("jrPName");
          const price = parseFloat(jVal("jrPPrice").replace(/[₹,\s]/g, ""));
          if (!name) jErrorOf("p_name_err");
          if (!(price > 0)) jErrorOf("p_price_err");
          const img = _jDraft.p_photo || "";
          // Stock is not tracked yet, so the product can be ordered straight
          // away; Part 3 switches counting on once there is a number.
          await api("/api/products/item", { method: "POST", json: {
            name, price, image_url: img, images: img ? [img] : [], listed: true,
            track_stock: false, stock: 0, status: "active" } });
          _jDraft.p_name = ""; _jDraft.p_price = ""; _jDraft.p_photo = "";
          await jAct("sync");
          jGo("products", true);
          requestAnimationFrame(() => { const i = $("jrPName"); if (i) i.focus(); });
        });
        document.querySelectorAll("[data-pdel]").forEach((b) => b.onclick = () => jRun(b, async () => {
          await api("/api/products/item/delete", { method: "POST", json: { id: b.dataset.pdel } });
          await jAct("sync");
          toast(jt("removed"));
          jGo("products", true, true);
        }));
      },
    };
  },

  /* ------------------------------------------------------------- site */
  site_look() {
    const f = F();
    if (!jDone("shop") || !(f.products || []).length) {
      return {
        title: jt("gate_t"),
        body: `<div class="jr-choices">
          ${!jDone("shop") ? jChoice("shop_name", "tag", jt("gate_name"), "") : ""}
          ${!(f.products || []).length ? jChoice("products", "bag", jt("gate_products"), "") : ""}</div>`,
        skip: "site",
        wire() { document.querySelectorAll("#jrBody [data-choice]").forEach((b) => b.onclick = () => jGo(b.dataset.choice)); },
      };
    }
    const rec = THEME_FOR[(typeof state !== "undefined" && state.productType) || "generic"] || "basic";
    // "basic" is every new site's built-in default, not a choice the seller
    // made, so the look suggested for what they sell wins over it.
    const cur = _jDraft.theme || (f.theme && f.theme !== "basic" ? f.theme : rec);
    _jDraft.theme = cur;
    const ordered = (_jThemes || []).slice().sort((a, b) => (b.id === rec) - (a.id === rec));
    const cards = ordered.map((th) => {
      const c = th.light || {};
      return `<button type="button" class="jr-theme${th.id === cur ? " on" : ""}" data-theme-id="${esc(th.id)}" aria-pressed="${th.id === cur}">
        <span class="jr-theme-art" style="background:${esc(c.bg || "#fff")};color:${esc(c.ink || "#111")}">
          <i style="background:${esc(c.accent || "#111")}"></i><i style="background:${esc(c.surface || "#eee")}"></i><i style="background:${esc(c.surface || "#eee")}"></i>
          <em>Aa</em></span>
        <span class="jr-theme-l"><b>${esc(th.label)}</b>${th.id === rec ? `<small>${esc(jt("look_rec"))}</small>` : ""}</span></button>`;
    }).join("");
    return {
      title: jt("look_t"), sub: jt("look_s"),
      body: _jThemes ? `<div class="jr-themes">${cards}</div>` : `<div class="jr-loading">…</div>`,
      primary: { label: jt("next"), run: async () => { await jSave("site", { theme: _jDraft.theme }); jGo("site_address"); } },
      skip: "site",
      wire() {
        if (!_jThemes) {
          api("/api/site/state").then((d) => { _jThemes = d.themes || []; if (_jScreen === "site_look") jGo("site_look", true, true); })
            .catch((e) => jErr(e.message));
          return;
        }
        document.querySelectorAll("[data-theme-id]").forEach((b) => b.onclick = () => {
          _jDraft.theme = b.dataset.themeId;
          document.querySelectorAll("[data-theme-id]").forEach((x) => {
            x.classList.toggle("on", x === b); x.setAttribute("aria-pressed", String(x === b));
          });
        });
      },
    };
  },
  site_address() {
    const sug = _jDraft.handle != null ? _jDraft.handle : (F().handle || F().suggested_handle || "");
    const latin = /[a-z0-9]/i.test(F().shop_name || "");
    return {
      title: jt("address_t"), sub: jt("address_s"),
      body: `<label class="jr-field" for="jrHandle"><span class="jr-sr">${esc(jt("address_t"))}</span>
          <span class="jr-url"><span>${esc(location.host)}/</span>
          <input id="jrHandle" value="${esc(latin || F().handle ? sug : "")}" maxlength="30" autocapitalize="none" autocomplete="off" spellcheck="false"
            placeholder="priya-kurtis" data-autofocus /></span>
          <small>${esc(jt("address_hint"))}</small></label>
        <div class="jr-check" id="jrHandleCheck" aria-live="polite"></div>`,
      primary: { label: jt("next"), run: async () => {
        const h = jVal("jrHandle").toLowerCase();
        if (h.replace(/[^a-z0-9]/g, "").length < 3) jErrorOf("address_short");
        await jSave("site", { handle: h });
        jGo("site_wa");
      } },
      skip: "site",
      wire() {
        const inp = $("jrHandle");
        let tm = null;
        const check = async () => {
          const raw = inp.value.trim().toLowerCase();
          _jDraft.handle = raw;
          const box = $("jrHandleCheck");
          if (raw.replace(/[^a-z0-9]/g, "").length < 3) { box.textContent = ""; return; }
          try {
            const r = await api(`/api/site/handle-check?handle=${encodeURIComponent(raw)}`);
            if (r.available) { box.innerHTML = `<span class="ok">${sic("check")}${esc(jt("address_ok"))}</span>`; return; }
            const alts = [];
            for (const tryH of [`${r.handle}-shop`, `${r.handle}-${new Date().getFullYear() % 100}`, `${r.handle}-india`]) {
              if (alts.length >= 2) break;
              try { const x = await api(`/api/site/handle-check?handle=${encodeURIComponent(tryH)}`); if (x.available) alts.push(x.handle); }
              catch (e) { /* skip */ }
            }
            box.innerHTML = `<span class="bad">${esc(jt("address_taken"))}</span> ${alts.map((a) =>
              `<button type="button" class="jr-chip" data-alt="${esc(a)}">${esc(a)}</button>`).join(" ")}`;
            box.querySelectorAll("[data-alt]").forEach((b) => b.onclick = () => { inp.value = b.dataset.alt; check(); });
          } catch (e) { box.textContent = ""; }
        };
        inp.oninput = () => {
          inp.value = inp.value.toLowerCase().replace(/[^a-z0-9-]/g, "-").replace(/-{2,}/g, "-");
          clearTimeout(tm); tm = setTimeout(check, 350);
        };
        inp.onkeydown = (e) => { if (e.key === "Enter") $("jrMain").click(); };
        check();
      },
    };
  },
  site_wa() {
    const cur = _jDraft.wa != null ? _jDraft.wa : String(F().whatsapp || "").replace(/^\+91/, "");
    return {
      title: jt("wa_t"), sub: jt("wa_s"),
      body: `<label class="jr-field" for="jrWa"><span class="jr-sr">${esc(jt("wa_t"))}</span>
        <span class="jr-url"><span>+91</span><input id="jrWa" type="tel" inputmode="numeric" autocomplete="tel-national"
          maxlength="14" value="${esc(cur)}" placeholder="98765 43210" data-autofocus /></span></label>`,
      primary: { label: jt("next"), run: async () => {
        const d = jVal("jrWa").replace(/\D/g, "").replace(/^91(?=\d{10}$)/, "");
        if (d.length !== 10) jErrorOf("wa_err");
        _jDraft.wa = d;
        await jSave("site", { whatsapp: d });
        jGo("site_about");
      } },
      skip: "site",
      wire() { $("jrWa").onkeydown = (e) => { if (e.key === "Enter") $("jrMain").click(); }; },
    };
  },
  site_about() {
    return {
      title: jt("about_t"), sub: jt("about_s"),
      body: `${jField("jrLegal", jt("about_name"), `maxlength="120" autocomplete="name" value="${esc(_jDraft.legal || F().legal_name || "")}" data-autofocus`)}
        <label class="jr-field" for="jrAddr"><span>${esc(jt("about_addr"))}</span>
          <textarea id="jrAddr" rows="3" maxlength="300" autocomplete="street-address" placeholder="${esc(jt("about_addr_ph"))}">${esc(_jDraft.addr || F().address || "")}</textarea></label>
        <p class="jr-note">${esc(jt("about_email", { email: (typeof state !== "undefined" && state.email) || "" }))}</p>`,
      primary: { label: jt("next"), run: async () => {
        _jDraft.legal = jVal("jrLegal"); _jDraft.addr = jVal("jrAddr");
        await jSave("site", { legal_name: _jDraft.legal, address: _jDraft.addr });
        jGo("site_delivery");
      } },
      skip: "site",
    };
  },
  site_delivery() {
    // Nothing is pre-picked. A new site carries a built-in ₹49 fee the seller
    // never chose, and pre-selecting it would charge their customers on a
    // guess. The answer given is applied exactly.
    const paid = _jDraft.paid;
    return {
      title: jt("delivery_t"),
      body: `<div class="jr-choices">
          ${jChoice("free", "gift", jt("delivery_free"), jt("delivery_free_s"), paid === false)}
          ${jChoice("paid", "truck", jt("delivery_paid"), jt("delivery_paid_s"), paid === true)}</div>
        <div id="jrFeeBox"${paid ? "" : " hidden"}>${jField("jrFee", jt("delivery_fee"),
          `inputmode="decimal" maxlength="6" value="${esc(_jDraft.fee || "")}" placeholder="49"`)}</div>`,
      primary: { label: jt("next"), disabled: paid == null, run: async () => {
        let f = 0;
        if (_jDraft.paid) {
          f = parseFloat(jVal("jrFee"));
          if (!(f > 0)) jErrorOf("fee_err");
          _jDraft.fee = f;
        }
        await jSave("site", { delivery_fee: f });
        jGo("site_preview");
      } },
      skip: "site",
      wire() {
        document.querySelectorAll("#jrBody [data-choice]").forEach((b) => b.onclick = () => {
          _jDraft.paid = b.dataset.choice === "paid";
          document.querySelectorAll("#jrBody [data-choice]").forEach((x) => {
            x.classList.toggle("on", x === b); x.setAttribute("aria-pressed", String(x === b));
          });
          $("jrFeeBox").hidden = !_jDraft.paid;
          $("jrMain").disabled = false;
          if (_jDraft.paid) $("jrFee").focus();
        });
      },
    };
  },
  site_preview() {
    const f = F();
    const src = f.handle ? `/s/${encodeURIComponent(f.handle)}?preview=${encodeURIComponent((typeof state !== "undefined" && state.token) || "")}` : "";
    return {
      title: jt("preview_t"), sub: jt("preview_s"),
      body: `${src ? `<div class="jr-frame"><iframe src="${esc(src)}" title="${esc(jt("preview_t"))}" loading="lazy"></iframe></div>` : ""}
        ${f.unlisted ? `<label class="jr-tick"><input type="checkbox" id="jrListAll" checked /> <span>${esc(jt("list_all", { n: f.unlisted }))}</span></label>` : ""}
        <button class="jr-link" type="button" id="jrFull">${esc(jt("full_builder"))}</button>`,
      primary: { label: jt("go_live"), run: async () => {
        if ($("jrListAll") && $("jrListAll").checked) await jSave("site", { list_all: true });
        await jSave("publish", {});
        await jAdvance();
      } },
      secondary: { label: jt("change_look"), run: async () => jGo("site_look") },
      skip: "site",
      wire() {
        $("jrFull").onclick = () => { closeJourney(); openModule("site"); };
      },
    };
  },

  /* ---------------------------------------------------------- payment */
  payment() {
    const f = F();
    const inr = (f.currency || "INR") === "INR";
    const needWa = !f.whatsapp;
    return {
      title: jt("pay_t"), sub: jt("pay_s"),
      body: `${jField("jrUpi", jt("upi"), `autocapitalize="none" autocomplete="off" spellcheck="false" maxlength="60" value="${esc(_jDraft.upi || f.upi_id || "")}" placeholder="${esc(jt("upi_ph"))}" data-autofocus`)}
        <details class="jr-help"><summary>${esc(jt("upi_where"))}</summary>
          <ul><li>${esc(jt("upi_gpay"))}</li><li>${esc(jt("upi_phonepe"))}</li><li>${esc(jt("upi_paytm"))}</li></ul></details>
        ${needWa ? jField("jrPayWa", jt("wa_t"), `type="tel" inputmode="numeric" maxlength="14" placeholder="98765 43210"`) : ""}
        <p class="jr-note">${sic(f.cod_enabled ? "check" : "close")}${esc(f.cod_enabled ? jt("cod_on") : jt("cod_off"))}</p>
        ${inr ? "" : `<div class="jr-warn">${esc(jt("not_inr"))}
          <label class="jr-tick"><input type="checkbox" id="jrInr" /> <span>${esc(jt("to_inr"))}</span></label></div>`}
        <button class="jr-link" type="button" id="jrRzp">${esc(jt("razorpay"))}</button>`,
      primary: { label: jt("save"), run: async () => {
        _jDraft.upi = jVal("jrUpi");
        if (needWa) {
          const d = jVal("jrPayWa").replace(/\D/g, "").replace(/^91(?=\d{10}$)/, "");
          if (d.length !== 10) jErrorOf("wa_err");
          await jSave("site", { whatsapp: d });
        }
        await jSave("payment", { upi_id: _jDraft.upi, rupees: !!($("jrInr") && $("jrInr").checked) });
        await jAdvance();
      } },
      skip: "payment",
      wire() {
        $("jrUpi").onkeydown = (e) => { if (e.key === "Enter") $("jrMain").click(); };
        $("jrRzp").onclick = async () => {
          closeJourney();
          await openModule("site");
          if (typeof goStep === "function") goStep("checkout");
        };
      },
    };
  },

  /* ---------------------------------------------------- Part 1 finish */
  part1_done() {
    const f = F();
    jAct("seen_part_done", { part: 1 }).catch(() => {});
    const more = `
      <h3 class="jr-h3">${esc(jt("more_parts"))}</h3>
      <ol class="jr-parts">
        <li><b>${esc(jt("more_p2"))}</b><span>${esc(jt("more_p2_s"))}</span></li>
        <li><b>${esc(jt("more_p3"))}</b><span>${esc(jt("more_p3_s"))}</span></li>
      </ol>`;
    const nextBtns = {
      primary: { label: jt("start_p2"), run: async () => { jGo(jPartEntry(2)); } },
      secondary: { label: jt("later"), run: async () => closeJourney() },
    };
    if (J.path === "connect") {
      const s = f.sales || {};
      return {
        title: jt("c_done_t"),
        body: `<div class="jr-stats">
            <div><b>${esc(fmt(s.orders || 0))}</b><span>${esc(jt("c_orders"))}</span></div>
            <div><b>${esc(fmt(s.customers || 0))}</b><span>${esc(jt("c_customers"))}</span></div></div>
          ${(s.top || []).length ? `<p class="jr-note"><b>${esc(jt("c_top"))}:</b> ${esc(s.top.join(", "))}</p>` : ""}
          <div class="jr-offer">${sic("bag")}<div><b>${esc(jt("c_want_shop"))}</b><span>${esc(jt("c_want_shop_s"))}</span></div>
            <button class="btn ghost sm" type="button" id="jrMakeShop">${esc(jt("c_make_shop"))}</button></div>
          ${more}`,
        ...nextBtns,
        wire() {
          $("jrMakeShop").onclick = () => jRun($("jrMakeShop"), async () => {
            await jAct("choose_path", { path: "create" });
            jGo(jPartEntry(1));
          });
        },
      };
    }
    if (!f.published) {
      return {
        title: jt("p1_notlive_t"), sub: jt("p1_notlive_s"),
        body: `<button class="btn primary sm" type="button" id="jrPutOnline">${esc(jt("put_online"))}</button>${more}`,
        ...nextBtns,
        wire() { $("jrPutOnline").onclick = () => jGo("site_look"); },
      };
    }
    const url = jPublicUrl();
    return {
      title: jt("p1_done_t"), sub: jt("p1_done_s"),
      body: `<div class="jr-live">${sic("check")}<a href="${esc(url)}" target="_blank" rel="noopener">${esc(url.replace(/^https?:\/\//, ""))}</a></div>
        <div class="jr-share">
          <a class="btn primary" href="https://wa.me/?text=${encodeURIComponent(jt("wa_share_text", { url }))}" target="_blank" rel="noopener">${sic("whatsapp")}${esc(jt("share_wa"))}</a>
          <button class="btn ghost" type="button" id="jrBio">${sic("instagram")}${esc(jt("copy_bio"))}</button>
        </div>
        <p class="jr-note">${esc(jt("bio_how"))}</p>
        ${more}`,
      ...nextBtns,
      wire() { $("jrBio").onclick = () => jCopy(url); },
    };
  },

  /* ----------------------------------------------------- connect path */
  connect_pick() {
    const icons = { shopify: "bag", woocommerce: "grid", wix: "globe", amazon: "package" };
    const cat = _jDraft.catalog || [];
    return {
      title: jt("connect_t"),
      body: `<div class="jr-choices two">
          ${cat.map((c) => jChoice(c.id, icons[c.id] || "globe", c.label, "", false)).join("")}
          ${jChoice("_file", "arrow-up-right", jt("connect_other"), jt("connect_other_s"))}</div>
        <button class="jr-link" type="button" id="jrMakeInstead">${esc(jt("make_instead"))}</button>`,
      skip: "connect",
      wire() {
        if (!_jDraft.catalog) {
          api("/api/commerce/status").then((d) => { _jDraft.catalog = d.connectors || []; if (_jScreen === "connect_pick") jGo("connect_pick", true, true); })
            .catch((e) => jErr(e.message));
        }
        document.querySelectorAll("#jrBody [data-choice]").forEach((b) => b.onclick = () => {
          if (b.dataset.choice === "_file") return jGo("connect_upload");
          _jDraft.connector = b.dataset.choice;
          jGo("connect_form");
        });
        $("jrMakeInstead").onclick = () => jRun($("jrMakeInstead"), async () => {
          await jAct("choose_path", { path: "create" });
          jGo(jPartEntry(1));
        });
      },
    };
  },
  connect_form() {
    const c = (_jDraft.catalog || []).find((x) => x.id === _jDraft.connector);
    if (!c) return SCREENS.connect_pick();
    // The platform's own help, split into numbered steps.
    const steps = String(c.help || "").split(/\s*→\s*|,\s*then\s+|\.\s+/).map((x) => x.trim()).filter(Boolean);
    return {
      title: c.label,
      body: `<details class="jr-help" open><summary>${esc(jt("connect_how"))}</summary>
          <ol>${steps.map((s) => `<li>${esc(s)}</li>`).join("")}</ol></details>
        ${(c.fields || []).map((fd, i) => jField(`jrC_${fd.key}`, fd.label,
          `${fd.secret ? 'type="password"' : ""} autocomplete="off" spellcheck="false" placeholder="${esc(fd.placeholder || "")}"${i === 0 ? " data-autofocus" : ""}`)).join("")}`,
      primary: { label: jt("connect_btn"), run: async () => {
        const creds = {};
        for (const fd of c.fields || []) creds[fd.key] = jVal(`jrC_${fd.key}`);
        $("jrMain").textContent = jt("connecting");
        await api("/api/commerce/connect", { method: "POST", json: { connector: c.id, credentials: creds } });
        $("jrMain").textContent = jt("pulling");
        await api("/api/commerce/pull", { method: "POST", json: { connector: c.id, days: 90 } });
        await jAct("sync");
        await jAdvance();
      } },
      skip: "connect",
    };
  },
  connect_upload() {
    return {
      title: jt("upload_t"), sub: jt("upload_s"),
      body: "",
      primary: { label: jt("choose_file"), run: async () => {
        // The existing upload and column check. When it finishes, the
        // journey opens again where it left off.
        _afterUpload = () => openJourney();
        closeJourney();
        startUpload("sales");
      } },
      skip: "connect",
    };
  },
  catalogue() {
    const n = F().unmatched || 0;
    if (!n) {
      return {
        title: jt("catalogue_none_t"), sub: jt("catalogue_none_s"),
        primary: { label: jt("products_t"), run: async () => jGo("products") },
        skip: "catalogue",
      };
    }
    return {
      title: jt("catalogue_t", { n }), sub: jt("catalogue_s"),
      primary: { label: jt("catalogue_add"), run: async () => { await jSave("import", {}); await jAdvance(); } },
      skip: "catalogue",
    };
  },

  /* ------------------------------------------------------------ Part 2 */
  p2_intro() {
    return {
      title: jt("p2_intro_t"),
      body: jSteps3(jt("p2_i1"), jt("p2_i2"), jt("p2_i3"), ["camera", "spark", "check"]),
      primary: { label: jt("start"), run: async () => { await jAct("open_part", { part: 2 }); jGo(jPartEntry(2), true); } },
    };
  },
  brand() {
    return {
      title: jt("brand_t"),
      body: `<label class="jr-field" for="jrAbout"><span>${esc(jt("brand_make"))}</span>
          <textarea id="jrAbout" rows="3" maxlength="400" placeholder="${esc(jt("brand_make_ph"))}" data-autofocus>${esc(_jDraft.about || "")}</textarea></label>
        ${jField("jrAud", jt("brand_who"), `maxlength="200" value="${esc(_jDraft.aud || "")}" placeholder="${esc(jt("brand_who_ph"))}"`)}`,
      primary: { label: jt("next"), run: async () => {
        _jDraft.about = jVal("jrAbout"); _jDraft.aud = jVal("jrAud");
        if (_jDraft.about.length < 5) jErrorOf("brand_err");
        const patch = { about: _jDraft.about };
        if (_jDraft.aud) patch.audience = _jDraft.aud;
        await api("/api/studio/brand", { method: "POST", json: { patch } });
        await jAct("sync");
        await jAdvance();
      } },
      skip: "brand",
    };
  },
  style() {
    const n = F().style_count || 0;
    const got = _jDraft.style || [];
    return {
      title: jt("style_t"), sub: jt("style_s"),
      body: `<div class="jr-count"><b>${esc(jt("style_count", { n: Math.min(n, 99) }))}</b>
          <span class="jr-bar"><i style="width:${Math.min(100, n / 3 * 100)}%"></i></span></div>
        ${got.length ? `<div class="jr-grid">${got.map((u) => jThumb(u)).join("")}</div>` : ""}
        <button class="btn ${n >= 3 ? "ghost" : "primary"} jr-add" type="button" id="jrStyleAdd">${sic("image")}${esc(jt("add_photos"))}</button>
        <div class="jr-up" id="jrStyleUp" hidden></div>`,
      primary: { label: jt("next"), disabled: n < 3, run: jAdvance },
      skip: "style",
      wire() {
        $("jrStyleAdd").onclick = async () => {
          const files = await jPickPhotos(true);
          if (!files.length) return;
          const up = $("jrStyleUp"); up.hidden = false;
          let i = 0, failed = 0;
          for (const file of files.slice(0, 8)) {
            i++;
            up.textContent = `${jt("uploading")} ${i} / ${Math.min(files.length, 8)}`;
            try {
              const url = await jUpload(file);
              await api("/api/studio/design-language/add", { method: "POST", json: { url } });
              (_jDraft.style = _jDraft.style || []).push(url);
            } catch (e) { failed++; }
          }
          await jAct("sync");
          jGo("style", true, true);
          if (failed) jErr(jt("upload_failed"));
        };
      },
    };
  },
  photos() {
    const prods = (F().products || []);
    if (!prods.length) {
      return { title: jt("photos_t"), sub: jt("photos_none"),
               primary: { label: jt("products_t"), run: async () => jGo("products") }, skip: "photos" };
    }
    const rows = prods.slice(0, 20).map((p) => `
      <li class="jr-prod">${jThumb(p.image_url)}<span><b>${esc(p.name)}</b></span>
        ${p.image_url ? `<span class="jr-ok" aria-label="Has a photo">${sic("check")}</span>`
          : `<button class="btn ghost sm" type="button" data-pphoto="${esc(p.id)}">${sic("camera")}${esc(jt("add_photo"))}</button>`}</li>`).join("");
    return {
      title: jt("photos_t"), sub: jt("photos_s"),
      body: `<ul class="jr-prods">${rows}</ul><div class="jr-up" id="jrPhUp" hidden></div>`,
      primary: { label: jt("next"), disabled: !jDone("photos"), run: jAdvance },
      skip: "photos",
      wire() {
        document.querySelectorAll("[data-pphoto]").forEach((b) => b.onclick = async () => {
          const files = await jPickPhotos(false);
          if (!files.length) return;
          const up = $("jrPhUp"); up.hidden = false; up.textContent = jt("uploading");
          try {
            const url = await jUpload(files[0]);
            await jSave("photo", { product_id: b.dataset.pphoto, url });
            jGo("photos", true, true);
          } catch (e) { up.textContent = `${jt("upload_failed")} ${e.message || ""}`; }
        });
      },
    };
  },
  instagram() {
    const done = jDone("instagram");
    return {
      title: jt("ig_t"), sub: jt("ig_s"),
      body: done ? `<p class="jr-live">${sic("check")}${esc(jt("ig_done"))}</p>` : `
        <div class="jr-warn">${sic("instagram")}<span>${esc(jt("ig_need"))}</span></div>
        <details class="jr-help"><summary>${esc(jt("ig_how"))}</summary>
          <ol><li>${esc(jt("ig_how_1"))}</li><li>${esc(jt("ig_how_2"))}</li><li>${esc(jt("ig_how_3"))}</li></ol></details>`,
      primary: done ? { label: jt("next"), run: jAdvance } : { label: jt("ig_btn"), run: async () => {
        const r = await api("/api/instagram/oauth/start");
        const popup = window.open(r.login_url, "ig_oauth", "width=560,height=720");
        if (!popup) throw new Error("Allow pop-ups for this site, then try again.");
        // When the seller comes back from Instagram, check again.
        window.addEventListener("focus", jOnFocus);
        const iv = setInterval(async () => {
          if (!popup.closed) return;
          clearInterval(iv);
          await jOnFocus();
        }, 800);
      } },
      skip: "instagram",
    };
  },
  part2_done() {
    jAct("seen_part_done", { part: 2 }).catch(() => {});
    return {
      title: jt("p2_done_t"), sub: jt("p2_done_s"),
      body: `<p class="jr-note">${sic("spark")}${esc(jt("p2_ai"))}</p>`,
      primary: { label: jt("next_p3"), run: async () => jGo(jPartEntry(3)) },
      secondary: { label: jt("plan_week"), run: async () => { closeJourney(); openModule("social"); } },
    };
  },

  /* ------------------------------------------------------------ Part 3 */
  p3_intro() {
    return {
      title: jt("p3_intro_t"),
      body: jSteps3(jt("p3_i1"), jt("p3_i2"), jt("p3_i3"), ["truck", "chart", "bell"]),
      primary: { label: jt("start"), run: async () => { await jAct("open_part", { part: 3 }); jGo(jPartEntry(3), true); } },
    };
  },
  supplier() {
    const s = _jDraft.sup || { name: (F().suppliers || [])[0] || "", phone: "", days: 7 };
    return {
      title: jt("sup_t"),
      body: `${jField("jrSupName", jt("sup_name"), `maxlength="120" value="${esc(s.name)}" placeholder="${esc(jt("sup_name_ph"))}" data-autofocus`)}
        ${jField("jrSupPhone", jt("sup_phone"), `type="tel" inputmode="numeric" maxlength="16" value="${esc(s.phone)}"`)}
        <label class="jr-field" for="jrSupDays"><span>${esc(jt("sup_days"))}</span>
          <span class="jr-step">
            <button type="button" class="jr-icon" data-days="-1" aria-label="Less">${sic("minus")}</button>
            <input id="jrSupDays" type="number" inputmode="numeric" min="1" max="120" value="${esc(s.days)}" />
            <button type="button" class="jr-icon" data-days="1" aria-label="More">${sic("plus")}</button>
          </span></label>`,
      primary: { label: jt("next"), run: async () => {
        const days = parseInt(jVal("jrSupDays"), 10);
        _jDraft.sup = { name: jVal("jrSupName"), phone: jVal("jrSupPhone"), days };
        if (_jDraft.sup.name.length < 2) jErrorOf("sup_err");
        if (!(days >= 1 && days <= 120)) jErrorOf("days_err");
        jGo("stock");
      } },
      skip: ["suppliers", "stock"],
      wire() {
        document.querySelectorAll("[data-days]").forEach((b) => b.onclick = () => {
          const i = $("jrSupDays");
          i.value = Math.max(1, Math.min(120, (parseInt(i.value, 10) || 0) + parseInt(b.dataset.days, 10)));
        });
      },
    };
  },
  stock() {
    if (!_jDraft.sup) return SCREENS.supplier();
    const prods = (F().products || []).filter((p) => !p.has_variants);
    const q = (_jDraft.q || "").toLowerCase();
    const shown = (q ? prods.filter((p) => String(p.name).toLowerCase().includes(q)) : prods).slice(0, 20);
    const counts = _jDraft.counts || {};
    const rows = shown.map((p) => `
      <li class="jr-prod">${jThumb(p.image_url)}<span><b>${esc(p.name)}</b></span>
        <input class="jr-num" type="number" inputmode="numeric" min="0" max="100000" aria-label="${esc(p.name)}"
          data-count="${esc(p.id)}" value="${esc(counts[p.id] != null ? counts[p.id] : (p.stock || ""))}" placeholder="0" /></li>`).join("");
    return {
      title: jt("stock_t"), sub: jt("stock_s"),
      body: `${prods.length > 20 ? `${jField("jrStockQ", jt("search"), `type="search" value="${esc(_jDraft.q || "")}"`)}<p class="jr-note">${esc(jt("stock_more"))}</p>` : ""}
        ${prods.length ? `<ul class="jr-prods">${rows}</ul>` : `<p class="jr-note">${esc(jt("photos_none"))}</p>`}`,
      primary: { label: jt("save"), disabled: !prods.length, run: async () => {
        const out = { ...(_jDraft.counts || {}) };
        document.querySelectorAll("[data-count]").forEach((i) => { if (i.value !== "") out[i.dataset.count] = i.value; });
        await jSave("stock", { supplier: _jDraft.sup, counts: out });
        await jAdvance();
      } },
      skip: ["suppliers", "stock"],
      wire() {
        document.querySelectorAll("[data-count]").forEach((i) => i.oninput = () => {
          (_jDraft.counts = _jDraft.counts || {})[i.dataset.count] = i.value;
        });
        const qi = $("jrStockQ");
        if (qi) qi.oninput = () => { _jDraft.q = qi.value; jGo("stock", true, true); requestAnimationFrame(() => { const x = $("jrStockQ"); if (x) { x.focus(); x.setSelectionRange(x.value.length, x.value.length); } }); };
      },
    };
  },
  part3_done() {
    jAct("seen_part_done", { part: 3 }).catch(() => {});
    const d = (_jDraft.sup && _jDraft.sup.days) || 7;
    const name = ((F().products || [])[0] || {}).name || "Kurta";
    // Supply's own rule: reorder when stock lasts less than delivery days + 20%.
    const base = 2 * d, point = Math.ceil(base * 1.2);
    return {
      title: jt("p3_done_t"),
      body: `<div class="jr-example"><span class="jr-tag">${esc(jt("p3_example"))}</span>
          <p>${esc(jt("p3_ex_1", { name }))}</p><p>${esc(jt("p3_ex_2", { d }))}</p>
          <p><b>${esc(jt("p3_ex_3", { n: point }))}</b></p>
          <small>${esc(jt("p3_ex_why", { d, base }))}</small></div>`,
      primary: { label: jt("done"), run: async () => jGo(jWhereNow()) },
    };
  },

  all_done() {
    const left = J.skipped_left || [];
    if (left.length) {
      return {
        title: jt("left_t"), sub: jt("left_s"),
        body: `<div class="jr-choices">${left.map((id) =>
          jChoice(id, "clock", jt("step_" + id), "")).join("")}</div>`,
        primary: { label: jt("finish_later"), run: async () => closeJourney() },
        wire() {
          document.querySelectorAll("#jrBody [data-choice]").forEach((b) =>
            b.onclick = () => jGo(STEP_SCREEN[b.dataset.choice]));
        },
      };
    }
    return {
      title: jt("all_done_t"), sub: jt("all_done_s"),
      body: jPublicUrl() ? `<div class="jr-live">${sic("check")}<a href="${esc(jPublicUrl())}" target="_blank" rel="noopener">${esc(jPublicUrl().replace(/^https?:\/\//, ""))}</a></div>` : "",
      primary: { label: jt("go_home"), run: async () => closeJourney() },
    };
  },
};

async function jOnFocus() {
  window.removeEventListener("focus", jOnFocus);
  if (!document.getElementById("jrBack")) return;
  try { await jAct("sync"); if (_jScreen === "instagram") jGo("instagram", true); } catch (e) { /* keep screen */ }
}

/* ========================================================= HOME CARD ===== */
/* Replaces the old setup card on home. It never nags: it can be hidden, and
   "Setup guide" in the header always brings the journey back. */
function journeyCardHtml(ob) {
  if (!ob) return "";
  const L = ob.lang === "hi" ? "hi" : "en";
  const T = (k, v) => { let s = (JT[L] && JT[L][k]) || JT.en[k] || k; if (v) for (const [a, b] of Object.entries(v)) s = s.split(`{${a}}`).join(String(b)); return s; };
  if (ob.dismissed) return "";
  // Skipped steps stay in view until they are really done: finishing the
  // parts by skipping is not the same as a shop that is set up.
  if (ob.finished && !(ob.skipped_left || []).length) return "";
  if (!ob.has_record || !ob.path) {
    return `<section class="jr-card-home" id="jrHome">
      <div class="jr-home-top"><div>
        <div class="setup-eyebrow">${esc(T("setup_guide"))}</div>
        <h3>${esc(T("card_title"))}</h3><p>${esc(T("card_sub"))}</p></div></div>
      <div class="jr-home-acts">
        <button class="btn primary" data-jhome="start">${esc(T("start"))}</button>
        <button class="btn ghost sm" data-jhome="hide">${esc(T("card_hide"))}</button></div>
    </section>`;
  }
  if (!ob.active) {
    const n = (ob.skipped_left || []).length;
    if (!n) return "";
    return `<section class="jr-card-home slim" id="jrHome">
      <span>${sic("clock")}${esc(T("card_skipped", { n, s: n === 1 ? "" : "s" }))}</span>
      <button class="btn ghost sm" data-jhome="skipped">${esc(T("card_finish"))}</button>
    </section>`;
  }
  const next = ob.next || {};
  const parts = (ob.parts || []).map((p) => {
    const done = p.steps.filter((s) => s.done).length;
    const state = p.finished ? "done" : p.unlocked ? "open" : "locked";
    const name = p.n === 1 ? (ob.path === "connect" ? T("part1_connect") : T("part1_create")) : p.n === 2 ? T("part2") : T("part3");
    return `<button class="jr-home-part ${state}" data-jpart="${p.n}"${p.unlocked ? "" : " disabled"}>
        <span class="jr-home-n">${p.finished ? sic("check") : p.n}</span>
        <span><b>${esc(name)}</b><small>${done}/${p.steps.length}</small></span></button>`;
  }).join("");
  const pct = Math.round((ob.done_count || 0) / Math.max(1, ob.total || 1) * 100);
  return `<section class="jr-card-home" id="jrHome">
    <div class="jr-home-top"><div>
      <div class="setup-eyebrow">${esc(T("part_of", { n: next.part || 1 }))}</div>
      <h3>${esc(T("card_next", { step: T("step_" + (next.step || "shop")) }))}</h3></div>
      <div class="setup-ring" style="--pct:${pct}"><span>${ob.done_count || 0}/${ob.total || 0}</span></div></div>
    <div class="jr-home-parts">${parts}</div>
    <div class="jr-home-acts">
      <button class="btn primary" data-jhome="continue">${esc(T("card_continue"))}</button>
      <button class="btn ghost sm" data-jhome="hide">${esc(T("card_hide"))}</button></div>
  </section>`;
}

function wireJourneyCard(ob) {
  document.querySelectorAll("[data-jhome]").forEach((b) => b.onclick = async () => {
    const a = b.dataset.jhome;
    if (a === "hide") {
      try { await api("/api/onboarding", { method: "POST", json: { action: "dismiss" } }); } catch (e) { toast(e.message); return; }
      const el = document.getElementById("jrHome"); if (el) el.remove();
      toast((ob && ob.lang === "hi") ? "छिपा दिया। ऊपर 'सेटअप गाइड' से वापस खोलें।" : "Hidden. Open it again from Setup guide at the top.");
      return;
    }
    if (a === "skipped") { openJourney({ step: (ob.skipped_left || [])[0] }); return; }
    openJourney();
  });
  document.querySelectorAll("[data-jpart]").forEach((b) => b.onclick = () => openJourney({ part: parseInt(b.dataset.jpart, 10) }));
}

/* Called once per home paint: a brand-new account sees the welcome by itself,
   exactly once; and a step finished inside a module closes its task. */
let _jAutoShown = false;
function journeyAfterHome(ob) {
  if (!ob) return;
  if (ob.needs_sync) {
    api("/api/onboarding", { method: "POST", json: { action: "sync" } })
      .then((r) => { if (r.tasks && typeof refreshTaskList === "function") refreshTaskList(r.tasks); })
      .catch(() => {});
  }
  if (ob.new_account && !_jAutoShown && !document.getElementById("jrBack")) {
    _jAutoShown = true;
    openJourney();
  }
}
