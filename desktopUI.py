#seAdaptive Skyboxes
#UI and Control
#Developed by Chris D. | Version 1 | Version Date 11/9/2025

#============================================================#
#|                    VERSION HISTORY                       |#
#============================================================#
# Version 0 (10/29/2025): Functional launch
# Version 1 (11/9/2025): UI reprogrammed in PyQt5 for better
#   resolution, more robust widgets, and modularity in full
#   program.
# TODO: Version 2: Handle all TODO's in file and tie in sub-
#   programs' interfaces as widgets of this as the main.

#============================================================#
#|                    IMPORTS AND GLOBALS                   |#
#============================================================#
from PyQt5 import QtCore, QtGui, QtWidgets
import os
import sys
import subprocess

scriptName = "LIVE SKYBOXES"
seLicense = "spaceengine.org/manual/license"
CAPTURE_TYPES = [
    "CubeMap","FishEye","Cylinder","VR","CrossEye","VePair","HorPair","Anaglyph","Shutter"
    ]

#============================================================#
#|                     FUNCTIONS / SETUP                    |#
#============================================================#
def ssExtensions(isPro: bool):
    return ["jpg","png","dds","tif","tga"] if isPro else ["jpg"]

def runScreenshotEngine(params):
    baseDir = os.path.dirname(os.path.abspath(__file__))
    exePath = os.path.join(baseDir,"SpaceEngine Autoamtion","seScreenshotEngine.exe")
    cmd = [
        exePath,
        "--out", params["outPath"],
        "--scriptName", params["scriptName"],
        "--capturePosition", params["capturePosition"],
        "--initialDate", params["initialDate"],
        "--startTime", params["startTime"],
        "--captureObject", params["captureObject"],
        "--captureType", params["captureType"],
        "--exportFiletype", params["exportFiletype"],
        "--frames", str(params["frames"]),
        "--intervalUnit", params["intervalUnit"],
        "--intervalStep", str(params["intervalStep"])
    ]
    subprocess.run(cmd,check=True)

