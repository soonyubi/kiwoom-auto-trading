import sys
import json
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout,
    QWidget, QTabWidget, QTextEdit, QTableWidget, QTableWidgetItem, QComboBox,
    QLineEdit, QSpinBox, QHBoxLayout, QDoubleSpinBox, QMessageBox
)
from PyQt5.QtGui import QFont, QColor
from PyQt5.QAxContainer import QAxWidget
from PyQt5.QtCore import QTimer
import pandas as pd


class AutoTrader:
    """자동 매매 기능을 담당하는 클래스"""
    def __init__(self, kiwoom, ui):
        self.kiwoom = kiwoom  # 키움 API 객체
        self.ui = ui  # UI 객체 참조
        self.auto_trade_timer = QTimer()  # ✅ 타이머를 미리 생성해둠
        self.auto_trade_timer.timeout.connect(self.execute_limited_buy_orders)
        self.pending_orders = {}  # 주문 대기 목록
        self.scheduled_orders = []  # 매수할 종목 리스트
        self.order_index = 0  # 현재 주문 진행 인덱스

    def start_auto_trade(self):
        """자동 매수 시작"""
        if self.auto_trade_timer.isActive():
            print("⚠️ 자동 매수가 이미 실행 중입니다.")
            return

        self.ui.auto_trade_button.setEnabled(False)  # 시작 버튼 비활성화
        self.ui.stop_trade_button.setEnabled(True)   # 중지 버튼 활성화
        print("✅ 자동 매수 시작")

        self.check_and_buy_stocks()  # ✅ 종목 선정 후 주문 리스트 업데이트
        self.auto_trade_timer.start(1000)  # ✅ 1초마다 주문 실행

    def stop_auto_trade(self):
        """자동 매수 중지"""
        if self.auto_trade_timer.isActive():
            self.auto_trade_timer.stop()
            print("🛑 자동 매수 종료됨")
        self.ui.auto_trade_button.setEnabled(True)  # 시작 버튼 활성화
        self.ui.stop_trade_button.setEnabled(False)  # 중지 버튼 비활성화

    def check_and_buy_stocks(self):
        """자동 매수 실행 (1초에 1개씩 실행)"""
        threshold = float(self.ui.threshold_input.text()) / 100
        buy_amount = int(self.ui.buy_amount_input.text())

        if not self.ui.account_manager.current_balance:
            print("🔄 잔고 정보가 없습니다. 잔고 조회 후 매수 실행")
            self.ui.account_manager.request_account_balance()
            return

        if self.ui.account_manager.current_balance < buy_amount:
            print(f"❌ 잔고 부족: {self.ui.account_manager.current_balance}원, 필요한 금액: {buy_amount}원")
            return

        stocks_to_buy = []

        for stock in self.ui.stock_data_manager.candidates_stocks:
            stock_code = stock["stock_code"]

            if stock_code in self.pending_orders:  # 이미 주문한 종목은 제외
                continue

            current_price = self.kiwoom.dynamicCall("GetMasterLastPrice(QString)", stock_code).strip()
            if not current_price:
                continue

            current_price = int(current_price.replace(",", ""))
            ma20_price = stock["price"]

            price_diff = abs((current_price - ma20_price) / ma20_price)

            if price_diff <= threshold:
                stocks_to_buy.append((stock_code, current_price, price_diff))

        # ✅ 절대값 차이가 작은 순으로 정렬
        stocks_to_buy.sort(key=lambda x: x[2])

        # ✅ 주문할 종목 리스트 업데이트
        self.scheduled_orders = stocks_to_buy
        self.order_index = 0

        if not self.scheduled_orders:
            print("🚫 매수할 종목이 없습니다. 자동 매수를 종료합니다.")
            self.stop_auto_trade()

    def execute_limited_buy_orders(self):
        """1초에 한 개씩 매수 주문 실행"""
        if not self.scheduled_orders or self.order_index >= len(self.scheduled_orders):
            print("🛑 더 이상 주문할 종목이 없습니다. 자동매수 종료")
            self.stop_auto_trade()
            return

        stock_code, price, _ = self.scheduled_orders[self.order_index]
        buy_amount = int(self.ui.buy_amount_input.text())

        order_id = self.place_buy_order(stock_code, price, buy_amount)

        if order_id == 0:
            print(f"📌 {stock_code} 매수 주문 완료. 주문 ID: {order_id}")
            self.pending_orders[stock_code] = order_id

        self.order_index += 1  # ✅ 다음 주문 대기

    def place_buy_order(self, stock_code, price, amount):
        """키움 OpenAPI를 통해 매수 주문 실행"""
        account_number = self.ui.account_combo.currentText()
        quantity = amount // price  # 구매 가능한 수량 계산

        if quantity < 1:
            print(f"❌ {stock_code}: 구매금액({amount})보다 주식의 가격({price})이 높습니다. 구매 실패 (수량: {quantity})")
            return None

        print(f"📌 {stock_code} 매수 주문 실행 ({quantity}주, 시장가) 총 매수 금액 : {price * quantity:,} 원")

        order_id = self.kiwoom.dynamicCall(
            "SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
            ["자동매수", "0101", account_number, 1, stock_code, quantity, 0, "03", ""]
        )

        if order_id == 0:
            print(f"✅ {stock_code} 주문 접수 성공 (주문 ID: {order_id})")
            self.pending_orders[stock_code] = order_id
            QTimer.singleShot(2000, self.ui.account_manager.request_account_balance)  # ✅ 주문 후 잔고 조회 요청 (2초 후 실행)
        else:
            print(f"❌ {stock_code} 주문 실패 (반환값: {order_id})")

        return order_id
    
