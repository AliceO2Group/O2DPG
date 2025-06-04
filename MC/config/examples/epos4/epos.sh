#!/bin/sh
# Script based on CRMC example
# EPOS4 option files must contain ihepmc set to 2 to print HepMC
# data on stdout. -hepmc flag is not needed anymore, but -hepstd is fundamental
# in order not to print useless information on stdout (a z-*optns*.mtr file will be created)

optns="example"
seed=$(od -An -N2 -tu2 /dev/urandom | tr -d ' ')
EPOS4=""

if [ -z "$EPO4VSN" ]; then
    echo "Error: EPO4VSN environment variable is not set"
    exit 1
fi

if [ "$EPO4VSN" = "4.0.0" ]; then
    EPOS4="$EPOS4_ROOT/epos4/scripts/epos"
    export LIBDIR=$EPOS4_ROOT/epos4/bin
else
    EPOS4="$EPOS4_ROOT/bin/epos"
fi

# Check if the environment variable EPO4 is set (mandatory with o2dpg-sim-tests on CI machines)
# If not, set all the EPOS4 related variables, most likely they are unset as well.
if [ -z "${EPO4}" ]; then
    export OPT=./
    export HTO=./
    export CHK=./
    if [ "$EPO4VSN" = "4.0.0" ]; then
        export EPO4=$EPOS4_ROOT/epos4/
    else
        export EPO4=$EPOS4_ROOT/
    fi
fi

while test $# -gt 0 ; do
    case $1 in
        -i|--input)   optns=$2 ; shift ;;
        -s|--seed)    seed=$2 ; shift ;;
        -h|--help) usage; exit 0 ;;
    esac
    shift
done

if [ ! -f $optns.optns ]; then
    echo "Error: Options file $optns.optns not found"
    exit 2
fi

if grep -Fq "set ihq 1" $optns.optns; then
    if [ -z "$EPO4HQVSN" ]; then
        # Error: EPOS4HQ version not found
        exit 3
    else
        # Running with EPOS4HQ
        if [ -z "${EPO4HQ}" ]; then
            export EPO4HQ=$EPOS4HQ_ROOT/
        fi
        EPOS4="$EPO4HQ/bin/eposhq"
    fi
fi

if [ $seed -eq 0 ]; then
    # Seed can't be 0, random number will be used
    seed=$(od -An -N2 -tu2 /dev/urandom | tr -d ' ')
fi

# OR filters the stdout with only HepMC useful data
$EPOS4 -hepstd -s $seed $optns | sed -n 's/^\(HepMC::\|[EAUWVP] \)/\1/p'