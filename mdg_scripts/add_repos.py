from py2neo import Node, Relationship, Graph
import csv
import os

if len(argv) < 2:
    print("Not enough arguments!")
    exit(1)

to_handle = argv[1]

data_dir = "data/"


# Convert the string in the csv to a usable list
def convert_dep_to_list(dep):
    split_dep = dep.split(",")
    if len(split_dep) != 3:
        return(None)
    real_dep = [split_dep[0][2:-1], split_dep[1][1:-1], split_dep[2][1:-2]]
    return(real_dep)


# Finds the node matching the groupID, artifactID and version of dep
def find_dep_node(matcher, dep):
    if len(dep) != 3:
        return(None)

    coords = dep[0] + ":" + dep[1] + ":" + dep[2]
    found_nodes = matcher.match("Artifact", coordinates=coords)

    return(found_nodes.first())


# Find a node with its coordinates
def get_node(matcher, coords):
    found_nodes = matcher.match("Artifact", coordinates=coords)

    return(found_nodes.first())


def main():
    # Don't forget to start the MDG up before using this script!
    MDG = Graph()
    tx = MDG.begin()
    deps = []
    matcher = NodeMatcher(MDG)

    with open(data_dir + t_handle, 'r', newline='') as f:
        reader = csv.reader(f)
        prev_repo, prev_node = None, None
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
            existing_node = get_node(matcher, repo_node[coordinates])
            if existing_node is not None:
                prev_repo, prev_node = repo, existing_node
                continue

            tx.create(repo_node)

            if repo == prev_repo:
                r_next = Relationship(repo_node, "NEXT", prev_node)
                tx.create(r_next)

            prev_repo, prev_node = repo, repo_node

            for d in row[6:]:
                if len(d) > 2:
                    deps.append((repo_node, convert_dep_to_list(d)))

    tx.commit()
    tx = MDG.begin()

    for (node, dep) in deps:
        dep_node = find_dep_node(matcher, dep)

        if dep_node is None:
            continue

        r_dep = Relationship(node, "DEPENDS_ON", dep_node)
        tx.create(r_dep)

    tx.commit()