class AccountManager:
    """계좌 정보를 관리하는 클래스"""
    def __init__(self, kiwoom, ui):
        self.kiwoom = kiwoom  # 키움 API 객체
        self.ui = ui  # UI 객체 참조
        self.current_balance = None  # 현재 잔고
        self.owned_stocks = set()
        
    def on_account_changed(self):
        """사용자가 계좌를 변경하면 해당 계좌의 보유 종목 조회"""
        selected_account = self.ui.account_combo.currentText()
        self.ui.account_label.setText(f"선택된 계좌: {selected_account}")
        
        # ✅ 선택된 계좌로 보유 종목 조회 실행
        self.get_holdings()
        
        self.ui.stock_data_manager.load_holdings_list()
        
    
    def get_holdings_from_tr(self, trcode, rqname):
        """TR 데이터를 이용해 보유 종목 정보를 가져옴"""
        try:
            stock_count = self.kiwoom.dynamicCall("GetRepeatCnt(QString, QString)", trcode, rqname)
            print(f"📥 보유 종목 조회 응답 수신: {stock_count}개 종목")

            holdings = []
            self.owned_stocks.clear()

            for i in range(stock_count):
                stock_code = self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, i, "종목코드").strip()
                stock_name = self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, i, "종목명").strip()
                quantity = self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, i, "보유수량").strip()
                buy_price = self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, i, "매입가").strip()

                holdings.append({"stock_name": stock_name, "quantity": quantity, "buy_price": buy_price, "stock_code": stock_code})

                self.owned_stocks.add(stock_code)
            return holdings  # 데이터 반환
        except Exception as e:
            print(f"❌ 보유 종목 조회 중 오류 발생: {e}")
            return []
        
    
    def get_holdings(self):
        """현재 보유 종목을 가져와서 owned_stocks에 저장"""
        account_number = self.ui.account_combo.currentText()
        if not account_number:
            print("❌ 계좌번호를 선택하세요.")
            return

        print(f"🔍 보유 종목 조회 요청 보냄... (계좌번호: {account_number})")

        try:
            self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "계좌번호", account_number)
            self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "비밀번호", "")
            self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "비밀번호입력매체구분", "00")
            self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "조회구분", "1")  # 1: 보유 종목 조회

            self.kiwoom.dynamicCall("CommRqData(QString, QString, int, QString)", "보유종목조회", "OPW00018", 0, "4000")
        except Exception as e:
            print(f"❌ 보유 종목 조회 중 오류 발생: {e}")

    def get_account_info(self):
        """로그인 후 계좌번호 가져오기"""
        account_list = self.kiwoom.dynamicCall("GetLoginInfo(QString)", "ACCNO")
        accounts = account_list.strip().split(';')[:-1]  # 마지막 빈 요소 제거

        if accounts:
            self.ui.account_combo.clear()
            self.ui.account_combo.addItems(accounts)  # 계좌 목록을 드롭다운에 추가
            self.ui.account_combo.setCurrentIndex(0)  # 첫 번째 계좌 선택
            self.ui.account_label.setText(f"선택된 계좌: {accounts[0]}")
            self.request_account_balance()  # 계좌 선택 후 잔고 조회
            self.get_holdings()
            self.ui.stock_data_manager.load_holdings_list()
        else:
            self.ui.account_label.setText("계좌번호를 가져오지 못했습니다.")

    def select_account(self):
        """사용자가 계좌를 선택하면 레이블 업데이트"""
        selected_account = self.ui.account_combo.currentText()
        self.ui.account_label.setText(f"선택된 계좌: {selected_account}")
        self.request_account_balance()
        self.get_holdings()

    def request_account_balance(self):
        """잔고 조회 요청"""
        account_number = self.ui.account_combo.currentText()
        
        if not account_number:
            print("❌ 계좌번호를 선택하세요.")
            return

        self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "계좌번호", account_number)
        self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "비밀번호", "")
        self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "비밀번호입력매체구분", "00")
        self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "조회구분", "2")  # 2: 전체 잔고 조회

        self.kiwoom.dynamicCall("CommRqData(QString, QString, int, QString)", "잔고조회", "OPW00001", 0, "2000")
        print(f"🔄 잔고 조회 요청 보냄... account number: {account_number}")

    def on_receive_tr_data(self, rqname, trcode):
        """TR 데이터 수신 이벤트 처리 (잔고 조회)"""
        if rqname == "잔고조회":
            balance_raw = self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, 0, "예수금").strip()

            print(f"📥 잔고 조회 응답 수신: {balance_raw}")  # ✅ 응답 로그 추가

            if balance_raw:
                try:
                    balance = int(balance_raw.replace(",", ""))  # 쉼표 제거 후 정수 변환
                    self.ui.balance_label.setText(f"계좌 잔액: {balance:,}원")
                    self.current_balance = balance
                    print(f"✅ 계좌 잔액 업데이트: {balance:,}원")
                except ValueError:
                    print(f"❌ 잔고 데이터 변환 실패: {balance_raw}")
                    self.ui.balance_label.setText("계좌 잔액: 변환 오류")
            else:
                print("❌ 계좌 잔액 조회 실패 (데이터 없음)")
                self.ui.balance_label.setText("계좌 잔액: 조회 실패")

