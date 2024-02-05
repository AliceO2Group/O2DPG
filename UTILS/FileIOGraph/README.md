This is a small custom tool to monitor file access
and to produce graphs of file production and file consumption
by O2DPG Monte Carlo tasks. Such information can be useful for

(a) verification of data paths
(b) early removal of files as soon as they are not needed anymore


In more detail, core elements of this directory are

* monitor_fileaccess:

A tool, useable by root, providing reports about
read and write events to files and which process is involved.
The tool is based on the efficient fanotify kernel system and reporting
can be restricted to certain shells (by giving a mother PID).

The tool is standalone and can be compiled, if needed, by running

`g++ monitor_fileaccess.cpp -O2 -o monitor_fileaccess.exe`

The tool can be run simply by

```
sudo MAXMOTHERPID=689584 ./monitor.exe | tee /tmp/fileaccess
```

to monitor file events happening by child processes of shell 689584.


* analyse_FileIO.py:







