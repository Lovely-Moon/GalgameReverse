 # -*- coding: utf-8 -*-
import os
import math
import re
import struct
import codecs
import numpy as np
import cv2
from PIL import ImageFont, ImageDraw, Image 
"""
Utils for extracting, building tile font, or generating font picture.
And something about tbl.

v0.1 initial version
v0.1.5 add function save_tbl, fix px48->pt error
"""

def generate_gb2312_tbl(outpath=r""):
    tbl = []
    for low in range(0x20, 0x7f): # asci
        charcode = struct.pack('<B', low)
        tbl.append((charcode, charcode.decode('gb2312')))
    
    for low in range(0xa1, 0xfe): # Punctuation
        charcode = struct.pack('<BB', 0xa1, low)
        tbl.append((charcode, charcode.decode('gb2312')))
    
    for low in range(0xa1, 0xfe): # fullwidth chractor
        charcode = struct.pack('<BB', 0xa3, low)
        tbl.append((charcode, charcode.decode('gb2312')))

    for low in range(0xa1, 0xf4): # hirakana
        charcode = struct.pack('<BB', 0xa4, low)
        tbl.append((charcode, charcode.decode('gb2312')))

    for low in range(0xa1, 0xf7): # katakana 
        charcode = struct.pack('<BB', 0xa5, low)
        tbl.append((charcode, charcode.decode('gb2312')))

    for high in range(0xb0, 0xf8): # Chinese charactor
        for low in range(0xa1, 0xff):
            if high == 0xd7 and 0xfa <= low <= 0xfe: continue
            charcode = struct.pack('<BB', high, low)
            tbl.append((charcode, charcode.decode('gb2312')))

    if outpath!="":
        with codecs.open(outpath, "w", encoding='utf-8') as fp:
            for charcode, c in tbl:
                if len(charcode) == 1:
                    d = struct.unpack('<B', charcode)[0]
                elif len(charcode) == 2:
                    d = struct.unpack('>H', charcode)[0]
                fp.writelines("{:X}={:s}\n".format(d, c))
    print("gb2312 with " + str(len(tbl)) + " generated!")
    return tbl

def load_tbl(inpath, encoding='utf-8'):
    tbl = []
    with codecs.open(inpath, 'r', encoding=encoding) as fp:
        re_line = re.compile(r'([0-9|A-F|a-f]*)=(\S|\s)$')
        while True:
            line = fp.readline()
            if not line : break
            m = re_line.match(line)
            if m is not None:
                d = int(m.group(1), 16)
                if d<0xff:
                    charcode = struct.pack("<B", d)
                elif d>0xff and d<0xffff:
                    charcode = struct.pack(">H", d)
                else:
                    charcode = struct.pack(">BBB", d>>16, (d>>8)&0xff, d&0xff)
                #print(m.group(1), m.group(2), d)
                c = m.group(2)
                tbl.append((charcode, c))
    print(inpath + " with " + str(len(tbl)) +" loaded!")
    return tbl

def save_tbl(tbl, outpath="out.tbl", encoding='utf-8'):
    with codecs.open(outpath, "w", encoding='utf-8') as fp:
        for charcode, c in tbl:
            if len(charcode) == 1:
                d = struct.unpack('<B', charcode)[0]
            elif len(charcode) == 2:
                d = struct.unpack('>H', charcode)[0]
            fp.writelines("{:X}={:s}\n".format(d, c))
        print("tbl with " + str(len(tbl)) + " saved!")