class StockDataManager:
    """종목 데이터 로딩 및 관리"""
    def __init__(self, ui):
        self.ui = ui
        self.candidates_stocks = []  # 종목 리스트 저장
        
    def remove_candidate(self, stock_code):
        """체결된 종목을 후보군 리스트와 UI에서 제거"""
        self.candidates_stocks = [s for s in self.candidates_stocks if s["stock_code"] != stock_code]
        self.load_candidates_list()  # ✅ UI 업데이트
        print(f"📉 {stock_code} 종목이 UI에서 삭제됨")

    def load_candidates_list(self):
        """filtered_candidates.json에서 종목을 불러와서 보유 종목을 제외하고 표시"""
        try:
            with open("filtered_candidates.json", "r", encoding="utf-8") as file:
                data = json.load(file)
                all_stocks = data.get("stocks", [])

            # 보유 종목 조회
            self.ui.account_manager.get_holdings()

            # 보유 종목 제외
            self.candidates_stocks = [s for s in all_stocks if s["stock_code"] not in self.ui.account_manager.owned_stocks]

            # 테이블에 추가
            self.ui.candidates_table.setRowCount(len(self.candidates_stocks))
            for row, stock in enumerate(self.candidates_stocks):
                self.ui.candidates_table.setItem(row, 0, QTableWidgetItem(stock["stock_code"]))
                self.ui.candidates_table.setItem(row, 1, QTableWidgetItem("-"))  # 현재가 (실시간 업데이트 예정)
                self.ui.candidates_table.setItem(row, 2, QTableWidgetItem(str(round(stock["price"], 2))))  # 20이평
                self.ui.candidates_table.setItem(row, 3, QTableWidgetItem("-"))  # 차이 (금액)
                self.ui.candidates_table.setItem(row, 4, QTableWidgetItem("-"))  # 차이 (%)

        except FileNotFoundError:
            self.candidates_stocks = []
            print("❌ filtered_candidates.json 파일을 찾을 수 없습니다.")

    def refresh_candidate_stocks(self):
        """후보군 데이터 갱신"""
        filter_candidates()
        self.load_candidates_list()
        
    def load_holdings_list(self):
        """보유 종목 리스트를 가져와서 UI 테이블 업데이트"""
        self.ui.account_manager.get_holdings()  # ✅ 보유 종목 정보 요청

        holdings = self.ui.account_manager.owned_stocks  # 보유 종목 데이터

        self.ui.holdings_table.setRowCount(len(holdings))

        for row, stock in enumerate(holdings):
            stock_code = stock["stock_code"]
            stock_name = stock["stock_name"]
            buy_price = int(stock["buy_price"].replace(",", ""))  # 매입평단가
            quantity = int(stock["quantity"].replace(",", ""))

            # ✅ 현재가 조회
            current_price = self.ui.kiwoom.dynamicCall("GetMasterLastPrice(QString)", stock_code).strip()
            if not current_price:
                current_price = 0
            else:
                current_price = int(current_price.replace(",", ""))

            # ✅ 차이(%) 계산
            price_diff = ((current_price - buy_price) / buy_price) * 100 if buy_price > 0 else 0

            # ✅ 테이블에 값 추가
            self.ui.holdings_table.setItem(row, 0, QTableWidgetItem(stock_name))
            self.ui.holdings_table.setItem(row, 1, QTableWidgetItem(str(current_price)))
            self.ui.holdings_table.setItem(row, 2, QTableWidgetItem(str(buy_price)))
            diff_item = QTableWidgetItem(f"{price_diff:.2f}%")

            # ✅ 차이(%) 색상 설정 (양수=빨강, 음수=파랑)
            if price_diff > 0:
                diff_item.setBackground(QColor(255, 200, 200))  # 빨간색 계열
            elif price_diff < 0:
                diff_item.setBackground(QColor(200, 200, 255))  # 파란색 계열

            self.ui.holdings_table.setItem(row, 3, diff_item)

        print(f"✅ 보유 종목 {len(holdings)}개 UI 업데이트 완료")
            

