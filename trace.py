#! /usr/bin/env python2

# Developed by Olivia Lucca Fraser
# for Tenable Network Security

from __future__ import print_function
import sys, os
import argparse
import math
import re

ATTRIBUTES = ["name", "total", "frequency", "average"]
COLOUR_ON = False
RAINBOW = ["yellow","green","blue","cyan","magenta","red"]

def colour(hue, shade="dark"):
    global COLOUR_ON
    if (not COLOUR_ON):
        return ""
    hues = {
        "reset":"0"
        ,"black":"30"
        ,"red":"31"
        ,"green":"32"
        ,"yellow":"33"
        ,"blue":"34"
        ,"magenta":"35"
        ,"cyan":"36"
    }
    shades = {
        "dark":"0"
        ,"light":"1"
    }
    return "\x1b["+shades[shade]+";"+hues[hue]+"m"

def rainbow(indent, light='light'):
    global RAINBOW
    l = len(RAINBOW)
    return colour(RAINBOW[indent % l],light)

def step(row):
    call_or_ret=row.split(" ")[0]
    if (call_or_ret == "call"):
        return 1
    elif (call_or_ret == "ret"):
        return -1
    else:
        return 0

def frame_time(split_row):
    """Returns the tuple (frame_name, elapsed_time)"""
    timestamp_s = re.findall(pattern=', ([0-9.]+)(?:(?: \([0-9]+usec\))?|\])', string=split_row[0])
    timestamp = float(timestamp_s[0]) * 1000
    row = split_row[1]
    frame_name = row.split(" ")[1].split("(")[0]
    if (frame_name == ""):
        frame_name = "INTERNAL"
    return (frame_name, timestamp)

def calc_timing_info(elapsed_frames):
    """Each frame is an tuple (frame_name, elapsed_time)"""
    times = {}
    for f in elapsed_frames:
        entry = ()
        fname = f[0]
        elapsed = f[1]
        if (f[0] in times):
            entry = ((times[fname])[0] + elapsed, (times[fname])[1] + 1)
        else:
            entry = (elapsed, 1)
        times[fname] = entry
    by_avg = []
    for fname in times.keys():
        avg = times[fname][0] / times[fname][1]
        by_avg.append((fname, times[fname][0], times[fname][1], avg))
    return by_avg

def display_timing_info (listing, sortby):
    global ATTRIBUTES
    stats = calc_timing_info(listing)
    if (sortby in ATTRIBUTES):
        idx = ATTRIBUTES.index(sortby)
    else:
        idx = 3
    hue = 'cyan'
    locol = colour(hue, 'dark')
    hicol = colour(hue, 'light')
    col = [hicol if n == idx else locol
           for n in range(len(ATTRIBUTES))]

    print (hicol)
    print ("\n-----------------------------------------------")
    print (" _____ _       _             ___       __     ")
    print ("|_   _(_)_ __ (_)_ _  __ _  |_ _|_ _  / _|___ ")
    print ("  | | | | '  \| | ' \/ _` |  | || ' \|  _/ _ \ ")
    print ("  |_| |_|_|_|_|_|_||_\__, | |___|_||_|_| \___/ ")
    print ("                     |___/")
    print ("-----------------------------------------------")
    print (locol)

    for p in sorted(stats, key=(lambda e: e[idx])):
        print (("{:s}{:s}{:s}: {:s}{:f}{:s}ms over {:s}{:d}{:s} call{:s},"+
                " avg: {:s}{:f}{:s}ms")\
               .format(col[0],p[0],locol,
                       col[1],p[1],locol,
                       col[2],p[2],locol,
                       ("" if p[2] == 1 else "s"),
                       col[3],p[3],locol))
    return stats

def abridge_args (fnstring, abridge_len, s):
    fnstring = fnstring.strip()
    splitter = "(" if s == 1 else "->"
    splitat = 1
    if "call (internal)" in fnstring:
        splitter = ")("
    if splitter not in fnstring:
        return fnstring
    parts = fnstring.split(splitter, 1)
    if (len(parts[1]) <= abridge_len):
        return fnstring
    else:
        chunk = parts[1][:abridge_len]
        return parts[0] + splitter + chunk + \
            ("...)" if s == 1 else "...")

def offset(frame_stack, focii):
    # When finding the depth of detail to provide, we want to find this
    # relative to the most recent occurrence of the function in focus.
    # frame_stack[0] is ("MAIN",_)
    fs = [x for (x, _) in frame_stack[::-1]]
    off = 0
    for frame in fs:
        if (frame in focii):
            return off
        else:
            off += 1
    return len(fs)

def overlap(col1, col2):
    return not set(col1).isdisjoint(set(col2))

def term_width():
    try:
        w = int(os.popen("stty size", "r").read().split()[1])
    except:
        w = 0
    if (w == 0):
        w = 60
    return w

