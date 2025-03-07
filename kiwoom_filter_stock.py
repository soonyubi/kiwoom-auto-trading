import sys
import json
import time
import pandas as pd
from PyQt5.QAxContainer import QAxWidget
from PyQt5.QtWidgets import QApplication
from datetime import datetime
import os 

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

        

        # ✅ stock_data 폴더가 없으면 생성
        os.makedirs("stock_data", exist_ok=True)


        # ✅ 최초 요청
        print(f"📢 {stock_code} 데이터 요청 시작...")
        self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "종목코드", stock_code)
        self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "기준일자", today)
        self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "수정주가구분", "1")
        self.kiwoom.dynamicCall("CommRqData(QString, QString, int, QString)", "주식일봉차트조회", "OPT10081", 0, "0101")

        # ✅ 데이터 수신 대기
        while not self.data_received:
            self.app.processEvents()

        self.data_received = False  # 다음 요청을 위해 초기화

        # ✅ 데이터 저장
        if self.stock_data:
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
                open_price = self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, i, "시가").strip()
                high_price = self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, i, "고가").strip()
                low_price = self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, i, "저가").strip()
                close_price = self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, i, "현재가").strip()
                volume = self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, i, "거래량").strip()

                open_price = abs(int(open_price))  
                high_price = abs(int(high_price))  
                low_price = abs(int(low_price))  
                close_price = abs(int(close_price))  
                volume = int(volume)

                self.stock_data.append({
                    "date": date, 
                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "close": close_price, 
                    "volume": volume
                })



            # ✅ 60개 이상 데이터를 받았으면 중단
            if len(self.stock_data) >= 60:
                self.data_received = True
                return

            # ✅ 60개 미만이고 추가 데이터가 있으면 요청 (prev_next = 2)
            if prev_next == "2":
                time.sleep(0.5)  # 요청 간격 유지
                print(f"🔄 {self.requesting_stock}: 추가 데이터 요청...")
                self.kiwoom.dynamicCall("CommRqData(QString, QString, int, QString)", "주식일봉차트조회", "OPT10081", 2, "0101")
            else:
                self.data_received = True  # 모든 데이터 수신 완료

    def run(self):
        self.app.exec_()


def get_korea_stock_list():
    """KRX 상장 종목 리스트 가져오기"""
    try:
        url = "https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13"
        stock_list = pd.read_html(url, encoding="euc-kr")[0]

        stock_list = stock_list[["종목코드", "회사명"]]
        stock_list["종목코드"] = stock_list["종목코드"].astype(str).str.zfill(6)  # 종목코드 6자리 변환
        return stock_list["종목코드"].tolist()
    except Exception as e:
        print(f"❌ KRX 종목 리스트 가져오기 실패: {e}")
        return []


def save_stock_list():
    """전체 종목 리스트를 JSON 파일에 저장"""
    stock_list = get_korea_stock_list()
    with open("all_stock_codes.json", "w", encoding="utf-8") as f:
        json.dump(stock_list, f, indent=4, ensure_ascii=False)
    print(f"✅ 전체 종목 코드 저장 완료 ({len(stock_list)}개)")


def load_stock_list():
    """JSON 파일에서 종목 리스트 불러오기"""
    try:
        with open("all_stock_codes.json", "r", encoding="utf-8") as f:
            stock_list = json.load(f)
        return stock_list
    except FileNotFoundError:
        print("❌ 종목 리스트 파일을 찾을 수 없습니다. 새로 생성합니다.")
        save_stock_list()
        return load_stock_list()


if __name__ == "__main__":
    # ✅ 종목 리스트 저장 (최초 실행 시)
    save_stock_list()

    # ✅ 키움 API 초기화 및 로그인
    kiwoom = Kiwoom()
    kiwoom.login()

    # ✅ 전체 종목 리스트 불러오기
    stock_list = load_stock_list()

    # ✅ 60일간의 데이터를 각 종목별로 가져오기
    for stock_code in stock_list[:10]:  # 테스트용 1개 종목만 실행
        kiwoom.get_stock_data(stock_code)
        time.sleep(1)  # 요청 간격 조절 (API 제한 방지)

    print("🎯 모든 데이터 저장 완료")
