#!/usr/bin/env python3

# Get list of PRs from provided repo that have a certain label assigned
# Can be used to figure out which PRs should be ported

import sys
import argparse
import requests
import re


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
    prs_merged = [pr for _, pr in sorted(zip(merged_at, prs_merged))]

    return prs_merged, prs_other


def get_prs(owner, repo, request_labels, pr_state, per_page=50, start_page=1, pages=1):
    """
    Get PRs according to some selection
    """
    # GitHub API endpoint for listing closed pull requests with a specific label
    prs_return = []

    has_error = False
    for page in range(start_page, pages + 1):
        url = f'https://api.github.com/repos/{owner}/{repo}/pulls?state={pr_state}&page={page}&per_page={per_page}'

        # Send GET request to GitHub API
        response = requests.get(url)

        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            # Parse JSON response
            prs = response.json()
            # PRs to return because we filter on a specific label
            for pr in prs:
                labels = pr['labels']
                take_pr = False
                for label in labels:
                    if label['name'] in request_labels:
                        # only with the correct the label will be accepted
                        take_pr = True
                        break
                if not take_pr:
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


def get_labels(owner, repo, regex=None):
    """
    Get the labels that match given regex
    """
    # the REST API url
    url = f'https://api.github.com/repos/{owner}/{repo}/labels'
    # Send GET request to GitHub API
    response = requests.get(url)

    if response.status_code != 200:
        print(f'ERROR: Problem to retrieve labels for owner {owner} and repository {repo}')
        return None

    return [label['name'] for label in response.json() if not repo or re.match(regex, label['name'])]


def separate_labels_request_accept(labels, accept_suffix=None):
    """
    Disentangle labels and <label>-accepted
    """
    if not accept_suffix:
        # all labels are considered request labels
        return labels.copy(), []

    labels_request = []
    labels_accept = []

    for label in labels:
        if label.endswith(accept_suffix):
            labels_accept.append(label)
            continue
        labels_request.append(label)

    return labels_request, labels_accept


def make_report(prs_merged, prs_other, repo, labels_request, label_accept_suffix, outfile):
    """
    Make a report

    The report consists of one table per label which will be written to a text file.
    """
    # common header for each single table
    common_header = '| Requestor | Package | PR | PR title | Merged at | Data or MC |\n| --- | --- | --- | --- | --- | --- |\n'
    rows_per_label = {label: [] for label in labels_request}

    with open(outfile, 'w') as f:

        f.write(f'Merged PRs: {len(prs_merged)}\nOther closed PRs: {len(prs_other)}\nLabels: {", ".join(labels_request)}\n\n')
        f.write('# List PRs from oldest to recent (merged)\n')

        # first put the merged PRs
        for pr in prs_merged:
            mc_data = []
            # collect the labels for which table this PR should be taken into account
            labels_take = []

            for label in pr['labels']:
                label_name = label['name']
                if label_name.lower() in ('mc', 'data'):
                    # get assigned MC or DATA label if this PR has it
                    mc_data.append(label['name'])
                if label_name in labels_request and (not label_accept_suffix or f'{label_name}-{label_accept_suffix}' not in pr['labels']):
                    # check if that label is one that flags a request. If at the same time there is also the corresponding accepted label, don't take this PR into account for the report.
                    labels_take.append(label_name)

            if not labels_take:
                # no labels of interest
                continue

            # if no specific MC or DATA label, assume valid for both
            mc_data = ','.join(mc_data) if mc_data else 'MC,DATA'
            for label in labels_take:
                rows_per_label[label].append(f'| {pr["user"]["login"]} | {repo} | [PR]({pr["html_url"]}) | {pr["title"]} | {pr["merged_at"]} | {mc_data} |\n')

        for label, rows in rows_per_label.items():
            if not rows:
                # nothing to add here
                continue
            f.write(f'\n==> START label {label} <==\n')
            f.write(common_header)
            for row in rows:
                f.write(row)
            f.write(f'==> END label {label} <==\n')

        # add all the other commits
        f.write('\n# Other PRs (not merged)\n')
        for pr in prs_other:
            f.write(f'| {pr["user"]["login"]} | {repo} | [PR]({pr["html_url"]}) | {pr["title"]} | not merged | {", ".join(labels_take)} | {mc_data} |\n')

    print(f"==> Report written to {outfile}")


if __name__ == '__main__':
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Retrieve closed pull requests with a specific label from a GitHub repository')
    parser.add_argument('--owner', help='GitHub repository owner', default='AliceO2Group')
    parser.add_argument('--repo', required=True, help='GitHub repository name, e.g. O2DPG or AliceO2')
    parser.add_argument('--pr-state', dest='pr_state', default='closed', help='The state of the PR')
    parser.add_argument('--output', default='o2dpg_pr_report.txt')
    parser.add_argument('--per-page', dest='per_page', default=50, help='How many results per page')
    parser.add_argument('--start-page', dest='start_page', type=int, default=1, help='Start on this page')
    parser.add_argument('--pages', type=int, default=1, help='Number of pages')
    parser.add_argument('--label-regex', dest='label_regex', help='Provide a regular expression to decide which labels to fetch.', default='^async-\w+')
    parser.add_argument('--label-accepted-suffix', dest='label_accepted_suffix', help='Provide a regular expression to decide which labels to fetch.', default='accept')
    parser.add_argument('--include-accepted', action='store_true', help='By default, only PRs are fetched where at least one label has no "<label>-accepted" label')
    args = parser.parse_args()

    # get all labels of interest
    labels = get_labels(args.owner, args.repo, args.label_regex)
    # split into request and accept labels, here we currently only need the request labels
    labels_request, _ = separate_labels_request_accept(labels, args.label_accepted_suffix)

    # Retrieve closed pull requests with the specified label, split into merged and other (closed) PRs
    prs_merged, prs_other = get_prs(args.owner, args.repo, labels_request, args.pr_state, args.per_page, args.start_page, args.pages)
    if prs_merged is None:
        print('ERROR: There was a problem fetching the info.')
        sys.exit(1)

    make_report(prs_merged, prs_other, args.repo, labels_request, args.label_accepted_suffix, args.output)

    sys.exit(0)
