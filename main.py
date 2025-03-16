from fastapi import FastAPI, HTTPException, Query
import requests
import os
import logging
import re
import html
from typing import Optional
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import openai

# ✅ 환경 변수 로드 (.env 파일 사용)
load_dotenv()

# ✅ FastAPI 앱 생성
app = FastAPI()

# ✅ 네이버 API & GPT-4o API 키 가져오기
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ✅ HTML 태그 및 엔터티 제거 함수
def clean_html(raw_html):
    text = html.unescape(raw_html)  # HTML 엔터티 변환
    text = BeautifulSoup(text, "html.parser").get_text()  # 태그 제거
    text = re.sub(r'\s+', ' ', text).strip()  # 불필요한 공백 정리
    return text

# ✅ 네이버 뉴스 검색
def get_naver_news(query):
    url = f"https://openapi.naver.com/v1/search/news.json?query={query}&display=10&start=1&sort=date"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        news_items = response.json().get("items", [])
        cleaned_news = [
            {
                "title": clean_html(item["title"]),
                "link": item["link"],
                "summary": clean_html(item["description"]),
            }
            for item in news_items
        ]
        return cleaned_news
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"네이버 뉴스 API 호출 실패: {str(e)}")

# ✅ GPT-4o를 사용한 뉴스 요약 또는 자체 답변 생성
def summarize_with_gpt(content):
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "뉴스 및 경제 정보를 요약하는 전문가입니다."},
                {"role": "user", "content": f"{content}에 대해 요약해줘."},
            ],
            temperature=0.3,
            max_tokens=100
        )
        return response.choices[0].message.content.strip()
    except openai.OpenAIError as e:
        return f"요약 실패: {str(e)}"

# ✅ 기본 엔드포인트
@app.get("/")
def home():
    return {"message": "Hello, FastAPI is running!"}

# ✅ 뉴스 검색 API
@app.get("/custom_api")
def fetch_news_data(query: Optional[str] = Query(default=None, description="검색어 입력")):
    if not query:
        return {"message": "검색어를 입력하세요. 예: /custom_api?query=삼성전자"}

    # "재현"이 포함된 경우 → 네이버 뉴스 검색 + GPT-4o 요약
    if "재현" in query:
        query = query.replace("재현", "").strip()
        news_items = get_naver_news(query)
        summarized_news = [
            {
                "title": item["title"],
                "link": item["link"],
                "summary": summarize_with_gpt(f"제목: {item['title']}\n내용: {item['summary']}"),
            }
            for item in news_items
        ]
        return {"query": query, "summarized_news": summarized_news}

    # "재현"이 없는 경우 → 네이버 API 호출 없이 GPT-4o 자체 답변 생성
    else:
        gpt_response = summarize_with_gpt(f"{query}에 대한 최신 뉴스를 요약해줘.")
        return {"query": query, "gpt_summary": gpt_response}