def tilefont2bgra(data, char_height, char_width, bpp, n_row=64, n_char=0, f_decode=None):
    def f_decode_default(data, bpp, idx):
        b=g=r=a = 0
        start = int(idx)
        if bpp==4:
            a = 255
            d = struct.unpack('<B', data[start:start+1])[0]
            if idx > start:  d >>= 4
            else: d &= 0b00001111
            r = g = b = round(d*255/15)
        elif bpp==8:
            a = 255
            r = b = g = struct.unpack('<B', data[start:start+1])[0]
        else:
            print("Invalid bpp value!")
            return None
        return np.array([b, g, r, a], dtype='uint8')

    n =  math.floor(len(data)*8/bpp/char_height/char_width)
    if n_char!=0 and n_char < n: n = n_char
    width = char_width * n_row
    height = char_height * math.ceil(n/n_row)
    bgra = np.zeros([height, width, 4], dtype='uint8')
    if f_decode is None: f_decode = f_decode_default
    print("%dX%d %dbpp %d tile chars -> %dX%d image"
          %(char_width, char_height, bpp, n, width, height))

    for i in range(n):
        for y in range(char_height):
            for x in range(char_width):
                idx_y = (i//n_row)*char_height + y
                idx_x = (i%n_row)*char_width + x
                idx = (i*char_height*char_width + y * char_height + x)*bpp/8
                bgra[idx_y][idx_x]=f_decode(data, bpp, idx)

    return bgra

def bgra2tilefont(bgra, char_height, char_width, bpp, n_row=64, n_char=0, f_encode=  None):
    def f_encode_default(data, bgra, bpp, idx, idx_x, idx_y):
        if bgra.shape[2] == 4:
            b, g , r, _ = bgra[idx_y][idx_x].tolist()
        else: 
            b, g, r = bgra[idx_y][idx_x].tolist()
            # a = 255

        start = int(idx)
        if bpp==4:
            d = round((r+b+g)/3*15/255)
            if idx > start:
                data[start] = (data[start] & 0b00001111) + (d<<4)
            else:
                data[start] = (data[start] & 0b11110000) + d
        elif bpp==8:
            struct.pack('<B', data[start:start+1], round((r+b+g)/3))
        else:
            print("Invalid bpp value!")
            return None

    height, width, _ = bgra.shape
    n = (height/char_height) * (width/char_width) 
    if n_char != 0 and n_char < n: n = n_char
    size = math.ceil(n*bpp/8*char_height*char_width) 
    data = bytearray(size)
    if f_encode is None: f_encode=f_encode_default
    print("%dX%d image -> %dX%d %dbpp %d tile chars, %d bytes"
          %(width, height, char_width, char_height, bpp, n, size))

    for i in range(n):
        for y in range(char_height):
            for x in range(char_width):
                idx_y = (i//n_row)*char_height + y
                idx_x = (i%n_row)*char_width + x
                idx =  (i*char_height*char_width + y * char_height + x)*bpp/8
                f_encode(data, bgra, bpp, idx, idx_x, idx_y)

    return data

def extract_tilefont(inpath, char_height, char_width, bpp, outpath=r".\out.png", n_row=64, n_char=0, addr=0, f_decode=None):
    with open(inpath, 'rb') as fp:
        fp.seek(addr)
        data = fp.read()
        bgra = tilefont2bgra(data, char_height, char_width, bpp, n_row=n_row, n_char=n_char, f_decode=f_decode)
        cv2.imwrite(outpath, bgra)
        print(outpath + " extracted!")

def build_tilefont(inpath, char_height, char_width, bpp, outpath=r".\out.bin", n_row=64, n_char=0, f_encode=None):
    bgra = cv2.imread(inpath, cv2.IMREAD_UNCHANGED)
    data = bgra2tilefont(bgra, char_height, char_width, bpp, n_row=n_row, n_char=n_char, f_encode=f_encode)
    with open(outpath, 'wb') as fp:
        fp.write(data)
    print(outpath + " tile font built!")

def build_picturefont(ttfpath, tblpath, char_width, char_height, n_row, outpath="", padding=(0,0,0,0)):
    """
    :param padding: (up, down, left, right)
    """

    tbl = load_tbl(tblpath)
    n = len(tbl)
    width = n_row*char_width + padding[2] + padding[3]
    height = math.ceil(n/n_row)*char_height + padding[0] + padding[1]
    img = np.zeros((height, width, 4), dtype=np.uint8)
    print("to build picture %dX%d with %d charactors..."%(width, height, n))
    
    ptpxmap = {8:6, 9:7, 16:12, 18:13.5, 24:18, 32:24, 48:36}
    font = ImageFont.truetype(ttfpath, ptpxmap[char_height])
    imgpil = Image.fromarray(img)
    draw = ImageDraw.Draw(imgpil)

    for i in range(n):
        c = tbl[i][1]
        x = (i%n_row)*char_width + padding[2]
        y = (i//n_row)*char_height + padding[0]
        draw.text([x,y], c, fill=(255,255,255,255), font=font)

    if outpath!="": imgpil.save(outpath)
    return np.array(imgpil)