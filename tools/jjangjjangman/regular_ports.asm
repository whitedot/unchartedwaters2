; nasm -f bin regular_ports.asm -o regular_ports.bin
bits 16
org 0
%define econ 0xfe40
%define defaults 0x500
%define extra 0xfe00
%define ports (extra-130*20)
%define padding (0x5f54+18)
jmp near regular
jmp near entrance
jmp near tiles
jmp near profile
jmp near script_profile
jmp near monthly
jmp near daily
jmp near new_game
jmp near load_game
jmp near save_game
jmp near national_totals
jmp near region_totals
jmp near region_list
jmp near get_port_far
jmp near script_port
jmp near known_ports
jmp near coordinate_ports
jmp near chart_ports
jmp near lookout_ports
jmp near name_ports
jmp near locate
jmp near boot
jmp near new_hook
jmp near load_hook
jmp near save_hook

regular:
 push ax
 mov al,[0xc3a]
 cmp al,100
 jb .done
 sub al,130
 cmp al,3
.done: pop ax
 retf

entrance:
 cmp al,130
 jae .done
 cmp al,100
 jbe .done
 mov al,100
.done: retf

tiles:
 mov al,[0xc3a]
 xor ah,ah
 mov di,ax
 cmp al,130
 jb .original
 mov al,4
 retf
.original: mov al,[bp+di-0x6c]
 retf

profile:
 call get_profile
 retf
script_profile:
 mov al,[bp-1]
 call get_profile
 mov si,ax
 retf
get_profile:
 cmp al,130
 jb .original
 cmp al,132
 ja .original
 sub al,130
 mov ah,37
 mul ah
 add ax,econ
 ret
.original:
 mov ah,37
 mul ah
 add ax,0x697c
 ret

monthly:
 add di,37
 mov si,[bp-8]
 inc si
 cmp si,100
 jne .end
 mov di,econ
.end: cmp si,103
 retf
daily:
 add di,37
 add si,20
 inc byte [bp-3]
 cmp byte [bp-3],100
 jne .end
 mov si,ports+130*20
 mov di,econ
 mov byte [bp-3],130
.end: cmp byte [bp-3],133
 retf

%macro preserve 0
 pushf
 pusha
 push es
 push ds
 pop es
 cld
%endmacro
restore:
 pop es
 popa
 popf
 ret
init_ports:
 mov si,defaults+111
 mov di,extra
 mov cx,60
 cs rep movsb
 mov di,0xfeb0
 mov cx,11
 cs rep movsb
 mov di,extra+19
 mov si,padding
 mov cx,3
.flags:
 mov al,[si]
 and al,0x50
 or al,0x16
 stosb
 add di,19
 add si,20
 loop .flags
 ret
new_game:
 preserve
 call init_ports
.init:
 mov si,defaults
 mov di,econ
 mov cx,111
 cs rep movsb
 jmp restore
load_game:
 preserve
 call init_ports
 cmp byte [padding+118*20],'K'
 jne .legacy
 cmp byte [padding+119*20],'4'
 jne .legacy
 mov si,padding+3*20
 mov di,econ
 mov cx,111
.read: movsb
 add si,19
 cmp si,padding+53*20
 jne .read_next
 add si,20
.read_next: loop .read
 mov di,ports+130*20+19
 mov cx,3
.flags: movsb
 add si,19
 add di,19
 loop .flags
 jmp restore
.legacy:
 cmp byte [0xc3a],130
 jb new_game.init
 cmp byte [0xc3a],132
 ja new_game.init
 mov byte [0xc3b],255
 jmp new_game.init
save_game:
 preserve
 mov si,extra+19
 mov di,padding
 mov cx,3
.legacy_flags:
 mov al,[si]
 and al,0x50
 stosb
 add di,19
 add si,20
 loop .legacy_flags
 mov byte [padding+118*20],'K'
 mov byte [padding+119*20],'4'
 mov si,econ
 mov di,padding+3*20
 mov cx,111
.write: movsb
 add di,19
 cmp di,padding+53*20
 jne .write_next
 add di,20
.write_next: loop .write
 mov si,ports+130*20+19
 mov cx,3
.flags: movsb
 add si,19
 add di,19
 loop .flags
 jmp restore

; Economic totals and the regional port list walk two separate native tables.
%macro advance_tables 0
 add di,20
 add si,37
 cmp si,0x697c+100*37
 jne %%done
 mov di,ports+130*20
 mov si,econ
%%done:
%endmacro
national_totals:
 advance_tables
 inc word [bp-8]
 cmp word [bp-8],103
 retf
region_totals:
 advance_tables
 inc word [bp-4]
 cmp word [bp-4],103
 retf
region_list:
 advance_tables
 inc byte [bp-1]
 retf

get_port_far:
 call get_port
 retf
script_port:
 mov al,[bp-1]
 call get_port
 mov si,ax
 retf
get_port:
 mov ah,20
 mul ah
 cmp ax,130*20
 jb .original
 cmp ax,133*20
 jae .original
 add ax,ports
 ret
.original:
 add ax,0x5f54
 ret

; The far call replaces CMP + a short conditional branch. On a taken
; branch, advance the return IP from the byte after CALL to its target.
%macro branch_taken 1
 push bp
 mov bp,sp
 add word [bp+2],%1
 pop bp
 retf
%endmacro
known_ports:
 cmp si,130
 jne .test
 mov word [bp-2],extra
.test: cmp si,133
 jge .end
 branch_taken (0x181d3-0x181ef)
.end: retf

%macro scan_ports 3
%1:
 cmp di,130
 jne %%test
 mov si,extra
%%test: cmp di,133
 jl %%next
 branch_taken (%3-(%2+5))
%%next: retf
%endmacro
scan_ports coordinate_ports,0x208ea,0x20909
scan_ports chart_ports,0x24b54,0x24bbc
scan_ports lookout_ports,0x35bd3,0x35c31
name_ports:
 inc byte [bp-1]
 add si,20
 cmp byte [bp-1],130
 jne .end
 mov si,extra
.end: retf

locate:
 push bx
 push cx
 push si
 xor bx,bx
 mov cx,133
 mov si,0x5f54
.next:
 cmp [si],ax
 jne .skip
 cmp [si+2],dx
 je .found
.skip:
 add si,20
 inc bx
 cmp bx,130
 jne .advance
 mov si,extra
.advance: loop .next
 mov bx,-1
.found: mov ax,bx
 pop si
 pop cx
 pop bx
 retf

; The C runtime has already based the DOS arenas on the original SP.
; Before main, reserve the top 0x100 bytes for the three mutable records,
; their economies and WALK.KEY. The native stack only grows below FE00.
boot:
 pop ax
 pop dx
 mov sp,extra
 push ss
 pop ds
 push word [0xbd5b]
 push dx
 push ax
 retf
new_hook:
 call new_game
 lea bx,[0x092c]
 retf
load_hook:
 call load_game
 test byte [0xc30],0x42
 retf
save_hook:
 call save_game
 mov ax,0x8b6c
 sub ax,0x0c30
 retf
