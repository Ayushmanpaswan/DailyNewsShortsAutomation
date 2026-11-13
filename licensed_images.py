import hashlib
import io
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

from PIL import Image, ImageOps


COMMONS_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "DailyNewsShortsAutomation/1.0 (licensed-news-short workflow)"
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MIN_IMAGE_WIDTH = 320
MIN_IMAGE_HEIGHT = 240
MIN_IMAGE_AREA = 120_000

ALLOWED_LICENSE_MARKERS = (
    "cc by",
    "cc-by",
    "cc0",
    "public domain",
    "pdm",
    "pd-us",
    "pd-india",
)
REJECTED_LICENSE_MARKERS = ("noncommercial", "non-commercial", "nc", "no derivatives", "nd")
STOPWORDS = set("the and for with from this that news latest india भारत की के का में और पर एक यह आज से को ने की है हैं था पर तक द्वारा बारे बड़ी बड़े खबर समाचार".split())
PLACEHOLDER_TERMS = ("logo", "icon", "placeholder", "no-image", "no_image", "default", "dummy", "favicon", "sprite", "avatar")
COMMONS_CACHE = {}
COMMONS_METRICS = {"api_requests": 0, "cache_hits": 0}
CACHE_FILE = Path(__file__).resolve().parent / "data" / "commons_image_cache.json"
CACHE_TTL_SECONDS = 7 * 24 * 60 * 60
NEGATIVE_CACHE_SECONDS = 6 * 60 * 60
MAX_API_RETRIES = 2
MAX_BACKOFF_SECONDS = 60
# These are deliberately explicit editorial mappings.  They are not a
# translator: every source spelling below must occur in the story before its
# canonical Commons search term can be used.
ENTITY_ALIASES = {
    "मोदी": "Narendra Modi",
    "नरेंद्र": "Narendra",
    "जेलेंस्की": "Volodymyr Zelenskyy",
    "सोनिया": "Sonia Gandhi",
    "गांधी": "Gandhi",
    "मुर्मु": "Droupadi Murmu",
    "द्रौपदी मुर्मु": "Droupadi Murmu",
    "राष्ट्रपति मुर्मु": "Droupadi Murmu",
    "योगी": "Yogi Adityanath",
    "योगी आदित्यनाथ": "Yogi Adityanath",
    "केजीएमयू": "KGMU",
    "केजीएमयू अस्पताल": "KGMU hospital",
    "किंग जॉर्ज चिकित्सा विश्वविद्यालय": "King George Medical University",
    "दिल्ली": "Delhi",
    "लखनऊ": "Lucknow",
    "मुंबई": "Mumbai",
    "वाराणसी": "Varanasi",
    "केरल": "Kerala",
    "केरलम": "Kerala",
    "भारत": "India",
    "अमेरिका": "United States",
    "रूस": "Russia",
    "यूक्रेन": "Ukraine",
    "पीएम": "Prime Minister",
    "भारत सरकार": "Government of India",
    "केंद्र सरकार": "Government of India",
    "सुप्रीम कोर्ट": "Supreme Court of India",
    "सर्वोच्च न्यायालय": "Supreme Court of India",
    "चुनाव आयोग": "Election Commission of India",
    "निर्वाचन आयोग": "Election Commission of India",
    "आरबीआई": "Reserve Bank of India",
    "भारतीय रिजर्व बैंक": "Reserve Bank of India",
    "इसरो": "Indian Space Research Organisation",
    "भारतीय अंतरिक्ष अनुसंधान संगठन": "Indian Space Research Organisation",
    "नासा": "NASA",
    "एम्स": "AIIMS",
    "अखिल भारतीय आयुर्विज्ञान संस्थान": "AIIMS",
    "आईसीएमआर": "Indian Council of Medical Research",
    "भारतीय आयुर्विज्ञान अनुसंधान परिषद": "Indian Council of Medical Research",
    "डब्ल्यूएचओ": "World Health Organization",
    "विश्व स्वास्थ्य संगठन": "World Health Organization",
    "भाजपा": "Bharatiya Janata Party",
    "बीजेपी": "Bharatiya Janata Party",
    "कांग्रेस": "Indian National Congress",
    "भारतीय रेल": "Indian Railways",
    "रेलवे": "Indian Railways",
    "दिल्ली पुलिस": "Delhi Police",
    "उत्तर प्रदेश सरकार": "Government of Uttar Pradesh",
    "यूपी सरकार": "Government of Uttar Pradesh",
    "महाराष्ट्र सरकार": "Government of Maharashtra",
    "पश्चिम बंगाल": "West Bengal",
    "उत्तर प्रदेश": "Uttar Pradesh",
    "नई दिल्ली": "New Delhi",
    "कोलकाता": "Kolkata",
    "चेन्नई": "Chennai",
    "बेंगलुरु": "Bengaluru",
    "हैदराबाद": "Hyderabad",
    "अहमदाबाद": "Ahmedabad",
    "पुणे": "Pune",
    "कश्मीर": "Kashmir",
    "जम्मू": "Jammu",
    "मणिपुर": "Manipur",
    "तमिलनाडु": "Tamil Nadu",
    "कर्नाटक": "Karnataka",
    "महाराष्ट्र": "Maharashtra",
    "बिहार": "Bihar",
    "गुजरात": "Gujarat",
    "पंजाब": "Punjab",
    "राजस्थान": "Rajasthan",
    "अमित शाह": "Amit Shah",
    "राहुल गांधी": "Rahul Gandhi",
    "प्रियंका गांधी": "Priyanka Gandhi",
    "मल्लिकार्जुन खड़गे": "Mallikarjun Kharge",
    "अरविंद केजरीवाल": "Arvind Kejriwal",
    "ममता बनर्जी": "Mamata Banerjee",
    "अखिलेश यादव": "Akhilesh Yadav",
    "अखिलेश": "Akhilesh Yadav",
    "स्वामी प्रसाद मौर्य": "Swami Prasad Maurya",
    "शिवराज सिंह चौहान": "Shivraj Singh Chouhan",
    "एकनाथ शिंदे": "Eknath Shinde",
    "नितिन गडकरी": "Nitin Gadkari",
    "एस जयशंकर": "S. Jaishankar",
    "शाहरुख खान": "Shah Rukh Khan",
    "अमिताभ बच्चन": "Amitabh Bachchan",
    "विराट कोहली": "Virat Kohli",
    "रोहित शर्मा": "Rohit Sharma",
    "नीरज चोपड़ा": "Neeraj Chopra",
    "शाहरुख": "Shah Rukh Khan",
    "शाहरुख खान": "Shah Rukh Khan",
    "काजोल": "Kajol",
    "बहरीन": "Bahrain", "ईरान": "Iran", "आईआरजीसी": "Islamic Revolutionary Guard Corps",
    "बीवाईडी": "BYD", "डेंजा": "Denza", "डेंजा एन8": "Denza N8", "ओला": "Ola Cabs",
    "सीसीपीए": "Central Consumer Protection Authority",
    "केंद्रीय उपभोक्ता संरक्षण प्राधिकरण": "Central Consumer Protection Authority",
    "एएनआई टेक्नोलॉजीज": "ANI Technologies",
}


