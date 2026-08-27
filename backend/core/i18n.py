"""
Plain-language insights, in 4 languages.

WHY THIS EXISTS
Insights used to be written as English f-strings inside analytics.py, in
consultant-speak ("concentration risk", "compounds across future orders").
A shop owner shouldn't need a business degree to read their own data.

So insight functions now emit a KEY + PARAMS instead of a sentence:
    {"type": "negative", "key": "revenue_down", "params": {"pct": "37.7%"}}
and this module turns that into text + action in the reader's language.

Adding a language = adding one column below. Nothing else changes.

WRITING RULES for every string here:
  - short sentences, everyday words a 10-year-old knows
  - say "money you made" not "revenue"; "customers" not "segments"
  - the ACTION must be one concrete thing to DO tomorrow, not a concept
"""

LANGUAGES = {
    "en": "English",
    "hi": "हिंदी",
    "ta": "தமிழ்",
    "kn": "ಕನ್ನಡ",
}
DEFAULT_LANG = "en"

# key -> {lang -> (text_template, action_template)}
T: dict[str, dict[str, tuple[str, str]]] = {
    "forecast_up": {
        "en": ("Next 30 days are tracking to ≈ ₹{value} — {pct} above your last 30 days.",
               "Lock supplier orders for {top_product} (your #1 seller) this week and add one extra staff shift on {peak_day}s — don't let stock-outs eat this growth."),
    },
    "forecast_down": {
        "en": ("Next 30 days are tracking to ≈ ₹{value} — {pct} below your last 30 days.",
               "Act this week: send your win-back list a comeback offer, and run a {slow_day} combo around {top_product} to lift your weakest day before the dip lands."),
    },

    # ---------------- ANALYTICS ----------------
    "revenue_up": {
        "en": ("Good news — you made {pct} more money last month than the month before.",
               "Think about what you did differently last month, and do it again this month."),
        "hi": ("अच्छी खबर — पिछले महीने आपने उससे पहले वाले महीने से {pct} ज़्यादा कमाई की।",
               "सोचिए पिछले महीने आपने क्या अलग किया था, और इस महीने वही दोबारा कीजिए।"),
        "ta": ("நல்ல செய்தி — முந்தைய மாதத்தை விட கடந்த மாதம் {pct} அதிக பணம் சம்பாதித்தீர்கள்.",
               "கடந்த மாதம் நீங்கள் என்ன வித்தியாசமாக செய்தீர்கள் என்று யோசியுங்கள், அதையே இந்த மாதமும் செய்யுங்கள்."),
        "kn": ("ಒಳ್ಳೆಯ ಸುದ್ದಿ — ಹಿಂದಿನ ತಿಂಗಳಿಗಿಂತ ಕಳೆದ ತಿಂಗಳು ನೀವು {pct} ಹೆಚ್ಚು ಹಣ ಗಳಿಸಿದ್ದೀರಿ.",
               "ಕಳೆದ ತಿಂಗಳು ನೀವು ಏನು ಬೇರೆಯಾಗಿ ಮಾಡಿದಿರಿ ಎಂದು ಯೋಚಿಸಿ, ಅದನ್ನೇ ಈ ತಿಂಗಳೂ ಮಾಡಿ."),
    },
    "revenue_down": {
        "en": ("Careful — you made {pct} less money last month than the month before.",
               "Check which items sold less last month. Usually only one or two items cause the drop."),
        "hi": ("ध्यान दीजिए — पिछले महीने आपकी कमाई उससे पहले वाले महीने से {pct} कम रही।",
               "देखिए पिछले महीने कौन सी चीज़ें कम बिकीं। आमतौर पर सिर्फ़ एक-दो चीज़ें ही गिरावट की वजह होती हैं।"),
        "ta": ("கவனம் — முந்தைய மாதத்தை விட கடந்த மாதம் {pct} குறைவாக சம்பாதித்தீர்கள்.",
               "கடந்த மாதம் எந்தப் பொருட்கள் குறைவாக விற்றன என்று பாருங்கள். பொதுவாக ஒன்று அல்லது இரண்டு பொருட்கள்தான் காரணம்."),
        "kn": ("ಎಚ್ಚರ — ಹಿಂದಿನ ತಿಂಗಳಿಗಿಂತ ಕಳೆದ ತಿಂಗಳು ನೀವು {pct} ಕಡಿಮೆ ಹಣ ಗಳಿಸಿದ್ದೀರಿ.",
               "ಕಳೆದ ತಿಂಗಳು ಯಾವ ವಸ್ತುಗಳು ಕಡಿಮೆ ಮಾರಾಟವಾದವು ಎಂದು ನೋಡಿ. ಸಾಮಾನ್ಯವಾಗಿ ಒಂದು-ಎರಡು ವಸ್ತುಗಳೇ ಕಾರಣ."),
    },
    "best_month": {
        "en": ("Your best month was {month}. You made {value} that month.",
               "Remember what was going on in {month} — the offers, the staff, the weather. Try to make that happen again."),
        "hi": ("आपका सबसे अच्छा महीना {month} था। उस महीने आपने {value} कमाए।",
               "याद कीजिए {month} में क्या चल रहा था — ऑफ़र, स्टाफ़, मौसम। वैसा ही दोबारा करने की कोशिश कीजिए।"),
        "ta": ("உங்கள் சிறந்த மாதம் {month}. அந்த மாதம் நீங்கள் {value} சம்பாதித்தீர்கள்.",
               "{month} மாதத்தில் என்ன நடந்தது என்று நினைவில் கொள்ளுங்கள் — சலுகைகள், ஊழியர்கள், வானிலை. அதையே மீண்டும் செய்ய முயற்சியுங்கள்."),
        "kn": ("ನಿಮ್ಮ ಅತ್ಯುತ್ತಮ ತಿಂಗಳು {month}. ಆ ತಿಂಗಳು ನೀವು {value} ಗಳಿಸಿದ್ದೀರಿ.",
               "{month} ತಿಂಗಳಲ್ಲಿ ಏನು ನಡೆಯುತ್ತಿತ್ತು ಎಂದು ನೆನಪಿಸಿಕೊಳ್ಳಿ — ಕೊಡುಗೆಗಳು, ಸಿಬ್ಬಂದಿ, ಹವಾಮಾನ. ಅದನ್ನೇ ಮತ್ತೆ ಮಾಡಲು ಪ್ರಯತ್ನಿಸಿ."),
    },
    "worst_month": {
        "en": ("Your weakest month was {month}. You made only {value} that month.",
               "If {month} is slow every year, plan a special offer for it now — don't wait for it to happen again."),
        "hi": ("आपका सबसे कमज़ोर महीना {month} था। उस महीने आपने सिर्फ़ {value} कमाए।",
               "अगर {month} हर साल धीमा रहता है, तो अभी से उसके लिए कोई ऑफ़र सोच लीजिए — दोबारा होने का इंतज़ार मत कीजिए।"),
        "ta": ("உங்கள் மோசமான மாதம் {month}. அந்த மாதம் நீங்கள் {value} மட்டுமே சம்பாதித்தீர்கள்.",
               "{month} ஒவ்வொரு வருடமும் மந்தமாக இருந்தால், இப்போதே ஒரு சிறப்பு சலுகையைத் திட்டமிடுங்கள் — மீண்டும் நடக்கும் வரை காத்திருக்க வேண்டாம்."),
        "kn": ("ನಿಮ್ಮ ದುರ್ಬಲ ತಿಂಗಳು {month}. ಆ ತಿಂಗಳು ನೀವು ಕೇವಲ {value} ಗಳಿಸಿದ್ದೀರಿ.",
               "{month} ಪ್ರತಿ ವರ್ಷ ನಿಧಾನವಾಗಿದ್ದರೆ, ಈಗಲೇ ವಿಶೇಷ ಕೊಡುಗೆ ಯೋಜಿಸಿ — ಮತ್ತೆ ಆಗುವವರೆಗೆ ಕಾಯಬೇಡಿ."),
    },
    "category_concentration_high": {
        "en": ("Most of your money — {pct} — comes from just one thing: {name}.",
               "Never let {name} run out of stock. Also try to grow your second-best item, so you don't depend on only one."),
        "hi": ("आपकी ज़्यादातर कमाई — {pct} — सिर्फ़ एक चीज़ से आती है: {name}।",
               "{name} कभी ख़त्म नहीं होना चाहिए। साथ ही अपनी दूसरी सबसे अच्छी चीज़ को भी बढ़ाइए, ताकि सिर्फ़ एक पर निर्भर न रहें।"),
        "ta": ("உங்கள் பணத்தில் பெரும்பகுதி — {pct} — ஒரே ஒரு பொருளிலிருந்து வருகிறது: {name}.",
               "{name} ஒருபோதும் தீர்ந்துபோகக் கூடாது. உங்கள் இரண்டாவது சிறந்த பொருளையும் வளர்க்க முயற்சியுங்கள்."),
        "kn": ("ನಿಮ್ಮ ಹೆಚ್ಚಿನ ಹಣ — {pct} — ಕೇವಲ ಒಂದೇ ವಸ್ತುವಿನಿಂದ ಬರುತ್ತದೆ: {name}.",
               "{name} ಎಂದಿಗೂ ಖಾಲಿಯಾಗಬಾರದು. ನಿಮ್ಮ ಎರಡನೇ ಅತ್ಯುತ್ತಮ ವಸ್ತುವನ್ನೂ ಬೆಳೆಸಲು ಪ್ರಯತ್ನಿಸಿ."),
    },
    "category_concentration_ok": {
        "en": ("{name} brings the most money — {pct} of your total.",
               "Sell {name} together with your slow items, so the slow ones also start selling."),
        "hi": ("{name} से सबसे ज़्यादा कमाई होती है — आपकी कुल कमाई का {pct}।",
               "{name} को अपनी धीमी बिकने वाली चीज़ों के साथ मिलाकर बेचिए, जिससे वे भी बिकने लगें।"),
        "ta": ("{name} அதிக பணம் கொண்டு வருகிறது — உங்கள் மொத்தத்தில் {pct}.",
               "{name}-ஐ மெதுவாக விற்கும் பொருட்களுடன் சேர்த்து விற்கவும், அவையும் விற்கத் தொடங்கும்."),
        "kn": ("{name} ಹೆಚ್ಚು ಹಣ ತರುತ್ತದೆ — ನಿಮ್ಮ ಒಟ್ಟು ಮೊತ್ತದ {pct}.",
               "{name} ಅನ್ನು ನಿಧಾನವಾಗಿ ಮಾರಾಟವಾಗುವ ವಸ್ತುಗಳೊಂದಿಗೆ ಸೇರಿಸಿ ಮಾರಿ, ಅವೂ ಮಾರಾಟವಾಗಲು ಶುರುವಾಗುತ್ತವೆ."),
    },
    "weekday_gap": {
        "en": ("{best} is your busiest day. {worst} is {pct} quieter.",
               "Make a special offer only for {worst}. And keep more staff and stock ready on {best}."),
        "hi": ("{best} आपका सबसे व्यस्त दिन है। {worst} को {pct} कम काम होता है।",
               "सिर्फ़ {worst} के लिए कोई ख़ास ऑफ़र निकालिए। और {best} को ज़्यादा स्टाफ़ और सामान तैयार रखिए।"),
        "ta": ("{best} உங்கள் பரபரப்பான நாள். {worst} அன்று {pct} அமைதியாக இருக்கும்.",
               "{worst} அன்று மட்டும் ஒரு சிறப்பு சலுகை கொடுங்கள். {best} அன்று அதிக ஊழியர்களையும் பொருட்களையும் தயாராக வைத்திருங்கள்."),
        "kn": ("{best} ನಿಮ್ಮ ಅತ್ಯಂತ ಬ್ಯುಸಿ ದಿನ. {worst} ದಿನ {pct} ಶಾಂತವಾಗಿರುತ್ತದೆ.",
               "{worst} ದಿನಕ್ಕೆ ಮಾತ್ರ ವಿಶೇಷ ಕೊಡುಗೆ ನೀಡಿ. {best} ದಿನ ಹೆಚ್ಚು ಸಿಬ್ಬಂದಿ ಮತ್ತು ಸಾಮಗ್ರಿ ಸಿದ್ಧವಾಗಿಡಿ."),
    },
    "aov": {
        "en": ("On average, each customer spends {value} per visit. If each spent just 10% more, you would have made {uplift} extra.",
               "Teach your staff to ask one simple question: \"Would you like something with that?\" This costs nothing and needs no new customers."),
        "hi": ("औसतन हर ग्राहक एक बार में {value} खर्च करता है। अगर हर कोई सिर्फ़ 10% ज़्यादा खर्च करता, तो आपको {uplift} अतिरिक्त मिलते।",
               "अपने स्टाफ़ को एक आसान सवाल पूछना सिखाइए: \"इसके साथ कुछ और लेंगे?\" इसमें कोई खर्च नहीं और नए ग्राहक भी नहीं चाहिए।"),
        "ta": ("சராசரியாக ஒவ்வொரு வாடிக்கையாளரும் ஒரு வருகைக்கு {value} செலவிடுகிறார். ஒவ்வொருவரும் 10% அதிகம் செலவிட்டால், உங்களுக்கு {uplift} கூடுதலாக கிடைத்திருக்கும்.",
               "உங்கள் ஊழியர்களுக்கு ஒரு எளிய கேள்வியைக் கேட்கக் கற்றுக் கொடுங்கள்: \"இதனுடன் ஏதாவது வேண்டுமா?\" இதற்கு செலவே இல்லை."),
        "kn": ("ಸರಾಸರಿ ಪ್ರತಿ ಗ್ರಾಹಕ ಒಂದು ಭೇಟಿಗೆ {value} ಖರ್ಚು ಮಾಡುತ್ತಾರೆ. ಪ್ರತಿಯೊಬ್ಬರೂ 10% ಹೆಚ್ಚು ಖರ್ಚು ಮಾಡಿದ್ದರೆ, ನಿಮಗೆ {uplift} ಹೆಚ್ಚುವರಿ ಸಿಗುತ್ತಿತ್ತು.",
               "ನಿಮ್ಮ ಸಿಬ್ಬಂದಿಗೆ ಒಂದು ಸರಳ ಪ್ರಶ್ನೆ ಕೇಳಲು ಕಲಿಸಿ: \"ಇದರ ಜೊತೆ ಏನಾದರೂ ಬೇಕೆ?\" ಇದಕ್ಕೆ ಖರ್ಚಿಲ್ಲ."),
    },

    # ---------------- SUBCATEGORY OVERVIEW ----------------
    "subcat_leader_high": {
        "en": ("{name} is your star — it brings {pct} of all your money.",
               "You depend a lot on {name}. Keep its quality high and never run out. One bad month here hurts everything."),
        "hi": ("{name} आपका सितारा है — इससे आपकी कुल कमाई का {pct} आता है।",
               "आप {name} पर बहुत निर्भर हैं। इसकी क्वालिटी अच्छी रखिए और कभी ख़त्म मत होने दीजिए। यहाँ एक बुरा महीना सब कुछ बिगाड़ देगा।"),
        "ta": ("{name} உங்கள் நட்சத்திரம் — உங்கள் மொத்தப் பணத்தில் {pct} இதிலிருந்தே வருகிறது.",
               "நீங்கள் {name}-ஐ நம்பியே இருக்கிறீர்கள். அதன் தரத்தை உயர்வாக வைத்திருங்கள், ஒருபோதும் தீர்ந்துபோக விடாதீர்கள்."),
        "kn": ("{name} ನಿಮ್ಮ ತಾರೆ — ನಿಮ್ಮ ಒಟ್ಟು ಹಣದ {pct} ಇದರಿಂದಲೇ ಬರುತ್ತದೆ.",
               "ನೀವು {name} ಮೇಲೆ ತುಂಬಾ ಅವಲಂಬಿತರಾಗಿದ್ದೀರಿ. ಅದರ ಗುಣಮಟ್ಟ ಕಾಪಾಡಿ, ಎಂದಿಗೂ ಖಾಲಿಯಾಗಲು ಬಿಡಬೇಡಿ."),
    },
    "subcat_leader_ok": {
        "en": ("{name} sells the most — {pct} of your money comes from it.",
               "Show {name} on your board or menu first. Put it next to slow items so those sell too."),
        "hi": ("{name} सबसे ज़्यादा बिकता है — आपकी कमाई का {pct} इससे आता है।",
               "{name} को अपने बोर्ड या मेन्यू में सबसे पहले दिखाइए। धीमी चीज़ों के पास रखिए ताकि वे भी बिकें।"),
        "ta": ("{name} அதிகம் விற்கிறது — உங்கள் பணத்தில் {pct} இதிலிருந்து வருகிறது.",
               "{name}-ஐ உங்கள் மெனுவில் முதலில் காட்டுங்கள். மெதுவாக விற்கும் பொருட்களுக்கு அருகில் வையுங்கள்."),
        "kn": ("{name} ಹೆಚ್ಚು ಮಾರಾಟವಾಗುತ್ತದೆ — ನಿಮ್ಮ ಹಣದ {pct} ಇದರಿಂದ ಬರುತ್ತದೆ.",
               "{name} ಅನ್ನು ನಿಮ್ಮ ಮೆನುವಿನಲ್ಲಿ ಮೊದಲು ತೋರಿಸಿ. ನಿಧಾನ ವಸ್ತುಗಳ ಪಕ್ಕದಲ್ಲಿ ಇಡಿ."),
    },
    "subcat_laggard": {
        "en": ("{name} sells the least — only {value} in total.",
               "Decide one way or the other: push {name} hard for one month with an offer, or stop selling it. Keeping it without a plan wastes your money and space."),
        "hi": ("{name} सबसे कम बिकता है — कुल मिलाकर सिर्फ़ {value}।",
               "एक फ़ैसला कीजिए: या तो एक महीने ऑफ़र देकर {name} को ज़ोर से बेचिए, या इसे बंद कर दीजिए। बिना योजना के रखना पैसा और जगह दोनों बर्बाद करता है।"),
        "ta": ("{name} மிகக் குறைவாக விற்கிறது — மொத்தம் {value} மட்டுமே.",
               "ஒரு முடிவு எடுங்கள்: ஒரு மாதம் சலுகையுடன் {name}-ஐ வலுவாக விற்கவும், அல்லது நிறுத்தவும். திட்டமின்றி வைத்திருப்பது பணத்தையும் இடத்தையும் வீணாக்குகிறது."),
        "kn": ("{name} ಅತಿ ಕಡಿಮೆ ಮಾರಾಟವಾಗುತ್ತದೆ — ಒಟ್ಟು ಕೇವಲ {value}.",
               "ಒಂದು ನಿರ್ಧಾರ ಮಾಡಿ: ಒಂದು ತಿಂಗಳು ಕೊಡುಗೆಯೊಂದಿಗೆ {name} ಅನ್ನು ಬಲವಾಗಿ ಮಾರಿ, ಅಥವಾ ನಿಲ್ಲಿಸಿ. ಯೋಜನೆಯಿಲ್ಲದೆ ಇಟ್ಟುಕೊಳ್ಳುವುದು ಹಣ ಮತ್ತು ಜಾಗ ಎರಡನ್ನೂ ವ್ಯರ್ಥ ಮಾಡುತ್ತದೆ."),
    },
    "subcat_top3_high": {
        "en": ("Just 3 things bring {pct} of all your money.",
               "This is risky. If one stops selling, you lose a lot. Slowly build up a 4th item that sells well."),
        "hi": ("सिर्फ़ 3 चीज़ों से आपकी कुल कमाई का {pct} आता है।",
               "यह जोखिम भरा है। अगर एक भी बिकना बंद हो गया, तो बड़ा नुकसान होगा। धीरे-धीरे एक चौथी अच्छी बिकने वाली चीज़ तैयार कीजिए।"),
        "ta": ("வெறும் 3 பொருட்கள் உங்கள் மொத்தப் பணத்தில் {pct} கொண்டு வருகின்றன.",
               "இது ஆபத்தானது. ஒன்று விற்பனை நின்றால், நீங்கள் நிறைய இழப்பீர்கள். மெதுவாக நான்காவது பொருளை உருவாக்குங்கள்."),
        "kn": ("ಕೇವಲ 3 ವಸ್ತುಗಳು ನಿಮ್ಮ ಒಟ್ಟು ಹಣದ {pct} ತರುತ್ತವೆ.",
               "ಇದು ಅಪಾಯಕಾರಿ. ಒಂದು ಮಾರಾಟ ನಿಂತರೆ, ನೀವು ತುಂಬಾ ಕಳೆದುಕೊಳ್ಳುತ್ತೀರಿ. ನಿಧಾನವಾಗಿ ನಾಲ್ಕನೇ ವಸ್ತುವನ್ನು ಬೆಳೆಸಿ."),
    },
    "subcat_top3_ok": {
        "en": ("Your top 3 items bring {pct} of your money. The rest is spread nicely.",
               "This is healthy. Keep it this way as you add new items."),
        "hi": ("आपकी टॉप 3 चीज़ों से {pct} कमाई आती है। बाकी अच्छी तरह फैली हुई है।",
               "यह अच्छी बात है। नई चीज़ें जोड़ते समय इसे ऐसे ही बनाए रखिए।"),
        "ta": ("உங்கள் சிறந்த 3 பொருட்கள் {pct} பணம் கொண்டு வருகின்றன. மீதி நன்றாக பரவியுள்ளது.",
               "இது ஆரோக்கியமானது. புதிய பொருட்களைச் சேர்க்கும்போது இதையே பராமரியுங்கள்."),
        "kn": ("ನಿಮ್ಮ ಟಾಪ್ 3 ವಸ್ತುಗಳು {pct} ಹಣ ತರುತ್ತವೆ. ಉಳಿದದ್ದು ಚೆನ್ನಾಗಿ ಹರಡಿದೆ.",
               "ಇದು ಆರೋಗ್ಯಕರ. ಹೊಸ ವಸ್ತುಗಳನ್ನು ಸೇರಿಸುವಾಗ ಹೀಗೇ ಇಟ್ಟುಕೊಳ್ಳಿ."),
    },

    # ---------------- SUBCATEGORY DETAIL ----------------
    "detail_share_high": {
        "en": ("{name} is a big part of your shop — {pct} of all your money.",
               "Be careful when changing the price of {name}. A small change here affects your whole shop."),
        "hi": ("{name} आपकी दुकान का बड़ा हिस्सा है — कुल कमाई का {pct}।",
               "{name} का दाम बदलते समय सावधान रहिए। यहाँ छोटा सा बदलाव पूरी दुकान पर असर डालता है।"),
        "ta": ("{name} உங்கள் கடையின் பெரிய பகுதி — மொத்தப் பணத்தில் {pct}.",
               "{name} விலையை மாற்றும்போது கவனமாக இருங்கள். இங்கு சிறிய மாற்றம் முழு கடையையும் பாதிக்கும்."),
        "kn": ("{name} ನಿಮ್ಮ ಅಂಗಡಿಯ ದೊಡ್ಡ ಭಾಗ — ಒಟ್ಟು ಹಣದ {pct}.",
               "{name} ಬೆಲೆ ಬದಲಾಯಿಸುವಾಗ ಎಚ್ಚರವಾಗಿರಿ. ಇಲ್ಲಿ ಸಣ್ಣ ಬದಲಾವಣೆ ಇಡೀ ಅಂಗಡಿಯ ಮೇಲೆ ಪರಿಣಾಮ ಬೀರುತ್ತದೆ."),
    },
    "detail_share_low": {
        "en": ("{name} is a small part of your shop — only {pct} of your money.",
               "Either give {name} a real push for one month, or stop spending time on it."),
        "hi": ("{name} आपकी दुकान का छोटा हिस्सा है — कमाई का सिर्फ़ {pct}।",
               "या तो एक महीने {name} को सही से बढ़ाइए, या इस पर समय लगाना बंद कीजिए।"),
        "ta": ("{name} உங்கள் கடையின் சிறிய பகுதி — உங்கள் பணத்தில் {pct} மட்டுமே.",
               "ஒரு மாதம் {name}-ஐ உண்மையாக முன்னெடுங்கள், அல்லது அதற்கு நேரம் செலவழிப்பதை நிறுத்துங்கள்."),
        "kn": ("{name} ನಿಮ್ಮ ಅಂಗಡಿಯ ಸಣ್ಣ ಭಾಗ — ನಿಮ್ಮ ಹಣದ ಕೇವಲ {pct}.",
               "ಒಂದು ತಿಂಗಳು {name} ಅನ್ನು ನಿಜವಾಗಿ ಮುನ್ನಡೆಸಿ, ಅಥವಾ ಅದಕ್ಕೆ ಸಮಯ ವ್ಯಯಿಸುವುದನ್ನು ನಿಲ್ಲಿಸಿ."),
    },
    "detail_trend_up": {
        "en": ("{name} is doing better — up {pct} from last month.",
               "People are already buying more {name}. Give it more space and tell customers about it now."),
        "hi": ("{name} बेहतर कर रहा है — पिछले महीने से {pct} ऊपर।",
               "लोग पहले से ही {name} ज़्यादा खरीद रहे हैं। इसे ज़्यादा जगह दीजिए और अभी ग्राहकों को बताइए।"),
        "ta": ("{name} சிறப்பாக செயல்படுகிறது — கடந்த மாதத்தை விட {pct} அதிகம்.",
               "மக்கள் ஏற்கனவே {name} அதிகம் வாங்குகிறார்கள். அதற்கு அதிக இடம் கொடுங்கள், இப்போதே வாடிக்கையாளர்களிடம் சொல்லுங்கள்."),
        "kn": ("{name} ಉತ್ತಮವಾಗಿ ಮಾಡುತ್ತಿದೆ — ಕಳೆದ ತಿಂಗಳಿಗಿಂತ {pct} ಹೆಚ್ಚು.",
               "ಜನರು ಈಗಾಗಲೇ {name} ಹೆಚ್ಚು ಖರೀದಿಸುತ್ತಿದ್ದಾರೆ. ಅದಕ್ಕೆ ಹೆಚ್ಚು ಜಾಗ ಕೊಡಿ, ಈಗಲೇ ಗ್ರಾಹಕರಿಗೆ ತಿಳಿಸಿ."),
    },
    "detail_trend_down": {
        "en": ("{name} is dropping — down {pct} from last month.",
               "Check three things: did it run out of stock, did the price change, or did the quality drop?"),
        "hi": ("{name} गिर रहा है — पिछले महीने से {pct} नीचे।",
               "तीन चीज़ें जाँचिए: क्या यह स्टॉक में ख़त्म हो गया, क्या दाम बदला, या क्या क्वालिटी गिर गई?"),
        "ta": ("{name} குறைந்து வருகிறது — கடந்த மாதத்தை விட {pct} குறைவு.",
               "மூன்று விஷயங்களைச் சரிபார்க்கவும்: இருப்பு தீர்ந்ததா, விலை மாறியதா, அல்லது தரம் குறைந்ததா?"),
        "kn": ("{name} ಕುಸಿಯುತ್ತಿದೆ — ಕಳೆದ ತಿಂಗಳಿಗಿಂತ {pct} ಕಡಿಮೆ.",
               "ಮೂರು ವಿಷಯ ಪರಿಶೀಲಿಸಿ: ಸ್ಟಾಕ್ ಖಾಲಿಯಾಯಿತೇ, ಬೆಲೆ ಬದಲಾಯಿತೇ, ಅಥವಾ ಗುಣಮಟ್ಟ ಕುಸಿಯಿತೇ?"),
    },
    "detail_best_day": {
        "en": ("{name} sells best on {day}.",
               "Never let {name} run out on a {day} — that's the day it makes you money."),
        "hi": ("{name} {day} को सबसे ज़्यादा बिकता है।",
               "{day} को {name} कभी ख़त्म मत होने दीजिए — उसी दिन यह आपको कमाई देता है।"),
        "ta": ("{name} {day} அன்று அதிகம் விற்கிறது.",
               "{day} அன்று {name} ஒருபோதும் தீர்ந்துபோக விடாதீர்கள் — அந்த நாளில்தான் அது உங்களுக்கு பணம் தருகிறது."),
        "kn": ("{name} {day} ದಿನ ಹೆಚ್ಚು ಮಾರಾಟವಾಗುತ್ತದೆ.",
               "{day} ದಿನ {name} ಎಂದಿಗೂ ಖಾಲಿಯಾಗಲು ಬಿಡಬೇಡಿ — ಆ ದಿನವೇ ಅದು ನಿಮಗೆ ಹಣ ತರುತ್ತದೆ."),
    },
    "detail_best_product": {
        "en": ("{product} is the best seller inside {name}.",
               "Sell {product} together with the slowest item in {name}. The popular one will pull the slow one along."),
        "hi": ("{name} में {product} सबसे ज़्यादा बिकने वाला है।",
               "{product} को {name} की सबसे धीमी चीज़ के साथ बेचिए। लोकप्रिय चीज़ धीमी चीज़ को भी खींच लेगी।"),
        "ta": ("{name}-க்குள் {product} அதிகம் விற்பனையாகிறது.",
               "{product}-ஐ {name}-இல் மெதுவாக விற்கும் பொருளுடன் சேர்த்து விற்கவும். பிரபலமானது மெதுவானதையும் இழுத்துச் செல்லும்."),
        "kn": ("{name} ಒಳಗೆ {product} ಅತಿ ಹೆಚ್ಚು ಮಾರಾಟವಾಗುತ್ತದೆ.",
               "{product} ಅನ್ನು {name} ನಲ್ಲಿನ ನಿಧಾನ ವಸ್ತುವಿನೊಂದಿಗೆ ಮಾರಿ. ಜನಪ್ರಿಯವಾದದ್ದು ನಿಧಾನವಾದದ್ದನ್ನೂ ಎಳೆದುಕೊಂಡು ಹೋಗುತ್ತದೆ."),
    },

    # ---------------- POSITIONING ----------------
    "pos_signature": {
        "en": ("People love you for one thing more than other cafés: {name}. They talk about it {gap} more than they talk about other cafés.",
               "Put {name} on your board, your Instagram, and your ads. This is the one thing you are already winning at — say it loudly."),
        "hi": ("लोग आपको एक चीज़ के लिए दूसरे कैफ़े से ज़्यादा पसंद करते हैं: {name}। वे इसके बारे में दूसरों से {gap} ज़्यादा बात करते हैं।",
               "{name} को अपने बोर्ड, इंस्टाग्राम और विज्ञापन में डालिए। यही वो चीज़ है जिसमें आप पहले से जीत रहे हैं — इसे ज़ोर से कहिए।"),
        "ta": ("மற்ற கபேக்களை விட ஒரு விஷயத்திற்காக மக்கள் உங்களை விரும்புகிறார்கள்: {name}. அதைப் பற்றி {gap} அதிகமாக பேசுகிறார்கள்.",
               "{name}-ஐ உங்கள் போர்டு, இன்ஸ்டாகிராம், விளம்பரங்களில் வையுங்கள். இதில் நீங்கள் ஏற்கனவே வெல்கிறீர்கள் — சத்தமாக சொல்லுங்கள்."),
        "kn": ("ಇತರ ಕೆಫೆಗಳಿಗಿಂತ ಒಂದು ವಿಷಯಕ್ಕಾಗಿ ಜನರು ನಿಮ್ಮನ್ನು ಇಷ್ಟಪಡುತ್ತಾರೆ: {name}. ಅದರ ಬಗ್ಗೆ {gap} ಹೆಚ್ಚು ಮಾತನಾಡುತ್ತಾರೆ.",
               "{name} ಅನ್ನು ನಿಮ್ಮ ಬೋರ್ಡ್, ಇನ್‌ಸ್ಟಾಗ್ರಾಂ, ಜಾಹೀರಾತುಗಳಲ್ಲಿ ಹಾಕಿ. ಇದರಲ್ಲಿ ನೀವು ಈಗಾಗಲೇ ಗೆಲ್ಲುತ್ತಿದ್ದೀರಿ — ಜೋರಾಗಿ ಹೇಳಿ."),
    },
    "pos_weakness": {
        "en": ("Customers are unhappy about {name}. They speak worse about it than customers of other cafés do.",
               "Fix {name} first, before spending money on ads. Read your last 10 reviews about {name} and fix the complaint you see most often."),
        "hi": ("ग्राहक {name} से ख़ुश नहीं हैं। वे इसके बारे में दूसरे कैफ़े के ग्राहकों से ज़्यादा बुरा कहते हैं।",
               "विज्ञापन पर पैसा लगाने से पहले {name} को ठीक कीजिए। {name} के बारे में अपने पिछले 10 रिव्यू पढ़िए और जो शिकायत सबसे ज़्यादा दिखे उसे ठीक कीजिए।"),
        "ta": ("வாடிக்கையாளர்கள் {name} பற்றி மகிழ்ச்சியாக இல்லை. மற்ற கபே வாடிக்கையாளர்களை விட மோசமாகப் பேசுகிறார்கள்.",
               "விளம்பரத்திற்கு பணம் செலவழிக்கும் முன் {name}-ஐ சரிசெய்யுங்கள். {name} பற்றிய கடைசி 10 விமர்சனங்களைப் படித்து, அடிக்கடி வரும் புகாரை சரிசெய்யுங்கள்."),
        "kn": ("ಗ್ರಾಹಕರು {name} ಬಗ್ಗೆ ಸಂತೋಷವಾಗಿಲ್ಲ. ಇತರ ಕೆಫೆ ಗ್ರಾಹಕರಿಗಿಂತ ಕೆಟ್ಟದಾಗಿ ಮಾತನಾಡುತ್ತಾರೆ.",
               "ಜಾಹೀರಾತಿಗೆ ಹಣ ಖರ್ಚು ಮಾಡುವ ಮೊದಲು {name} ಸರಿಪಡಿಸಿ. {name} ಬಗ್ಗೆ ಕೊನೆಯ 10 ವಿಮರ್ಶೆಗಳನ್ನು ಓದಿ, ಪದೇ ಪದೇ ಬರುವ ದೂರನ್ನು ಸರಿಪಡಿಸಿ."),
    },
    "pos_rating_above": {
        "en": ("Your rating is {value} stars. Other cafés average {peer} stars. You are ahead!",
               "Print your {value} star rating on your board and menu. People trust it and walk in because of it."),
        "hi": ("आपकी रेटिंग {value} स्टार है। दूसरे कैफ़े की औसत {peer} स्टार है। आप आगे हैं!",
               "अपनी {value} स्टार रेटिंग बोर्ड और मेन्यू पर छपवाइए। लोग इस पर भरोसा करते हैं और इसी वजह से अंदर आते हैं।"),
        "ta": ("உங்கள் மதிப்பீடு {value} நட்சத்திரங்கள். மற்ற கபேக்களின் சராசரி {peer}. நீங்கள் முன்னிலையில் இருக்கிறீர்கள்!",
               "உங்கள் {value} நட்சத்திர மதிப்பீட்டை போர்டிலும் மெனுவிலும் அச்சிடுங்கள். மக்கள் அதை நம்பி உள்ளே வருகிறார்கள்."),
        "kn": ("ನಿಮ್ಮ ರೇಟಿಂಗ್ {value} ನಕ್ಷತ್ರಗಳು. ಇತರ ಕೆಫೆಗಳ ಸರಾಸರಿ {peer}. ನೀವು ಮುಂದಿದ್ದೀರಿ!",
               "ನಿಮ್ಮ {value} ನಕ್ಷತ್ರ ರೇಟಿಂಗ್ ಅನ್ನು ಬೋರ್ಡ್ ಮತ್ತು ಮೆನುವಿನಲ್ಲಿ ಮುದ್ರಿಸಿ. ಜನರು ಅದನ್ನು ನಂಬಿ ಒಳಗೆ ಬರುತ್ತಾರೆ."),
    },
    "pos_rating_below": {
        "en": ("Your rating is {value} stars. Other cafés average {peer} stars. You are behind.",
               "Reply to every unhappy review within one day and invite them back. Angry customers who come back often change their rating."),
        "hi": ("आपकी रेटिंग {value} स्टार है। दूसरे कैफ़े की औसत {peer} स्टार है। आप पीछे हैं।",
               "हर नाराज़ रिव्यू का जवाब एक दिन में दीजिए और उन्हें वापस बुलाइए। जो नाराज़ ग्राहक लौटते हैं, वे अक्सर अपनी रेटिंग बदल देते हैं।"),
        "ta": ("உங்கள் மதிப்பீடு {value} நட்சத்திரங்கள். மற்ற கபேக்களின் சராசரி {peer}. நீங்கள் பின்தங்கியிருக்கிறீர்கள்.",
               "ஒவ்வொரு அதிருப்தி விமர்சனத்திற்கும் ஒரு நாளுக்குள் பதிலளித்து மீண்டும் அழையுங்கள். திரும்பி வரும் கோபமான வாடிக்கையாளர்கள் அடிக்கடி மதிப்பீட்டை மாற்றுகிறார்கள்."),
        "kn": ("ನಿಮ್ಮ ರೇಟಿಂಗ್ {value} ನಕ್ಷತ್ರಗಳು. ಇತರ ಕೆಫೆಗಳ ಸರಾಸರಿ {peer}. ನೀವು ಹಿಂದಿದ್ದೀರಿ.",
               "ಪ್ರತಿ ಅತೃಪ್ತ ವಿಮರ್ಶೆಗೆ ಒಂದು ದಿನದೊಳಗೆ ಉತ್ತರಿಸಿ ಮತ್ತೆ ಆಹ್ವಾನಿಸಿ. ಹಿಂತಿರುಗುವ ಕೋಪಗೊಂಡ ಗ್ರಾಹಕರು ಆಗಾಗ್ಗೆ ರೇಟಿಂಗ್ ಬದಲಾಯಿಸುತ್ತಾರೆ."),
    },
    "pos_untapped": {
        "en": ("Customers of other cafés talk a lot about {name}, but almost nobody mentions it for you.",
               "Pick one: either start doing {name} well, or forget it completely and focus on what you are already good at. Doing neither is the worst choice."),
        "hi": ("दूसरे कैफ़े के ग्राहक {name} के बारे में बहुत बात करते हैं, लेकिन आपके लिए कोई इसका ज़िक्र नहीं करता।",
               "एक चुनिए: या तो {name} अच्छे से करना शुरू कीजिए, या इसे पूरी तरह भूलकर जिसमें आप अच्छे हैं उस पर ध्यान दीजिए। दोनों न करना सबसे बुरा है।"),
        "ta": ("மற்ற கபே வாடிக்கையாளர்கள் {name} பற்றி நிறைய பேசுகிறார்கள், ஆனால் உங்களுக்கு யாரும் குறிப்பிடவில்லை.",
               "ஒன்றைத் தேர்ந்தெடுங்கள்: {name}-ஐ நன்றாக செய்யத் தொடங்குங்கள், அல்லது முற்றிலும் மறந்துவிட்டு நீங்கள் சிறந்ததில் கவனம் செலுத்துங்கள்."),
        "kn": ("ಇತರ ಕೆಫೆ ಗ್ರಾಹಕರು {name} ಬಗ್ಗೆ ತುಂಬಾ ಮಾತನಾಡುತ್ತಾರೆ, ಆದರೆ ನಿಮಗಾಗಿ ಯಾರೂ ಹೇಳುವುದಿಲ್ಲ.",
               "ಒಂದನ್ನು ಆರಿಸಿ: {name} ಅನ್ನು ಚೆನ್ನಾಗಿ ಮಾಡಲು ಶುರು ಮಾಡಿ, ಅಥವಾ ಸಂಪೂರ್ಣ ಮರೆತು ನೀವು ಒಳ್ಳೆಯದಾಗಿರುವುದರ ಮೇಲೆ ಗಮನ ಕೊಡಿ."),
    },
    "pos_sentiment": {
        "en": ("Looking at all {count} reviews, customers feel {mood} about your café overall.",
               "Check this number every month. When customers start feeling worse, sales usually drop 2-3 months later."),
        "hi": ("सभी {count} रिव्यू देखकर लगता है कि ग्राहक आपके कैफ़े के बारे में कुल मिलाकर {mood} महसूस करते हैं।",
               "इस नंबर को हर महीने देखिए। जब ग्राहक बुरा महसूस करने लगते हैं, तो 2-3 महीने बाद बिक्री गिरती है।"),
        "ta": ("அனைத்து {count} விமர்சனங்களைப் பார்த்தால், வாடிக்கையாளர்கள் உங்கள் கபே பற்றி மொத்தத்தில் {mood} உணர்கிறார்கள்.",
               "இந்த எண்ணை ஒவ்வொரு மாதமும் சரிபார்க்கவும். வாடிக்கையாளர்கள் மோசமாக உணரத் தொடங்கினால், 2-3 மாதங்களில் விற்பனை குறையும்."),
        "kn": ("ಎಲ್ಲಾ {count} ವಿಮರ್ಶೆಗಳನ್ನು ನೋಡಿದರೆ, ಗ್ರಾಹಕರು ನಿಮ್ಮ ಕೆಫೆ ಬಗ್ಗೆ ಒಟ್ಟಾರೆ {mood} ಭಾವಿಸುತ್ತಾರೆ.",
               "ಈ ಸಂಖ್ಯೆಯನ್ನು ಪ್ರತಿ ತಿಂಗಳು ಪರಿಶೀಲಿಸಿ. ಗ್ರಾಹಕರು ಕೆಟ್ಟದಾಗಿ ಭಾವಿಸಲು ಶುರುವಾದರೆ, 2-3 ತಿಂಗಳಲ್ಲಿ ಮಾರಾಟ ಕುಸಿಯುತ್ತದೆ."),
    },
}

