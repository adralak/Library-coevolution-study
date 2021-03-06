import csv
import os
import operator

data_dir = "data/"
new_data_dir = "processed_data/"
log_dir = "logs/"

try:
    os.mkdir(log_dir)
except:
    ()

try:
    os.mkdir(new_data_dir)
except:
    ()


# The hash is in the url, so we need to extract it
def get_hash(url):
    if len(url) < 34:
        return("")

    repo_and_hash = url[34:]
    slash = 0

    for i in range(len(repo_and_hash)):
        if repo_and_hash[i] == '/':
            slash += 1

        if slash == 2:
            return(repo_and_hash[i+1:-1])

    return("")


# Convert the string in the csv to a usable list
def convert_dep_to_coords(dep):
    split_dep = dep.split(",")
    if len(split_dep) != 3:
        return(None)
    real_dep = [split_dep[0][2:-1], split_dep[1][2:-1], split_dep[2][2:-2]]
    return(real_dep[0] + ":" + real_dep[1] + ":" + real_dep[2])


# This is to avoid the fact that '4.10' < '4.2' lexicographically
def transform_version(row):
    version = row[5]
    # Split the version on the dots: '4.10' becomes ['4', '10']
    split_version = version.split('.')
    # Add lengths: ['4', '10'] becomes [(1, '4'), (2, '10')]
    split_version_with_len = [[len(s), s] for s in split_version]

    if "SNAPSHOT" in split_version_with_len[-1][1]:
        split_version_with_len[-1][0] -= 8

    return(split_version_with_len)


def main():
    f1, f2, f3 = (open(new_data_dir + "artifacts.csv", 'w', newline=''),
                  open(new_data_dir + "next.csv", 'w', newline=''),
                  open(new_data_dir + "deps.csv", 'w', newline=''))
    nodes, nexts, dependencies = csv.writer(f1), csv.writer(f2), csv.writer(f3)
    log = open(log_dir + "conversion_log.txt", 'w')

    nodes.writerow(["groupID", "artifact", "version", "coordinates",
                    "stars", "url", "commit_hash", "packaging", "from_github"])
    nexts.writerow(["coords1", "coords2"])
    dependencies.writerow(["coords1", "coords2"])

    for to_handle in os.listdir(data_dir):
        with open(data_dir + to_handle, 'r', newline='') as f:
            reader = csv.reader(f)

            sorted_by_vrs = sorted(reader, key=transform_version)
            sorted_by_gid = sorted(sorted_by_vrs, key=operator.itemgetter(3))
            sorted_by_aid = sorted(sorted_by_gid, key=operator.itemgetter(4))

            sorted_rows = sorted_by_aid

            prev_gid, prev_art, prev_version, prev_coords = (
                None, None, None, None)
            n_same = 0

            for row in sorted_rows:
                # If the row is too short for some reason, skip it
                if len(row) < 7:
                    continue

                gid, aid, version, coords = (row[3], row[4], row[5],
                                             row[3] + ":" + row[4] + ":" + row[5])

                if prev_gid == gid and prev_art == aid and \
                   prev_version == version:
                    coords += "-GITHUB" + str(n_same)
                    nodes.writerow([gid, aid, version + "-GITHUB" +
                                    str(n_same), coords, row[1], row[2],
                                    get_hash(row[2]), row[6], "True"])
                    n_same += 1
                else:
                    n_same = 0
                    nodes.writerow([gid, aid, version, coords, row[1], row[2],
                                    get_hash(row[2]), row[6], "True"])

                nexts.writerow([prev_coords, coords])

                prev_gid, prev_art, prev_version, prev_coords = (
                    gid, aid, version, coords)

                repo_deps = []
                for d in row[7:]:
                    # There may be some empty spots, skip them
                    if len(d) > 2:
                        dep_coords = convert_dep_to_coords(d)
                        if dep_coords is not None:
                            dependencies.writerow([coords, dep_coords])

    f1.close()
    f2.close()
    f3.close()
    log.close()


main()
