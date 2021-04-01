#!/usr/bin/env python3

#
# A script producing a consistent MC->RECO->AOD workflow
# with optional embedding with parameters for PWGHF.
# 

import os
import sys

# we simply delegate to main script with some PWGHF settings
command='${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py -eCM 13000 -col pp -proc ccbar --embedding '

# and add given user options
for i in range(1, len(sys.argv)):
   command += sys.argv[i]
   command += ' '

os.system(command)
