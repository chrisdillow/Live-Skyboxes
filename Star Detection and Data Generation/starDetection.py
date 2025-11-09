#Star Detection
#Chris D.
#Version 0
#Version Date: 11/6/2025

# ============================================================== #
#|                    PROGRAM DESCRIPTION                      | #
# ============================================================== #
# Interactive star detection and exporter for hemispherical stereographic
# maps.

import argparse
import os
import sys
import math
from typing import List, Tuple, Optional, Dict
import cv2
import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets
from dataclasses import dataclass

# ============================================================== #
# |                    FUNCTION DEFINITIONS                    | #
# ============================================================== #
# ----------------------- BASIC FUNCTIONS ---------------------- #
def generateLabel():
    letters = [chr(ord('A') + i) for i in range(26)]
    n = 1
    while True:
        for ch in letters:
            yield f"{ch}{n}"
        n += 1

def labelsForN(n: int):
    letters = [chr(ord('A') + i) for i in range(26)]
    labels = []
    k = 1
    while len(labels) < n:
        for ch in letters:
            if len(labels) >= n:
                break
            labels.append(f"{ch}{k}")
        k += 1
    return labels

def dmsToDegrees(dms: str) -> float:
    dms = str(dms).strip()
    if ":" in dms:
        parts = dms.split(":")
        if len(parts) != 3:
            raise ValueError("Time/angle must be 'hh:mm:ss' or 'dd:mm:ss'.")
        hours, minutes, seconds = map(float,parts)
        sign = -1 if dms.strip().startswith("-") else 1
        return sign * (abs(hours) + minutes / 60.0 + seconds / 3600.0) * (15.0 if abs(hours) > 24 else 1.0)
    else:
        return float(dms)

def circleRadiusFromArea(area: float) -> float:
    return max(1.0,math.sqrt(max(area, 1.0) / math.pi))

def toGray(bgr):
    return cv2.cvtColor(bgr,cv2.COLOR_BGR2GRAY) if bgr.ndim == 3 else bgr

def filterBySeparation(rows,minSeparation,maxKeep):
    if not rows:
        return []
    rowsSorted = sorted(rows,key=scoreRow,reverse=True)
    kept = []
    minSepSquared = float(minSeparation) * float(minSeparation)
    for row in rowsSorted:
        centerX,centerY = row['centerX'],row['centerY']
        ok = True
        for star in kept:
            xDist = centerX - star['centerX']; yDist = centerY - star['centerY']
            if xDist * xDist + yDist * yDist < minSepSquared:
                ok = False
                break
        if ok:
            kept.append(row)
            if len(kept) >= int(maxKeep):
                break
    return kept

def scoreRow(r):
    return r['sumIntensity']


# ------------------------ STAR DETECTION ----------------------- #
def percentile(img,q):
    q = float(np.clip(q,0.0,1.0))
    hist = cv2.calcHist([img],[0],None,[256],[0,256]).ravel()
    c = np.cumsum(hist)
    total = c[-1]
    p = q * total
    binIdx = np.searchsorted(c,p)
    return float(binIdx)