ENGLISH_ENTITY_ALIASES = {
    "narendra modi": "Narendra Modi",
    "volodymyr zelenskyy": "Volodymyr Zelenskyy",
    "sonia gandhi": "Sonia Gandhi",
    "aishwarya rai": "Aishwarya Rai",
    "shatrughan sinha": "Shatrughan Sinha",
    "udit narayan": "Udit Narayan",
    "droupadi murmu": "Droupadi Murmu",
    "yogi adityanath": "Yogi Adityanath",
    "kgmu": "KGMU",
    "king george medical university": "King George Medical University",
    "kerala": "Kerala",
    "government of india": "Government of India",
    "supreme court of india": "Supreme Court of India",
    "election commission of india": "Election Commission of India",
    "reserve bank of india": "Reserve Bank of India",
    "indian space research organisation": "Indian Space Research Organisation",
    "aiims": "AIIMS",
    "indian council of medical research": "Indian Council of Medical Research",
    "world health organization": "World Health Organization",
    "bharatiya janata party": "Bharatiya Janata Party",
    "indian national congress": "Indian National Congress",
    "indian railways": "Indian Railways",
    "delhi police": "Delhi Police",
    "government of uttar pradesh": "Government of Uttar Pradesh",
    "uttar pradesh": "Uttar Pradesh",
    "new delhi": "New Delhi",
    "kolkata": "Kolkata", "chennai": "Chennai", "bengaluru": "Bengaluru",
    "hyderabad": "Hyderabad", "ahmedabad": "Ahmedabad", "pune": "Pune",
    "amit shah": "Amit Shah", "rahul gandhi": "Rahul Gandhi",
    "mamata banerjee": "Mamata Banerjee", "arvind kejriwal": "Arvind Kejriwal",
    "shah rukh khan": "Shah Rukh Khan", "amitabh bachchan": "Amitabh Bachchan",
    "virat kohli": "Virat Kohli", "rohit sharma": "Rohit Sharma",
    "neeraj chopra": "Neeraj Chopra", "tuberculosis": "tuberculosis",
    "akhilesh yadav": "Akhilesh Yadav", "shivraj singh chouhan": "Shivraj Singh Chouhan",
    "swami prasad maurya": "Swami Prasad Maurya",
    "shahrukh": "Shah Rukh Khan", "kajol": "Kajol",
    "byd": "BYD", "denza n8": "Denza N8", "denza": "Denza", "ola": "Ola Cabs", "ola cabs": "Ola Cabs",
    "ccpa": "Central Consumer Protection Authority",
    "central consumer protection authority": "Central Consumer Protection Authority",
    "ani technologies": "ANI Technologies", "bahrain": "Bahrain", "iran": "Iran",
    "irgc": "Islamic Revolutionary Guard Corps", "georgia": "Georgia",
}
CONTEXT_ALIASES = {
    "war": "war", "election": "election", "pollution": "pollution",
    "accident": "accident", "murder": "murder", "arrest": "arrest",
    "meeting": "meeting", "talks": "talks", "phone": "phone call",
    "scheme": "scheme", "policy": "policy", "project": "project",
    "song": "song", "festival": "festival",
    "protest": "protest", "demonstration": "demonstration", "strike": "strike",
    "bomb threat": "bomb threat", "threat": "threat", "coalition": "coalition",
    "tribute": "tribute", "death": "death", "funeral": "funeral",
    "launch": "launch", "inauguration": "inauguration", "opening": "opening",
    "verdict": "court verdict", "hearing": "court hearing", "judgment": "court judgment",
    "budget": "budget", "cabinet": "cabinet meeting", "summit": "summit",
    "agreement": "agreement", "deal": "deal", "visit": "official visit",
    "rain": "rain", "flood": "flood", "cyclone": "cyclone", "earthquake": "earthquake",
    "fire": "fire", "crash": "crash", "collapse": "building collapse",
    "outbreak": "disease outbreak", "vaccine": "vaccine", "vaccination": "vaccination",
    "hospital": "hospital", "health": "public health", "disease": "disease",
    "match": "cricket match", "tournament": "tournament", "medal": "medal",
    "attack": "attack", "attacked": "attack", "claim": "claim", "claimed": "claim",
    "retaliation": "retaliation", "fine": "fine", "penalty": "penalty",
    "action": "regulatory action", "advisory": "advisory", "traffic advisory": "traffic advisory",
    "dance": "dance", "video": "video", "electric car": "electric car",
    "electric vehicle": "electric vehicle",
    "यात्रा": "official visit", "दौरा": "official visit", "धरना": "protest",
    "प्रदर्शन": "protest", "हड़ताल": "strike", "शुरुआत": "launch",
    "छठ पूजा": "Chhath Puja", "बम की धमकी": "bomb threat", "धमकी": "threat",
    "गठबंधन": "coalition", "श्रद्धांजलि": "tribute", "निधन": "death",
    "उद्घाटन": "inauguration", "फैसला": "court verdict", "सुनवाई": "court hearing",
    "प्रक्षेपण": "launch",
    "बजट": "budget", "मंत्रिमंडल": "cabinet meeting", "शिखर सम्मेलन": "summit",
    "बारिश": "rain", "बाढ़": "flood", "चक्रवात": "cyclone", "भूकंप": "earthquake",
    "आग": "fire", "विस्फोट": "explosion", "टक्कर": "crash", "गिरना": "collapse",
    "प्रकोप": "disease outbreak", "वैक्सीन": "vaccine", "टीकाकरण": "vaccination",
    "अस्पताल": "hospital", "बीमारी": "disease", "मैच": "cricket match",
    "टूर्नामेंट": "tournament", "पदक": "medal",
    "हमला": "attack", "हमले": "attack", "हमलों": "attack", "दावा": "claim", "दावे": "claim",
    "बदला": "retaliation", "जुर्माना": "fine", "जुर्माने": "fine",
    "कार्रवाई": "regulatory action",
    "एडवाइजरी": "advisory", "ट्रैफिक एडवाइजरी": "traffic advisory",
    "गाना": "song", "नाच": "dance", "डांस": "dance", "वीडियो": "video",
    "इलेक्ट्रिक": "electric vehicle", "ईवी": "electric vehicle",
    "युद्ध": "war", "चुनाव": "election",
    "प्रदूषण": "pollution", "हादसा": "accident",
    "हत्या": "murder", "गिरफ्तार": "arrest",
    "बैठक": "meeting", "बातचीत": "talks",
    "फोन": "phone call", "योजना": "scheme",
    "नीति": "policy", "परियोजना": "project",
    "गीत": "song", "महोत्सव": "festival",
    "टीबी": "tuberculosis", "क्षय रोग": "tuberculosis",
    "पोर्टेबल एक्स-रे": "portable x-ray", "एक्स-रे": "x-ray",
    "जांच": "investigation", "जाँच": "investigation",
    "भ्रामक सूचना": "misinformation", "डीपफेक": "deepfake",
    "स्मार्ट पुलिसिंग": "smart policing",
    "नियुक्ति पत्र": "appointment letter", "नियुक्ति": "appointment",
    "जूनियर असिस्टेंट": "junior assistant", "सरकारी नौकरी": "government job",
    "एथनॉल": "ethanol", "गड़बड़ी": "irregularities",
    "पेट्रोल": "petrol", "मिश्रण": "blending",
    "हिंदू-मुस्लिम एकता": "communal harmony", "सांप्रदायिक सौहार्द": "communal harmony",
    "मुखाग्नि": "cremation", "चिता": "cremation", "अंतिम संस्कार": "funeral rites",
}

