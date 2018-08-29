#!/usr/bin/python

#-------------------------------------------------
# act_storage_latency.py
#
# Analyze a act_storage output file. Typical usage:
#	$ ./act_storage_latency.py -l act_storage_out.txt
# where act_storage_out.txt is output generated by act_storage, and which uses
# defaults:
# -t 3600
# -s 0
# -n 7
# -e 1
# (-x - not set)
#-------------------------------------------------


#===========================================================
# Imports.
#

import getopt
import re
import sys


#===========================================================
# Constants.
#

BUCKET_LABELS = ("00", "01", "02", "03", "04", "05", "06", "07", "08", "09",
	"10", "11", "12", "13", "14", "15", "16")
ALL_BUCKETS = len(BUCKET_LABELS)
BUCKET_PATTERNS = [re.compile('.*?\(' + b + ': (.*?)\).*?')
	for b in BUCKET_LABELS]
GAP_PAD = "  "


#===========================================================
# Function definitions.
#

#-------------------------------------------------
# Parse a histogram total from a act output line.
#
def read_total_ops(line, file_id):
	total = long(line[line.find("(") + 1: line.find(" total)")])
	line = file_id.readline()
	return total, line

#-------------------------------------------------
# Get one set of bucket values.
#
def read_bucket_values(line, file_id, max_bucket):
	values = [0] * max_bucket
	total, line = read_total_ops(line, file_id)
	b_min = 0
	while True:
		found = 0
		for b in range(b_min, max_bucket):
			r = BUCKET_PATTERNS[b]
			if r.search(line):
				found += 1
				values[b] = long(r.search(line).group(1))
		if found == 0:
			break
		line = file_id.readline()
		b_min += found
	return total, values, line

#-------------------------------------------------
# Get the data chunk reported by act at the specified after_time.
#
def read_chunk(file_id, after_time, max_bucket):
	find_line = "After " + str(after_time) + " "
	while True:
		line = file_id.readline()
		if not line:
			return 0, 0, 0, 0, 0, 0, False
		if line.startswith(find_line):
			break
	line = file_id.readline()
	while line and line.strip():
		if line.startswith("RAW READS"):
			raw_total, raw_values, line = read_bucket_values(
				line, file_id, max_bucket)
		elif line.startswith("READS"):
			trans_total, trans_values, line = read_bucket_values(
				line, file_id, max_bucket)
		elif line.startswith("LARGE BLOCK READS"):
			lbread_total, line = read_total_ops(line, file_id)
		elif line.startswith("LARGE BLOCK WRITES"):
			lbwrite_total, line = read_total_ops(line, file_id)
		else:
			line = file_id.readline()
	try:
		lbread_total, lbwrite_total, \
		raw_total, raw_values, trans_total, trans_values
	except NameError:
		return 0, 0, 0, 0, 0, 0, False
	return lbread_total, lbwrite_total, \
		raw_total, raw_values, trans_total, trans_values, True

#-------------------------------------------------
# Get the percentage excesses for every bucket.
#
def bucket_percentages_over(total, values, max_bucket):
	percentages = [0.0] * max_bucket
	if total == 0:
		return percentages
	delta = 0
	for b in range(max_bucket):
		delta += values[b]
		percentages[b] = round(((total - delta) * 100.0) / total, 2)
	return percentages

#-------------------------------------------------
# Generate padding.
#
def repeat(what, n):
	pad = ""
	for i in range(n):
		pad += what
	return pad

#-------------------------------------------------
# Print a latency data output line.
#
def print_line(slice_tag, trans_overs, raw_overs, start_bucket, max_bucket,
		every_nth, extra=False, trans_rate=0, lbread_rate=0, lbwrite_rate=0):
	output = "%5s" % (slice_tag) + GAP_PAD
	for i in range(start_bucket, max_bucket, every_nth):
		output += "%7.2f" % (trans_overs[i])
	output += GAP_PAD
	for i in range(start_bucket, max_bucket, every_nth):
		output += "%7.2f" % (raw_overs[i])
	if extra:
		output += GAP_PAD + " [" + "%.1f" % (trans_rate)
		output += ", " + "%.1f" % (lbread_rate)
		output += ", " + "%.1f" % (lbwrite_rate) + "]"
	print output

#-------------------------------------------------
# Print usage.
#
def usage():
	print "Usage:"
	print " -l act_storage output file"
	print "    MANDATORY - NO DEFAULT"
	print "    e.g. act_storage_out.txt"
	print " -t analysis slice interval in seconds"
	print "    default: 3600"
	print " -s start display from this bucket"
	print "    default: 0"
	print " -n number of buckets to display"
	print "    default: 7"
	print " -e show start bucket then every n-th bucket"
	print "    default: 1"
	print " -x (show extra information for each slice)"
	print "    default: not set"

