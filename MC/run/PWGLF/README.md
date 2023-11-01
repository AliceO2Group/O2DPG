# Run script for PWG-LF MC injector

Simple script to run the PWG-LF MC injector.

The configuration file is stored in the ini directory: [O2DPG/MC/config/PWGLF/](O2DPG/MC/config/PWGLF/)
 - ini/***.ini: configuration file for the MC injector
 - pythia8/generator/***.gun: configuration file for the Pythia8 gun
 - pythia8/generator/***.cfg: configuration file for the Pythia8 generator (custom decay table if needed)
## Usage
```
cd {O2DPG_ROOT}/MC/run/PWGLF
./runLFInjector.sh ${O2DPG_ROOT}/MC/config/PWGLF/ini/GeneratorLFDeTrHe_pp.ini # For nuclei injection
./runLFInjector.sh ${O2DPG_ROOT}/MC/config/PWGLF/ini/GeneratorLF_Resonances_pp.ini # For resonance injection
```
## Configuration
The following variables can be set from the outside:
 - `NWORKERS`: number of workers to use (default 8)
 - `MODULES`: modules to be run (default "--skipModules ZDC")
 - `SIMENGINE`: simulation engine (default TGeant4)
 - `NSIGEVENTS`: number of signal events (default 1)
 - `NBKGEVENTS`: number of background events (default 1)
 - `NTIMEFRAMES`: number of time frames (default 1)
 - `INTRATE`: interaction rate (default 50000)
 - `SYSTEM`: collision system (default pp)
 - `ENERGY`: collision energy (default 900)
 - `CFGINIFILE`: path to the ini file (example ${O2DPG_ROOT}/MC/config/PWGLF/ini/GeneratorLFDeTrHe_pp.ini)
 - `SPLITID`: split ID (default "")
 - `O2_SIM_WORKFLOW`: path to the workflow script (default ${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py)
 - `O2_SIM_WORKFLOW_RUNNER`: path to the workflow runner script (default ${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py)
Example:
```
export NWORKERS=4
export NSIGEVENTS=10
export SIMENGINE=TGeant3
./runLFInjector.sh ${O2DPG_ROOT}/MC/config/PWGLF/ini/GeneratorLFDeTrHe_pp.ini
```