# A place or country can be useful corroboration, but it cannot identify a
# specific incident when the story also names a company, person, organization,
# vehicle, or multiple participants. These are deliberately conservative.
BROAD_ENTITY_TERMS = {
    "India", "Delhi", "New Delhi", "Mumbai", "Kolkata", "Chennai", "Bengaluru",
    "Hyderabad", "Ahmedabad", "Pune", "Uttar Pradesh", "Maharashtra", "Bihar",
    "Gujarat", "Punjab", "Rajasthan", "United States", "Russia", "Ukraine",
}

# If one of these appears in the story, it is the event being illustrated.
# A related topic such as "electric vehicle" or a festival name cannot replace
# the primary action (for example, launch or traffic advisory).
PRIMARY_EVENT_CONTEXTS = {
    "attack", "accident", "arrest", "bomb threat", "collapse", "court hearing",
    "court judgment", "court verdict", "crash", "death", "explosion", "fine",
    "flood", "fire", "funeral", "inauguration", "launch", "murder", "official visit",
    "protest", "regulatory action", "strike", "traffic advisory", "war",
}

# Explicit story-specific anchors. They are usable only when the source
# spelling occurs in the story; they are not translated or inferred.
STORY_ANCHOR_ALIASES = {
    "early-warning radar": "early-warning radar",
    "अर्ली-वॉर्निंग रडार": "early-warning radar",
    "रडार": "early-warning radar",
    "telecom tower": "telecom tower",
    "टेलीकॉम टावर": "telecom tower",
    "sirik": "Sirik",
    "सिरिक": "Sirik",
    "denza n8": "Denza N8",
    "डेंजा एन8": "Denza N8",
}


