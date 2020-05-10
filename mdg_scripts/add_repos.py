from py2neo import Node, Relationship, Graph, NodeMatcher, RelationshipMatcher
import csv
import os
from sys import argv

if len(argv) < 2:
    print("Not enough arguments!")
    print("Correct use: python3 csv \ncsv is a csv file inside data_dir\nusername is the username used to connect to the graph; if there is no such thing, write None\npassword is the password used to connect to the graph; if there is no such thing, write None")
    exit(1)

to_handle = argv[1]

data_dir = "data/"
exec_space = "exec_space" + to_handle + "/"

try:
    os.mkdir(exec_space)
except:
    ()

exceptions = open(exec_space + "exceptions" + to_handle + ".txt", "w")


"""def is_mid_exclude(version, i):
    if i + 1 < len(version):
        prev_c, next_c = version[i - 1], version[i + 1]

        return(prev_c == ')' and next_c == '(')

    return(False)"""


def get_midpoint(interval):
    for i in range(len(interval)):
        if interval[i] == ";":
            return(i)

    return(-1)


def get_effective_version(version):
    if version == "version":
        return("any", False, False)

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


# Finds the node matching the groupID, artifactID and version of dep
def find_dep_node(MDG, matcher, dep):
    if len(dep) != 3:
        return(None, "the dependency is malformed!")

    # Remember, we fiddled with dep so dep[2] is not quite version
    version, needs_match = dep[2]
    # If it needs a match, there are two trailing characters at the end
    if needs_match:
        coords = dep[0] + ":" + dep[1] + ":" + version[:-2]
    else:
        coords = dep[0] + ":" + dep[1] + ":" + version

    found_nodes = matcher.match("Artifact", coordinates=coords)
    found_node = found_nodes.first()

    # If we can't find the node, we add it to the MDG
    if found_node is None:
        tx = MDG.begin()
        dep_node = Node("Artifact", groupID=dep[0], artifact=dep[1],
                        version=dep[2], coordinates=coords)
        tx.create(dep_node)
        tx.commit()

        # If we need a match, this is not the node we're looking for
        # and we can't really find the one we're looking for
        # so we simply add it to the exceptions
        if needs_match:
            return(None, "finding the dependency requires a node match that is impossible!")
        else:
            return(dep_node, "")

    # Otherwise, we found the node. If we need a match
    if needs_match:
        r_matcher = RelationshipMatcher(MDG)

        # Either we need the version immediately preceding or
        # immediately following the current node.
        # In both cases, if we can't find the relationship, we can't do much
        # If we do, we return the corresponding node
        # NB: the "None" in nodes mean "any node"
        if version[-1] == 'm':
            found_rs = r_matcher.match(nodes=(None, found_node), r_type="NEXT")
            found_r = found_rs.first()

            if found_r is None:
                return(None, "finding the dependency requires a relationship match that is impossible!")

            return(found_r.start_node, "")
        else:
            found_rs = r_matcher.match(nodes=(found_node, None), r_type="NEXT")
            found_r = found_rs.first()

            if found_r is None:
                return(None, "finding the dependency requires a relationship match that is impossible!")

            return(found_r.end_node, "")

    else:
        return(found_node, "")


# Find a node with its coordinates
def get_node(matcher, coords):
    found_nodes = matcher.match("Artifact", coordinates=coords)

    return(found_nodes.first())


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
            if len(curr_dep) < 3 or real_hard_req:
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

        # We don't match here, so if matching is needed, we
        # want to keep that info
        real_dep[2] = real_version, real_needs_match
        purged_deps.append(real_dep)

    return(purged_deps)


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
        prev_gid, prev_art, prev_node, prev_version = None, None, None, None
        for row in reader:
            # Get metadata
            repo, gid, aid, version, packaging = row[0], row[3], row[4], row[5], row[6]

            # Missing: release date, packaging
            # Create & add node
            repo_node = Node("Artifact", stars=row[1], url=row[2], groupID=gid,
                             artifact=aid, version=version, packaging=packaging,
                             coordinates=gid+":"+aid+":"+version,
                             from_github="True")

            # If it already exists, the only thing to do is update the prev_repo and prev_node
            existing_node = get_node(matcher, repo_node["coordinates"])
            if existing_node is not None:
                prev_gid, prev_art, prev_node, prev_version = gid, aid, existing_node, version
                continue

            if version != prev_version or (aid != prev_art and gid != prev_gid):
                tx.create(repo_node)

                if aid == prev_art and gid == prev_gid:
                    r_next = Relationship(repo_node, "NEXT", prev_node)
                    tx.create(r_next)

                prev_gid, prev_art, prev_node, prev_version = gid, aid, repo_node, version

            for d in row[7:]:
                repo_deps = []
                if len(d) > 2:
                    dep_list = convert_dep_to_list(d)
                    if dep_list is not None:
                        repo_deps.append(dep_list)

            deps.append((repo_node, dep_list))

  #  print("Done adding nodes and NEXT")
    tx.commit()
    tx = MDG.begin()

    for (node, dep_list) in deps:
        node_deps = purge_deps(dep_list)

        for dep in node_deps:
            dep_node, reason = find_dep_node(MDG, matcher, dep)

            if dep_node is None:
                exceptions.write(node[coordinates] + ": could not create dependency with " +
                                 dep[0] + ":" + dep[1] + ":" + dep[2][0] + "because " + reason)
                continue

            r_dep = Relationship(node, "DEPENDS_ON", dep_node)
            tx.merge(r_dep)

    tx.commit()
#    print("All done")


main()
