"""Safe, local-only helpers used by GHOSTNODE tools (no Qt dependency)."""
from __future__ import annotations
import hashlib, os, platform, socket, struct, subprocess, sys, time, math, re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(chunk_size), b''):
            h.update(chunk)
    return h.hexdigest()


def secure_password(length: int = 20, upper=True, lower=True, digits=True, symbols=True) -> str:
    import secrets, string
    pools = []
    if upper: pools.append(string.ascii_uppercase)
    if lower: pools.append(string.ascii_lowercase)
    if digits: pools.append(string.digits)
    if symbols: pools.append('!@#$%^&*()-_=+[]{};:,.?')
    if not pools: raise ValueError('Select at least one character set.')
    if length < len(pools) or length > 256: raise ValueError('Length must be between character-set count and 256.')
    chars = [secrets.choice(pool) for pool in pools]
    all_chars = ''.join(pools)
    chars.extend(secrets.choice(all_chars) for _ in range(length-len(chars)))
    secrets.SystemRandom().shuffle(chars)
    return ''.join(chars)


def password_strength(password: str) -> Dict[str, object]:
    """Local heuristic only; never transmits or tests a password against accounts."""
    if not password: return {'score': 0, 'label': 'EMPTY', 'entropy': 0.0, 'issues': ['Enter a sample password.']}
    pool = 0
    for test, size in ((str.islower,26),(str.isupper,26),(str.isdigit,10)):
        if any(test(c) for c in password): pool += size
    if any(not c.isalnum() for c in password): pool +=  symbol_pool_size()
    entropy = len(password) * math.log2(max(pool,1))
    score = min(4, int(entropy // 25))
    labels = ['VERY WEAK','WEAK','FAIR','STRONG','VERY STRONG']
    issues=[]
    if len(password)<12: issues.append('Consider 12+ characters.')
    if len(set(password))<len(password)*0.5: issues.append('Contains many repeated characters.')
    if password.lower() in ('password','qwerty','letmein','admin'): issues.append('Common password pattern.')
    if not issues: issues.append('No obvious weaknesses in this local heuristic.')
    return {'score':score,'label':labels[score],'entropy':entropy,'issues':issues}

def symbol_pool_size(): return 32


def file_metadata(path: Path) -> Dict[str, object]:
    st=path.stat()
    with path.open('rb') as f: head=f.read(32)
    signatures=[(b'\x89PNG\r\n\x1a\n','PNG image'),(b'\xff\xd8\xff','JPEG image'),(b'GIF8','GIF image'),(b'%PDF','PDF document'),(b'PK\x03\x04','ZIP / Office archive'),(b'MZ','Windows executable'),(b'\x7fELF','ELF executable'),(b'ID3','MP3 audio')]
    kind=next((name for sig,name in signatures if head.startswith(sig)),'Unknown / text / other')
    return {'name':path.name,'path':str(path),'size':st.st_size,'modified':time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(st.st_mtime)),'created':time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(st.st_ctime)),'type':kind,'sha256':sha256_file(path)}