class RealtimeDataManager:
    """실시간 데이터 업데이트 관리"""
    def __init__(self, kiwoom, ui):
        self.kiwoom = kiwoom
        self.ui = ui
        self.current_request_index = 0  # ✅ 현재 요청 중인 종목 인덱스
        self.stock_request_queue = []  # ✅ 후보군 종목 요청 대기열
        self.holdings_request_queue = []  # ✅ 보유 종목 요청 대기열

        self.timer = QTimer()
        self.timer.timeout.connect(self.request_stock_prices)

        self.holdings_timer = QTimer()
        self.holdings_timer.timeout.connect(self.request_holdings_prices)

    def start_realtime_updates(self):
        """실시간 데이터 업데이트 시작"""
        self.stock_request_queue = [stock["stock_code"] for stock in self.ui.stock_data_manager.candidates_stocks]
        self.holdings_request_queue = list(self.ui.account_manager.owned_stocks)

        self.current_request_index = 0
        self.request_stock_prices()  # ✅ 후보군 리스트 업데이트 시작
        self.request_holdings_prices()  # ✅ 보유 종목 업데이트 시작

    def stop_realtime_updates(self):
        """실시간 데이터 업데이트 중지"""
        self.timer.stop()
        self.holdings_timer.stop()
        print("🛑 실시간 주가 업데이트 중지")

    # ✅ 후보군 리스트의 종목들 현재가 요청
    def request_stock_prices(self):
        """후보군 종목별 현재가를 opt10001로 요청"""
        if self.current_request_index >= len(self.stock_request_queue):
            print("✅ 후보군 리스트 현재가 업데이트 완료")
            return

        stock_code = self.stock_request_queue[self.current_request_index]
        self.current_request_index += 1

        print(f"📡 현재가 요청: {stock_code} (후보군 리스트)")

        self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "종목코드", stock_code)
        self.kiwoom.dynamicCall("CommRqData(QString, QString, int, QString)", "현재가조회", "opt10001", 0, "5000")

        # ✅ 500ms 후에 다음 종목 요청
        QTimer.singleShot(500, self.request_stock_prices)

    # ✅ 보유 종목의 현재가 요청
    def request_holdings_prices(self):
        """보유 종목별 현재가를 opt10001로 요청"""
        if self.current_request_index >= len(self.holdings_request_queue):
            print("✅ 보유 종목 현재가 업데이트 완료")
            return

        stock_code = self.holdings_request_queue[self.current_request_index]
        self.current_request_index += 1

        print(f"📡 현재가 요청: {stock_code} (보유 종목)")

        self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "종목코드", stock_code)
        self.kiwoom.dynamicCall("CommRqData(QString, QString, int, QString)", "보유종목현재가조회", "opt10001", 0, "6000")

        # ✅ 500ms 후에 다음 종목 요청
        QTimer.singleShot(500, self.request_holdings_prices)
    

