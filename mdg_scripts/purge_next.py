from py2neo import Node, Relationship, Graph, NodeMatcher, RelationshipMatcher

log_dir = "logs/"

try:
    os.mkdir(log_dir)
except:
    ()

exceptions = open(log_dir + "purge_exceptions.txt", "w")
errors = open(log_dir + "purge_errors.txt", "w")


def main():
    MDG = Graph()
    tx = MDG.begin()
    node_matcher = NodeMatcher(MDG)
    rel_matcher = RelationshipMatcher(MDG)
    all_nodes = node_matcher.match("Artifact")

    for node in all_nodes:
        nexts = rel_matcher.match(nodes=(node, None), r_type="NEXT")

        if len(nexts) <= 1:
            continue

        if len(nexts) > 2:
            exceptions.write(
                node[coordinates] + ": node has 3 or more NEXT!\n")
            continue

        seq_next = []
        seq_rel = []
        for r in nexts:
            seq_rel.append(r)
            i = 0
            for n in walk(r):
                if i == 1:
                    seq_next.append(n)

        r1, r2 = seq_rel[0], seq_rel[1]
        n1, n2 = seq_next[0], seq_next[1]
        if n1["version"] < n2["version"]:
            tx.separate(r2)
        else:
            tx.separate(r1)

    tx.commit()
