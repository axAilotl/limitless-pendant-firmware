# install-ours.tcl — ERASEALL -> UICR debug-open words -> our loader -> our-signed
# app -> read both regions back -> reset only if every word matches.
#
# From this directory, after mkwords.py produced loader-words.tcl and app-words.tcl:
#   openocd -f swd.cfg -c init -c "source install-ours.tcl"
#
# The session stays attached. On VERIFY-FAILED the core is left halted
# (telnet 4444) and nothing is reset.

proc rdword {addr} { mem2array t 32 $addr 1; return [lindex $t 1] }

# Compare flash at $base against the word list $W, 1024 words per read.
proc check_words {name base} {
    global W
    set n [llength $W]
    set bad 0
    set seen 0
    set i 0
    while {$i < $n} {
        set cnt 1024
        if {$n - $i < $cnt} { set cnt [expr {$n - $i}] }
        foreach {idx val} [mem2array v 32 [expr {$base + 4*$i}] $cnt] {
            if {$val != [lindex $W [expr {$i + $idx}]]} { incr bad }
            incr seen
        }
        incr i $cnt
    }
    if {$seen != $n} { incr bad [expr {$n - $seen}] }
    echo "VERIFY $name: $bad mismatches in $n words"
    return $bad
}

echo "STAGE0: ERASEALL"
nrferaseall_noreset

echo "STAGE1: UICR debug-open words"
mww 0x50039504 1
while {[expr {[rdword 0x50039408] & 1}] == 0} { sleep 1 }
mww 0xFF8000 0x50fa50fa
while {[expr {[rdword 0x50039408] & 1}] == 0} { sleep 1 }
mww 0xFF801C 0x50fa50fa
while {[expr {[rdword 0x50039408] & 1}] == 0} { sleep 1 }
mww 0x50039504 0
echo "UICR: [format %x [rdword 0xFF8000]] [format %x [rdword 0xFF801C]]"

echo "STAGE2: loader"
source loader-words.tcl
set base 0x0
source write-words.tcl
set bad [check_words loader 0x0]

echo "STAGE3: app"
source app-words.tcl
set base 0x14000
source write-words.tcl
incr bad [check_words app 0x14000]

if {$bad == 0} {
    echo "VERIFY-OK: releasing the core"
    reset run
} else {
    echo "VERIFY-FAILED: $bad words differ; core left halted, session attached"
}
