"""Qt widgets for GHOSTNODE tools. All operations are local and user-initiated."""
from __future__ import annotations
import os, json, shutil, subprocess, sys, secrets, string, math
from pathlib import Path
from typing import Any
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,QPushButton,
    QLineEdit,QTextEdit,QPlainTextEdit,QComboBox,QCheckBox,QSpinBox,QFileDialog,QMessageBox,
    QTableWidget,QTableWidgetItem,QHeaderView,QProgressBar,QGroupBox)
from core import diagnostics
from modules import toolkit_core as tc
from ui import theme


def _label(text):
    w=QLabel(text); w.setWordWrap(True); return w

def _button(text, cb):
    b=QPushButton(text); b.clicked.connect(cb); return b

def _layout(widget):
    lay=QVBoxLayout(widget); lay.setContentsMargins(10,10,10,10); lay.setSpacing(9); return lay

def _row(*widgets):
    row=QHBoxLayout()
    for w in widgets: row.addWidget(w)
    return row

def _copy_button(text_getter, parent):
    def copy():
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(text_getter())
    return _button('COPY',copy)

def _choose_file(parent, caption='Select file'):
    path,_=QFileDialog.getOpenFileName(parent,caption,'','All files (*.*)')
    return Path(path) if path else None

def _choose_save(parent, caption='Save as', suggested=''):
    path,_=QFileDialog.getSaveFileName(parent,caption,suggested,'All files (*.*)')
    return Path(path) if path else None

def _message(parent, title, text, error=False):
    (QMessageBox.critical if error else QMessageBox.information)(parent,title,text)

def _safe_error(parent, exc): _message(parent,'GHOSTNODE // ERROR',str(exc),True)

class ToolPage(QWidget):
    def __init__(self, ctx, title, intro=''):
        super().__init__(); self.ctx=ctx; self.root=_layout(self)
        if intro: self.root.addWidget(_label(intro))

class Inspector(ToolPage):
    def __init__(self,ctx):
        super().__init__(ctx,'System Inspector','Live local host diagnostics. No data leaves this computer.')
        self.out=QPlainTextEdit(); self.out.setReadOnly(True); self.root.addWidget(self.out,1)
        self.root.addWidget(_button('REFRESH SYSTEM SNAPSHOT',self.refresh)); self.refresh()
    def refresh(self):
        h=diagnostics.host_summary(); ram=diagnostics.ram_info(); usage=diagnostics.disk_usage(self.ctx.paths.root)
        lines=['SHRXK // SYSTEM INSPECTOR','='*48,f"OS: {diagnostics.os_name()}",f"Host: {__import__('socket').gethostname()}",f"Architecture: {h.get('arch','unknown')}",f"Processor: {__import__('platform').processor() or 'Unknown'}"]
        if ram: lines += [f"RAM total: {diagnostics.human_bytes(ram[0])}",f"RAM available: {diagnostics.human_bytes(ram[1])}",f"RAM used: {diagnostics.human_bytes(ram[0]-ram[1])}"]
        if usage: lines += [f"App drive total: {diagnostics.human_bytes(usage[0])}",f"App drive used: {diagnostics.human_bytes(usage[1])}",f"App drive free: {diagnostics.human_bytes(usage[2])}"]
        lines += [f"Python: {__import__('sys').version.split()[0]}",f"Portable root: {self.ctx.paths.root}",f"Privilege: {'Administrator' if diagnostics.is_admin() else 'Standard user'}"]
        self.out.setPlainText('\n'.join(lines))

