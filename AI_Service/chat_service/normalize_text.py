import re

# ===== TU VIET TAT CHUYEN NGANH BAO HIEM XA HOI =====

ABBREVIATIONS = {
    "BHXH": "bảo hiểm xã hội",
    "BHYT": "bảo hiểm y tế",
    "BHTN": "bảo hiểm thất nghiệp",
    "BHTNLD": "bảo hiểm tai nạn lao động",
    "BNN": "bệnh nghề nghiệp",
    "TNLD": "tai nạn lao động",
    "NLD": "người lao động",
    "NSDLD": "người sử dụng lao động",
    "HDLD": "hợp đồng lao động",
    "UBND": "ủy ban nhân dân",
    "HDND": "hội đồng nhân dân",
    "BYT": "bộ y tế",
    "BLDTBXH": "bộ lao động thương binh và xã hội",
    "BTC": "bộ tài chính",
    "LDTBXH": "lao động thương binh và xã hội",
    "CSSK": "chăm sóc sức khỏe",
    "KCB": "khám chữa bệnh",
    "ND": "nghị định",
    "QD": "quyết định",
    "NQ": "nghị quyết",
    "CV": "công văn",
    "VBHN": "văn bản hợp nhất",
    "BLLD": "bộ luật lao động",
    "LCS": "lương cơ sở",
    "BHXHBB": "bảo hiểm xã hội bắt buộc",
    "BHXHTN": "bảo hiểm xã hội tự nguyện",
    "TCTN": "trợ cấp thất nghiệp",
    "VND": "Việt Nam đồng",
    "NSNN": "ngân sách nhà nước",
    "LTT": "lương tối thiểu",
    "CSYT": "cơ sở y tế",
    "BV": "bệnh viện",
    "PK": "phòng khám",
    "TTYT": "trung tâm y tế",
    "CMND": "chứng minh nhân dân",
    "CCCD": "căn cước công dân",
    "MST": "mã số thuế",
    "TTHC": "thủ tục hành chính",
    "DVC": "dịch vụ công",
    "DN": "doanh nghiệp",
    "CB": "cán bộ",
    "VC": "viên chức",
    "CSXH": "chính sách xã hội",
    "ASXH": "an sinh xã hội",
}

# ===== CHUYEN DOI SO SANG CHU TIENG VIET =====

ONES = ["khong", "mot", "hai", "ba", "bon", "nam", "sau", "bay", "tam", "chin"]
ONES_TONE = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]

def _read_two_digits(n, has_tens=True):
    if n == 0:
        return ""
    tens = n // 10
    ones = n % 10
    result = ""
    if tens == 0 and has_tens:
        result = "lẻ "
    elif tens == 1:
        result = "mười "
    elif tens > 1:
        result = ONES_TONE[tens] + " mươi "

    if ones == 0:
        pass
    elif ones == 1 and tens > 1:
        result += "mốt"
    elif ones == 4 and tens > 1:
        result += "tư"
    elif ones == 5 and tens >= 1:
        result += "lăm"
    else:
        result += ONES_TONE[ones]

    return result.strip()

def _read_three_digits(n, has_hundreds=True):
    if n == 0:
        return ""
    hundreds = n // 100
    remainder = n % 100
    result = ""
    if hundreds > 0:
        result = ONES_TONE[hundreds] + " trăm "
    elif has_hundreds:
        result = "không trăm "

    if remainder > 0:
        result += _read_two_digits(remainder, has_tens=(hundreds > 0 or has_hundreds))

    return result.strip()

def number_to_vietnamese(n):
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
        has_hundreds = (i < len(groups) - 1)
        text = _read_three_digits(groups[i], has_hundreds=has_hundreds)
        if text:
            if i < len(units):
                text += " " + units[i] if units[i] else ""
            parts.append(text.strip())

    return " ".join(parts)

def _convert_number_with_dot_separator(match):
    num_str = match.group(0)
    parts = num_str.split(".")
    if all(len(p) == 3 for p in parts[1:]) and len(parts[0]) <= 3:
        clean_num = int(num_str.replace(".", ""))
        return number_to_vietnamese(clean_num)
    return num_str

def _convert_decimal_number(match):
    integer_part = match.group(1)
    decimal_part = match.group(2)
    result = number_to_vietnamese(int(integer_part)) + " phẩy "
    for digit in decimal_part:
        result += ONES_TONE[int(digit)] + " "
    return result.strip()

def _convert_plain_number(match):
    num_str = match.group(0)
    try:
        n = int(num_str)
        return number_to_vietnamese(n)
    except ValueError:
        return num_str


# ===== HAM CHINH =====

