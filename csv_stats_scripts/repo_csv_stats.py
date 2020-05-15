import csv
import os
from time import sleep

csv_dir = "data/"
output_dir = "output/"

try:
    os.mkdir(output_dir)
except:
    ()


class Counter(dict):
    def __missing__(self, key):
        return(0)


def get_midpoint(interval):
    for i in range(len(interval)):
        if interval[i] == ";":
            return(i)

    return(-1)


def get_effective_version(version):
    if version == "version":
        return("0.any", False, False)
    elif version[0] == "$":
        return("", False, False)

    numbers = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']

    # If it's just a number, there's nothing to do
    if version[0] in numbers:
        return(version, False, False)

    closing_bracket = [']', ')']

    v_list = list(version)
    # Transform the string for easy split
    # This turns the string "[2,5],(6.0,7.0],[8.0,)" into "[2;5],(6.0;7.0],[8.0;)"
    for i in range(1, len(version)):
        if version[i] == ',' and version[i-1] not in closing_bracket:
            v_list[i] = ';'

    version = ''.join(v_list)
    intervals = version.split(",")
    used_v = ""

    for interval in intervals:
        i = get_midpoint(interval)

        # If it doesn't have a midpoint it's of the form [version],
        # which means a hard requirement
        if i == -1:
            return(interval[1:-1], False, True)

        # If it's closed on the right, take the high version
        if interval[-1] == ']':
            used_v = max(used_v, interval[i+1:-1])
        # Otherwise, it's open on the right
        # If it has an upper bound, use the version directly preceding it
        elif interval[-2] != ";":
            used_v = max(used_v, interval[i+1:-1] + "$m")
        # If it's closed on the left, take the low version
        elif interval[0] == '[':
            used_v = max(used_v, interval[1:i])
        # Otherwise, it's open on both sides and has no upper bound
        # If it has a lower bound, use the version directly following it
        elif interval[1] != ";":
            used_v = max(used_v, interval[1:i] + "$p")
        # Otherwise the interval is (,) which shouldn't be possible
        else:
            continue

    needs_match = used_v[-2] == '$' and (used_v[-1]
                                         == 'm' or used_v[-1] == 'p')
    return(used_v, needs_match, False)


# Convert the string in the csv to a usable list
def convert_dep_to_list(dep):
    split_dep = dep.split(",")
    if len(split_dep) != 3:
        return(None)
    real_dep = [split_dep[0][2:-1], split_dep[1][1:-1], split_dep[2][1:-2]]
    return(real_dep)


def purge_deps(deps):
    i = 0
    purged_deps = []

    deps.sort()

    while i < len(deps):
        real_dep = deps[i]
        real_version, real_needs_match, real_hard_req = get_effective_version(
            real_dep[2])
        curr_gid, curr_aid = real_dep[0], real_dep[1]

        # While we're on the same dep (same groupID, same artifactID)
        while i < len(deps) and deps[i][0] == curr_gid and deps[i][1] == curr_aid:
            curr_dep = deps[i]
            i += 1

            # If the dep is malformed or the real_dep is a hard requirement, skip
            if len(curr_dep) < 3 or real_hard_req or len(curr_dep[0]) <= 1 \
               or len(curr_dep[1]) <= 1 or len(curr_dep[2]) <= 1:
                continue

            # Otherwise, get the actual version of curr_dep
            version, needs_match, hard_req = get_effective_version(curr_dep[2])

            # If it's more recent or not vague,
            # or if it's a hard requirement,
            # update the "real" variables
            if (version > real_version and version != "any") or hard_req \
               or (real_version == "any" and version != "any"):
                real_dep, real_version, real_needs_match, real_hard_req = (
                    curr_dep, version, needs_match, hard_req)

        for s in real_dep:
            s = s.replace('\'', '')

        if real_version == "":
            continue

        # We don't match here, so if matching is needed, we
        # want to keep that info
        real_dep[2] = real_version, real_needs_match
        purged_deps.append(real_dep)

    return(purged_deps)


def write_dep_numbers(count_deps, r):
    for key in count_deps:
        r.write(key + " is used " + str(count_deps[key]) + " times\n")


def main():
    n_repos, n_same, n_rows, n_deps = 0, 0, 0, 0
    prev_repo, prev_gid, prev_aid, prev_v, prev_url = (
        None, None, None, None, None)
    count_deps = Counter()

    for to_handle in os.listdir(csv_dir):
        with open(csv_dir + to_handle, "r", newline='') as f:
            reader = csv.reader(f)

            n_rows += reader.line_num

            for row in reader:
                repo, gid, aid, v, url = row[0], row[3], row[4], row[5], row[2]

                if url == prev_url:
                    continue

                if repo != prev_repo:
                    n_repos += 1

                if gid == prev_gid and aid == prev_aid and v == prev_v:
                    n_same += 1

                prev_repo, prev_gid, prev_aid, prev_v, prev_url = (
                    repo, gid, aid, v, url)

                for d in row[6:]:
                    repo_deps = []
                    if len(d) > 3:
                        dep = convert_dep_to_list(d)

                        if dep is not None:
                            repo_deps.append(dep)

                tmp_repo_deps = purge_deps(repo_deps)
                repo_deps = [d[0].replace('\'', '') + ":" + d[1].replace('\'', '') + ":" +
                             d[2][0].replace('\'', '')
                             for d in tmp_repo_deps]
                n_deps += len(repo_deps)

                for dep in repo_deps:
                    count_deps[dep] += 1

    with open(output_dir + "results.txt", "w") as r:
        r.write(str(n_repos) + ": number of repos\n" + str(n_same) +
                ": number of tags with the same coordinates\n" +
                str(n_rows) + ": number of tags\n" +
                str(n_deps) + ": number of dependency relationships\n")

        write_dep_numbers(count_deps, r)


main()
