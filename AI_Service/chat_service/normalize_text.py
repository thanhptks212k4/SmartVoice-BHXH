import re

# ============================================================
# ABBREVIATIONS - expand AFTER legal doc codes are processed
# ============================================================
ABBREVIATIONS = {
    "BHXH":     "bảo hiểm xã hội",
    "BHYT":     "bảo hiểm y tế",
    "BHTN":     "bảo hiểm thất nghiệp",
    "BHTNLD-BNN": "bảo hiểm tai nạn lao động bệnh nghề nghiệp",
    "BHTNLD":   "bảo hiểm tai nạn lao động",
    "BNN":      "bệnh nghề nghiệp",
    "TNLD":     "tai nạn lao động",
    "NLD":      "người lao động",
    "NSDLD":    "người sử dụng lao động",
    "HDLD":     "hợp đồng lao động",
    "UBND":     "ủy ban nhân dân",
    "HDND":     "hội đồng nhân dân",
    "BYT":      "bộ y tế",
    "BLDTBXH":  "bộ lao động thương binh và xã hội",
    "BTC":      "bộ tài chính",
    "LDTBXH":   "lao động thương binh và xã hội",
    "CSSK":     "chăm sóc sức khỏe",
    "KCB":      "khám chữa bệnh",
    "BLLD":     "bộ luật lao động",
    "LCS":      "lương cơ sở",
    "BHXHBB":   "bảo hiểm xã hội bắt buộc",
    "BHXHTN":   "bảo hiểm xã hội tự nguyện",
    "TCTN":     "trợ cấp thất nghiệp",
    "VND":      "Việt Nam đồng",
    "NSNN":     "ngân sách nhà nước",
    "LTT":      "lương tối thiểu",
    "CSYT":     "cơ sở y tế",
    "BV":       "bệnh viện",
    "PK":       "phòng khám",
    "TTYT":     "trung tâm y tế",
    "CMND":     "chứng minh nhân dân",
    "CCCD":     "căn cước công dân",
    "MST":      "mã số thuế",
    "TTHC":     "thủ tục hành chính",
    "DVC":      "dịch vụ công",
    "DN":       "doanh nghiệp",
    "CB":       "cán bộ",
    "VC":       "viên chức",
    "CSXH":     "chính sách xã hội",
    "ASXH":     "an sinh xã hội",
    "ND":       "nghị định",
    "QD":       "quyết định",
    "NQ":       "nghị quyết",
    "CV":       "công văn",
    "VBHN":     "văn bản hợp nhất",
}

# ============================================================
# LEGAL DOCUMENT TYPE MAP - ordered longest-first to avoid
# partial matches (e.g. "TT" matching inside "TT-BLDTBXH")
# ============================================================
_DOC_TYPE_MAP = [
    ("ND-CP",       "nghị định chính phủ"),
    ("TT-BTC",      "thông tư bộ tài chính"),
    ("TT-BLDTBXH",  "thông tư bộ lao động thương binh và xã hội"),
    ("TT-BYT",      "thông tư bộ y tế"),
    ("TT-BHXH",     "thông tư bảo hiểm xã hội"),
    ("QD-TTG",      "quyết định thủ tướng"),
    ("QD-BHXH",     "quyết định bảo hiểm xã hội"),
    ("QD-BYT",      "quyết định bộ y tế"),
    ("NQ-CP",       "nghị quyết chính phủ"),
    ("QH15",        "quốc hội khóa mười lăm"),
    ("QH14",        "quốc hội khóa mười bốn"),
    ("QH13",        "quốc hội khóa mười ba"),
    ("TT",          "thông tư"),
    ("QD",          "quyết định"),
    ("NQ",          "nghị quyết"),
]


def _normalize_doc_type_key(raw: str) -> str:
    """
    Normalize a captured document type string before lookup.
    Strips whitespace, newlines, normalizes dashes, uppercases.
    Example: "ND-CP\\n" -> "ND-CP", "nd–cp" -> "ND-CP"
    """
    # Replace en-dash / em-dash with ASCII hyphen
    raw = raw.replace("\u2013", "-").replace("\u2014", "-")
    # Remove all whitespace including newlines
    raw = re.sub(r"\s+", "", raw)
    return raw.upper()


