from PySide6.QtCore import (QCoreApplication, QMetaObject, QSize, Qt)
from PySide6.QtWidgets import (QComboBox, QDialogButtonBox, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QSizePolicy, QSpacerItem)


class Ui_Connector(object):
    def setupUi(self, Dialog):
        if not Dialog.objectName():
            Dialog.setObjectName(u"Dialog")
        Dialog.resize(380, 72)
        self.gridLayout = QGridLayout(Dialog)
        self.gridLayout.setObjectName(u"gridLayout")
        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.ip_address = QHBoxLayout()
        self.ip_address.setObjectName(u"ip_address")
        self.label = QLabel(Dialog)
        self.label.setObjectName(u"label")
        sizePolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label.sizePolicy().hasHeightForWidth())
        self.label.setSizePolicy(sizePolicy)

        self.ip_address.addWidget(self.label)

        self.ip_selector = QComboBox(Dialog)
        self.ip_selector.addItem("")
        self.ip_selector.addItem("")
        self.ip_selector.setObjectName(u"ip_selector")
        sizePolicy1 = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.ip_selector.sizePolicy().hasHeightForWidth())
        self.ip_selector.setSizePolicy(sizePolicy1)
        self.ip_selector.setEditable(True)

        self.ip_address.addWidget(self.ip_selector)

        self.horizontalLayout.addLayout(self.ip_address)

        self.port = QHBoxLayout()
        self.port.setObjectName(u"port")
        self.label_2 = QLabel(Dialog)
        self.label_2.setObjectName(u"label_2")
        sizePolicy.setHeightForWidth(self.label_2.sizePolicy().hasHeightForWidth())
        self.label_2.setSizePolicy(sizePolicy)

        self.port.addWidget(self.label_2)

        self.port_editor = QLineEdit(Dialog)
        self.port_editor.setObjectName(u"port_editor")
        sizePolicy2 = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.port_editor.sizePolicy().hasHeightForWidth())
        self.port_editor.setSizePolicy(sizePolicy2)
        self.port_editor.setMinimumSize(QSize(20, 0))

        self.port.addWidget(self.port_editor)

        self.horizontalLayout.addLayout(self.port)

        self.gridLayout.addLayout(self.horizontalLayout, 0, 0, 1, 2)

        self.horizontalSpacer = QSpacerItem(175, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.gridLayout.addItem(self.horizontalSpacer, 1, 0, 1, 1)

        self.buttonBox = QDialogButtonBox(Dialog)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        self.buttonBox.setCenterButtons(False)

        self.gridLayout.addWidget(self.buttonBox, 1, 1, 1, 1)

        self.retranslateUi(Dialog)
        self.buttonBox.accepted.connect(Dialog.accept)
        self.buttonBox.rejected.connect(Dialog.reject)

        QMetaObject.connectSlotsByName(Dialog)

    # setupUi

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QCoreApplication.translate("Dialog", u"Please connect to a device...", None))
        self.label.setText(QCoreApplication.translate("Dialog", u"IP:", None))
        self.ip_selector.setItemText(0, QCoreApplication.translate("Dialog", u"127.0.0.1", None))
        self.ip_selector.setItemText(1, QCoreApplication.translate("Dialog", u"input", None))

        self.label_2.setText(QCoreApplication.translate("Dialog", u"Port:", None))
        self.port_editor.setText(QCoreApplication.translate("Dialog", u"5555", None))
    # retranslateUi
