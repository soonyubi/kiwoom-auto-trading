import sys
import json
import numpy as np
import pandas as pd
from PyQt5.QAxContainer import QAxWidget
from PyQt5.QtWidgets import QApplication
from datetime import datetime
import os
import time

class Kiwoom:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.kiwoom = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")
        self.kiwoom.OnEventConnect.connect(self.on_event_connect)
        self.kiwoom.OnReceiveTrData.connect(self.on_receive_tr_data)
        self.connected = False
        self.data_received = False
        self.stock_data = []
        self.requesting_stock = None

    def login(self):
        """키움증권 API 로그인"""
        self.kiwoom.dynamicCall("CommConnect()")
        while not self.connected:
            self.app.processEvents()
        print("✅ 로그인 완료")

    def on_event_connect(self, err_code):
        """로그인 이벤트 처리"""
        if err_code == 0:
            print("🔗 연결 성공")
            self.connected = True
        else:
            print(f"❌ 연결 실패 (에러 코드: {err_code})")

    def get_stock_data(self, stock_code, days=60):
        """키움 API를 활용해 최근 60일간의 일봉 데이터 조회"""
        today = datetime.today().strftime("%Y%m%d")

        self.stock_data = []
        self.requesting_stock = stock_code
        self.data_received = False

        os.makedirs("stock_data", exist_ok=True)

        # ✅ 최초 요청
        print(f"📢 {stock_code} 데이터 요청 시작...")
        self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "종목코드", stock_code)
        self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "기준일자", today)
        self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "수정주가구분", "1")
        self.kiwoom.dynamicCall("CommRqData(QString, QString, int, QString)", "주식일봉차트조회", "OPT10081", 0, "0101")

        while not self.data_received:
            self.app.processEvents()
        self.data_received = False  # 다음 요청을 위해 초기화

        # ✅ 데이터 저장
        if len(self.stock_data) >= 60:
            with open(f"stock_data/{stock_code}.json", "w", encoding="utf-8") as f:
                json.dump(self.stock_data[:60], f, indent=4, ensure_ascii=False)
            print(f"✅ {stock_code} 데이터 저장 완료 ({len(self.stock_data[:60])}일)")

    def on_receive_tr_data(self, screen_no, rqname, trcode, recordname, prev_next, data_len, err_code, msg1, msg2):
        """TR 데이터 수신 이벤트"""
        if rqname == "주식일봉차트조회":
            count = self.kiwoom.dynamicCall("GetRepeatCnt(QString, QString)", trcode, rqname)
            print(f"📊 {self.requesting_stock}: {count}개 데이터 수신 중...")

            for i in range(count):
                date = self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, i, "일자").strip()
                close_price = abs(int(self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, i, "현재가").strip()))
                volume = int(self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, i, "거래량").strip())

                self.stock_data.append({"date": date, "close": close_price, "volume": volume})

            if len(self.stock_data) >= 60:
                self.data_received = True
                return

            if prev_next == "2":
                self.kiwoom.dynamicCall("CommRqData(QString, QString, int, QString)", "주식일봉차트조회", "OPT10081", 2, "0101")
            else:
                self.data_received = True

    def run(self):
        self.app.exec_()


def filter_candidates():
    """매수 후보군 필터링"""
    filtered_candidates = []
    
    stock_list = json.load(open("all_stock_codes.json", "r", encoding="utf-8"))

    for stock_code in stock_list:
        try:
            with open(f"stock_data/{stock_code}.json", "r", encoding="utf-8") as f:
                stock_data = json.load(f)

            df = pd.DataFrame(stock_data).sort_values("date")
            df["5_MA"] = df["close"].rolling(window=5).mean()
            df["20_MA"] = df["close"].rolling(window=20).mean()
            df["Volume_MA5"] = df["volume"].rolling(window=5).mean()

            # 최근 15일 이내 골든크로스 발생 확인
            golden_cross = False
            for i in range(1, min(16, len(df))):
                if df["5_MA"].iloc[-i - 1] < df["20_MA"].iloc[-i - 1] and df["5_MA"].iloc[-i] > df["20_MA"].iloc[-i]:
                    golden_cross = True
                    break
            
            if not golden_cross:
                continue

            # 20일 이동평균선 상승 중인지 확인
            if df["20_MA"].iloc[-1] <= df["20_MA"].iloc[-15]:
                continue

            # 종가 기준 필터링
            last_close = df["close"].iloc[-1]
            avg_volume_5 = df["Volume_MA5"].iloc[-1]

            if 2000 <= last_close < 10000 and avg_volume_5 < 500000:
                continue
            if last_close >= 10000 and avg_volume_5 < 100000:
                continue

            filtered_candidates.append({"stock_code": stock_code, "price": df["20_MA"].iloc[-1]})

        except FileNotFoundError:
            continue

    # ✅ JSON 파일로 저장
    with open("filtered_candidates.json", "w", encoding="utf-8") as f:
        json.dump({"stocks": filtered_candidates}, f, indent=4, ensure_ascii=False)

    print(f"✅ {len(filtered_candidates)}개 종목이 조건을 만족했습니다. (filtered_candidates.json 저장 완료)")


if __name__ == "__main__":
    kiwoom = Kiwoom()
    kiwoom.login()

    stock_list = json.load(open("all_stock_codes.json", "r", encoding="utf-8"))

    for stock_code in stock_list[:100]:  # 테스트용 10개 종목 실행
        kiwoom.get_stock_data(stock_code)
        time.sleep(1)

    filter_candidates()