# words used inside params that also need translating
WORDS = {
    "happy": {"en": "happy", "hi": "ख़ुश", "ta": "மகிழ்ச்சி", "kn": "ಸಂತೋಷ"},
    "okay": {"en": "just okay", "hi": "ठीक-ठाक", "ta": "பரவாயில்லை", "kn": "ಪರವಾಗಿಲ್ಲ"},
    "unhappy": {"en": "not happy", "hi": "ख़ुश नहीं", "ta": "மகிழ்ச்சியில்லை", "kn": "ಸಂತೋಷವಿಲ್ಲ"},
}

UI = {
    "whats_happening": {"en": "What's happening", "hi": "क्या हो रहा है", "ta": "என்ன நடக்கிறது", "kn": "ಏನಾಗುತ್ತಿದೆ"},
    "do_this": {"en": "DO THIS", "hi": "यह कीजिए", "ta": "இதைச் செய்யுங்கள்", "kn": "ಇದನ್ನು ಮಾಡಿ"},
}


# Theme names — translated so a Hindi/Tamil/Kannada sentence doesn't end up
# with an English phrase glued into the middle of it.
THEMES = {
    "Work Friendly":         {"en": "Work Friendly", "hi": "काम के लिए अच्छा", "ta": "வேலைக்கு ஏற்றது", "kn": "ಕೆಲಸಕ್ಕೆ ಸೂಕ್ತ"},
    "Cozy Comfort":          {"en": "Cozy & Comfortable", "hi": "आरामदायक माहौल", "ta": "வசதியான சூழல்", "kn": "ಆರಾಮದಾಯಕ ವಾತಾವರಣ"},
    "Social Hangout":        {"en": "Meeting Friends", "hi": "दोस्तों से मिलने की जगह", "ta": "நண்பர்களைச் சந்திக்கும் இடம்", "kn": "ಸ್ನೇಹಿತರನ್ನು ಭೇಟಿಯಾಗುವ ಸ್ಥಳ"},
    "Premium Experience":    {"en": "Premium Feel", "hi": "प्रीमियम अनुभव", "ta": "உயர்தர அனுபவம்", "kn": "ಪ್ರೀಮಿಯಂ ಅನುಭವ"},
    "Instagrammable":        {"en": "Good for Photos", "hi": "फ़ोटो के लिए अच्छा", "ta": "புகைப்படத்திற்கு ஏற்றது", "kn": "ಫೋಟೋಗೆ ಸೂಕ್ತ"},
    "Coffee Focused":        {"en": "Coffee Quality", "hi": "कॉफ़ी की क्वालिटी", "ta": "காபி தரம்", "kn": "ಕಾಫಿ ಗುಣಮಟ್ಟ"},
    "Food Destination":      {"en": "Food & Snacks", "hi": "खाना और स्नैक्स", "ta": "உணவு மற்றும் தின்பண்டங்கள்", "kn": "ಆಹಾರ ಮತ್ತು ತಿಂಡಿ"},
    "Value For Money":       {"en": "Value for Money", "hi": "पैसे की कीमत", "ta": "பணத்திற்கு ஏற்ற மதிப்பு", "kn": "ಹಣಕ್ಕೆ ತಕ್ಕ ಮೌಲ್ಯ"},
    "Ambience Led":          {"en": "Look & Feel", "hi": "माहौल और सजावट", "ta": "சூழல் மற்றும் அலங்காரம்", "kn": "ವಾತಾವರಣ ಮತ್ತು ಅಲಂಕಾರ"},
    "Service Quality":       {"en": "Staff & Service", "hi": "स्टाफ़ और सेवा", "ta": "ஊழியர் மற்றும் சேவை", "kn": "ಸಿಬ್ಬಂದಿ ಮತ್ತು ಸೇವೆ"},
    "Cleanliness & Hygiene": {"en": "Cleanliness", "hi": "साफ़-सफ़ाई", "ta": "தூய்மை", "kn": "ಸ್ವಚ್ಛತೆ"},
    "Speed & Efficiency":    {"en": "Speed of Service", "hi": "सेवा की तेज़ी", "ta": "சேவை வேகம்", "kn": "ಸೇವೆಯ ವೇಗ"},
    "Loyalty & Advocacy":    {"en": "Customers Recommend You", "hi": "ग्राहक सलाह देते हैं", "ta": "வாடிக்கையாளர் பரிந்துரை", "kn": "ಗ್ರಾಹಕರ ಶಿಫಾರಸು"},
}

