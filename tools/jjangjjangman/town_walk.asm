; nasm -f bin town_walk.asm -o town_walk.bin
bits 16
; The town loop has already polled the DOS keyboard into [bp-1].
mov al, [bp-1]
test al,al
jz poll
cmp al,0x1c
jb done
cmp al,0x1f
jbe poll
cmp al,'1'
jb done
cmp al,'9'
ja done
poll:
; DOS reads one byte from the emulator’s in-memory WALK.KEY.
; An absent file or neutral input preserves a queued key tap.
mov dx,0xc700
mov ax,0x3d00
int 0x21
jc done
mov bx,ax
mov dx,0xc709
mov cx,1
mov ah,0x3f
int 0x21
jc close_file
cmp ax,1
jne close_file
mov al,[0xc709]
test al,al
jz close_file
mov [bp-1],al
close_file:
mov ah,0x3e
int 0x21
done:
jmp continue_input
times 0x48-($-$$) db 0x90
timer:
; Original timer is 8 or 4 ticks (graphics delay on or off).
; Use 4 or 2 for movement and the original period for idle turns.
mov al,[0xc30]
and ax,1
inc ax
shl ax,1
cmp byte [bp-1],0
je idle
test di,di
jnz timer_done
idle:
shl ax,1
timer_done:
ret
times 0x64-($-$$) db 0x90
continue_input:
