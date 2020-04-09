import os

data_dir = "data/"
csvs = os.listdir(data_dir)
i = 0

for csv in csvs:
    os.rename(data_dir + csv, data_dir + "data" + str(i) + ".csv")
    i += 1
