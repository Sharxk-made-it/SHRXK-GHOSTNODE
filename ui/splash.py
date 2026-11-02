"""Original GHOSTNODE boot splash: abstract glitch mask, not a copied franchise logo."""
from __future__ import annotations
import random
from PySide6.QtCore import Qt, QTimer, Signal, QPointF
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget
from ui import theme

class BootSplash(QWidget):
    finished = Signal()
    def __init__(self, family: str, duration_ms: int=2600):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(620,360); self.family=family; self.progress=0; self.tick=0; self.duration=duration_ms
        self.timer=QTimer(self); self.timer.setInterval(35); self.timer.timeout.connect(self.advance)
        self.lines=['BOOTSTRAPPING PORTABLE NODE','LOADING LOCAL TOOLKIT','CHECKING DATA ROOT','INITIALIZING SESSION']
        self._start=0
    def showEvent(self,event):
        super().showEvent(event)
        screen=self.screen().availableGeometry(); self.move(screen.center().x()-self.width()//2,screen.center().y()-self.height()//2)
        self.timer.start()
    def advance(self):
        self.tick+=1; self.progress=min(100,int(self.tick*35*100/self.duration)); self.update()
        if self.progress>=100:
            self.timer.stop(); QTimer.singleShot(260,self.finished.emit)
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(),QColor(theme.BG))
        p.setPen(QPen(QColor(theme.YELLOW),1)); p.drawRect(8,8,self.width()-16,self.height()-16)
        # abstract geometric mask/eye mark
        cx,cy=310,116; jitter=random.randint(-2,2) if self.tick%4==0 else 0
        p.setPen(QPen(QColor(theme.YELLOW),3)); p.setBrush(Qt.BrushStyle.NoBrush)
        poly=QPolygonF([QPointF(cx-72+jitter,cy-42),QPointF(cx-20,cy-58),QPointF(cx+56,cy-42),QPointF(cx+76,cy+2),QPointF(cx+38,cy+54),QPointF(cx-40,cy+54),QPointF(cx-76,cy+2)])
        p.drawPolygon(poly)
        p.setPen(QPen(QColor(theme.RED),4)); p.drawLine(cx-48,cy-8,cx-8,cy-8); p.drawLine(cx+12,cy-8,cx+50,cy-8)
        p.setPen(QPen(QColor(theme.YELLOW_DIM),2)); p.drawLine(cx-22,cy+22,cx+22,cy+22); p.drawLine(cx-12,cy+36,cx+12,cy+36)
        font=QFont(self.family); font.setBold(True); font.setPointSize(21); font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing,3)
        p.setFont(font); p.setPen(QColor(theme.RED)); p.drawText(91,207,'GHOSTNODE')
        p.setPen(QColor(theme.YELLOW)); p.drawText(89,205,'GHOSTNODE')
        font.setPointSize(9); font.setBold(False); font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing,2); p.setFont(font); p.setPen(QColor(theme.TEXT_DIM))
        p.drawText(90,230,'PORTABLE DIGITAL OPERATIONS TOOLKIT')
        p.setPen(QColor(theme.TEXT));
        idx=min(3,self.progress//25)
        for i,line in enumerate(self.lines[:idx+1]): p.drawText(90,264+i*15,'> '+line+('...' if i==idx else ' [OK]'))
        p.setPen(QPen(QColor(theme.LINE),1)); p.drawRect(90,322,440,8)
        p.fillRect(91,323,int(438*self.progress/100),6,QColor(theme.YELLOW))
        p.setPen(QColor(theme.YELLOW)); p.drawText(540,330,f'{self.progress:03d}%')