def _lookup_doc_type(raw: str) -> str:
    """
    Look up document type string. Returns Vietnamese reading.
    Falls back to lowercased, hyphen-replaced string if unknown.
    """
    key = _normalize_doc_type_key(raw)
    for map_key, map_val in _DOC_TYPE_MAP:
        if key == map_key:
            return map_val
    # Readable fallback: "XYZ-ABC" -> "xyz abc"
    return key.lower().replace("-", " ")


# ============================================================
# NUMBER TO VIETNAMESE
# ============================================================
_ONES = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]


def _read_two_digits(n: int, has_tens: bool = True) -> str:
    if n == 0:
        return ""
    tens, ones = divmod(n, 10)
    result = ""
    if tens == 0 and has_tens:
        result = "lẻ "
    elif tens == 1:
        result = "mười "
    elif tens > 1:
        result = _ONES[tens] + " mươi "

    if ones == 0:
        pass
    elif ones == 1 and tens > 1:
        result += "mốt"
    elif ones == 4 and tens > 1:
        result += "tư"
    elif ones == 5 and tens >= 1:
        result += "lăm"
    else:
        result += _ONES[ones]
    return result.strip()


def _read_three_digits(n: int, has_hundreds: bool = True) -> str:
    if n == 0:
        return ""
    hundreds, remainder = divmod(n, 100)
    result = ""
    if hundreds > 0:
        result = _ONES[hundreds] + " trăm "
    elif has_hundreds:
        result = "không trăm "
    if remainder > 0:
        result += _read_two_digits(remainder, has_tens=(hundreds > 0 or has_hundreds))
    return result.strip()


def number_to_vietnamese(n: int) -> str:
    if n < 0:
        return "âm " + number_to_vietnamese(-n)
    if n == 0:
        return "không"
    units = ["", "nghìn", "triệu", "tỷ", "nghìn tỷ", "triệu tỷ"]
    groups = []
    while n > 0:
        groups.append(n % 1000)
        n //= 1000
    parts = []
    for i in range(len(groups) - 1, -1, -1):
        if groups[i] == 0 and i > 0:
            continue
        has_hundreds = i < len(groups) - 1
        chunk = _read_three_digits(groups[i], has_hundreds=has_hundreds)
        if chunk:
            suffix = (" " + units[i]) if i < len(units) and units[i] else ""
            parts.append(chunk + suffix)
    return " ".join(parts)


def _convert_number_with_dot_separator(match: re.Match) -> str:
    num_str = match.group(0)
    parts = num_str.split(".")
    if all(len(p) == 3 for p in parts[1:]) and len(parts[0]) <= 3:
        return number_to_vietnamese(int(num_str.replace(".", "")))
    return num_str


def _convert_decimal_number(match: re.Match) -> str:
    integer_part = int(match.group(1))
    decimal_part = match.group(2)
    result = number_to_vietnamese(integer_part) + " phẩy "
    result += " ".join(_ONES[int(d)] for d in decimal_part)
    return result.strip()


def _convert_plain_number(match: re.Match) -> str:
    try:
        return number_to_vietnamese(int(match.group(0)))
    except ValueError:
        return match.group(0)


# ============================================================
# LEGAL DOCUMENT CODE HANDLERS
# ============================================================

# Pattern: 115/2015/ND-CP  (with year)
# Group 1: number, Group 2: year (19xx/20xx), Group 3: doc type (ASCII only)
_RE_DOC_WITH_YEAR = re.compile(
    r"\b(\d+)/((?:19|20)\d{2})/([A-Z0-9][A-Z0-9\-]*[A-Z0-9]|[A-Z0-9]+)\b",
    re.ASCII
)

# Pattern: 595/QD-BHXH  (without year)
# Group 1: number, Group 2: doc type
_RE_DOC_NO_YEAR = re.compile(
    r"\b(\d+)/([A-Z][A-Z0-9\-]*[A-Z0-9]|[A-Z]{2,})\b",
    re.ASCII
)


def _replace_doc_with_year(m: re.Match) -> str:
    so = number_to_vietnamese(int(m.group(1)))
    nam = number_to_vietnamese(int(m.group(2)))
    loai = _lookup_doc_type(m.group(3))
    return f"số {so} năm {nam} {loai}"


