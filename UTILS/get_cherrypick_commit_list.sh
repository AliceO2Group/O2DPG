#!/bin/bash

# given a commit cp_commit on branch source_branch as well
# as another branch target_branch, this script finds the list
# of all commits that are needed to succesfully cherry-pick cp_commit
# onto the target branch

cp_commit=$1        # Commit you want to cherry-pick
source_branch=$2    # Branch containing commit cp_commit (e.g., master)
target_branch=$3    # Branch you want to cherry-pick onto (e.g., foo)

# Check if all required arguments are provided
if [ -z "$cp_commit" ] || [ -z "$source_branch" ] || [ -z "$target_branch" ]; then
    echo "Usage: $0 <commit-hash-A> <source-branch> <target-branch>"
    exit 1
fi

# Function to check if two git commits modify at least one common file
modifies_common_files() {
    if [ "$#" -ne 2 ]; then
        echo "Usage: check_common_files <commit1> <commit2>"
        return 1
    fi

    local commit1="$1"
    local commit2="$2"

    # Get the list of modified files for each commit
    local files_commit1
    files_commit1=$(git diff --name-only "${commit1}^" "${commit1}")
    
    local files_commit2
    files_commit2=$(git diff --name-only "${commit2}^" "${commit2}")

    # Check for common files
    local common_files
    common_files=$(echo -e "${files_commit1}\n${files_commit2}" | sort | uniq -d)

    # Output result
    if [ -n "$common_files" ]; then
	return 1
    fi
    return 0
}

# function to check if 2 commits can be swapped. This can determine if a commit needs
# to come stricly before another commit.
can_swap_commits() {
    local commitA="$1"
    shift
    local commitB=("$@")   # this is the list of commits that should swap (as a whole) with commitA

    reverseCommitList=()

    # Loop through the original array in reverse order
    for ((i=${#commitB[@]}-1; i>=0; i--)); do
      reverseCommitList+=("${commitB[i]}")
    done

    # Create a temporary branch for testing
    local temp_branch="temp_swap_test_branch"

    # record current state
    GIT_CUR=$(git branch --show-current)
    # Create a new temporary branch from the current HEAD
    git checkout ${commitA}^ -b "$temp_branch" &> /dev/null

    RC=1
    for commit in "${reverseCommitList[@]}"; do
      # Cherry-pick commit B onto a branch without commitA
      if git cherry-pick "$commit" &> /dev/null; then
        # RC=1  # Commits can be swapped
	RC_local=1
      else
        RC=0  # Cannot swap due to conflict when cherry-picking B
        git cherry-pick --abort
      fi
    done
 
    # Cleanup: Reset to the original branch and delete the temp branch
    git checkout ${GIT_CUR} &> /dev/null
    git branch -D "$temp_branch" &>/dev/null
    return ${RC}
}

# Step 1: Identify branch-break off point
BRANCHPOINT=$(git merge-base "$source_branch" "$target_branch")


COMMITLIST=()
# Collect the initial set of commits to consider using a while loop
while IFS= read -r line; do
    COMMITLIST+=("$line")
done < <(git log ${cp_commit}^...${BRANCHPOINT} --pretty=format:"%H")

# filter out commits not touching the same files
FILTERED_COMMITS1=()
for commit_hash in "${COMMITLIST[@]}"; do
    modifies_common_files ${commit_hash} ${cp_commit}
    RC=$?
    if [ ${RC} -eq 1 ]; then
	FILTERED_COMMITS1+=(${commit_hash})
    fi
done

# Next, filter out commits which are irrelevant for ${cp_commit}
CP_COMMIT_LIST=(${cp_commit}) # The list of CP=cherry_pick commits to keep/construct

for commit_hash in "${FILTERED_COMMITS1[@]}"; do
    if [ ! "${commit_hash}" == "${cp_commit}" ]; then
      can_swap_commits "${commit_hash}" "${CP_COMMIT_LIST[@]}"
      if [ $? -eq 0 ]; then
        # echo "COMMIT ${commit_hash} is needed"
	# in this case we need to record it to the list of relevant commits
	# and also trace it's dependencies in turn
	CP_COMMIT_LIST+=(${commit_hash})
      fi
    fi
done

# reverse the final list to have correct cherry-pick order

CP_COMMITS_REVERSED=()
for ((i=${#CP_COMMIT_LIST[@]}-1; i>=0; i--)); do
  CP_COMMITS_REVERSED+=("${CP_COMMIT_LIST[i]}")
done

# List the commits
echo "To cherry-pick ${cp_commit} onto branch ${target_branch}, we need to apply:"
for ((i=0;i<${#CP_COMMITS_REVERSED[@]}; i++)); do
  echo "${i}: ${CP_COMMITS_REVERSED[i]}"
done

exit 0
