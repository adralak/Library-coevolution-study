import csv
import os

to_merge = "to_merge/"
list_of_files = os.listdir(to_merge)


with open("data.csv", "w", newline='') as f:
    writer = csv.writer(f)
    for d in list_of_files:
        with open(to_merge + d, "r") as csv_f:
            for line in csv_f:
                writer.writerow(line)
