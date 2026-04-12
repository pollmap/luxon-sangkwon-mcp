"""
소상공인 상가정보 업종코드 매핑.

3-level hierarchy:
  대분류 (e.g., Q = 음식)
  중분류 (e.g., Q01 = 한식, Q12 = 커피점/카페)
  소분류 (e.g., Q12A01 = 커피전문점/카페/다방)

Default analysis level: 중분류 (~200 categories)
"""
from typing import Dict, Optional

# 대분류 코드 → 이름
CATEGORY_L = {
    "Q": "음식",
    "D": "소매",
    "F": "생활서비스",
    "N": "학문/교육",
    "R": "부동산",
    "L": "숙박",
    "P": "스포츠",
    "O": "관광/여가/오락",
    "S": "수리/개인",
    "G": "의료",
    "I": "제조",
    "E": "도매",
}

# 대분류별 경쟁 가중치 (음식이 가장 경쟁 치열)
CATEGORY_WEIGHT = {
    "Q": 1.2,   # 음식
    "D": 1.0,   # 소매
    "F": 0.8,   # 생활서비스
    "L": 1.1,   # 숙박
    "O": 0.9,   # 관광/여가
    "G": 0.7,   # 의료
}
DEFAULT_WEIGHT = 0.9

# 한국어 별칭 → 중분류 코드
# 사용자가 "카페"라고 하면 Q12로 매핑
CATEGORY_ALIASES: Dict[str, str] = {
    # 음식 (Q)
    "한식": "Q01", "한국음식": "Q01", "한정식": "Q01",
    "중식": "Q02", "중국음식": "Q02", "중국집": "Q02",
    "일식": "Q03", "일본음식": "Q03", "초밥": "Q03", "스시": "Q03",
    "양식": "Q04", "서양음식": "Q04", "이탈리안": "Q04", "파스타": "Q04",
    "제과점": "Q05", "베이커리": "Q05", "빵집": "Q05", "빵": "Q05",
    "패스트푸드": "Q06", "햄버거": "Q06", "버거": "Q06",
    "치킨": "Q07", "치킨집": "Q07", "닭": "Q07", "통닭": "Q07",
    "분식": "Q08", "떡볶이": "Q08", "김밥": "Q08",
    "술집": "Q09", "호프": "Q09", "맥주": "Q09", "바": "Q09", "포차": "Q09",
    "카페": "Q12", "커피": "Q12", "커피숍": "Q12", "커피전문점": "Q12", "다방": "Q12",
    "음식점": "Q01",  # default to 한식
    "고기": "Q10", "삼겹살": "Q10", "고깃집": "Q10", "구이": "Q10",
    "피자": "Q11", "피자집": "Q11",

    # 소매 (D)
    "편의점": "D01", "슈퍼마켓": "D02", "슈퍼": "D02", "마트": "D02",
    "의류": "D03", "옷가게": "D03", "옷": "D03", "패션": "D03",
    "화장품": "D04", "뷰티": "D04", "코스메틱": "D04",
    "약국": "D05", "드럭스토어": "D05",
    "꽃집": "D06", "꽃": "D06", "플라워": "D06",
    "안경": "D07", "안경점": "D07",
    "서점": "D08", "책방": "D08", "책": "D08",
    "휴대폰": "D09", "핸드폰": "D09", "스마트폰": "D09",
    "반려동물": "D10", "애완동물": "D10", "펫": "D10", "펫샵": "D10",

    # 생활서비스 (F)
    "미용": "F01", "미용실": "F01", "헤어": "F01", "헤어샵": "F01", "머리": "F01",
    "세탁": "F02", "세탁소": "F02", "빨래": "F02",
    "부동산중개": "F03", "공인중개사": "F03",
    "네일": "F04", "네일샵": "F04", "네일아트": "F04",
    "피부관리": "F05", "에스테틱": "F05", "피부": "F05",
    "필라테스": "F06", "요가": "F06", "헬스": "F06", "헬스장": "F06", "PT": "F06", "피트니스": "F06",

    # 숙박 (L)
    "호텔": "L01", "모텔": "L02", "펜션": "L03", "게스트하우스": "L04",

    # 교육 (N)
    "학원": "N01", "영어학원": "N01", "수학학원": "N01",
    "유치원": "N02", "어린이집": "N02",
}

# 중분류 코드 → 이름 (주요 항목)
# 전체 목록은 SQLite categories 테이블에서 로드
CATEGORY_M_NAMES: Dict[str, str] = {
    "Q01": "한식", "Q02": "중식", "Q03": "일식", "Q04": "양식",
    "Q05": "제과점/베이커리", "Q06": "패스트푸드", "Q07": "치킨",
    "Q08": "분식", "Q09": "호프/주점", "Q10": "구이", "Q11": "피자",
    "Q12": "커피점/카페",
    "D01": "편의점", "D02": "슈퍼마켓", "D03": "의류",
    "D04": "화장품", "D05": "약국", "D06": "꽃집",
    "D07": "안경", "D08": "서점", "D09": "휴대폰", "D10": "반려동물",
    "F01": "미용실", "F02": "세탁소", "F03": "부동산중개",
    "F04": "네일샵", "F05": "피부관리", "F06": "헬스/피트니스",
    "L01": "호텔", "L02": "모텔", "L03": "펜션",
    "N01": "학원", "N02": "유치원/어린이집",
}


def resolve_category(user_input: str) -> Optional[Dict]:
    """
    Resolve user's natural language input to a category code.

    Args:
        user_input: Korean text like "카페", "치킨", "Q12"

    Returns:
        {"code": "Q12", "name": "커피점/카페", "level": "중분류", "대분류": "음식"}
        or None if no match
    """
    if not user_input:
        return None

    text = user_input.strip()

    # Direct code match (e.g., "Q12")
    if text.upper() in CATEGORY_M_NAMES:
        code = text.upper()
        return _build_result(code)

    # Exact alias match
    if text in CATEGORY_ALIASES:
        code = CATEGORY_ALIASES[text]
        return _build_result(code)

    # Case-insensitive alias match
    text_lower = text.lower()
    for alias, code in CATEGORY_ALIASES.items():
        if alias.lower() == text_lower:
            return _build_result(code)

    # Substring search: only match if user input contains a full alias (not the reverse)
    # e.g., "커피전문점" contains "커피" → match. But "커" alone won't match "커피".
    for alias, code in CATEGORY_ALIASES.items():
        if alias in text and len(alias) >= 2:
            return _build_result(code)

    # Substring search in category names (same direction)
    for code, name in CATEGORY_M_NAMES.items():
        if name in text and len(name) >= 2:
            return _build_result(code)

    return None


def _build_result(code: str) -> Dict:
    """Build a category result dict from a 중분류 code."""
    l_code = code[0]
    return {
        "code": code,
        "name": CATEGORY_M_NAMES.get(code, code),
        "level": "중분류",
        "대분류코드": l_code,
        "대분류": CATEGORY_L.get(l_code, "기타"),
    }


def get_category_weight(category_code: str) -> float:
    """Get competition weight for a category (based on 대분류)."""
    if not category_code:
        return DEFAULT_WEIGHT
    l_code = category_code[0]
    return CATEGORY_WEIGHT.get(l_code, DEFAULT_WEIGHT)