def prettify_trace (filename, depth=0, focii=set(["MAIN"]),
                    show_origins=False, enum=False,
                    timing_info="", abridge=1024,
                    quiet=False, ignore=[], show_plugin=False):
    try:
        rows=[r for r in open(filename).readlines()]
        frame_stack = [] # [("MAIN", frame_time(split_rows[0])[1])]
        fmt="{:"+str(int(math.ceil(math.log
            (len(rows), 10))))+"d}"
    except:
        sys.stderr.write("Detected irregularity in data format. Check input.\n")
        exit(1)

    # initialize some variables
    indent=0
    tab=' '*2
    n=0
    off = 0 # offset
    ret_from = ''
    ret_elapsed = 0
    elapsed_frames = []
    active_plugin = ""
    last_n = 0
    width = term_width()
    live_frames = (lambda : [ret_from]+[f[0] for f in frame_stack])

    for row in rows:
        split_row = row.split("(TRACE) ")
        if (not frame_stack):
            frame_stack = [("MAIN", frame_time(split_row)[1])]
        s = step(split_row[1])
        action = abridge_args(split_row[1], abridge, s)
        ft = frame_time(split_row)
        if (show_plugin):
            last_active_plugin = active_plugin
            active_plugin = split_row[0].split(',')[0][1:]+' '
            if (last_active_plugin != "" and active_plugin != last_active_plugin):
                frame_stack[:] = [("MAIN", frame_time(split_row)[1])]
                off = 0
                # raw_input("[HIT ENTER]")
        n += 1 # line number
        if (s == 1): # 1 = call, -1 = ret, 0 = ?
            frame_stack.append(ft)
            off = offset(frame_stack, focii)
        elif (s == -1):
            try:
                off = offset(frame_stack, focii)
                r_ft = frame_stack.pop()
                ret_from = r_ft[0]
                ret_elapsed  = ft[1] - r_ft[1]
                if (ret_elapsed < 0):
                    ## Let's just say these represent glitches in nasl -T
                    ## for now, or are some artifact of threading.
                    ret_elapsed = 0
                if (overlap(focii, live_frames())):
                    elapsed_frames.append((ret_from, ret_elapsed))
            except Exception as e:
                sys.stderr.write(colour('red','light')+ \
                                 "<< call stack anomaly at line",n,">>\n"+ \
                                 str(e) + "\n" + colour('reset'))
                return
        ### Here's the noisy section:
        try:
            if ((not quiet)
                and (depth == 0 or depth >= off)
                and (overlap(focii, live_frames()))
                and (not overlap(ignore, live_frames()))):
                if (n != last_n+1):
                    print (colour('black','light')+'-'*(width), end='\n')
                last_n = n
                if (enum):
                    print (colour('black','light')+active_plugin+\
                           fmt.format(n)+colour('reset'),
                           end=" "),
                print (rainbow(indent)+(tab*max(0,indent))+ \
                       action+colour('reset'), end=" "),
                if (s == -1): # if action is ret
                    print (rainbow(indent,'dark')+"[from {:s}".format(ret_from) + \
                           (" after {:.4f}ms]".format(ret_elapsed) if timing_info else "]")\
                           + colour('reset'))
                    ret_from=''
                elif (show_origins and len(frame_stack) > 1):
                    print (rainbow(indent,'dark')+"[from {:s}]"\
                           .format(frame_stack[-2][0]) + colour('reset'))
                else:
                    print ()
        except IOError: # so that the tool plays nicely with pipes
            exit() 
        ### End of noisy section ###
        indent = max(0, indent + s)
    if (timing_info):
        display_timing_info(elapsed_frames, timing_info)

    return

def attribute_string ():
    global ATTRIBUTES
    s = "<"
    for attr in ATTRIBUTES:
        s += attr
        s += "|"
    s = s[:-1] + ">"
    return s

def main ():
    global COLOUR_ON
    parser = argparse.ArgumentParser(description =
                                     "Reconstruct call stack from nasl -T"+
                                     " trace, and structure trace output "+
                                     " accordingly.")
    parser.add_argument("tracefile", 
                        help="the output file generated by nasl -T")
    parser.add_argument("--depth", "-d", metavar="<calls deep>", type=int,
                        default=0,
                        help="how deep to peer into the call stack, relative"+
                        " to most recent occurrence of focus function.")
    parser.add_argument("--functions", "-f", metavar="<function name>",
                        type=str, action='append',
                        default=[],
                        help="if you would like to restrict the"+
                        " view to just one set of function, list them")
    parser.add_argument("--ignore", "-i", metavar="<function name>",
                        type=str, action='append', default=[],
                        help="if you would like to ignore any functions, "+
                        "specify them here.")
    parser.add_argument("--sources", "-s", action="store_true", default=False,
                      help="display the name of the function from which each"+
                      " function is called")
    parser.add_argument("--timing", "-t", type=str, default="",
                        metavar=attribute_string(),
                        help="specify the attribute by which to sort the timing information")
    parser.add_argument("--enum", "-n", action="store_true", default=False,
                        help="enumerate the trace lines")
    parser.add_argument("--quiet", "-q", action="store_true", default=False)
    parser.add_argument("--abridge", "-a", type=int,
                        default=1024, help="abridge arguments longer "+
                        "than <n> characters", metavar="<n>")
    parser.add_argument("--rainbow", "-r", action="store_true", default=False,
                        help="colour-code the call stack")
    parser.add_argument("--plugin", "-p", action="store_true",
                        help="display the active plugin in left margin")
    args = parser.parse_args()
    COLOUR_ON = args.rainbow
    if (not args.functions):
        args.functions = ["MAIN"]
    # if (len(args.functions) > 1):
    #     args.enum = True
    prettify_trace(filename=args.tracefile,
                   depth=args.depth,
                   focii=set(args.functions),
                   ignore=set(args.ignore),
                   show_origins=args.sources,
                   enum=args.enum,
                   quiet=args.quiet,
                   abridge=args.abridge,
                   show_plugin=args.plugin,
                   timing_info=args.timing)

if __name__ == "__main__":
    main()