class ImageSelectionError(ValueError):
    def __init__(self, message, records):
        super().__init__(message)
        self.records = records


def _value(metadata, key):
    value = metadata.get(key, {})
    if isinstance(value, dict):
        return str(value.get("value", "")).strip()
    return str(value or "").strip()


def _tokens(text):
    return [token.casefold() for token in re.findall(r"[A-Za-z\u0900-\u097F][A-Za-z\u0900-\u097F0-9'-]{2,}", text or "") if token.casefold() not in STOPWORDS]


def _matched_mappings(item):
    text = f"{item.get('headline', '')} {item.get('detail', '')}"
    folded = text.casefold()
    entities = []
    contexts = []
    for source_term, english in sorted(ENTITY_ALIASES.items(), key=lambda pair: len(pair[0]), reverse=True):
        if source_term.casefold() in folded:
            entities.append({"source_term": source_term, "canonical": english})
    for source_term, english in sorted(ENGLISH_ENTITY_ALIASES.items(), key=lambda pair: len(pair[0]), reverse=True):
        if _term_present(folded, source_term):
            entities.append({"source_term": source_term, "canonical": english})
    for source_term, english in sorted(CONTEXT_ALIASES.items(), key=lambda pair: len(pair[0]), reverse=True):
        if source_term.casefold() in folded:
            contexts.append({"source_term": source_term, "canonical": english})
    dedup = lambda entries: list({entry["canonical"]: entry for entry in entries}.values())
    return dedup(entities), dedup(contexts)


