import json
import os
import time
from datetime import datetime
from PyQt5.QAxContainer import QAxWidget
from PyQt5.QtWidgets import QApplication
import sys

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
        self.requesting_stock = stock_code  # 현재 요청 중인 종목 저장
        self.data_received = False

        # 최초 요청
        print(f"📢 {stock_code} 데이터 요청 시작...")
        self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "종목코드", stock_code)
        self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "기준일자", today)
        self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "수정주가구분", "1")
        self.kiwoom.dynamicCall("CommRqData(QString, QString, int, QString)", "주식일봉차트조회", "OPT10081", 0, "0101")

        # 데이터 수신 완료될 때까지 대기
        while not self.data_received:
            self.app.processEvents()
        
        self.data_received = False  # 다음 요청을 위해 초기화

        # 데이터 저장
        if self.stock_data:
            os.makedirs("stock_data", exist_ok=True)
            with open(f"stock_data/{stock_code}.json", "w", encoding="utf-8") as f:
                json.dump(self.stock_data, f, indent=4, ensure_ascii=False)
            print(f"✅ {stock_code} 데이터 저장 완료 ({len(self.stock_data)}일)")

    def on_receive_tr_data(self, screen_no, rqname, trcode, recordname, prev_next, data_len, err_code, msg1, msg2):
        """TR 데이터 수신 이벤트"""
        if rqname == "주식일봉차트조회":
            count = self.kiwoom.dynamicCall("GetRepeatCnt(QString, QString)", trcode, rqname)
            print(f"📊 {self.requesting_stock}: {count}개 데이터 수신 중...")

            for i in range(count):
                date = self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, i, "일자").strip()
                close_price = self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, i, "현재가").strip()
                volume = self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, i, "거래량").strip()

                close_price = abs(int(close_price))  # 음수 변환 방지
                volume = int(volume)

                self.stock_data.append({"date": date, "close": close_price, "volume": volume})

            # 60일 데이터가 확보되지 않았으면 추가 요청 (prev_next = 2)
            if len(self.stock_data) < 60 and prev_next == "2":
                time.sleep(0.5)  # 요청 간격 유지
                print(f"🔄 {self.requesting_stock}: 추가 데이터 요청...")
                self.kiwoom.dynamicCall("CommRqData(QString, QString, int, QString)", "주식일봉차트조회", "OPT10081", 2, "0101")
            else:
                self.data_received = True  # 모든 데이터 수신 완료

    def run(self):
        self.app.exec_()


if __name__ == "__main__":
    kiwoom = Kiwoom()
    kiwoom.login()

    # ✅ 테스트 종목 (삼성전자)
    kiwoom.get_stock_data("005930")

    print("🎯 모든 데이터 저장 완료")
