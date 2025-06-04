import streamlit as st
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from urllib.parse import urljoin
import random
from collections import defaultdict

# -------------------------------
# 1. 환경설정 및 세션 상태 초기화
# -------------------------------
st.set_page_config(page_title="한국 문학 대화형 검색 시스템", page_icon="📚", layout="wide")

if "messages_query" not in st.session_state:
    st.session_state.messages_query = []
if "messages_chat" not in st.session_state:
    st.session_state.messages_chat = []
if "book_metadata" not in st.session_state:
    st.session_state.book_metadata = {}
if "loan_stats" not in st.session_state:
    st.session_state.loan_stats = defaultdict(lambda: {"rank": random.randint(1, 50), "count": random.randint(1, 300)})
if "feedback" not in st.session_state:
    st.session_state.feedback = defaultdict(list)

# -------------------------------
# 2. Gemini API Key 입력
# -------------------------------
st.sidebar.title("🔑 API 및 플랫폼 설정")
gemini_api_key = st.sidebar.text_input("Gemini API Key", type="password")
genai.configure(api_key=gemini_api_key) if gemini_api_key else None

# -------------------------------
# 3. 크롤러 함수 (샘플: YES24, 교보문고, 대학도서관)
# -------------------------------
def crawl_book_metadata(url, max_pages=1):
    """플랫폼별 도서 메타데이터 자동 크롤링 및 키워드 추출"""
    try:
        content_dict = {}
        visited = set()
        to_visit = [url]
        while to_visit and len(visited) < max_pages:
            current_url = to_visit.pop(0)
            if current_url in visited:
                continue
            response = requests.get(current_url, timeout=5)
            soup = BeautifulSoup(response.content, "html.parser")
            # 샘플: 제목, 저자, 출판사, 연도, 요약, 서평, 영상화 여부 등 추출
            title = soup.title.string if soup.title else "제목 없음"
            summary = soup.find("meta", {"name": "description"})
            summary = summary["content"] if summary else soup.get_text()[:500]
            # 실제 서비스에서는 각 플랫폼별 HTML 구조에 맞게 파싱 필요
            content_dict[current_url] = {
                "title": title,
                "summary": summary,
                "content": soup.get_text()[:2000],
                "external_links": [current_url],
                "platform": url.split("/")[2]
            }
            visited.add(current_url)
            # 내부 링크 추가(샘플)
            for link in soup.find_all("a", href=True):
                child_url = urljoin(url, link['href'])
                if child_url.startswith(url) and child_url not in visited and child_url not in to_visit:
                    to_visit.append(child_url)
        return content_dict
    except Exception as e:
        st.warning(f"크롤링 오류: {str(e)}")
        return {}

# -------------------------------
# 4. 생성형 AI 기반 메타데이터/키워드 추출
# -------------------------------
def generate_metadata_ai(book_content):
    """생성형 AI로 인물, 사건, 배경, 감정 등 키워드 및 메타데이터 추출"""
    prompt = f"""
    다음 도서 내용을 분석하여 아래 항목별로 정보를 추출해줘.
    - 인물/주요 등장인물
    - 주요 사건/갈등
    - 시대적 배경
    - 감정적 요소(애증, 고독감 등)
    - 영상화 여부(영화/드라마/웹툰 등, 플랫폼명 포함)
    - 서평(간략 요약)
    - 외부링크(있으면)
    [도서 내용]
    {book_content[:1500]}
    """
    try:
        model = genai.GenerativeModel("gemini-pro")
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI 메타데이터 생성 오류: {str(e)}"

# -------------------------------
# 5. 대출순위/대출횟수 샘플 함수
# -------------------------------
def get_loan_stats(title):
    """로그 분석 기반 대출순위/횟수(샘플)"""
    stats = st.session_state.loan_stats[title]
    return stats["rank"], stats["count"]

# -------------------------------
# 6. 피드백 저장 함수
# -------------------------------
def save_feedback(book_title, meta_type, feedback_text):
    st.session_state.feedback[(book_title, meta_type)].append(feedback_text)

# -------------------------------
# 7. 도서 검색 및 메타데이터 생성 파이프라인
# -------------------------------
def search_and_extract(url):
    # 1) 크롤링
    crawled = crawl_book_metadata(url)
    # 2) AI 메타데이터 생성
    for u, data in crawled.items():
        ai_meta = generate_metadata_ai(data["content"])
        # 간단 파싱(실제 서비스는 구조화 필요)
        data["ai_metadata"] = ai_meta
        # 대출 데이터
        rank, count = get_loan_stats(data["title"])
        data["loan_rank"] = rank
        data["loan_count"] = count
        st.session_state.book_metadata[data["title"]] = data
    return crawled

# -------------------------------
# 8. Streamlit UI: 탭 구조
# -------------------------------
st.title("📚 대화형 문학 디지털 도서 검색 시스템")
st.markdown("""
- 다양한 플랫폼(교보문고, YES24, 대학도서관 등)에서 자동 크롤링 및 AI 기반 메타데이터 추출
- 인물, 사건, 배경, 감정, 영상화, 서평, 외부링크, 대출순위/횟수 등 제공
- 질의탭: 심층 분석/정보, 일반 대화탭: 자유 토론/의견
""")

