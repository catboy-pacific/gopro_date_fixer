# program to fix date of media taken on GoPro Hero 5 Session.
# gopro has no concept of UTC and writes the local time directly into the "time" fields.
#
# Time fields are:
# [System]        FileModifyDate        usually doesn't change when file is copied
# [System]        FileAccessDate        can be anything
# [System]        FileCreateDate        may change if file is copied
# [QuickTime]     CreateDate            should be in UTC; on GoPro Hero 5 Session it is the local time instead. Time when recording started
# [QuickTime]     ModifyDate            should be in UTC; on GoPro Hero 5 Session it is the local time instead. Time when recording finished
# [Track1]        TrackCreateDate       same as CreateDate for some reason
# [Track1]        TrackModifyDate
# [Track1]        MediaCreateDate
# [Track1]        MediaModifyDate
# [Track2]        TrackCreateDate
# [Track2]        TrackModifyDate
# [Track2]        MediaCreateDate
# [Track2]        MediaModifyDate
# ...

# Issues:
# 1.    [QuickTime] CreateDate, ModifyDate has the LOCAL time recorded, which is interpreted as UTC.
#       Therefore the timezone offset must be subtracted from CreateDate and ModifyDate to have the actual UTC.
#       EXAMPLE: a 1-min video was taken from 18:00 to 18:01 Perth Time (AWST). [QuickTime] CreateDate, ModifyDate is set by GoPro to be 18:00, 18:01.
#               In reality, the video was taken at UTC 10:00 to 10:01. CreateDate, ModifyDate will have the UTC offset of the local time zone (AWST = +8:00)
#               subtracted to calculate the actual UTC date.
#
# 2.    [Track1, 2, ...] TrackCreateDate, TrackModifyDate, MediaCreateDate, MediaModifyDate all must be changed to mirror CreateDate and ModifyDate as well.
#
# 3.    [System] FileModifyDate and FileAccessDate are stamped as local time by camera


# exiftool quirk: writing "04:27:21" to [QuickTime] CreateDate, it is understood as UTC,
# but writing "04:27:21" to [System] FileModifyDate is interpreted as local time of computer (in this case, AWST)
# so when modifying [System] metadata, it is imperative to append "Z" after the timestamp to indicate Zulu time (UTC).

# when changing [System] FileModifyDate, FileAccessDate, FileCreateDate, make sure to specify -System:FileModifyDate (the System part) in args,
# otherwise XMP-xmp FileModifyDate will also be changed.

# GOOD NEWS: simply setting all dates (system, quicktime and track) to UTC/Zulu time (specified with a "Z") will be adequate.


# GoPro photos don't have QuickTime fields, as those are for the MP4 file format. Instead, photos use EXIF:DateTimeOriginal.
# EXIF:DateTimeOriginal is a timezone-naive field and always represents the "local time" the photo was taken
# EXIF:OffsetTimeOriginal is a field added in 2016 representing the UTC offset when photo was taken
# for now, ignore photos

import sys
import exiftool
from datetime import datetime, timedelta, timezone
from timezonefinder import TimezoneFinder

if len(sys.argv) < 3:
    raise Exception("ERROR: Correct format for arguments is 'python date_fixer.py [TIMEZONE_OFFSET (hours decimal)] [filename1] [filename2] [...]'")

try:
    UTC_Offset = float(sys.argv[1])
    UTC_Offset_H = int(UTC_Offset)
    UTC_Offset_M = int(round((UTC_Offset-UTC_Offset_H) * 60))
    deltaDT = timedelta(hours=UTC_Offset_H, minutes=UTC_Offset_M)
    # print("timezone offset is", deltaDT)
except:
    raise Exception("ERROR: second argument must be a number")

# TODO: feature: enter the name of the city, and the program will automatically determine the UTC offset given the local datetime
#           (taking into account daylight savings etc)

files = sys.argv[2:]

with exiftool.ExifTool() as et, exiftool.ExifToolHelper() as eth:
    # read all files - recursive, will handle directories
    # easy solution: terminate all if there is one single incorrect filepath.
    try:
        metadata = eth.get_metadata(files, params=['-r']) # TODO: ADD ERROR CHECKING
    except:
        raise Exception("ERROR: ensure all filepaths are correct")


    # USER SAFETY CHECK: THESE FILES ARE ABOUT TO BE PROCESSED COWABUNGA
    detectedFilenames = [d['SourceFile'] for d in metadata]
    print(f"Following files are found and will be shifted by {UTC_Offset_H} H and {UTC_Offset_M} M: (photos will be skipped)")
    print("\n".join(detectedFilenames))
    prompt = input("Reply 'y' to continue, or any other key to exit:")
    if prompt != 'y':
        print("aborting")
        quit()


    # Process files one by one (there is probably a more efficient way but fuckit, we ball)
    for md in metadata:
        fileName = md['SourceFile']
        # skip if file is a photo (doesn't have quicktime tags)
        # HEIC photos have quicktime tags but yknow, that's kinda on the user if they specify a DIR with stuff they don't plan on changing
        if 'QuickTime:CreateDate' not in md:
            continue
        createDateStr = md['QuickTime:CreateDate']
        modifyDateStr = md['QuickTime:ModifyDate']
        dateStrFormat = '%Y:%m:%d %H:%M:%S%z'

        # print(f'{fileName} has createDate {createDateStr} and modifyDate {modifyDateStr}')

        # pretend this is in UTC (append 'Z" for Zulu), so the datetime object is an 'aware' datetime
        createDateDT = datetime.strptime(createDateStr + 'Z', dateStrFormat)
        modifyDateDT = datetime.strptime(modifyDateStr + 'Z', dateStrFormat)
        # print("parsed dateTime:", createDateDT)

        # apply the timezone offset to get the actual zulu times of creation and modification
        createDateDT -= deltaDT
        modifyDateDT -= deltaDT

        # add zulu timestamp prefix to filename, in format "YYYYMMDDTHHMMSSZ_filename.MP4"
        # filename may contain directory, e.g. ./path/to/filename.MP4
        # therefore name change must be added to final item after splitting with str.split
        zuluString = createDateDT.strftime('%Y%m%dT%H%M%SZ')
        fileNameSplit = fileName.split('/')
        fileNameSplit[-1] = zuluString + '_' + fileNameSplit[-1]
        zuluFileName = '/'.join(fileNameSplit)

        print("processing", zuluFileName)
        # print("create date string to be appended to filename:", createDateDT.strftime(f'%Y%m%dT%H%M%SZ_{fileName}'))
        # print(f'new createDate = {createDateDT} and new modifyDate = {modifyDateDT}')

        # using exiftoolhelper just works better than directly calling et.execute() tbh
        eth.set_tags(
            [fileName],
            tags={
                "FileName": zuluFileName,
                "FileCreateDate": createDateDT,
                "CreateDate": createDateDT,
                "TrackCreateDate": createDateDT,
                "MediaCreateDate": createDateDT,
                "FileModifyDate": modifyDateDT,
                "ModifyDate": modifyDateDT,
                "TrackModifyDate": modifyDateDT,
                "MediaModifyDate": modifyDateDT
            },
            params=["-P"]
        )
        continue