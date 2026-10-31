#!/bin/bash
# VHS accepts one shell executable. This wrapper loads demo/vhs_bashrc.
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
exec bash --rcfile "$root/demo/vhs_bashrc" -i
