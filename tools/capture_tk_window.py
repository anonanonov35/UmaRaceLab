"""Capture only our Tk window through WM_PRINT, including when it is occluded."""
import ctypes as C
from ctypes import wintypes as W
from PIL import Image


def capture(window,path):
    window.update_idletasks()
    user=C.WinDLL('user32',use_last_error=True)
    gdi=C.WinDLL('gdi32',use_last_error=True)
    user.GetAncestor.argtypes=[W.HWND,W.UINT];user.GetAncestor.restype=W.HWND
    user.GetClientRect.argtypes=[W.HWND,C.POINTER(W.RECT)]
    user.GetDC.argtypes=[W.HWND];user.GetDC.restype=W.HDC
    user.ReleaseDC.argtypes=[W.HWND,W.HDC]
    user.PrintWindow.argtypes=[W.HWND,W.HDC,W.UINT]
    gdi.CreateCompatibleDC.argtypes=[W.HDC];gdi.CreateCompatibleDC.restype=W.HDC
    gdi.CreateCompatibleBitmap.argtypes=[W.HDC,C.c_int,C.c_int];gdi.CreateCompatibleBitmap.restype=C.c_void_p
    gdi.SelectObject.argtypes=[W.HDC,C.c_void_p];gdi.SelectObject.restype=C.c_void_p
    gdi.DeleteObject.argtypes=[C.c_void_p]
    gdi.DeleteDC.argtypes=[W.HDC]
    gdi.GetDIBits.argtypes=[W.HDC,C.c_void_p,W.UINT,W.UINT,C.c_void_p,C.c_void_p,W.UINT]
    hwnd=user.GetAncestor(window.winfo_id(),2)
    rect=W.RECT()
    if not user.GetClientRect(hwnd,C.byref(rect)):
        raise C.WinError(C.get_last_error())
    width,height=rect.right,rect.bottom
    dc=user.GetDC(hwnd)
    memory=gdi.CreateCompatibleDC(dc)
    bitmap=gdi.CreateCompatibleBitmap(dc,width,height)
    old=gdi.SelectObject(memory,bitmap)
    class Header(C.Structure):
        _fields_=[('size',W.DWORD),('width',W.LONG),('height',W.LONG),('planes',W.WORD),
                  ('bits',W.WORD),('compression',W.DWORD),('bytes',W.DWORD),
                  ('xppm',W.LONG),('yppm',W.LONG),('used',W.DWORD),('important',W.DWORD)]
    try:
        # PW_CLIENTONLY | PW_RENDERFULLCONTENT. No desktop pixels are read.
        if not user.PrintWindow(hwnd,memory,3):
            raise RuntimeError('PrintWindow failed; refusing desktop fallback')
        gdi.SelectObject(memory,old)
        header=Header(C.sizeof(Header),width,height,1,32,0,width*height*4,0,0,0,0)
        pixels=C.create_string_buffer(width*height*4)
        if gdi.GetDIBits(dc,bitmap,0,height,pixels,C.byref(header),0)!=height:
            raise RuntimeError('GetDIBits failed')
        Image.frombytes('RGB',(width,height),pixels.raw,'raw','BGRX',0,-1).save(path)
    finally:
        gdi.SelectObject(memory,old)
        gdi.DeleteObject(bitmap);gdi.DeleteDC(memory);user.ReleaseDC(hwnd,dc)
