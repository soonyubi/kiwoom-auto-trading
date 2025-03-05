import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QWidget, QTabWidget, QMessageBox, QComboBox)
from PyQt5.QtGui import QFont
from PyQt5.QAxContainer import QAxWidget

class KiwoomLogin(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("Kiwoom 자동매매 로그인")
        self.setGeometry(100,100,500,400)

        # Kiwoom API Object creation
        self.kiwoom = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")
        self.kiwoom.OnEventConnect.connect(self.on_event_connect)

        # tab widget
        self.tabs = QTabWidget(self)
        self.setCentralWidget(self.tabs)

        # tab1: Login tab
        self.login_tab = QWidget()
        self.tabs.addTab(self.login_tab, "Login")

        # tab2: Account Info
        self.account_tab = QWidget()
        self.tabs.addTab(self.account_tab, "Account Info")

        self.setup_login_ui()
        self.setup_account_ui()


    def setup_login_ui(self):
        """ login/logout ui settings"""
        layout = QVBoxLayout()

        # login status label
        self.status_label = QLabel("Login Status: Not Connected!!")
        self.status_label.setFont(QFont("Arial",12 ))
        layout.addWidget(self.status_label)

        # Login button
        self.login_button = QPushButton("Login")
        self.login_button.setFont(QFont("Arial",12))
        self.login_button.clicked.connect(self.kiwoom_login)
        layout.addWidget(self.login_button)

        # logout button
        self.logout_button = QPushButton("Logout")
        self.logout_button.setFont(QFont("Arial",12))
        self.logout_button.setEnabled(False)
        self.logout_button.clicked.connect(self.kiwoom_logout)
        layout.addWidget(self.logout_button)

        self.login_tab.setLayout(layout)

    def setup_account_ui(self):
        """ account info ui settings """
        layout = QVBoxLayout()

        # account selection dropdown
        self.account_combo = QComboBox(self)
        self.account_combo.setFont(QFont("Arial",12))
        layout.addWidget(self.account_combo)

        # selected account 
        self.account_label = QLabel("Selected Account : -")
        self.account_label.setFont(QFont("Arial",12))
        layout.addWidget(self.account_label)

        # account selection button
        self.select_account_button = QPushButton("Select Account")
        self.select_account_button.setFont(QFont("Arial",12))
        self.select_account_button.clicked.connect(self.select_account)
        layout.addWidget(self.select_account_button)

        self.account_tab.setLayout(layout)

    def kiwoom_login(self):
        """ login request """
        self.kiwoom.dynamicCall("CommConnect()")

    def kiwoom_logout(self):
        """ logout request"""
        QMessageBox.information(self, "Logout", "Kiwoom OpenAPI 는 강제 로그아웃이 없습니다. \n 프로그램을 종료해주세요.")

    def on_event_connect(self, err_code):
        """ process login event"""
        if err_code == 0:
            self.status_label.setText("Login Status: Connected")
            self.login_button.setEnabled(False)
            self.logout_button.setEnabled(True)
            self.get_account_info()
        else:
            self.status_label.setText("Login Status: Not Connected")

    def get_account_info(self):
        """ get account after login""" 
        account_list = self.kiwoom.dynamicCall("GetLoginInfo(QString)", "ACCNO")
        accounts = account_list.strip().split(';')[:-1]

        if accounts:
            self.account_combo.clear()
            self.account_combo.addItems(accounts)
            self.account_combo.setCurrentIndex(0)
            self.account_label.setText(f"Selected Account: ${accounts[0]}")
        else:
            self.account_label.setText("Couldn't get account list")

    def select_account(self):
        """ update selected account """
        selected_account = self.account_combo.currentText()
        self.account_label.setText(f"Selected Account: ${selected_account}")
        
if __name__ == "__main__":
    app = QApplication(sys.argv)
    login_window = KiwoomLogin()
    login_window.show()
    sys.exit(app.exec_())
