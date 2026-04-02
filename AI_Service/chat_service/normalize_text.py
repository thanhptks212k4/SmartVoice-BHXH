import re

# ===== TỪ VIẾT TẮT CHUYÊN NGÀNH BẢO HIỂM XÃ HỘI =====

ABBREVIATIONS = {
    # --- Bảo hiểm ---
    "BHXH": "bảo hiểm xã hội",
    "BHYT": "bảo hiểm y tế",
    "BHTN": "bảo hiểm thất nghiệp",
    "BHTNLĐ": "bảo hiểm tai nạn lao động",
    "BNN": "bệnh nghề nghiệp",
    "TNLĐ": "tai nạn lao động",
    "TNLĐ-BNN": "tai nạn lao động bệnh nghề nghiệp",

    # --- Đối tượng ---
    "NLĐ": "người lao động",
    "NSDLĐ": "người sử dụng lao động",
    "HĐLĐ": "hợp đồng lao động",

    # --- Cơ quan, tổ chức ---
    "UBND": "ủy ban nhân dân",
    "HĐND": "hội đồng nhân dân",
    "CP": "chính phủ",
    "QH": "quốc hội",
    "BYT": "bộ y tế",
    "BLĐTBXH": "bộ lao động thương binh và xã hội",
    "BTC": "bộ tài chính",
    "LĐTBXH": "lao động thương binh và xã hội",
    "CSSK": "chăm sóc sức khỏe",
    "KCB": "khám chữa bệnh",
    "CSKH": "chăm sóc khách hàng",

    # --- Văn bản pháp luật ---
    "NĐ": "nghị định",
    "TT": "thông tư",
    "QĐ": "quyết định",
    "NQ": "nghị quyết",
    "CV": "công văn",
    "VBHN": "văn bản hợp nhất",
    "QPPL": "quy phạm pháp luật",
    "BLLĐ": "bộ luật lao động",

    # --- Chế độ BHXH ---
    "MĐCS": "mức đóng cơ sở",
    "LCS": "lương cơ sở",
    "LCBĐ": "lương cơ bản đóng",
    "LTTĐ": "lương tối thiểu đóng",
    "BHXHBB": "bảo hiểm xã hội bắt buộc",
    "BHXHTN": "bảo hiểm xã hội tự nguyện",
    "TCTN": "trợ cấp thất nghiệp",

    # --- Thuật ngữ tài chính ---
    "VNĐ": "Việt Nam đồng",
    "GDP": "tổng sản phẩm quốc nội",
    "NSNN": "ngân sách nhà nước",
    
    # --- Lương, thu nhập ---
    "LTT": "lương tối thiểu",
    "LTTVN": "lương tối thiểu vùng",
    "TNBQ": "thu nhập bình quân",

    # --- Y tế, khám chữa bệnh ---
    "CSYT": "cơ sở y tế",
    "BV": "bệnh viện",
    "PK": "phòng khám",
    "ĐKKCBBĐ": "đăng ký khám chữa bệnh ban đầu",
    "TTYT": "trung tâm y tế",
    "DVYT": "dịch vụ y tế",
    "DMTBHYT": "danh mục thuốc bảo hiểm y tế",
    "VTYT": "vật tư y tế",

    # --- Sổ, thẻ ---
    "CMND": "chứng minh nhân dân",
    "CCCD": "căn cước công dân",
    "MST": "mã số thuế",
    "MSBHXH": "mã số bảo hiểm xã hội",

    # --- Hành chính ---
    "TP": "thành phố",
    "TX": "thị xã",
    "TT": "thị trấn",
    "TTHC": "thủ tục hành chính",
    "DVC": "dịch vụ công",
    "DVCTT": "dịch vụ công trực tuyến",
    "CSDL": "cơ sở dữ liệu",
    "CNTT": "công nghệ thông tin",

    # --- Chế độ hưu trí, tử tuất ---
    "LHTT": "lương hưu trí tử tuất",

    # --- Từ viết tắt phổ biến ---
    "VD": "ví dụ",
    "VN": "Việt Nam",
    "ĐK": "đăng ký",
    "ĐT": "điện thoại",
    "NS": "ngân sách",
    "HĐ": "hợp đồng",
    "DN": "doanh nghiệp",
    "TC": "tổ chức",
    "CB": "cán bộ",
    "CCVC": "công chức viên chức",
    "VC": "viên chức",
    "HCSN": "hành chính sự nghiệp",
    "ĐBQH": "đại biểu quốc hội",
    "XHCN": "xã hội chủ nghĩa",
    "CSXH": "chính sách xã hội",
    "ASXH": "an sinh xã hội",
}

# ===== CHUYỂN ĐỔI SỐ SANG CHỮ TIẾNG VIỆT =====

ONES = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]

def _read_two_digits(n, has_tens=True):
    """Đọc số có 2 chữ số."""
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
        result = ONES[tens] + " mươi "
    
    if ones == 0:
        pass
    elif ones == 1 and tens > 1:
        result += "mốt"
    elif ones == 4 and tens > 1:
        result += "tư"
    elif ones == 5 and tens >= 1:
        result += "lăm"
    else:
        result += ONES[ones]
    
    return result.strip()

def _read_three_digits(n, has_hundreds=True):
    """Đọc số có 3 chữ số."""
    if n == 0:
        return ""
    hundreds = n // 100
    remainder = n % 100
    result = ""
    if hundreds > 0:
        result = ONES[hundreds] + " trăm "
    elif has_hundreds:
        result = "không trăm "
    
    if remainder > 0:
        result += _read_two_digits(remainder, has_tens=(hundreds > 0 or has_hundreds))
    
    return result.strip()

