This macro ReleaseValidation.C permits to compare the QC.root output from different passes


## Usage
The input variables which we need to give to the macro are:

- the two QC.root files, with corresponind path

- the Monitor object collection we want to focus on:
QcTaskMIDDigits;
DigitQcTaskFV0;
TaskDigits;
DigitQcTaskFT0;
QcMFTAsync;
ITSTrackTask;
MatchedTracksITSTPC;
MatchingTOF;
ITSClusterTask;
Clusters;
PID;
Tracks;
Vertexing 

- which compatibility test we want to perform (bit mask):
1->Chi-square;
2--> ContBinDiff;
3 (combination of 1 and 2)--> Chi-square+MeanDiff;
4-> N entries;
5 (combination of 1 and 4) --> Nentries + Chi2;
6 (combination of 1 and 2)--> N entries + MeanDiff;
7 (combination of 1, 2 and 3)--> Nentries + Chi2 + MeanDiff

- threshold values for checks on Chi-square and on content of bins

- choose if we want to work on the grid or on local laptop (to be fixed)

- tell the script it there are "critical "histograms (the list of names of critical plots has to be written in a txt file), which we need to keep separated from the other histograms. The corresponding plots will be saved in a separated pdf file


The macro is currently working only on real data (will be fixed soon)