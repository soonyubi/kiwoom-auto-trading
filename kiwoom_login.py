import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout,
    QWidget, QTabWidget, QMessageBox, QComboBox, QTextEdit
)
from PyQt5.QtGui import QFont
from PyQt5.QAxContainer import QAxWidget
import numpy as np


class KiwoomUI(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Kiwoom 자동매매 프로그램")
        self.setGeometry(100, 100, 600, 500)  # 창 크기 확대

        # Kiwoom API 객체 생성
        self.kiwoom = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")
        self.kiwoom.OnEventConnect.connect(self.on_event_connect)
        self.kiwoom.OnReceiveTrData.connect(self.on_receive_tr_data)  # TR 데이터 수신 이벤트 연결

        # 탭 위젯 추가
        self.tabs = QTabWidget(self)
        self.setCentralWidget(self.tabs)

        # 탭 1: 로그인 탭
        self.login_tab = QWidget()
        self.tabs.addTab(self.login_tab, "로그인")

        # 탭 2: 계좌정보 및 보유 종목 탭
        self.account_tab = QWidget()
        self.tabs.addTab(self.account_tab, "계좌정보")

        # # 조건검색 탭
        # self.search_tab = QWidget()
        # self.tabs.addTab(self.search_tab, "조건검색")

        # 탭 3 : 매수 후보군
        self.buy_tab = QWidget()
        self.tabs.addTab(self.buy_tab, "매수 후보군")

        

        self.candidates_stocks = self.load_candidate_stocks()
        self.current_stock_index = 0
        self.filtered_stocks = []


        # 조건에 맞는 종목 저장
        self.filtered_stocks = []
        self.all_stock_codes = ["005930", "035420", "068270"]  # 삼성전자, NAVER, 셀트리온 (예제 종목)
        self.current_stock_index = 0

        # UI 설정
        self.setup_login_ui()
        self.setup_account_ui()
        self.setup_search_ui()
        self.setup_buy_tap_ui()

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

    def setup_search_ui(self):
        """조건검색 UI 설정"""
        layout = QVBoxLayout()

        # 검색 버튼
        self.search_button = QPushButton("조건 검색 실행")
        self.search_button.clicked.connect(self.start_search)
        layout.addWidget(self.search_button)

        # 결과 출력창
        self.result_text = QTextEdit(self)
        self.result_text.setReadOnly(True)
        layout.addWidget(self.result_text)

        self.search_tab.setLayout(layout)

    def start_search(self):
        """검색 시작"""
        self.filtered_stocks = []
        self.current_stock_index = 0
        self.result_text.setText("검색 중...")

        self.request_stock_data()

    def request_stock_data(self):
        """현재 종목의 일봉 데이터 요청"""
        if self.current_stock_index >= len(self.all_stock_codes):
            self.result_text.setText("\n".join(self.filtered_stocks) if self.filtered_stocks else "조건에 맞는 종목 없음")
            return

        stock_code = self.all_stock_codes[self.current_stock_index]
        self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "종목코드", stock_code)
        self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "기준일자", "20240301")  # 최근 일봉 기준
        self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "수정주가구분", "1")
        self.kiwoom.dynamicCall("CommRqData(QString, QString, int, QString)", "주식일봉차트조회", "OPT10081", 0, "0101")

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

    def get_holdings(self):
        """선택된 계좌의 보유 종목 조회 (TR: OPW00018)"""
        account_number = self.account_combo.currentText()

        if not account_number:
            QMessageBox.warning(self, "경고", "계좌를 선택하세요.")
            return

        self.stock_text.setText("보유 종목 조회 중...")
        
        self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "계좌번호", account_number)
        self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "비밀번호", "0000")
        self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "비밀번호입력매체구분", "00")
        self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "조회구분", "2")
        self.kiwoom.dynamicCall("CommRqData(QString, QString, int, QString)", "보유종목조회", "OPW00018", 0, "0101")

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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = KiwoomUI()
    window.show()
    sys.exit(app.exec_())
