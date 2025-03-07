import yfinance as yf
import pandas as pd
import numpy as np
import json
import time
from concurrent.futures import ThreadPoolExecutor

# ✅ KOSPI/KOSDAQ 전체 종목 리스트 자동 가져오기
def get_korea_stock_list():
    """KRX 상장 종목 리스트 가져오기"""
    try:
        url = "https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13"
        stock_list = pd.read_html(url, encoding="euc-kr")[0]

        stock_list = stock_list[["종목코드", "회사명"]]
        stock_list["종목코드"] = stock_list["종목코드"].astype(str).str.zfill(6) + ".KS"  # KOSPI/KOSDAQ 변환
        return stock_list["종목코드"].tolist()
    except Exception as e:
        print(f"❌ KRX 종목 리스트 가져오기 실패: {e}")
        return []

# ✅ 테스트를 위해 한 종목만 사용
# STOCK_LIST = ["057030.KS"]
STOCK_LIST = get_korea_stock_list()

def fetch_multiple_stock_data(stock_codes, max_retries=3):
    """yfinance에서 여러 종목 데이터를 한 번에 가져오는 함수 (Rate Limit 대응)"""
    retries = 0
    while retries < max_retries:
        try:
            df = yf.download(stock_codes, period="60d", progress=False, group_by="ticker")
            if df.empty:
                print("⛔ 가져온 데이터가 없습니다. (yfinance API 문제 또는 종목 코드 오류)")
                return None
            return df
        except yf.YFRateLimitError:
            wait_time = (retries + 1) * 10  # 재시도할 때마다 10초씩 증가
            print(f"⏳ Rate Limit 도달. {wait_time}초 후 재시도... ({retries + 1}/{max_retries})")
            time.sleep(wait_time)
            retries += 1
    print("🚨 최대로 재시도했으나 실패. Yahoo Finance 요청 제한 초과.")
    return None

def check_conditions(df, stock_code):
    """조건을 만족하는지 확인하는 함수"""
    try:
        stock_df = df[stock_code]

        # ✅ 데이터 개수 확인 (최소 20개 이상 필요)
        if stock_df.empty or len(stock_df) < 20:
            print(f"❌ {stock_code}: 데이터 개수 부족 (현재 {len(stock_df)}개)")
            return None

        # ✅ 이동평균선 계산
        stock_df["5_MA"] = stock_df["Close"].rolling(window=5).mean()
        stock_df["20_MA"] = stock_df["Close"].rolling(window=20).mean()
        stock_df["Volume_MA5"] = stock_df["Volume"].rolling(window=5).mean()

        # ✅ NaN이 포함된 행 제거
        stock_df = stock_df.dropna(subset=["5_MA", "20_MA", "Volume_MA5"])

        # ✅ 데이터 개수 확인 (NaN 제거 후에도 최소 20개 이상 필요)
        if stock_df.empty or len(stock_df) < 20:
            print(f"❌ {stock_code}: NaN 제거 후 데이터 부족 (현재 {len(stock_df)}개)")
            return None

        # ✅ 골든크로스 확인 (15일 내 5이평이 20이평을 뚫은 경우)
        golden_cross = False
        for i in range(1, min(16, len(stock_df) - 1)):  # 데이터 개수 부족 방지
            prev_5ma = stock_df["5_MA"].iloc[-i - 1]
            prev_20ma = stock_df["20_MA"].iloc[-i - 1]
            curr_5ma = stock_df["5_MA"].iloc[-i]
            curr_20ma = stock_df["20_MA"].iloc[-i]

            if prev_5ma < prev_20ma and curr_5ma > curr_20ma:
                golden_cross = True
                break

        if not golden_cross:
            print(f"❌ {stock_code}: 15일 이내 골든크로스 없음")
            return None

        # ✅ 20일 이동평균선이 상승 중인지 확인
        if stock_df["20_MA"].iloc[-1] <= stock_df["20_MA"].iloc[-2]:
            print(f"❌ {stock_code}: 20일 이동평균이 하락 중")
            return None

        print(f"✅ {stock_code}: 조건 충족 (골든크로스 발생 & 20이평 상승)")

        return {"stock_code": stock_code, "price": stock_df["20_MA"].iloc[-1]}  
    except Exception as e:
        print(f"⛔ {stock_code} 데이터 처리 중 오류 발생: {e}")
        return None

def filter_stocks():
    """조건을 만족하는 종목을 필터링하여 저장"""
    filtered_stocks = []

    # ✅ ThreadPoolExecutor를 사용하여 병렬 처리
    batch_size = 20  # 한 번에 가져올 종목 개수 (기존 50 → 20)
    stock_batches = [STOCK_LIST[i:i + batch_size] for i in range(0, len(STOCK_LIST), batch_size)]

    with ThreadPoolExecutor(max_workers=3) as executor:  # ✅ max_workers=3으로 줄임
        for batch in stock_batches:
            df = fetch_multiple_stock_data(batch)
            
            if df is None:  # ✅ 요청 실패 시 건너뛰기
                continue

            for stock_code in batch:
                if stock_code not in df:
                    continue  # 데이터가 없는 종목 건너뛰기
                
                stock_info = check_conditions(df, stock_code)
                if stock_info:
                    filtered_stocks.append(stock_info)

            # ✅ 요청 간격을 두어 Rate Limit 방지 (1초 대기)
            time.sleep(1)

    # ✅ JSON 파일로 저장
    with open("filtered_stocks.json", "w", encoding="utf-8") as f:
        json.dump({"stocks": filtered_stocks}, f, indent=4, ensure_ascii=False)

    print(f"✅ {len(filtered_stocks)}개 종목이 조건을 만족했습니다. (filtered_stocks.json 저장 완료)")

if __name__ == "__main__":
    filter_stocks()