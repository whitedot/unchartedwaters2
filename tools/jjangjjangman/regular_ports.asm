; nasm -f bin regular_ports.asm -o regular_ports.bin
bits 16
org 0xd400
%define econ 0xd270
%define defaults 0xd300
%define ports 0xc800
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
new_game:
 preserve
.init:
 mov si,defaults
 mov di,econ
 mov cx,111
 rep movsb
 jmp restore
load_game:
 preserve
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