def _term_present(text, term):
    return re.search(
        rf"(?<![\w\u0900-\u097f]){re.escape(term.casefold())}(?![\w\u0900-\u097f])",
        text.casefold(),
    ) is not None


def _query_terms(item):
    entities, contexts = _story_terms(item)
    return list(dict.fromkeys(entities + contexts))[:12]


def _story_terms(item):
    entities, contexts = _matched_mappings(item)
    return list(dict.fromkeys(entry["canonical"] for entry in entities)), list(dict.fromkeys(entry["canonical"] for entry in contexts))


def _story_anchor_terms(item):
    text = f"{item.get('headline', '')} {item.get('detail', '')}"
    folded = text.casefold()
    anchors = []
    for source_term, canonical in sorted(STORY_ANCHOR_ALIASES.items(), key=lambda pair: len(pair[0]), reverse=True):
        if _term_present(folded, source_term):
            anchors.append(canonical)
    return list(dict.fromkeys(anchors))


def story_mapping(item):
    """Return an auditable record of only the explicit aliases found in the story."""
    entities, contexts = _matched_mappings(item)
    entity_terms = list(dict.fromkeys(entry["canonical"] for entry in entities))
    context_terms = list(dict.fromkeys(entry["canonical"] for entry in contexts))
    missing = []
    if not entity_terms:
        missing.append("entity")
    if not context_terms:
        missing.append("event/context")
    return {
        "entities": entities,
        "contexts": contexts,
        "entity_terms": entity_terms,
        "context_terms": context_terms,
        "story_anchor_terms": _story_anchor_terms(item),
        "queries": [f"{entity} {context}" for entity in entity_terms for context in context_terms][:8],
        "status": "ready" if entity_terms and context_terms else "rejected",
        "mapping_explanation": (
            "Explicit source-term matches only; no translation or inferred aliases. "
            f"Matched {len(entities)} entity mapping(s) and {len(contexts)} event/context mapping(s)."
        ),
        "rejection_reason": None if entity_terms and context_terms else "missing explicit " + " and ".join(missing) + " mapping",
    }


def search_query(item):
    queries = search_queries(item)
    return queries[0] if queries else ""


def search_queries(item):
    entities, contexts = _story_terms(item)
    if not entities or not contexts:
        return []
    queries = []
    for entity in entities:
        for context in contexts:
            query = f"{entity} {context}"
            if query not in queries:
                queries.append(query)
    return queries[:8]


