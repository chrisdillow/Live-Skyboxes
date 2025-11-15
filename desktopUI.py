#Live Skyboxes
#Main UI and Control
#Developed by Chris D. | Version 2 | Version Date 11/15/2025

#============================================================#
#|                    VERSION HISTORY                       |#
#============================================================#
# Version 0 (10/29/2025): Functional launch
# Version 1 (11/9/2025): UI reprogrammed in PyQt5 for better
#   resolution, more robust widgets, and modularity in full
#   program.
# Version 2 (11/10/2025): Functionality with seObjectParser.py
#   was added.
#           (11/15/2025): Debugged, cleaned up, and prepared
#           for subprogram UI linkage.
# TODO: Version 3: Tie in sub-programs' interfaces as widgets
#       of this as the main.

#============================================================#
#|                    IMPORTS AND GLOBALS                   |#
#============================================================#
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QSettings
import os
import sys
import subprocess
from SpaceEngine_Automation.seObjectParser import readText, writeTXTCopy, parseBlocks, buildCalendarSpec

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

def getScreenshotEnginePath(name="seScreenshotEngine.exe"):
    baseDir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(baseDir,"SpaceEngine_Automation",name)

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
        
        # ----- Output Filename ----- #
        nameRow = QtWidgets.QHBoxLayout()
        self.outNameEdit = QtWidgets.QLineEdit("adaptiveSkybox.se")
        nameRow.addWidget(QtWidgets.QLabel("Output Filename:"))
        nameRow.addWidget(self.outNameEdit,1)
        seLayout.addLayout(nameRow)

        # ----- Optional Target Object File Handling ----- #
        objectRow = QtWidgets.QHBoxLayout()
        self.objectEdit = QtWidgets.QLineEdit()
        self.objectEdit.setPlaceholderText("[OPTIONAL] Target Object File (.se/.sc/.txt)")
        objectBtn = QtWidgets.QPushButton("Browse...")
        objectBtn.clicked.connect(self.pickObjectFile)
        objectRow.addWidget(QtWidgets.QLabel("Target Object:")); objectRow.addWidget(self.objectEdit,1)
        objectRow.addWidget(objectBtn)
        seLayout.addLayout(objectRow)

        # ----- Planet Selection ----- #
        planetRow = QtWidgets.QHBoxLayout()
        self.planetBox = QtWidgets.QComboBox()
        planetRow.addWidget(QtWidgets.QLabel("Select Planet:"))
        planetRow.addWidget(self.planetBox,1)
        seLayout.addLayout(planetRow)

        # ----- Moon Selection ----- #
        moonRow = QtWidgets.QHBoxLayout()
        self.moonBox = QtWidgets.QComboBox()
        moonRow.addWidget(QtWidgets.QLabel("Month-Determining Moon:"))
        moonRow.addWidget(self.moonBox,1)
        seLayout.addLayout(moonRow)

        # ----- Capture Position ----- #
        positionRow = QtWidgets.QHBoxLayout()
        self.capturePosEdit = QtWidgets.QLineEdit("Sol/Earth")
        positionRow.addWidget(QtWidgets.QLabel("Capture Position:"))
        positionRow.addWidget(self.capturePosEdit,1)
        seLayout.addLayout(positionRow)

        # ----- Capture Type and Filetype Handling ----- #
        captureRow = QtWidgets.QHBoxLayout()
        self.captureTypeBox = QtWidgets.QComboBox(); self.captureTypeBox.addItems(CAPTURE_TYPES)
        self.filetypeBox = QtWidgets.QComboBox(); self.filetypeBox.addItems(ssExtensions(False))
        captureRow.addWidget(QtWidgets.QLabel("Capture Type:")); captureRow.addWidget(self.captureTypeBox,1)
        captureRow.addSpacing(16)
        captureRow.addWidget(QtWidgets.QLabel("Export Filetype:")); captureRow.addWidget(self.filetypeBox,1)
        seLayout.addLayout(captureRow)

        # ----- Date/Time and Interval Controls ----- #
        # --- Start Date/Time --- #
        startRow = QtWidgets.QHBoxLayout()
        self.startDateEdit = QtWidgets.QLineEdit("2000.01.01")
        self.startTimeEdit = QtWidgets.QLineEdit("00:00:00.00")
        startRow.addWidget(QtWidgets.QLabel("Screenshot Start Date:"))
        startRow.addWidget(self.startDateEdit)
        startRow.addWidget(QtWidgets.QLabel("Screenshot Start Time:"))
        startRow.addWidget(self.startTimeEdit)
        seLayout.addLayout(startRow)
        # --- End Date/Time (Optional) --- #
        endRow = QtWidgets.QHBoxLayout()
        self.endDateEdit = QtWidgets.QLineEdit("")
        self.endTimeEdit = QtWidgets.QLineEdit("00:00:00.00")
        endRow.addWidget(QtWidgets.QLabel("Screenshot End Date:"))
        endRow.addWidget(self.endDateEdit)
        endRow.addWidget(QtWidgets.QLabel("Screenshot End Time:"))
        endRow.addWidget(self.endTimeEdit)
        seLayout.addLayout(endRow)
        # --- Screenshot Interval --- #
        intervalRow = QtWidgets.QHBoxLayout()
        self.intervalUnitBox = QtWidgets.QComboBox()
        self.intervalUnitBox.addItems(["seconds","hours","days","months","years"])
        self.intervalStepEdit = QtWidgets.QLineEdit("1.0")
        intervalRow.addWidget(QtWidgets.QLabel("Screenshot Interval:"))
        intervalRow.addWidget(self.intervalUnitBox)
        intervalRow.addWidget(QtWidgets.QLabel("Screenshot Interval Step:"))
        intervalRow.addWidget(self.intervalStepEdit)
        seLayout.addLayout(intervalRow)

        # ----- Frames (Optional) ----- #
        framesRow = QtWidgets.QHBoxLayout()
        self.framesEdit = QtWidgets.QLineEdit("")
        self.framesEdit.setPlaceholderText("[Optional] If this is empty and End Date is set, the engine will derive the frame count to export.")
        framesRow.addWidget(QtWidgets.QLabel("Frames:"))
        framesRow.addWidget(self.framesEdit,1)
        seLayout.addLayout(framesRow)

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
        self.updateFiletypesForPro(self.proCheck.isChecked())
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
        # Load saved UI state:
        self.loadSettings()
    
    # =============== SLOTS AND HELPERS ============== #
    def loadSettings(self):
        settings = QSettings("Chris D.","Live Skyboxes")
        self.debugPathEdit.setText(settings.value("debugPath","",str))
        self.exportPathEdit.setText(settings.value("exportPath","",str))
        self.objectEdit.setText(settings.value("objectPath","",str))
        self.capturePosEdit.setText(settings.value("capturePosition","Sol/Earth",str))
        self.outNameEdit.setText(settings.value("outName","adaptiveSkybox.se",str))
        # ----- Date/Time ----- #
        if hasattr(self,"startDateEdit"):
            self.startDateEdit.setText(settings.value("startDate","2000.01.01",str))
        if hasattr(self,"startTimeEdit"):
            self.startTimeEdit.setText(settings.value("startTime","00:00:00.00",str))
        if hasattr(self,"endDateEdit"):
            self.endDateEdit.setText(settings.value("endDate","",str))
        if hasattr(self,"endTimeEdit"):
            self.endTimeEdit.setText(settings.value("endTime","00:00:00.00",str))
        # ----- Screenshot Interval and Frames ----- #
        if hasattr(self,"intervalUnitBox"):
            intervalUnit = settings.value("intervalUnit","hours",str)
            idx = self.intervalUnitBox.findText(intervalUnit)
            self.intervalUnitBox.setCurrentIndex(idx if idx >= 0 else 0)
        if hasattr(self,"intervalStepEdit"):
            self.intervalStepEdit.setText(settings.value("intervalStep","1.0",str))
        if hasattr(self,"framesEdit"):
            self.framesEdit.setText(settings.value("frames","",str))
        # ----- Capture, Filetype, and Capture Type ----- #
        if hasattr(self,"captureTypeBox"):
            captureType = settings.value("captureType","",str)
            idx = self.captureTypeBox.findText(captureType)
            if idx >= 0:
                self.captureTypeBox.setCurrentIndex(idx)
        if hasattr(self,"filetypeBox"):
            filetype = settings.value("exportFiletype","",str)
            idx = self.filetypeBox.findText(filetype)
            if idx >= 0:
                self.filetypeBox.setCurrentIndex(idx)
        # ----- SE PRO User Checkbox ----- #
        if hasattr(self,"proCheck"):
            self.proCheck.setChecked(settings.value("proUser",False,bool))
            self.updateFiletypesForPro(self.proCheck.isChecked())
    
    def saveSettings(self):
        settings = QSettings("Chris D.","Live Skyboxes")
        settings.setValue("debugPath",self.debugPathEdit.text().strip())
        settings.setValue("exportPath",self.exportPathEdit.text().strip())
        settings.setValue("objectPath",self.objectEdit.text().strip())
        settings.setValue("capturePosition",getattr(self,"capturePosEdit",QtWidgets.QLineEdit("Sol/Earth")).text().strip())
        settings.setValue("outName",self.outNameEdit.text().strip()if hasattr(self,"outNameEdit") else "adaptiveSkybox.se")
        if hasattr(self,"startDateEdit"):
            settings.setValue("startDate",self.startDateEdit.text().strip())
        if hasattr(self,"startTimeEdit"):
            settings.setValue("startTime",self.startTimeEdit.text().strip())
        if hasattr(self,"endDateEdit"):
            settings.setValue("endDate",self.endDateEdit.text().strip())
        if hasattr(self,"endTimeEdit"):
            settings.setValue("endTime",self.endTimeEdit.text().strip())
        if hasattr(self,"intervalUnitBox"):
            settings.setValue("intervalUnit",self.intervalUnitBox.currentText())
        if hasattr(self,"intervalStepEdit"):
            settings.setValue("intervalStep",self.intervalStepEdit.text().strip())
        if hasattr(self,"framesEdit"):
            settings.setValue("frames",self.framesEdit.text().strip())
        if hasattr(self,"captureTypeBox"):
            settings.setValue("captureType",self.captureTypeBox.currentText())
        if hasattr(self,"filetypeBox"):
            settings.setValue("exportFiletype",self.filetypeBox.currentText())
        if hasattr(self,"proCheck"):
            settings.setValue("proUser",self.proCheck.isChecked())

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

    def onGenerate(self):
        name = (self.outNameEdit.text().strip() or "adaptiveSkybox.se")
        if not name.lower().endswith(".se"):
            name += ".se"
        outPath = os.path.join(self.exportPathEdit.text().strip() or "",name)
        if not (self.exportPathEdit.text().strip()):
            QtWidgets.QMessageBox.warning(self,"Missing Export Path",
                                          "Please choose an SE Code Path (export folder) first.")
            return
        debugDir = self.debugPathEdit.text().strip()
        objectPath = self.objectEdit.text().strip() or ""

        calendar = {"dayHours": 24.0,"monthDays": 30.0,"yearDays": 365.0,"year0": 2000}
        try:
            if objectPath and os.path.exists(objectPath):
                writeTXTCopy(objectPath,debugDir)
                txt = readText(objectPath)
                roots = parseBlocks(txt)
            
            # Populate Planet / Moon selectors once if empty
                try:
                    if self.planetBox.count() == 0:
                        planetNames = [item.name for item in roots if getattr(item,"type","") == "Planet" and getattr(item,"name",None)]
                        if planetNames:
                            self.planetBox.addItems(planetNames)
                    if self.moonBox.count() == 0:
                        moonNames = []
                        for item in roots:
                            if getattr(item,"type","") == "Moon" and getattr(item,"name",None):
                                moonNames.append(item.name)
                        if moonNames:
                            self.moonBox.addItems(moonNames)
                except Exception:
                    pass
                
                # Use the current user selections to build the calendar
                planetName = self.planetBox.currentText().strip() or None
                moonName = self.moonBox.currentText().strip() or None
                calendar = buildCalendarSpec(roots,planetName=planetName,chosenMoon=moonName)

        except Exception as e:
            QtWidgets.QMessageBox.warning(self,"Parser Warning",
                                        f"Could not fully parse the object file.\n"
                                        f"Proceeding with the defaults.\n\n{e}")
            
        exePath = getScreenshotEnginePath("seScreenshotEngine.exe")
        if not os.path.exists(exePath):
            QtWidgets.QMessageBox.critical(self,"Engine Not Found",
                                           f"Could not find the screenshot engine at:\n{exePath}\n\n"
                                           "Make sure seScreenshotEngine.exe is in:\nSpaceEngine_Automation/.")
            return
        
        try:
            step = float(self.intervalStepEdit.text().strip() or "1.0")
            if step <= 0:
                raise ValueError
        except ValueError:
            QtWidgets.QMessageBox.warning(self,"Invalid Screenshot Interval",
                                          "Interval Step must be a positive number.")
            return

        cmd = [
            exePath,
        "--out",outPath,
        "--scriptName","Live Skybox",
        "--capturePosition",self.capturePosEdit.text().strip() or "Sol/Earth",
        "--initialDate",self.startDateEdit.text().strip() or "2000.01.01",
        "--startTime",self.startTimeEdit.text().strip() or "00:00:00.00",
        "--captureObject","ISS",
        "--captureType",self.captureTypeBox.currentText(),
        "--exportFiletype",self.filetypeBox.currentText(),
        "--intervalUnit",self.intervalUnitBox.currentText(),
        "--intervalStep",str(step),
        "--dayHours",str(calendar["dayHours"]),
        "--monthDays",str(calendar["monthDays"]),
        "--yearDays",str(calendar["yearDays"]),
        "--year0",str(calendar["year0"]),
        "--debugDir",debugDir
        ]

        if self.endDateEdit.text().strip():
            cmd += ["--endDate",self.endDateEdit.text().strip(),
                    "--endTime",self.endTimeEdit.text().strip() or "00:00:00.00"]
        else:
            framesText = self.framesEdit.text().strip() if hasattr(self,"framesEdit") else ""
            framesCount = framesText if framesText else "20"
            cmd += ["--frames",framesCount]

        try:
            subprocess.run(cmd,check=True)
            QtWidgets.QMessageBox.information(self,"Done",
                                              f"Skybox frame export script written:\n{outPath}\n\n"
                                              f"Debug Copy (if set):\n{debugDir}")
        except subprocess.CalledProcessError as e:
            QtWidgets.QMessageBox.critical(self,"Engine Error",
                                           f"seScreenshotEngine exited with an error.\n\n"
                                           f"Command:\n{' '.join(cmd)}\n\n{e}")
    
    def onPreview(self):
        exportDir = self.exportPathEdit.text().strip()
        debugDir = self.debugPathEdit.text().strip()
        objectPath = self.objectEdit.text().strip() or ""

        if not exportDir:
            QtWidgets.QMessageBox.warning(self,"Missing Export Path",
                                          "Please choose an SE Code Path (export folder) first.")
            return

        outPath = os.path.join(exportDir,"adaptiveSkybox_preview.se")
        calendar = {"dayHours": 24.0,"monthDays": 30.0,"yearDays": 365.0,"year0": 2000}
        try:
            if objectPath and os.path.exists(objectPath):
                writeTXTCopy(objectPath,debugDir)
                txt = readText(objectPath)
                roots = parseBlocks(txt)

                try:
                    if self.planetBox.count() == 0:
                        planetNames = [item.name for item in roots if getattr(item,"type","") == "Planet" and getattr(item,"name",None)]
                        if planetNames:
                            self.planetBox.addItems(planetNames)
                    if self.moonBox.count() == 0:
                        moonNames = []
                        for item in roots:
                            if getattr(item,"type","") == "Moon" and getattr(item,"name",None):
                                moonNames.append(item.name)
                        if moonNames:
                            self.moonBox.addItems(moonNames)
                except Exception:
                    pass
                
                planetName = self.planetBox.currentText().strip() or None
                moonName = self.moonBox.currentText().strip() or None
                calendar = buildCalendarSpec(roots,planetName=planetName,chosenMoon=moonName)
        
        except Exception as e:
            QtWidgets.QMessageBox.warning(self,"Parser Warning",
                                        f"Could not fully parse the object file.\n"
                                        f"Proceeding with the defaults.\n\n{e}")
                            
        exePath = getScreenshotEnginePath("seScreenshotEngine.exe")
        if not os.path.exists(exePath):
            QtWidgets.QMessageBox.critical(self,"Engine Not Found",
                                           f"Could not find engine at:\n{exePath}\n\n"
                                           f"Make sure seScreenshotEngine.exe is in:\nSpaceEngine_Automation/.")
            return
        
        try:
            step = float(self.intervalStepEdit.text().strip() or "1.0")
            if step <= 0:
                raise ValueError
        except ValueError:
            QtWidgets.QMessageBox.warning(self,"Invalid Screenshot Interval",
                                          "Interval Step must be a positive number.")
            return
        
        cmd = [
            exePath,
        "--out", outPath,
        "--scriptName","Live Skybox (Preview)",
        "--capturePosition",self.capturePosEdit.text().strip() or "Sol/Earth",
        "--initialDate",self.startDateEdit.text().strip() or "2000.01.01",
        "--startTime",self.startTimeEdit.text().strip() or "00:00:00.00",
        "--captureObject","ISS",
        "--captureType",self.captureTypeBox.currentText(),
        "--exportFiletype",self.filetypeBox.currentText(),
        "--frames","1",
        "--intervalUnit",self.intervalUnitBox.currentText(),
        "--intervalStep",str(step),
        "--dayHours",str(calendar["dayHours"]),
        "--monthDays",str(calendar["monthDays"]),
        "--yearDays",str(calendar["yearDays"]),
        "--year0",str(calendar["year0"]),
        "--debugDir",debugDir
        ]

        try:
            completed = subprocess.run(cmd,check=False,capture_output=True,text=True)
            if completed.returncode == 0:
                QtWidgets.QMessageBox.information(self,"Preview OK",
                                                f"Preview script generated successfully.\n\n"
                                                f"SE File:\n{outPath}\n\n"
                                                f"Debug Copy (if set):\n{debugDir or '(not set)'}")
            else:
                QtWidgets.QMessageBox.critical(self,"Preview Failed",
                                            f"seScreenshotEngine returned an error\n\n"
                                            f"Command:\n{' '.join(cmd)}\n\n"
                                            f"STDOUT:\n{completed.stdout or '(empty)'}\n\n"
                                            f"STDERR:\n{completed.stderr or '(empty)'}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self,"Preview Exception",
                                        f"Failed to run preview.\n\n{e}")
    
    def closeEvent(self,ev):
        try:
            self.saveSettings()
        finally:
            super().closeEvent(ev)
    
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