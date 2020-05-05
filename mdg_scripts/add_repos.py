from py2neo import Node, Relationship, Graph, NodeMatcher
import csv
import os
from sys import argv

if len(argv) < 4:
    print("Not enough arguments!")
    exit(1)

to_handle = argv[1]
username = argv[2]
password = argv[3]

data_dir = "data/"


# Convert the string in the csv to a usable list
def convert_dep_to_list(dep):
    split_dep = dep.split(",")
    if len(split_dep) != 3:
        return(None)
    real_dep = [split_dep[0][2:-1], split_dep[1][1:-1], split_dep[2][1:-2]]
    return(real_dep)


# Finds the node matching the groupID, artifactID and version of dep
def find_dep_node(MDG, matcher, dep):
    if len(dep) != 3:
        return(None)

    coords = dep[0] + ":" + dep[1] + ":" + dep[2]
    found_nodes = matcher.match("Artifact", coordinates=coords)
    found_node = found_nodes.first()

    if found_node is None:
        # Either we just return None or we can add the node,
        # not sure what's best...
        tx = MDG.begin()
        dep_node = Node("Artifact", groupID=dep[0], artifact=dep[1],
                        version=dep[2], coordinates=coords)
        tx.create(dep_node)
        tx.commit()

        return(dep_node)

    return(found_node)


# Find a node with its coordinates
def get_node(matcher, coords):
    found_nodes = matcher.match("Artifact", coordinates=coords)

    return(found_nodes.first())


def main():
    # Don't forget to start the MDG up before using this script!
    if username == "None":
        MDG = Graph()
    else:
        MDG = Graph(auth=(username, password))
    tx = MDG.begin()
    deps = []
    matcher = NodeMatcher(MDG)

    # print("Starting")

    with open(data_dir + to_handle, 'r', newline='') as f:
        reader = csv.reader(f)
        prev_repo, prev_node, prev_version = None, None, None
        for row in reader:
            # Get metadata
            repo, gid, aid, version = row[0], row[3], row[4], row[5]

            # Missing: release date, packaging
            # Create & add node
            repo_node = Node("Artifact", stars=row[1], url=row[2], groupID=gid,
                             artifact=aid, version=version,
                             coordinates=gid+":"+aid+":"+version,
                             from_github="True")

            # If it already exists, the only thing to do is update the prev_repo and prev_node
            existing_node = get_node(matcher, repo_node["coordinates"])
            if existing_node is not None:
                prev_repo, prev_node, prev_version = repo, existing_node, version
                continue

            if version != prev_version or repo != prev_repo:
                tx.create(repo_node)

                if repo == prev_repo:
                    r_next = Relationship(repo_node, "NEXT", prev_node)
                    tx.create(r_next)

                prev_repo, prev_node, prev_version = repo, repo_node, version

            for d in row[6:]:
                if len(d) > 2:
                    dep_list = convert_dep_to_list(d)
                    if dep_list is not None:
                        deps.append((repo_node, dep_list))

  #  print("Done adding nodes and NEXT")
    tx.commit()
    tx = MDG.begin()

    for (node, dep) in deps:
        dep_node = find_dep_node(MDG, matcher, dep)

        if dep_node is None:
            continue

        r_dep = Relationship(node, "DEPENDS_ON", dep_node)
        tx.merge(r_dep)

    tx.commit()
#    print("All done")


main()