def _load_persistent_cache():
    if not CACHE_FILE.is_file():
        return {"version": 1, "queries": {}, "rejected": {}}
    try:
        value = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        if value.get("version") != 1:
            return {"version": 1, "queries": {}, "rejected": {}}
        value.setdefault("queries", {})
        value.setdefault("rejected", {})
        return value
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "queries": {}, "rejected": {}}


PERSISTENT_CACHE = _load_persistent_cache()


def get_commons_metrics():
    return dict(COMMONS_METRICS)


def _save_persistent_cache():
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = CACHE_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(PERSISTENT_CACHE, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(CACHE_FILE)


def _retry_delay(response, attempt):
    retry_after = response.headers.get("Retry-After") if response else None
    if retry_after:
        try:
            return min(MAX_BACKOFF_SECONDS, max(0, int(retry_after)))
        except ValueError:
            try:
                retry_date = parsedate_to_datetime(retry_after)
                return min(MAX_BACKOFF_SECONDS, max(0, int(retry_date.timestamp() - datetime.now(timezone.utc).timestamp())))
            except (TypeError, ValueError, OverflowError):
                pass
    return min(MAX_BACKOFF_SECONDS, 2 ** attempt)


def _license_info(metadata):
    short = _value(metadata, "LicenseShortName")
    usage = _value(metadata, "UsageTerms")
    url = _value(metadata, "LicenseUrl")
    combined = f"{short} {usage} {url}".casefold()
    if not short or any(marker in combined for marker in REJECTED_LICENSE_MARKERS):
        return None
    if not any(marker in combined for marker in ALLOWED_LICENSE_MARKERS):
        return None
    return short, url, usage


def _commons_candidates(query):
    if query in COMMONS_CACHE:
        COMMONS_METRICS["cache_hits"] += 1
        return COMMONS_CACHE[query]
    now = time.time()
    cached = PERSISTENT_CACHE["queries"].get(query)
    if cached:
        if cached.get("blocked_until", 0) > now:
            COMMONS_METRICS["cache_hits"] += 1
            COMMONS_CACHE[query] = []
            return []
        if now - cached.get("updated_at", 0) < CACHE_TTL_SECONDS:
            COMMONS_METRICS["cache_hits"] += 1
            pages = cached.get("pages", [])
            COMMONS_CACHE[query] = pages
            return pages
    time.sleep(0.25)
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": "6",
        "gsrlimit": "12",
        "prop": "imageinfo|categories",
        "iiprop": "url|size|extmetadata",
        "iiurlwidth": "1600",
        "format": "json",
        "formatversion": "2",
    }
    request = urllib.request.Request(
        COMMONS_API + "?" + urllib.parse.urlencode(params),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    payload = None
    for attempt in range(1, MAX_API_RETRIES + 1):
        try:
            COMMONS_METRICS["api_requests"] += 1
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as error:
            if error.code not in {429, 500, 502, 503, 504} or attempt >= MAX_API_RETRIES:
                PERSISTENT_CACHE["queries"][query] = {"pages": [], "updated_at": now, "blocked_until": now + NEGATIVE_CACHE_SECONDS}
                _save_persistent_cache()
                COMMONS_CACHE[query] = []
                return []
            time.sleep(_retry_delay(error, attempt))
        except (urllib.error.URLError, TimeoutError):
            if attempt >= MAX_API_RETRIES:
                PERSISTENT_CACHE["queries"][query] = {"pages": [], "updated_at": now, "blocked_until": now + NEGATIVE_CACHE_SECONDS}
                _save_persistent_cache()
                COMMONS_CACHE[query] = []
                return []
            time.sleep(min(MAX_BACKOFF_SECONDS, 2 ** attempt))
    pages = payload.get("query", {}).get("pages", []) if payload else []
    PERSISTENT_CACHE["queries"][query] = {"pages": pages, "updated_at": now, "blocked_until": 0}
    _save_persistent_cache()
    COMMONS_CACHE[query] = pages
    return pages


def prefetch_queries(queries):
    """Batch related queries once; exact query caches remain authoritative."""
    unique = list(dict.fromkeys(query for query in queries if query))
    for start in range(0, len(unique), 3):
        batch = unique[start:start + 3]
        if len(batch) == 1 or all(query in COMMONS_CACHE or query in PERSISTENT_CACHE["queries"] for query in batch):
            continue
        combined = " OR ".join(f'"{query}"' for query in batch)
        pages = _commons_candidates(combined)
        for query in batch:
            PERSISTENT_CACHE["queries"].setdefault(query, {"pages": pages, "updated_at": time.time(), "blocked_until": 0})
            COMMONS_CACHE.setdefault(query, pages)
    _save_persistent_cache()


def _relevance_assessment(item, page, metadata):
    entity_terms, context_terms = _story_terms(item)
    anchor_terms = _story_anchor_terms(item)
    evidence_text = " ".join([
        page.get("title", ""),
        _value(metadata, "ObjectName"),
        _value(metadata, "ImageDescription"),
        _value(metadata, "Categories"),
        " ".join(str(category.get("title", "")) for category in page.get("categories", [])),
    ]).casefold()
    matched_entities = [term for term in entity_terms if _term_present(evidence_text, term)]
    matched_context = [term for term in context_terms if _term_present(evidence_text, term)]
    matched_anchors = [term for term in anchor_terms if _term_present(evidence_text, term)]
    if not matched_entities:
        return None, "metadata contains no matching story entity"
    if not matched_context:
        return None, "metadata contains no matching story event/context"

    primary_contexts = [term for term in context_terms if term in PRIMARY_EVENT_CONTEXTS]
    matched_primary = [term for term in primary_contexts if term in matched_context]
    if primary_contexts and not matched_primary:
        return None, (
            "metadata matches only a broad topic or secondary context; "
            "the story's primary event is not identified"
        )
    if anchor_terms and not matched_anchors:
        return None, (
            "metadata matches the broad subject/event but not the story-specific "
            "incident, location detail, or model anchor"
        )

    specific_entities = [term for term in entity_terms if term not in BROAD_ENTITY_TERMS]
    matched_specific = [term for term in specific_entities if term in matched_entities]
    if specific_entities and not matched_specific:
        return None, (
            "metadata matches only broad locations/countries; "
            "no story-specific subject is identified"
        )

    evidence = (
        "Metadata-only match; not visual confirmation. "
        "Entity terms: " + ", ".join(sorted(set(matched_entities))) +
        "; event/context terms: " + ", ".join(sorted(set(matched_context))) +
        "; primary event terms: " + ", ".join(sorted(set(matched_primary or matched_context))) +
        "; specific subject terms: " + ", ".join(sorted(set(matched_specific or matched_entities))) +
        "; story anchor terms: " + ", ".join(sorted(set(matched_anchors or anchor_terms)))
    )
    return evidence, None


def _relevance(item, page, metadata):
    evidence, _ = _relevance_assessment(item, page, metadata)
    return evidence


def _download_valid(url, output_path, used_hashes):
    if any(term in urllib.parse.unquote(url).casefold() for term in PLACEHOLDER_TERMS):
        raise ValueError("placeholder or UI asset URL")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "image/jpeg,image/png,image/webp,*/*"})
    with urllib.request.urlopen(request, timeout=30) as response:
        content_type = response.headers.get_content_type()
        if content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise ValueError(f"unsupported image response type: {content_type}")
        raw = response.read(MAX_IMAGE_BYTES + 1)
    if len(raw) > MAX_IMAGE_BYTES:
        raise ValueError("image exceeds size limit")
    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.verify()
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            width, height = image.size
            if width < MIN_IMAGE_WIDTH or height < MIN_IMAGE_HEIGHT or width * height < MIN_IMAGE_AREA:
                raise ValueError(f"image is too small: {width}x{height}")
            if width == height:
                raise ValueError("square image is likely a logo, icon, or placeholder")
            normalized = ImageOps.exif_transpose(image).convert("RGB")
            normalized.save(output_path, format="JPEG", quality=90, optimize=True)
        digest = hashlib.sha256(output_path.read_bytes()).hexdigest()
        if digest in used_hashes:
            raise ValueError("duplicate photograph")
        used_hashes.add(digest)
    except (OSError, ValueError) as error:
        output_path.unlink(missing_ok=True)
        raise ValueError(f"image validation failed: {error}") from error