class KiwoomUI(QMainWindow):
    RQNAME_DAILY_CHART = "주식일봉차트조회"
    
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Kiwoom 자동매매 프로그램")
        self.setGeometry(100, 100, 800, 500)

        # Kiwoom API 객체 생성
        self.kiwoom = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")
        self.kiwoom.OnEventConnect.connect(self.on_event_connect)
        self.kiwoom.OnReceiveChejanData.connect(self.on_receive_chejan_data)
        self.kiwoom.OnReceiveTrData.connect(self.on_receive_tr_data)
        
        # 계좌 관리 객체 생성
        self.account_manager = AccountManager(self.kiwoom, self)

        # 자동매매 객체 생성
        self.trader = AutoTrader(self.kiwoom, self)

        # 종목 데이터 관리 객체 생성
        self.stock_data_manager = StockDataManager(self)
        
        # 실시간 데이터 관리 객체 생성
        self.realtime_data_manager = RealtimeDataManager(self.kiwoom, self)

        # 데이터 로드
        self.auto_buy_amount = 100000
        self.auto_buy_threshold = 0.8 / 100
        

        self.setup_ui()
        
    def setup_ui(self):
        """전체 UI 초기화"""
        self.tabs = QTabWidget(self)
        self.setCentralWidget(self.tabs)

        # 각 탭 추가
        self.login_tab = QWidget()
        self.account_tab = QWidget()
        self.candidates_tab = QWidget()
        self.holdings_tab = QWidget() 

        self.tabs.addTab(self.login_tab, "로그인")
        self.tabs.addTab(self.account_tab, "계좌정보")
        self.tabs.addTab(self.candidates_tab, "후보군 리스트")
        self.tabs.addTab(self.holdings_tab, "체결 리스트")

        # 개별 UI 설정 함수 호출
        self.setup_login_ui()
        self.setup_account_ui()
        self.setup_candidates_tab_ui()
        self.setup_holdings_tab_ui()
        
    def setup_holdings_tab_ui(self):
        """체결 리스트 UI 설정"""
        layout = QVBoxLayout()

        # ✅ 보유 종목 리스트 테이블 생성
        self.holdings_table = QTableWidget()
        self.holdings_table.setColumnCount(4)  # 종목명, 현재가, 매입평단가, 차이(%)
        self.holdings_table.setHorizontalHeaderLabels(["종목명", "현재가", "매입평단가", "차이(%)"])
        layout.addWidget(self.holdings_table)

        self.holdings_tab.setLayout(layout)

        
    def setup_candidates_tab_ui(self):
        """후보군 리스트 UI 설정"""
        layout = QHBoxLayout()

        # 종목 리스트 테이블
        self.candidates_table = QTableWidget()
        self.candidates_table.setColumnCount(5)  # 종목코드, 현재가, 20이평, 차이(금액), 차이(%)
        self.candidates_table.setHorizontalHeaderLabels(["종목코드", "현재가", "20이평", "차이(금액)", "차이(%)"])
        layout.addWidget(self.candidates_table)

        # ✅ 자동 매수 설정 UI
        self.auto_trade_layout = QVBoxLayout()

        self.balance_label = QLabel("계좌 잔액: -")
        self.auto_trade_layout.addWidget(self.balance_label)

        self.buy_amount_label = QLabel("매수 금액:")
        self.buy_amount_input = QLineEdit(str(self.auto_buy_amount))
        self.auto_trade_layout.addWidget(self.buy_amount_label)
        self.auto_trade_layout.addWidget(self.buy_amount_input)

        self.threshold_label = QLabel("매수 기준 차이 %:")
        self.threshold_input = QDoubleSpinBox()
        self.threshold_input.setRange(0.0, 5.0)  # 0.0% ~ 5.0% 범위
        self.threshold_input.setSingleStep(0.1)  # 0.1% 단위 증가/감소 가능
        self.threshold_input.setValue(self.auto_buy_threshold * 100)  # 기존 값 유지
        self.auto_trade_layout.addWidget(self.threshold_label)
        self.auto_trade_layout.addWidget(self.threshold_input)

        # 자동 매수 버튼
        self.auto_trade_button = QPushButton("자동 매수 시작")
        self.auto_trade_button.clicked.connect(self.trader.start_auto_trade)
        self.auto_trade_layout.addWidget(self.auto_trade_button)
        
        self.stop_trade_button = QPushButton("자동 매수 중지")
        self.stop_trade_button.clicked.connect(self.trader.stop_auto_trade)
        self.auto_trade_layout.addWidget(self.stop_trade_button)
        self.stop_trade_button.setEnabled(False)  # 초기에는 비활성화

        layout.addLayout(self.auto_trade_layout)
        self.candidates_tab.setLayout(layout)
        
    
    def on_receive_chejan_data(self, gubun, item_cnt, fid_list):
        """체결 데이터 수신 이벤트"""
        print("on_receive_chejan_data called",gubun)
        if gubun == "0":  # 주문체결
            stock_code = self.kiwoom.dynamicCall("GetChejanData(int)", 9001).strip()  # 종목코드
            order_status = self.kiwoom.dynamicCall("GetChejanData(int)", 913).strip()  # 체결 상태
            order_price = self.kiwoom.dynamicCall("GetChejanData(int)", 910).strip()  # 주문 가격
            executed_qty = self.kiwoom.dynamicCall("GetChejanData(int)", 911).strip()  # 체결 수량
            remaining_qty = self.kiwoom.dynamicCall("GetChejanData(int)", 902).strip()  # 미체결 수량

            print(f"📥 체결 이벤트 수신: {stock_code} | 상태: {order_status} | 주문가: {order_price} | 체결량: {executed_qty} | 미체결량: {remaining_qty}")

            if stock_code in self.trader.pending_orders:
                if order_status == "체결":
                    print(f"✅ {stock_code} 체결 완료!")

                    # ✅ StockDataManager에서 종목 리스트 갱신 처리
                    self.stock_data_manager.remove_candidate(stock_code)

                    # ✅ 체결된 종목 삭제
                    del self.trader.pending_orders[stock_code]
                    
                    # ✅ 보유 종목 목록 업데이트
                    self.account_manager.get_holdings()

                    # ✅ 후보군 리스트에서 완전히 제거
                    self.stock_data_manager.remove_from_filtered_candidates(stock_code)
                    
                    # ✅ UI 업데이트
                    self.stock_data_manager.load_candidates_list()
                    
                    # ✅ 계좌 잔고 갱신
                    self.account_manager.request_account_balance()
                    
    def remove_from_filtered_candidates(self, stock_code):
        """filtered_candidates.json에서 특정 종목을 제거"""
        try:
            with open("filtered_candidates.json", "r", encoding="utf-8") as file:
                data = json.load(file)

            # ✅ 체결된 종목을 리스트에서 제거
            updated_stocks = [s for s in data.get("stocks", []) if s["stock_code"] != stock_code]

            # ✅ 변경된 리스트 저장
            with open("filtered_candidates.json", "w", encoding="utf-8") as file:
                json.dump({"stocks": updated_stocks}, file, indent=4, ensure_ascii=False)

            print(f"🗑 {stock_code} 후보군 리스트에서 삭제 완료 (filtered_candidates.json 업데이트)")

        except FileNotFoundError:
            print("❌ filtered_candidates.json 파일을 찾을 수 없습니다.")


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
        
        self.account_combo.currentIndexChanged.connect(self.account_manager.on_account_changed)

        # 선택된 계좌번호 표시
        self.account_label = QLabel("선택된 계좌: -")
        self.account_label.setFont(QFont("Arial", 12))
        layout.addWidget(self.account_label)

        # 계좌 선택 버튼
        self.select_account_button = QPushButton("계좌 선택")
        self.select_account_button.setFont(QFont("Arial", 12))
        self.select_account_button.clicked.connect(self.account_manager.select_account)
        layout.addWidget(self.select_account_button)

        # 보유 종목 조회 버튼
        self.get_stocks_button = QPushButton("보유 종목 조회")
        self.get_stocks_button.setFont(QFont("Arial", 12))
        self.get_stocks_button.clicked.connect(self.account_manager.get_holdings)
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
            self.account_manager.get_account_info()
            self.stock_data_manager.refresh_candidate_stocks()
            self.realtime_data_manager.start_realtime_updates()
        else:
            self.status_label.setText(f"로그인 상태: 실패 (에러코드 {err_code})")


    def on_receive_tr_data(self, screen_no, rqname, trcode, recordname, prev_next, data_len, err_code, msg1, msg2):
        """TR 데이터 수신 이벤트"""
        print(f"📩 TR 데이터 수신: {rqname} (TR 코드: {trcode})")
        if rqname == "보유종목조회":
            holdings = self.account_manager.get_holdings_from_tr(trcode, rqname)  # ✅ AccountManager에서 데이터 가져옴
            
            if holdings:
                stock_info = "\n".join([f"종목명: {h['stock_name']}, 수량: {h['quantity']}, 매입가: {h['buy_price']}" for h in holdings])
            else:
                stock_info = "보유 종목 없음"

            self.stock_text.setText(stock_info)  # ✅ UI 업데이트만 수행
        
        if rqname == "잔고조회":
            self.account_manager.on_receive_tr_data(rqname, trcode)
            
        if rqname == "현재가조회":  # ✅ opt10001 응답 처리
            stock_code = self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, 0, "종목코드").strip()
            current_price = self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, 0, "현재가").strip()

            # ✅ 데이터가 정상적으로 들어왔는지 확인
            if not stock_code or not current_price:
                print(f"⚠️ 현재가 데이터 없음, stock_code={stock_code}, current_price={current_price}")
                return  # ✅ 잘못된 응답은 무시

            # ✅ 데이터 정리
            stock_code = stock_code.replace("A", "").strip()  # "A" 접두사 제거
            current_price = int(current_price.replace(",", ""))

            print(f"📥 {stock_code} 현재가 수신: {current_price}")

            # ✅ 후보군 리스트에서 해당 종목 찾기
            for stock in self.stock_data_manager.candidates_stocks:
                if stock["stock_code"] == stock_code:
                    stock["current_price"] = current_price  # ✅ 현재가 업데이트

                    # ✅ 20이평 가격 가져오기
                    ma20_price = stock["price"]
                    diff_amount = current_price - ma20_price
                    diff_percent = (diff_amount / ma20_price) * 100 if ma20_price > 0 else 0

                    # ✅ UI 테이블 업데이트
                    for row in range(self.candidates_table.rowCount()):
                        if self.candidates_table.item(row, 0).text() == stock_code:
                            self.candidates_table.setItem(row, 1, QTableWidgetItem(str(current_price)))  # 현재가
                            self.candidates_table.setItem(row, 3, QTableWidgetItem(str(diff_amount)))  # 차이 금액

                            diff_item = QTableWidgetItem(f"{diff_percent:.2f}%")
                            if diff_percent > 0:
                                diff_item.setBackground(QColor(255, 200, 200))  # 빨간색 계열
                            elif diff_percent < 0:
                                diff_item.setBackground(QColor(200, 200, 255))  # 파란색 계열

                            self.candidates_table.setItem(row, 4, diff_item)
                            break  # ✅ 찾으면 종료

            # ✅ Qt UI 강제 갱신
            QApplication.processEvents()
        
      
            
        
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

            # 최근 15일 내에서 5이평이 20이평보다 계속 작다가 골든크로스 발생 후 항상 위에 있어야 함
            golden_cross = False
            cross_index = -1  # 골든크로스 발생 인덱스 저장

            for i in range(15, 0, -1):  # 최근 15일을 역순 탐색
                if df["5_MA"].iloc[-i] < df["20_MA"].iloc[-i]:  
                    continue  # 아직 5이평이 20이평보다 작음

                if df["5_MA"].iloc[-i - 1] < df["20_MA"].iloc[-i - 1] and df["5_MA"].iloc[-i] > df["20_MA"].iloc[-i]:
                    golden_cross = True
                    cross_index = -i  # 골든크로스 발생 인덱스 저장
                    break

            # 골든크로스가 없거나, 이후 5이평이 20이평보다 작아지는 경우 제외
            if not golden_cross or any(df["5_MA"].iloc[cross_index:] < df["20_MA"].iloc[cross_index:]):
                continue

            ma20_last_15 = df["20_MA"].iloc[-15:].values  # NumPy 배열로 변환
            # 최근 3일간 연속 상승하는지 확인
            is_recent_3days_upward = all(ma20_last_15[i] < ma20_last_15[i + 1] for i in range(len(ma20_last_15) - 3, len(ma20_last_15) - 1))

            if not is_recent_3days_upward:
                continue

            # 종가 기준 필터링
            last_close = df["close"].iloc[-1]
            avg_volume_5 = df["Volume_MA5"].iloc[-1]

            if last_close < 2000:
                continue

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