class HashTool(ToolPage):
    def __init__(self,ctx):
        super().__init__(ctx,'Hash Generator','Calculate SHA-256 locally and compare hashes for integrity checks.')
        self.path=QLineEdit(); self.path.setReadOnly(True); self.hash=QLineEdit(); self.hash.setReadOnly(True); self.expected=QLineEdit(); self.status=_label('Select a file to begin.')
        self.root.addLayout(_row(self.path,_button('BROWSE',self.browse)))
        self.root.addWidget(_label('SHA-256')); self.root.addLayout(_row(self.hash,_copy_button(self.hash.text,self)))
        self.root.addWidget(_label('Expected hash (optional)')); self.root.addWidget(self.expected)
        self.root.addLayout(_row(_button('CALCULATE / VERIFY',self.calculate),_button('CLEAR',self.clear)))
        self.root.addWidget(self.status); self.root.addStretch(1)
    def browse(self):
        p=_choose_file(self); 
        if p: self.path.setText(str(p)); self.calculate()
    def calculate(self):
        try:
            p=Path(self.path.text()); digest=tc.sha256_file(p); self.hash.setText(digest)
            exp=self.expected.text().strip().lower()
            self.status.setText('MATCH — integrity verified' if exp and secrets.compare_digest(exp,digest) else ('MISMATCH — hashes differ' if exp else 'Hash calculated. Add an expected hash to compare.'))
        except Exception as e: _safe_error(self,e)
    def clear(self): self.path.clear(); self.hash.clear(); self.expected.clear(); self.status.setText('Select a file to begin.')

class PassGen(ToolPage):
    def __init__(self,ctx):
        super().__init__(ctx,'Password Generator','Uses Python’s cryptographic random source. Passwords are not saved.')
        row=QHBoxLayout(); self.length=QSpinBox(); self.length.setRange(8,128); self.length.setValue(24); row.addWidget(_label('Length')); row.addWidget(self.length); self.root.addLayout(row)
        self.checks=[]
        for label,default in [('Uppercase A-Z',True),('Lowercase a-z',True),('Digits 0-9',True),('Symbols',True)]:
            cb=QCheckBox(label); cb.setChecked(default); self.checks.append(cb); self.root.addWidget(cb)
        self.result=QLineEdit(); self.result.setReadOnly(True); self.root.addLayout(_row(self.result,_copy_button(self.result.text,self)))
        self.root.addWidget(_button('GENERATE',self.generate)); self.root.addStretch(1)
    def generate(self):
        try: self.result.setText(tc.secure_password(self.length.value(),*[c.isChecked() for c in self.checks]))
        except Exception as e: _safe_error(self,e)

class NetInfo(ToolPage):
    def __init__(self,ctx):
        super().__init__(ctx,'Network Info','Local adapter and connection summary. No traffic is transmitted by this tool.')
        self.out=QPlainTextEdit(); self.out.setReadOnly(True); self.root.addWidget(self.out,1)
        self.root.addLayout(_row(_button('REFRESH',self.refresh),_button('OPEN WINDOWS NETWORK SETTINGS',self.open_settings)))
        self.refresh()
    def refresh(self):
        info=tc.local_network_info(); lines=['LOCAL NETWORK SUMMARY']+[f'{k.replace("_"," ").title()}: {v}' for k,v in info.items()]
        if sys.platform=='win32':
            try:
                cp=subprocess.run(['ipconfig','/all'],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=8)
                lines+=['','ADAPTER DETAILS','-'*32,cp.stdout[:16000]]
            except Exception as e: lines.append(str(e))
        self.out.setPlainText('\n'.join(lines))
    def open_settings(self):
        if sys.platform=='win32': os.startfile('ms-settings:network-wifi')
        else: _message(self,'Network settings','Open your operating system network settings.')

