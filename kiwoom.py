import sys
import json
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout,
    QWidget, QTabWidget, QTextEdit, QTableWidget, QTableWidgetItem, QComboBox
)
from PyQt5.QtGui import QFont
from PyQt5.QAxContainer import QAxWidget
from PyQt5.QtCore import QTimer

class KiwoomUI(QMainWindow):
    RQNAME_DAILY_CHART = "주식일봉차트조회"
    
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Kiwoom 자동매매 프로그램")
        self.setGeometry(100, 100, 800, 500)

        # Kiwoom API 객체 생성
        self.kiwoom = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")
        self.kiwoom.OnEventConnect.connect(self.on_event_connect)

        # 데이터 로드
        self.candidates_stocks = []
        self.owned_stocks = set()

        # 탭 위젯 추가
        self.tabs = QTabWidget(self)
        self.setCentralWidget(self.tabs)

        # 탭 1: 로그인
        self.login_tab = QWidget()
        self.tabs.addTab(self.login_tab, "로그인")

        # 탭 2: 계좌정보
        self.account_tab = QWidget()
        self.tabs.addTab(self.account_tab, "계좌정보")

        # 탭 3: 후보군 리스트
        self.candidates_tab = QWidget()
        self.tabs.addTab(self.candidates_tab, "후보군 리스트")

        # UI 설정
        self.setup_login_ui()
        self.setup_account_ui()
        self.setup_candidates_tab_ui()

        # 실시간 업데이트 타이머 설정 (5초마다 실행)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_stock_prices)
        self.timer.start(5000)

        # ✅ 후보군 데이터 갱신
        self.refresh_candidate_stocks()
        
    def setup_candidates_tab_ui(self):
        """후보군 리스트 UI 설정"""
        layout = QVBoxLayout()

        # 종목 리스트 테이블
        self.candidates_table = QTableWidget()
        self.candidates_table.setColumnCount(5)  # 종목코드, 현재가, 20이평, 차이(금액), 차이(%)
        self.candidates_table.setHorizontalHeaderLabels(["종목코드", "현재가", "20이평", "차이(금액)", "차이(%)"])
        layout.addWidget(self.candidates_table)

        # 후보군 업데이트 버튼
        self.update_candidates_button = QPushButton("후보군 업데이트")
        self.update_candidates_button.clicked.connect(self.refresh_candidate_stocks)
        layout.addWidget(self.update_candidates_button)

        self.candidates_tab.setLayout(layout)

        # 초기 데이터 로드
        self.load_candidates_list()

    def load_candidates_list(self):
        """filtered_candidates.json에서 종목을 불러와서 보유 종목을 제외하고 표시"""
        try:
            with open("filtered_candidates.json", "r", encoding="utf-8") as file:
                data = json.load(file)
                all_stocks = data.get("stocks", [])

            # 보유 종목 조회
            self.get_holdings()

            # 보유 종목 제외
            self.candidates_stocks = [s for s in all_stocks if s["stock_code"] not in self.owned_stocks]

            # 테이블에 추가
            self.candidates_table.setRowCount(len(self.candidates_stocks))
            for row, stock in enumerate(self.candidates_stocks):
                self.candidates_table.setItem(row, 0, QTableWidgetItem(stock["stock_code"]))
                self.candidates_table.setItem(row, 1, QTableWidgetItem("-"))  # 현재가 (실시간 업데이트 예정)
                self.candidates_table.setItem(row, 2, QTableWidgetItem(str(round(stock["price"], 2))))  # 20이평
                self.candidates_table.setItem(row, 3, QTableWidgetItem("-"))  # 차이 (금액)
                self.candidates_table.setItem(row, 4, QTableWidgetItem("-"))  # 차이 (%)

        except FileNotFoundError:
            self.candidates_stocks = []
            print("❌ filtered_candidates.json 파일을 찾을 수 없습니다.")

    def update_stock_prices(self):
        """주기적으로 현재가를 가져와서 테이블 업데이트"""
        for row, stock in enumerate(self.candidates_stocks):
            stock_code = stock["stock_code"]

            # 현재가 가져오기
            current_price = self.kiwoom.dynamicCall("GetMasterLastPrice(QString)", stock_code).strip()
            if not current_price:
                continue
            current_price = int(current_price.replace(",", ""))

            # 20이평 가격 가져오기
            ma20_price = stock["price"]

            # 차이 계산
            diff_amount = current_price - ma20_price
            diff_percent = (diff_amount / ma20_price) * 100

            # 테이블 업데이트
            self.candidates_table.setItem(row, 1, QTableWidgetItem(str(current_price)))
            self.candidates_table.setItem(row, 3, QTableWidgetItem(str(diff_amount)))
            self.candidates_table.setItem(row, 4, QTableWidgetItem(f"{diff_percent:.2f}%"))

    def refresh_candidate_stocks(self):
        """후보군 데이터 갱신"""
        filter_candidates()
        self.load_candidates_list()


    def get_holdings(self):
        """현재 보유 종목을 가져와서 owned_stocks에 저장"""
        account_number = self.account_combo.currentText()
        if not account_number:
            return

        self.owned_stocks.clear()

        stock_count = self.kiwoom.dynamicCall("GetRepeatCnt(QString, QString)", "OPW00018", "보유종목조회")
        for i in range(stock_count):
            stock_code = self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", "OPW00018", "보유종목조회", i, "종목코드").strip()
            self.owned_stocks.add(stock_code)

    def setup_buy_tab_ui(self):
        """매수 후보군 UI 설정"""
        layout = QVBoxLayout()

        # 검색 버튼
        self.search_button = QPushButton("매수 조건 검색")
        self.search_button.clicked.connect(self.start_buy_search)
        layout.addWidget(self.search_button)

        # 결과 출력창
        self.result_text = QTextEdit(self)
        self.result_text.setReadOnly(True)
        layout.addWidget(self.result_text)

        self.buy_tab.setLayout(layout)

    def load_candidate_stocks(self):
        """매수 후보군 로드"""
        try:
            with open("filtered_stocks.json", "r", encoding="utf-8") as file:
                data = json.load(file)
                return data.get("stocks", [])
        except FileNotFoundError:
            return []

    def setup_buy_tap_ui(self):
        """ 매수 후보군 ui settings """
        layout = QVBoxLayout()

        # 검색버튼
        self.search_button = QPushButton("매수 조건 검색")
        self.search_button.clicked.connect(self.start_buy_search)
        layout.addWidget(self.search_button)

        # 결과 출력창
        self.result_text = QTextEdit(self)
        self.result_text.setReadOnly(True)
        layout.addWidget(self.result_text)
        
        self.buy_tab.setLayout(layout)
        
        
    def start_buy_search(self):
        """매수 후보 검색 실행"""
        self.filtered_stocks = []
        self.current_stock_index = 0
        self.result_text.setText("검색 중...")

        if not self.candidates_stocks:
            self.result_text.setText("저장된 후보 종목이 없습니다.")
            return

        self.request_stock_data()

    def request_stock_data(self):
        """현재 종목의 일봉 데이터 요청"""
        if self.current_stock_index >= len(self.candidates_stocks):
            self.result_text.setText("\n".join(self.filtered_stocks) if self.filtered_stocks else "조건에 맞는 종목 없음")
            return

        stock_code = self.candidates_stocks[self.current_stock_index]
        self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "종목코드", stock_code)
        self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "기준일자", "20240301")  # 최근 일봉 기준
        self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "수정주가구분", "1")
        self.kiwoom.dynamicCall("CommRqData(QString, QString, int, QString)", self.RQNAME_DAILY_CHART, "OPT10081", 0, "0101")

    def setup_login_ui(self):
        """로그인/로그아웃 UI 설정"""
        layout = QVBoxLayout()

        # 로그인 상태 레이블
        self.status_label = QLabel("로그인 상태: 미접속")
        self.status_label.setFont(QFont("Arial", 12))
        layout.addWidget(self.status_label)

        # 로그인 버튼
        self.login_button = QPushButton("로그인")
        self.login_button.setFont(QFont("Arial", 12))
        self.login_button.clicked.connect(self.kiwoom_login)
        layout.addWidget(self.login_button)

        # 로그아웃 버튼
        self.logout_button = QPushButton("로그아웃")
        self.logout_button.setFont(QFont("Arial", 12))
        self.logout_button.setEnabled(False)  # 처음에는 비활성화
        self.logout_button.clicked.connect(self.kiwoom_logout)
        layout.addWidget(self.logout_button)

        self.login_tab.setLayout(layout)

    def setup_account_ui(self):
        """계좌정보 UI 설정"""
        layout = QVBoxLayout()

        # 계좌 선택 드롭다운
        self.account_combo = QComboBox(self)
        self.account_combo.setFont(QFont("Arial", 12))
        layout.addWidget(self.account_combo)

        # 선택된 계좌번호 표시
        self.account_label = QLabel("선택된 계좌: -")
        self.account_label.setFont(QFont("Arial", 12))
        layout.addWidget(self.account_label)

        # 계좌 선택 버튼
        self.select_account_button = QPushButton("계좌 선택")
        self.select_account_button.setFont(QFont("Arial", 12))
        self.select_account_button.clicked.connect(self.select_account)
        layout.addWidget(self.select_account_button)

        # 보유 종목 조회 버튼
        self.get_stocks_button = QPushButton("보유 종목 조회")
        self.get_stocks_button.setFont(QFont("Arial", 12))
        self.get_stocks_button.clicked.connect(self.get_holdings)
        layout.addWidget(self.get_stocks_button)

        # 보유 종목 리스트 출력
        self.stock_text = QTextEdit(self)
        self.stock_text.setFont(QFont("Arial", 10))
        self.stock_text.setReadOnly(True)
        layout.addWidget(self.stock_text)

        self.account_tab.setLayout(layout)

    def kiwoom_login(self):
        """로그인 요청"""
        self.kiwoom.dynamicCall("CommConnect()")

    def kiwoom_logout(self):
        """로그아웃 요청 (Kiwoom API에서는 직접 로그아웃이 불가능)"""
        QMessageBox.information(self, "로그아웃", "Kiwoom OpenAPI는 강제 로그아웃 기능이 없습니다.\n프로그램을 종료 후 다시 실행하세요.")

    def on_event_connect(self, err_code):
        """로그인 이벤트 처리"""
        if err_code == 0:
            self.status_label.setText("로그인 상태: 성공")
            self.login_button.setEnabled(False)
            self.logout_button.setEnabled(True)
            self.get_account_info()
        else:
            self.status_label.setText(f"로그인 상태: 실패 (에러코드 {err_code})")

    def get_account_info(self):
        """로그인 후 계좌번호 가져오기"""
        account_list = self.kiwoom.dynamicCall("GetLoginInfo(QString)", "ACCNO")
        accounts = account_list.strip().split(';')[:-1]  # 마지막 빈 요소 제거

        if accounts:
            self.account_combo.clear()
            self.account_combo.addItems(accounts)  # 계좌 목록을 드롭다운에 추가
            self.account_combo.setCurrentIndex(0)  # 첫 번째 계좌 선택
            self.account_label.setText(f"선택된 계좌: {accounts[0]}")
        else:
            self.account_label.setText("계좌번호를 가져오지 못했습니다.")

    def select_account(self):
        """사용자가 계좌를 선택하면 레이블 업데이트"""
        selected_account = self.account_combo.currentText()
        self.account_label.setText(f"선택된 계좌: {selected_account}")


    def on_receive_tr_data(self, screen_no, rqname, trcode, recordname, prev_next, data_len, err_code, msg1, msg2):
        """TR 데이터 수신 이벤트"""
        if rqname == "보유종목조회":
            stock_count = self.kiwoom.dynamicCall("GetRepeatCnt(QString, QString)", trcode, rqname)
            stock_info = ""

            for i in range(stock_count):
                stock_name = self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, i, "종목명").strip()
                quantity = self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, i, "보유수량").strip()
                buy_price = self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, i, "매입가").strip()

                stock_info += f"종목명: {stock_name}, 수량: {quantity}, 매입가: {buy_price}\n"

            self.stock_text.setText(stock_info if stock_info else "보유 종목 없음")
        
        if rqname == "주식일봉차트조회":
            count = 30  # 최근 30일 데이터 조회
            prices = []
            volumes = []

            for i in range(count):
                close_price = self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, i, "현재가").strip()
                volume = self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, i, "거래량").strip()
                
                close_price = abs(int(close_price))  # 음수 처리 방지
                volume = int(volume)

                prices.append(close_price)
                volumes.append(volume)

            if len(prices) < 20:
                self.current_stock_index += 1
                self.request_stock_data()
                return

            # 이동평균선 계산
            prices.reverse()
            volumes.reverse()
            ma5_list = np.convolve(prices, np.ones(5)/5, mode='valid')
            ma20_list = np.convolve(prices, np.ones(20)/20, mode='valid')

            # 최근 30일 평균 거래량
            avg_volume_30 = np.mean(volumes)

            # 조건 확인
            last_ma5 = ma5_list[-1]
            prev_ma5 = ma5_list[-2]
            last_ma20 = ma20_list[-1]
            prev_ma20 = ma20_list[-2]
            prev_prev_ma5 = ma5_list[-3]

            is_price_above_5000 = prices[-1] >= 5000
            is_volume_above_100k = avg_volume_30 >= 100000
            is_ma5_crossed_below_ma20 = prev_prev_ma5 > prev_ma20 and last_ma5 < last_ma20
            is_ma20_upward = last_ma20 > prev_ma20

            if is_price_above_5000 and is_volume_above_100k and is_ma5_crossed_below_ma20 and is_ma20_upward:
                stock_code = self.all_stock_codes[self.current_stock_index]
                self.filtered_stocks.append(f"{stock_code}: 현재가 {prices[-1]}, MA5 {last_ma5:.2f}, MA20 {last_ma20:.2f}")

            # 다음 종목 요청
            self.current_stock_index += 1
            self.request_stock_data()
            
    def process_daily_chart_data(self, trcode, rqname):
        """일봉 데이터 수신 후 매수 조건 확인"""
        count = 20 # 최근 20일 데이터 조회
        prices = []
        
        for i in range(count):
            close_price = self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, i, "현재가").strip()
            close_price = abs(int(close_price)) # 음수 처리 방지
            prices.append(close_price)
            
        if len(prices) < 20:
            self.current_stock_index += 1
            self.request_stock_data()
            return
        
        prices.reverse()
        
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

            # 최근 15일 내 5이평이 20이평을 돌파한 경우 필터링
            golden_cross = False
            for i in range(1, min(16, len(df))):
                if df["5_MA"].iloc[-i - 1] < df["20_MA"].iloc[-i - 1] and df["5_MA"].iloc[-i] > df["20_MA"].iloc[-i]:
                    golden_cross = True
                    break
            
            if not golden_cross:
                continue

            # 20일 이동평균선이 상승 중인지 확인
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
    app = QApplication(sys.argv)
    window = KiwoomUI()
    window.show()
    sys.exit(app.exec_())
