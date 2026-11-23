# nrferaseall.tcl — CTRL-AP AP2 ERASEALL proc (app core only).
# Loaded by probe.cfg (baseline reads) and by restore-all.tcl (single-invocation run).
# Offsets per probe-rs nrf53_recover.rs + openocd nrf52_recover:
#   RESET@0x00, ERASEALL@0x04 (task: write 0 then 1), ERASEALLSTATUS@0x08,
#   APPROTECTSTATUS@0x0C, SECURELOCKSTATUS@0x10, IDR@0xFC.

proc nrferaseall {} {
    set dap ndap.dap
    set IDR [$dap apreg 2 0xfc]
    if {$IDR != 0x12880000} {
        echo "FATAL: CTRL-AP AP2 IDR = $IDR (expected 0x12880000)"
        shutdown error
    }
    echo "CTRL-AP AP2 IDR OK (0x12880000)"
    echo "PRE:  APPROTECTSTATUS=[$dap apreg 2 0x0c] SECURELOCKSTATUS=[$dap apreg 2 0x10]"
    echo "ERASEALL task trigger..."
    $dap apreg 2 4 0
    $dap apreg 2 4 1
    set t0 [ms]
    for {set i 0} {1} {incr i} {
        set ST [$dap apreg 2 8]
        if {$ST == 0} { echo "ERASEALL complete ([expr {[ms]-$t0}] ms, ${i} polls)"; break }
        if {$i >= 3000} {
            echo "FATAL: ERASEALL not complete after 5 min"
            shutdown error
        }
        sleep 100
    }
    echo "POST: APPROTECTSTATUS=[$dap apreg 2 0x0c] SECURELOCKSTATUS=[$dap apreg 2 0x10]"
    $dap apreg 2 0 1
    sleep 50
    $dap apreg 2 0 0
    $dap apreg 2 4 0
    sleep 100
    set idr0 [$dap apreg 0 0xfc]
    echo "window test: AP0 IDR = $idr0"
    if {$idr0 == 0x00000000 || $idr0 == 0xffffffff} {
        echo "FATAL: AP0 unreadable — window closed. Re-run nrferaseall to retry."
        shutdown error
    }
    echo "=== WINDOW OPEN (AP0 IDR=$idr0) ==="
}

proc nrferaseall_noreset {} {
    set dap ndap.dap
    set IDR [$dap apreg 2 0xfc]
    if {$IDR != 0x12880000} { echo "FATAL: AP2 IDR=$IDR"; shutdown error }
    echo "PRE:  APPROTECTSTATUS=[$dap apreg 2 0x0c] SECURELOCKSTATUS=[$dap apreg 2 0x10]"
    $dap apreg 2 4 0
    $dap apreg 2 4 1
    set t0 [ms]
    for {set i 0} {1} {incr i} {
        set ST [$dap apreg 2 8]
        if {$ST == 0} { echo "ERASEALL complete ([expr {[ms]-$t0}] ms)"; break }
        if {$i >= 3000} { echo "FATAL: ERASEALL timeout"; shutdown error }
        sleep 100
    }
    $dap apreg 2 4 0
    echo "POST: APPROTECTSTATUS=[$dap apreg 2 0x0c] SECURELOCKSTATUS=[$dap apreg 2 0x10]"
    # NO reset toggle: erased UICR re-arms protection on reset; window must
    # survive until flashing completes. Memory test replaces IDR test:
    if {[catch {ndap.cpu arp_examine} werr]} {
        echo "FATAL: examine failed after ERASEALL (window closed): $werr"
        shutdown error
    }
    echo "=== WINDOW OPEN (core examined) ==="
}