class Notes(ToolPage):
    def __init__(self,ctx):
        super().__init__(ctx,'Quick Notes','Notes are stored only in the GHOSTNODE portable data folder.')
        self.file=ctx.paths.data/'notes.json'; self.notes=[]
        self.list=QComboBox(); self.editor=QTextEdit(); self.title=QLineEdit(); self.title.setPlaceholderText('Note title')
        self.root.addLayout(_row(self.list,_button('LOAD',self.load_selected),_button('NEW',self.new_note)))
        self.root.addWidget(self.title); self.root.addWidget(self.editor,1)
        self.root.addLayout(_row(_button('SAVE',self.save),_button('DELETE',self.delete_note)))
        self.load_all()
    def load_all(self):
        try: self.notes=json.loads(self.file.read_text(encoding='utf-8')) if self.file.exists() else []
        except Exception: self.notes=[]
        self.list.clear(); self.list.addItems([n.get('title','Untitled') for n in self.notes])
        if self.notes: self.load_selected()
    def load_selected(self):
        i=self.list.currentIndex()
        if 0<=i<len(self.notes): self.title.setText(self.notes[i].get('title','')); self.editor.setPlainText(self.notes[i].get('body',''))
    def new_note(self): self.list.setCurrentIndex(-1); self.title.clear(); self.editor.clear(); self.title.setFocus()
    def save(self):
        i=self.list.currentIndex(); item={'title':self.title.text().strip() or 'Untitled','body':self.editor.toPlainText()}
        if i<0: self.notes.append(item)
        else: self.notes[i]=item
        try: self.file.parent.mkdir(parents=True,exist_ok=True); self.file.write_text(json.dumps(self.notes,ensure_ascii=False,indent=2),encoding='utf-8'); self.load_all(); self.list.setCurrentIndex(len(self.notes)-1 if i<0 else i)
        except Exception as e: _safe_error(self,e)
    def delete_note(self):
        i=self.list.currentIndex()
        if i<0:return
        if QMessageBox.question(self,'Delete note?','Delete this note from the USB?')==QMessageBox.StandardButton.Yes:
            self.notes.pop(i); self.file.write_text(json.dumps(self.notes,ensure_ascii=False,indent=2),encoding='utf-8'); self.load_all(); self.new_note()

class Vault(ToolPage):
    MAGIC=b'GNV1'
    def __init__(self,ctx):
        super().__init__(ctx,'File Vault','AES-256-GCM authenticated encryption. Keep your password safe; it cannot be recovered.')
        self.path=QLineEdit(); self.path.setReadOnly(True); self.pw=QLineEdit(); self.pw.setEchoMode(QLineEdit.EchoMode.Password); self.pw.setPlaceholderText('Vault password')
        self.root.addLayout(_row(self.path,_button('BROWSE',self.browse))); self.root.addWidget(self.pw)
        self.root.addLayout(_row(_button('ENCRYPT TO .gnv',self.encrypt),_button('DECRYPT .gnv',self.decrypt))); self.root.addStretch(1)
    def browse(self):
        p=_choose_file(self); 
        if p:self.path.setText(str(p))
    def encrypt(self):
        try:
            from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            p=Path(self.path.text()); data=p.read_bytes(); salt=os.urandom(16); nonce=os.urandom(12)
            key=Scrypt(salt=salt,length=32,n=2**14,r=8,p=1).derive(self.pw.text().encode())
            out=self.MAGIC+salt+nonce+AESGCM(key).encrypt(nonce,data,None)
            dest=_choose_save(self,'Save encrypted file',str(p)+'.gnv')
            if dest: dest.write_bytes(out); _message(self,'Vault','File encrypted. Original was not changed.')
        except Exception as e: _safe_error(self,e)
    def decrypt(self):
        try:
            from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            p=Path(self.path.text()); blob=p.read_bytes()
            if not blob.startswith(self.MAGIC) or len(blob)<32: raise ValueError('Not a GHOSTNODE .gnv file.')
            salt=blob[4:20]; nonce=blob[20:32]; ciphertext=blob[32:]
            key=Scrypt(salt=salt,length=32,n=2**14,r=8,p=1).derive(self.pw.text().encode())
            data=AESGCM(key).decrypt(nonce,ciphertext,None)
            dest=_choose_save(self,'Save decrypted file',str(p.with_suffix('')))
            if dest: dest.write_bytes(data); _message(self,'Vault','File decrypted. Encrypted original was not changed.')
        except Exception as e: _safe_error(self,e)

