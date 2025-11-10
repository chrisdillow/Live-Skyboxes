#Cylindrical Panoramic to Stereographically Projected Hemispheres
#User Interface
#Chris D. | Version 1 | Version Date: 11/8/2025

# ============================================================== #
#|                       VERSION HISTORY                       | #
# ============================================================== #
#   Version 0 (11/3/2025): Functional Launch
#   Version 1 (11/8/2025): UI reprogrammed in PyQt5 for better
#       resolution, more robust widgets, and modularityin full
#       program.

# ============================================================== #
#|                    SUBPROGRAM DESCRIPTION                   | #
# ============================================================== #
# Takes a user's 2:1 aspect ratio image as an input and outputs
# a double-hemisphere stereographic projection of that image,
# such as seen in continental and celestial maps.

import os, shutil, subprocess, sys
from PyQt5 import QtCore, QtGui, QtWidgets

# ============================================================== #
#|                    PYTHON COMPATIBILITY                     | #
# ============================================================== #
def appDir():
    if getattr(sys,"frozen",False) and hasattr(sys,"_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

def findExe():
    exe = "stereographicProjectionEngine.exe" if os.name == "nt" else "stereographicProjectionEngine"
    bundled = os.path.join(appDir(),exe)
    if os.path.exists(bundled):
        return bundled
    if os.path.exists(exe):
        return exe
    found = shutil.which(exe)
    return found or exe

# ============================================================== #
#|                       USER INTERFACE                        | #
# ============================================================== #
class StereographicProjectionWidget(QtWidgets.QWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setObjectName("Stereographic Projection Maker")

        # ======================= STATE ======================== #
        self.inPath = QtWidgets.QLineEdit()
        self.size = QtWidgets.QLineEdit("2048")
        self.lon0 = QtWidgets.QLineEdit("0")
        self.southOffset = QtWidgets.QLineEdit("0")
        self.southMirror = QtWidgets.QCheckBox("Mirror South Disc (astronomy)")
        self.southMirror.setChecked(True)
        self.bothHemispheres = QtWidgets.QCheckBox("Export Both Hemispheres Together (in addition to individuals)")
        self.bothHemispheres.setChecked(True)

        # ======================= LAYOUT ======================= #
        root = QtWidgets.QVBoxLayout(self)
        grid = QtWidgets.QGridLayout()
        root.addLayout(grid)

        # --------------------- INPUT ROWS --------------------- #
        inputLabel = QtWidgets.QLabel("Import Base Image:")
        infoIcon = QtWidgets.QLabel("ⓘ")
        infoIcon.setCursor(QtCore.Qt.PointingHandCursor)
        infoIcon.setToolTip(
            "Equirectangular (2:1 aspect ratio) images provide the best results, "
            "but similar ratios work well too. 2:1 aspect ratio is typical for panoramas."
        )

        browseBtn = QtWidgets.QPushButton("Browse...")
        browseBtn.clicked.connect(self.onBrowse)

        grid.addWidget(inputLabel,0,0,1,1)
        grid.addWidget(inputLabel,0,1,1,1)
        grid.addWidget(self.inPath,1,0,1,2)
        grid.addWidget(browseBtn,1,2,1,1)

        currentRow = 2

        sizeLabel = QtWidgets.QLabel("Output Hemisphere Diameter (px):")
        grid.addWidget(sizeLabel,currentRow,0,1,1)
        grid.addWidget(self.size,currentRow,1,1,1); currentRow += 1

        lon0Label = QtWidgets.QLabel("Longitude Up (degrees):")
        grid.addWidget(lon0Label,currentRow,0,1,1)
        grid.addWidget(self.lon0,currentRow,1,1,1); currentRow += 1

        southLabel = QtWidgets.QLabel("South Longitudinal Offset (degrees):")
        grid.addWidget(southLabel,currentRow,0,1,1)
        grid.addWidget(self.southOffset,currentRow,1,1,1); currentRow += 1

        grid.addWidget(self.southMirror,currentRow,0,1,2); currentRow += 1
        grid.addWidget(self.bothHemispheres,currentRow,0,1,2); currentRow += 1

        # ---------------------- RUN ROW ---------------------- #
        runRow = QtWidgets.QHBoxLayout()
        self.runBtn = QtWidgets.QPushButton("Generate")
        self.runBtn.clicked.connect(self.onRun)
        self.status = QtWidgets.QLabel("")
        runRow.addWidget(self.runBtn,0)
        runRow.addWidget(self.status,1)
        root.addLayout(runRow)

        # -------------------- UI GEOMETRY -------------------- #
        grid.setColumnStretch(0,1)
        grid.setColumnStretch(1,0)
        grid.setColumnStretch(2,0)
        self.setMinimumWidth(520)

    def onBrowse(self):
        path,_ = QtWidgets.QFileDialog.getOpenFileName(
            self,"Input Image Selection","",
            "Images (*.png *.jpg *.jpeg *.tif *.tiff *.bmp);;All Files (*)"
        )
        if path:
            self.inPath.setText(path)
    
    def onRun(self):
        exe = findExe()
        if not os.path.exists(exe) and shutil.which(exe) is None:
            QtWidgets.QMessageBox.critical(self,"EXECUTABLE NOT FOUND",
                                 f"Could not locate the C++ engine:\n{exe}\n\n"
                                 "Recompile the source code or put it in your PATH.")
            return
        if not self.inPath.text().strip():
            QtWidgets.QMessageBox.critical(self,"MISSING INPUT","Please select a base image.")
            return
        
        try:
            size = int(self.size.text().strip())
            lon0 = float(self.lon0.text().strip())
            southOffset = float(self.southOffset.text().strip())
        except ValueError:
            QtWidgets.QMessageBox.critical(self,"INVALID PARAMETER TYPES",
                                 "Please enter valid numbers for size and longitude.")
            return
        
        args = [
            exe,
            self.inPath.text().strip(),
            "--size",str(size),
            "--lon0",str(lon0),
            "--southOffset",str(southOffset),
            "--southMirror", "1" if self.southMirror.isChecked() else "0",
            "--bothHemispheres", "1" if self.bothHemispheres.isChecked() else "0",
        ]

        try:
            self.status.setText("Running...")
            #TODO: Implement QProcess or QThread for intensive processing (future version)
            print("ENGINE:",exe)
            print("ARGS:",args)
            proc = subprocess.run(args,capture_output=True,text=True)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self,"RUN FAILED",f"Could not run the executable:\n{e}")
            self.status.setText("")
            return
        
        if proc.returncode != 0:
            self.status.setText("")
            stderr = (proc.stderr or "").strip()
            QtWidgets.QMessageBox.critical(self,"ERROR",stderr if stderr else "UNKNOWN ERROR")
        else:
            self.status.setText("Done")
            QtWidgets.QMessageBox.information(self,"SUCCESS",(proc.stdout or "").strip())

# ============================================================== #
#|                          EXECUTION                          | #
# ============================================================== #
if __name__ == "__main__":
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling,True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps,True)

    app = QtWidgets.QApplication(sys.argv)
    window = StereographicProjectionWidget()
    window.setWindowTitle("Hemispherical Map Maker")
    window.show()
    sys.exit(app.exec_())