def _replace_doc_no_year(m: re.Match) -> str:
    so = number_to_vietnamese(int(m.group(1)))
    loai = _lookup_doc_type(m.group(2))
    return f"số {so} {loai}"


# ============================================================
# MAIN NORMALIZE FUNCTION
# ============================================================

def normalize_text(text: str) -> str:
    """
    Normalize Vietnamese LLM output for TTS:
    1. Strip markdown
    2. Process legal document codes (BEFORE abbreviation expansion)
    3. Expand abbreviations
    4. Convert math symbols
    5. Convert percentages
    6. Convert numbers
    7. Clean whitespace
    """

    # ── 1. Strip markdown ──────────────────────────────────
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"\1", text)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"`(.+?)`", r"\1", text)

    # ── 2. Legal document codes (MUST run before abbr expansion) ──
    # Date: ngày DD/MM/YYYY
    text = re.sub(
        r"\bngày\s+(\d{1,2})/(\d{1,2})/(\d{4})\b",
        lambda m: (
            "ngày " + number_to_vietnamese(int(m.group(1))) +
            " tháng " + number_to_vietnamese(int(m.group(2))) +
            " năm " + number_to_vietnamese(int(m.group(3)))
        ),
        text,
    )
    # Month: tháng M/YYYY
    text = re.sub(
        r"\btháng\s+(\d{1,2})/(\d{4})\b",
        lambda m: (
            "tháng " + number_to_vietnamese(int(m.group(1))) +
            " năm " + number_to_vietnamese(int(m.group(2)))
        ),
        text,
    )
    # Year: năm YYYY
    text = re.sub(
        r"\bnăm\s+((?:19|20)\d{2})\b",
        lambda m: "năm " + number_to_vietnamese(int(m.group(1))),
        text,
    )
    # Doc with year: 115/2015/ND-CP
    text = _RE_DOC_WITH_YEAR.sub(_replace_doc_with_year, text)
    # Doc without year: 595/QD-BHXH  (run AFTER with-year to avoid partial match)
    text = _RE_DOC_NO_YEAR.sub(_replace_doc_no_year, text)

    # Article/clause references
    text = re.sub(
        r"\bĐiều\s+(\d+)\b",
        lambda m: "Điều " + number_to_vietnamese(int(m.group(1))),
        text,
    )
    text = re.sub(
        r"\bKhoản\s+(\d+)\b",
        lambda m: "Khoản " + number_to_vietnamese(int(m.group(1))),
        text,
    )
    text = re.sub(
        r"\bMục\s+(\d+)\b",
        lambda m: "Mục " + number_to_vietnamese(int(m.group(1))),
        text,
    )

    # ── 3. Expand abbreviations ────────────────────────────
    for abbr in sorted(ABBREVIATIONS, key=len, reverse=True):
        text = re.sub(r"\b" + re.escape(abbr) + r"\b", ABBREVIATIONS[abbr], text)

    # ── 4. Math symbols ────────────────────────────────────
    # Multiplication: digit x digit  (before number conversion)
    text = re.sub(r"(?<=\d)\s*[xX]\s*(?=[\d(])", " nhân ", text)
    text = re.sub(r"(?<=\d)\s*\*\s*(?=\d)", " nhân ", text)
    text = re.sub(r"(?<=\d)\s*/\s*(?=\d)", " chia ", text)
    text = re.sub(r"(?<=\d)\s*\+\s*(?=\d)", " cộng ", text)
    text = re.sub(r"(?<=\d)\s*-\s*(?=\d)", " trừ ", text)
    text = re.sub(r"(?<=\d)\s*=\s*", " bằng ", text)
    text = re.sub(r"=\s*(?=\d)", " bằng ", text)
    text = re.sub(r">=", " lớn hơn hoặc bằng ", text)
    text = re.sub(r"<=", " nhỏ hơn hoặc bằng ", text)
    text = re.sub(r"≥", " lớn hơn hoặc bằng ", text)
    text = re.sub(r"≤", " nhỏ hơn hoặc bằng ", text)
    text = re.sub(r"×", " nhân ", text)
    text = re.sub(r"÷", " chia ", text)
    text = re.sub(r"→", ", ", text)
    text = re.sub(r"[–—]", " đến ", text)
    text = re.sub(r"\.{2,}", " ", text)
    text = re.sub(r'[""""]', "", text)
    text = re.sub(r"[''''`]", "", text)
    text = re.sub(r"[()]", " ", text)
    text = re.sub(r"[\[\]]", " ", text)
    text = re.sub(r";", ".", text)
    text = re.sub(r":(?=\s)", ",", text)

    # ── 5. Unit separators ─────────────────────────────────
    text = re.sub(r"đồng/tháng", "đồng một tháng", text)
    text = re.sub(r"đồng/năm",   "đồng một năm",   text)
    text = re.sub(r"đồng/ngày",  "đồng một ngày",  text)
    text = re.sub(r"đồng/người", "đồng một người", text)
    text = re.sub(r"tháng/năm",  "tháng trên năm", text)
    text = re.sub(r"lần/năm",    "lần một năm",    text)
    text = re.sub(r"ngày/tháng", "ngày một tháng", text)
    text = re.sub(r"người/tháng","người một tháng",text)

    # ── 6. Percentages (MUST run before number conversion) ─
    # Decimal with dot: 10.5%
    text = re.sub(
        r"(\d+)\.(\d+)\s*%",
        lambda m: (
            number_to_vietnamese(int(m.group(1))) +
            " phẩy " +
            number_to_vietnamese(int(m.group(2))) +
            " phần trăm"
        ),
        text,
    )
    # Decimal with comma: 17,5%
    text = re.sub(
        r"(\d+),(\d+)\s*%",
        lambda m: (
            number_to_vietnamese(int(m.group(1))) +
            " phẩy " +
            number_to_vietnamese(int(m.group(2))) +
            " phần trăm"
        ),
        text,
    )
    # Integer percent: 8%
    text = re.sub(
        r"(\d+)\s*%",
        lambda m: number_to_vietnamese(int(m.group(1))) + " phần trăm",
        text,
    )

    # ── 7. Numbers ─────────────────────────────────────────
    # Thousands separator: 10.000.000
    text = re.sub(r"\d{1,3}(?:\.\d{3})+", _convert_number_with_dot_separator, text)
    # Decimal dot: 17.5
    text = re.sub(
        r"(\d+)\.(\d+)",
        lambda m: (
            number_to_vietnamese(int(m.group(1))) +
            " phẩy " +
            number_to_vietnamese(int(m.group(2)))
        ),
        text,
    )
    # Decimal comma: 3,5
    text = re.sub(r"(\d+),(\d+)", _convert_decimal_number, text)
    # Plain integers
    text = re.sub(r"\b\d+\b", _convert_plain_number, text)

    # ── 8. Final cleanup ───────────────────────────────────
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Ensure no stray newline inside a sentence
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    text = text.strip()

    return text


