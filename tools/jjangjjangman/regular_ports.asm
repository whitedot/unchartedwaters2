; nasm -f bin regular_ports.asm -o regular_ports.bin
bits 16
org 0
%define econ 0xfe40
%define defaults 0x800
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
jmp near ship_record
jmp near ship_stats
jmp near yard_list
jmp near yard_first
jmp near ship_art
jmp near figure_list
jmp near figure_effect
jmp near final_hull
jmp near preview_hull
jmp near location_marker
jmp near sell_index
jmp near yard_hull
jmp near figure_price
jmp near figure_row
jmp near gun_menu
jmp near selected_gun
jmp near fleet_day

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
 mov si,0xa00
 mov di,0xfc90
 mov cx,99 ; five 9-word gun tables and the terminated name
 cs rep movsb
 mov si,0x900
 mov di,0xfd00
 mov cx,256
 cs rep movsb
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
 cmp byte [padding+120*20],5
 je restore
 ; Refresh fixed specialty definitions for saves written by v1.4.
 mov si,defaults+24
 mov di,econ+24
 cs movsw
 cs movsw
 add si,70
 add di,70
 cs movsw
 cs movsw
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
 mov byte [padding+120*20],5
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
; The stack grows below the gun tables at FC90, ship catalog at FD00,
; and port records at FE00.
boot:
 pop ax
 pop dx
 mov sp,0xfc90
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

; Model 25 and its template (instance 40+25) are independent of all
; stock models, and cargo and equipment IDs survive in native save slots.
ship_record:
 cmp al,65
 jne .stock
 mov ax,0xfd78
 retf
.stock: mov ah,25
 mul ah
 add ax,0x57ce
 retf
ship_stats:
 cmp al,25
 jne .stock
 mov ax,0xfd91
 retf
.stock: mov ah,12
 mul ah
 add ax,0x5e28
 retf
yard_list:
 shl si,cl
 add si,0xb752
 cmp byte [0xc3a],131
 jne .done
 mov si,0xfd9d
.done: retf
yard_first:
 shl bx,cl
 mov al,[bx+0xb752]
 cmp byte [0xc3a],131
 jne .done
 mov al,25
.done: retf
ship_art:
 shl ax,cl
 cmp bx,25
 jne .stock
 mov bx,65
 retf
.stock: add bx,28
 retf
figure_list:
 mov [bp-8],ax
 xor si,si
 cmp byte [0xc3a],131
 jne .done
 ; Keep the native selection, append the new fitting at Busan.
 mov bx,[bp-10]
 mov [0xfde8],bx
 inc word [bp-10]
.done: retf
figure_effect:
 mov al,[bx+0x1d]
 xor ah,ah
 cmp al,11
 jne .done
 dec ax
.done: retf
final_hull:
 mov bx,[bp-0xc]
 cmp byte [bp-3],25
 jne .done
 mov al,100
.done: mov [bx+3],al
 retf
preview_hull:
 idiv cx
 cmp byte [bp-8],25
 jne .done
 mov ax,100
.done: mov dx,100
 retf
location_marker:
 mov al,[0xc3a]
 cmp al,131
 jne .native
 mov al,125 ; unused supply-port mooring tag
.native: or al,128
 retf
sell_index:
 mov bl,[bp-2]
 xor bh,bh
 cmp bl,46
 jb .done
 ; Use regional prices for ginger and fish as the price references.
 mov bl,5
 cmp byte [bp-2],46
 je .done
 mov bl,12
.done: retf
yard_hull:
 idiv cx
 cmp byte [bp-0xe],25
 jne .store
 mov ax,100
.store: mov [bp-1],al
 retf
figure_price:
 mov [bp-1],cl
 xor ch,ch
 cmp cl,11
 jne .done
 dec cx ; same fitting price as the Goddess
.done: mov ax,cx
 retf
figure_row:
 lea ax,[si+1]
 mov bx,si
 cmp byte [0xc3a],131
 jne .done
 cmp si,[0xfde8]
 jne .done
 mov ax,11
.done: retf

gun_menu:
 mov dx,[bp-0x12]
 cmp byte [0xc3a],131
 jne .done
 mov bx,dx
 shl bx,1
 mov word [bx+0x574],8
 inc dx
.done: mov ax,0x91
 retf
selected_gun:
 mov [bp-7],al
 xor ah,ah
 mov [bp-0xa],ax
 retf

; The day loop tracks the current zero-based day in DS:0570. When day
; 10 or 20 ends, run only the four native fleet maintenance routines.
; The existing month boundary handles the third pass and the economy.
fleet_day:
 mov byte [0xc39],0
 cmp byte [0x570],9
 je .rebuild
 cmp byte [0x570],19
 jne .done
.rebuild:
 push bp
 mov bp,sp
 pusha
 ; These routines share the caller's native code segment. The saved IP
 ; points to file offset 1E4B8, immediately following the patched call.
%macro fleet_call 1
 mov ax,[bp+2]
 add ax,%1-0x1e4b8
 push cs
 call .enter_native
%endmacro
 fleet_call 0x1d07f ; merchant fleets
 fleet_call 0x1d173 ; convoys
 fleet_call 0x1d268 ; voyaging fleets
 fleet_call 0x1d71e ; appoint captains and relaunch
 popa
 pop bp
.done: retf
.enter_native:
 push word [bp+4]
 push ax
 retf