tab_query, tab_chat = st.tabs(["🔎 질의 (심층 분석)", "💬 일반 대화 (토론/자유 의견)"])

# -------------------------------
# 9. 질의탭: 도서 검색 및 심층 분석
# -------------------------------
with tab_query:
    st.subheader("도서 플랫폼 링크 입력 후 검색")
    url = st.text_input("도서 상세 페이지 URL 입력 (교보문고, YES24, 대학도서관 등)", "")
    if st.button("자동 크롤링 및 AI 분석"):
        if not gemini_api_key:
            st.warning("Gemini API Key를 입력하세요.")
        elif url:
            with st.spinner("도서 정보 분석 중..."):
                results = search_and_extract(url)
            if results:
                for title, data in results.items():
                    st.markdown(f"### {data['title']}")
                    st.write(f"**요약:** {data['summary']}")
                    st.write(f"**AI 메타데이터:**\n{data['ai_metadata']}")
                    st.write(f"**대출순위:** {data['loan_rank']}위 / **대출횟수:** {data['loan_count']}회")
                    st.write(f"**외부링크:**")
                    for link in data["external_links"]:
                        st.markdown(f"- [{data['platform']}]({link})")
                    # 피드백
                    with st.expander("이 도서의 메타데이터에 피드백 남기기"):
                        meta_type = st.selectbox("피드백 항목", ["전체", "키워드", "서평", "영상화", "외부링크"])
                        feedback_text = st.text_area("피드백 입력")
                        if st.button(f"피드백 제출_{title}_{meta_type}"):
                            save_feedback(title, meta_type, feedback_text)
                            st.success("피드백이 저장되었습니다.")
            else:
                st.info("도서 정보를 찾지 못했습니다. URL을 확인하세요.")

    # 심층 질의(챗봇)
    st.divider()
    st.subheader("심층 질의 (도서/메타데이터 기반)")
    user_query = st.text_input("도서, 시대, 감정, 키워드 등으로 질문해보세요.", key="query_input")
    if user_query:
        # 가장 최근 도서 데이터 활용
        if st.session_state.book_metadata:
            last_book = list(st.session_state.book_metadata.values())[-1]
            prompt = f"""
            다음 도서의 메타데이터와 내용을 참고하여, 아래 질문에 답하고, 답변에는 도서 내 직접 인용(문장)도 포함해줘.
            [도서 메타데이터]
            {last_book['ai_metadata']}
            [질문]
            {user_query}
            """
            model = genai.GenerativeModel("gemini-pro")
            response = model.generate_content(prompt)
            st.session_state.messages_query.append(("user", user_query))
            st.session_state.messages_query.append(("ai", response.text))
            st.markdown(f"**AI 답변:**\n{response.text}")
        else:
            st.info("먼저 도서 검색을 진행해주세요.")

# -------------------------------
# 10. 일반 대화탭: 자유 토론/의견
# -------------------------------
with tab_chat:
    st.subheader("자유 의견/토론 (도서, 문학, 감정 등)")
    user_chat = st.chat_input("자유롭게 의견을 남겨보세요!")
    if user_chat:
        st.session_state.messages_chat.append(("user", user_chat))
        # AI는 최근 도서 메타데이터, 키워드 일부만 참고
        context = ""
        if st.session_state.book_metadata:
            last_book = list(st.session_state.book_metadata.values())[-1]
            context = f"참고 도서 키워드: {last_book['ai_metadata'][:200]}"
        prompt = f"""
        사용자가 남긴 의견/질문: {user_chat}
        {context}
        자유로운 문학 토론, 감정 공유, 다양한 관점 제시를 부탁해.
        """
        model = genai.GenerativeModel("gemini-pro")
        response = model.generate_content(prompt)
        st.session_state.messages_chat.append(("ai", response.text))
        st.chat_message("assistant").write(response.text)

    # 대화 히스토리
    for role, msg in st.session_state.messages_chat:
        st.chat_message("user" if role == "user" else "assistant").write(msg)

# -------------------------------
# 11. 피드백 분석 및 통계
# -------------------------------
st.sidebar.title("📊 피드백/로그 통계")
if st.sidebar.button("피드백 통계 보기"):
    for (book_title, meta_type), fb_list in st.session_state.feedback.items():
        st.sidebar.write(f"도서: {book_title} / 항목: {meta_type} / 피드백 수: {len(fb_list)}")
        for fb in fb_list:
            st.sidebar.write(f"- {fb}")

# -------------------------------
# 12. 안내 및 유의사항
# -------------------------------
st.sidebar.info("""
- 크롤링은 각 플랫폼의 robots.txt 및 저작권 정책을 준수해야 합니다.
- AI 답변은 도서 내 직접 인용, 키워드 기반 일관성, 피드백 반영을 지향합니다.
- 실제 서비스 적용 시, 데이터베이스와 연동 및 로그/피드백 분석 고도화가 필요합니다.
""")