def parse_classic_pcap(path: Path, limit: int=200000) -> Dict[str, object]:
    """Read classic pcap offline; no live capture. Summarizes Ethernet IPv4/IPv6 packets."""
    with path.open('rb') as f:
        header=f.read(24)
        if len(header)!=24: raise ValueError('File is too short for a classic PCAP header.')
        magic=header[:4]
        formats={b'\xd4\xc3\xb2\xa1':'<',b'\xa1\xb2\xc3\xd4':'>',b'\x4d\x3c\xb2\xa1':'<',b'\xa1\xb2\x3c\x4d':'>'}
        if magic not in formats: raise ValueError('Unsupported capture. Use classic .pcap (not pcapng).')
        endian=formats[magic]
        linktype=struct.unpack(endian+'I',header[20:24])[0]
        packets=0; bytes_total=0; protocols={}; endpoints={}; rows=[]
        while packets<limit:
            ph=f.read(16)
            if not ph: break
            if len(ph)<16: break
            ts_sec,ts_usec,incl,orig=struct.unpack(endian+'IIII',ph)
            data=f.read(incl)
            if len(data)<incl: break
            packets+=1; bytes_total+=orig
            proto='OTHER'; src=dst=''
            if linktype==1 and len(data)>=14:
                etype=struct.unpack('!H',data[12:14])[0]; off=14
                if etype==0x0800 and len(data)>=34:
                    ihl=(data[14]&15)*4; proto_num=data[23]
                    src=socket.inet_ntop(socket.AF_INET,data[26:30]); dst=socket.inet_ntop(socket.AF_INET,data[30:34]); off=14+ihl
                    proto={1:'ICMP',6:'TCP',17:'UDP'}.get(proto_num,'IPv4')
                    if proto_num in (6,17) and len(data)>=off+4:
                        sport,dport=struct.unpack('!HH',data[off:off+4]); src+=f':{sport}'; dst+=f':{dport}'
                elif etype==0x86dd and len(data)>=54:
                    src=socket.inet_ntop(socket.AF_INET6,data[22:38]); dst=socket.inet_ntop(socket.AF_INET6,data[38:54]); proto_num=data[20]
                    proto={6:'TCP',17:'UDP',58:'ICMPv6'}.get(proto_num,'IPv6')
                elif etype==0x0806: proto='ARP'
            protocols[proto]=protocols.get(proto,0)+1
            for ep in (src,dst):
                if ep: endpoints[ep]=endpoints.get(ep,0)+1
            if len(rows)<12: rows.append({'time':ts_sec+ts_usec/1e6,'protocol':proto,'source':src or '-','destination':dst or '-','length':orig})
        return {'packets':packets,'bytes':bytes_total,'protocols':protocols,'endpoints':endpoints,'rows':rows,'linktype':linktype,'truncated':packets>=limit}


def wifi_scan_windows() -> List[Dict[str,str]]:
    if sys.platform!='win32': raise RuntimeError('Wi-Fi scan is available on Windows only.')
    cp=subprocess.run(['netsh','wlan','show','networks','mode=bssid'],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=15)
    if cp.returncode: raise RuntimeError(cp.stderr.strip() or 'netsh WLAN scan failed. Check that Wi-Fi is enabled.')
    networks=[]; current=None
    # netsh output is localized; parse common English labels and fall back to line labels.
    for raw in cp.stdout.splitlines():
        line=raw.strip()
        if line.lower().startswith('ssid ') and ':' in line:
            if current: networks.append(current)
            current={'ssid':line.split(':',1)[1].strip() or '(hidden)','security':'Unknown','signal':'?','channel':'?','bssid':''}
        elif current and ':' in line:
            k,v=[x.strip() for x in line.split(':',1)]
            kl=k.lower()
            if kl in ('authentication','authentifizierung','autenticación','autenticacion'): current['security']=v
            elif kl in ('signal','signalstärke','señal'): current['signal']=v
            elif kl in ('channel','kanal','canal'): current['channel']=v
            elif kl in ('bssid','physical address','dirección física','direccion fisica'): current['bssid']=v
    if current: networks.append(current)
    # Mark open networks based on common localized labels.
    for n in networks:
        s=n['security'].lower()
        n['open']='yes' if any(x in s for x in ('open','abierta','offen')) or s in ('none','sin seguridad') else 'no'
    return networks


def local_network_info() -> Dict[str,str]:
    host=socket.gethostname()
    try: ip=socket.gethostbyname(host)
    except OSError: ip='Unavailable'
    gateway='Use Windows network settings'
    if sys.platform=='win32':
        try:
            cp=subprocess.run(['ipconfig'],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=8)
            lines=cp.stdout.splitlines()
            for i,line in enumerate(lines):
                if 'Default Gateway' in line or 'Puerta de enlace predeterminada' in line:
                    vals=[line.split(':',1)[-1].strip()]
                    if not vals[0] and i+1<len(lines): vals=[lines[i+1].strip()]
                    val=next((x for x in vals if x and ':' not in x), '')
                    if val: gateway=val; break
        except Exception: pass
    return {'hostname':host,'local_ip':ip,'gateway':gateway,'platform':platform.platform()}


def arp_table() -> str:
    if sys.platform=='win32': cmd=['arp','-a']
    else: cmd=['arp','-a']
    cp=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=8)
    if cp.returncode: return cp.stderr.strip() or 'ARP table unavailable.'
    return cp.stdout.strip() or 'ARP table is empty.'
