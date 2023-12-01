#!/usr/bin/env bash

# script to check for indication of failure in a file
# and to report on the first error

filetocheck=$1
if [ ! "${filetocheck}" ]; then
  echo "Specify a file to search"
  exit 1
fi

# list of typical failure patterns (append if needed)
pattern="-e \"\<[Ee]xception\"                         \
         -e \"segmentation violation\"                 \
         -e \"error while setting up workflow\"        \
         -e \"bus error\"                              \
         -e \"Assertion.*failed\"                      \
         -e \"Fatal in\"                               \
         -e \"libc++abi.*terminating\"                 \
         -e \"There was a crash.\"                     \
         -e \"arrow.*Check failed\"                    \
         -e \"terminate called after\"                 \
         -e \"terminate called without an active\"     \
         -e \"\]\[FATAL\]\"                            \
         -e \"\*\*\* Program crashed\"                 \
         -e \"\*\*\* Error in\"" # <--- LIBC fatal error messages

CMD="grep -m 1 -B2 -A10 ${pattern} $filetocheck"
T=$(eval "${CMD}")
if [ "$?" -eq 0 ]; then
  echo ""
  echo "==============================ERROR in ${filetocheck} =============================="
  echo ""
  echo "${T}"
fi