def detectStars(bgr,threshold=200,minArea=3,maxArea=5000,blur=3,*,snrThreshold=4.0,bgKernel=61,
                brightPercentile=0.998,haloScale=2.5,suppressHalo=True):
    gray = toGray(bgr)
    k = int(bgKernel) | 1
    if k < 3:
        k = 3
    background = cv2.medianBlur(gray,k)
    residual = cv2.subtract(gray,background)
    absResidual = cv2.blur(cv2.absdiff(gray,background),(k,k))
    sigma = np.maximum(absResidual.astype(np.float32),1.0)
    z = (gray.astype(np.float32) - background.astype(np.float32)) / sigma

    # ----- SNR Mask ----- #
    snrMask = (z > float(snrThreshold)).astype(np.uint8) * 255
    if blur and int(blur) > 1:
        kk = int(blur) | 1
        snrMask = cv2.morphologyEx(snrMask,cv2.MORPH_OPEN,np.ones((3,3),np.uint8),iterations=1)
        snrMask = cv2.GaussianBlur(snrMask,(kk,kk),0)
        _,snrMask = cv2.threshold(snrMask,127,255,cv2.THRESH_BINARY)
    
    # ----- Bright Source Detection ----- #
    pVal = percentile(gray,brightPercentile)
    _,brightMask = cv2.threshold(gray,int(pVal),255,cv2.THRESH_BINARY)
    brightMask = cv2.morphologyEx(brightMask,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8),iterations=2)

    # ----- Halo and Bright Source Handling ----- #
    if suppressHalo:
        numB,labelB,statsB,centsB = cv2.connectedComponentsWithStats(brightMask,connectivity=8)
        halo = np.zeros_like(brightMask)
        for i in range(1,numB):
            _,_,width,height,area = statsB[i]
            if area < 50:
                continue
            radiusSource = circleRadiusFromArea(float(area))
            radiusHalo = int(max(10,haloScale * radiusSource))
            centerXb,centerYb = map(int,centsB[i])
            cv2.circle(halo,(centerXb,centerYb),radiusHalo,255,thickness=-1)
        #Suppress the SNR mask inside the halo unless SNR is very high:
        veryHigh = (z > (snrThreshold * 2.0)).astype(np.uint8) * 255
        keep = cv2.bitwise_and(halo,veryHigh)
        snrMask = cv2.bitwise_and(snrMask,cv2.bitwise_not(halo))
        snrMask = cv2.bitwise_or(snrMask,keep)

    #Connected components on the final candidate mask:
    num,labels,stats,cents = cv2.connectedComponentsWithStats(snrMask,connectivity=8)
    rows = []
    for i in range(1,num):
        x,y,width,height,area = stats[i]
        if area < minArea or area > maxArea:
            continue
        centerX,centerY = map(float,cents[i])
        roi = gray[y:y+height,x:x+width]
        mask = (labels[y:y+height,x:x+width] == i).astype(np.uint8)
        if mask.sum() == 0:
            continue
        sI = float((roi * mask).sum())
        meanI = sI / float(mask.sum())

        rows.append(dict(centerX=centerX,centerY=centerY,area=int(area),sumIntensity=sI,meanIntensity=meanI))

    rows.sort(key=lambda r: (r['sumIntensity'],r['area']),reverse=True)
    return rows,snrMask

def matchPoints(prevPts,newPts,maxDist=12.0):
    out = [None] * len(newPts)
    used = set()
    for j, (x,y) in enumerate(newPts):
        best,bestd2 = None,(maxDist + 1) ** 2
        for i,(prevX,prevY) in enumerate(prevPts):
            if i in used:
                continue
            d2 = (x - prevX) * (x - prevX) + (y - prevY) * (y - prevY)
            if d2 < bestd2:
                bestd2,best = d2,i
        if best is not None:
            used.add(best)
            out[j] = best
    return out


# ----------------------- MATH AND MAPPING ---------------------- #
def inverseStereoToXYZ(normX: float,normY: float) -> Tuple[float,float,float]:
    radiusSquared = normX * normX + normY * normY
    denom = 1.0 + radiusSquared
    return (2.0 * normX / denom, 2.0 * normY / denom,(1.0 - radiusSquared) / denom)


def wrapPi(colatitude: float) -> float:
    colatitude = (colatitude + math.pi) % (2.0 * math.pi)
    return colatitude - math.pi


def wrap360(colatitude: float) -> float:
    colatitude = colatitude % 360.0
    return colatitude if colatitude >= 0 else colatitude + 360


@dataclass
class ProjectionMeta:
    # ----- Disc Geometry in Pixels ----- #
    width: int
    height: int
    centerX: float
    centerY: float
    radius: float
    # ----- Orientation ----- #
    rightAscensionNaught: float = 0.0
    declinationNaught: float = 90.0
    positionAngle: float = 0.0
    # ----- Optional Time and Location ----- #
    greenwichSiderealTime: Optional[float] = None
    observerLatitude: Optional[float] = None
    observerLongitude: Optional[float] = None


def imageXYtoEquatorial(meta: 'ProjectionMeta',xPix: float,yPix: float) -> Tuple[float,float]:
    u = (xPix - meta.centerX) / meta.radius
    v = (meta.centerY - yPix) / meta.radius
    x,y,z = inverseStereoToXYZ(u,v)
    positionAngle = -math.radians(meta.positionAngle)
    xRadius = x * math.cos(positionAngle) - y * math.sin(positionAngle)
    yRadius = x * math.sin(positionAngle) + y * math.cos(positionAngle)
    zRadius = z
    declinationNaught = math.radians(meta.declinationNaught)
    cosTilt,sinTilt = math.cos((math.pi / 2) - declinationNaught), math.sin((math.pi / 2) - declinationNaught)
    rotatedX = xRadius
    rotatedY = yRadius * cosTilt - zRadius * sinTilt
    rotatedZ = yRadius * sinTilt + zRadius * cosTilt
    rightAscensionNaught = math.radians(meta.rightAscensionNaught)
    outX = rotatedX * math.cos(rightAscensionNaught) - rotatedY * math.sin(rightAscensionNaught)
    outY = rotatedX * math.sin(rightAscensionNaught) + rotatedY * math.cos(rightAscensionNaught)
    outZ = rotatedZ
    rightAscension = math.degrees(math.atan2(outY,outX))
    if rightAscension < 0:
        rightAscension += 360.0
    declination = math.degrees(math.asin(max(-1.0,min(1.0,outZ))))
    return (rightAscension,declination)