def normalize_text(text: str) -> str:
    """
    Chuan hoa text tu LLM truoc khi gui TTS:
    - Loai bo markdown
    - Chuyen viet tat thanh day du
    - Chuyen ky hieu toan hoc thanh chu
    - Chuyen so thanh chu tieng Viet
    """

    # 1. Loai bo markdown formatting
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'(?<!\w)_(.+?)_(?!\w)', r'\1', text)
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'`(.+?)`', r'\1', text)

    # 2. Thay the viet tat
    sorted_abbrs = sorted(ABBREVIATIONS.keys(), key=len, reverse=True)
    for abbr in sorted_abbrs:
        pattern = r'\b' + re.escape(abbr) + r'\b'
        text = re.sub(pattern, ABBREVIATIONS[abbr], text)

    # 3.5. Xu ly 'x' lam dau nhan TRUOC khi convert so (vi sau convert so khong con digit)
    text = re.sub(r'(?<=\d)\s*[xX]\s*(?=[\d(])', ' nhân ', text)

    # 3. Xu ly phan tram: "8%" -> "tam phan tram"
    text = re.sub(
        r'(\d+),(\d+)\s*%',
        lambda m: _convert_decimal_number(m) + " phần trăm",
        text
    )
    text = re.sub(
        r'(\d+)\s*%',
        lambda m: number_to_vietnamese(int(m.group(1))) + " phần trăm",
        text
    )

    # 4. Xu ly ky hieu toan hoc va dau dac biet
    # Xu ly 'x' va 'X' lam dau nhan truoc (truoc khi convert so)
    text = re.sub(r'(?<=\d)\s*[xX]\s*(?=\d)', ' nhân ', text)
    text = re.sub(r'(?<=\d)\s*[xX]\s*(?=\d)', ' nhân ', text)
    text = re.sub(r'\s*\*\s*(?=\d)', ' nhân ', text)
    text = re.sub(r'(?<=\d)\s*\*\s*', ' nhân ', text)
    text = re.sub(r'(?<=\d)\s*/\s*(?=\d)', ' chia ', text)
    text = re.sub(r'(?<=\d)\s*\+\s*(?=\d)', ' cộng ', text)
    text = re.sub(r'(?<=\d)\s*-\s*(?=\d)', ' trừ ', text)
    text = re.sub(r'(?<=\d)\s*=\s*', ' bằng ', text)
    text = re.sub(r'=\s*(?=\d)', ' bằng ', text)
    text = re.sub(r'>=', ' lớn hơn hoặc bằng ', text)
    text = re.sub(r'<=', ' nhỏ hơn hoặc bằng ', text)
    text = re.sub(r'(?<=\s)>\s*(?=\d)', ' lớn hơn ', text)
    text = re.sub(r'(?<=\s)<\s*(?=\d)', ' nhỏ hơn ', text)
    text = re.sub(r'≥', ' lớn hơn hoặc bằng ', text)
    text = re.sub(r'≤', ' nhỏ hơn hoặc bằng ', text)
    text = re.sub(r'×', ' nhân ', text)
    text = re.sub(r'÷', ' chia ', text)
    text = re.sub(r'→', ', ', text)
    text = re.sub(r'–', ' đến ', text)
    text = re.sub(r'—', ', ', text)
    text = re.sub(r'\.{2,}', ' ', text)
    text = re.sub(r'[""""]', '', text)
    text = re.sub(r"[''''`]", '', text)
    text = re.sub(r'[()]', ' ', text)
    text = re.sub(r'[\[\]]', ' ', text)
    text = re.sub(r';', '.', text)
    text = re.sub(r':(?=\s)', ',', text)

    # 5. Xu ly don vi / phan cach
    text = re.sub(r'đồng/tháng', 'đồng một tháng', text)
    text = re.sub(r'đồng/năm', 'đồng một năm', text)
    text = re.sub(r'đồng/ngày', 'đồng một ngày', text)
    text = re.sub(r'tháng/năm', 'tháng trên năm', text)
    text = re.sub(r'lần/năm', 'lần một năm', text)

    # 6. Xu ly so co dau cham phan cach hang nghin (VD: 10.000.000)
    text = re.sub(r'\d{1,3}(?:\.\d{3})+', _convert_number_with_dot_separator, text)

    # 7. Xu ly so thap phan (VD: 3,5)
    text = re.sub(r'(\d+),(\d+)', _convert_decimal_number, text)

    # 8. Xu ly so nguyen con lai
    text = re.sub(r'\b\d+\b', _convert_plain_number, text)

    # 9. Don dep khoang trang thua
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()

    return text


if __name__ == "__main__":
    tests = [
        "Mức đóng BHXH là 10.000.000 VND",
        "Tỷ lệ đóng là 8% cho NLD và 17,5% cho NSDLD",
        "**Chế độ thai sản** bao gồm:",
        "Lương cơ sở: 1.800.000 đồng/tháng",
        "8.000.000 * 8% = 640.000 đồng",
        "8.000.000 x 17,5% = 1.400.000 đồng",
        "Mức hưởng >= 75% lương đóng BHXH",
        "### Các chế độ BHXH bắt buộc\n- Ốm đau\n- Thai sản\n- TNLD\n- Hưu trí\n- Tử tuất",
        "Mức hưởng TCTN bằng 60% mức bình quân tiền lương đóng BHTN",
    ]

    for t in tests:
        print(f"Input:  {t}")
        print(f"Output: {normalize_text(t)}")
        print()