def _page_url(page):
    return "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(
        page.get("title", ""), safe=":()"
    )


def _candidate_record(page, query, metadata, image_url=""):
    return {
        "query": query,
        "image_page_url": _page_url(page),
        "image_url": image_url,
        "author": re.sub(r"<[^>]+>", "", _value(metadata, "Artist") or _value(metadata, "Credit")).strip(),
        "license": _value(metadata, "LicenseShortName"),
        "license_url": _value(metadata, "LicenseUrl"),
    }


def select_image(item, output_path, used_hashes, rejection_record=None):
    records = []
    rejection_record = rejection_record if rejection_record is not None else {"candidates": []}
    queries = search_queries(item)
    if not queries:
        mapping = story_mapping(item)
        print(
            f"Mapping rejected: {item.get('headline', '')} — {mapping['rejection_reason']}; "
            f"entities={mapping['entity_terms'] or 'none'}; contexts={mapping['context_terms'] or 'none'}"
        )
        records.append({
            "rejection_stage": "query_generation",
            "rejection_reason": mapping["rejection_reason"],
        })
        rejection_record["mapping"] = mapping
        rejection_record["candidates"] = records
        raise ImageSelectionError("story has no explicit entity and event/context terms", records)
    mapping = story_mapping(item)
    print(
        f"Mapping ready: {item.get('headline', '')} — "
        f"entities={mapping['entity_terms']}; contexts={mapping['context_terms']}; "
        f"queries={queries}"
    )

    for query in queries:
        pages = _commons_candidates(query)
        if not pages:
            records.append({
                "query": query,
                "rejection_stage": "discovery",
                "rejection_reason": "no Commons candidates returned",
            })
            continue
        for page in pages:
            info = (page.get("imageinfo") or [{}])[0]
            metadata = info.get("extmetadata", {})
            image_url = info.get("thumburl") or info.get("url", "")
            candidate = _candidate_record(page, query, metadata, image_url)
            license_data = _license_info(metadata)
            if not license_data:
                candidate.update({
                    "rejection_stage": "license",
                    "rejection_reason": "missing or non-permissive license",
                })
                records.append(candidate)
                continue
            relevance, relevance_reason = _relevance_assessment(item, page, metadata)
            if not relevance:
                candidate.update({
                    "rejection_stage": "relevance",
                    "rejection_reason": relevance_reason or "specific entity and primary event evidence did not match",
                })
                records.append(candidate)
                continue
            if not image_url:
                candidate.update({
                    "rejection_stage": "image_validation",
                    "rejection_reason": "candidate has no downloadable image URL",
                })
                records.append(candidate)
                continue
            try:
                _download_valid(image_url, output_path, used_hashes)
            except (OSError, ValueError, urllib.error.URLError) as error:
                reason = str(error)
                candidate.update({
                    "rejection_stage": "duplicate" if "duplicate" in reason.casefold() else "image_validation",
                    "rejection_reason": reason,
                })
                records.append(candidate)
                continue
            short, license_url, usage = license_data
            title = page.get("title", "").removeprefix("File:")
            page_url = _page_url(page)
            author = candidate["author"] or "Unknown author"
            attribution = f"{title} — {author}; {short}; {license_url or usage}; source: {page_url}"
            candidate.update({
                "status": "accepted",
                "relevance_evidence": relevance,
                "attribution": attribution,
            })
            records.append(candidate)
            rejection_record["candidates"] = records
            return {
                "image": str(output_path),
                "image_source_url": image_url,
                "image_page_url": page_url,
                "image_author": author,
                "image_license": short,
                "image_license_url": license_url,
                "image_attribution": attribution,
                "image_relevance_evidence": relevance,
                "image_title": title,
                "image_sharealike": "sa" in short.casefold(),
            }
    rejection_record["candidates"] = records
    raise ImageSelectionError(
        "no verified relevant licensed Commons photograph found",
        records,
    )