class AdaptiveSkyboxWidget(QtWidgets.QWidget):
    def __init__(self,path: str = None,parent=None):
        super().__init__(parent)

        # ----- State ----- #
        self.isPro = False

        # ================== ROOT LAYOUT ================== #
        horizLayout = QtWidgets.QHBoxLayout(self)
        # ----- Left Tabs ----- #
        self.tabs = QtWidgets.QTabWidget()
        horizLayout.addWidget(self.tabs,5)

        # ----- Right: TODO Reserved for future global actions ----- #
        rightVertLayout = QtWidgets.QVBoxLayout()
        rightVertLayout.addStretch(1)
        rightVertHost = QtWidgets.QWidget()
        rightVertHost.setLayout(rightVertLayout)
        rightVertHost.setSizePolicy(QtWidgets.QSizePolicy.Preferred,QtWidgets.QSizePolicy.Expanding)
        horizLayout.addWidget(rightVertHost,1)

        # =============== (SE) EXPORT SKYBOX =============== #
        seTab = QtWidgets.QWidget()
        self.tabs.addTab(seTab,"(SE) Export Skybox")
        seLayout = QtWidgets.QVBoxLayout(seTab)

        heroText = QtWidgets.QLabel("Assistant and pipeline for generating adaptive skyboxes.")
        heroText.setAlignment(QtCore.Qt.AlignLeft); heroText.setStyleSheet("font-size:18px;")
        seLayout.addWidget(heroText)

        # ----- User Outputs Debug Path ----- #
        debugRow = QtWidgets.QHBoxLayout()
        self.debugPathEdit = QtWidgets.QLineEdit()
        self.debugPathEdit.setPlaceholderText("Select where to put your debuggable exports...")
        debugBtn = QtWidgets.QPushButton("Browse...")
        debugBtn.clicked.connect(self.pickDebugPath)
        debugRow.addWidget(QtWidgets.QLabel("SE Debug Path:")); debugRow.addWidget(self.debugPathEdit,1)
        debugRow.addWidget(debugBtn)
        seLayout.addLayout(debugRow)

        # ----- Export Path ----- #
        exportRow = QtWidgets.QHBoxLayout()
        self.exportPathEdit = QtWidgets.QLineEdit()
        self.exportPathEdit.setPlaceholderText("Select SpaceEngine code export path...")
        exportBtn = QtWidgets.QPushButton("Browse...")
        exportBtn.clicked.connect(self.pickExportPath)
        exportRow.addWidget(QtWidgets.QLabel("SE Code Path:")); exportRow.addWidget(self.exportPathEdit,1)
        exportRow.addWidget(exportBtn)
        seLayout.addLayout(exportRow)

        # ----- Optional Target Object File Handling ----- #
        objectRow = QtWidgets.QHBoxLayout()
        self.objectEdit = QtWidgets.QLineEdit()
        self.objectEdit.setPlaceholderText("[OPTIONAL] Target Object File (.se/.sc/.txt)")
        objectBtn = QtWidgets.QPushButton("Browse...")
        objectBtn.clicked.connect(self.pickObjectFile)
        objectRow.addWidget(QtWidgets.QLabel("Target Object:")); objectRow.addWidget(self.objectEdit,1)
        objectRow.addWidget(objectBtn)
        seLayout.addLayout(objectRow)

        # ----- Capture Type and Filetype Handling ----- #
        captureRow = QtWidgets.QHBoxLayout()
        self.captureTypeBox = QtWidgets.QComboBox(); self.captureTypeBox.addItems(CAPTURE_TYPES)
        self.filetypeBox = QtWidgets.QComboBox(); self.filetypeBox.addItems(ssExtensions(False)) #TODO: Check if this handles pro user as a variable
        captureRow.addWidget(QtWidgets.QLabel("Capture Type:")); captureRow.addWidget(self.captureTypeBox,1)
        captureRow.addSpacing(16)
        captureRow.addWidget(QtWidgets.QLabel("Export Filetype:")); captureRow.addWidget(self.filetypeBox,1)
        seLayout.addLayout(captureRow)

        # ----- Actions #TODO: Wire ----- #
        btnRow = QtWidgets.QHBoxLayout()
        self.previewBtn = QtWidgets.QPushButton("Preview / Validate")
        self.generateBtn = QtWidgets.QPushButton("Generate Skybox Script")
        self.previewBtn.clicked.connect(self.onPreview)
        self.generateBtn.clicked.connect(self.onGenerate)
        btnRow.addStretch(1); btnRow.addWidget(self.previewBtn); btnRow.addWidget(self.generateBtn)
        seLayout.addLayout(btnRow)
        seLayout.addStretch(1)
    
        # ============= BLENDER AUTOMATION ============= #
        #TODO: Further development of Blender pipeline
        blenderTab = QtWidgets.QWidget()
        self.tabs.addTab(blenderTab,"(BLENDER) Skybox Setup")
        blenderLayout = QtWidgets.QVBoxLayout(blenderTab)
        blenderLayout.addWidget(QtWidgets.QLabel("[NOT YET IMPLEMENTED] Blender setup helpers."))
        blenderLayout.addStretch(1)

        # ============== UNREAL ENGINE 5 =============== #
        #TODO: Further development of the Unreal pipeline
        unrealTab = QtWidgets.QWidget()
        self.tabs.addTab(unrealTab,"(UE) Skybox Import and Test")
        unrealLayout = QtWidgets.QVBoxLayout(unrealTab)
        unrealLayout.addWidget(QtWidgets.QLabel("[NOT YET IMPLEMENTED] Unreal Engine 5 assistant."))
        unrealLayout.addStretch(1)

        # ================= SETTINGS =================== #
        settingsTab = QtWidgets.QWidget()
        self.tabs.addTab(settingsTab,"Settings")
        settingsLayout = QtWidgets.QVBoxLayout(settingsTab)
        self.proCheck = QtWidgets.QCheckBox("(SE) PRO User")
        self.proCheck.toggled.connect(self.updateFiletypesForPro)
        settingsLayout.addWidget(self.proCheck)
        settingsLayout.addStretch(1)

        # ================= LICENSE =================== #
        licenseTab = QtWidgets.QWidget()
        self.tabs.addTab(licenseTab,"License Information")
        licenseLayout = QtWidgets.QVBoxLayout(licenseTab)
        license = QtWidgets.QLabel(seLicense)
        license.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        licenseLayout.addWidget(license)
        licenseLayout.addStretch(1)

        # ===== Optional Initial Path ===== #
        if path and os.path.exists(path):
            self.debugPathEdit.setText(path)
    
    # =============== SLOTS AND HELPERS ============== #
    def pickDebugPath(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(self,"Select SE Debug Path")
        if path:
            self.debugPathEdit.setText(path)
    
    def pickExportPath(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(self,"Select SE Code Export Path")
        if path:
            self.exportPathEdit.setText(path)
    
    def pickObjectFile(self):
        path,_ = QtWidgets.QFileDialog.getOpenFileName(
            self,"Select Target Object File","",
            "SpaceEngine (*.se *.sc);;Text (*.txt);;All Files (*)"
        )
        if path:
            self.objectEdit.setText(path)
    
    def updateFiletypesForPro(self,checked: bool):
        keep = self.filetypeBox.currentText()
        self.filetypeBox.blockSignals(True)
        self.filetypeBox.clear()
        self.filetypeBox.addItems(ssExtensions(bool(checked)))
        idx = self.filetypeBox.findText(keep)
        self.filetypeBox.setCurrentIndex(idx if idx >= 0 else 0)
        self.filetypeBox.blockSignals(False)

    #TODO: Wire the following upon coding their background logic
    def onGenerate(self):
        QtWidgets.QMessageBox.information(self,"Generate","[WIP] Export your skybox code.") #TODO: Find better descriptor
    
    def onPreview(self):
        QtWidgets.QMessageBox.information(self,"Preview","[WIP] Hook up preview / validation here.") #TODO: same as above
    
#============================================================#
#|                         EXECUTION                        |#
#============================================================#
if __name__ == "__main__":
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling,True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps,True)

    app = QtWidgets.QApplication(sys.argv)
    window = AdaptiveSkyboxWidget(path=sys.argv[1] if len(sys.argv) > 1 else None)
    window.setWindowTitle("Live Skybox Toolkit")
    window.show()
    sys.exit(app.exec_())