class FileUtils(ToolPage):
    def __init__(self,ctx):
        super().__init__(ctx,'File Utilities','Copy or move files with explicit destination selection. No automatic deletion.')
        self.path=QLineEdit(); self.path.setReadOnly(True); self.root.addLayout(_row(self.path,_button('SELECT FILE',self.browse)))
        self.root.addLayout(_row(_button('COPY TO…',self.copy),_button('MOVE TO…',self.move)))
        self.root.addWidget(_label('Move removes the source only after the destination copy succeeds.')); self.root.addStretch(1)
    def browse(self):
        p=_choose_file(self); 
        if p:self.path.setText(str(p))
    def _transfer(self,moving):
        p=Path(self.path.text()); destdir=QFileDialog.getExistingDirectory(self,'Choose destination folder')
        if not destdir:return
        dest=Path(destdir)/p.name
        if dest.exists() and QMessageBox.question(self,'Overwrite?','Destination exists. Replace it?')!=QMessageBox.StandardButton.Yes:return
        try:
            shutil.copy2(p,dest)
            if moving:
                if QMessageBox.question(self,'Confirm move','Copy succeeded. Remove the original file?')==QMessageBox.StandardButton.Yes: p.unlink()
            _message(self,'File Utilities',f'Completed: {dest}')
        except Exception as e:_safe_error(self,e)
    def copy(self): self._transfer(False)
    def move(self): self._transfer(True)

class Wifi(ToolPage):
    def __init__(self,ctx):
        super().__init__(ctx,'Wi-Fi Recon','Nearby network visibility. This does not crack passwords or bypass protected networks. Connect only to open networks or networks you are authorized to use.')
        self.table=QTableWidget(0,5); self.table.setHorizontalHeaderLabels(['SSID','Security','Signal','Channel','Open?']); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); self.root.addWidget(self.table,1)
        self.root.addLayout(_row(_button('SCAN NEARBY NETWORKS',self.scan),_button('OPEN WINDOWS WI-FI SETTINGS',self.settings)))
        self.root.addWidget(_label('For a protected network, use credentials provided by its owner. Open-network connection is handled by Windows.'))
    def scan(self):
        try:
            rows=tc.wifi_scan_windows(); self.table.setRowCount(len(rows))
            for r,row in enumerate(rows):
                for c,key in enumerate(('ssid','security','signal','channel','open')): self.table.setItem(r,c,QTableWidgetItem(row.get(key,'')))
        except Exception as e:_safe_error(self,e)
    def settings(self):
        try:
            if sys.platform=='win32': os.startfile('ms-settings:network-wifi')
            else:_message(self,'Wi-Fi','Use your OS Wi-Fi menu to connect.')
        except Exception as e:_safe_error(self,e)

class Pcap(ToolPage):
    def __init__(self,ctx):
        super().__init__(ctx,'Packet Analyzer','Offline PCAP file inspection only. No live capture or packet injection. Supports classic .pcap files.')
        self.path=QLineEdit(); self.path.setReadOnly(True); self.root.addLayout(_row(self.path,_button('OPEN PCAP',self.browse)))
        self.out=QPlainTextEdit(); self.out.setReadOnly(True); self.root.addWidget(self.out,1)
    def browse(self):
        p,_=QFileDialog.getOpenFileName(self,'Open capture','','PCAP files (*.pcap);;All files (*.*)')
        if not p:return
        self.path.setText(p)
        try:
            d=tc.parse_classic_pcap(Path(p)); lines=[f"Packets: {d['packets']}",f"Bytes: {d['bytes']}",f"Link type: {d['linktype']}",'','PROTOCOLS']
            lines += [f'  {k}: {v}' for k,v in d['protocols'].items()]
            lines+=['','SAMPLE PACKETS']
            lines += [f"{r['protocol']:8} {r['source']} -> {r['destination']} ({r['length']} B)" for r in d['rows']]
            lines+=['','ENDPOINTS']+[f'  {k}: {v}' for k,v in sorted(d['endpoints'].items(),key=lambda x:-x[1])[:30]]
            self.out.setPlainText('\n'.join(lines))
        except Exception as e:_safe_error(self,e)

class Mapper(ToolPage):
    def __init__(self,ctx):
        super().__init__(ctx,'Network Mapper','Local network overview using host information and the existing ARP cache. No active probing or remote scanning.')
        self.out=QPlainTextEdit(); self.out.setReadOnly(True); self.root.addWidget(self.out,1)
        self.root.addLayout(_row(_button('REFRESH LOCAL INFO',self.refresh),_button('OPEN NETWORK SETTINGS',self.settings))); self.refresh()
    def refresh(self):
        info=tc.local_network_info(); arp=tc.arp_table(); self.out.setPlainText('\n'.join([f'{k}: {v}' for k,v in info.items()]+['','EXISTING ARP CACHE','-'*32,arp]))
    def settings(self):
        if sys.platform=='win32': os.startfile('ms-settings:network-status')