def number_to_vietnamese(n):
    """Chuyển số nguyên thành chữ tiếng Việt."""
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
    """Xử lý số có dấu chấm phân cách hàng nghìn (VD: 10.000.000)."""
    num_str = match.group(0)
    # Kiểm tra xem đó có phải số với dot separator không (các nhóm 3 chữ số)
    parts = num_str.split(".")
    if all(len(p) == 3 for p in parts[1:]) and len(parts[0]) <= 3:
        # Đây là số có dấu chấm phân cách hàng nghìn
        clean_num = int(num_str.replace(".", ""))
        return number_to_vietnamese(clean_num)
    return num_str

def _convert_decimal_number(match):
    """Xử lý số thập phân với dấu phẩy (VD: 3,5)."""
    integer_part = match.group(1)
    decimal_part = match.group(2)
    result = number_to_vietnamese(int(integer_part)) + " phẩy "
    # Đọc từng chữ số phần thập phân
    for digit in decimal_part:
        result += ONES[int(digit)] + " "
    return result.strip()

def _convert_plain_number(match):
    """Xử lý số đơn giản."""
    num_str = match.group(0)
    try:
        n = int(num_str)
        return number_to_vietnamese(n)
    except ValueError:
        return num_str


# ===== HÀM CHÍNH =====

def normalize_text(text: str) -> str:
    """
    Chuẩn hóa text từ LLM trước khi gửi TTS.
    - Chuyển viết tắt → đầy đủ
    - Chuyển số → chữ tiếng Việt
    - Chuyển ký hiệu → chữ
    - Loại bỏ markdown formatting
    """
    
    # 1. Loại bỏ markdown formatting
    # Bỏ headers (##, ###, etc.)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Bỏ bold **text** hoặc __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    # Bỏ italic *text* hoặc _text_  
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'(?<!\w)_(.+?)_(?!\w)', r'\1', text)
    # Bỏ bullet points
    text = re.sub(r'^\s*[\*\-\+]\s+', '', text, flags=re.MULTILINE)
    # Bỏ numbered list markers
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    # Bỏ backtick code
    text = re.sub(r'`(.+?)`', r'\1', text)
    
    # 2. Thay thế viết tắt (ưu tiên viết tắt dài trước)
    sorted_abbrs = sorted(ABBREVIATIONS.keys(), key=len, reverse=True)
    for abbr in sorted_abbrs:
        # Dùng word boundary để tránh thay thế sai (VD: "BV" trong "BHXHBBV")
        pattern = r'\b' + re.escape(abbr) + r'\b'
        text = re.sub(pattern, ABBREVIATIONS[abbr], text)
    
    # 3. Xử lý phần trăm: "8%" → "tám phần trăm"
    # Số thập phân + %
    text = re.sub(r'(\d+),(\d+)\s*%', lambda m: _convert_decimal_number(m) + " phần trăm", text)
    # Số nguyên + %
    text = re.sub(r'(\d+)\s*%', lambda m: number_to_vietnamese(int(m.group(1))) + " phần trăm", text)
    
    # 4. Xử lý "đồng/tháng", "đồng/năm" etc.
    text = re.sub(r'đồng/tháng', 'đồng một tháng', text)
    text = re.sub(r'đồng/năm', 'đồng một năm', text)
    text = re.sub(r'đồng/ngày', 'đồng một ngày', text)
    text = re.sub(r'tháng/năm', 'tháng trên năm', text)
    text = re.sub(r'lần/năm', 'lần một năm', text)
    
    # 5. Xử lý số có dấu chấm phân cách hàng nghìn (VD: 10.000.000)
    text = re.sub(r'\d{1,3}(?:\.\d{3})+', _convert_number_with_dot_separator, text)
    
    # 6. Xử lý số thập phân (VD: 3,5)
    text = re.sub(r'(\d+),(\d+)', _convert_decimal_number, text)
    
    # 7. Xử lý số nguyên còn lại
    text = re.sub(r'\b\d+\b', _convert_plain_number, text)
    
    # 8. Dọn dẹp khoảng trắng thừa
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    
    return text


if __name__ == "__main__":
    # Test cases
    tests = [
        "Mức đóng BHXH là 10.000.000 VNĐ",
        "Tỷ lệ đóng là 8% cho NLĐ và 17,5% cho NSDLĐ",
        "**Chế độ thai sản** bao gồm:",
        "Lương cơ sở: 1.800.000 đồng/tháng",
        "Theo NĐ 115/2015/NĐ-CP của CP",
        "NLĐ đóng BHXHBB, BHYT, BHTN theo quy định của BLĐTBXH",
        "Thẻ BHYT có giá trị KCB tại các CSYT trên toàn quốc",
        "CCCD hoặc CMND khi làm thủ tục TTHC",
        "### Các chế độ BHXH bắt buộc\n- Ốm đau\n- Thai sản\n- TNLĐ-BNN\n- Hưu trí\n- Tử tuất",
        "Mức hưởng TCTN bằng 60% mức bình quân tiền lương đóng BHTN",
        "Quỹ BHXH chi trả 1.500.000.000 VNĐ cho 25.000 người thụ hưởng",
    ]
    
    for t in tests:
        print(f"Input:  {t}")
        print(f"Output: {normalize_text(t)}")
        print()
