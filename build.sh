#!/bin/bash
#Builds a PEX executable.
#Requires the virtualenv to be active (to find pex).
pex -r <(grep -v pex requirements.txt) gflow -e gflow -o gflow.pex