class Forensics(ToolPage):
    def __init__(self,ctx):
        super().__init__(ctx,'Digital Forensics','Read-only local file metadata, file signature and SHA-256. Files are never executed.')
        self.path=QLineEdit(); self.path.setReadOnly(True); self.root.addLayout(_row(self.path,_button('SELECT FILE',self.browse)))
        self.out=QPlainTextEdit(); self.out.setReadOnly(True); self.root.addWidget(self.out,1)
    def browse(self):
        p=_choose_file(self); 
        if not p:return
        self.path.setText(str(p))
        try:
            d=tc.file_metadata(p); self.out.setPlainText('\n'.join(f'{k}: {v}' for k,v in d.items()))
        except Exception as e:_safe_error(self,e)

class PasswordAudit(ToolPage):
    def __init__(self,ctx):
        super().__init__(ctx,'Password Audit','Local heuristic only. Never tests credentials against accounts or services. Use a sample, not a password you currently use.')
        self.pw=QLineEdit(); self.pw.setEchoMode(QLineEdit.EchoMode.Password); self.pw.setPlaceholderText('Enter a sample password')
        self.out=QPlainTextEdit(); self.out.setReadOnly(True); self.root.addWidget(self.pw); self.root.addWidget(_button('ANALYZE LOCALLY',self.analyze)); self.root.addWidget(self.out,1)
    def analyze(self):
        d=tc.password_strength(self.pw.text()); self.out.setPlainText(f"Rating: {d['label']}\nEstimated entropy: {d['entropy']:.1f} bits (rough heuristic)\n\n"+'\n'.join('• '+x for x in d['issues']))

class HexViewer(ToolPage):
    def __init__(self,ctx):
        super().__init__(ctx,'Hex Viewer','Read-only hexadecimal view. Large files are limited to the first 1 MiB for responsiveness.')
        self.path=QLineEdit(); self.path.setReadOnly(True); self.root.addLayout(_row(self.path,_button('OPEN FILE',self.browse)))
        self.out=QPlainTextEdit(); self.out.setReadOnly(True); self.root.addWidget(self.out,1)
    def browse(self):
        p=_choose_file(self); 
        if not p:return
        self.path.setText(str(p))
        try:
            data=p.read_bytes()[:1024*1024]; lines=[]
            for off in range(0,len(data),16):
                chunk=data[off:off+16]; hx=' '.join(f'{b:02X}' for b in chunk).ljust(47); asc=''.join(chr(b) if 32<=b<127 else '.' for b in chunk)
                lines.append(f'{off:08X}  {hx}  |{asc}|')
            self.out.setPlainText('\n'.join(lines)+('\n[display truncated at 1 MiB]' if p.stat().st_size>len(data) else ''))
        except Exception as e:_safe_error(self,e)