POINTS = {"en": "points", "hi": "अंक", "ta": "புள்ளிகள்", "kn": "ಅಂಕಗಳು"}


def theme(name: str, lang: str) -> str:
    """Translate a benchmark theme name; unknown names pass through unchanged."""
    return THEMES.get(name, {}).get(lang) or THEMES.get(name, {}).get(DEFAULT_LANG, name)


def points(lang: str) -> str:
    return POINTS.get(lang, POINTS[DEFAULT_LANG])


def word(key: str, lang: str) -> str:
    return WORDS.get(key, {}).get(lang) or WORDS.get(key, {}).get(DEFAULT_LANG, key)


def ui(key: str, lang: str) -> str:
    return UI.get(key, {}).get(lang) or UI.get(key, {}).get(DEFAULT_LANG, key)


def render(insight: dict, lang: str = DEFAULT_LANG) -> dict:
    """
    Turn {"type","key","params","highlight"} into a display-ready insight
    with `text` and `action` in the requested language. Unknown keys or
    languages fall back to English rather than crashing the page.
    """
    key = insight.get("key")
    params = insight.get("params", {})
    entry = T.get(key)
    if not entry:
        return {**insight, "text": insight.get("text", key or ""), "action": insight.get("action", "")}
    text_tpl, action_tpl = entry.get(lang) or entry.get(DEFAULT_LANG)
    try:
        text = text_tpl.format(**params)
        action = action_tpl.format(**params)
    except (KeyError, IndexError):
        text, action = text_tpl, action_tpl
    return {"type": insight.get("type", "neutral"), "text": text,
            "action": action, "highlight": insight.get("highlight")}


def render_all(insights: list[dict], lang: str = DEFAULT_LANG) -> list[dict]:
    return [render(i, lang) for i in insights]