def equatorialToHorizontal(rightAscension: float,declination: float,latitude: float,longitude: float,localSiderealTime: float) -> Tuple[float,float]:
    hourAngle = math.radians((localSiderealTime - rightAscension) % 360.0)
    declination = math.radians(declination)
    latitude = math.radians(latitude)
    sinAltitude = math.sin(declination) * math.sin(latitude) + math.cos(declination) * math.cos(latitude) * math.cos(hourAngle)
    altitude = math.degrees(math.asin(max(-1.0, min(1.0,sinAltitude))))
    y = -math.sin(hourAngle) * math.cos(declination)
    x = math.sin(declination) * math.cos(latitude) - math.cos(declination) * math.sin(latitude) * math.cos(hourAngle)
    azimuth = (math.degrees(math.atan2(y, x)) + 360.0) % 360.0
    return (azimuth,altitude)


# ----------------------- DETECTION MODEL ---------------------- #
class DetectionModel(QtCore.QAbstractTableModel):
    HEAD = ["ID","Name","Area","Mean","Sum","X","Y"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []

    nameEdited = QtCore.pyqtSignal(int,str)
    
    def setData(self,idx,value,role):
        if role != QtCore.Qt.EditRole or not idx.isValid() or idx.column() != 1:
            return False
        r = idx.row()
        self.rows[r]['name'] = str(value)
        self.dataChanged.emit(idx,idx)
        self.nameEdited.emit(r,self.rows[r]['name'])
        return True

    def rowCount(self,*_): return len(self.rows)

    def columnCount(self,*_): return len(self.HEAD)

    def headerData(self,i,orientation,role):
        return self.HEAD[i] if role == QtCore.Qt.DisplayRole and orientation == QtCore.Qt.Horizontal else None

    def flags(self,idx):
        base = QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled
        return base | QtCore.Qt.ItemIsEditable if idx.isValid() and idx.column() == 1 else base

    def data(self,idx,role=QtCore.Qt.DisplayRole):
        if not idx.isValid():
            return None
        r,c = idx.row(),idx.column()
        row = self.rows[r]
        if role in (QtCore.Qt.DisplayRole,QtCore.Qt.EditRole):
            if c == 0: return row['id']
            if c == 1: return row.get('name') or ""
            if c == 2: return row['area']
            if c == 3: return f"{row['meanIntensity']:.1f}"
            if c == 4: return f"{row['sumIntensity']:.1f}"
            if c == 5: return f"{row['centerX']:.1f}"
            if c == 6: return f"{row['centerY']:.1f}"
        return None

    def setRows(self,rows):
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def getRows(self):
        return self.rows


# ============================================================== #
#|                        MAIN PROGRAM                         | #
# ============================================================== #
class App(QtWidgets.QMainWindow):
    def __init__(self,path=None):
        super().__init__()
        self.setWindowTitle("Star Detection and Overlay Export")

        # ----- State ----- #
        self.bgr = None
        self.prevPts = []
        self.prevMeta = []
        self.overlayColor = QtGui.QColor(255,200,0)
        self.markerScale = 1.5
        self.sizeByBrightness = True
        self.meta = None  # ProjectionMeta
        self.lastPix = None
        self.previewMode = "single" #Single (one hemisphere) or dual (both hemispheres)

        # ================== User Interface ================== #
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        H = QtWidgets.QHBoxLayout(central)

        self.view = QtWidgets.QLabel(alignment=QtCore.Qt.AlignCenter)
        self.view.setStyleSheet("background:#111;")
        self.view.setSizePolicy(QtWidgets.QSizePolicy.Expanding,QtWidgets.QSizePolicy.Expanding)

        right = QtWidgets.QVBoxLayout()
        
        # ----- Buttons ----- #
        row = QtWidgets.QHBoxLayout()
        self.openBtn = QtWidgets.QPushButton("Open...")
        self.saveOverlayBtn = QtWidgets.QPushButton("Export Overlay...")
        self.saveTxtBtn = QtWidgets.QPushButton("Export Star Catalog (.txt)...")
        row.addWidget(self.openBtn)
        row.addWidget(self.saveOverlayBtn)
        row.addWidget(self.saveTxtBtn)
        right.addLayout(row)

        # ----- Sliders ----- #
        #   --- Star Prominence and Sizing ---  #
        self.threshold = self.addSlider(right,"SNR Threshold",8,20,12)
        self.minArea = self.addSlider(right,"Min Star Size (px)",2,60,12)
        self.maxArea = self.addSlider(right,"Max Star Size (px)",20,800,50)
        self.blur = self.addSlider(right,"Blur Sensitivity (odd px)",1,21,3)
        self.scale = self.addSlider(right,"Star Marker Scale (x0.1)",5,50,15)
        self.labelSize = self.addSlider(right,"Label Font Size",3,28,12)
        self.labelSize.valueChanged.connect(self.onParams)
        #    --- Background and Halo Behavior ---   #
        self.bgKernel = self.addSlider(right,"Background Sensitivity Radius (px)",31,121,81)
        self.haloScale = self.addSlider(right,"Halo Sensitivity Scale (x0.1)",15,35,25)
        self.brightPercentile = self.addSlider(right,"Brightness Sensitivity Percentile (x0.1%)",996,999,998)
        self.haloSuppression = QtWidgets.QCheckBox("Halo Suppression")
        self.haloSuppression.setChecked(True)
        right.addWidget(self.haloSuppression)
        self.minSeparation = self.addSlider(right,"Min Separation (px)",8,500,20)
        self.maxStars = self.addSlider(right,"Maximum Stars to Detect",10,500,150)

        # ----- Options ----- #
        options = QtWidgets.QHBoxLayout()
        self.colorBtn = QtWidgets.QPushButton("Marker Color...")
        self.live = QtWidgets.QCheckBox("Live Preview")
        self.live.setChecked(True)
        self.sizeMode = QtWidgets.QCheckBox("Size by Brightness * Area")
        self.sizeMode.setChecked(True)
        options.addWidget(self.colorBtn)
        options.addWidget(self.live)
        options.addWidget(self.sizeMode)
        right.addLayout(options)

        self.showMask = QtWidgets.QCheckBox("Show Binary Mask Inset")
        right.addWidget(self.showMask)

        # ----- Projection Meta Button ----- #
        self.metaBtn = QtWidgets.QPushButton("Projection / Coordinate Settings...")
        right.addWidget(self.metaBtn)

        # ----- Table ----- #
        self.model = DetectionModel(self)
        self.table = QtWidgets.QTableView()
        self.table.setModel(self.model)
        self.table.horizontalHeader().setStretchLastSection(True)

        self.model.nameEdited.connect(self.onModelChanged)

        # ----- Wire Events ----- #
        self.openBtn.clicked.connect(self.onOpen)
        self.saveOverlayBtn.clicked.connect(self.onExportOverlay)
        self.saveTxtBtn.clicked.connect(self.onExportTxt)
        self.colorBtn.clicked.connect(self.onPickColor)
        self.metaBtn.clicked.connect(self.onEditMeta)
        for s in (self.threshold,self.minArea,self.maxArea,self.blur,self.scale,self.bgKernel,self.haloScale,self.brightPercentile,
                  self.minSeparation,self.maxStars):
            s.valueChanged.connect(self.onParams)
        self.haloSuppression.toggled.connect(self.onParams)
        self.live.toggled.connect(self.onParams)
        self.sizeMode.toggled.connect(self.onParams)
        self.showMask.toggled.connect(self.onParams)

        # ----- Layout ----- #
        rightHost = QtWidgets.QWidget()
        rightHost.setLayout(right)
        rightHost.setSizePolicy(QtWidgets.QSizePolicy.Preferred,QtWidgets.QSizePolicy.Minimum)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidget(rightHost)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll.setSizePolicy(QtWidgets.QSizePolicy.Preferred,QtWidgets.QSizePolicy.Expanding)
        splitLeft = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        splitLeft.addWidget(self.view)
        splitLeft.addWidget(self.table)
        splitLeft.setStretchFactor(0,1)
        splitLeft.setStretchFactor(1,0)
        H.addWidget(splitLeft,4)
        H.addWidget(scroll,2)

        if path and os.path.exists(path):
            self.loadImage(path)

    def addSlider(self,parentLayout,title,lo,hi,val):
        box = QtWidgets.QGroupBox(title)
        vertLayout = QtWidgets.QVBoxLayout(box)
        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        slider.setRange(lo, hi)
        slider.setValue(val)
        label = QtWidgets.QLabel(str(val), alignment=QtCore.Qt.AlignRight)
        slider.valueChanged.connect(lambda x: label.setText(str(x)))
        vertLayout.addWidget(slider)
        vertLayout.addWidget(label)
        parentLayout.addWidget(box)
        return slider

    def onOpen(self):
        path,_ = QtWidgets.QFileDialog.getOpenFileName(
            self,"Open stereographic hemisphere","",
            "Images (*.png *.jpg *.jpeg *.tif *.tiff *.bmp)"
        )
        if not path:
            return
        self.loadImage(path)

    def loadImage(self,path):
        bgr = cv2.imread(path,cv2.IMREAD_COLOR)
        if bgr is None:
            QtWidgets.QMessageBox.critical(self,"ERROR",f"Failed to load:\n{path}")
            return
        self.bgr = bgr
        height,width = bgr.shape[:2]
        # Default projection meta as a disc inferred from bounds
        radius = min(width,height) / 2.0
        self.meta = ProjectionMeta(width=width,height=height,centerX=width / 2.0,centerY=height / 2.0,radius=radius)
        dialog = HemisphereDialog(self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            self.previewMode = dialog.mode()
        else:
            self.previewMode = "single"
        self.view.setSizePolicy(QtWidgets.QSizePolicy.Expanding,QtWidgets.QSizePolicy.Expanding)
        self.prevPts = []
        self.prevMeta = []
        self.updateView()

    def onPickColor(self):
        color = QtWidgets.QColorDialog.getColor(self.overlayColor,self,"Pick overlay color")
        if color.isValid():
            self.overlayColor = color
            self.updateView()

    def onParams(self,*args):
        if self.live.isChecked():
            self.updateView()

    def onEditMeta(self):
        if self.bgr is None:
            return
        dialog = MetaDialog(self,self.meta)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            self.meta = dialog.value()
            self.updateView()
    
    def resizeEvent(self,ev):
        super().resizeEvent(ev)
        if self.lastPix is not None:
            self.showScaled(self.lastPix)
    
    def onModelChanged(self,*args):
        rows = self.model.getRows()
        self.prevMeta = [
            {"id": row['id'],"name": row.get("name",row['id']),"custom": (row.get("name",row['id']) != row['id'])}
            for row in rows
        ]
        pix = self.renderOverlay(self.bgr,rows,binimg=None)
        self.showScaled(pix)

    # =============== Rendering and Detection =============== #
    def getParams(self):
        return (
            self.threshold.value(),
            self.minArea.value(),
            self.maxArea.value(),
            self.blur.value(),
            self.scale.value() / 10.0
        )
    
    def getDetectKwargs(self):
        return dict (
            snrThreshold = float(self.threshold.value()),
            bgKernel = int(self.bgKernel.value()), # detectStars() will force this odd via | 1
            haloScale = float(self.haloScale.value()) / 10.0,
            brightPercentile = float(self.brightPercentile.value()) / 1000.0,
            suppressHalo = self.haloSuppression.isChecked()
        )

    def updateView(self):
        if self.bgr is None:
            return
        self.markerScale = self.getParams()[-1]
        self.sizeByBrightness = self.sizeMode.isChecked()

        _,minArea,maxArea,blur,_ = self.getParams()
        rows,binimg = detectStars(
            self.bgr,
            threshold=0, #Ignored in SNR mode; keep for function signature compatibility
            minArea=minArea,
            maxArea=maxArea,
            blur=blur,
            **self.getDetectKwargs()
        )
        rows = filterBySeparation(
            rows,
            minSeparation=int(self.minSeparation.value()),
            maxKeep=int(self.maxStars.value())
        )
        pts = [(row['centerX'],row['centerY']) for row in rows]
        mapping = matchPoints(self.prevPts,pts,maxDist=12.0)

        carriedNames = [None] * len(rows)
        for j,i in enumerate(mapping):
            if i is not None and i < len(self.prevMeta):
                prev = self.prevMeta[i]
                wasCustom = prev.get("custom",prev.get("name") != prev.get("id"))
                if wasCustom:
                    carriedNames[j] = prev.get("name")

        ids = labelsForN(len(rows))

        outputRows = []
        for j,row in enumerate(rows):
            newID = ids[j]
            name = carriedNames[j] if carriedNames[j] else newID
            r = dict(row)
            r['id'] = newID
            r['name'] = name
            outputRows.append(r)

        self.prevPts = pts
        self.prevMeta = [{"id": r["id"],"name": r.get("name"),"custom": (r["name"] != r["id"])} for r in outputRows]
        self.model.setRows(outputRows)

        fullresPix = self.renderOverlay(self.bgr,outputRows,binimg if self.showMask.isChecked() else None)
        self.showScaled(fullresPix)

    def renderOverlay(self,bgr,rows,binimg=None,transparent=False,withLabels=True):
        height, width = bgr.shape[:2]
        if transparent:
            pix = QtGui.QPixmap(width,height)
            pix.fill(QtCore.Qt.transparent)
        else:
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            qimg = QtGui.QImage(rgb.data,width,height,rgb.strides[0],QtGui.QImage.Format.Format_RGB888)
            pix = QtGui.QPixmap.fromImage(qimg)

        painter = QtGui.QPainter(pix)
        painter.setRenderHint(QtGui.QPainter.Antialiasing,True)
        brush = QtGui.QBrush(self.overlayColor)
        font = QtGui.QFont()
        font.setPointSize(int(self.labelSize.value()))
        font.setBold(True)
        painter.setFont(font)

        for row in rows:
            centerX,centerY = row['centerX'], row['centerY']
            baseRadius = circleRadiusFromArea(row['area'])
            factor = 1.0 + (row['meanIntensity'] / 255.0) if self.sizeByBrightness else 1.0
            radius = baseRadius * self.markerScale * factor

            # ----- Fill Marker ----- #
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(brush)
            painter.drawEllipse(QtCore.QPointF(centerX,centerY),radius,radius)

            if withLabels:
                text = row.get('name') or row.get('id', '')
                #Text with soft outline:
                painter.setPen(QtGui.QPen(QtGui.QColor(0,0,0,180),3))
                painter.drawText(int(centerX + radius + 4),int(centerY - radius - 4),text)
                painter.setPen(QtGui.QPen(QtGui.QColor(255,255,255),1))
                painter.drawText(int(centerX + radius + 4),int(centerY - radius - 4),text)

        # Inset mask for preview only:
        if binimg is not None and not transparent:
            scaledWidth = int(width * 0.28)
            scaledHeight = int(scaledWidth * binimg.shape[0] / binimg.shape[1])
            binRGB = cv2.cvtColor(binimg,cv2.COLOR_GRAY2RGB)
            maskPreviewImg = QtGui.QImage(binRGB.data,binRGB.shape[1],binRGB.shape[0],binRGB.strides[0],
                            QtGui.QImage.Format.Format_RGB888)
            iPix = QtGui.QPixmap.fromImage(maskPreviewImg).scaled(
                scaledWidth,scaledHeight,QtCore.Qt.KeepAspectRatio,QtCore.Qt.SmoothTransformation
            )
            margin = 12
            x0 = margin
            y0 = height - iPix.height() - margin
            painter.setPen(QtGui.QPen(QtGui.QColor(0,0,0,160),2))
            painter.setBrush(QtGui.QBrush(QtGui.QColor(0,0,0,120)))
            painter.drawRect(x0 - 4, y0 - 4,iPix.width() + 8,iPix.height() + 8)
            painter.drawPixmap(x0,y0,iPix)
            # ----- Inset SNR Mask ----- #
            painter.setPen(QtGui.QPen(QtGui.QColor(255,255,255,220)))
            font = QtGui.QFont()
            font.setPointSize(int(self.labelSize.value()))
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(x0 + 6,y0 + 16,"SNR Mask")

        painter.end()
        return pix
    
    def showScaled(self,fullresPix: QtGui.QPixmap):
        self.lastPix = fullresPix
        avail = self.view.size()
        if avail.width() > 0 and avail.height() > 0:
            scaled = fullresPix.scaled(avail,QtCore.Qt.KeepAspectRatio,QtCore.Qt.SmoothTransformation)
            self.view.setPixmap(scaled)
        else:
            self.view.setPixmap(fullresPix)
    
    def showEvent(self,ev):
        super().showEvent(ev)
        screenGeometry = QtWidgets.QApplication.primaryScreen().availableGeometry()
        if self.height() > screenGeometry.height():
            self.resize(self.width(),screenGeometry.height() - 40)

    # ====================== Exports ====================== #
    def onExportOverlay(self):
        if self.bgr is None:
            return
        dialog = OverlayExportDialog(self)
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return
        outPath,withLabels = dialog.filepath(),dialog.includeLabels()

        pix = self.renderOverlay(self.bgr,self.model.getRows(),binimg=None,
                                 transparent=True,withLabels=withLabels)
        exportSuccessful = pix.save(outPath,"PNG")
        QtWidgets.QMessageBox.information(
            self,"Export Overlay",
            "Saved:\n" + outPath if exportSuccessful else "Failed to save."
        )

    def onExportTxt(self):
        if self.bgr is None or self.meta is None:
            return
        dialog = CatalogExportDialog(self,self.meta)
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return

        meta = dialog.meta()
        mode = dialog.mode()  # "equatorial" or "horizontal"
        includeGHA = dialog.includeGHA()  # Greenwich Hour Angle

        path,_ = QtWidgets.QFileDialog.getSaveFileName(self,"Save Catalog",".","Text (*.txt)")
        if not path:
            return

        rows = self.model.getRows()
        with open(path,"w",newline="") as file:
            writeOut = lambda s: file.write(s + "\n")
            if mode == "equatorial":
                header = "id\tname\txpix\typix\tra_deg\tdec_deg" + ("\tgha_deg" if includeGHA else "")
                writeOut(header)
                for row in rows:
                    ra,dec = imageXYtoEquatorial(meta,row['centerX'],row['centerY'])
                    line = f"{row['id']}\t{row.get('name','')}\t{row['centerX']:.3f}\t{row['centerY']:.3f}\t{ra:.6f}\t{dec:.6f}"
                    if includeGHA and meta.greenwichSiderealTime is not None:
                        gha = (meta.greenwichSiderealTime - ra) % 360.0
                        line += f"\t{gha:.6f}"
                    writeOut(line)
            else:
                # Horizontal requires latitude + local sidereal time (LST)
                if meta.observerLatitude is None:
                    QtWidgets.QMessageBox.warning(self,"Horizontal Export",
                                                "Observer latitude is required.")
                    return
                # Interpret greenwichSiderealTime as LST if longitude is None; otherwise LST = GST + longitude
                if meta.greenwichSiderealTime is None and meta.observerLongitude is None:
                    QtWidgets.QMessageBox.warning(self,"Horizontal Export",
                                                "Provide LST (or GST and observer longitude).")
                    return
                if meta.greenwichSiderealTime is not None:
                    lst = (meta.greenwichSiderealTime + (meta.observerLongitude or 0.0)) % 360.0 #Local Sidereal Time
                else:
                    lst = 0.0

                header = "id\tname\txpix\typix\taz_deg\talt_deg"
                writeOut(header)
                for row in rows:
                    ra,dec = imageXYtoEquatorial(meta,row['centerX'],row['centerY'])
                    az,alt = equatorialToHorizontal(
                        ra,dec,meta.observerLatitude,meta.observerLongitude or 0.0,lst
                    )
                    writeOut(f"{row['id']}\t{row.get('name','')}\t{row['centerX']:.3f}\t{row['centerY']:.3f}\t{az:.6f}\t{alt:.6f}")
        QtWidgets.QMessageBox.information(self, "Export Catalog", f"Saved:\n{path}")


# ----------- PROJECTION, IMPORT, AND EXPORT DIALOGS ---------- #
class MetaDialog(QtWidgets.QDialog):
    def __init__(self,parent,meta: 'ProjectionMeta'):
        super().__init__(parent)
        self.setWindowTitle("Projection / Coordinate Settings")
        self._meta = ProjectionMeta(**meta.__dict__)
        grid = QtWidgets.QGridLayout(self)

        def addRow(row,label,widget):
            grid.addWidget(QtWidgets.QLabel(label),row,0)
            grid.addWidget(widget,row,1)

        self.centerX = QtWidgets.QDoubleSpinBox(maximum=1e6,decimals=3)
        self.centerX.setValue(meta.centerX)

        self.centerY = QtWidgets.QDoubleSpinBox(maximum=1e6,decimals=3)
        self.centerY.setValue(meta.centerY)

        self.radius = QtWidgets.QDoubleSpinBox(maximum=1e6,decimals=3)
        self.radius.setValue(meta.radius)

        self.rightAscensionNaught = QtWidgets.QDoubleSpinBox(maximum=360,decimals=6)
        self.rightAscensionNaught.setValue(meta.rightAscensionNaught)

        self.declinationNaught = QtWidgets.QDoubleSpinBox(minimum=-90,maximum=90,decimals=6)
        self.declinationNaught.setValue(meta.declinationNaught)

        self.positionAngle = QtWidgets.QDoubleSpinBox(minimum=-360,maximum=360,decimals=6)
        self.positionAngle.setValue(meta.positionAngle)

        self.greenwichSiderealTime = QtWidgets.QDoubleSpinBox(minimum=-1e6,maximum=1e6,decimals=6)
        self.greenwichSiderealTime.setValue(meta.greenwichSiderealTime if meta.greenwichSiderealTime is not None else 0.0)

        self.latitude = QtWidgets.QDoubleSpinBox(minimum=-90,maximum=90,decimals=6)
        self.latitude.setValue(meta.observerLatitude if meta.observerLatitude is not None else 0.0)

        self.longitude = QtWidgets.QDoubleSpinBox(minimum=-180,maximum=180,decimals=6)
        self.longitude.setValue(meta.observerLongitude if meta.observerLongitude is not None else 0.0)

        row = 0
        addRow(row,"Disc Center X (px): ",self.centerX); row += 1
        addRow(row,"Disc Center Y (px): ",self.centerY); row += 1
        addRow(row,"Disc Radius (px): ",self.radius); row += 1
        addRow(row,"Right Ascension₀ (degrees): ",self.rightAscensionNaught); row += 1
        addRow(row,"Declination₀ (degrees): ",self.declinationNaught); row += 1
        addRow(row,"Position Angle (degrees CCW): ",self.positionAngle); row += 1
        addRow(row,"LST or GST (degrees): ",self.greenwichSiderealTime); row += 1
        addRow(row,"Observer Latitude (degrees): ",self.latitude); row += 1
        addRow(row,"Observer Longitude E+ (degrees): ",self.longitude); row += 1

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        grid.addWidget(btns,row,0,1,2)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

    def value(self) -> 'ProjectionMeta':
        meta = self._meta
        meta.centerX = self.centerX.value()
        meta.centerY = self.centerY.value()
        meta.radius = self.radius.value()
        meta.rightAscensionNaught = self.rightAscensionNaught.value()
        meta.declinationNaught = self.declinationNaught.value()
        meta.positionAngle = self.positionAngle.value()
        meta.greenwichSiderealTime = self.greenwichSiderealTime.value()
        meta.observerLatitude = self.latitude.value()
        meta.observerLongitude = self.longitude.value()
        return meta


class OverlayExportDialog(QtWidgets.QDialog):
    def __init__(self,parent):
        super().__init__(parent)
        self.setWindowTitle("Export Transparent Overlay")
        vertLayout = QtWidgets.QVBoxLayout(self)
        self._withLabels = QtWidgets.QCheckBox("Include Labels")
        self._withLabels.setChecked(True)
        vertLayout.addWidget(self._withLabels)
        self.path = QtWidgets.QLineEdit(os.path.abspath("overlay.png"))
        vertLayout.addWidget(self.path)
        pick = QtWidgets.QPushButton("Browse...")
        vertLayout.addWidget(pick)
        pick.clicked.connect(self._browse)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        vertLayout.addWidget(btns)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

    def _browse(self):
        path,_ = QtWidgets.QFileDialog.getSaveFileName(self,"Save Overlay","overlay.png","PNG (*.png)")
        if path:
            self.path.setText(path)

    def includeLabels(self):
        return self._withLabels.isChecked()

    def filepath(self):
        return self.path.text()


class CatalogExportDialog(QtWidgets.QDialog):
    def __init__(self,parent,meta: 'ProjectionMeta'):
        super().__init__(parent)
        self.setWindowTitle("Export Catalog (.txt)")
        self._meta = ProjectionMeta(**meta.__dict__)
        vertLayout = QtWidgets.QVBoxLayout(self)
        self.modeBox = QtWidgets.QComboBox()
        self.modeBox.addItems(["Equatorial (RA/Declination)","Horizontal (Azimuth/Altitude)"])
        vertLayout.addWidget(self.modeBox)
        self.greenwichHourAngle = QtWidgets.QCheckBox("Also include GHA (if LST/GST were provided)")
        vertLayout.addWidget(self.greenwichHourAngle)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        vertLayout.addWidget(btns)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

    def meta(self):
        return self._meta

    def mode(self):
        return "equatorial" if self.modeBox.currentIndex() == 0 else "horizontal"

    def includeGHA(self):
        return self.greenwichHourAngle.isChecked()

class HemisphereDialog(QtWidgets.QDialog):
    def __init__(self,parent):
        super().__init__(parent)
        self.setWindowTitle("Image Layout")
        vertLayout = QtWidgets.QVBoxLayout(self)
        self.single = QtWidgets.QRadioButton("Single Hemisphere (square preview)")
        self.dual = QtWidgets.QRadioButton("Two Hemispheres Side-by-Side (2:1 preview)")
        self.single.setChecked(True)
        vertLayout.addWidget(self.single)
        vertLayout.addWidget(self.dual)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        vertLayout.addWidget(btns); btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
    
    def mode(self):
        return "dual" if self.dual.isChecked() else "single"


# ============================================================== #
#|                          EXECUTION                          | #
# ============================================================== #
def main():
    app = QtWidgets.QApplication(sys.argv)
    path = sys.argv[1] if len(sys.argv) > 1 else None
    window = App(path)

    # ----- Fit to Screen ----- #
    screenGeometry = app.primaryScreen().availableGeometry()
    windowWidth = max(800,int(screenGeometry.width() * 0.9))
    windowHeight = max(500,int(screenGeometry.height() * 0.9))
    window.resize(windowWidth,windowHeight)
    window.setMinimumSize(640,480)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()