#!/bin/bash

diff /tools/gtkwave/_install/gtkwave-gtk3-3.3.98/src/tcl_commands.c /tools/gtkwave/_install/gtkwave-gtk3-3.3.98_ch/src/tcl_commands.c > tcl_commands.diff

diff /tools/gtkwave/_install/gtkwave-gtk3-3.3.98/src/main.c /tools/gtkwave/_install/gtkwave-gtk3-3.3.98_ch/src/main.c > main.diff

diff /tools/gtkwave/_install/gtkwave-gtk3-3.3.98/src/signalwindow.c /tools/gtkwave/_install/gtkwave-gtk3-3.3.98_ch/src/signalwindow.c > signalwindow.diff