# ============================================================
# SELF-TEST
# ============================================================
if __name__ == "__main__":
    cases = [
        ("115/2015/ND-CP",      "số một trăm mười lăm năm hai nghìn không trăm mười lăm nghị định chính phủ"),
        ("59/2015/TT-BLDTBXH",  "số năm mươi chín năm hai nghìn không trăm mười lăm thông tư bộ lao động thương binh và xã hội"),
        ("58/2014/QH13",        "số năm mươi tám năm hai nghìn không trăm mười bốn quốc hội khóa mười ba"),
        ("595/QD-BHXH",         "số năm trăm chín mươi lăm quyết định bảo hiểm xã hội"),
        ("10.5% va 21.5%",      "mười phẩy năm phần trăm va hai mươi mốt phẩy năm phần trăm"),
        ("BHTNLD-BNN",          "bảo hiểm tai nạn lao động bệnh nghề nghiệp"),
        ("Điều 26 Luật BHXH",   "Điều hai mươi sáu Luật bảo hiểm xã hội"),
        ("10.000.000 đồng",     "mười triệu đồng"),
    ]

    all_pass = True
    for inp, expected in cases:
        result = normalize_text(inp)
        status = "PASS" if result == expected else "FAIL"
        if status == "FAIL":
            all_pass = False
        print(f"[{status}] IN:  {inp}")
        if status == "FAIL":
            print(f"       EXP: {expected}")
            print(f"       GOT: {result}")
        else:
            print(f"       OUT: {result}")
        print()

    print("All tests passed!" if all_pass else "Some tests FAILED.")
