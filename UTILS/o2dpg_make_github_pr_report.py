#!/usr/bin/env python3

# Get list of PRs from provided repo that have a certain label assigned
# Can be used to figure out which PRs should be ported

import sys
import argparse
import requests


def organise_prs(prs):
    """
    Sort PRs by time merged, starting from old to recent
    """
    # collect merged PRs
    prs_merged = []
    # collect the time of merged PRs
    merged_at = []
    # other PRs, open, closed and not merged
    prs_other = []

    for pr in prs:
        if not pr['merged_at']:
            # that has not been merged
            prs_other.append(pr)
            continue
        # get the PR itself and the merged timestamp
        prs_merged.append(pr)
        merged_at.append(pr['merged_at'])

    # sort the merged PRs by their merged timestamp
    prs_merged = [pr for _, pr in sorted(zip(merged_at, prs))]

    return prs_merged, prs_other


def get_prs(owner, repo, prod_label, pr_state, include_unmerged, per_page=50, start_page=1, pages=1):
    """
    Get PRs according to some selection
    """
    # GitHub API endpoint for listing closed pull requests with a specific label
    merged_token = '&is:merged=true' if not include_unmerged else ''
    prs_return = []

    has_error = False
    for page in range(start_page, pages + 1):
        url = f'https://api.github.com/repos/{owner}/{repo}/pulls?state={pr_state}{merged_token}&page={page}&per_page={per_page}'
        print(f'Fetch PRs accrodring to {url}')

        # Send GET request to GitHub API
        response = requests.get(url)

        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            # Parse JSON response
            prs = response.json()
            # PRs to return because we filter on a specific label
            for pr in prs:
                labels = pr['labels']
                accept = False
                for label in labels:
                    if label['name'] == prod_label:
                        # only with the correct the label will be accepted
                        accept = True
                        break
                if not accept:
                    continue
                # we will end up here if accepted, so append
                prs_return.append(pr)

        else:
            print(f'Failed to retrieve data: {response.status_code} - {response.text}')
            has_error = True
            break

    if has_error:
        return None, None

    # organise PRs into different lists (merged and others)
    return organise_prs(prs_return)


def make_report(prs_merged, prs_other, outfile):
    """
    Make a report

    simply dump into text file
    """

    with open(outfile, 'w') as f:
        f.write('# FROM OLDEST TO RECENT\n')
        # our common header
        f.write('| Date of next tag | Requestor | Package | PR | Data or MC | Comment | JIRA (if it exists) | Accepted | In production | Validated by requestor |\n')
        f.write('| ---------------- | ------------ | ------- | --------------------------------------------------------:|:--------------------------------------------- | ------------------- | ---------------- | ------------- |-------------| ------------------|\n')

        # first put the merged PRs
        for pr in prs_merged:
            mc_data = []

            for label in pr['labels']:
                if label['name'] in ('MC', 'DATA'):
                    # get assigned MC or DATA label if this PR has it
                    mc_data.append(label['name'])

            # if no specific MC or DATA label, assume valid for both
            mc_data = ','.join(mc_data) if mc_data else 'MC,DATA'
            # add the full line to the output file
            f.write(f'| {args.date} | {pr["user"]["login"]} | {args.repo} | [PR]({pr["html_url"]}) | {mc_data} |  {pr["title"]} |  | | |  |\n')

        # add all the other commits
        f.write('OTHER PRs\n')
        for pr in prs_other:
            f.write(f'| {args.date} | {pr["user"]["login"]} | {args.repo} | [PR]({pr["html_url"]}) |  |  {pr["title"]} |  | | |  |\n')


if __name__ == '__main__':
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Retrieve closed pull requests with a specific label from a GitHub repository')
    parser.add_argument('--owner', help='GitHub repository owner', default='AliceO2Group')
    parser.add_argument('--repo', required=True, help='GitHub repository name, e.g. O2DPG or AliceO2')
    parser.add_argument('--prod-label', dest='prod_label', required=True, help='Production label to filter PRs')
    parser.add_argument('--pr-state', dest='pr_state', default='closed', help='The state of the PR')
    parser.add_argument('--include-unmerged', dest='include_unmerged', action='store_true', help='To fetch also unmerged PRs')
    parser.add_argument('--output', default='o2dpg_pr_report.txt')
    parser.add_argument('--date', help='The date tag to be put', required=True)
    parser.add_argument('--per-page', dest='per_page', default=50, help='How many results per page')
    parser.add_argument('--start-page', dest='start_page', type=int, default=1, help='Start on this page')
    parser.add_argument('--pages', type=int, default=1, help='Number of pages')


    args = parser.parse_args()

    # Retrieve closed pull requests with the specified label
    prs_merged, prs_other = get_prs(args.owner, args.repo, args.prod_label, args.pr_state, args.include_unmerged, args.per_page, args.start_page, args.pages)
    if prs_merged is None:
        print('ERROR: There was a problem fetching the info.')
        sys.exit(1)

    make_report(prs_merged, prs_other, args.output)

    sys.exit(0)