#-------------------------------------------------
# Main function.
#
def main(arg_log, arg_slice, arg_start_bucket, arg_num_buckets, arg_every_nth,
		arg_extra):
	# Sanity-check the arguments:
	if arg_log is None:
		usage()
		sys.exit(-1)
	if arg_slice < 1:
		print "slice must be more than 0"
		sys.exit(-1)
	if arg_start_bucket < 0 or arg_start_bucket >= ALL_BUCKETS:
		print "start_bucket must be non-negative and less than " + ALL_BUCKETS
		sys.exit(-1)
	if arg_num_buckets < 1:
		print "num_buckets must be more than 0"
		sys.exit(-1)
	if arg_every_nth < 1:
		print "every_nth must be more than 0"
		sys.exit(-1)

	# Find index + 1 of last bucket to display:
	for b in range(arg_start_bucket, ALL_BUCKETS, arg_every_nth):
		max_bucket = b + 1
		if arg_num_buckets == 1:
			break
		else:
			arg_num_buckets = arg_num_buckets - 1

	# Open the log file:
	try:
		file_id = open(arg_log, "r")
	except:
		print "log file " + arg_log + " not found"
		sys.exit(-1)

	# Find and echo the version:
	line = file_id.readline()
	while line and not line.startswith("Aerospike ACT"):
		line = file_id.readline()
	if not line:
		print "can't find any output data"
		sys.exit(-1)
	if line.split(" ")[2] != "version":
		print "data ACT version not found"
		sys.exit(-1)
	version = line.split(" ")[3].strip()
	print "data is ACT version " + version + "\n"
	numeric_version = float(version)
	if numeric_version < 5.0 or numeric_version >= 6.0:
		print "data ACT version not compatible"
		sys.exit(-1)

	# Find the reporting interval:
	line = file_id.readline()
	while line and not line.startswith("report-interval-sec"):
		line = file_id.readline()
	if not line:
		print "can't find report interval"
		sys.exit(-1)
	interval = long(line.split(" ")[1])
	if interval < 1:
		print "reporting interval must be more than 0"
		sys.exit(-1)

	# Find the histograms' scale:
	scale_label = " %>(ms)"
	file_id.seek(0, 0)
	line = file_id.readline()
	while line and not line.startswith("microsecond-histograms"):
		line = file_id.readline()
	if not line:
		print "can't find histograms' scale, assuming milliseconds"
		file_id.seek(0, 0)
	elif line.split(" ")[1].startswith("y"):
		scale_label = " %>(us)"

	# Adjust the slice time if necessary:
	slice_time = ((arg_slice + interval - 1) / interval) * interval
	if slice_time != arg_slice:
		print "analyzing time slices of " + str(slice_time) + " seconds"

	# Echo the config from the log file:
	file_id.seek(0, 0)
	line = file_id.readline()
	while line and not line.startswith("ACT_STORAGE CONFIGURATION"):
		line = file_id.readline()
	if not line:
		print "can't find storage configuration"
		sys.exit(-1)
	line = line.strip()
	while line:
		print line
		line = file_id.readline().strip()
	print ""
	line = file_id.readline()
	while line and not line.startswith("DERIVED CONFIGURATION"):
		line = file_id.readline()
	if not line:
		print "can't find derived configuration"
		sys.exit(-1)
	line = line.strip()
	while line:
		print line
		line = file_id.readline().strip()
	print ""

	# Print the output table header:
	labels_prefix = "slice"
	len_labels_prefix = len(labels_prefix)
	threshold_labels = ""
	threshold_underline = ""
	for i in range(arg_start_bucket, max_bucket, arg_every_nth):
		threshold_labels = threshold_labels + "%7s" % (pow(2, i))
		threshold_underline = threshold_underline + " ------"
	len_justify = len(threshold_labels) - 7
	prefix_pad = repeat(" ", len_labels_prefix)
	justify_pad = repeat(" ", len_justify)
	print prefix_pad + GAP_PAD + " trans " + justify_pad + GAP_PAD + " device"
	print prefix_pad + GAP_PAD + scale_label + justify_pad + GAP_PAD + \
		scale_label
	print labels_prefix + GAP_PAD + threshold_labels + GAP_PAD + \
		threshold_labels
	underline = repeat("-", len_labels_prefix) + GAP_PAD + \
		threshold_underline + GAP_PAD + threshold_underline
	print underline

	# Initialization before processing time slices:
	which_slice = 0
	after_time = slice_time
	old_lbread_total = 0
	old_lbwrite_total = 0
	old_trans_total = 0
	old_raw_total = 0
	old_trans_values = [0] * max_bucket
	old_raw_values = [0] * max_bucket
	trans_overs = [0.0] * max_bucket
	raw_overs = [0.0] * max_bucket
	avg_trans_overs = [0.0] * max_bucket
	avg_raw_overs = [0.0] * max_bucket
	max_trans_overs = [0.0] * max_bucket
	max_raw_overs = [0.0] * max_bucket

	# Process all the time slices:
	while True:
		(new_lbread_total, new_lbwrite_total,
			new_raw_total, new_raw_values, new_trans_total, new_trans_values,
			got_chunk) = read_chunk(file_id, after_time, max_bucket)
		if not got_chunk:
			# Note - we ignore the (possible) incomplete slice at the end.
			break

		# Get the "deltas" for this slice:
		slice_lbread_total = new_lbread_total - old_lbread_total
		slice_lbwrite_total = new_lbwrite_total - old_lbwrite_total
		slice_trans_total = new_trans_total - old_trans_total
		slice_raw_total = new_raw_total - old_raw_total
		slice_trans_values = [a - b
			for a, b in zip(new_trans_values, old_trans_values)]
		slice_raw_values = [a - b
			for a, b in zip(new_raw_values, old_raw_values)]

		# Get the rates for this slice:
		lbread_rate = round(float(slice_lbread_total) / slice_time, 1)
		lbwrite_rate = round(float(slice_lbwrite_total) / slice_time, 1)
		trans_rate = round(float(slice_trans_total) / slice_time, 1)

		# Convert bucket values for this slice to percentages over threshold:
		trans_overs = bucket_percentages_over(
			slice_trans_total, slice_trans_values, max_bucket)
		raw_overs = bucket_percentages_over(
			slice_raw_total, slice_raw_values, max_bucket)

		# For each (displayed) theshold, accumulate percentages over threshold:
		for i in range(arg_start_bucket, max_bucket, arg_every_nth):
			avg_trans_overs[i] += trans_overs[i]
			avg_raw_overs[i] += raw_overs[i]
			if (trans_overs[i] > max_trans_overs[i]):
				max_trans_overs[i] = trans_overs[i]
			if (raw_overs[i] > max_raw_overs[i]):
				max_raw_overs[i] = raw_overs[i]

		# Print this slice's percentages over thresholds:
		which_slice += 1
		print_line(which_slice, trans_overs, raw_overs, arg_start_bucket,
			max_bucket, arg_every_nth, arg_extra, trans_rate, lbread_rate,
			lbwrite_rate)

		# Prepare for next slice:
		old_lbread_total = new_lbread_total
		old_lbwrite_total = new_lbwrite_total
		old_trans_total = new_trans_total
		old_raw_total = new_raw_total
		old_trans_values = new_trans_values
		old_raw_values = new_raw_values
		after_time += slice_time

	# Print averages and maximums:
	if which_slice:
		for i in range(arg_start_bucket, max_bucket, arg_every_nth):
			avg_trans_overs[i] = avg_trans_overs[i] / which_slice
			avg_raw_overs[i] = avg_raw_overs[i] / which_slice
		print underline
		print_line("avg", avg_trans_overs, avg_raw_overs, arg_start_bucket,
			max_bucket, arg_every_nth)
		print_line("max", max_trans_overs, max_raw_overs, arg_start_bucket,
			max_bucket, arg_every_nth)
	else:
		print "could not find " + str(slice_time) + " seconds of data"


#===========================================================
# Execution.
#

print "act_storage_latency.py " + " ".join(sys.argv[1:])

# Read the input arguments:
try:
	opts, args = getopt.getopt(sys.argv[1:], "l:t:s:n:e:x",
		["log=", "slice=", "start_bucket=", "num_buckets=", "every_nth=",
		 "extra"])
except getopt.GetoptError, err:
	print str(err)
	usage()
	sys.exit(-1)

# Default values for arguments:
arg_log = None
arg_slice = 3600
arg_start_bucket = 0
arg_num_buckets = 7
arg_every_nth = 1
arg_extra = False

# Set the arguments:
for o, a in opts:
	if o == "-l" or o == "--log":
		arg_log = a
	if o == "-t" or o == "--slice":
		arg_slice = long(a)
	if o == "-s" or o == "--start_bucket":
		arg_start_bucket = int(a)
	if o == "-n" or o == "--num_buckets":
		arg_num_buckets = int(a)
	if o == "-e" or o == "--every_nth":
		arg_every_nth = int(a)
	if o == "-x" or o == "--extra":
		arg_extra = True

# Call main():
main(arg_log, arg_slice, arg_start_bucket, arg_num_buckets, arg_every_nth,
	arg_extra)
