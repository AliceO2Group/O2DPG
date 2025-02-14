# Source path for the script
# source  $NOTES/JIRA/ATO-648/workflowToJSON.sh

# Description:
# This script converts workflow configuration logs into a structured JSON format for enhanced data analysis and readability.

# Usage:
# Example: source $O2DPG/UTILS/Parsers/workflowToJSON.sh

alias helpCat=cat
[[ -x "$(command -v pygmentize)" ]] && alias helpCat="pygmentize -O style=borland,linenos=1 -l bash"

function helpCat0() {
    local language="$1"
    shift
    [[ -x "$(command -v pygmentize)" ]] && pygmentize -O style=monokai,linenos=1 -l "$language" | cat - "$@"
    [[ ! -x "$(command -v pygmentize)" ]] && cat - "$@"
}

init648() {
  cat <<HELP_USAGE | helpCat
      Function Overview: init648

      This function initializes the script environment and provides access to a series of utility commands designed to assist in handling and transforming workflow logs.

      Available Commands:
      - \[init648]: Initializes the necessary environment settings for script execution. Use this before running other related functions to ensure all configurations are correctly set.
      - \[description]: Provides a comprehensive explanation of the workflow processing, detailing each step and its purpose within the system.
      - \[makeParse]: Executes the log parsing process, transforming verbose workflow logs into a structured JSON format, facilitating easier data manipulation and analysis.
      - \[makeDiffExample]: Demonstrates how to compare two JSON files derived from workflow logs, highlighting differences.

      Usage:
      To learn more about each command, type the command followed by 'help'. This will display detailed information about the command's function and usage examples.

      Example:
        \$ init648 help   # Displays help information for the init648 command.

      Note: Tests were conducted in the directory:
HELP_USAGE
}

description() {
cat <<HELP_USAGE | helpCat0 bash
Description:
This script parses 'workflowconfig.log' files, which contain lines of commands complete with switches and configuration settings. It is designed to transform these log entries into a structured JSON format, making the data easier to manipulate and read.

Purpose:
- To convert workflow configuration logs into a JSON structure where each command, along with its switches and key values, is represented as an object within an array. This facilitates easier data manipulation and readability.

Structure of Log Entries:
- Each line in the log file represents a single command with its options, structured as follows:
  <commandName> <switches> --configKeyValues

Example Command:
A typical command in the log might appear like this:
o2-ctf-reader-workflow --session default_1304519_3825 --severity info --shm-segment-id 0 --shm-segment-size 64000000000 --resources-monitoring 50 --resources-monitoring-dump-interval 50 --early-forward-policy noraw --fairmq-rate-logging 0 --timeframes-rate-limit 2 --timeframes-rate-limit-ipcid 0 --ans-version compat --delay 1 --loop 0 --max-tf 2 --ctf-input list.list --onlyDet ITS,TPC,TOF,FV0,FT0,FDD,TRD,CTP --pipeline tpc-entropy-decoder:1 --allow-missing-detectors --its-digits --mft-digits --configKeyValues "keyval.input_dir=/tmp/tmp.rgwfzmuG63;keyval.output_dir=/dev/null;;"

Transformation:
This script processes each command line from the log, turning them into JSON objects. This structural change not only organizes the data but also enhances accessibility for programmatic queries and analysis.
HELP_USAGE
}


makeParse() {
    # Use heredoc to send help text through helpCat alias, which will apply syntax highlighting if pygmentize is available.
    if [[ -z "$1" ]]; then
        # Use heredoc to send help text through helpCat alias, which will apply syntax highlighting if pygmentize is available.
        cat <<'HELP_USAGE' | helpCat0 bash
makeParse: Parse the workflow log and create an output.json file.
Usage:
    makeParse <workflowconfig.log>

Example usage:
    #makeParse workflowconfig.log  > ~/output.json            # To parse a specific log file.
    makeParse /lustre/alice/tpcdata/Run3/SCDprodTests/fullRec/PbPb_Streamers_Tune_ClusterErrors-merge-streamer/avgCharge_fullTPC_sampling_TimeBins16-Average0_rejectEdgeCl-Seed0-Track0-margin0/LHC23zzh.b5p/544116.38kHz/0110/workflowconfig.log  > workflow.json
    cat workflow.json | jq '.[] | select(.command | test("^o2-dpl"))'   # Filter DPL workflows.
    jq '.[] | select(.command | test("^o2-gpu"))' workflow.json  # Filter GPU related commands.

HELP_USAGE
        return  # Exit the function if no parameters provided
    fi
    #
    log_file=$1
jq -Rn '
  [inputs | split("\n")[] | select(length > 0 and startswith("o2-")) |
    {
      command: (split(" ")[0]),
      switches: (split(" ") | .[1:-1] |
        reduce .[] as $item ({};
          if $item | startswith("--") then
            if $item | contains("=") then
              . + ({($item | ltrimstr("--") | split("=")[0]): ($item | split("=")[1])})
            else
              . + ({($item | ltrimstr("--")): true})
            end
          else
            .[keys_unsorted[-1]] = $item
          end
        )),
        configKeyValues: (if (contains("--configKeyValues")) then
        (split("--configKeyValues")[1] | split("|")[0] | gsub("^\\s+\"|\"\\s+;"; "") | split(";") |
        map(select(. != "" and contains("="))) |
        map(split("=") | select(length == 2)) |
        map({(.[0]): .[1]})) | add
      else
        {}
      end
      )
    }
  ]' "$log_file"
}

makeDiffExample(){
  cat <<HELP_USAGE | helpCat
Description:

This function provides examples of how to parse workflow configuration logs into JSON format and then compare these JSON files using \`diff\`. The comparison can be done directly using \`jq\` to filter and sort the JSON data, which helps in identifying the differences more clearly.

Examples:

1. Parse workflow configuration logs into JSON format:
   \`makeParse /lustre/alice/tpcdata/Run3/SCDprodTests/fullRec/PbPb_Streamers_Tune_ClusterErrors-merge-streamer/avgCharge_fullTPC_sampling_TimeBins16-Average0_rejectEdgeCl-Seed0-Track0-margin0/LHC23zzh.b5p/544116.38kHz/0110/workflowconfig.log  > workflow0.json\`

   \`makeParse /lustre/alice/tpcdata/Run3/SCDprodTests/fullRec/PbPb_Streamers_Tune_ClusterErrors-merge-streamer/avgCharge_fullTPC_sampling_TimeBins16-Average0_rejectEdgeCl-Seed0-Track0-margin0-ref/LHC23zzh.b5p/544116.38kHz/0110/workflowconfig.log  > workflow1.json\`

2. Compare two JSON files using \`jq\` and \`diff\` directly without temporary files:
   \diff <(jq --sort-keys . workflow1.json) <(jq --sort-keys . workflow0.json)\

3. Use \`diff\` with side-by-side view and color using ANSI color codes:
   \`diff --side-by-side --left-column --color=always <(jq --sort-keys . workflow1.json) <(jq --sort-keys . workflow0.json) | less -R\`

4. Compare JSON files focusing only on commands starting with "o2-gpu":
   Filtering the entries where the command starts with "o2-gpu" and then comparing:
   \ diff --side-by-side --left-column --color=always  <(jq '.[] | select(.command | test("^o2-gpu"))' workflow1.json | jq --sort-keys .)  <(jq '.[] | select(.command | test("^o2-gpu"))' workflow0.json | jq --sort-keys .) | less -R
HELP_USAGE
}

init648