class AsciiEarth(ToolPage):
    """Animated ASCII globe visualization; entirely local and decorative."""
    def __init__(self, ctx):
        super().__init__(ctx, 'ASCII // EARTH',
                         'Local 3D-style ASCII globe. Drag-free visualization; no network or location data.')
        self.mode=QComboBox()
        self.mode.addItems(['EARTH','WIRE','SCAN','GLITCH'])
        self.speed=QSpinBox(); self.speed.setRange(1,10); self.speed.setValue(4)
        self.speed.setSuffix('x')
        self.pause=_button('PAUSE ROTATION',self.toggle)
        self.root.addLayout(_row(_label('MODE'),self.mode,_label('ROTATION'),self.speed,self.pause))
        self.view=QPlainTextEdit(); self.view.setReadOnly(True)
        self.view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.view.setStyleSheet('QPlainTextEdit { background:#03070b; color:#48f5c5; border:1px solid #164c52; }')
        font=QFont('Cascadia Mono',9); font.setStyleHint(QFont.StyleHint.Monospace)
        self.view.setFont(font); self.root.addWidget(self.view,1)
        self.status=_label('ORBITAL VIEW // LOCAL RENDER')
        self.root.addWidget(self.status)
        self.angle=0.0; self.running=True; self.frame=0
        self.timer=QTimer(self); self.timer.timeout.connect(self.render_frame); self.timer.start(120)
        self.mode.currentTextChanged.connect(self.render_frame)
        self.render_frame()

    def toggle(self):
        self.running=not self.running
        self.pause.setText('PAUSE ROTATION' if self.running else 'RESUME ROTATION')
        if self.running:self.timer.start(120)
        else:self.timer.stop()

    @staticmethod
    def _land(lat, lon):
        # Stylized continent silhouettes, intentionally illustrative.
        blobs=[
            (-0.25,-1.95,0.38,0.72),(-0.72,-1.55,0.28,0.36), # North America
            (-0.05,-1.25,0.23,0.22),(-0.72,-0.95,0.42,0.28), # South America
            (0.55,0.25,0.22,0.42),(0.05,0.42,0.36,0.55), # Europe/Africa
            (0.62,1.35,0.34,0.65),(0.22,1.65,0.28,0.52), # Asia
            (-0.45,2.15,0.24,0.30),(-0.78,2.25,0.12,0.22) # Australia
        ]
        for cy,cx,ry,rx in blobs:
            dx=(lon-cx+math.pi)%(2*math.pi)-math.pi
            if (lat-cy)**2/(ry*ry)+(dx*math.cos(lat))**2/(rx*rx)<1:
                return True
        return False

    def render_frame(self, *_):
        self.frame+=1
        if self.running:
            self.angle += 0.035*self.speed.value()
        rows, cols = 31, 76
        lines=[]
        mode=self.mode.currentText()
        for y in range(rows):
            line=[]
            for x in range(cols):
                # Static sparse star field outside the globe
                seed=(x*37+y*19)%97
                ch=' ' if seed>93 else ('.' if seed==7 else ' ')
                nx=(x-(cols-1)/2)/(cols*0.36)
                ny=((rows-1)/2-y)/(rows*0.43)
                rr=nx*nx+ny*ny
                if rr<=1:
                    z=math.sqrt(max(0,1-rr))
                    lat=math.asin(max(-1,min(1,ny)))
                    lon=math.atan2(nx,z)-self.angle
                    land=self._land(lat,lon)
                    if mode=='WIRE':
                        ch='@' if abs(rr-0.92)<0.045 or abs(nx)<0.018 or abs(ny)<0.025 else ('+' if z>0.15 else '.')
                    elif mode=='SCAN':
                        scan=(self.frame%rows)/rows
                        ch='=' if abs((y/rows)-scan)<0.045 else ('#' if land and z>0.15 else '.' if z>0.1 else ' ')
                    elif mode=='GLITCH' and (self.frame%23 in (0,1)) and seed%9==0:
                        ch='X' if z>0 else ' '
                    elif land:
                        ch=('@' if z>0.65 else '#' if z>0.35 else '+') if z>0 else '.'
                    else:
                        ch='.' if z>0.35 else ':' if z>0 else ' '
                    if z<0.12 and mode!='WIRE': ch='.'
                line.append(ch)
            lines.append(''.join(line).rstrip())
        title=' SHRXK // ASCII EARTH     MODE: %-6s   ROT: %05.1f° ' % (mode,(self.angle*180/math.pi)%360)
        self.view.setPlainText(title+'\n'+'\n'.join(lines)+'\n\n [LOCAL ASCII RENDER]  •  [ESC: switch module]  •  [NO NETWORK]')
        self.status.setText('ORBITAL VIEW // FRAME %05d // %s' % (self.frame,'ROTATING' if self.running else 'PAUSED'))

_MAP={'inspector':Inspector,'hash':HashTool,'passgen':PassGen,'netinfo':NetInfo,'notes':Notes,'vault':Vault,'files':FileUtils,'wifi':Wifi,'pcap':Pcap,'mapper':Mapper,'forensics':Forensics,'pwaudit':PasswordAudit,'hex':HexViewer,'ascii-earth':AsciiEarth}
def build_tool_widget(module_id,ctx):
    cls=_MAP.get(module_id)
    if not cls:return None
    return cls(ctx)
